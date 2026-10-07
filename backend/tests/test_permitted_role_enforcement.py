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

# Fresh users for the regulated.json/vocabulary-1 fixture below -- kept
# separate from ADMIN/CONTRIB/APPROVER above, which belong to the
# standard-framework fixture, so the two fixtures cannot interfere.
REG_ADMIN = "regadmin@roleenf.example"
REG_ASSURANCE = "regassurance@roleenf.example"
REG_APPROVER = "regapprover@roleenf.example"


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


@pytest.fixture()
def project_with_regulated_roles(client):
    """TST-032 fix round 1, Finding 2 / Ruling 5: pins vocabulary-1 ("no
    vocabulary_version key") attest enforcement using regulated.json's R2
    gate, rule R2.R1, whose permitted_role_ids is exactly
    ["assurance_reviewer"] -- a platform role that attests but is not a
    decision authority (it is absent from
    app.models.ROLES_REQUIRING_MFA and from
    app.routers.decisions.DECISION_AUTHORITY_ROLES). An approver member is
    also seeded, since approver IS a decision authority and IS in
    ROLES_REQUIRING_MFA -- the second test below needs both facts true of
    that member to prove deciding authority does not imply attest
    authority."""
    register_and_login(client, REG_ADMIN)
    tenant_id = client.post("/orgs", json={"name": "Regulated Role Enforcement Co"}).json()["id"]
    schema = json.loads((FIXTURES_DIR / "regulated.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "Regulated", "schema_json": schema}
    ).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )

    assurance_id = _invite(client, tenant_id, REG_ASSURANCE, "assurance_reviewer")
    # _invite leaves us as the invited user, and only a tenant administrator
    # may issue an invitation -- so come back as the admin first.
    login(client, REG_ADMIN, PASSWORD)
    approver_id = _invite(client, tenant_id, REG_APPROVER, "approver")
    enable_mfa(client)  # approver role requires MFA (models.ROLES_REQUIRING_MFA)

    login(client, REG_ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Regulated Role Enforcement",
            "template_version_id": created["id"],
            "class_id": "Regulated-Standard",
            "members": [
                {"user_id": assurance_id, "role": "assurance_reviewer"},
                {"user_id": approver_id, "role": "approver"},
            ],
        },
    ).json()

    item = next(e for e in project["evidence_items"] if e["gate_id"] == "R2")
    assert item["permitted_role_ids"] == ["assurance_reviewer"], (
        f"these tests need R2.R1's declared permitted role; regulated.json gave {item['permitted_role_ids']}"
    )
    return tenant_id, item, assurance_id, approver_id


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


def test_a_permitted_non_deciding_role_may_attest_at_vocabulary_1(client, project_with_regulated_roles):
    """Pins that "permitted to attest" is driven by the template's declared
    permitted_role_ids, not by whether a role can decide a gate.
    assurance_reviewer attests R2.R1 but is absent from
    DECISION_AUTHORITY_ROLES -- it may not decide any gate. If this ever
    fails, attest authority has become tied to decision authority, which
    would silently break every regulated-framework project relying on an
    assurance reviewer (not an approver, sponsor, or tenant administrator)
    to supply this evidence."""
    tenant_id, item, _, _ = project_with_regulated_roles
    login(client, REG_ASSURANCE, PASSWORD)

    resp = _submit(client, tenant_id, item["id"])

    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["status"] == "Complete"


def test_an_unnamed_decider_is_refused_at_vocabulary_1(client, project_with_regulated_roles):
    """The sharp half of the pin: a platform decider the rule does not name
    is still refused. approver IS in DECISION_AUTHORITY_ROLES (may decide
    gates) and IS in ROLES_REQUIRING_MFA, but R2.R1 names only
    assurance_reviewer -- deciding authority must not imply attest
    authority. If this ever fails, any approver could attest an item the
    template deliberately restricted to assurance reviewers."""
    tenant_id, item, _, _ = project_with_regulated_roles
    login(client, REG_APPROVER, PASSWORD)

    resp = _submit(client, tenant_id, item["id"])

    assert resp.status_code == 403, resp.text
    assert "role" in resp.text.lower()

    # And nothing landed: the refusal must be before the insert, not after.
    login(client, REG_ADMIN, PASSWORD)
    detail = client.get(f"/orgs/{tenant_id}/evidence/{item['id']}").json()
    assert detail["item"]["status"] != "Complete"
    assert detail["item"]["latest_revision_number"] == 1


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


