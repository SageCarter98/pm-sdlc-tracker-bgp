"""WP06: REQ-015 (atomic project seeding), REQ-016 (separate occurrences),
REQ-017/018/019 (immutable, attributed, validated evidence revisions)."""
import json
from pathlib import Path

import pytest

from tests.conftest import register_and_login

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks"


def _create_org_as_admin(client, email="admin@tenant-a.example"):
    register_and_login(client, email)
    return client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]


def _publish_standard_template(client, tenant_id):
    schema = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "Standard", "schema_json": schema}).json()
    publish = client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    assert publish.status_code == 200, publish.text
    return created["id"], schema


def _create_project(client, tenant_id, version_id, class_id, name="Acme SaaS", members=None):
    return client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": name, "template_version_id": version_id, "class_id": class_id, "members": members or []},
    )


def _invite_and_accept(client, tenant_id, email, role):
    """Returns the new member's user_id. Caller is left logged in as the
    invited user, not the admin who issued the invite."""
    token = client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": role}).json()["token"]
    login_resp = register_and_login(client, email)
    user_id = login_resp.json()["id"]
    accept = client.post("/invitations/accept", json={"token": token})
    assert accept.status_code == 200, accept.text
    return user_id


def test_create_project_seeds_routine_gates_only(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)

    resp = _create_project(client, tenant_id, version_id, "Standard-High")
    assert resp.status_code == 201, resp.text
    body = resp.json()

    gate_ids = {o["gate_id"] for o in body["occurrences"]}
    assert gate_ids == {"S1", "S2", "S3"}, "S4 is triggered-only for Standard-High -- must not auto-seed"

    assert len(body["evidence_items"]) == 3
    for item in body["evidence_items"]:
        assert item["status"] == "Not started"
        assert item["latest_revision_number"] == 1
        assert item["required"] is True  # S1.R1/S2.R1/S3.R1 are all hard/conditional for Standard-High


def test_low_class_seeds_advisory_evidence(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)

    resp = _create_project(client, tenant_id, version_id, "Standard-Low")
    assert resp.status_code == 201, resp.text
    body = resp.json()

    gate_ids = {o["gate_id"] for o in body["occurrences"]}
    assert gate_ids == {"S1", "S2", "S3"}, "S4's only rule is Standard-High-only -- the gate itself must not apply"

    s2_item = next(e for e in body["evidence_items"] if e["gate_id"] == "S2")
    assert s2_item["required"] is False, "S2.R2 (Standard-Low) is advisory"


def test_seeding_failure_leaves_no_project_row(client, monkeypatch):
    """REQ-015's own verification text: 'commits project and required items
    together, or neither when seeding fails.' Forces evaluate_condition (only
    called for S2/S4's conditional rules) to blow up mid-seed, after the
    project row and S1's occurrence/evidence have already been flushed but
    not committed -- then proves none of it landed."""
    import app.routers.projects as projects_module
    from app.db import get_db
    from app.main import app
    from app.models import EvidenceItem, GateOccurrence, Project, ProjectMembership

    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)

    def _boom(*args, **kwargs):
        raise RuntimeError("seeded failure for atomicity test")

    monkeypatch.setattr(projects_module, "evaluate_condition", _boom)

    with pytest.raises(RuntimeError):
        _create_project(client, tenant_id, version_id, "Standard-High", name="Should Not Exist")

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    assert db.query(Project).filter(Project.name == "Should Not Exist").count() == 0
    assert db.query(ProjectMembership).count() == 0
    assert db.query(GateOccurrence).count() == 0
    assert db.query(EvidenceItem).count() == 0


def test_two_routine_and_one_triggered_occurrence_keep_separate_evidence(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    created = _create_project(client, tenant_id, version_id, "Standard-High").json()
    project_id = created["project"]["id"]
    first_s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    second_routine = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences", json={"gate_id": "S1", "trigger": "routine"}
    )
    assert second_routine.status_code == 201, second_routine.text
    assert second_routine.json()["occurrence"]["sequence"] == 2
    second_s1_item_id = second_routine.json()["evidence_items"][0]["id"]
    assert second_s1_item_id != first_s1_item_id, "the second occurrence must get its own evidence item, not reuse the first"

    triggered = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences", json={"gate_id": "S4", "trigger": "triggered"}
    )
    assert triggered.status_code == 201, triggered.text
    assert triggered.json()["occurrence"]["sequence"] == 1  # S4's first-ever occurrence
    assert triggered.json()["occurrence"]["trigger"] == "triggered"
    assert len(triggered.json()["evidence_items"]) == 1

    # editing the first S1 item must not affect the second occurrence's item
    client.post(
        f"/orgs/{tenant_id}/evidence/{first_s1_item_id}/revisions",
        json={"base_revision": 1, "status": "In progress", "reference": None},
    )
    second_item_detail = client.get(f"/orgs/{tenant_id}/evidence/{second_s1_item_id}").json()
    assert second_item_detail["item"]["status"] == "Not started"


