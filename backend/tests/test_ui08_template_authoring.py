"""UI08 (docs/DEFECT_REGISTER.md IPA02): guided template authoring. Before
this, template authoring (templates.py's create/import/fork/update_draft/
publish) was API-only -- no /ui page existed, and DEC07 (rule vocabulary)
being Decided (2026-09-25/27, see TRACKER.md) removed the last blocker on
building it. Same live-Postgres requirement as the other IPA02/UI09 webapp
test files -- these routes go through the RLS-scoped get_db the SQLite
`client` fixture doesn't provide."""

import json
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
    from fastapi.testclient import TestClient

    from app.main import app

    invite = admin_client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": role}).json()
    member_client = TestClient(app, follow_redirects=True)
    _register_and_login_ui(member_client, email)
    accept = member_client.post("/invitations/accept", json={"token": invite["token"]})
    assert accept.status_code == 200, accept.text
    return member_client


def _create_blank_draft(client, tenant_id, name="UI08 draft"):
    resp = client.post(f"/ui/orgs/{tenant_id}/templates", data={"name": name})
    assert resp.status_code == 200, resp.text
    versions = client.get(f"/orgs/{tenant_id}/templates").json()
    template_id = next(t["id"] for t in versions if t["name"] == name)
    version = client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions").json()[0]
    return template_id, version["id"]


