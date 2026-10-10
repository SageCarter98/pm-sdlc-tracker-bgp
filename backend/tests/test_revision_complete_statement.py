"""An evidence-revision request is a COMPLETE STATEMENT of the item's fields.

Owner's design decision, 2026-10-08, settling the register row "A status-only
evidence revision silently clears `owner_user_id`, `due_date` and
`completed_date`".

The two candidate readings of that defect were a missing partial-update
semantic, or an undocumented complete-statement contract. The owner chose the
second: `EvidenceItem` mirroring the latest `EvidenceRevision` is intended, so
each revision is a whole statement of the item's state and `None` legitimately
means "no owner". What was wrong was never the mirroring -- it was that the
request model let a caller OMIT those fields and receive a 201, so ownership
and dates were lost by accident rather than by instruction.

The fix therefore makes the four mirrored fields required and still nullable:
clearing an owner stays possible, but only when a caller says so explicitly.
`source_version` and `source_hash` are deliberately NOT included -- they are
recorded on the revision and never mirrored onto the item, so they are not
part of this contract.
"""

import pytest

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3

MIRRORED_FIELDS = ["owner_user_id", "due_date", "completed_date", "reference"]


@pytest.fixture()
def owned_item(client):
    """An item carrying an owner and a due date, both set by a complete
    revision -- the state a status-only revision used to wipe."""
    register_and_login(client, "admin@completestmt.example")
    enable_mfa(client)
    admin_id = client.get("/auth/me").json()["id"]
    tenant_id = client.post("/orgs", json={"name": "Complete Stmt Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    )
    assert project.status_code == 201, project.text
    item = project.json()["evidence_items"][0]

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={
            "base_revision": 1,
            "status": "Not met",
            "owner_user_id": admin_id,
            "due_date": "2026-12-01T00:00:00",
            "completed_date": None,
            "reference": None,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["owner_user_id"] == admin_id
    return tenant_id, item["id"], admin_id


@pytest.mark.parametrize("omitted", MIRRORED_FIELDS)
def test_a_revision_omitting_a_mirrored_field_is_refused(client, owned_item, omitted):
    """The defect itself: such a payload used to return 201 and silently blank
    the omitted field on the item."""
    tenant_id, item_id, admin_id = owned_item
    payload = {
        "base_revision": 2,
        "status": "Not met",
        "owner_user_id": admin_id,
        "due_date": "2026-12-01T00:00:00",
        "completed_date": None,
        "reference": None,
    }
    del payload[omitted]

    resp = client.post(f"/orgs/{tenant_id}/evidence/{item_id}/revisions", json=payload)

    assert resp.status_code == 422, f"omitting {omitted} must be refused, not mirrored as None"
    assert omitted in resp.text, f"the refusal must name {omitted} so a caller can fix the payload"


def test_a_refused_revision_leaves_the_owner_and_due_date_intact(client, owned_item):
    """A refusal that still mutated the item would be worse than the defect it
    replaces, so the preserved state is asserted, not assumed."""
    tenant_id, item_id, admin_id = owned_item

    refused = client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/revisions",
        json={"base_revision": 2, "status": "Not met"},
    )
    assert refused.status_code == 422, refused.text

    item = client.get(f"/orgs/{tenant_id}/evidence/{item_id}").json()["item"]
    assert item["owner_user_id"] == admin_id
    assert item["due_date"] is not None
    assert item["latest_revision_number"] == 2, "a refused revision must not have been recorded"


def test_an_explicit_null_still_clears_the_owner(client, owned_item):
    """The complete-statement contract keeps clearing available -- it only
    requires that the caller ask for it."""
    tenant_id, item_id, _ = owned_item

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/revisions",
        json={
            "base_revision": 2,
            "status": "Not met",
            "owner_user_id": None,
            "due_date": None,
            "completed_date": None,
            "reference": None,
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["owner_user_id"] is None
    assert resp.json()["item"]["due_date"] is None


def test_a_complete_revision_carries_the_owner_and_due_date_forward(client, owned_item):
    """REQ-017 requires owner, due date and completion date to stay tracked
    across a routine status change."""
    tenant_id, item_id, admin_id = owned_item

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/revisions",
        json={
            "base_revision": 2,
            "status": "Not met",
            "owner_user_id": admin_id,
            "due_date": "2026-12-01T00:00:00",
            "completed_date": None,
            "reference": None,
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["owner_user_id"] == admin_id, "REQ-017: ownership must survive a status change"
    assert resp.json()["item"]["due_date"] is not None


def test_source_version_and_hash_stay_optional(client, owned_item):
    """They are recorded on the revision but never mirrored onto the item, so
    they are outside this contract and must not have been swept into it."""
    tenant_id, item_id, admin_id = owned_item

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/revisions",
        json={
            "base_revision": 2,
            "status": "Not met",
            "owner_user_id": admin_id,
            "due_date": None,
            "completed_date": None,
            "reference": None,
        },
    )

    assert resp.status_code == 201, resp.text


def test_the_ui_submit_form_carries_the_owner_and_dates_forward(client, owned_item):
    """UI04's Submit button is the live caller of this endpoint, and it only
    collects status and reference -- the two fields its form actually edits.
    Under the complete-statement contract that form must restate the owner
    and dates it is NOT editing, or it becomes the very wiper this contract
    exists to prevent (which it was: `webapp/router.py` built the payload
    from status and reference alone, so every UI submit cleared ownership).
    Making the fields required turns that silent loss into a crash unless
    the form carries them forward, so both halves are asserted here."""
    tenant_id, item_id, admin_id = owned_item

    resp = client.post(
        f"/ui/orgs/{tenant_id}/evidence/{item_id}/submit",
        data={"status": "Not met", "reference": "ui-ref"},
    )

    assert resp.status_code == 200, resp.text[:800]
    item = client.get(f"/orgs/{tenant_id}/evidence/{item_id}").json()["item"]
    assert item["latest_revision_number"] == 3, "the UI submit must have been recorded"
    assert item["reference"] == "ui-ref", "the field the form DOES edit must still take effect"
    assert item["owner_user_id"] == admin_id, "the UI submit must not clear the owner it never asked about"
    assert item["due_date"] is not None, "nor the due date"
