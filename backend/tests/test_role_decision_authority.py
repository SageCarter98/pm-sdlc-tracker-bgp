"""Decision authority resolves through the bound template at the PROJECT
layer, while the TENANT layer stays platform-fixed -- the two halves of
spec Sec.4's narrowing invariant."""

import json

import pytest

from app.routers.decisions import TENANT_DECISION_AUTHORITY_ROLES
from tests.conftest import enable_mfa, login, register_and_login
from tests.test_projects import FIXTURES_DIR

PASSWORD = "correct horse battery staple"
ADMIN = "admin@roledec.example"
DECIDER = "decider@roledec.example"
WORKER = "worker@roledec.example"

V4 = {
    "schema_version": 1,
    "vocabulary_version": 4,
    "tracks": ["Increment"],
    "classes": ["Team"],
    "roles": [
        {"id": "product_owner", "attests": True, "decides": True},
        {"id": "developer", "attests": True},
    ],
    "statuses": [{"id": "Not met", "initial": True}, {"id": "Met", "satisfies": True}],
    "decision_outcomes": [
        {"id": "Increment accepted", "kind": "approving"},
        {"id": "Not accepted", "kind": "recording"},
    ],
    "gates": [
        {
            "gate_id": "dod",
            "name": "Definition of done",
            "sequence": 1,
            "class_ids": ["Team"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "dod.checks",
                    "evidence_kind": "document",
                    "required": True,
                    "blocker_level": "hard",
                    "permitted_role_ids": ["developer", "product_owner"],
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                }
            ],
        }
    ],
}


def _invite(client, tenant_id, email, tenant_role):
    token = client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": tenant_role}).json()["token"]
    user_id = register_and_login(client, email).json()["id"]
    assert client.post("/invitations/accept", json={"token": token}).status_code == 200
    return user_id


@pytest.fixture()
def v4_project(client):
    """decider: tenant approver + project product_owner (declared decider).
    worker:  tenant approver + project developer (declared non-decider).
    The worker's TENANT role deliberately permits deciding, so a refusal
    can only come from the declared project role -- that is the point."""
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Role Dec Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": V4}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )

    decider_id = _invite(client, tenant_id, DECIDER, "approver")
    enable_mfa(client)
    login(client, ADMIN, PASSWORD)
    worker_id = _invite(client, tenant_id, WORKER, "approver")
    enable_mfa(client)

    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Squad",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [
                {"user_id": decider_id, "role": "product_owner"},
                {"user_id": worker_id, "role": "developer"},
            ],
        },
    ).json()
    return tenant_id, project, decider_id, worker_id


def _prepare_and_preview(client, tenant_id, project):
    """The worker supplies the evidence, so separation of duties is
    satisfied when someone else decides."""
    item = project["evidence_items"][0]
    login(client, WORKER, PASSWORD)
    assert (
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Met", "reference": "https://ci/1"},
        ).status_code
        == 201
    )
    occurrence_id = project["occurrences"][0]["id"]
    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/preview", json={}
    )
    assert preview.status_code == 200, preview.text
    return occurrence_id, preview.json()


def test_a_declared_decider_may_record_a_decision(client, v4_project):
    tenant_id, project, _, _ = v4_project
    occurrence_id, preview = _prepare_and_preview(client, tenant_id, project)
    assert preview["hard_blockers"] == []

    login(client, DECIDER, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": preview["manifest_digest"]},
        headers={"Idempotency-Key": "v4-decider-1"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["outcome"] == "Increment accepted"


def test_a_declared_non_decider_is_refused_even_with_a_permitting_tenant_role(client, v4_project):
    """Review Focus 1 and spec Sec.4: the worker's tenant role is approver,
    which passes the endpoint guard, so the only thing that can refuse this
    is the bound template's declared role capability. If this test ever
    passes a 201, the project-layer check has been lost."""
    tenant_id, project, _, _ = v4_project
    occurrence_id, preview = _prepare_and_preview(client, tenant_id, project)

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": preview["manifest_digest"]},
        headers={"Idempotency-Key": "v4-worker-1"},
    )
    assert resp.status_code == 403, resp.text
    assert "decision" in resp.text.lower() or "role" in resp.text.lower()


def test_a_declared_non_decider_cannot_record_a_compensating_review(client, v4_project):
    """Spec Sec.6's compensating-reviewer case, at the site that actually
    gates it. A compensating review is the reviewer's OWN authenticated
    action (`POST .../compensating-reviews`, body just `{"note": ...}` --
    `reviewer_user_id` is always the caller's own id, never typed by
    someone else), and that endpoint calls the same
    `_require_decision_authority` the decision endpoint does.

    So REQ-006's independence cannot be satisfied by someone the bound
    template says does not decide: the worker's tenant role is approver,
    which passes the endpoint guard, and the refusal can only come from
    the declared project role."""
    tenant_id, project, _, _ = v4_project
    occurrence_id = project["occurrences"][0]["id"]

    login(client, WORKER, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/compensating-reviews",
        json={"note": "I looked at it"},
    )

    assert resp.status_code == 403, resp.text


def test_a_declared_decider_can_record_a_compensating_review(client, v4_project):
    """The positive half, so the test above cannot pass for the wrong
    reason (e.g. the endpoint refusing everyone)."""
    tenant_id, project, _, _ = v4_project
    occurrence_id = project["occurrences"][0]["id"]

    login(client, DECIDER, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/compensating-reviews",
        json={"note": "I looked at it"},
    )

    assert resp.status_code == 201, resp.text


def test_the_tenant_layer_set_is_unchanged_and_still_platform_fixed():
    """Spec Sec.3.1: tenant roles gate MFA and endpoint access and predate
    any template binding, so this set must NOT become template-declared."""
    assert TENANT_DECISION_AUTHORITY_ROLES == {"approver", "sponsor", "tenant_administrator"}


def test_a_v1_v2_project_decides_exactly_as_before(client):
    """Review Focus 2 / G5, end to end rather than at the schema layer:
    the standard fixture is vocabulary 1 and its approver still decides."""
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Legacy Co"}).json()["id"]
    schema = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "Standard", "schema_json": schema}
    ).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    approver_id = _invite(client, tenant_id, DECIDER, "approver")
    enable_mfa(client)
    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Legacy",
            "template_version_id": created["id"],
            "class_id": "Standard-High",
            "members": [{"user_id": approver_id, "role": "approver"}],
        },
    ).json()
    item = next(e for e in project["evidence_items"] if e["gate_id"] == "S1")

    login(client, DECIDER, PASSWORD)
    assert (
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
        ).status_code
        == 201
    )
