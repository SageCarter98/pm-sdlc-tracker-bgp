"""WP09: REQ-030 (complete open-format export, lossless clean-instance
re-import without privilege transfer), REQ-031 (own-data export always
available). BGP-F04 (BGP_Development_Review_Findings_v1.0.pdf): full
revision history, decision/exception/compensating-review content and its
survival across a SECOND export -> import hop."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

from tests.conftest import login, register_and_login
from tests.test_decisions import _complete_item, _setup_project_with_second_approver
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


def test_full_evidence_revision_history_survives_import(client):
    """BGP-F04 verification point 1/2: export a fixture with MULTIPLE
    evidence revisions and source hashes; import into a clean tenant;
    the full history -- not just current state -- must be there."""
    tenant_a = _create_org_as_admin(client, "admin@tenant-a.example")
    version_id, _ = _publish_standard_template(client, tenant_a)
    created = _create_project(client, tenant_a, version_id, "Standard-High").json()
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    client.post(
        f"/orgs/{tenant_a}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "doc-1", "source_hash": "sha256:v1"},
    )
    client.post(
        f"/orgs/{tenant_a}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "Complete", "reference": "doc-2", "source_hash": "sha256:v2"},
    )
    archive = client.post(f"/orgs/{tenant_a}/exports").json()["archive"]

    exported_item = next(
        i for p in archive["projects"] for o in p["occurrences"] for i in o["evidence_items"]
        if i["source_id"] == s1_item_id
    )
    assert len(exported_item["revisions"]) == 3, "seed-time revision 1 plus the two explicit edits above"
    assert [r["source_hash"] for r in exported_item["revisions"][-2:]] == ["sha256:v1", "sha256:v2"]

    tenant_b = _create_org_as_admin(client, "admin@tenant-a.example")
    job_id = client.post(f"/orgs/{tenant_b}/imports/validate", json={"archive": archive}).json()["id"]
    commit_report = client.post(f"/orgs/{tenant_b}/imports/{job_id}/commit").json()["commit_report"]
    # 3 seed-time revisions (one per Standard-High evidence item: S1/S2/S3)
    # plus the two explicit edits to S1 above.
    assert commit_report["counts"]["evidence_revisions"] == 5

    # Evidence items aren't independently listable, so re-export tenant_b
    # and check the just-imported item's revisions directly -- this also
    # doubles as the first half of the re-export reconciliation check.
    reexported = client.post(f"/orgs/{tenant_b}/exports").json()["archive"]
    reimported_item = next(
        i for p in reexported["projects"] for o in p["occurrences"] for i in o["evidence_items"]
        if i["source_id"] == s1_item_id
    )
    assert len(reimported_item["revisions"]) == 3
    assert [r["source_hash"] for r in reimported_item["revisions"][-2:]] == ["sha256:v1", "sha256:v2"]
    assert reimported_item["source_id"] == s1_item_id, "source_id must survive even though 'id' was regenerated on import"
    assert reimported_item["id"] != s1_item_id, "the LIVE id in tenant_b must be freshly generated, never reuse tenant_a's"


def test_unmatched_revision_author_and_timestamp_survive_reexport(client):
    """BGP-F04 follow-up (BGP_Follow_Up_Review_Findings_v1.0.pdf) verification
    point 1: import a revision whose author has no local match, then
    re-export. Both the ORIGINAL author identity and the ORIGINAL created_at
    must come back unchanged -- neither may silently become the importer's
    identity or the import's own timestamp."""
    tenant_a = _create_org_as_admin(client, "admin@tenant-a.example")
    version_id, _ = _publish_standard_template(client, tenant_a)
    created = _create_project(client, tenant_a, version_id, "Standard-High").json()
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")
    original_author_id = client.get("/auth/me").json()["id"]

    client.post(
        f"/orgs/{tenant_a}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "doc-1", "source_hash": "sha256:v1"},
    )
    archive = client.post(f"/orgs/{tenant_a}/exports").json()["archive"]
    original_item = next(
        i for p in archive["projects"] for o in p["occurrences"] for i in o["evidence_items"] if i["source_id"] == s1_item_id
    )
    original_revision = original_item["revisions"][-1]
    assert original_revision["actor_actor_id"] == original_author_id
    original_created_at = original_revision["created_at"]

    # A completely different person, no email overlap -- nothing in the
    # archive's actor list can match, so the importer becomes the live
    # actor_user_id on the imported row (existing, unchanged behaviour).
    tenant_b = _create_org_as_admin(client, "someone-else@tenant-b.example")
    job_id = client.post(f"/orgs/{tenant_b}/imports/validate", json={"archive": archive}).json()["id"]
    client.post(f"/orgs/{tenant_b}/imports/{job_id}/commit")

    reexported = client.post(f"/orgs/{tenant_b}/exports").json()["archive"]
    reexported_item = next(
        i for p in reexported["projects"] for o in p["occurrences"] for i in o["evidence_items"] if i["source_id"] == s1_item_id
    )
    reexported_revision = reexported_item["revisions"][-1]
    assert reexported_revision["actor_actor_id"] == original_author_id, (
        "an unmatched author's ORIGINAL identity must survive re-export, not silently become the importer"
    )
    assert reexported_revision["created_at"] == original_created_at, (
        "the ORIGINAL creation time must survive re-export, not silently become the import time"
    )

    # The preserved identity is still resolvable by email for a future
    # import, and is never turned into a live local account by this export.
    preserved_actor = next(a for a in reexported["actors"] if a["id"] == original_author_id)
    assert preserved_actor["email"] == "admin@tenant-a.example"
    b_admin_id = client.get("/auth/me").json()["id"]
    assert original_author_id != b_admin_id


