"""IPA02 (docs/DEFECT_REGISTER.md): UI10 membership revocation/role-change
had no backend endpoint at all before this -- settings.html's own hint said
so ("There is no revoke-membership or change-role control here yet -- no
such endpoint exists in the API this page calls"). These tests cover the
new JSON API in app/routers/orgs.py; test_ipa02_membership_settings_ui.py
covers the /ui page built on top of it."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import register_and_login


def _invite_and_accept(admin_client, tenant_id, email, role="contributor"):
    """Creates the invitation as the admin, then accepts it from a SEPARATE
    session actually logged in as `email` -- accept_invitation checks the
    invitation's email against the caller's own session (REQ-038/BGP-F02
    territory: acceptance is not something another account can do on your
    behalf), so accepting via the admin's own client would just 403 silently
    if the caller forgot to check the response, as this file's first draft
    did. Returns the new membership_id from the admin's own access-review."""
    invite = admin_client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": role}).json()
    member_client = TestClient(app)
    register_and_login(member_client, email)
    accept = member_client.post("/invitations/accept", json={"token": invite["token"]})
    assert accept.status_code == 200, accept.text
    membership_id = next(
        row["membership_id"]
        for row in admin_client.get(f"/orgs/{tenant_id}/access-review").json()
        if row["email"] == email
    )
    return membership_id, member_client


def test_admin_can_revoke_a_members_membership(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id, _ = _invite_and_accept(client, tenant_id, "member@example.com")

    resp = client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/revoke")
    assert resp.status_code == 200, resp.text
    assert resp.json()["active"] is False

    review = client.get(f"/orgs/{tenant_id}/access-review").json()
    revoked = next(row for row in review if row["email"] == "member@example.com")
    assert revoked["active"] is False


def test_admin_can_change_a_members_role(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id, _ = _invite_and_accept(client, tenant_id, "member@example.com")

    resp = client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/role", json={"role": "approver"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "approver"

    review = client.get(f"/orgs/{tenant_id}/access-review").json()
    changed = next(row for row in review if row["email"] == "member@example.com")
    assert changed["role"] == "approver"


def test_non_admin_cannot_revoke_or_change_role(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id, member_client = _invite_and_accept(client, tenant_id, "member@example.com")

    resp = member_client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/revoke")
    assert resp.status_code == 403

    resp = member_client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/role", json={"role": "approver"})
    assert resp.status_code == 403


def test_cannot_revoke_the_only_active_tenant_administrator(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id = next(row["membership_id"] for row in client.get(f"/orgs/{tenant_id}/access-review").json())

    resp = client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/revoke")
    assert resp.status_code == 409, resp.text

    review = client.get(f"/orgs/{tenant_id}/access-review").json()
    assert review[0]["active"] is True


def test_cannot_demote_the_only_active_tenant_administrator(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id = next(row["membership_id"] for row in client.get(f"/orgs/{tenant_id}/access-review").json())

    resp = client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/role", json={"role": "contributor"})
    assert resp.status_code == 409, resp.text

    review = client.get(f"/orgs/{tenant_id}/access-review").json()
    assert review[0]["role"] == "tenant_administrator"


def test_a_second_administrator_can_be_revoked_or_demoted(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id, _ = _invite_and_accept(client, tenant_id, "second-admin@example.com", role="tenant_administrator")

    resp = client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/role", json={"role": "contributor"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "contributor"


def test_revoking_an_already_revoked_membership_is_rejected(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id, _ = _invite_and_accept(client, tenant_id, "member@example.com")

    first = client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/revoke")
    assert first.status_code == 200
    second = client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/revoke")
    assert second.status_code == 409


def test_revoked_member_loses_active_membership_access(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]
    membership_id, member_client = _invite_and_accept(client, tenant_id, "member@example.com")
    assert member_client.get(f"/orgs/{tenant_id}/me").status_code == 200

    client.post(f"/orgs/{tenant_id}/memberships/{membership_id}/revoke")

    assert member_client.get(f"/orgs/{tenant_id}/me").status_code == 403


def test_unknown_membership_id_returns_404(client):
    register_and_login(client, "admin@example.com")
    tenant_id = client.post("/orgs", json={"name": "Org"}).json()["id"]

    resp = client.post(f"/orgs/{tenant_id}/memberships/does-not-exist/revoke")
    assert resp.status_code == 404

    resp = client.post(f"/orgs/{tenant_id}/memberships/does-not-exist/role", json={"role": "approver"})
    assert resp.status_code == 404


def test_a_membership_from_another_tenant_is_not_visible_here(client):
    register_and_login(client, "admin@example.com")
    tenant_a = client.post("/orgs", json={"name": "Org A"}).json()["id"]
    tenant_b = client.post("/orgs", json={"name": "Org B"}).json()["id"]
    membership_id_in_b = next(row["membership_id"] for row in client.get(f"/orgs/{tenant_b}/access-review").json())

    resp = client.post(f"/orgs/{tenant_a}/memberships/{membership_id_in_b}/revoke")
    assert resp.status_code == 404
