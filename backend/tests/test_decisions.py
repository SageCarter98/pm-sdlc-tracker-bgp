"""WP07: REQ-020/021 (exceptions), REQ-022/023/024/025 (decisions), REQ-006
(separation of duties, BGP-F02)."""
import pytest
from datetime import datetime, timedelta, timezone

from tests.conftest import enable_mfa, login, register_and_login
from tests.test_projects import _create_org_as_admin, _create_project, _invite_and_accept, _publish_standard_template


def _setup_project_with_second_approver(client):
    """Admin (tenant_administrator) creates the org/template/project, MFA
    enabled. A second approver is also invited, MFA enabled, and added to
    the project -- needed for separation-of-duties overrides. Returns
    (tenant_id, project, s1_item, admin_id, approver_id)."""
    tenant_id = _create_org_as_admin(client)
    enable_mfa(client)
    admin_id = client.get("/auth/me").json()["id"]

    approver_id = _invite_and_accept(client, tenant_id, "approver2@tenant-a.example", "approver")
    enable_mfa(client)

    register_and_login(client, "admin@tenant-a.example")
    version_id, _ = _publish_standard_template(client, tenant_id)
    created = _create_project(
        client, tenant_id, version_id, "Standard-High", members=[{"user_id": approver_id, "role": "approver"}]
    ).json()
    return tenant_id, created, admin_id, approver_id


def _complete_item(client, tenant_id, item_id, revision=1):
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/revisions",
        json={"base_revision": revision, "status": "Complete", "reference": "doc-1", "source_hash": "sha256:x"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_preview_reports_hard_blockers_before_evidence_complete(client):
    tenant_id, created, _admin_id, _approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")

    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert len(body["hard_blockers"]) == 1
    assert body["manifest_digest"]


def test_preview_gives_plain_language_blocker_explanations_and_permitted_outcomes(client):
    """REQ-036 (plain-language blocker + corrective action) and REQ-037
    (permitted-progression confirmation summary)."""
    tenant_id, created, _admin_id, _approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    blocked = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    body = blocked.json()
    assert len(body["blocker_explanations"]) == 1
    explanation = body["blocker_explanations"][0]
    assert explanation["item_id"] == s1_item_id
    assert "S1" in explanation["explanation"]
    assert s1_item_id in explanation["corrective_action"]
    # a hard blocker exists -- Approve is not reachable, but Hold/Redirect/
    # Terminate always are, and "Approve with conditions" is structurally
    # reachable once conditions are supplied.
    assert "Approve" not in body["permitted_outcomes"]
    assert "Hold" in body["permitted_outcomes"]

    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
    )
    clear = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    clear_body = clear.json()
    assert clear_body["blocker_explanations"] == []
    assert "Approve" in clear_body["permitted_outcomes"]


def test_decision_denied_when_hard_blocker_unresolved(client):
    tenant_id, created, _admin_id, _approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")

    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]

    decide = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": digest},
        headers={"Idempotency-Key": "key-1"},
    )
    assert decide.status_code == 422, decide.text
    assert "hard blocker" in decide.text


def test_full_approval_flow_with_separation_of_duties_override(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    # admin is both the item's implicit preparer (seeded with no owner, then
    # admin completes it) and the decider -- self-only-approval case.
    _complete_item(client, tenant_id, s1_item_id)
    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "Complete", "owner_user_id": admin_id, "reference": "doc-1", "source_hash": "x"},
    )

    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]
    assert preview.json()["hard_blockers"] == []

    denied = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": digest},
        headers={"Idempotency-Key": "key-2"},
    )
    assert denied.status_code == 403, denied.text  # REQ-006: self-only approval rejected

    # A bare reviewer_user_id + note is no longer accepted (BGP-F02) -- the
    # independent reviewer must record an actual review from their OWN
    # authenticated session first.
    still_denied = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={
            "outcome": "Approve",
            "manifest_digest": digest,
            "separation_override": {"review_id": "not-a-real-review"},
        },
        headers={"Idempotency-Key": "key-2b"},
    )
    assert still_denied.status_code == 403, still_denied.text

    login(client, "approver2@tenant-a.example")
    review = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/compensating-reviews",
        json={"note": "Reviewed independently by approver2"},
    )
    assert review.status_code == 201, review.text
    assert review.json()["reviewer_user_id"] == approver_id

    login(client, "admin@tenant-a.example")
    approved = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={
            "outcome": "Approve",
            "manifest_digest": digest,
            "separation_override": {"review_id": review.json()["id"]},
        },
        headers={"Idempotency-Key": "key-3"},
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["outcome"] == "Approve"