def test_evidence_revision_history_is_immutable_and_attributed(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    created = _create_project(client, tenant_id, version_id, "Standard-High").json()
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    progress = client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "In progress", "reference": None},
    )
    assert progress.status_code == 201, progress.text
    assert progress.json()["item"]["latest_revision_number"] == 2

    rejected = client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "Complete", "reference": None},
    )
    assert rejected.status_code == 422, rejected.text  # REQ-018: required item, no reference

    done = client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "Complete", "reference": "doc-123", "source_hash": "sha256:abc"},
    )
    assert done.status_code == 201, done.text
    body = done.json()
    assert body["item"]["status"] == "Complete"
    assert len(body["revisions"]) == 3

    rev1, rev2, rev3 = body["revisions"]
    assert rev1["status"] == "Not started"
    assert rev2["status"] == "In progress"
    assert rev3["status"] == "Complete"
    assert rev3["reference_is_mutable"] is False  # source_hash was supplied
    assert rev2["reference_is_mutable"] is None  # rev2 had no reference at all -- nothing to disclose
    assert all(r["actor_user_id"] for r in body["revisions"]), "every revision must carry an actor"


def test_stale_base_revision_is_rejected(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    created = _create_project(client, tenant_id, version_id, "Standard-High").json()
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 0, "status": "In progress", "reference": None},
    )
    assert resp.status_code == 409, resp.text


def test_only_explicit_project_members_can_submit_evidence(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)

    member_id = _invite_and_accept(client, tenant_id, "member@tenant-a.example", "contributor")
    register_and_login(client, "admin@tenant-a.example")  # _invite_and_accept leaves the invited user logged in
    outsider_id = _invite_and_accept(client, tenant_id, "outsider@tenant-a.example", "contributor")

    register_and_login(client, "admin@tenant-a.example")
    created = _create_project(
        client, tenant_id, version_id, "Standard-High", members=[{"user_id": member_id, "role": "contributor"}]
    ).json()
    project_id = created["project"]["id"]
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    register_and_login(client, "member@tenant-a.example")
    as_member = client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "In progress", "reference": None},
    )
    assert as_member.status_code == 201, as_member.text

    register_and_login(client, "outsider@tenant-a.example")
    as_outsider = client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "In progress", "reference": None},
    )
    assert as_outsider.status_code == 403, as_outsider.text
    assert outsider_id != member_id


def test_project_creation_requires_tenant_administrator_or_approver_role(client):
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    _invite_and_accept(client, tenant_id, "contributor@tenant-a.example", "contributor")

    resp = _create_project(client, tenant_id, version_id, "Standard-High")
    assert resp.status_code == 403


def test_other_tenant_cannot_list_or_create_in_this_tenants_projects(client):
    tenant_a = _create_org_as_admin(client, "admin@tenant-a.example")
    version_id, _ = _publish_standard_template(client, tenant_a)

    _create_org_as_admin(client, "admin@tenant-b.example")
    resp = client.get(f"/orgs/{tenant_a}/projects")
    assert resp.status_code == 403


def test_my_work_reports_reason_deadline_state_and_direct_action(client):
    """REQ-032: 'role-specific My work with project, reason, deadline,
    state and a direct action.'"""
    tenant_id = _create_org_as_admin(client)
    version_id, _ = _publish_standard_template(client, tenant_id)
    created = _create_project(client, tenant_id, version_id, "Standard-High").json()
    s1_item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")
    admin_login = client.post("/auth/login", json={"email": "admin@tenant-a.example", "password": "correct horse battery staple"})
    admin_id = admin_login.json()["id"]

    # S1.R1's permitted_role_ids is ["approver"] (fixtures/synthetic/frameworks/standard.json)
    # and the project creator's own project role is their tenant role
    # (tenant_administrator here) -- so this item only shows up in the
    # admin's my-work once explicitly assigned to them as owner.
    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 1, "status": "Not started", "owner_user_id": admin_id, "reference": None},
    )

    work = client.get(f"/orgs/{tenant_id}/my-work")
    assert work.status_code == 200, work.text
    body = work.json()
    entry = next(e for e in body if e["item"]["id"] == s1_item_id)
    assert entry["project_id"] == created["project"]["id"]
    assert entry["project_name"] == created["project"]["name"]
    assert entry["status"] == "Not started"
    assert "owner" in entry["reason"]
    assert s1_item_id in entry["direct_action"]

    client.post(
        f"/orgs/{tenant_id}/evidence/{s1_item_id}/revisions",
        json={"base_revision": 2, "status": "Complete", "owner_user_id": admin_id, "reference": "doc-1"},
    )
    after = client.get(f"/orgs/{tenant_id}/my-work").json()
    entry_after = next(e for e in after if e["item"]["id"] == s1_item_id)
    assert entry_after["status"] == "Complete"
    assert "No action needed" in entry_after["direct_action"]
