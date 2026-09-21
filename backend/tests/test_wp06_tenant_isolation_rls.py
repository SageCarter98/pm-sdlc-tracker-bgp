"""WP06 extension of the WP04 RLS proof (REQ-007) onto the new `projects`
table. test_tenant_isolation_rls.py's own threat-model follow-up
(docs/wp02/threat_model_and_privacy_assessment.md, finding T1.4) flagged that
the seeded-leak proof had only ever been run against `memberships` -- this
repeats both the basic isolation check and the seeded-leak proof against
`projects` so WP06's tenant-owned tables aren't taken on faith. The other
four WP06 tables (project_memberships, gate_occurrences, evidence_items,
evidence_revisions) use the identical migration-generated policy shape
(0004_wp06_projects.py applies the same USING/WITH CHECK clause to all five
in one loop) -- not independently re-proven here, which is a smaller gap than
before this file existed, not a closed one.
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
def two_tenants_with_projects():
    """Seed two tenants, each with a user, a published template/version, and
    one project -- all as bgp_owner. bgp_owner is NOT exempt from RLS (see
    test_tenant_isolation_rls.py's two_tenants_with_memberships docstring
    for the 2026-09-17 superuser-bug story): templates, template_versions
    and projects are all RLS-governed with a tenant-matching WITH CHECK
    (template_versions' policy has no explicit WITH CHECK, so Postgres
    reuses its USING clause -- which still requires app.tenant_id to match
    via the parent template lookup), so each tenant's rows are seeded under
    their own SET LOCAL app.tenant_id, one tenant fully at a time, rather
    than interleaved. tenants/users have no RLS (WP04's own migration:
    'global identities, not tenant-owned rows')."""
    tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    template_a, template_b = str(uuid.uuid4()), str(uuid.uuid4())
    version_a, version_b = str(uuid.uuid4()), str(uuid.uuid4())
    project_a, project_b = str(uuid.uuid4()), str(uuid.uuid4())

    minimal_schema = '{"schema_version": 1, "tracks": ["Delivery"], "classes": ["A"], "roles": ["contributor"], "statuses": ["Not started"], "decision_outcomes": ["Approve"], "gates": []}'

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

        for tid, tpl_id, ver_id, pid, uid in [
            (tenant_a, template_a, version_a, project_a, user_a),
            (tenant_b, template_b, version_b, project_b, user_b),
        ]:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(
                text("INSERT INTO templates (id, tenant_id, name, created_at) VALUES (:id, :tid, 'T', now())"),
                {"id": tpl_id, "tid": tid},
            )
            conn.execute(
                text(
                    "INSERT INTO template_versions (id, template_id, version_number, schema_json, status, "
                    "created_by_user_id, created_at, published_at) "
                    "VALUES (:id, :tpl, 1, CAST(:schema AS JSON), 'published', :uid, now(), now())"
                ),
                {"id": ver_id, "tpl": tpl_id, "schema": minimal_schema, "uid": uid},
            )
            conn.execute(
                text(
                    "INSERT INTO projects (id, tenant_id, name, template_version_id, class_id, owner_user_id, created_at) "
                    "VALUES (:id, :tid, 'P', :ver, 'A', :uid, now())"
                ),
                {"id": pid, "tid": tid, "ver": ver_id, "uid": uid},
            )

    yield {"tenant_a": tenant_a, "tenant_b": tenant_b, "project_a": project_a, "project_b": project_b}

    with _owner_engine.begin() as conn:
        for tid, ver_id, tpl_id in [(tenant_a, version_a, template_a), (tenant_b, version_b, template_b)]:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(text("DELETE FROM projects WHERE tenant_id = :tid"), {"tid": tid})
            conn.execute(text("DELETE FROM template_versions WHERE id = :id"), {"id": ver_id})
            conn.execute(text("DELETE FROM templates WHERE id = :id"), {"id": tpl_id})
        conn.execute(text("DELETE FROM users WHERE id IN (:a, :b)"), {"a": user_a, "b": user_b})
        conn.execute(text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": tenant_a, "b": tenant_b})


def test_missing_tenant_context_returns_no_project_rows(two_tenants_with_projects):
    with _app_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM projects")).fetchall()
    assert rows == []


def test_cross_tenant_project_is_invisible_even_by_direct_id(two_tenants_with_projects):
    t = two_tenants_with_projects
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT * FROM projects WHERE id = :pid"), {"pid": t["project_b"]}).fetchall()
    assert rows == []


def test_correct_tenant_context_sees_only_its_own_project(two_tenants_with_projects):
    t = two_tenants_with_projects
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT id FROM projects")).fetchall()
    assert [r.id for r in rows] == [t["project_a"]]


_ORIGINAL_POLICY = "tenant_id = current_setting('app.tenant_id', true)"


def test_seeded_leak_in_projects_rls_policy_is_detected(two_tenants_with_projects):
    """Same proof as test_tenant_isolation_rls.py's memberships version, run
    against `projects` -- see that file's docstring for why this repetition
    matters (T1.4 in the threat model)."""
    t = two_tenants_with_projects
    with _owner_engine.begin() as conn:
        conn.execute(text("ALTER POLICY projects_tenant_isolation ON projects USING (true) WITH CHECK (true)"))

    try:
        with _app_engine.connect() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
            leaked_ids = {r.id for r in conn.execute(text("SELECT id FROM projects")).fetchall()}
        assert t["project_b"] in leaked_ids, "seeded leak was not observed -- the weakened policy did not take effect"
    finally:
        with _owner_engine.begin() as conn:
            conn.execute(
                text(
                    f"ALTER POLICY projects_tenant_isolation ON projects USING ({_ORIGINAL_POLICY}) WITH CHECK ({_ORIGINAL_POLICY})"
                )
            )

    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_a"]})
        rows = conn.execute(text("SELECT id FROM projects")).fetchall()
    if [r.id for r in rows] != [t["project_a"]]:
        pytest.fail("policy restore after the seeded leak did not fully take effect on `projects`")
