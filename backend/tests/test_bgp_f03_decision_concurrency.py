"""BGP-F03 (BGP_Development_Review_Findings_v1.0.pdf): decision checks read
authority and evidence readiness, then commit later, with nothing
serialising a concurrent write in between. This proves the fix holds
against REAL concurrent Postgres sessions -- the SQLite TestClient suite
runs single-threaded against one connection and cannot demonstrate a
genuine two-session race at all (same reason test_wp0X_tenant_isolation_
rls.py exists as a separate live-Postgres suite rather than folding into
the SQLite tests).

Two techniques, both avoiding real threads (which would need careful
teardown and are flaky under CI scheduling jitter):

1. Lock-blocking proof: session A takes `FOR UPDATE` and holds the
   transaction open; session B sets a short `lock_timeout` and attempts a
   conflicting write, which must fail with a lock-timeout error while A
   still holds it, then succeed once A releases. This is a deterministic,
   synchronous way to prove a lock actually blocks a second writer without
   needing two real concurrent threads.
2. Constraint proof: the two new partial unique indexes (migration
   0011_bgp_f03_concurrency) are exercised directly with raw SQL, proving
   the database itself -- not just applicaton code that happens to run
   first -- refuses a second root decision or a second supersession for
   the same target.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import settings

try:
    _owner_engine = create_engine(settings.migration_database_url, future=True)
    with _owner_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    _app_engine = create_engine(settings.database_url, future=True)
    with _app_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    POSTGRES_AVAILABLE = True
except OperationalError:
    POSTGRES_AVAILABLE = False

pytestmark = pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app not configured")


@pytest.fixture()
def seeded_project():
    tenant_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    membership_id = str(uuid.uuid4())
    template_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    project_id, occurrence_id, item_id, pm_id = (
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
    )
    root_decision_id = str(uuid.uuid4())

    minimal_schema = '{"schema_version": 1, "tracks": ["Delivery"], "classes": ["A"], "roles": ["contributor"], "statuses": ["Not started"], "decision_outcomes": ["Approve"], "gates": []}'

    with _owner_engine.begin() as conn:
        conn.execute(text("INSERT INTO tenants (id, name, created_at) VALUES (:id, 'T', now())"), {"id": tenant_id})
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled, token_version) VALUES (:id, :email, 'x', false, now(), false, 0)"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        conn.execute(
            text(
                "INSERT INTO memberships (id, tenant_id, user_id, role, active, created_at) VALUES (:id, :tid, :uid, 'approver', true, now())"
            ),
            {"id": membership_id, "tid": tenant_id, "uid": user_id},
        )
        conn.execute(
            text("INSERT INTO templates (id, tenant_id, name, created_at) VALUES (:id, :tid, 'T', now())"),
            {"id": template_id, "tid": tenant_id},
        )
        conn.execute(
            text(
                "INSERT INTO template_versions (id, template_id, version_number, schema_json, status, created_by_user_id, created_at, published_at) "
                "VALUES (:id, :tpl, 1, CAST(:schema AS JSON), 'published', :uid, now(), now())"
            ),
            {"id": version_id, "tpl": template_id, "schema": minimal_schema, "uid": user_id},
        )
        conn.execute(
            text(
                "INSERT INTO projects (id, tenant_id, name, template_version_id, class_id, owner_user_id, created_at) VALUES (:id, :tid, 'P', :ver, 'A', :uid, now())"
            ),
            {"id": project_id, "tid": tenant_id, "ver": version_id, "uid": user_id},
        )
        conn.execute(
            text(
                "INSERT INTO project_memberships (id, tenant_id, project_id, user_id, role, created_at) VALUES (:id, :tid, :pid, :uid, 'approver', now())"
            ),
            {"id": pm_id, "tid": tenant_id, "pid": project_id, "uid": user_id},
        )
        conn.execute(
            text(
                "INSERT INTO gate_occurrences (id, tenant_id, project_id, gate_id, sequence, trigger, created_at) VALUES (:id, :tid, :pid, 'G1', 1, 'routine', now())"
            ),
            {"id": occurrence_id, "tid": tenant_id, "pid": project_id},
        )
        conn.execute(
            text(
                "INSERT INTO evidence_items (id, tenant_id, project_id, occurrence_id, gate_id, rule_id, evidence_kind, required, blocker_level, permitted_role_ids, status, latest_revision_number, created_at) "
                "VALUES (:id, :tid, :pid, :oid, 'G1', 'R1', 'document', true, 'hard', CAST('[]' AS JSON), 'Not started', 0, now())"
            ),
            {"id": item_id, "tid": tenant_id, "pid": project_id, "oid": occurrence_id},
        )
        conn.execute(
            text(
                "INSERT INTO decision_records (id, tenant_id, project_id, occurrence_id, actor_user_id, actor_role, outcome, manifest_json, reviewed_manifest_digest, created_at) "
                "VALUES (:id, :tid, :pid, :oid, :uid, 'approver', 'Approve', CAST('{}' AS JSON), 'deadbeef', now())"
            ),
            {"id": root_decision_id, "tid": tenant_id, "pid": project_id, "oid": occurrence_id, "uid": user_id},
        )

    yield {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "project_id": project_id,
        "occurrence_id": occurrence_id,
        "item_id": item_id,
        "pm_id": pm_id,
        "membership_id": membership_id,
        "root_decision_id": root_decision_id,
    }

    with _owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        conn.execute(text("DELETE FROM decision_records WHERE occurrence_id = :oid"), {"oid": occurrence_id})
        conn.execute(text("DELETE FROM evidence_items WHERE id = :id"), {"id": item_id})
        conn.execute(text("DELETE FROM gate_occurrences WHERE id = :id"), {"id": occurrence_id})
        conn.execute(text("DELETE FROM project_memberships WHERE id = :id"), {"id": pm_id})
        conn.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project_id})
        conn.execute(text("DELETE FROM template_versions WHERE id = :id"), {"id": version_id})
        conn.execute(text("DELETE FROM templates WHERE id = :id"), {"id": template_id})
        conn.execute(text("DELETE FROM memberships WHERE id = :id"), {"id": membership_id})
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def test_evidence_item_lock_blocks_a_concurrent_writer(seeded_project):
    """Simulates decisions.py's _compute_readiness(lock=True) (session A)
    racing app/routers/projects.py's create_evidence_revision (session B) --
    B must block, not silently read/write stale evidence."""
    t = seeded_project
    conn_a = _app_engine.connect()
    txn_a = conn_a.begin()
    conn_a.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
    conn_a.execute(text("SELECT * FROM evidence_items WHERE id = :id FOR UPDATE"), {"id": t["item_id"]})

    try:
        with pytest.raises(OperationalError, match="lock"):
            with _app_engine.begin() as conn_b:
                conn_b.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
                conn_b.execute(text("SET LOCAL lock_timeout = '300ms'"))
                conn_b.execute(
                    text("UPDATE evidence_items SET status = 'Complete' WHERE id = :id"), {"id": t["item_id"]}
                )
    finally:
        txn_a.rollback()
        conn_a.close()

    # Now that A released the lock, the same write succeeds immediately.
    with _app_engine.begin() as conn_c:
        conn_c.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        conn_c.execute(text("UPDATE evidence_items SET status = 'Complete' WHERE id = :id"), {"id": t["item_id"]})


def test_project_membership_lock_blocks_a_concurrent_writer(seeded_project):
    """Simulates decisions.py's _require_decision_authority (session A,
    FOR UPDATE on the caller's ProjectMembership row) racing a hypothetical
    concurrent role change/revocation (session B) -- B must block."""
    t = seeded_project
    conn_a = _app_engine.connect()
    txn_a = conn_a.begin()
    conn_a.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
    conn_a.execute(text("SELECT * FROM project_memberships WHERE id = :id FOR UPDATE"), {"id": t["pm_id"]})

    try:
        with pytest.raises(OperationalError, match="lock"):
            with _app_engine.begin() as conn_b:
                conn_b.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
                conn_b.execute(text("SET LOCAL lock_timeout = '300ms'"))
                conn_b.execute(
                    text("UPDATE project_memberships SET role = 'contributor' WHERE id = :id"), {"id": t["pm_id"]}
                )
    finally:
        txn_a.rollback()
        conn_a.close()

    with _app_engine.begin() as conn_c:
        conn_c.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        conn_c.execute(text("UPDATE project_memberships SET role = 'contributor' WHERE id = :id"), {"id": t["pm_id"]})


def test_tenant_membership_lock_blocks_a_concurrent_writer(seeded_project):
    """REQ-024/BGP-IPA-001 IPA04: _require_decision_authority now also locks
    the caller's tenant-level Membership row FOR UPDATE (not just their
    ProjectMembership) -- app/deps.py's get_active_membership only ever
    checked this once, unlocked, before the handler ran, so a concurrent
    removal from the organisation entirely could previously ride through to
    a committed decision undetected. Same lock-blocking proof as the
    ProjectMembership test above, targeting `memberships` instead."""
    t = seeded_project
    conn_a = _app_engine.connect()
    txn_a = conn_a.begin()
    conn_a.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
    conn_a.execute(text("SELECT * FROM memberships WHERE id = :id FOR UPDATE"), {"id": t["membership_id"]})

    try:
        with pytest.raises(OperationalError, match="lock"):
            with _app_engine.begin() as conn_b:
                conn_b.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
                conn_b.execute(text("SET LOCAL lock_timeout = '300ms'"))
                conn_b.execute(
                    text("UPDATE memberships SET active = false WHERE id = :id"), {"id": t["membership_id"]}
                )
    finally:
        txn_a.rollback()
        conn_a.close()

    with _app_engine.begin() as conn_c:
        conn_c.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        conn_c.execute(text("UPDATE memberships SET active = false WHERE id = :id"), {"id": t["membership_id"]})


def test_second_root_decision_for_same_occurrence_rejected_at_db_level(seeded_project):
    """migration 0011_bgp_f03_concurrency's uq_decision_records_one_root_per_occurrence
    -- the fixture already seeded one root (supersedes_decision_id IS NULL)
    decision; a second one for the same occurrence must be refused by the
    database itself, not merely by application code that happened to check
    first."""
    t = seeded_project
    with pytest.raises(IntegrityError, match="duplicate key value violates unique constraint"):
        with _app_engine.begin() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(
                text(
                    "INSERT INTO decision_records (id, tenant_id, project_id, occurrence_id, actor_user_id, actor_role, outcome, manifest_json, reviewed_manifest_digest, created_at) "
                    "VALUES (:id, :tid, :pid, :oid, :uid, 'approver', 'Approve', CAST('{}' AS JSON), 'deadbeef', now())"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": t["tenant_id"],
                    "pid": t["project_id"],
                    "oid": t["occurrence_id"],
                    "uid": t["user_id"],
                },
            )


def test_second_supersession_of_same_decision_rejected_at_db_level(seeded_project):
    """migration 0011_bgp_f03_concurrency's uq_decision_records_supersedes_once
    -- two concurrent 'correct this decision' requests for the SAME original
    decision must not both succeed and create conflicting successor
    histories; the second insert is refused by the database."""
    t = seeded_project
    with _app_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        conn.execute(
            text(
                "INSERT INTO decision_records (id, tenant_id, project_id, occurrence_id, actor_user_id, actor_role, outcome, manifest_json, reviewed_manifest_digest, supersedes_decision_id, reason, created_at) "
                "VALUES (:id, :tid, :pid, :oid, :uid, 'approver', 'Hold', CAST('{}' AS JSON), 'deadbeef', :sup, 'first correction', now())"
            ),
            {
                "id": str(uuid.uuid4()),
                "tid": t["tenant_id"],
                "pid": t["project_id"],
                "oid": t["occurrence_id"],
                "uid": t["user_id"],
                "sup": t["root_decision_id"],
            },
        )

    with pytest.raises(IntegrityError, match="duplicate key value violates unique constraint"):
        with _app_engine.begin() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(
                text(
                    "INSERT INTO decision_records (id, tenant_id, project_id, occurrence_id, actor_user_id, actor_role, outcome, manifest_json, reviewed_manifest_digest, supersedes_decision_id, reason, created_at) "
                    "VALUES (:id, :tid, :pid, :oid, :uid, 'approver', 'Hold', CAST('{}' AS JSON), 'deadbeef', :sup, 'second correction', now())"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": t["tenant_id"],
                    "pid": t["project_id"],
                    "oid": t["occurrence_id"],
                    "uid": t["user_id"],
                    "sup": t["root_decision_id"],
                },
            )
