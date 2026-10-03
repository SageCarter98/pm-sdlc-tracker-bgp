"""DEC07: a template's declared decision outcomes become recordable,
resolved by declared kind rather than by matching English words."""

import pytest

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3


@pytest.fixture()
def ready_v3(client):
    register_and_login(client, "admin@v3out.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Out Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()
    item = project["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met", "reference": "https://ci/1"},
    )
    assert resp.status_code == 201, resp.text
    return tenant_id, project


def _preview(client, tenant_id, project, outcome=None):
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{project['occurrences'][0]['id']}/preview",
        json={"outcome": outcome} if outcome else {},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_declared_outcomes_are_permitted_once_blockers_clear(client, ready_v3):
    """G2: `permitted_outcomes` was [] for any framework not using the
    Blueprint's five words."""
    tenant_id, project = ready_v3
    body = _preview(client, tenant_id, project)
    assert body["hard_blockers"] == []
    assert set(body["permitted_outcomes"]) == {"Increment accepted", "Not accepted"}


def test_an_approving_outcome_can_actually_be_recorded(client, ready_v3):
    tenant_id, project = ready_v3
    body = _preview(client, tenant_id, project, outcome="Increment accepted")
    assert body["outcome_allowed"] is True, body["outcome_denial_reason"]

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}"
        f"/occurrences/{project['occurrences'][0]['id']}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": body["manifest_digest"]},
        headers={"Idempotency-Key": "v3-accept-1"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["outcome"] == "Increment accepted"


def test_a_recording_outcome_needs_no_cleared_blockers(client):
    """`recording` is the Hold/Redirect/Terminate behaviour: recorded, not
    an approval, so it must work with blockers outstanding."""
    register_and_login(client, "admin@v3rec.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Rec Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()

    body = _preview(client, tenant_id, project)
    assert body["hard_blockers"], "this test needs an outstanding blocker to be meaningful"
    assert "Not accepted" in body["permitted_outcomes"]

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}"
        f"/occurrences/{project['occurrences'][0]['id']}/decisions",
        json={"outcome": "Not accepted", "manifest_digest": body["manifest_digest"]},
        headers={"Idempotency-Key": "v3-reject-1"},
    )
    assert resp.status_code == 201, resp.text


def test_an_outcome_the_template_never_declared_is_still_refused(client, ready_v3):
    tenant_id, project = ready_v3
    body = _preview(client, tenant_id, project)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}"
        f"/occurrences/{project['occurrences'][0]['id']}/decisions",
        json={"outcome": "Approve", "manifest_digest": body["manifest_digest"]},
        headers={"Idempotency-Key": "v3-bogus-1"},
    )
    assert resp.status_code == 422
    assert "not a decision outcome declared by this template version" in resp.text


def test_a_v3_outcome_is_found_not_reported_undeclared(client, ready_v3):
    """CONTROLLER NOTE: after Task 2, `decision_outcomes` holds
    OutcomeDefinition OBJECTS for a v3 template, not strings. A stale
    `outcome in schema.decision_outcomes` string-membership check would
    MISS every v3 entry and refuse it as undeclared even though it is
    declared with a perfectly good kind. Pin that a declared v3 outcome is
    recognised as declared -- i.e. never denied with the 'is not a
    decision outcome declared by this template version' message -- which
    is only true if the eligibility check resolves outcomes object-aware."""
    tenant_id, project = ready_v3
    body = _preview(client, tenant_id, project, outcome="Increment accepted")
    assert body["outcome_allowed"] is True
    assert body["outcome_denial_reason"] is None
