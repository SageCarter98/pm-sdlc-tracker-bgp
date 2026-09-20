"""Page-route auth: same checks as app/deps.py, but returning None instead
of raising HTTPException -- a browser page redirects to /ui/login on a
missing/invalid session, it doesn't render a JSON 401 body."""

from fastapi import Request
from sqlalchemy.orm import Session

from app.deps import SESSION_COOKIE, get_active_membership
from app.models import Membership, User
from app.security import read_session_token


def page_current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if token is None:
        return None
    payload = read_session_token(token)
    if payload is None:
        return None
    user = db.get(User, payload.get("user_id"))
    if user is None or user.token_version != payload.get("tv"):
        return None
    return user


def page_mfa_verified(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if token is None:
        return False
    payload = read_session_token(token)
    return bool(payload and payload.get("mfa_verified"))


def page_membership(db: Session, tenant_id: str, user: User) -> Membership | None:
    """Reuses app/deps.py's get_active_membership directly -- calling it
    with real values instead of its Depends() defaults runs the identical
    tenant-context-then-lookup logic migration 0014 fixed, so a page never
    re-derives (and risks re-breaking) that ordering itself. Returns None on
    the 403 it raises for "not a member" rather than propagating the
    exception -- a page decides what to show for that itself (e.g. the org
    picker), it doesn't want a bare error page."""
    from fastapi import HTTPException

    try:
        return get_active_membership(tenant_id=tenant_id, db=db, user=user)
    except HTTPException:
        return None