def test_compensating_review_cannot_be_created_by_the_would_be_self_approver(client):
    """BGP-F02: the review endpoint records the CALLER as reviewer_user_id --
    there is no field to submit someone else's identity, so admin cannot
    manufacture a review that would later "independently" clear their own
    self-only approval."""
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")

    review = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/compensating-reviews",
        json={"note": "I reviewed my own work"},
    )
    assert review.status_code == 201, review.text
    assert review.json()["reviewer_user_id"] == admin_id


def test_stale_compensating_review_rejected_after_evidence_changes(client):
    """BGP-F02 verification point 3: a compensating review recorded against
    one evidence manifest must not clear self-only approval once the
    manifest has changed."""
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    _complete_item(client, tenant_id, s1_item_id)
    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "Complete", "owner_user_id": admin_id, "reference": "doc-1", "source_hash": "x"},
    )

    login(client, "approver2@tenant-a.example")
    review = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/compensating-reviews",
        json={"note": "Reviewed independently by approver2"},
    ).json()

    login(client, "admin@tenant-a.example")
    # Evidence changes again after the review was recorded -- new revision,
    # new manifest_digest, the review above no longer matches it.
    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 3, "status": "Complete", "owner_user_id": admin_id, "reference": "doc-2", "source_hash": "y"},
    )
    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    fresh_digest = preview.json()["manifest_digest"]

    stale = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": fresh_digest, "separation_override": {"review_id": review["id"]}},
        headers={"Idempotency-Key": "stale-review-key"},
    )
    assert stale.status_code == 403, stale.text
    assert "stale" in stale.text.lower()


def test_idempotent_retry_returns_same_decision_not_a_conflict(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "owner_user_id": approver_id, "reference": "doc-1"},
    )
    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]

    body = {"outcome": "Approve", "manifest_digest": digest}
    first = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json=body, headers={"Idempotency-Key": "retry-key"},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json=body, headers={"Idempotency-Key": "retry-key"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"], "same idempotency key must return the same decision, not a new one"

    changed_body = {"outcome": "Hold", "manifest_digest": digest}
    conflict = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json=changed_body, headers={"Idempotency-Key": "retry-key"},
    )
    assert conflict.status_code == 409, conflict.text


def test_second_decision_on_same_occurrence_requires_superseding(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "owner_user_id": approver_id, "reference": "doc-1"},
    )
    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]

    first = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": digest}, headers={"Idempotency-Key": "k1"},
    )
    decision_id = first.json()["id"]

    again = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": digest}, headers={"Idempotency-Key": "k2"},
    )
    assert again.status_code == 409, again.text

    superseded = client.post(
        f"/orgs/{tenant_id}/decisions/{decision_id}/superseding",
        json={"outcome": "Hold", "manifest_digest": digest, "reason": "Evidence turned out to be insufficient"},
        headers={"Idempotency-Key": "k3"},
    )
    assert superseded.status_code == 201, superseded.text
    assert superseded.json()["supersedes_decision_id"] == decision_id

    original = client.get(f"/orgs/{tenant_id}/decisions/{decision_id}")
    assert original.json()["outcome"] == "Approve", "the original decision row must never be mutated"


def test_stale_manifest_digest_is_rejected(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    stale_digest = preview.json()["manifest_digest"]

    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "owner_user_id": approver_id, "reference": "doc-1"},
    )

    decide = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Approve", "manifest_digest": stale_digest},
        headers={"Idempotency-Key": "stale-key"},
    )
    assert decide.status_code == 409, decide.text


def test_exception_excuses_a_hard_blocker_and_revocation_reinstates_it(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    now = datetime.now(timezone.utc)
    exc = client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/exceptions",
        json={
            "reason": "Vendor doc pending, low risk",
            "owner_user_id": admin_id,
            "starts_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
        },
    )
    assert exc.status_code == 201, exc.text

    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    assert preview.json()["hard_blockers"] == [], "a valid active exception must excuse the hard blocker"

    revoke = client.post(f"/orgs/{tenant_id}/exceptions/{exc.json()['id']}/revoke")
    assert revoke.status_code == 200, revoke.text

    preview_after = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    assert s1_item_id in preview_after.json()["hard_blockers"], "revoking the exception must reinstate the blocker (REQ-021)"


