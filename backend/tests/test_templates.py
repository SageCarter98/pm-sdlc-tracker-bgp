import uuid

from tests.conftest import register_and_login

MINIMAL_SCHEMA = {
    "tracks": ["Delivery"],
    "classes": ["A"],
    "roles": ["contributor", "approver"],
    "statuses": ["Not started", "Complete"],
    "decision_outcomes": ["Approve", "Hold"],
    "gates": [
        {
            "gate_id": "G1",
            "name": "Intake",
            "sequence": 1,
            "class_ids": ["A"],
            "rules": [],
        }
    ],
}


def _create_org_as_admin(client, email="admin@tenant-a.example"):
    register_and_login(client, email)
    return client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]


def test_create_blank_template_is_valid_draft(client):
    tenant_id = _create_org_as_admin(client)
    resp = client.post(f"/orgs/{tenant_id}/templates", json={"name": "My Framework"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["version_number"] == 1
    assert body["schema_json"]["classes"] == ["Draft"]


def test_create_with_invalid_schema_explains_the_field(client):
    tenant_id = _create_org_as_admin(client)
    bad = {**MINIMAL_SCHEMA, "gates": [{**MINIMAL_SCHEMA["gates"][0], "class_ids": ["NOPE"]}]}
    resp = client.post(f"/orgs/{tenant_id}/templates", json={"name": "Bad", "schema_json": bad})
    assert resp.status_code == 422
    assert "undeclared class" in str(resp.json())


def test_list_templates_shows_created_template(client):
    tenant_id = _create_org_as_admin(client)
    client.post(f"/orgs/{tenant_id}/templates", json={"name": "My Framework"})
    resp = client.get(f"/orgs/{tenant_id}/templates")
    assert resp.status_code == 200
    assert any(t["name"] == "My Framework" for t in resp.json())


def test_edit_draft_then_publish_then_edit_rejected(client):
    tenant_id = _create_org_as_admin(client)
    created = client.post(f"/orgs/{tenant_id}/templates", json={"name": "F", "schema_json": MINIMAL_SCHEMA}).json()
    template_id, version_id = created["template_id"], created["id"]

    updated_schema = {**MINIMAL_SCHEMA, "tracks": ["Delivery", "Assurance"]}
    edit = client.put(
        f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}", json={"schema_json": updated_schema}
    )
    assert edit.status_code == 200
    assert edit.json()["schema_json"]["tracks"] == ["Delivery", "Assurance"]

    publish = client.post(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/publish")
    assert publish.status_code == 200
    assert publish.json()["status"] == "published"

    edit_after_publish = client.put(
        f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}", json={"schema_json": MINIMAL_SCHEMA}
    )
    assert edit_after_publish.status_code == 409

    republish = client.post(f"/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/publish")
    assert republish.status_code == 409


def test_import_valid_schema(client):
    tenant_id = _create_org_as_admin(client)
    resp = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "Imported", "schema_json": MINIMAL_SCHEMA})
    assert resp.status_code == 201
    assert resp.json()["schema_json"]["classes"] == ["A"]


def test_import_malformed_schema_rejected_with_field_errors(client):
    tenant_id = _create_org_as_admin(client)
    bad = {**MINIMAL_SCHEMA, "gates": [{**MINIMAL_SCHEMA["gates"][0], "rules": [{"op": "regex"}]}]}
    # deliberately break shape further: rules must be Rule objects, not raw conditions
    resp = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "Bad", "schema_json": bad})
    assert resp.status_code == 422


def test_fork_creates_independent_copy(client):
    tenant_id = _create_org_as_admin(client)
    original = client.post(
        f"/orgs/{tenant_id}/templates", json={"name": "Original", "schema_json": MINIMAL_SCHEMA}
    ).json()

    forked = client.post(f"/orgs/{tenant_id}/templates/{original['template_id']}/versions/{original['id']}/fork")
    assert forked.status_code == 201
    forked_body = forked.json()
    assert forked_body["template_id"] != original["template_id"]
    assert forked_body["schema_json"] == MINIMAL_SCHEMA

    # editing the fork must not touch the original
    client.put(
        f"/orgs/{tenant_id}/templates/{forked_body['template_id']}/versions/{forked_body['id']}",
        json={**MINIMAL_SCHEMA, "tracks": ["Changed"]},
    )
    original_after = client.get(
        f"/orgs/{tenant_id}/templates/{original['template_id']}/versions/{original['id']}"
    ).json()
    assert original_after["schema_json"]["tracks"] == ["Delivery"]


def test_contributor_cannot_create_or_publish_templates(client):
    tenant_id = _create_org_as_admin(client)
    token = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "c@tenant-a.example", "role": "contributor"}
    ).json()["token"]
    register_and_login(client, "c@tenant-a.example")
    client.post("/invitations/accept", json={"token": token})

    resp = client.post(f"/orgs/{tenant_id}/templates", json={"name": "Nope"})
    assert resp.status_code == 403


def test_other_tenant_cannot_edit_or_publish_this_tenants_template(client):
    tenant_a = _create_org_as_admin(client, "admin@tenant-a.example")
    created = client.post(f"/orgs/{tenant_a}/templates", json={"name": "F", "schema_json": MINIMAL_SCHEMA}).json()

    _create_org_as_admin(client, "admin@tenant-b.example")
    # tenant B has no membership in tenant A -- the tenant_id in the URL is tenant A's,
    # so the membership check on tenant_a itself should already deny tenant B's session.
    resp = client.put(
        f"/orgs/{tenant_a}/templates/{created['template_id']}/versions/{created['id']}",
        json={"schema_json": MINIMAL_SCHEMA},
    )
    assert resp.status_code == 403


def test_shared_starter_is_visible_and_forkable_but_not_editable(client):
    """Simulates what a platform seed script does: insert a template with
    tenant_id=None directly (no endpoint creates these -- see
    routers/templates.py policy notes), then confirm a tenant can see and
    fork it, but not edit or publish it directly."""
    from app.models import Template, TemplateVersion

    tenant_id = _create_org_as_admin(client)

    # Reach into the same overridden test DB via the app's dependency override.
    from app.db import get_db
    from app.main import app

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    starter = Template(id=str(uuid.uuid4()), tenant_id=None, name="Neutral Starter")
    db.add(starter)
    db.flush()
    starter_version = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=starter.id,
        version_number=1,
        schema_json=MINIMAL_SCHEMA,
        status="published",
        created_by_user_id=None,
    )
    db.add(starter_version)
    db.commit()

    listing = client.get(f"/orgs/{tenant_id}/templates").json()
    assert any(t["id"] == starter.id for t in listing)

    fork = client.post(f"/orgs/{tenant_id}/templates/{starter.id}/versions/{starter_version.id}/fork")
    assert fork.status_code == 201
    assert fork.json()["template_id"] != starter.id

    edit_attempt = client.put(
        f"/orgs/{tenant_id}/templates/{starter.id}/versions/{starter_version.id}", json={"schema_json": MINIMAL_SCHEMA}
    )
    assert edit_attempt.status_code == 403
