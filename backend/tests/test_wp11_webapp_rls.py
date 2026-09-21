"""WP11: the webapp page routes (app/webapp/router.py) are the first code
in this project that needs to keep reading the database AFTER catching an
HTTPException raised mid-request -- every existing JSON endpoint just lets
FastAPI turn the exception into a response and stops. That exposed two real
defects only a real Postgres run with real page-to-page navigation could
show (SQLite has no RLS to break against, and no prior test drove these
routes through actual HTTP):

1. `create_evidence_revision`'s own success path re-queried the DB (via
   get_evidence_item) AFTER its db.commit() -- SET LOCAL app.tenant_id had
   already gone out of scope with that commit, so the query silently saw
   nothing under RLS and raised "Evidence item not found", masking a
   revision that had, in fact, just been saved. Fixed by building the
   response from data read BEFORE the commit.
2. The webapp's own decide-submission error handler re-queried the
   occurrence/project AFTER catching an HTTPException from
   decisions.py's _deny() (a legitimate control that commits an audit
   trail for a denied decision before raising, e.g. BGP-F02's separation-
   of-duties check) -- same root cause, different call site. Fixed with
   app/webapp/router.py's _reset_tenant_context helper.

Both found manually driving the real /ui pages in a browser against real
Postgres while building WP11 (2026-09-20) -- these tests lock them in."""

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


def _seed_hard_gate_project(client, tenant_id):
    schema = {
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
    tv = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "T", "schema_json": schema}).json()
    client.post(f"/orgs/{tenant_id}/templates/{tv['template_id']}/versions/{tv['id']}/publish")
    proj = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "P", "template_version_id": tv["id"], "class_id": "A"},
    ).json()
    return proj


def test_evidence_revision_page_reflects_the_just_saved_revision(ui_client):
    """Regression test for defect 1 above: submitting the guided evidence
    form must show the NEW revision immediately, not a masking 404."""
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP11 RLS test org"}).json()["id"]
    proj = _seed_hard_gate_project(ui_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]

    resp = ui_client.post(
        f"/ui/orgs/{tenant_id}/evidence/{item_id}/submit",
        data={"status": "Complete", "reference": "design-doc-1"},
    )
    assert resp.status_code == 200, resp.text
    assert "There is a problem" not in resp.text, "the fixed post-commit query bug would surface here"
    assert "design-doc-1" in resp.text
    assert resp.text.count('data-status="Complete"') >= 1


def test_decide_page_recovers_cleanly_after_a_denied_decision(ui_client):
    """Regression test for defect 2 above: after decisions.py's _deny()
    commits an audit trail and raises (here: self-only approval requires a
    compensating review, BGP-F02), the error page must render the ACTUAL
    reason -- not an unrelated, uncaught 'Occurrence not found' from a
    stale-tenant-context re-query in the error-recovery path itself."""
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP11 RLS test org 2"}).json()["id"]
    proj = _seed_hard_gate_project(ui_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]
    project_id = proj["project"]["id"]
    occurrence_id = proj["occurrences"][0]["id"]

    ui_client.post(
        f"/ui/orgs/{tenant_id}/evidence/{item_id}/submit",
        data={"status": "Complete", "reference": "d"},
    )

    import pyotp

    enroll = ui_client.post("/auth/mfa/enroll").json()
    secret = pyotp.parse_uri(enroll["provisioning_uri"]).secret
    ui_client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()})

    decide_url = f"/ui/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide"
    page = ui_client.get(decide_url)
    digest = page.text.split('name="manifest_digest" value="')[1].split('"')[0]

    resp = ui_client.post(decide_url, data={"outcome": "Approve", "manifest_digest": digest})
    assert resp.status_code == 200, resp.text
    assert "There is a problem" in resp.text
    assert "compensating review" in resp.text, (
        f"expected the real self-approval denial reason, got something else: {resp.text[:2000]}"
    )

    # And the page must still be genuinely usable afterward -- a fresh,
    # permitted outcome succeeds through the same route.
    resp2 = ui_client.post(decide_url, data={"outcome": "Hold", "manifest_digest": digest})
    assert resp2.status_code == 200, resp2.text
    assert "Decision recorded" in resp2.text
