"""REQ-035 / BGP-IPA-001 finding IPA03: the `/ui` decide route generated a
fresh `uuid.uuid4()` idempotency key on every POST instead of reusing the one
tied to the rendered form -- so "drop the response after commit; recovery
displays the existing decision without creating another" (REQ-035's own
verify text) could never actually happen through the webapp. A browser that
resubmitted the exact same form after losing the response would always look
like a brand-new request to decisions.py's idempotency check, landing on the
confusing "Occurrence already has decision ..." 409 instead of the decision
it had, in fact, just recorded.

Fixed: `decide_page` (GET) mints one idempotency key per render and embeds it
in a hidden form field; `decide_submit` (POST) uses that field's value
instead of generating its own; a re-render after a denial/error mints a
*fresh* key (see router.py's comment there) so a genuinely different
follow-up attempt is never mistaken for a stale retry of the first one.

This file proves the recovery half specifically: resubmitting the identical
rendered form (same key, same outcome, same manifest_digest) after the first
submission already committed returns the SAME decision, not a duplicate or
an error -- the same live-Postgres-only pattern as test_wp11_webapp_rls.py
and test_wp13_webapp_new_pages.py, since this route's RLS/tenant-context
handling only exercises for real against actual Postgres."""

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


def _seed_project(client, tenant_id):
    tv = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "T", "schema_json": _SCHEMA}).json()
    client.post(f"/orgs/{tenant_id}/templates/{tv['template_id']}/versions/{tv['id']}/publish")
    return client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "P", "template_version_id": tv["id"], "class_id": "A"},
    ).json()


def test_resubmitting_the_same_rendered_form_recovers_the_existing_decision_not_a_duplicate(ui_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "REQ-035 org"}).json()["id"]
    proj = _seed_project(ui_client, tenant_id)
    project_id = proj["project"]["id"]
    occurrence_id = proj["occurrences"][0]["id"]

    import pyotp

    enroll = ui_client.post("/auth/mfa/enroll").json()
    secret = pyotp.parse_uri(enroll["provisioning_uri"]).secret
    ui_client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()})

    decide_url = f"/ui/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide"
    page = ui_client.get(decide_url)
    digest = page.text.split('name="manifest_digest" value="')[1].split('"')[0]
    key = page.text.split('name="idempotency_key" value="')[1].split('"')[0]
    form = {"outcome": "Hold", "manifest_digest": digest, "idempotency_key": key}

    first = ui_client.post(decide_url, data=form)
    assert first.status_code == 200, first.text
    assert "Decision recorded" in first.text
    decision_id = first.text.split("<dt>Decision id</dt>\n  <dd>")[1].split("</dd>")[0]

    # Simulate the response having been dropped after the server actually
    # committed: the browser has only the original rendered decide.html (same
    # hidden idempotency_key, same outcome, same manifest_digest) and
    # resubmits it verbatim.
    retry = ui_client.post(decide_url, data=form)
    assert retry.status_code == 200, retry.text
    assert "There is a problem" not in retry.text, (
        f"recovery must show the existing decision, not an error: {retry.text[:2000]}"
    )
    assert "Decision recorded" in retry.text
    retry_decision_id = retry.text.split("<dt>Decision id</dt>\n  <dd>")[1].split("</dd>")[0]
    assert retry_decision_id == decision_id, "the retry must return the SAME decision, never a second one"

    # And it must be genuinely the same row, not two rows that happen to
    # render identically.
    decisions = ui_client.get(f"/orgs/{tenant_id}/projects/{project_id}/decisions").json()
    matching = [d for d in decisions if d["occurrence_id"] == occurrence_id]
    assert len(matching) == 1, f"expected exactly one decision on this occurrence, got {len(matching)}: {matching}"


def test_changing_the_answer_after_a_fresh_page_load_gets_a_new_key_and_is_not_blocked(ui_client):
    """A real second decide-page load (not a raw resubmit of the same form)
    must mint a NEW idempotency key -- otherwise a user who reloads the page
    and picks a different outcome would collide with decisions.py's
    "Idempotency-Key already used for a different request" check."""
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "REQ-035 org 2"}).json()["id"]
    proj = _seed_project(ui_client, tenant_id)
    project_id = proj["project"]["id"]
    occurrence_id = proj["occurrences"][0]["id"]

    decide_url = f"/ui/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide"

    page1 = ui_client.get(decide_url)
    key1 = page1.text.split('name="idempotency_key" value="')[1].split('"')[0]
    page2 = ui_client.get(decide_url)
    key2 = page2.text.split('name="idempotency_key" value="')[1].split('"')[0]
    assert key1 != key2, "each decide-page render must mint its own idempotency key"
