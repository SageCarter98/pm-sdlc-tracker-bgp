"""DEC07: the authoring and evidence UIs must render a structured status
and decision-outcome list as ids, not as Python dict reprs."""

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3


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
    """Amendment 2: decision_outcomes carries the identical defect two lines
    below each statuses `|join` in template_editor.html -- a v3 template's
    outcomes are just as likely to reach this page as its statuses."""
    tenant_id, created, _ = _setup(client)
    page = client.get(f"/ui/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}")
    assert page.status_code == 200, page.text
    body = page.text
    _assert_no_dict_repr(body)
    assert "OutcomeDefinition" not in body
    for outcome_id in ("Increment accepted", "Not accepted"):
        assert outcome_id in body, f"{outcome_id} missing from the rendered decision outcomes"
