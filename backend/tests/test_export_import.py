"""WP09: REQ-030 (complete open-format export, lossless clean-instance
re-import without privilege transfer), REQ-031 (own-data export always
available)."""
import copy

from tests.conftest import register_and_login
from tests.test_projects import _create_org_as_admin, _create_project, _publish_standard_template


def test_export_produces_self_verifying_archive(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    created = _create_project(client, tenant_id, version_id, "Standard-High").json()

    resp = client.post(f"/orgs/{tenant_id}/exports")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    archive = body["archive"]

    assert len(archive["templates"]) == 1
    assert len(archive["projects"]) == 1
    assert archive["projects"][0]["id"] == created["project"]["id"]

    # digests are self-verifying -- an independent recompute must match
    # exactly what validate() will later check.
    import hashlib
    import json

    for section, expected in archive["manifest"]["section_digests"].items():
        recomputed = hashlib.sha256(json.dumps(archive[section], sort_keys=True, default=str).encode()).hexdigest()
        assert recomputed == expected, f"section {section} digest does not self-verify"

    fetched = client.get(f"/orgs/{tenant_id}/exports/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["archive"] == archive


def test_tampered_archive_is_rejected_at_validation(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    _create_project(client, tenant_id, version_id, "Standard-High")
    archive = client.post(f"/orgs/{tenant_id}/exports").json()["archive"]

    tampered = copy.deepcopy(archive)
    tampered["projects"][0]["name"] = "Sneaky rename after export"

    resp = client.post(f"/orgs/{tenant_id}/imports/validate", json={"archive": tampered})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert any("projects" in e for e in body["validation_report"]["errors"])


def test_unsupported_format_version_is_rejected(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    _create_project(client, tenant_id, version_id, "Standard-High")
    archive = client.post(f"/orgs/{tenant_id}/exports").json()["archive"]
    archive["manifest"]["format_version"] = 999

    resp = client.post(f"/orgs/{tenant_id}/imports/validate", json={"archive": archive})
    assert resp.json()["status"] == "rejected"
    assert any("format_version" in e for e in resp.json()["validation_report"]["errors"])


def test_round_trip_import_recreates_current_state_with_matched_actor(client):
    tenant_a = _create_org_as_admin(client, "admin@tenant-a.example")
    version_id, _ = _publish_standard_template(client, tenant_a)
    created = _create_project(client, tenant_a, version_id, "Standard-High").json()
    project_id = created["project"]["id"]
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")
    client.post(
        f"/orgs/{tenant_a}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "doc-1", "source_hash": "x"},
    )
    archive = client.post(f"/orgs/{tenant_a}/exports").json()["archive"]

    # Same real person (same email) sets up a second, independent tenant --
    # this is the "clean instance" scenario: their identity carries over
    # because the email matches, nothing else does.
    tenant_b = _create_org_as_admin(client, "admin@tenant-a.example")

    validated = client.post(f"/orgs/{tenant_b}/imports/validate", json={"archive": archive})
    assert validated.status_code == 201, validated.text
    assert validated.json()["status"] == "validated"
    job_id = validated.json()["id"]
    assert validated.json()["validation_report"]["unmatched_actor_count"] == 0

    committed = client.post(f"/orgs/{tenant_b}/imports/{job_id}/commit")
    assert committed.status_code == 201, committed.text
    report = committed.json()["commit_report"]
    assert report["counts"]["projects"] == 1
    assert report["counts"]["evidence_items"] == 3
    assert report["unmatched_actor_count"] == 0

    listing = client.get(f"/orgs/{tenant_b}/projects").json()
    assert len(listing) == 1
    assert listing[0]["id"] != project_id, "imported project must get a fresh id, never reuse the source id"
    assert listing[0]["name"] == created["project"]["name"]


def test_unmatched_actor_falls_back_to_importer_not_fabricated(client):
    tenant_a = _create_org_as_admin(client, "admin@tenant-a.example")
    version_id, _ = _publish_standard_template(client, tenant_a)
    _create_project(client, tenant_a, version_id, "Standard-High")
    archive = client.post(f"/orgs/{tenant_a}/exports").json()["archive"]

    # A completely different person imports this into their own tenant --
    # no email overlap, so nothing in the archive's actor list can match.
    tenant_b = _create_org_as_admin(client, "someone-else@tenant-b.example")
    b_admin_login = client.post("/auth/login", json={"email": "someone-else@tenant-b.example", "password": "correct horse battery staple"})
    b_admin_id = b_admin_login.json()["id"]

    validated = client.post(f"/orgs/{tenant_b}/imports/validate", json={"archive": archive})
    assert validated.json()["validation_report"]["unmatched_actor_count"] == validated.json()["validation_report"]["section_counts"].get("actors", 0)
    job_id = validated.json()["id"]

    committed = client.post(f"/orgs/{tenant_b}/imports/{job_id}/commit")
    assert committed.status_code == 201, committed.text
    assert committed.json()["commit_report"]["counts"]["project_memberships"] == 0, "no live user existed to attach an unmatched historical member to"

    project = client.get(f"/orgs/{tenant_b}/projects").json()[0]
    assert project["owner_user_id"] == b_admin_id, "an unmatched required owner must fall back to the importing user, never a fabricated identity"


def test_commit_requires_validated_status_first(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    _create_project(client, tenant_id, version_id, "Standard-High")
    archive = client.post(f"/orgs/{tenant_id}/exports").json()["archive"]

    validated = client.post(f"/orgs/{tenant_id}/imports/validate", json={"archive": archive})
    job_id = validated.json()["id"]

    first_commit = client.post(f"/orgs/{tenant_id}/imports/{job_id}/commit")
    assert first_commit.status_code == 201, first_commit.text

    second_commit = client.post(f"/orgs/{tenant_id}/imports/{job_id}/commit")
    assert second_commit.status_code == 409


def test_import_requires_tenant_administrator_role(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    _create_project(client, tenant_id, version_id, "Standard-High")
    archive = client.post(f"/orgs/{tenant_id}/exports").json()["archive"]

    token = client.post(f"/orgs/{tenant_id}/invitations", json={"email": "c@tenant-a.example", "role": "contributor"}).json()["token"]
    register_and_login(client, "c@tenant-a.example")
    client.post("/invitations/accept", json={"token": token})

    resp = client.post(f"/orgs/{tenant_id}/imports/validate", json={"archive": archive})
    assert resp.status_code == 403
