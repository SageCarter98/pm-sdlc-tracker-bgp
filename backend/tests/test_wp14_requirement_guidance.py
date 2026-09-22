"""WP14: optional plain-language guidance on template gates/rules
(Rule.guidance, Rule.evidence_example, GateDefinition.description in
app/rule_engine.py), rendered on the evidence form and gate dashboard pages
a contributor/approver actually uses. Purely descriptive -- never evaluated,
never affects readiness or blocker logic (see rule_engine.py's own
docstring on these fields). This mirrors the same "what to do / evidence to
provide" pattern built into the external KenAddme tracker's own UI
(2026-09-21), but sourced from each tenant's own template, since BGP's
gates are tenant-authored, not a fixed institutional catalogue."""

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


_SCHEMA_WITH_GUIDANCE = {
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
            "description": "WP14-TEST-GATE-PURPOSE: confirm the request is worth pursuing.",
            "rules": [
                {
                    "version": 1,
                    "rule_id": "R1",
                    "class_ids": ["A"],
                    "occurrence_type": "routine",
                    "evidence_kind": "document",
                    "permitted_role_ids": ["tenant_administrator"],
                    "blocker_level": "hard",
                    "guidance": "WP14-TEST-WHAT-TO-DO: write a short intake note.",
                    "evidence_example": "WP14-TEST-EVIDENCE-EXAMPLE: a linked intake ticket.",
                }
            ],
        }
    ],
}

# A second, older-shaped schema with no guidance fields at all -- proves a
# template authored before this feature existed still validates and renders
# cleanly, with no guidance block shown (not an empty/broken one).
_SCHEMA_WITHOUT_GUIDANCE = {
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


def _publish(client, tenant_id, schema, name="WP14 starter"):
    tv = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": name, "schema_json": schema}).json()
    client.post(f"/orgs/{tenant_id}/templates/{tv['template_id']}/versions/{tv['id']}/publish")
    return tv


def _create_project(client, tenant_id, tv):
    return client.post(
        f"/orgs/{tenant_id}/projects", json={"name": "P", "template_version_id": tv["id"], "class_id": "A"}
    ).json()


def test_evidence_form_shows_rule_guidance_when_the_template_supplies_it(ui_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP14 org 1"}).json()["id"]
    tv = _publish(ui_client, tenant_id, _SCHEMA_WITH_GUIDANCE)
    proj = _create_project(ui_client, tenant_id, tv)
    item_id = proj["evidence_items"][0]["id"]

    resp = ui_client.get(f"/ui/orgs/{tenant_id}/evidence/{item_id}")
    assert resp.status_code == 200
    assert "WP14-TEST-WHAT-TO-DO" in resp.text
    assert "WP14-TEST-EVIDENCE-EXAMPLE" in resp.text
    assert "What to do / evidence to provide" in resp.text


def test_gate_dashboard_shows_gate_description_when_the_template_supplies_it(ui_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP14 org 2"}).json()["id"]
    tv = _publish(ui_client, tenant_id, _SCHEMA_WITH_GUIDANCE)
    proj = _create_project(ui_client, tenant_id, tv)
    project_id = proj["project"]["id"]

    resp = ui_client.get(f"/ui/orgs/{tenant_id}/projects/{project_id}/gates")
    assert resp.status_code == 200
    assert "WP14-TEST-GATE-PURPOSE" in resp.text
    assert "What this gate is for" in resp.text


def test_evidence_form_omits_guidance_block_when_template_has_none(ui_client):
    """A template authored before this feature existed must still render
    cleanly -- no broken/empty guidance block, just nothing."""
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP14 org 3"}).json()["id"]
    tv = _publish(ui_client, tenant_id, _SCHEMA_WITHOUT_GUIDANCE)
    proj = _create_project(ui_client, tenant_id, tv)
    item_id = proj["evidence_items"][0]["id"]

    resp = ui_client.get(f"/ui/orgs/{tenant_id}/evidence/{item_id}")
    assert resp.status_code == 200
    assert "What to do / evidence to provide" not in resp.text
