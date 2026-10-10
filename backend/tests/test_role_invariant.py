"""Spec Sec.4, end to end: a declared `decides` role NARROWS authority
within the Blueprint's model and never grants authority the holder's
tenant role lacks.

This is the test that would catch the endpoint guard being reordered
after the project-role check. It is deliberately in its own file so it
is hard to delete by accident along with a fixture refactor.

It differs from test_role_decision_authority.py's
test_a_project_approver_whose_tenant_role_is_contributor_is_now_refused in
the one way that matters: that test refuses at the authority gate with a
deliberately bogus manifest_digest and no evidence prepared, which proves
the gate runs FIRST but cannot prove a ready, correctly-addressed decision
is still refused. Here the gate is genuinely ready and the digest is the
real one from preview, so a 403 can only be the intersection holding.
"""

from tests.conftest import enable_mfa, login, register_and_login
from tests.test_role_decision_authority import V4, _invite

PASSWORD = "correct horse battery staple"
ADMIN = "admin@invariant.example"
WEAK = "weak@invariant.example"


def test_a_declared_decider_whose_tenant_role_cannot_decide_is_still_refused(client):
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Invariant Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": V4}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )

    # Tenant role 'contributor' -- cannot decide at the tenant layer, and is
    # not in ROLES_REQUIRING_MFA, so no enable_mfa() call is needed for this
    # user and a 403 cannot be the MFA dependency in disguise.
    # Project role 'product_owner' -- the template says it DOES decide.
    weak_id = _invite(client, tenant_id, WEAK, "contributor")
    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Squad",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": weak_id, "role": "product_owner"}],
        },
    ).json()
    occurrence_id = project["occurrences"][0]["id"]

    # The admin prepares every hard item, so the gate is genuinely ready and
    # the refusal below cannot be readiness wearing a 403.
    for item in project["evidence_items"]:
        assert (
            client.post(
                f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
                json={
                    "base_revision": 1,
                    "status": "Met",
                    "reference": "https://ci.example/run/1",
                    "owner_user_id": None,
                    "due_date": None,
                    "completed_date": None,
                },
            ).status_code
            == 201
        ), item
    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/preview", json={}
    ).json()
    assert preview["hard_blockers"] == [], f"this test is only meaningful on a READY gate: {preview}"

    login(client, WEAK, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": preview["manifest_digest"]},
        headers={"Idempotency-Key": "invariant-1"},
    )

    assert resp.status_code == 403, (
        "a template-declared decider must not reach a decision when the holder's "
        f"TENANT role does not permit deciding -- got {resp.status_code}: {resp.text}"
    )
    assert resp.json()["detail"] == "Role does not permit recording decisions", (
        f"refused, but by the wrong control: {resp.text}"
    )
