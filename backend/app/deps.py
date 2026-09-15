from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ROLES_REQUIRING_MFA, Membership, Role, User
from app.security import read_session_token

SESSION_COOKIE = "bgp_session"


def get_current_user(
    db: Session = Depends(get_db),
    bgp_session: str | None = Cookie(default=None),
) -> User:
    if bgp_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = read_session_token(bgp_session)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalid or expired")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalid or expired")
    return user


def get_active_membership(
    tenant_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Membership:
    """REQ-003: resolve/verify membership from the authenticated session,
    never from a client-supplied tenant claim alone -- callers pass tenant_id
    from the URL path, and this always re-checks it against real membership
    rows, so a forged or stale claim cannot substitute for one."""
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
) -> User:
    """REQ-002: MFA required for approval authority. Applies to any role in
    ROLES_REQUIRING_MFA, not just 'approver' by name -- sponsors and tenant
    administrators hold approval-adjacent authority too (Blueprint Sec.2)."""
    if Role(membership.role) in ROLES_REQUIRING_MFA and not user.mfa_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "MFA is required for this role before approving")
    return user
