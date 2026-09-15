import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, get_current_user, require_mfa, require_role
from app.models import Invitation, Membership, Role, Tenant, User

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


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    # SQLite (test fixture only -- production target is PostgreSQL, REQ-007)
    # drops tzinfo on round-trip; treat a naive value as UTC rather than
    # letting the comparison below raise.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.post("/orgs", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(payload: CreateOrgRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Tenant:
    """REQ-001: explicit organisation membership before project access --
    the creator becomes tenant_administrator of their own new tenant, not of
    any tenant they didn't create or weren't invited to."""
    tenant = Tenant(name=payload.name)
    db.add(tenant)
    db.flush()
    db.add(Membership(tenant_id=tenant.id, user_id=user.id, role=Role.TENANT_ADMINISTRATOR.value))
    db.commit()
    db.refresh(tenant)
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
    _membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
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
    db.commit()
    return InviteOut(invitation_id=invitation.id, token=token)


@router.post("/invitations/accept", response_model=MembershipOut)
def accept_invitation(
    payload: AcceptInvitationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Membership:
    """REQ-038: invited user reaches the intended project after sign-in."""
    invitation = db.query(Invitation).filter(Invitation.token_hash == _hash_token(payload.token)).one_or_none()
    if invitation is None or invitation.accepted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found or already used")
    if _as_utc(invitation.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_410_GONE, "Invitation expired -- request another")
    if invitation.email.lower() != user.email.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invitation was issued to a different address")

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
    db.commit()
    db.refresh(membership)
    return membership


@router.get("/orgs/{tenant_id}/me", response_model=MembershipOut)
def my_membership(membership: Membership = Depends(get_active_membership)) -> Membership:
    """REQ-003: active tenant resolved from session and re-verified here,
    never trusted from a client-supplied claim."""
    return membership


@router.get("/orgs/{tenant_id}/approval-gate-check")
def approval_gate_check(tenant_id: str, user: User = Depends(require_mfa)) -> dict:
    """REQ-002 enforcement placeholder: proves the MFA gate for
    approval-adjacent roles works before WP07's actual decision endpoints
    exist to protect. Delete once POST /api/occurrences/{id}/decisions
    (Blueprint Sec.5.3/5.4) is built and carries this same dependency."""
    return {"ok": True}
