"""DEC07: the authoring and evidence UIs must render a structured status
and decision-outcome list as ids, not as Python dict reprs."""

from tests.conftest import enable_mfa, login, register_and_login
from tests.test_dec07_readiness_semantics import V3
from tests.test_projects import _invite_and_accept

# I8: a v3 template whose approving outcome requires conditions
# (`conditional_approving`) -- used to pin that the webapp decide form
# resolves the conditions fieldset and the ConditionsIn it builds through
# `outcome_lookup()`'s declared `kind`, not the literal "Approve with
# conditions" (webapp/router.py's `_conditional_outcome_ids`). The rule is
# advisory on purpose, so hard_blockers is always empty and the outcome's
# own eligibility (conditions present, owner set, deadline in the future)
# is the only thing gating acceptance.
V3_CONDITIONAL = {
    "vocabulary_version": 3,
    "tracks": ["Increment"],
    "classes": ["Team"],
    "roles": ["developer"],
    "statuses": [
        {"id": "Not met", "initial": True},
        {"id": "Met", "satisfies": True},
    ],
    "decision_outcomes": [
        {"id": "Accept", "kind": "approving"},
        {"id": "Accept with follow-ups", "kind": "conditional_approving"},
    ],
    "gates": [
        {
            "gate_id": "dod",
            "name": "Definition of Done",
            "sequence": 1,
            "class_ids": ["Team"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "dod.note",
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                    "evidence_kind": "note",
                    "permitted_role_ids": ["developer"],
                    "blocker_level": "advisory",
                }
            ],
        }
    ],
}


def _assert_no_dict_repr(body: str) -> None:
    """A structured status/outcome entry is a Pydantic object with an `id`
    key. Jinja's default autoescape turns a literal `{'id': ...}` repr into
    `{&#39;id&#39;: ...}` before it reaches the response body, so the
    un-escaped fragment never actually appears -- check the form that does."""
    assert "{'id'" not in body and '{"id"' not in body, "a dict repr leaked into the page unescaped"
    assert "&#39;id&#39;" not in body, "an HTML-escaped dict repr leaked into the page"


def _setup(client):
    register_and_login(client, "admin@ui.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "UI Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()
    return tenant_id, created, project


def test_evidence_form_offers_declared_status_ids(client):
    tenant_id, _, project = _setup(client)
    item_id = project["evidence_items"][0]["id"]
    page = client.get(f"/ui/orgs/{tenant_id}/evidence/{item_id}")
    assert page.status_code == 200, page.text
    body = page.text

    for status_id in ("Not met", "Met", "Waived"):
        assert f'value="{status_id}"' in body, f"{status_id} missing from the status control"
    assert "StatusDefinition" not in body
    _assert_no_dict_repr(body)


def test_template_editor_renders_status_ids_not_dict_reprs(client):
    tenant_id, created, _ = _setup(client)
    page = client.get(f"/ui/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}")
    assert page.status_code == 200, page.text
    _assert_no_dict_repr(page.text)
    for status_id in ("Not met", "Met", "Waived"):
        assert status_id in page.text, f"{status_id} missing from the rendered statuses"


def test_template_editor_renders_outcome_ids_not_dict_reprs(client):
    """decision_outcomes carries the identical defect two lines below each
    statuses `|join` in template_editor.html -- a v3 template's outcomes
    are just as likely to reach this page as its statuses."""
    tenant_id, created, _ = _setup(client)
    page = client.get(f"/ui/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}")
    assert page.status_code == 200, page.text
    body = page.text
    _assert_no_dict_repr(body)
    assert "OutcomeDefinition" not in body
    for outcome_id in ("Increment accepted", "Not accepted"):
        assert outcome_id in body, f"{outcome_id} missing from the rendered decision outcomes"


def test_decide_page_offers_conditions_for_a_declared_conditional_outcome(client):
    """I8: before the fix, the conditions fieldset and the ConditionsIn
    built from it were keyed on the literal "Approve with conditions", so a
    v3 template's own `conditional_approving` outcome ("Accept with
    follow-ups" here) rendered no fieldset at all -- the form had no way to
    collect a condition owner or deadline for it."""
    register_and_login(client, "admin@webappcond.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Cond Co"}).json()["id"]
    approver_id = _invite_and_accept(client, tenant_id, "approver@webappcond.example", "approver")
    enable_mfa(client)

    login(client, "admin@webappcond.example")
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "V3Cond", "schema_json": V3_CONDITIONAL}
    ).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Squad",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": approver_id, "role": "approver"}],
        },
    ).json()
    project_id = project["project"]["id"]
    occurrence_id = project["occurrences"][0]["id"]

    # admin seeded (and so prepared) the evidence; the approver decides --
    # not the sole preparer, so this is deliberately not a
    # separation-of-duties case.
    login(client, "approver@webappcond.example")
    decide_url = f"/ui/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide"
    page = client.get(decide_url)
    assert page.status_code == 200, page.text
    body = page.text
    assert "Accept with follow-ups" in body, "the declared conditional_approving outcome must be offered"
    assert "condition_owner_user_id" in body, "no conditions fieldset rendered for the declared outcome"

    digest = body.split('name="manifest_digest" value="')[1].split('"')[0]
    key = body.split('name="idempotency_key" value="')[1].split('"')[0]

    resp = client.post(
        decide_url,
        data={
            "outcome": "Accept with follow-ups",
            "manifest_digest": digest,
            "idempotency_key": key,
            "condition_items": "Close out the follow-up ticket",
            "condition_owner_user_id": approver_id,
            "condition_deadline": "2099-01-01T00:00",
        },
    )
    assert resp.status_code == 200, resp.text
    assert "missing deadline or condition owner" not in resp.text, (
        "ConditionsIn was not built -- the outcome is still being matched by literal, not by declared kind"
    )
    assert "There is a problem" not in resp.text, resp.text
    assert "Accept with follow-ups" in resp.text
