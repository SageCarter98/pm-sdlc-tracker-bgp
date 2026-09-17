"""WP10/REQ-034: save and resume drafts."""
from tests.test_projects import _create_org_as_admin


def test_create_resume_and_update_a_draft(client):
    tenant_id = _create_org_as_admin(client)

    missing = client.get(f"/orgs/{tenant_id}/drafts/evidence:abc")
    assert missing.status_code == 404

    created = client.put(f"/orgs/{tenant_id}/drafts/evidence:abc", json={"base_revision": 0, "form_data": {"note": "first pass"}})
    assert created.status_code == 200, created.text
    assert created.json()["revision"] == 1

    resumed = client.get(f"/orgs/{tenant_id}/drafts/evidence:abc")
    assert resumed.status_code == 200
    assert resumed.json()["form_data"] == {"note": "first pass"}

    updated = client.put(f"/orgs/{tenant_id}/drafts/evidence:abc", json={"base_revision": 1, "form_data": {"note": "second pass"}})
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["form_data"] == {"note": "second pass"}


def test_stale_base_revision_conflicts(client):
    tenant_id = _create_org_as_admin(client)
    client.put(f"/orgs/{tenant_id}/drafts/evidence:abc", json={"base_revision": 0, "form_data": {"note": "v1"}})

    conflict = client.put(f"/orgs/{tenant_id}/drafts/evidence:abc", json={"base_revision": 0, "form_data": {"note": "clobber"}})
    assert conflict.status_code == 409


def test_discard_draft(client):
    tenant_id = _create_org_as_admin(client)
    client.put(f"/orgs/{tenant_id}/drafts/evidence:abc", json={"base_revision": 0, "form_data": {"note": "v1"}})

    deleted = client.delete(f"/orgs/{tenant_id}/drafts/evidence:abc")
    assert deleted.status_code == 204

    gone = client.get(f"/orgs/{tenant_id}/drafts/evidence:abc")
    assert gone.status_code == 404


def test_drafts_are_owner_scoped_not_visible_to_other_tenant_members(client):
    from tests.test_projects import _invite_and_accept
    from tests.conftest import register_and_login

    tenant_id = _create_org_as_admin(client)
    client.put(f"/orgs/{tenant_id}/drafts/evidence:abc", json={"base_revision": 0, "form_data": {"note": "admin's private draft"}})

    _invite_and_accept(client, tenant_id, "contributor@tenant-a.example", "contributor")
    # _invite_and_accept leaves the invited user logged in
    hidden = client.get(f"/orgs/{tenant_id}/drafts/evidence:abc")
    assert hidden.status_code == 404

    listing = client.get(f"/orgs/{tenant_id}/drafts")
    assert listing.json() == []

    register_and_login(client, "admin@tenant-a.example")
    own_listing = client.get(f"/orgs/{tenant_id}/drafts")
    assert len(own_listing.json()) == 1
