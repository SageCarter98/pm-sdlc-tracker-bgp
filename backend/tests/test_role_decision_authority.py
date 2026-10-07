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
    assert resp.json()["detail"] == "Role does not permit recording decisions", resp.text


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
    assert resp.json()["detail"] == "Role does not permit recording decisions", resp.text


def test_a_declared_decider_can_record_a_compensating_review(client, v4_project):
    """The positive half, so the test above cannot pass for the wrong
    reason (e.g. the endpoint refusing everyone)."""
    tenant_id, project, decider_id, _ = v4_project
    occurrence_id = project["occurrences"][0]["id"]

    login(client, DECIDER, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/compensating-reviews",
        json={"note": "I looked at it"},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["note"] == "I looked at it"
    assert body["reviewer_user_id"] == decider_id


def test_the_tenant_layer_set_is_unchanged_and_still_platform_fixed():
    """Spec Sec.3.1: tenant roles gate MFA and endpoint access and predate
    any template binding, so this set must NOT become template-declared."""
    assert TENANT_DECISION_AUTHORITY_ROLES == {"approver", "sponsor", "tenant_administrator"}


def test_a_v1_project_members_approver_may_still_attest_as_before(client):
    """Fix round 1, minor item 1: this test is misnamed and does not test
    DECIDING -- it ends on an evidence-revision POST and would pass even
    with the decision-authority gate deleted outright. Renamed honestly to
    say what it actually covers (attestation on a standard v1 fixture);
    actually DECIDING on a v1-3 binding, by someone other than the tenant
    administrator, is covered end to end by
    test_a_tenant_sponsor_may_still_decide_on_a_lightweight_v1_binding and
    test_a_tenant_approver_may_still_decide_on_an_agile_v3_binding below."""
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


CONTRIBUTOR = "contributor@roledec.example"


def test_a_project_approver_whose_tenant_role_is_contributor_is_now_refused(client):
    """Ruling 13 (Critical 1): the deliberate tightening. Before this fix,
    _project_role_decides took tenant_role but only ever used it to GRANT
    (the tenant-administrator carve-out) -- it never required tenant_role
    to be a platform decider at all, and nothing else on this path does
    either (decisions.py has no Depends(require_role(...)), only
    require_mfa, which never restricts role). So a member whose PROJECT
    role is 'approver' but whose TENANT role is only 'contributor' -- an
    admin can create exactly that pairing today, assigning a project role
    that differs from the member's tenant role -- could decide before this
    fix and must not be able to after it. That is the privilege-escalation
    path spec Sec.4's intersection exists to close.

    No evidence preparation is needed: the tenant-floor check inside
    _require_decision_authority runs before readiness/outcome evaluation,
    so this is refused at the authority gate regardless of the payload."""
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Escalation Co"}).json()["id"]
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
    # 'contributor' is not in ROLES_REQUIRING_MFA, so no enable_mfa() call
    # is needed for this user to pass the require_mfa dependency.
    mismatched_id = _invite(client, tenant_id, CONTRIBUTOR, "contributor")
    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Escalation",
            "template_version_id": created["id"],
            "class_id": "Standard-High",
            "members": [{"user_id": mismatched_id, "role": "approver"}],
        },
    ).json()
    occurrence_id = project["occurrences"][0]["id"]

    login(client, CONTRIBUTOR, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": "irrelevant-authority-denies-first"},
        headers={"Idempotency-Key": "escalation-1"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "Role does not permit recording decisions", resp.text


LIGHTWEIGHT_SPONSOR = "sponsor@roledec.example"


def test_a_tenant_sponsor_may_still_decide_on_a_lightweight_v1_binding(client):
    """Ruling 14 (Critical 2), the exact case that regressed: lightweight.json
    declares roles ["contributor", "approver"] -- it was never written to
    enumerate 'sponsor' -- so a declaration-only check wrongly refuses a
    tenant sponsor who held decision authority before this commit. The
    vocabulary<=3 legacy branch answers WITHOUT regard to declaration,
    testing the project role against rule_engine._LEGACY_DECIDING_ROLES
    directly, exactly reproducing the old behaviour."""
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Lightweight Co"}).json()["id"]
    schema = json.loads((FIXTURES_DIR / "lightweight.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    assert "sponsor" not in schema["roles"], "this test only means something while lightweight.json omits sponsor"
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "Lightweight", "schema_json": schema}
    ).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    sponsor_id = _invite(client, tenant_id, LIGHTWEIGHT_SPONSOR, "sponsor")
    enable_mfa(client)
    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Small thing",
            "template_version_id": created["id"],
            "class_id": "Light",
            "members": [{"user_id": sponsor_id, "role": "sponsor"}],
        },
    ).json()
    item = next(e for e in project["evidence_items"] if e["gate_id"] == "L1")

    # ADMIN (tenant_administrator) attests via _require_permitted_to_attest's
    # existing exemption, so the sponsor below is a different actor from
    # the preparer and REQ-006 self-only-approval never triggers.
    assert (
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
        ).status_code
        == 201
    )

    login(client, LIGHTWEIGHT_SPONSOR, PASSWORD)
    occurrence_id = next(o["id"] for o in project["occurrences"] if o["gate_id"] == "L1")
    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/preview", json={}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["hard_blockers"] == []

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": preview.json()["manifest_digest"]},
        headers={"Idempotency-Key": "lightweight-sponsor-1"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["outcome"] == "Approve"


AGILE_V3_APPROVER = "approver@agilev3.example"


def test_a_tenant_approver_may_still_decide_on_an_agile_v3_binding(client):
    """Ruling 14's second required case: a decision recorded by someone who
    is NOT the tenant administrator, so the admin carve-out in
    _project_role_decides cannot be what makes it pass -- agile.json's
    `roles` list (product_owner/developer/facilitator) has never declared
    a platform decider either, the same regression as lightweight.json.

    agile.v3.json, not agile.json (true v2), is used here: agile.json's own
    decision_outcomes ('Increment accepted', 'Not accepted') never resolve
    to a kind at vocabulary 2 -- a separate, already-pinned gap
    (test_the_v1_fixture_is_retained_and_still_fails_closed in
    test_dec07_q11_agile_fixture.py) that makes ANY decision on it
    impossible regardless of role. agile.v3.json is vocabulary_version 3 --
    still inside Ruling 14's '<=3' legacy branch -- and its roles are still
    bare strings, so this exercises exactly the same code path.

    'Not accepted' is declared recording-kind, so no evidence preparation
    is needed: a recording outcome is eligible regardless of hard
    blockers (Blueprint Sec.2.2), which keeps this test about AUTHORITY,
    not readiness."""
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Agile V3 Co"}).json()["id"]
    schema = json.loads((FIXTURES_DIR / "agile.v3.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    assert schema["vocabulary_version"] == 3
    assert "approver" not in schema["roles"], "this test only means something while agile.v3.json omits approver"
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "Agile V3", "schema_json": schema}
    ).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    approver_id = _invite(client, tenant_id, AGILE_V3_APPROVER, "approver")
    enable_mfa(client)
    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Squad",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": approver_id, "role": "approver"}],
        },
    ).json()
    occurrence_id = project["occurrences"][0]["id"]

    login(client, AGILE_V3_APPROVER, PASSWORD)
    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/preview", json={}
    )
    assert preview.status_code == 200, preview.text

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Not accepted", "manifest_digest": preview.json()["manifest_digest"]},
        headers={"Idempotency-Key": "agile-v3-approver-1"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["outcome"] == "Not accepted"
