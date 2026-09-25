"""REQ-038 / BGP-IPA-001 finding: "MFA/recovery are real, but
`accept_invitation` has no matching HTML template; grep-confirmed no
invitation-landing page exists anywhere in `backend/app/templates/`"
(TRACKER.md, 2026-09-24 pass). The JSON API (`POST /invitations/accept`) has
always worked -- see test_identity.py -- but nothing under `/ui` let an
invited user actually follow an emailed-style link and land anywhere.

Fixed: `GET/POST /ui/invitations/accept` plus `invitation_accept.html`, and a
`next` redirect target threaded through login/register/mfa-login-verify so
signing in from the landing page returns the user there automatically
instead of dropping them at the generic org picker -- REQ-038's own verify
text: "An invited user reaches the intended project after sign-in".

Same live-Postgres-only pattern as test_wp11_webapp_rls.py/
test_wp13_webapp_new_pages.py: `/ui` routes exercise real RLS/tenant-context
handling that SQLite has nothing to break against."""

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


def _new_client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app, follow_redirects=True)


def test_signed_out_visitor_signs_in_via_next_and_lands_on_the_invited_org(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "REQ-038 org"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    invite = ui_client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": member_email, "role": "contributor"}
    ).json()

    member_client = _new_client()
    landing_url = f"/ui/invitations/accept?token={invite['token']}"

    # Not signed in yet: the landing page must offer sign-in/register, not
    # error out, and must not silently accept anything.
    page = member_client.get(landing_url)
    assert page.status_code == 200
    assert "Log in" in page.text
    assert "Create an account" in page.text
    assert f"next=/ui/invitations/accept?token={invite['token']}" in page.text

    # Registering (a brand-new account, so no MFA hop) via the link's own
    # `next` must return the user to the invitation landing page, not the
    # generic org picker.
    resp = member_client.post(
        "/ui/register",
        data={
            "email": member_email,
            "password": "correct horse battery staple",
            "confirm_password": "correct horse battery staple",
            "next": landing_url,
        },
    )
    assert resp.status_code == 200, resp.text
    assert "Join this organisation" in resp.text, (
        f"expected to land back on the invitation page after registering, got: {resp.text[:2000]}"
    )

    accept = member_client.post("/ui/invitations/accept", data={"token": invite["token"]})
    assert accept.status_code == 200, accept.text
    assert "My work" in accept.text or "my-work" in str(accept.url), (
        f"REQ-038: must reach the intended org's work list after accepting, landed on {accept.url}"
    )

    settings_resp = member_client.get(f"/ui/orgs/{tenant_id}/settings")
    assert settings_resp.status_code == 200
    assert "Invite a member" not in settings_resp.text  # contributor, not admin


def test_already_signed_in_user_sees_a_deliberate_confirm_step_not_an_auto_accept(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "REQ-038 org 2"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    invite = ui_client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": member_email, "role": "contributor"}
    ).json()

    member_client = _new_client()
    _register_and_login_ui(member_client, member_email)

    landing_url = f"/ui/invitations/accept?token={invite['token']}"
    page = member_client.get(landing_url)
    assert page.status_code == 200
    assert "Join this organisation" in page.text
    # GET must never itself accept -- confirmed by checking no membership
    # exists yet via the settings page redirecting to login/orgs for a
    # non-member... simpler: the JSON list of my orgs must not include it.
    my_orgs = member_client.get("/me/orgs").json()
    assert not any(o["tenant_id"] == tenant_id for o in my_orgs), "GET must not have a side effect"

    accept = member_client.post("/ui/invitations/accept", data={"token": invite["token"]})
    assert accept.status_code == 200, accept.text
    my_orgs_after = member_client.get("/me/orgs").json()
    assert any(o["tenant_id"] == tenant_id for o in my_orgs_after)


def test_expired_or_reused_invitation_shows_an_honest_error_not_a_crash(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "REQ-038 org 3"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    invite = ui_client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": member_email, "role": "contributor"}
    ).json()

    member_client = _new_client()
    _register_and_login_ui(member_client, member_email)
    first = member_client.post("/ui/invitations/accept", data={"token": invite["token"]})
    assert first.status_code == 200

    # Reusing the same (now-accepted) token must render the landing page's
    # own error state, not raise an unhandled exception.
    second = member_client.post("/ui/invitations/accept", data={"token": invite["token"]})
    assert second.status_code == 200, second.text
    assert "Already a member" in second.text or "not found or already used" in second.text.lower()