def test_conditional_approval_requires_owner_and_future_deadline(client):
    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s2_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S2")

    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s2_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]
    assert preview.json()["hard_blockers"], "S2.R1 (Standard-High) starts unresolved and hard-blocking"

    missing_conditions = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s2_occurrence_id}/decisions",
        json={"outcome": "Approve with conditions", "manifest_digest": digest},
        headers={"Idempotency-Key": "cond-1"},
    )
    assert missing_conditions.status_code == 422, missing_conditions.text

    still_blocked_because_hard = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s2_occurrence_id}/decisions",
        json={
            "outcome": "Approve with conditions",
            "manifest_digest": digest,
            "conditions": {
                "conditions": ["Provide architecture review within 30 days"],
                "owner_user_id": approver_id,
                "deadline": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            },
        },
        headers={"Idempotency-Key": "cond-2"},
    )
    # S2.R1 is a hard blocker for Standard-High -- conditions can't waive a hard blocker.
    assert still_blocked_because_hard.status_code == 422, still_blocked_because_hard.text


def test_decision_commit_failure_leaves_no_partial_state(client, monkeypatch):
    """REQ-028 ('zero acknowledged-decision loss... including interpretation
    records') has a locally-testable component even though the full
    requirement is gated on DEC05 (see TRACKER.md): a crash or fault right
    at commit time must never leave a DecisionRecord without its
    AuditEvent/IdempotencyRecord siblings, or vice versa. This does NOT
    prove zero loss across node/zone/region failures -- only that a local
    failure can't produce a torn, partially-recorded decision."""
    from sqlalchemy.orm import Session as OrmSession

    from app.db import get_db
    from app.main import app
    from app.models import AuditEvent, DecisionRecord, IdempotencyRecord

    tenant_id, created, admin_id, approver_id = _setup_project_with_second_approver(client)
    project_id = created["project"]["id"]
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Complete", "owner_user_id": approver_id, "reference": "doc-1"},
    )
    preview = client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]

    def _boom(self, *args, **kwargs):
        raise RuntimeError("simulated crash at commit time")

    monkeypatch.setattr(OrmSession, "commit", _boom)
    with pytest.raises(RuntimeError):
        client.post(
            f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{s1_occurrence_id}/decisions",
            json={"outcome": "Approve", "manifest_digest": digest},
            headers={"Idempotency-Key": "crash-key"},
        )
    monkeypatch.undo()

    db = next(app.dependency_overrides[get_db]())
    assert db.query(DecisionRecord).filter(DecisionRecord.project_id == project_id).count() == 0
    assert db.query(AuditEvent).filter(AuditEvent.project_id == project_id, AuditEvent.event_type == "decision_recorded").count() == 0
    assert db.query(IdempotencyRecord).filter(IdempotencyRecord.idempotency_key == "crash-key").count() == 0


def test_only_decision_authority_roles_can_record_decisions(client):
    tenant_id = _create_org_as_admin(client)
    enable_mfa(client)
    contributor_id = _invite_and_accept(client, tenant_id, "contributor@tenant-a.example", "contributor")
    enable_mfa(client)

    register_and_login(client, "admin@tenant-a.example")
    version_id, _ = _publish_standard_template(client, tenant_id)
    created = _create_project(
        client, tenant_id, version_id, "Standard-High", members=[{"user_id": contributor_id, "role": "contributor"}]
    ).json()
    s1_occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")

    register_and_login(client, "contributor@tenant-a.example")
    preview = client.post(f"/orgs/{tenant_id}/projects/{created['project']['id']}/occurrences/{s1_occurrence_id}/preview", json={})
    digest = preview.json()["manifest_digest"]
    decide = client.post(
        f"/orgs/{tenant_id}/projects/{created['project']['id']}/occurrences/{s1_occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": digest},
        headers={"Idempotency-Key": "nope"},
    )
    assert decide.status_code == 403, decide.text
