"""IPA02 (docs/DEFECT_REGISTER.md): the /ui counterpart to
test_ipa02_membership_revocation.py's JSON API. settings.html used to say
"There is no revoke-membership or change-role control here yet -- no such
endpoint exists in the API this page calls" -- these tests cover the actual
HTML form controls (app/templates/settings.html) and the two new page routes
(app/webapp/router.py: settings_revoke_submit, settings_role_submit) built on
top of that API. Same live-Postgres requirement as test_wp13_webapp_new_pages.py
-- these routes go through the RLS-scoped get_db the SQLite `client` fixture
doesn't provide."""

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


def _register_and_login_ui(client, email, password="correct horse battery staple"):
    resp = client.post(
        "/ui/register",
        data={"email": email, "password": password, "confirm_password": password},
    )
    assert resp.status_code in (200, 303), resp.text
    return resp


@pytest.fixture()
def ui_client():
    from fastapi.testclient import TestClient

    from app.main import app

    assert app.dependency_overrides == {}, "this test needs the REAL Postgres get_db, not the SQLite fixture"
    return TestClient(app, follow_redirects=True)


def _invite_and_accept_ui(admin_client, tenant_id, email, role="contributor"):
    """Same two-session shape as the JSON API test's _invite_and_accept --
    accept_invitation checks the invitation's email against the caller's own
    session, so it has to happen from a client logged in as `email`."""
    from fastapi.testclient import TestClient

    from app.main import app

    invite = admin_client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": role}).json()
    member_client = TestClient(app, follow_redirects=True)
    _register_and_login_ui(member_client, email)
    accept = member_client.post("/invitations/accept", json={"token": invite["token"]})
    assert accept.status_code == 200, accept.text
    return member_client


def test_settings_page_shows_revoke_and_role_controls_for_an_active_member(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "IPA02 UI org 1"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    _invite_and_accept_ui(ui_client, tenant_id, member_email)

    membership_id = next(
        row["membership_id"]
        for row in ui_client.get(f"/orgs/{tenant_id}/access-review").json()
        if row["email"] == member_email
    )

    resp = ui_client.get(f"/ui/orgs/{tenant_id}/settings")
    assert resp.status_code == 200
    assert f"/ui/orgs/{tenant_id}/settings/memberships/{membership_id}/revoke" in resp.text
    assert f"/ui/orgs/{tenant_id}/settings/memberships/{membership_id}/role" in resp.text
    assert "There is no revoke-membership or change-role control" not in resp.text


def test_admin_can_revoke_a_membership_from_the_settings_page(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "IPA02 UI org 2"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    _invite_and_accept_ui(ui_client, tenant_id, member_email)
    membership_id = next(
        row["membership_id"]
        for row in ui_client.get(f"/orgs/{tenant_id}/access-review").json()
        if row["email"] == member_email
    )

    resp = ui_client.post(f"/ui/orgs/{tenant_id}/settings/memberships/{membership_id}/revoke")
    assert resp.status_code == 200
    assert "Membership revoked." in resp.text

    review = ui_client.get(f"/orgs/{tenant_id}/access-review").json()
    revoked = next(row for row in review if row["email"] == member_email)
    assert revoked["active"] is False
    # REQ-047: the revoked row must still be visible in the review table,
    # not vanish -- a review that can't see past revocations can't confirm
    # they actually took effect.
    assert member_email in resp.text


def test_admin_can_change_a_role_from_the_settings_page(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "IPA02 UI org 3"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    _invite_and_accept_ui(ui_client, tenant_id, member_email)
    membership_id = next(
        row["membership_id"]
        for row in ui_client.get(f"/orgs/{tenant_id}/access-review").json()
        if row["email"] == member_email
    )

    resp = ui_client.post(f"/ui/orgs/{tenant_id}/settings/memberships/{membership_id}/role", data={"role": "approver"})
    assert resp.status_code == 200
    assert "Role updated." in resp.text

    review = ui_client.get(f"/orgs/{tenant_id}/access-review").json()
    changed = next(row for row in review if row["email"] == member_email)
    assert changed["role"] == "approver"


def test_non_admin_cannot_revoke_or_change_role_via_the_settings_page(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "IPA02 UI org 4"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    member_client = _invite_and_accept_ui(ui_client, tenant_id, member_email)
    membership_id = next(
        row["membership_id"]
        for row in ui_client.get(f"/orgs/{tenant_id}/access-review").json()
        if row["email"] == member_email
    )

    resp = member_client.post(f"/ui/orgs/{tenant_id}/settings/memberships/{membership_id}/revoke")
    assert resp.status_code == 200
    assert "Role does not permit this operation" in resp.text

    resp = member_client.post(
        f"/ui/orgs/{tenant_id}/settings/memberships/{membership_id}/role", data={"role": "approver"}
    )
    assert resp.status_code == 200
    assert "Role does not permit this operation" in resp.text

    # Neither attempt actually changed anything.
    review = ui_client.get(f"/orgs/{tenant_id}/access-review").json()
    untouched = next(row for row in review if row["email"] == member_email)
    assert untouched["active"] is True
    assert untouched["role"] == "contributor"


def test_cannot_revoke_the_only_active_tenant_administrator_via_the_settings_page(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "IPA02 UI org 5"}).json()["id"]
    membership_id = next(row["membership_id"] for row in ui_client.get(f"/orgs/{tenant_id}/access-review").json())

    resp = ui_client.post(f"/ui/orgs/{tenant_id}/settings/memberships/{membership_id}/revoke")
    assert resp.status_code == 200
    assert "only active tenant administrator" in resp.text

    review = ui_client.get(f"/orgs/{tenant_id}/access-review").json()
    assert review[0]["active"] is True


def test_unknown_membership_id_shows_an_honest_error_on_the_settings_page(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "IPA02 UI org 6"}).json()["id"]

    resp = ui_client.post(f"/ui/orgs/{tenant_id}/settings/memberships/does-not-exist/revoke")
    assert resp.status_code == 200
    assert "Membership not found" in resp.text
