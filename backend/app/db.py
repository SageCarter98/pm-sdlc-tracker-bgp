from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, future=True)
# expire_on_commit=False: SQLAlchemy's default expires every ORM attribute
# after commit() and transparently re-queries on next access -- but that
# re-query runs in a NEW transaction, after SET LOCAL app.tenant_id (scoped
# to the transaction that just ended) is gone. Against real Postgres RLS,
# any "create X, commit, then read X.some_field for the response" pattern
# (used across nearly every router -- almost every tenant-owned table has
# RLS, see the ENABLE ROW LEVEL SECURITY migrations) would silently see zero
# rows on that re-query and raise ObjectDeletedError, as if the just-created
# row had vanished. Discovered the same session as the org-bootstrap RLS
# ordering fix (migration 0014) -- same root cause (tenant context that
# doesn't outlive the transaction it was set in), different trigger. Kept
# object attributes as committed is correct here regardless of RLS: each
# request gets its own session, closed at the end of that request
# (app/db.py's get_db), so there is no cross-request staleness to guard
# against by expiring.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
