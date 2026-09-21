"""WP13: the four new /ui page routes (project creation, gate readiness
dashboard, audit history, organisation settings) call straight into
app/routers/*.py the same way WP11's pages do -- see test_wp11_webapp_rls.py
for why that means a real Postgres run through real HTTP is the only thing
that actually exercises the RLS-context handling these routes add on top of
the plain JSON endpoints (list_occurrences, list_decisions,
list_published_versions all read tables RLS protects)."""

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


_SCHEMA = {
    "schema_version": 1,
    "tracks": ["Delivery"],
    "classes": ["A"],
    "roles": ["tenant_administrator"],
    "statuses": ["Not started", "In progress", "Complete"],
    "decision_outcomes": ["Approve", "Hold"],
    "gates": [
        {
            "gate_id": "G1",
            "name": "Intake",
            "sequence": 1,
            "class_ids": ["A"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "R1",
                    "class_ids": ["A"],
                    "occurrence_type": "routine",
                    "evidence_kind": "document",
                    "permitted_role_ids": ["tenant_administrator"],
                    "blocker_level": "hard",
                }
            ],
        }
    ],
}


def _publish_starter(client, tenant_id, name="WP13 starter"):
    tv = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": name, "schema_json": _SCHEMA}).json()
    client.post(f"/orgs/{tenant_id}/templates/{tv['template_id']}/versions/{tv['id']}/publish")
    return tv


def test_project_creation_page_lists_published_starter_and_creates_project(ui_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP13 org 1"}).json()["id"]
    tv = _publish_starter(ui_client, tenant_id)

    form_page = ui_client.get(f"/ui/orgs/{tenant_id}/projects/new")
    assert form_page.status_code == 200
    assert "WP13 starter" in form_page.text
    assert "classes: A" in form_page.text

    resp = ui_client.post(
        f"/ui/orgs/{tenant_id}/projects/new",
        data={"name": "My first project", "template_version_id": tv["id"], "class_id": "A"},
    )
    assert resp.status_code == 200, resp.text
    assert "My work" in resp.text  # redirected to /ui/orgs/{tenant_id}/my-work

    projects = ui_client.get(f"/orgs/{tenant_id}/projects").json()
    assert any(p["name"] == "My first project" for p in projects)


def test_project_creation_rejects_unknown_class_without_creating_a_partial_project(ui_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP13 org 2"}).json()["id"]
    tv = _publish_starter(ui_client, tenant_id)

    resp = ui_client.post(
        f"/ui/orgs/{tenant_id}/projects/new",
        data={"name": "Bad project", "template_version_id": tv["id"], "class_id": "NoSuchClass"},
    )
    assert resp.status_code == 200
    assert "There is a problem" in resp.text
    projects = ui_client.get(f"/orgs/{tenant_id}/projects").json()
    assert not any(p["name"] == "Bad project" for p in projects)


def test_gate_dashboard_lists_occurrence_and_links_into_decide(ui_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP13 org 3"}).json()["id"]
    tv = _publish_starter(ui_client, tenant_id)
    proj = ui_client.post(
        f"/orgs/{tenant_id}/projects", json={"name": "P", "template_version_id": tv["id"], "class_id": "A"}
    ).json()
    project_id = proj["project"]["id"]
    occurrence_id = proj["occurrences"][0]["id"]

    resp = ui_client.get(f"/ui/orgs/{tenant_id}/projects/{project_id}/gates")
    assert resp.status_code == 200
    assert "G1" in resp.text
    assert f"/ui/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide" in resp.text
    assert "hard" in resp.text  # unresolved hard blocker on the seeded evidence item


def test_project_history_shows_a_recorded_decision_and_its_supersession(ui_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP13 org 4"}).json()["id"]
    tv = _publish_starter(ui_client, tenant_id)
    proj = ui_client.post(
        f"/orgs/{tenant_id}/projects", json={"name": "P", "template_version_id": tv["id"], "class_id": "A"}
    ).json()
    project_id = proj["project"]["id"]
    occurrence_id = proj["occurrences"][0]["id"]

    import pyotp

    enroll = ui_client.post("/auth/mfa/enroll").json()
    secret = pyotp.parse_uri(enroll["provisioning_uri"]).secret
    ui_client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()})

    decide_url = f"/ui/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide"
    page = ui_client.get(decide_url)
    digest = page.text.split('name="manifest_digest" value="')[1].split('"')[0]
    ui_client.post(decide_url, data={"outcome": "Hold", "manifest_digest": digest})

    resp = ui_client.get(f"/ui/orgs/{tenant_id}/projects/{project_id}/history")
    assert resp.status_code == 200
    assert "Hold" in resp.text
    assert digest in resp.text


def test_mfa_enrolment_keeps_the_session_usable_afterward(ui_client):
    """Regression test for a real bug found 2026-09-20 driving MFA enrolment
    through an actual browser: mfa_enroll_verify_submit renders
    mfa_enrolled.html directly (to show recovery codes) instead of returning
    the RedirectResponse mfa_router.verify() set its reissued, bumped-
    token_version session cookie on -- so the browser kept its stale
    pre-enrolment cookie and the very next request got silently logged out
    by page_current_user's token_version check. Fixed by copying the
    Set-Cookie header across in app/webapp/router.py."""
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)

    import pyotp

    enroll = ui_client.post("/auth/mfa/enroll").json()
    secret = pyotp.parse_uri(enroll["provisioning_uri"]).secret
    verify_resp = ui_client.post("/ui/mfa/enroll/verify", data={"code": pyotp.TOTP(secret).now()})
    assert verify_resp.status_code == 200, verify_resp.text
    assert "Recovery codes" in verify_resp.text

    # The bug: this next request, using whatever cookie the client now has,
    # would silently bounce to the login page instead of succeeding.
    orgs_resp = ui_client.get("/ui/orgs")
    assert orgs_resp.status_code == 200
    assert "Log in" not in orgs_resp.text
    assert "Your organisations" in orgs_resp.text


def test_settings_page_hides_admin_controls_from_a_non_admin_member(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP13 org 5"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    invite = ui_client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": member_email, "role": "contributor"}
    ).json()

    # A second, unrelated session: register as the invited contributor and
    # accept, then check their own settings page never renders the
    # tenant_administrator-only membership/invite controls.
    from fastapi.testclient import TestClient

    from app.main import app

    member_client = TestClient(app, follow_redirects=True)
    _register_and_login_ui(member_client, member_email)
    accept = member_client.post("/invitations/accept", json={"token": invite["token"]})
    assert accept.status_code == 200, accept.text

    resp = member_client.get(f"/ui/orgs/{tenant_id}/settings")
    assert resp.status_code == 200
    assert "Invite a member" not in resp.text
    assert "Membership and access review" not in resp.text

    # And the tenant administrator's own settings page DOES show them.
    admin_resp = ui_client.get(f"/ui/orgs/{tenant_id}/settings")
    assert "Invite a member" in admin_resp.text
    assert member_email in admin_resp.text