def test_decision_exception_and_compensating_review_preserved_through_second_export(client):
    """BGP-F04 verification points 2/3: a conditional decision, a
    compensating-review override, an exception and a superseding decision
    must all still be retrievable, linked and stable-identified after an
    import -- and preserved through a SUBSEQUENT export of the importing
    tenant, not silently dropped after one hop."""
    tenant_a, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")
    s2_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S2")
    s2_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S2")

    # An exception excusing S2's hard blocker.
    now = datetime.now(timezone.utc)
    client.post(
        f"/orgs/{tenant_a}/evidence/{s2_item_id}/exceptions",
        json={"reason": "Vendor doc pending", "owner_user_id": admin_id, "starts_at": now.isoformat(), "expires_at": (now + timedelta(days=30)).isoformat()},
    )

    # Complete S1 (owned by admin -- self-only approval, needs a real
    # compensating review from approver2's own session, BGP-F02).
    _complete_item(client, tenant_a, s1_item_id)
    client.post(
        f"/orgs/{tenant_a}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "Complete", "owner_user_id": admin_id, "reference": "doc-1", "source_hash": "x"},
    )
    preview = client.post(f"/orgs/{tenant_a}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]

    login(client, "approver2@tenant-a.example")
    review_id = client.post(
        f"/orgs/{tenant_a}/projects/{project_id}/occurrences/{s1_occurrence_id}/compensating-reviews",
        json={"note": "Reviewed independently by approver2"},
    ).json()["id"]

    login(client, "admin@tenant-a.example")
    original_decision = client.post(
        f"/orgs/{tenant_a}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": digest, "separation_override": {"review_id": review_id}},
        headers={"Idempotency-Key": "hist-1"},
    ).json()

    # A superseding correction on top of it.
    superseded = client.post(
        f"/orgs/{tenant_a}/decisions/{original_decision['id']}/superseding",
        json={"outcome": "Hold", "manifest_digest": digest, "reason": "Correction for export history test"},
        headers={"Idempotency-Key": "hist-2"},
    ).json()

    archive = client.post(f"/orgs/{tenant_a}/exports").json()["archive"]
    assert len(archive["decisions"]) == 2
    assert len(archive["exceptions"]) == 1
    assert len(archive["compensating_reviews"]) == 1

    tenant_b = _create_org_as_admin(client, "admin@tenant-a.example")
    job_id = client.post(f"/orgs/{tenant_b}/imports/validate", json={"archive": archive}).json()["id"]
    commit_report = client.post(f"/orgs/{tenant_b}/imports/{job_id}/commit").json()["commit_report"]
    assert commit_report["historical_counts"]["decision"] == 2
    assert commit_report["historical_counts"]["exception"] == 1
    assert commit_report["historical_counts"]["compensating_review"] == 1
    assert commit_report["skipped_historical_broken_references"] == 0

    new_project_id = client.get(f"/orgs/{tenant_b}/projects").json()[0]["id"]

    # Re-export tenant_b -- the SECOND hop. Content must still be there,
    # keyed by the SAME source_id as the very first export, even though
    # every live id (project/occurrence) has been regenerated.
    reexported = client.post(f"/orgs/{tenant_b}/exports").json()["archive"]
    assert len(reexported["decisions"]) == 2
    assert len(reexported["exceptions"]) == 1
    assert len(reexported["compensating_reviews"]) == 1

    reexported_root = next(d for d in reexported["decisions"] if d["source_id"] == original_decision["id"])
    reexported_correction = next(d for d in reexported["decisions"] if d["source_id"] == superseded["id"])
    assert reexported_correction["supersedes_decision_id"] == original_decision["id"], "the supersession link is content, not a live FK -- it stays as first exported"
    assert reexported_correction["reason"] == "Correction for export history test"
    assert reexported_root["project_id"] == new_project_id, "the live-row reference IS remapped to tenant_b's own id"
    assert reexported_root["project_id"] != project_id

    reexported_review = reexported["compensating_reviews"][0]
    assert reexported_review["source_id"] == review_id
    assert reexported_review["note"] == "Reviewed independently by approver2"

    reexported_exception = reexported["exceptions"][0]
    assert reexported_exception["reason"] == "Vendor doc pending"


def _digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def test_commit_rejects_corrupted_archive_cleanly_without_partial_state(client):
    """BGP-F04 verification point 4: a structurally broken archive (here, a
    project pointing at a template_version that doesn't exist in the
    archive's own templates section) must fail with a clean 4xx at commit
    time, not an unhandled 500 -- and must leave no partially-created
    project behind. The digest is recomputed after tampering so this gets
    past validate() and actually exercises commit()'s own defence."""
    tenant_a = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_a)
    _create_project(client, tenant_a, version_id, "Standard-High")
    archive = client.post(f"/orgs/{tenant_a}/exports").json()["archive"]

    tampered = copy.deepcopy(archive)
    tampered["projects"][0]["template_version_id"] = "does-not-exist-in-this-archive"
    tampered["manifest"]["section_digests"]["projects"] = _digest(tampered["projects"])

    tenant_b = _create_org_as_admin(client, "admin-corrupt@tenant-a.example")
    validated = client.post(f"/orgs/{tenant_b}/imports/validate", json={"archive": tampered})
    assert validated.json()["status"] == "validated", "digest was recomputed -- this must get past validation"
    job_id = validated.json()["id"]

    committed = client.post(f"/orgs/{tenant_b}/imports/{job_id}/commit")
    assert committed.status_code == 422, committed.text
    assert "malformed" in committed.text.lower() or "missing" in committed.text.lower()

    assert client.get(f"/orgs/{tenant_b}/projects").json() == [], "a rejected commit must leave no partially-created project"
