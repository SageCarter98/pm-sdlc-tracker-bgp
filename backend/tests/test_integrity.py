"""WP08: REQ-026 (hash-chain tamper detection) and REQ-027 (open incidents
block new decisions). Pure application-layer logic -- runs against the
SQLite test fixture like every other functional test; the *database-role*
half of REQ-026 (not even bgp_owner can UPDATE/DELETE a checkpoint) is
Postgres-only and lives in test_wp08_tenant_isolation_rls.py instead."""

from app.db import get_db
from app.main import app
from app.models import AuditEvent
from tests.conftest import login
from tests.test_decisions import _setup_project_with_second_approver


def _get_db_session():
    return next(app.dependency_overrides[get_db]())


def _record_one_approval(client, tenant_id, created, approver_id, key="k1"):
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    # BGP-F02 follow-up: preparation is attributed to whoever actually calls
    # this endpoint (EvidenceRevision.actor_user_id), not to the named
    # owner_user_id field -- approver2 has to genuinely be the one who
    # completes this item so admin (the decider below) is a real, different
    # preparer, not just a different name written into a field admin itself
    # submitted.
    login(client, "approver2@tenant-a.example")
    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "owner_user_id": approver_id, "reference": "doc-1"},
    )
    login(client, "admin@tenant-a.example")
    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]
    decide = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": digest},
        headers={"Idempotency-Key": key},
    )
    assert decide.status_code == 201, decide.text
    return decide.json(), s1_occurrence_id


def test_checkpoint_and_verify_clean_when_untampered(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    _record_one_approval(client, tenant_id, created, approver_id)
    project_id = created["project"]["id"]

    checkpoint = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint")
    assert checkpoint.status_code == 201, checkpoint.text
    assert checkpoint.json()["event_count"] == 1

    verify = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    assert verify.status_code == 200, verify.text
    assert verify.json()["ok"] is True
    assert verify.json()["incident"] is None


def test_checkpoint_is_noop_when_nothing_new(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    _record_one_approval(client, tenant_id, created, approver_id)
    project_id = created["project"]["id"]

    first = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint")
    assert first.status_code == 201
    second = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint")
    assert second.status_code == 201
    assert second.json() is None


def test_tampered_audit_event_is_detected_and_blocks_new_decisions(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    decision, s1_occurrence_id = _record_one_approval(client, tenant_id, created, approver_id)
    project_id = created["project"]["id"]

    checkpoint = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint")
    assert checkpoint.status_code == 201

    # Simulate privileged tampering: mutate the audit event's content
    # directly at the DB layer, bypassing every app-level route.
    db = _get_db_session()
    event = db.query(AuditEvent).filter(AuditEvent.project_id == project_id).one()
    event.event_type = "decision_recorded_TAMPERED"
    db.commit()

    verify = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    assert verify.status_code == 200, verify.text
    assert verify.json()["ok"] is False
    assert verify.json()["incident"]["status"] == "open"

    # REQ-027: a second occurrence's decision must now be blocked.
    s2_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S3")
    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s2_occurrence_id}/preview", json={})
    blocked = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s2_occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": preview.json()["manifest_digest"]},
        headers={"Idempotency-Key": "blocked-key"},
    )
    assert blocked.status_code == 423, blocked.text


def test_deleted_audit_event_is_detected_by_count_mismatch(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    _record_one_approval(client, tenant_id, created, approver_id)
    project_id = created["project"]["id"]
    client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint")

    db = _get_db_session()
    event = db.query(AuditEvent).filter(AuditEvent.project_id == project_id).first()
    db.delete(event)
    db.commit()

    verify = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    assert verify.json()["ok"] is False


def test_resolving_incident_unblocks_new_decisions(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    decision, s1_occurrence_id = _record_one_approval(client, tenant_id, created, approver_id)
    project_id = created["project"]["id"]
    client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint")

    db = _get_db_session()
    event = db.query(AuditEvent).filter(AuditEvent.project_id == project_id).one()
    event.event_type = "TAMPERED"
    db.commit()

    verify = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    incident_id = verify.json()["incident"]["id"]

    s3_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S3")
    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s3_occurrence_id}/preview", json={})
    still_blocked = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s3_occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": preview.json()["manifest_digest"]},
        headers={"Idempotency-Key": "k-blocked"},
    )
    assert still_blocked.status_code == 423

    resolve = client.post(
        f"/orgs/{tenant_id}/integrity/incidents/{incident_id}/resolve",
        json={"resolution_note": "Investigated: confirmed test-induced tamper, no real breach"},
    )
    assert resolve.status_code == 200, resolve.text
    assert resolve.json()["status"] == "resolved"

    now_allowed = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s3_occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": preview.json()["manifest_digest"]},
        headers={"Idempotency-Key": "k-unblocked"},
    )
    assert now_allowed.status_code == 201, now_allowed.text


def test_resolve_requires_nonempty_note(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    _record_one_approval(client, tenant_id, created, approver_id)
    project_id = created["project"]["id"]
    client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint")

    db = _get_db_session()
    event = db.query(AuditEvent).filter(AuditEvent.project_id == project_id).one()
    event.event_type = "TAMPERED"
    db.commit()

    verify = client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    incident_id = verify.json()["incident"]["id"]

    resp = client.post(f"/orgs/{tenant_id}/integrity/incidents/{incident_id}/resolve", json={"resolution_note": "   "})
    assert resp.status_code == 422
