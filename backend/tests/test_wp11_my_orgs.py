"""WP11: GET /me/orgs (needed by the new frontend's login landing page --
DEC04 resolved, see TRACKER.md) and migration 0015's narrow self-lookup RLS
policy it depends on."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from tests.conftest import register_and_login


def test_lists_every_org_the_user_belongs_to(client):
    register_and_login(client, "founder@tenant-a.example")
    tenant_a = client.post("/orgs", json={"name": "Tenant A"}).json()["id"]
    tenant_b = client.post("/orgs", json={"name": "Tenant B"}).json()["id"]

    resp = client.get("/me/orgs")
    assert resp.status_code == 200, resp.text
    seen = {row["tenant_id"]: row for row in resp.json()}
    assert set(seen) == {tenant_a, tenant_b}
    assert seen[tenant_a]["tenant_name"] == "Tenant A"
    assert seen[tenant_a]["role"] == "tenant_administrator"


def test_user_with_no_memberships_sees_an_empty_list(client):
    register_and_login(client, "orphan@tenant-a.example")
    resp = client.get("/me/orgs")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


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


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app not configured")
def test_memberships_self_lookup_policy_cannot_see_another_users_rows():
    """Raw-SQL proof of migration 0015's policy shape, independent of the
    endpoint: setting app.member_user_id to user A's id must return ONLY
    user A's membership rows, never user B's -- even with no app.tenant_id
    set at all, and even though both rows are otherwise-ordinary tenant-
    isolated data in the same table."""
    tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    membership_a, membership_b = str(uuid.uuid4()), str(uuid.uuid4())

    with _owner_engine.begin() as conn:
        for tid, name in [(tenant_a, "Tenant A"), (tenant_b, "Tenant B")]:
            conn.execute(
                text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
                {"id": tid, "name": name},
            )
        for uid, email in [
            (user_a, f"{user_a}@example.com"),
            (user_b, f"{user_b}@example.com"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled) "
                    "VALUES (:id, :email, 'x', false, now(), false)"
                ),
                {"id": uid, "email": email},
            )
        for mid, tid, uid in [
            (membership_a, tenant_a, user_a),
            (membership_b, tenant_b, user_b),
        ]:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
            conn.execute(
                text(
                    "INSERT INTO memberships (id, tenant_id, user_id, role, active, created_at) "
                    "VALUES (:id, :tid, :uid, 'tenant_administrator', true, now())"
                ),
                {"id": mid, "tid": tid, "uid": uid},
            )

    try:
        with _app_engine.connect() as conn:
            conn.execute(text("SET LOCAL app.member_user_id = :uid"), {"uid": user_a})
            rows = conn.execute(text("SELECT id, user_id FROM memberships")).fetchall()
        assert [r.id for r in rows] == [membership_a], "self-lookup must return only the matching user's own row"

        with _app_engine.connect() as conn:
            rows = conn.execute(text("SELECT id FROM memberships")).fetchall()
        assert rows == [], "no app.member_user_id and no app.tenant_id set must still return nothing"
    finally:
        with _owner_engine.begin() as conn:
            for tid, mid in [(tenant_a, membership_a), (tenant_b, membership_b)]:
                conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tid})
                conn.execute(text("DELETE FROM memberships WHERE id = :id"), {"id": mid})
            conn.execute(
                text("DELETE FROM users WHERE id IN (:a, :b)"),
                {"a": user_a, "b": user_b},
            )
            conn.execute(
                text("DELETE FROM tenants WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
