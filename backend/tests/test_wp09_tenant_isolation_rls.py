"""WP09: basic tenant isolation on export_jobs -- these rows hold a full
archive of a tenant's governance data, so cross-tenant visibility here
would be a significant leak. Same repeated-proof rationale as
test_wp06/07/08_tenant_isolation_rls.py (threat model finding T1.4):
migration-generated policies aren't assumed safe until checked directly
against Postgres for the tables that actually matter to check."""
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
def two_tenants_with_exports():
    tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    export_a, export_b = str(uuid.uuid4()), str(uuid.uuid4())

    with _owner_engine.begin() as conn:
        for tid, name in [(tenant_a, "Tenant A"), (tenant_b, "Tenant B")]:
            conn.execute(text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"), {"id": tid, "name": name})
        for uid, email in [(user_a, f"{user_a}@example.com"), (user_b, f"{user_b}@example.com")]:
            conn.execute(
                text("INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled) VALUES (:id, :email, 'x', false, now(), false)"),
                {"id": uid, "email": email},
            )
        for eid, tid, uid in [(export_a, tenant_a, user_a), (export_b, tenant_b, user_b)]:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(
                text(
                    "INSERT INTO export_jobs (id, tenant_id, requested_by_user_id, status, format_version, archive_json, archive_digest, created_at) "
                    "VALUES (:id, :tid, :uid, 'complete', 1, CAST('{}' AS JSON), 'x', now())"
                ),
                {"id": eid, "tid": tid, "uid": uid},
            )

    yield {"tenant_a": tenant_a, "tenant_b": tenant_b, "export_a": export_a, "export_b": export_b}

    with _owner_engine.begin() as conn:
        for tid, eid in [(tenant_a, export_a), (tenant_b, export_b)]:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(text("DELETE FROM export_jobs WHERE id = :id"), {"id": eid})
        conn.execute(text("DELETE FROM users WHERE id IN (:a, :b)"), {"a": user_a, "b": user_b})
        conn.execute(text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": tenant_a, "b": tenant_b})


def test_missing_tenant_context_returns_no_export_rows(two_tenants_with_exports):
    with _app_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM export_jobs")).fetchall()
    assert rows == []


def test_cross_tenant_export_is_invisible_even_by_direct_id(two_tenants_with_exports):
    t = two_tenants_with_exports
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT * FROM export_jobs WHERE id = :id"), {"id": t["export_b"]}).fetchall()
    assert rows == []


def test_correct_tenant_context_sees_only_its_own_export(two_tenants_with_exports):
    t = two_tenants_with_exports
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT id FROM export_jobs")).fetchall()
    assert [r.id for r in rows] == [t["export_a"]]
