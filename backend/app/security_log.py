"""WP12/REQ-047: minimal, append-style helper for writing to
SecurityLogEvent. Callers still own the transaction (this only calls
db.add, never db.commit) -- see each call site in app/routers/auth.py,
app/routers/mfa.py and app/routers/orgs.py for what triggers each event
and what ends up in `detail` (email only where genuinely useful for a
self-service security history; never a password or code value)."""
from sqlalchemy.orm import Session

from app.models import SecurityLogEvent


def log_security_event(
    db: Session,
    event_type: str,
    *,
    user_id: str | None = None,
    tenant_id: str | None = None,
    detail: dict | None = None,
) -> None:
    db.add(SecurityLogEvent(user_id=user_id, tenant_id=tenant_id, event_type=event_type, detail=detail))
