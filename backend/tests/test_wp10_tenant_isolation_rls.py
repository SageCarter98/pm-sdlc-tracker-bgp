"""WP10: basic tenant isolation on drafts. Owner-scoping within a tenant
(never visible to another user in the SAME tenant) is enforced at the
application layer, not RLS (app/models.py's Draft docstring explains why);
this file proves the layer RLS *does* cover -- cross-tenant isolation --
same repeated-proof rationale as test_wp06/07/08/09 (threat model finding
T1.4)."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings

try:
    _owner_engine = create_engine(settings.migration_database_url, future=True)
    with _owner_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    _app_engine = create_engine(settings.database_url, future=True)
    with _app_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    POSTGRES_AVAILABLE = True
except OperationalError:
    POSTGRES_AVAILABLE = False

pytestmark = pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app not configured")


@pytest.fixture()
def two_tenants_with_drafts():
    tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    draft_a, draft_b = str(uuid.uuid4()), str(uuid.uuid4())

    with _owner_engine.begin() as conn:
        for tid, name in [(tenant_a, "Tenant A"), (tenant_b, "Tenant B")]:
            conn.execute(
                text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"), {"id": tid, "name": name}
            )
        for uid, email in [(user_a, f"{user_a}@example.com"), (user_b, f"{user_b}@example.com")]:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled) VALUES (:id, :email, 'x', false, now(), false)"
                ),
                {"id": uid, "email": email},
            )
        for did, tid, uid in [(draft_a, tenant_a, user_a), (draft_b, tenant_b, user_b)]:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(
                text(
                    "INSERT INTO drafts (id, tenant_id, user_id, draft_key, form_data, revision, created_at, updated_at) "
                    "VALUES (:id, :tid, :uid, 'test-key', CAST('{}' AS JSON), 1, now(), now())"
                ),
                {"id": did, "tid": tid, "uid": uid},
            )

    yield {"tenant_a": tenant_a, "tenant_b": tenant_b, "draft_a": draft_a, "draft_b": draft_b}

    with _owner_engine.begin() as conn:
        for tid, did in [(tenant_a, draft_a), (tenant_b, draft_b)]:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(text("DELETE FROM drafts WHERE id = :id"), {"id": did})
        conn.execute(text("DELETE FROM users WHERE id IN (:a, :b)"), {"a": user_a, "b": user_b})
        conn.execute(text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": tenant_a, "b": tenant_b})


def test_missing_tenant_context_returns_no_draft_rows(two_tenants_with_drafts):
    with _app_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM drafts")).fetchall()
    assert rows == []


def test_cross_tenant_draft_is_invisible_even_by_direct_id(two_tenants_with_drafts):
    t = two_tenants_with_drafts
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT * FROM drafts WHERE id = :id"), {"id": t["draft_b"]}).fetchall()
    assert rows == []


def test_correct_tenant_context_sees_only_its_own_draft(two_tenants_with_drafts):
    t = two_tenants_with_drafts
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT id FROM drafts")).fetchall()
    assert [r.id for r in rows] == [t["draft_a"]]