def test_templates_list_page_offers_create_and_import_to_an_admin(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 1"}).json()["id"]

    resp = ui_client.get(f"/ui/orgs/{tenant_id}/templates")
    assert resp.status_code == 200
    assert "Create blank draft" in resp.text
    assert "Import" in resp.text


def test_non_admin_member_sees_templates_read_only(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 2"}).json()["id"]

    member_email = f"{uuid.uuid4()}@example.com"
    member_client = _invite_and_accept_ui(ui_client, tenant_id, member_email)

    resp = member_client.get(f"/ui/orgs/{tenant_id}/templates")
    assert resp.status_code == 200
    assert "Create blank draft" not in resp.text


def test_create_blank_draft_and_view_editor(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 3"}).json()["id"]

    resp = ui_client.post(f"/ui/orgs/{tenant_id}/templates", data={"name": "Blank draft"})
    assert resp.status_code == 200
    assert "draft" in resp.text
    # The blank starter's own default gate (_BLANK_SCHEMA in templates.py).
    assert "Intake" in resp.text
    assert "Publish this version" in resp.text


def test_guided_add_gate_and_add_rule_with_a_single_condition(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 4"}).json()["id"]
    template_id, version_id = _create_blank_draft(ui_client, tenant_id)

    add_gate = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates",
        data={"gate_id": "S1", "name": "Security review", "sequence": 2, "class_ids": ["Draft"]},
    )
    assert add_gate.status_code == 200
    assert "added" in add_gate.text
    assert "Security review" in add_gate.text

    add_rule = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/S1/rules",
        data={
            "rule_id": "R1",
            "class_ids": ["Draft"],
            "occurrence_type": "routine",
            "evidence_kind": "document",
            "permitted_role_ids": ["approver"],
            "blocker_level": "hard",
            "guidance": "Upload the signed report.",
            "cond_combinator": "single",
            "cond1_fact": "class_id",
            "cond1_op": "eq",
            "cond1_value": "Draft",
            "cond2_fact": "",
            "cond2_op": "",
            "cond2_value": "",
            "cond3_fact": "",
            "cond3_op": "",
            "cond3_value": "",
        },
    )
    assert add_rule.status_code == 200
    assert "added to gate" in add_rule.text and "S1" in add_rule.text
    assert "class_id = &#39;Draft&#39;" in add_rule.text or "class_id = 'Draft'" in add_rule.text

    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    gate = next(g for g in version["schema_json"]["gates"] if g["gate_id"] == "S1")
    rule = gate["rules"][0]
    assert rule["conditions"] == {"op": "eq", "fact": "class_id", "value": "Draft"}
    assert rule["permitted_role_ids"] == ["approver"]


def test_guided_add_rule_with_any_combinator_builds_a_wrapped_condition(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 5"}).json()["id"]
    template_id, version_id = _create_blank_draft(ui_client, tenant_id)

    ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/G1/rules",
        data={
            "rule_id": "R1",
            "class_ids": ["Draft"],
            "occurrence_type": "routine",
            "evidence_kind": "document",
            "permitted_role_ids": ["approver"],
            "blocker_level": "advisory",
            "cond_combinator": "any",
            "cond1_fact": "class_id",
            "cond1_op": "eq",
            "cond1_value": "Draft",
            "cond2_fact": "region",
            "cond2_op": "in",
            "cond2_value": "eu, us",
            "cond3_fact": "",
            "cond3_op": "",
            "cond3_value": "",
        },
    )

    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    rule = version["schema_json"]["gates"][0]["rules"][0]
    assert rule["conditions"] == {
        "op": "any",
        "conditions": [
            {"op": "eq", "fact": "class_id", "value": "Draft"},
            {"op": "in", "fact": "region", "value": ["eu", "us"]},
        ],
    }


def test_remove_rule_and_remove_gate(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 6"}).json()["id"]
    template_id, version_id = _create_blank_draft(ui_client, tenant_id)

    ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/G1/rules",
        data={
            "rule_id": "R1",
            "class_ids": ["Draft"],
            "occurrence_type": "routine",
            "evidence_kind": "document",
            "permitted_role_ids": ["approver"],
            "blocker_level": "hard",
        },
    )
    remove_rule = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/G1/rules/R1/remove"
    )
    assert remove_rule.status_code == 200
    assert "removed" in remove_rule.text

    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    assert version["schema_json"]["gates"][0]["rules"] == []

    # TemplateSchema.gates has Field(min_length=1) -- a template can never
    # have zero gates. Removing the ONLY gate must be honestly rejected by
    # the same validation every other path goes through, not silently
    # allowed by the guided UI.
    remove_only_gate = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/G1/remove"
    )
    assert remove_only_gate.status_code == 200
    assert "at least 1 item" in remove_only_gate.text or "gates" in remove_only_gate.text.lower()
    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    assert len(version["schema_json"]["gates"]) == 1

    # Add a second gate, then removing the first one succeeds -- the
    # min-length invariant is about the template as a whole, not any one gate.
    ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates",
        data={"gate_id": "S1", "name": "Security review", "sequence": 2, "class_ids": ["Draft"]},
    )
    remove_gate = ui_client.post(f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/G1/remove")
    assert remove_gate.status_code == 200
    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    assert [g["gate_id"] for g in version["schema_json"]["gates"]] == ["S1"]


def test_publish_makes_the_version_immutable_and_offers_fork(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 7"}).json()["id"]
    template_id, version_id = _create_blank_draft(ui_client, tenant_id)

    publish = ui_client.post(f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/publish")
    assert publish.status_code == 200
    assert "Published." in publish.text
    assert "immutable" in publish.text
    assert "Fork to a new draft" in publish.text
    assert "Add a gate" not in publish.text

    blocked = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates",
        data={"gate_id": "S1", "name": "Too late", "sequence": 2, "class_ids": ["Draft"]},
    )
    assert blocked.status_code == 200
    assert "immutable" in blocked.text

    # fork_template (templates.py) creates a brand-new template lineage,
    # linked via forked_from_version_id -- not a version 2 of the same
    # template (there is no "new version of the same template" endpoint at
    # all; update_draft only ever mutates the current draft in place).
    fork = ui_client.post(f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/fork")
    assert fork.status_code == 200
    assert "Version 1" in fork.text
    assert "draft" in fork.text
    assert "Add a gate" in fork.text


def test_advanced_json_replace_and_malformed_json_error(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 8"}).json()["id"]
    template_id, version_id = _create_blank_draft(ui_client, tenant_id)

    bad = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/raw",
        data={"schema_text": "{not valid json"},
    )
    assert bad.status_code == 200
    assert "Not valid JSON" in bad.text

    new_schema = {
        "schema_version": 1,
        "tracks": ["Delivery"],
        "classes": ["Draft"],
        "roles": ["contributor", "approver"],
        "statuses": ["Not started", "Complete"],
        "decision_outcomes": ["Approve", "Hold"],
        "gates": [
            {
                "gate_id": "G1",
                "name": "Intake",
                "sequence": 1,
                "class_ids": ["Draft"],
                "rules": [
                    {
                        "version": 1,
                        "rule_id": "R1",
                        "class_ids": ["Draft"],
                        "occurrence_type": "routine",
                        "evidence_kind": "document",
                        "permitted_role_ids": ["approver"],
                        "blocker_level": "hard",
                        "conditions": {
                            "op": "all",
                            "conditions": [
                                {"op": "eq", "fact": "a", "value": "1"},
                                {"op": "eq", "fact": "b", "value": "2"},
                            ],
                        },
                    }
                ],
            }
        ],
    }
    good = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/raw",
        data={"schema_text": json.dumps(new_schema)},
    )
    assert good.status_code == 200
    assert "Schema replaced" in good.text

    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    assert version["schema_json"]["gates"][0]["rules"][0]["conditions"]["op"] == "all"


def test_non_admin_cannot_author_or_publish(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 9"}).json()["id"]
    template_id, version_id = _create_blank_draft(ui_client, tenant_id)

    member_email = f"{uuid.uuid4()}@example.com"
    member_client = _invite_and_accept_ui(ui_client, tenant_id, member_email)

    resp = member_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates",
        data={"gate_id": "S1", "name": "Nope", "sequence": 2, "class_ids": ["Draft"]},
    )
    assert resp.status_code == 200
    assert "Role does not permit this operation" in resp.text

    resp = member_client.post(f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/publish")
    assert resp.status_code == 200
    assert "Role does not permit this operation" in resp.text

    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    assert version["schema_json"]["gates"][0]["gate_id"] == "G1"
    assert version["status"] == "draft"


def test_metadata_update_and_import_via_the_list_page(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI08 org 10"}).json()["id"]
    template_id, version_id = _create_blank_draft(ui_client, tenant_id)

    resp = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/metadata",
        data={
            "tracks": "Delivery, Security",
            "classes": "Draft, Standard",
            "roles": "contributor, approver, tenant_administrator",
            "statuses": "Not started, In progress, Complete",
            "decision_outcomes": "Approve, Hold",
        },
    )
    assert resp.status_code == 200
    assert "Template metadata updated." in resp.text

    version = ui_client.get(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}").json()
    assert version["schema_json"]["tracks"] == ["Delivery", "Security"]
    assert version["schema_json"]["classes"] == ["Draft", "Standard"]

    schema = {
        "schema_version": 1,
        "tracks": ["Delivery"],
        "classes": ["A"],
        "roles": ["approver"],
        "statuses": ["Not started", "Complete"],
        "decision_outcomes": ["Approve"],
        "gates": [{"gate_id": "G1", "name": "Intake", "sequence": 1, "class_ids": ["A"], "rules": []}],
    }
    resp = ui_client.post(
        f"/ui/orgs/{tenant_id}/templates/import", data={"name": "Imported via UI", "schema_text": json.dumps(schema)}
    )
    assert resp.status_code == 200
    assert "Imported via UI" in resp.text
