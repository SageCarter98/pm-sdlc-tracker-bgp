"""DEC07: readiness resolves a status through the bound template's
declared semantics instead of matching the literal "Complete"."""

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import enable_mfa, register_and_login

V3 = {
    "vocabulary_version": 3,
    "tracks": ["Increment"],
    "classes": ["Team"],
    "roles": ["developer", "approver"],
    "statuses": [
        {"id": "Not met", "initial": True},
        {"id": "Met", "satisfies": True},
        {"id": "Waived", "satisfies": True, "requires_exception": True},
    ],
    "decision_outcomes": [
        {"id": "Increment accepted", "kind": "approving"},
        {"id": "Not accepted", "kind": "recording"},
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
                    "rule_id": "dod.checks",
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                    "evidence_kind": "link",
                    "permitted_role_ids": ["developer"],
                    "blocker_level": "hard",
                }
            ],
        }
    ],
}


@pytest.fixture()
def v3_project(client):
    register_and_login(client, "admin@v3.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    pub = client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    assert pub.status_code == 200, pub.text
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    )
    assert project.status_code == 201, project.text
    return tenant_id, project.json()


def _preview(client, tenant_id, created, outcome=None):
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{created['project']['id']}/occurrences/{created['occurrences'][0]['id']}/preview",
        json={"outcome": outcome} if outcome else {},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_a_declared_satisfying_status_clears_a_hard_blocker(client, v3_project):
    """G1: the whole point. "Met" is this framework's completion word and
    the engine must honour it."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    assert _preview(client, tenant_id, created)["hard_blockers"] == [item["id"]]

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met", "reference": "https://ci/1"},
    )
    assert resp.status_code == 201, resp.text
    assert _preview(client, tenant_id, created)["hard_blockers"] == []


def test_the_literal_complete_is_not_special_for_a_v3_template(client, v3_project):
    """Owner ruling: Complete is a state concept, not a literal. A v3
    template that never declares it must reject it (Task 4 enforces the
    rejection; here we only require that it does not SATISFY)."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "x"},
    )
    if resp.status_code == 201:
        assert _preview(client, tenant_id, created)["hard_blockers"] == [item["id"]]
    else:
        assert resp.status_code == 422


def test_requires_exception_status_does_not_satisfy_without_a_valid_exception(client, v3_project):
    """Without this, declaring an extra satisfying status is a route around
    a hard blocker -- the exact failure mode this work closes."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Waived", "reference": "waiver-note"},
    )
    assert resp.status_code == 201, resp.text
    assert _preview(client, tenant_id, created)["hard_blockers"] == [item["id"]], (
        "a requires_exception status must not satisfy readiness on its own"
    )


def test_requires_exception_status_satisfies_with_a_valid_exception(client, v3_project):
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    admin_id = client.get("/auth/me").json()["id"]
    now = datetime.now(timezone.utc)

    client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Waived", "reference": "waiver-note"},
    )
    exc = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/exceptions",
        json={
            "reason": "accepted for this increment",
            "owner_user_id": admin_id,
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert exc.status_code == 201, exc.text
    assert _preview(client, tenant_id, created)["hard_blockers"] == []


def test_an_expired_exception_does_not_satisfy_on_the_locked_commit_path(client, v3_project):
    """REVIEW FOCUS 5. An exception valid at preview time but expired by
    commit time must not approve. The locked readiness path re-checks
    validity rather than trusting the earlier read."""
    from app.db import get_db
    from app.main import app
    from app.models import ExceptionRecord

    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    admin_id = client.get("/auth/me").json()["id"]
    now = datetime.now(timezone.utc)

    client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Waived", "reference": "waiver-note"},
    )
    client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/exceptions",
        json={
            "reason": "accepted for this increment",
            "owner_user_id": admin_id,
            "starts_at": (now - timedelta(hours=2)).isoformat(),
            "expires_at": (now + timedelta(days=1)).isoformat(),
        },
    )
    body = _preview(client, tenant_id, created)
    assert body["hard_blockers"] == [], "precondition: the valid exception should satisfy at preview"
    digest = body["manifest_digest"]

    # Expire it behind the caller's back, exactly as elapsed time would.
    # Same direct-DB-manipulation pattern as test_decisions.py's expired-
    # exception test: go through the SAME overridden session the TestClient
    # uses (app.db.SessionLocal binds to the real dev Postgres, not this
    # test's in-memory SQLite).
    db = next(app.dependency_overrides[get_db]())
    record = db.query(ExceptionRecord).filter(ExceptionRecord.evidence_item_id == item["id"]).one()
    record.expires_at = now - timedelta(minutes=1)
    db.commit()

    refused = client.post(
        f"/orgs/{tenant_id}/projects/{created['project']['id']}"
        f"/occurrences/{created['occurrences'][0]['id']}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": digest},
        headers={"Idempotency-Key": "expired-exception-1"},
    )
    assert refused.status_code in (409, 422), (
        "an expired exception must not approve -- either the manifest is stale (409) or the "
        f"blocker is unresolved (422), got {refused.status_code}: {refused.text[:200]}"
    )


def test_an_undeclared_stored_status_fails_closed(client, v3_project):
    """REVIEW FOCUS 3. Reachable for legacy rows. Readiness must treat an
    unknown status as not satisfying and must not raise."""
    from app.db import get_db
    from app.main import app
    from app.models import EvidenceItem

    tenant_id, created = v3_project
    item_id = created["evidence_items"][0]["id"]

    # Same overridden-session pattern as above -- app.db.SessionLocal binds
    # to the real dev Postgres, not this test's in-memory SQLite.
    db = next(app.dependency_overrides[get_db]())
    row = db.query(EvidenceItem).filter(EvidenceItem.id == item_id).one()
    row.status = "Legacy word"
    db.commit()

    body = _preview(client, tenant_id, created)
    assert body["hard_blockers"] == [item_id]
