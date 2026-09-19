from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ROLES_REQUIRING_MFA, Membership, Role, User
from app.security import read_session_token

SESSION_COOKIE = "bgp_session"
# BGP-F01: separate cookie for the password-verified/second-factor-pending
# state -- never read by get_current_user, so a pre-auth token can never be
# used as if it were a real session, no matter what claims it carries.
PREAUTH_SESSION_COOKIE = "bgp_preauth"


def get_current_user(
    db: Session = Depends(get_db),
    bgp_session: str | None = Cookie(default=None),
) -> User:
    if bgp_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = read_session_token(bgp_session)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalid or expired")
    user = db.get(User, payload.get("user_id"))
    # BGP-F01: a session signed before a factor reset/replacement (which
    # bumps users.token_version -- app/routers/mfa.py) must stop working,
    # not keep being honoured just because its signature still verifies.
    if user is None or user.token_version != payload.get("tv"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalid or expired")
    return user


def get_session_mfa_verified(bgp_session: str | None = Cookie(default=None)) -> bool:
    """BGP-F01: whether THIS session actually completed a second-factor
    challenge. Deliberately independent of get_current_user/users.mfa_enabled
    -- an account-level 'MFA is enrolled' flag is not evidence that the
    session presenting it ever passed a second-factor check."""
    if bgp_session is None:
        return False
    payload = read_session_token(bgp_session)
    return bool(payload and payload.get("mfa_verified"))


def get_active_membership(
    tenant_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Membership:
    """REQ-003: resolve/verify membership from the authenticated session,
    never from a client-supplied tenant claim alone -- callers pass tenant_id
    from the URL path, and this always re-checks it against real membership
    rows, so a forged or stale claim cannot substitute for one.

    Tenant context is set from the CLAIMED tenant_id (the URL path) BEFORE
    the membership row is even looked up -- not after. `memberships` itself
    is RLS-protected (`tenant_id = current_setting('app.tenant_id', true)`,
    fail-closed with no context set), so querying it before setting context
    always returned zero rows against real Postgres, rejecting every
    legitimate member with "No active membership" -- a request could never
    succeed at all. This is safe: setting context to an arbitrary claimed
    tenant_id grants no access by itself, it only scopes what the FOLLOWING
    query can see; the actual authorization is still the membership check
    below, which correctly finds nothing (403) for a tenant the caller isn't
    really in."""
    if db.get_bind().dialect.name == "postgresql":
        # REQ-008: reset tenant context per transaction, not per pooled
        # connection. SET LOCAL only lasts until the transaction ends
        # (commit, rollback, or this request's session.close()), so the next
        # request to reuse this physical connection -- for any tenant --
        # starts clean; it never inherits this request's setting. No-op
        # outside Postgres (SQLite in tests has no RLS to protect, and no
        # SET LOCAL syntax).
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})

    membership = (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.user_id == user.id, Membership.active.is_(True))
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active membership in this organisation")

    return membership


def require_role(*allowed: Role):
    """REQ-004: enforce project/template role permissions at each operation."""

    def _check(membership: Membership = Depends(get_active_membership)) -> Membership:
        if Role(membership.role) not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Role does not permit this operation")
        return membership

    return _check


def require_mfa(
    user: User = Depends(get_current_user),
    membership: Membership = Depends(get_active_membership),
    mfa_verified: bool = Depends(get_session_mfa_verified),
) -> User:
    """REQ-002: MFA required for approval authority. Applies to any role in
    ROLES_REQUIRING_MFA, not just 'approver' by name -- sponsors and tenant
    administrators hold approval-adjacent authority too (Blueprint Sec.2).

    BGP-F01 fix: gated on `mfa_verified` (this session actually completed a
    second-factor challenge -- app/routers/mfa.py's verify/login-verify are
    the only places that ever set it) AND `user.mfa_enabled` (the account
    still has an active factor right now), not on `user.mfa_enabled` alone.
    A password-only session, or a session left over from before a factor
    reset, satisfies neither."""
    if Role(membership.role) in ROLES_REQUIRING_MFA and not (mfa_verified and user.mfa_enabled):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "MFA verification is required for this session before approving")
    return user
