"""DEC07 G5: a rule's `conditions` tree is evaluated for readiness
against facts built from the occurrence's own evidence items, making the
Q10 operators load-bearing. Narrow scope: no project-state facts."""

import copy

import pytest

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3

# A gate whose summary item requires at least 2 of the 3 checks satisfied.
V3_COUNT = copy.deepcopy(V3)
V3_COUNT["gates"][0]["rules"] = [
    {
        "version": 1,
        "rule_id": "dod.a",
        "class_ids": ["Team"],
        "occurrence_type": "routine",
        "evidence_kind": "note",
        "permitted_role_ids": ["developer"],
        "blocker_level": "advisory",
    },
    {
        "version": 1,
        "rule_id": "dod.b",
        "class_ids": ["Team"],
        "occurrence_type": "routine",
        "evidence_kind": "note",
        "permitted_role_ids": ["developer"],
        "blocker_level": "advisory",
    },
    {
        "version": 1,
        "rule_id": "dod.summary",
        "class_ids": ["Team"],
        "occurrence_type": "routine",
        "evidence_kind": "note",
        "permitted_role_ids": ["approver"],
        "blocker_level": "hard",
        "conditions": {
            "op": "count",
            "compare": "gte",
            "value": 2,
            "conditions": [
                {"op": "eq", "fact": "item:dod.a", "value": "satisfied"},
                {"op": "eq", "fact": "item:dod.b", "value": "satisfied"},
                {"op": "eq", "fact": "item:dod.missing", "value": "satisfied"},
            ],
        },
    },
]


@pytest.fixture()
def count_project(client):
    register_and_login(client, "admin@cond.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Cond Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "Cond", "schema_json": V3_COUNT}).json()
    pub = client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    assert pub.status_code == 200, pub.text
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    )
    assert project.status_code == 201, project.text
    return tenant_id, project.json()


def _items(created):
    return {i["rule_id"]: i for i in created["evidence_items"]}


def _preview(client, tenant_id, created):
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{created['project']['id']}/occurrences/{created['occurrences'][0]['id']}/preview",
        json={},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _meet(client, tenant_id, item):
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met", "reference": "note-1"},
    )
    assert resp.status_code == 201, resp.text


def test_conditions_withhold_satisfaction_until_the_count_is_met(client, count_project):
    """G5 and spec 4.4: a satisfying status is necessary but not
    sufficient -- the conditions tree must also hold."""
    tenant_id, created = count_project
    items = _items(created)

    _meet(client, tenant_id, items["dod.summary"])
    assert items["dod.summary"]["id"] in _preview(client, tenant_id, created)["hard_blockers"], (
        "status alone must not satisfy an item whose conditions are false"
    )

    _meet(client, tenant_id, items["dod.a"])
    assert items["dod.summary"]["id"] in _preview(client, tenant_id, created)["hard_blockers"], (
        "one of three satisfied is below the count of 2"
    )

    _meet(client, tenant_id, items["dod.b"])
    assert items["dod.summary"]["id"] not in _preview(client, tenant_id, created)["hard_blockers"], (
        "two of three satisfied meets count gte 2, so the item is now satisfied"
    )


def test_conditions_can_only_withhold_never_grant(client, count_project):
    """Spec 4.4: with conditions true but the status not satisfying, the
    item stays unsatisfied. The human attestation remains the auditable
    act."""
    tenant_id, created = count_project
    items = _items(created)
    _meet(client, tenant_id, items["dod.a"])
    _meet(client, tenant_id, items["dod.b"])

    assert items["dod.summary"]["id"] in _preview(client, tenant_id, created)["hard_blockers"]


def test_a_fact_for_an_unseeded_rule_fails_closed(client, count_project):
    """REVIEW FOCUS 4. `item:dod.missing` names no seeded rule, so the
    fact is unknown. It must evaluate false without raising -- which the
    count test above already relies on, since 2 of 3 is only reachable if
    the third is false rather than an error."""
    tenant_id, created = count_project
    body = _preview(client, tenant_id, created)
    assert isinstance(body["hard_blockers"], list)


def test_conditions_are_not_evaluated_for_a_v2_template(client):
    """G6 boundary: the same shaped rule at vocabulary 2 must behave as it
    does today -- conditions ignored, status alone decides."""
    v2 = copy.deepcopy(V3_COUNT)
    v2["vocabulary_version"] = 2
    v2["statuses"] = ["Not started", "In progress", "Complete"]
    v2["decision_outcomes"] = ["Approve", "Hold"]

    register_and_login(client, "admin@cond2.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Cond2 Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "Cond2", "schema_json": v2}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()
    items = _items(project)

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{items['dod.summary']['id']}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "note-1"},
    )
    assert resp.status_code == 201, resp.text
    assert items["dod.summary"]["id"] not in _preview(client, tenant_id, project)["hard_blockers"], (
        "conditions must stay unevaluated at vocabulary 2"
    )