def test_a_non_permitted_role_cannot_displace_the_active_attachment(client, project_with_roles):
    """Attachment upload answers the same question and so gets the same
    control -- because an upload SUPERSEDES whatever was active.

    Probed 2026-10-04 before the check existed: a contributor's upload to an
    approver-only item returned 201, leaving the approver's file
    'superseded' and the contributor's 'active'. The displacement was
    attributed (`uploaded_by_user_id`) and reversible (nothing is deleted),
    which is why it was Medium rather than High -- but the active evidence a
    reviewer sees must not be swappable by a role the template never
    permitted."""
    tenant_id, item, _, _ = project_with_roles
    url = f"/orgs/{tenant_id}/evidence/{item['id']}/attachments"

    login(client, APPROVER, PASSWORD)
    first = client.post(url, files={"file": ("approved.txt", b"approver evidence", "text/plain")})
    assert first.status_code == 201, first.text

    login(client, CONTRIB, PASSWORD)
    refused = client.post(url, files={"file": ("contributor.txt", b"contributor evidence", "text/plain")})
    assert refused.status_code == 403, refused.text

    # The point of the test: the approver's attachment is still the active
    # one. A refusal that still superseded would be worse than useless.
    listing = client.get(url)
    assert listing.status_code == 200, listing.text
    active = [a for a in listing.json() if a["status"] == "active"]
    assert len(active) == 1, listing.json()
    assert active[0]["filename"] == "approved.txt"


def test_a_permitted_role_may_still_upload_an_attachment(client, project_with_roles):
    """The positive half -- the attachment check must not lock out the people
    the template nominates."""
    tenant_id, item, _, _ = project_with_roles
    login(client, APPROVER, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/attachments",
        files={"file": ("approved.txt", b"approver evidence", "text/plain")},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "active"


V4_ATTEST = {
    "schema_version": 1,
    "vocabulary_version": 4,
    "tracks": ["Delivery"],
    "classes": ["Team"],
    "roles": [
        {"id": "product_owner", "attests": True, "decides": True},
        {"id": "observer", "attests": False},
    ],
    "statuses": [{"id": "Not met", "initial": True}, {"id": "Met", "satisfies": True}],
    "decision_outcomes": [{"id": "Accept", "kind": "approving"}],
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
                    "permitted_role_ids": ["product_owner"],
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                }
            ],
        }
    ],
}


def test_a_v4_declared_role_may_attest_without_being_a_platform_role(client):
    """The payoff: 'product_owner' is not a platform Role, and at v4 it no
    longer has to be. This is the case the fallback used to swallow."""
    register_and_login(client, "admin@v4attest.example")
    tenant_id = client.post("/orgs", json={"name": "V4 Attest Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": V4_ATTEST}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    member_id = _invite(client, tenant_id, "po@v4attest.example", "contributor")
    login(client, "admin@v4attest.example", PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "V4 Attest",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "product_owner"}],
        },
    ).json()
    item = project["evidence_items"][0]

    login(client, "po@v4attest.example", PASSWORD)
    resp = _submit(client, tenant_id, item["id"], status="Met")

    assert resp.status_code == 201, resp.text


def test_the_unassignable_fallback_does_not_apply_at_v4(client):
    """G6: below v4 the fallback is the only thing keeping custom-role
    frameworks usable; at v4 declared roles are assignable, so a role the
    rule does not name must be refused rather than waved through."""
    register_and_login(client, "admin@v4fb.example")
    tenant_id = client.post("/orgs", json={"name": "V4 FB Co"}).json()["id"]
    schema = dict(V4_ATTEST)
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": schema}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    # 'observer' declares attests: false and is not in permitted_role_ids.
    member_id = _invite(client, tenant_id, "obs@v4fb.example", "contributor")
    login(client, "admin@v4fb.example", PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "V4 FB",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "observer"}],
        },
    ).json()
    item = project["evidence_items"][0]

    login(client, "obs@v4fb.example", PASSWORD)
    resp = _submit(client, tenant_id, item["id"], status="Met")

    assert resp.status_code == 403, resp.text
