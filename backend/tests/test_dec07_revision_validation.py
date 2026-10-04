"""DEC07: REQ-018 keyed on semantics, undeclared statuses rejected, and
the initial status taken from the template rather than a literal."""

import pytest

from app.rule_engine import validate_template_schema
from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3


@pytest.fixture()
def v3_project(client):
    register_and_login(client, "admin@v3rev.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Rev Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    )
    assert project.status_code == 201, project.text
    return tenant_id, project.json()


def test_seeded_item_starts_in_the_templates_declared_initial_status(client, v3_project):
    """G7: the platform must stop writing "Not started" into a framework
    that never declares it."""
    _, created = v3_project
    assert {i["status"] for i in created["evidence_items"]} == {"Not met"}


def test_req018_catches_a_satisfying_status_with_no_reference(client, v3_project):
    """G3: the control keys on `satisfies`, so "Met" is caught exactly as
    "Complete" is for a legacy template."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    assert item["required"] is True

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met"},
    )
    assert resp.status_code == 422
    assert "REQ-018" in resp.text


def test_a_non_satisfying_status_needs_no_reference(client, v3_project):
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Not met"},
    )
    assert resp.status_code == 201, resp.text


def test_an_undeclared_status_is_rejected(client, v3_project):
    """G4: `statuses` must constrain something."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Bananas", "reference": "x"},
    )
    assert resp.status_code == 422
    assert "Bananas" in resp.text


@pytest.mark.parametrize("near_miss", ["met", " Met", "MET", "Met "])
def test_near_miss_status_ids_are_rejected_not_silently_stored(client, v3_project, near_miss):
    """Exact match only. A near-miss stored as a
    non-satisfying status would look accepted and never satisfy, which is
    the confusing failure this whole change exists to remove."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": near_miss, "reference": "x"},
    )
    assert resp.status_code == 422, f"{near_miss!r} should be rejected, not stored"


V2_NO_COMPLETE_SCHEMA = {
    "schema_version": 1,
    "vocabulary_version": 2,
    "tracks": ["Delivery"],
    "classes": ["C"],
    "roles": ["approver"],
    "statuses": ["Not started", "In progress", "Done"],
    "decision_outcomes": ["Approve", "Hold"],
    "gates": [
        {
            "gate_id": "g1",
            "name": "Test Gate",
            "sequence": 1,
            "class_ids": ["C"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "r1",
                    "class_ids": ["C"],
                    "occurrence_type": "routine",
                    "evidence_kind": "document",
                    "required_fields": [],
                    "permitted_role_ids": ["approver"],
                    "blocker_level": "hard",
                }
            ],
        }
    ],
}


def test_undeclared_complete_still_demands_a_reference_below_v3(client):
    """Regression pin for the fix-wave's own I4(b) gating regression
    (re-review finding 1): `projects.py`'s undeclared-status 422 is
    correctly gated behind `vocabulary_version >= 3`, but the REQ-018
    reference guard a few lines below used to key SOLELY on
    `status_lookup().get("Complete")` resolving to a definition. For a
    v1/v2 template that never declares "Complete", that lookup is None,
    so the reference guard was ALSO skipped -- a required item could be
    marked "Complete" with no reference at all, the exact state REQ-018
    exists to forbid. Pre-DEC07 the check was an unconditional
    `payload.status == "Complete"` literal that ignored the template
    entirely, so it demanded a reference regardless of declaration; this
    pins that restored behaviour.

    Made non-vacuous per the standing instruction (this exact failure mode
    -- a fixture change silently emptying a test -- has already happened
    twice on this branch): assert the schema's resolved `status_lookup()`
    genuinely lacks "Complete" before relying on that gap existing."""
    resolved = validate_template_schema(V2_NO_COMPLETE_SCHEMA)
    assert resolved.vocabulary_version == 2
    assert resolved.status_lookup().get("Complete") is None, (
        "this schema must NOT declare 'Complete', or this test stops pinning the regression"
    )

    register_and_login(client, "admin@undeclaredcomplete.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Undeclared Co"}).json()["id"]

    imported = client.post(
        f"/orgs/{tenant_id}/templates/import",
        json={"name": "v2_no_complete", "schema_json": V2_NO_COMPLETE_SCHEMA},
    ).json()
    published = client.post(f"/orgs/{tenant_id}/templates/{imported['template_id']}/versions/{imported['id']}/publish")
    assert published.status_code == 200, published.text

    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Project", "template_version_id": imported["id"], "class_id": "C", "members": []},
    ).json()
    item = project["evidence_items"][0]
    assert item["required"] is True

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Complete"},
    )
    assert resp.status_code == 422, resp.text
    assert "REQ-018" in resp.text
