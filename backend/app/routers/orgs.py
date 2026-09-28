import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, get_current_user, require_mfa, require_role
from app.models import Invitation, Membership, Role, Tenant, User
from app.security_log import log_security_event

router = APIRouter(tags=["orgs"])

INVITATION_TTL = timedelta(days=7)


class CreateOrgRequest(BaseModel):
    name: str


class OrgOut(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: EmailStr
    role: Role


class InviteOut(BaseModel):
    invitation_id: str
    token: str  # returned directly: no mail infra in this prototype (WP03 gap, tracked)


class AcceptInvitationRequest(BaseModel):
    token: str


class MembershipOut(BaseModel):
    tenant_id: str
    role: str

    model_config = {"from_attributes": True}


class MyOrgOut(BaseModel):
    tenant_id: str
    tenant_name: str
    role: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    # SQLite (test fixture only -- production target is PostgreSQL, REQ-007)
    # drops tzinfo on round-trip; treat a naive value as UTC rather than
    # letting the comparison below raise.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.post("/orgs", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(
    payload: CreateOrgRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Tenant:
    """REQ-001: explicit organisation membership before project access --
    the creator becomes tenant_administrator of their own new tenant, not of
    any tenant they didn't create or weren't invited to.

    Org bootstrap fix: `memberships` is RLS-protected, fail-closed with no
    `app.tenant_id` set -- there is no existing membership dependency to set
    it here (this IS the request that creates the first one), so this
    endpoint sets it itself, from the just-generated tenant.id, before the
    INSERT. Without this the INSERT was rejected outright
    (`new row violates row-level security policy`) against real Postgres --
    nobody could ever create an organisation there at all."""
    tenant = Tenant(name=payload.name)
    db.add(tenant)
    db.flush()
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant.id})
    db.add(Membership(tenant_id=tenant.id, user_id=user.id, role=Role.TENANT_ADMINISTRATOR.value))
    db.commit()
    # No db.refresh() -- expire_on_commit=False (app/db.py) already keeps
    # every field set in Python before commit; tenants carries no RLS
    # (it isn't tenant-owned data) so this one was merely unnecessary, not
    # broken, but the same reasoning applies everywhere in this codebase.
    return tenant


@router.post(
    "/orgs/{tenant_id}/invitations",
    response_model=InviteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    tenant_id: str,
    payload: InviteRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> InviteOut:
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        tenant_id=tenant_id,
        email=payload.email,
        role=payload.role.value,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + INVITATION_TTL,
    )
    db.add(invitation)
    log_security_event(
        db,
        "invitation_created",
        user_id=membership.user_id,
        tenant_id=tenant_id,
        detail={"invited_email": payload.email, "role": payload.role.value},
    )
    db.commit()
    return InviteOut(invitation_id=invitation.id, token=token)


