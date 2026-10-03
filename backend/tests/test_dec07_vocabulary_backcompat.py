"""G6: vocabulary 1/2 templates must evaluate identically forever.

Written BEFORE the vocabulary-indirection change and must stay green
through every task of it. If one of these fails, back-compat broke --
that is the whole purpose of this file, so do not "update the
expectation" to match new behaviour.
"""

import json
from pathlib import Path

import pytest

from tests.conftest import enable_mfa, register_and_login

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks"
V1_V2_FIXTURES = ["standard", "regulated", "lightweight"]


def _schema(stem: str) -> dict:
    data = json.loads((FIXTURES_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


def _publish(client, tenant_id: str, stem: str) -> str:
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": stem, "schema_json": _schema(stem)}
    ).json()
    resp = client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    assert resp.status_code == 200, resp.text
    return created["id"]


@pytest.mark.parametrize("stem", V1_V2_FIXTURES)
def test_seeded_items_start_in_not_started(client, stem):
    """Today's seeding literal. A v1/v2 template must keep producing
    exactly 'Not started', because its stored rows already say so."""
    register_and_login(client, "admin@backcompat.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "BC Co"}).json()["id"]
    version_id = _publish(client, tenant_id, stem)
    schema = _schema(stem)

    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "BC project",
            "template_version_id": version_id,
            "class_id": schema["classes"][0],
            "members": [],
        },
    )
    assert created.status_code == 201, created.text
    items = created.json()["evidence_items"]
    assert items, f"{stem} seeded no evidence items for class {schema['classes'][0]}"
    assert {i["status"] for i in items} == {"Not started"}


@pytest.mark.parametrize("stem", V1_V2_FIXTURES)
def test_complete_still_clears_a_blocker_and_permits_the_declared_outcomes(client, stem):
    """The literal 'Complete' must keep working for v1/v2, and the
    permitted-outcome list must be unchanged."""
    register_and_login(client, "admin@backcompat.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "BC Co"}).json()["id"]
    version_id = _publish(client, tenant_id, stem)
    schema = _schema(stem)
    class_id = schema["classes"][0]

    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "BC project", "template_version_id": version_id, "class_id": class_id, "members": []},
    ).json()
    project_id = created["project"]["id"]
    occurrence_id = created["occurrences"][0]["id"]
    gate_id = created["occurrences"][0]["gate_id"]

    for item in created["evidence_items"]:
        if item["gate_id"] == gate_id and item["blocker_level"] in ("hard", "conditional"):
            resp = client.post(
                f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
                json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
            )
            assert resp.status_code == 201, resp.text

    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/preview", json={}
    ).json()
    assert preview["hard_blockers"] == []
    assert preview["conditional_blockers"] == []

    assert set(preview["permitted_outcomes"]) <= set(schema["decision_outcomes"])
    assert "Approve" in preview["permitted_outcomes"], (
        "Approve must stay permitted once blockers clear, for every v1/v2 fixture"
    )


@pytest.mark.parametrize("stem", V1_V2_FIXTURES)
def test_rule_conditions_are_still_not_evaluated_for_v1_v2(client, stem):
    """G6 specifically: turning conditions on for v3 must not turn it on
    for v1/v2. Completing a hard item clears its blocker even though no
    facts are ever supplied to satisfy its conditions tree."""
    register_and_login(client, "admin@backcompat.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "BC Co"}).json()["id"]
    version_id = _publish(client, tenant_id, stem)
    schema = _schema(stem)
    class_id = schema["classes"][0]

    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "BC project", "template_version_id": version_id, "class_id": class_id, "members": []},
    ).json()
    project_id = created["project"]["id"]
    occurrence = created["occurrences"][0]

    hard = [
        i for i in created["evidence_items"] if i["gate_id"] == occurrence["gate_id"] and i["blocker_level"] == "hard"
    ]
    if not hard:
        pytest.skip(f"{stem}'s first occurrence has no hard item to prove this with")

    for item in hard:
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
        )

    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence['id']}/preview", json={}
    ).json()
    assert preview["hard_blockers"] == []
