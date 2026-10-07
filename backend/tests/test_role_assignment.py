"""Review Focus 5: the assignment boundary must work in BOTH directions --
a declared role assignable at v4, and only platform roles below it."""

import json

import pytest

from tests.conftest import login, register_and_login
from tests.test_projects import FIXTURES_DIR
from tests.test_role_decision_authority import V4, _invite

PASSWORD = "correct horse battery staple"
ADMIN = "admin@roleassign.example"


def _publish(client, tenant_id, name, schema):
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": name, "schema_json": schema}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    return created["id"]


@pytest.fixture()
def tenant(client):
    register_and_login(client, ADMIN)
    return client.post("/orgs", json={"name": "Role Assign Co"}).json()["id"]


def test_a_v4_declared_role_is_assignable(client, tenant):
    version_id = _publish(client, tenant, "V4", V4)
    member_id = _invite(client, tenant, "dev@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "developer"}],
        },
    )

    assert resp.status_code == 201, resp.text


def test_an_undeclared_role_is_refused_at_v4(client, tenant):
    version_id = _publish(client, tenant, "V4", V4)
    member_id = _invite(client, tenant, "ghost@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "approver"}],
        },
    )

    assert resp.status_code == 422, resp.text
    assert "developer" in resp.text and "product_owner" in resp.text


def test_below_v4_only_platform_roles_are_accepted(client, tenant):
    """The other direction: a v1 template must not start accepting
    arbitrary strings just because the field stopped being enum-typed."""
    schema = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    version_id = _publish(client, tenant, "Standard", schema)
    member_id = _invite(client, tenant, "legacy@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Standard-High",
            "members": [{"user_id": member_id, "role": "product_owner"}],
        },
    )

    assert resp.status_code == 422, resp.text


def test_below_v4_a_platform_role_still_works(client, tenant):
    schema = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    version_id = _publish(client, tenant, "Standard", schema)
    member_id = _invite(client, tenant, "ok@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Standard-High",
            "members": [{"user_id": member_id, "role": "approver"}],
        },
    )

    assert resp.status_code == 201, resp.text


def test_the_starter_picker_reports_the_member_roles_its_binding_permits(client, tenant):
    """The assignment boundary is only usable if the form fronting it can say
    what the binding accepts. Before this, project_new.html hardcoded the
    five platform roles -- every one of which a v4 template refuses."""
    v4_id = _publish(client, tenant, "V4", V4)
    standard = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    standard.pop("_meta", None)
    v1_id = _publish(client, tenant, "Standard", standard)

    published = {s["version_id"]: s for s in client.get(f"/orgs/{tenant}/templates/published").json()}

    assert published[v4_id]["member_roles"] == ["developer", "product_owner"], (
        "a v4 binding's assignable roles are the ones it declares"
    )
    assert published[v1_id]["member_roles"] == [
        "approver",
        "assurance_reviewer",
        "contributor",
        "sponsor",
        "tenant_administrator",
    ], "below v4 the assignable set is still exactly the platform enum, unchanged"