@router.post("/invitations/accept", response_model=MembershipOut)
def accept_invitation(
    payload: AcceptInvitationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Membership:
    """REQ-038: invited user reaches the intended project after sign-in.

    Org bootstrap fix, two parts. First: the initial `Invitation` lookup is
    BY TOKEN, deliberately without knowing the tenant yet -- that is the
    whole point of a self-contained invitation link. But `invitations` is
    RLS-protected the same way `memberships` is, and there is no tenant
    context to set beforehand here (unlike get_active_membership, the
    tenant isn't known until AFTER this exact query finds it). Migration
    0014 adds a second, narrowly-scoped permissive SELECT policy on
    `invitations` keyed on `app.invitation_lookup_token_hash` -- Postgres
    combines multiple permissive policies for the same command with OR, so
    a caller who sets this to the token hash they're presenting can find
    that ONE row regardless of tenant context, without weakening the
    tenant-isolation policy for anything else (INSERT/UPDATE/DELETE, or a
    SELECT that doesn't set this). Knowing the unguessable, high-entropy
    token IS the authorization to read that row -- the same trust
    assumption an emailed invitation link already relies on. Second: once
    the invitation's real tenant_id is known, context is set from it before
    the `existing`-membership check and the INSERT below -- the same
    ordering bug create_org had, for the same reason (no prior
    get_active_membership dependency to have set it already)."""
    token_hash = _hash_token(payload.token)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL app.invitation_lookup_token_hash = :h"), {"h": token_hash})
    invitation = db.query(Invitation).filter(Invitation.token_hash == token_hash).one_or_none()
    if invitation is None or invitation.accepted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found or already used")
    if _as_utc(invitation.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_410_GONE, "Invitation expired -- request another")
    if invitation.email.lower() != user.email.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invitation was issued to a different address")

    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": invitation.tenant_id})

    existing = (
        db.query(Membership)
        .filter(Membership.tenant_id == invitation.tenant_id, Membership.user_id == user.id)
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member of this organisation")

    membership = Membership(tenant_id=invitation.tenant_id, user_id=user.id, role=invitation.role)
    invitation.accepted_at = datetime.now(timezone.utc)
    db.add(membership)
    log_security_event(
        db, "invitation_accepted", user_id=user.id, tenant_id=invitation.tenant_id, detail={"role": invitation.role}
    )
    db.commit()
    # No db.refresh() -- see app/db.py's SessionLocal docstring
    # (expire_on_commit=False): every field here was already set in Python
    # before commit, and memberships is RLS-protected, so a post-commit
    # refresh would run with no tenant context left and raise -- this was
    # STILL broken after migration 0014's ordering fix (which only fixed
    # the INSERT itself), found 2026-09-20 while building WP11.
    return membership


@router.get("/orgs/{tenant_id}/me", response_model=MembershipOut)
def my_membership(membership: Membership = Depends(get_active_membership)) -> Membership:
    """REQ-003: active tenant resolved from session and re-verified here,
    never trusted from a client-supplied claim."""
    return membership


@router.get("/me/orgs", response_model=list[MyOrgOut])
def my_orgs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[MyOrgOut]:
    """WP11 frontend entry point: which organisations can this user act in,
    before any tenant_id is known to put in a URL -- get_active_membership
    can't help here, it requires a tenant_id already claimed. Uses migration
    0015's narrow self-lookup policy (see there for why the ordinary
    per-tenant RLS policy structurally can't answer this in one query).
    `tenants` itself carries no RLS (it isn't tenant-owned data, see WP04
    migration's TENANT_OWNED_TABLES), so the name lookup needs no context."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL app.member_user_id = :uid"), {"uid": user.id})
    rows = db.query(Membership).filter(Membership.user_id == user.id, Membership.active.is_(True)).all()
    tenant_names = {t.id: t.name for t in db.query(Tenant).filter(Tenant.id.in_([m.tenant_id for m in rows])).all()}
    return [MyOrgOut(tenant_id=m.tenant_id, tenant_name=tenant_names.get(m.tenant_id, ""), role=m.role) for m in rows]


@router.get("/orgs/{tenant_id}/approval-gate-check")
def approval_gate_check(tenant_id: str, user: User = Depends(require_mfa)) -> dict:
    """REQ-002 enforcement placeholder: proves the MFA gate for
    approval-adjacent roles works before WP07's actual decision endpoints
    exist to protect. Delete once POST /api/occurrences/{id}/decisions
    (Blueprint Sec.5.3/5.4) is built and carries this same dependency."""
    return {"ok": True}


class AccessReviewEntryOut(BaseModel):
    membership_id: str
    user_id: str
    email: str
    role: str
    active: bool
    member_since: datetime


@router.get("/orgs/{tenant_id}/access-review", response_model=list[AccessReviewEntryOut])
def access_review(
    tenant_id: str,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> list[AccessReviewEntryOut]:
    """WP12/REQ-047: 'review access quarterly' -- this is the mechanism
    (a complete, current membership listing for a tenant administrator to
    actually review) not the cadence itself, which stays an operational
    practice this endpoint doesn't schedule (same honest split as WP08's
    checkpoint-frequency note: the capability exists, running it on a
    real quarterly cycle is a process decision, not code). Includes
    inactive (revoked) memberships too -- a review that only shows who
    currently has access can't confirm past revocations actually took
    effect."""
    rows = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.tenant_id == tenant_id)
        .order_by(Membership.created_at)
        .all()
    )
    return [
        AccessReviewEntryOut(
            membership_id=m.id, user_id=u.id, email=u.email, role=m.role, active=m.active, member_since=m.created_at
        )
        for m, u in rows
    ]


class RoleChangeRequest(BaseModel):
    role: Role


def _get_membership_or_404(db: Session, tenant_id: str, membership_id: str) -> Membership:
    membership = (
        db.query(Membership).filter(Membership.id == membership_id, Membership.tenant_id == tenant_id).one_or_none()
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    return membership


def _active_tenant_administrator_count(db: Session, tenant_id: str, exclude_membership_id: str) -> int:
    return (
        db.query(Membership)
        .filter(
            Membership.tenant_id == tenant_id,
            Membership.role == Role.TENANT_ADMINISTRATOR.value,
            Membership.active.is_(True),
            Membership.id != exclude_membership_id,
        )
        .count()
    )


def _membership_out(db: Session, membership: Membership) -> AccessReviewEntryOut:
    user = db.get(User, membership.user_id)
    return AccessReviewEntryOut(
        membership_id=membership.id,
        user_id=membership.user_id,
        email=user.email,
        role=membership.role,
        active=membership.active,
        member_since=membership.created_at,
    )


@router.post("/orgs/{tenant_id}/memberships/{membership_id}/role", response_model=AccessReviewEntryOut)
def change_membership_role(
    tenant_id: str,
    membership_id: str,
    payload: RoleChangeRequest,
    db: Session = Depends(get_db),
    actor: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> AccessReviewEntryOut:
    """UI10/FE-014: role changes are a tenant_administrator-only operation
    (docs/DEFECT_REGISTER.md IPA02 -- previously unbuilt). Never allowed to
    leave a tenant with zero active administrators: nobody would be left who
    could ever undo it, invite anyone else, or run the next access review."""
    target = _get_membership_or_404(db, tenant_id, membership_id)
    if not target.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot change the role of a revoked membership")

    old_role = target.role
    if (
        old_role == Role.TENANT_ADMINISTRATOR.value
        and payload.role is not Role.TENANT_ADMINISTRATOR
        and _active_tenant_administrator_count(db, tenant_id, exclude_membership_id=target.id) == 0
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot change this member's role: they are the only active tenant administrator",
        )

    target.role = payload.role.value
    log_security_event(
        db,
        "membership_role_changed",
        user_id=actor.user_id,
        tenant_id=tenant_id,
        detail={
            "membership_id": target.id,
            "target_user_id": target.user_id,
            "old_role": old_role,
            "new_role": target.role,
        },
    )
    db.commit()
    return _membership_out(db, target)


@router.post("/orgs/{tenant_id}/memberships/{membership_id}/revoke", response_model=AccessReviewEntryOut)
def revoke_membership(
    tenant_id: str,
    membership_id: str,
    db: Session = Depends(get_db),
    actor: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> AccessReviewEntryOut:
    """UI10/FE-014 (docs/DEFECT_REGISTER.md IPA02 -- previously unbuilt).
    Revocation never deletes the row -- same pattern as REQ-021's exception
    revoke -- so access-review's own 'includes inactive memberships too'
    claim stays true after a real revocation happens through this endpoint,
    not just when a row is seeded inactive directly in a test."""
    target = _get_membership_or_404(db, tenant_id, membership_id)
    if not target.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already revoked")

    if (
        target.role == Role.TENANT_ADMINISTRATOR.value
        and _active_tenant_administrator_count(db, tenant_id, exclude_membership_id=target.id) == 0
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot revoke this member: they are the only active tenant administrator",
        )

    target.active = False
    log_security_event(
        db,
        "membership_revoked",
        user_id=actor.user_id,
        tenant_id=tenant_id,
        detail={"membership_id": target.id, "target_user_id": target.user_id, "role": target.role},
    )
    db.commit()
    return _membership_out(db, target)
