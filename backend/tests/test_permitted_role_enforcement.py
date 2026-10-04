"""TST-032 / REQ-032: `permitted_role_ids` says WHO MAY ATTEST an evidence
item, and that is enforced server-side when a revision is submitted -- not
merely used to decide what appears in my-work.

Before this suite existed the field was declared in the template, validated
against the schema's declared roles (`rule_engine.py`, "references undeclared
role(s)"), consulted as a my-work visibility filter, and then **never checked
at the write boundary**: any project member could submit a revision to any
item in the project, including marking a hard, required, approver-only item
"Complete". Probed and confirmed 2026-10-04 (201, persisted) before the fix;
recorded as an unverified lead in docs/DEFECT_REGISTER.md's DEC07-Q11 row
until then.

Two exemptions are deliberate, owner-approved, and each pinned by its own
test below, so neither can be removed or widened silently:

1. The explicitly assigned owner (`owner_user_id`) may always submit --
   assignment is itself an authorised act by someone who had the authority
   to make it, and the assignee is precisely the person being asked to act.
2. A tenant administrator may always submit -- they already administer the
   tenant, and the assignment workflow this product relies on has an admin
   writing the first revision to set an owner.

Separation of duties for DECISIONS is a different control living in
`decisions.py` (`_check_separation_of_duties`); this is about who may supply
evidence, not who may approve a gate.
"""

import json

import pytest

from tests.conftest import enable_mfa, login, register_and_login
from tests.test_projects import FIXTURES_DIR

PASSWORD = "correct horse battery staple"
ADMIN = "admin@roleenf.example"
CONTRIB = "contrib@roleenf.example"
APPROVER = "approver@roleenf.example"


def _invite(client, tenant_id, email, role):
    """Invites and accepts; leaves the client logged in as the invited user."""
    token = client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": role}).json()["token"]
    user_id = register_and_login(client, email).json()["id"]
    assert client.post("/invitations/accept", json={"token": token}).status_code == 200
    return user_id


@pytest.fixture()
def project_with_roles(client):
    """A standard-framework project whose S1.R1 item is approver-only, with a
    contributor and an approver as project members alongside the admin."""
    register_and_login(client, ADMIN)
    tenant_id = client.post("/orgs", json={"name": "Role Enforcement Co"}).json()["id"]
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

    contributor_id = _invite(client, tenant_id, CONTRIB, "contributor")
    # _invite leaves us as the invited user, and only a tenant administrator
    # may issue an invitation -- so come back as the admin first.
    login(client, ADMIN, PASSWORD)
    approver_id = _invite(client, tenant_id, APPROVER, "approver")
    enable_mfa(client)  # approver role requires MFA (models.ROLES_REQUIRING_MFA)

    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Role Enforcement",
            "template_version_id": created["id"],
            "class_id": "Standard-High",
            "members": [
                {"user_id": contributor_id, "role": "contributor"},
                {"user_id": approver_id, "role": "approver"},
            ],
        },
    ).json()

    item = next(e for e in project["evidence_items"] if e["gate_id"] == "S1")
    assert item["permitted_role_ids"] == ["approver"], (
        f"these tests need an approver-only item; standard.json gave {item['permitted_role_ids']}"
    )
    return tenant_id, item, contributor_id, approver_id


def _submit(client, tenant_id, item_id, base_revision=1, **extra):
    body = {"base_revision": base_revision, "status": "Complete", "reference": "https://ci.example/run/1"}
    body.update(extra)
    return client.post(f"/orgs/{tenant_id}/evidence/{item_id}/revisions", json=body)


def test_a_non_permitted_project_role_is_refused(client, project_with_roles):
    """The regression this suite exists for. A contributor is a legitimate
    project member, is not the assigned owner, and is not an administrator --
    so an approver-only item must refuse them."""
    tenant_id, item, _, _ = project_with_roles
    login(client, CONTRIB, PASSWORD)

    resp = _submit(client, tenant_id, item["id"])

    assert resp.status_code == 403, resp.text
    assert "role" in resp.text.lower()

    # And nothing landed: the refusal must be before the insert, not after.
    login(client, ADMIN, PASSWORD)
    detail = client.get(f"/orgs/{tenant_id}/evidence/{item['id']}").json()
    assert detail["item"]["status"] != "Complete"
    assert detail["item"]["latest_revision_number"] == 1


