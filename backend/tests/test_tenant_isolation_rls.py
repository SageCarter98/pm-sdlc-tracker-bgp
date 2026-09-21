"""REQ-007/008/009: PostgreSQL RLS actually enforced through the restricted
bgp_app role. These tests need a real local Postgres with the WP04 migration
applied (backend/scripts/setup_postgres_dev.sql, then `alembic upgrade
head`) -- they skip cleanly everywhere else rather than failing CI on
environments without it configured.

REQ-009 requires this suite to run as a *blocking* CI check (see
.github/workflows/ci.yml for the Postgres service container -- wired since
WP04; a private remote exists since 2026-09-16 but nothing has been pushed
yet, so this still has never actually executed as a real CI run) and to
demonstrate detection of a seeded leak --
`test_seeded_leak_in_rls_policy_is_detected` below does that: it commits a
deliberately permissive policy, proves cross-tenant rows become visible
through bgp_app, then restores the original policy and re-verifies isolation
before the test ends (via `pytest.fail` in a `finally`, not a bare assert --
if the restore itself silently failed, the database would be left weakened
for every later test/run, so that failure has to be loud).
"""

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
def two_tenants_with_memberships():
    """Seed two tenants with one membership row each, as bgp_owner. bgp_owner
    is NOT exempt from RLS here -- FORCE ROW LEVEL SECURITY (migration
    0002_wp04_rls.py) applies to the table owner too (a real bug was found
    and fixed 2026-09-17: bgp_owner had accidentally been created as an
    actual Postgres superuser, which unconditionally bypasses RLS
    regardless of FORCE; superuser status was removed, and every owner-seeded
    fixture in this project, this one included, needed SET LOCAL
    app.tenant_id before each tenant-owned INSERT as a result -- see
    TRACKER.md for the full story). `tenants`/`users` have no RLS at all
    (WP04's own migration docstring: 'global identities, not tenant-owned
    rows'), so only the `memberships` inserts below need the tenant context
    set immediately before each one."""
    tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    with _owner_engine.begin() as conn:
        for tid, name in [(tenant_a, "Tenant A"), (tenant_b, "Tenant B")]:
            conn.execute(
                text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"), {"id": tid, "name": name}
            )
        for uid, email in [(user_a, f"{user_a}@example.com"), (user_b, f"{user_b}@example.com")]:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled) "
                    "VALUES (:id, :email, 'x', false, now(), false)"
                ),
                {"id": uid, "email": email},
            )
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_a})
        conn.execute(
            text(
                "INSERT INTO memberships (id, tenant_id, user_id, role, active, created_at) "
                "VALUES (:id, :tid, :uid, 'contributor', true, now())"
            ),
            {"id": str(uuid.uuid4()), "tid": tenant_a, "uid": user_a},
        )
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_b})
        conn.execute(
            text(
                "INSERT INTO memberships (id, tenant_id, user_id, role, active, created_at) "
                "VALUES (:id, :tid, :uid, 'contributor', true, now())"
            ),
            {"id": str(uuid.uuid4()), "tid": tenant_b, "uid": user_b},
        )
    yield {"tenant_a": tenant_a, "tenant_b": tenant_b, "user_a": user_a, "user_b": user_b}
    with _owner_engine.begin() as conn:
        # DELETE on memberships is RLS-governed too (FOR ALL, no command
        # restriction in migration 0002_wp04_rls.py) -- one tenant context
        # at a time, same reasoning as the inserts above.
        for tid in (tenant_a, tenant_b):
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(text("DELETE FROM memberships WHERE tenant_id = :tid"), {"tid": tid})
        conn.execute(text("DELETE FROM users WHERE id IN (:a, :b)"), {"a": user_a, "b": user_b})
        conn.execute(text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": tenant_a, "b": tenant_b})


def test_missing_tenant_context_returns_no_rows(two_tenants_with_memberships):
    """TST-007: missing tenant context returns no owned records."""
    with _app_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM memberships")).fetchall()
    assert rows == []


def test_cross_tenant_row_is_invisible_even_by_direct_id(two_tenants_with_memberships):
    """TST-009 spirit: a service query naming tenant B's own user_id directly
    still returns nothing while app.tenant_id is set to tenant A -- RLS, not
    application code, is what's blocking it."""
    t = two_tenants_with_memberships
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT * FROM memberships WHERE user_id = :uid"), {"uid": t["user_b"]}).fetchall()
    assert rows == []


def test_correct_tenant_context_sees_only_its_own_row(two_tenants_with_memberships):
    t = two_tenants_with_memberships
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT tenant_id FROM memberships")).fetchall()
    assert [r.tenant_id for r in rows] == [t["tenant_a"]]


def test_pooled_connection_reset_between_tenants(two_tenants_with_memberships):
    """TST-008: reuse one connection across two tenants -- SET LOCAL inside
    separate transactions must not leak the first tenant's context into the
    second."""
    t = two_tenants_with_memberships
    with _app_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
            rows_a = conn.execute(text("SELECT tenant_id FROM memberships")).fetchall()
        with conn.begin():
            rows_unset = conn.execute(text("SELECT tenant_id FROM memberships")).fetchall()
        with conn.begin():
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_b"]})
            rows_b = conn.execute(text("SELECT tenant_id FROM memberships")).fetchall()

    assert [r.tenant_id for r in rows_a] == [t["tenant_a"]]
    assert rows_unset == []
    assert [r.tenant_id for r in rows_b] == [t["tenant_b"]]


def test_app_role_cannot_disable_row_level_security(two_tenants_with_memberships):
    """REQ-007: the restricted role cannot bypass RLS or act as the table
    owner -- it must not even be able to turn RLS off."""
    with pytest.raises(Exception):
        with _app_engine.begin() as conn:
            conn.execute(text("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY"))


def test_app_role_cannot_alter_or_drop_the_table(two_tenants_with_memberships):
    with pytest.raises(Exception):
        with _app_engine.begin() as conn:
            conn.execute(text("ALTER TABLE memberships ADD COLUMN sneaky text"))


_ORIGINAL_POLICY = "tenant_id = current_setting('app.tenant_id', true)"


def test_seeded_leak_in_rls_policy_is_detected(two_tenants_with_memberships):
    """REQ-009: prove this suite actually catches a real tenant-isolation
    leak, not just that it passes when nothing is broken. Deliberately
    replaces the memberships policy with a permissive one (USING true), shows
    that cross-tenant rows leak through bgp_app exactly as a real
    misconfiguration would, then restores the real policy and re-checks
    isolation holds again -- so the seeded leak never outlives this test."""
    t = two_tenants_with_memberships
    with _owner_engine.begin() as conn:
        conn.execute(text("ALTER POLICY memberships_tenant_isolation ON memberships USING (true) WITH CHECK (true)"))

    try:
        with _app_engine.connect() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
            leaked_tenants = {r.tenant_id for r in conn.execute(text("SELECT tenant_id FROM memberships")).fetchall()}
        assert t["tenant_b"] in leaked_tenants, (
            "seeded leak was not observed -- the weakened policy did not take "
            "effect, so this test cannot claim to demonstrate detection"
        )
    finally:
        with _owner_engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER POLICY memberships_tenant_isolation ON memberships "
                    f"USING ({_ORIGINAL_POLICY}) WITH CHECK ({_ORIGINAL_POLICY})"
                )
            )

    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT tenant_id FROM memberships")).fetchall()
    if [r.tenant_id for r in rows] != [t["tenant_a"]]:
        pytest.fail(
            "policy restore after the seeded leak did not fully take effect -- "
            "memberships RLS may still be weakened, investigate before running "
            "anything else against this database"
        )