def test_a_permitted_project_role_is_allowed(client, project_with_roles):
    """The positive case -- the fix must not break the people the template
    actually nominates."""
    tenant_id, item, _, _ = project_with_roles
    login(client, APPROVER, PASSWORD)

    resp = _submit(client, tenant_id, item["id"])

    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["status"] == "Complete"


def test_the_assigned_owner_may_submit_even_without_a_permitted_role(client, project_with_roles):
    """Exemption 1, pinned. The admin assigns the contributor as owner; the
    contributor may then act, because being asked to act is the point of
    assignment."""
    tenant_id, item, contributor_id, _ = project_with_roles

    assign = _submit(client, tenant_id, item["id"], status="In progress", reference=None, owner_user_id=contributor_id)
    assert assign.status_code == 201, assign.text

    login(client, CONTRIB, PASSWORD)
    resp = _submit(client, tenant_id, item["id"], base_revision=2)

    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["status"] == "Complete"


def test_an_unassignable_role_vocabulary_falls_back_to_membership(client):
    """The ONE place this control deliberately fails open, pinned so it
    cannot be widened or removed silently.

    Project membership roles come from the fixed platform `Role` enum, not
    from the bound template's declared `roles`. A framework naming its own
    roles -- as agile.json and agile.v3.json do (product_owner, developer,
    facilitator; none assignable) -- therefore has `permitted_role_ids` that
    no project member's role can ever match. Enforcing strictly there would
    make every item in such a framework attestable only by a tenant
    administrator or the assigned owner.

    Recorded in docs/DEFECT_REGISTER.md as "declared role vocabulary is not
    honoured" -- the DEC07 status/outcome vocabulary gap in a different
    field. The real fix is the same indirection treatment, not widening this
    fallback."""
    register_and_login(client, "admin@fallback.example")
    tenant_id = client.post("/orgs", json={"name": "Fallback Co"}).json()["id"]
    schema = {
        "schema_version": 1,
        "tracks": ["Delivery"],
        "classes": ["Team"],
        "roles": ["product_owner", "developer"],
        "statuses": ["Not started", "Complete"],
        "decision_outcomes": ["Approve", "Hold"],
        "gates": [
            {
                "gate_id": "G1",
                "name": "Done",
                "sequence": 1,
                "class_ids": ["Team"],
                "rules": [
                    {
                        "version": 1,
                        "rule_id": "G1.R1",
                        "evidence_kind": "document",
                        "required": True,
                        "blocker_level": "hard",
                        "permitted_role_ids": ["developer"],
                        "class_ids": ["Team"],
                        "occurrence_type": "routine",
                    }
                ],
            }
        ],
    }
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "Custom", "schema_json": schema}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )

    member_id = _invite(client, tenant_id, "member@fallback.example", "contributor")
    login(client, "admin@fallback.example", PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Fallback",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "contributor"}],
        },
    ).json()
    item = project["evidence_items"][0]
    assert item["permitted_role_ids"] == ["developer"]
    assert "developer" not in {"contributor", "approver", "sponsor", "assurance_reviewer", "tenant_administrator"}, (
        "this test is only meaningful while 'developer' is NOT a platform-assignable role"
    )

    login(client, "member@fallback.example", PASSWORD)
    resp = _submit(client, tenant_id, item["id"])

    assert resp.status_code == 201, (
        f"an unassignable declared role vocabulary must fall back to membership-only, not lock everyone out: {resp.text}"
    )


def test_a_tenant_administrator_may_submit_without_a_permitted_role(client, project_with_roles):
    """Exemption 2, pinned. The admin's own project role is their tenant role
    (tenant_administrator), which is not in permitted_role_ids -- and the
    assignment workflow depends on them being able to write."""
    tenant_id, item, _, _ = project_with_roles

    resp = _submit(client, tenant_id, item["id"])

    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["status"] == "Complete"
