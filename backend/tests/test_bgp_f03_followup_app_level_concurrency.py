"""BGP-F03 follow-up (BGP_Follow_Up_Review_Findings_v1.0.pdf): the ORIGINAL
BGP-F03 test file (test_bgp_f03_decision_concurrency.py) proves the
underlying locks and unique constraints work via raw SQL on both sides --
it never drives a real HTTP request through the actual decision endpoint
into a genuine conflict. The follow-up review named this gap explicitly:
"they do not verify the application's complete transaction and HTTP error
paths." This file closes that gap for the two specific code changes made
in response:

1. `_record_decision`'s `db.flush()` moved INSIDE the `try/except
   IntegrityError` block (it used to run before it, so a losing concurrent
   decision could raise an uncaught IntegrityError -> unhandled 500).
2. Tenant context (`SET LOCAL app.tenant_id`) restored immediately after
   `db.rollback()` in that handler (rollback ends the transaction the
   context was set on; the conflict-resolution queries that follow run
   under RLS and would silently see zero rows without it).

Technique: one side is a raw connection (same style as the sibling file)
that takes a `FOR UPDATE` lock on the occurrence's evidence rows, then --
*while still holding that lock* -- inserts a competing root decision and
commits. The OTHER side is a real HTTP call through the actual FastAPI app
(TestClient bound to the real Postgres `get_db`, not the SQLite fixture),
which blocks on that same lock inside `_compute_readiness`, then unblocks
the instant the raw side commits. This makes the app's own decision-commit
code path hit the exact conflict the fix addresses, deterministically (no
hoped-for race): the lock blocks B until A has already committed, so B is
guaranteed to lose. A `threading.Event` marks when A has the lock; a short
sleep after that gives B's real HTTP request time to reach its own FOR
UPDATE and genuinely block before A commits and releases it."""
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.deps import SESSION_COOKIE
from app.main import app
from app.security import create_session_token

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
def seeded_decidable_project():
    """Same seeding style as test_bgp_f03_decision_concurrency.py's
    seeded_project, plus a tenant-level Membership row (get_active_membership
    needs one) and mfa_enabled=true (require_mfa needs it) -- the additions
    needed to drive this through the REAL endpoint, not raw SQL. The evidence
    item is seeded already `status='Complete'` so a decision on it is
    actually approvable (no hard blocker) with zero EvidenceRevision rows --
    latest_revision_number stays 0, so BGP-F02's attribution-based
    separation-of-duties check finds no preparer and does not require a
    compensating review, keeping this fixture focused on the F03 path."""
    tenant_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    membership_id = str(uuid.uuid4())
    template_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    project_id, occurrence_id, item_id, pm_id = (
        str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    )

    # Unlike the sibling file's identical-looking fixture (which drives
    # everything via raw SQL and never touches the app's own schema
    # validation), this test goes through the real /preview endpoint, which
    # calls _load_bound_schema -- TemplateSchema requires at least one gate,
    # so an empty "gates": [] (fine for the raw-SQL sibling) fails here with
    # a 422 before the race is ever exercised.
    minimal_schema = (
        '{"schema_version": 1, "tracks": ["Delivery"], "classes": ["A"], "roles": ["contributor"], '
        '"statuses": ["Not started"], "decision_outcomes": ["Approve"], '
        '"gates": [{"gate_id": "G1", "name": "G1", "sequence": 1, "class_ids": ["A"], "rules": []}]}'
    )

    with _owner_engine.begin() as conn:
        conn.execute(text("INSERT INTO tenants (id, name, created_at) VALUES (:id, 'T', now())"), {"id": tenant_id})
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled, token_version) "
                "VALUES (:id, :email, 'x', false, now(), true, 0)"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        conn.execute(
            text("INSERT INTO memberships (id, tenant_id, user_id, role, active, created_at) VALUES (:id, :tid, :uid, 'approver', true, now())"),
            {"id": membership_id, "tid": tenant_id, "uid": user_id},
        )
        conn.execute(text("INSERT INTO templates (id, tenant_id, name, created_at) VALUES (:id, :tid, 'T', now())"), {"id": template_id, "tid": tenant_id})
        conn.execute(
            text(
                "INSERT INTO template_versions (id, template_id, version_number, schema_json, status, created_by_user_id, created_at, published_at) "
                "VALUES (:id, :tpl, 1, CAST(:schema AS JSON), 'published', :uid, now(), now())"
            ),
            {"id": version_id, "tpl": template_id, "schema": minimal_schema, "uid": user_id},
        )
        conn.execute(
            text("INSERT INTO projects (id, tenant_id, name, template_version_id, class_id, owner_user_id, created_at) VALUES (:id, :tid, 'P', :ver, 'A', :uid, now())"),
            {"id": project_id, "tid": tenant_id, "ver": version_id, "uid": user_id},
        )
        conn.execute(
            text("INSERT INTO project_memberships (id, tenant_id, project_id, user_id, role, created_at) VALUES (:id, :tid, :pid, :uid, 'approver', now())"),
            {"id": pm_id, "tid": tenant_id, "pid": project_id, "uid": user_id},
        )
        conn.execute(
            text("INSERT INTO gate_occurrences (id, tenant_id, project_id, gate_id, sequence, trigger, created_at) VALUES (:id, :tid, :pid, 'G1', 1, 'routine', now())"),
            {"id": occurrence_id, "tid": tenant_id, "pid": project_id},
        )
        conn.execute(
            text(
                "INSERT INTO evidence_items (id, tenant_id, project_id, occurrence_id, gate_id, rule_id, evidence_kind, required, blocker_level, permitted_role_ids, status, latest_revision_number, created_at) "
                "VALUES (:id, :tid, :pid, :oid, 'G1', 'R1', 'document', true, 'hard', CAST('[]' AS JSON), 'Complete', 0, now())"
            ),
            {"id": item_id, "tid": tenant_id, "pid": project_id, "oid": occurrence_id},
        )

    yield {
        "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id,
        "occurrence_id": occurrence_id, "item_id": item_id, "pm_id": pm_id,
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


def test_real_endpoint_returns_clean_409_not_500_when_it_loses_the_race(seeded_decidable_project):
    t = seeded_decidable_project
    assert app.dependency_overrides == {}, "a prior test left a dependency override active -- this test needs the REAL Postgres get_db"

    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, create_session_token(t["user_id"], token_version=0, mfa_verified=True))

    preview = client.post(f"/orgs/{t['tenant_id']}/projects/{t['project_id']}/occurrences/{t['occurrence_id']}/preview", json={})
    assert preview.status_code == 200, preview.text
    digest = preview.json()["manifest_digest"]
    assert preview.json()["hard_blockers"] == []

    winning_decision_id = str(uuid.uuid4())
    lock_acquired = threading.Event()
    http_response = {}

    def _raw_sql_winner():
        conn = _app_engine.connect()
        txn = conn.begin()
        try:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(text("SELECT * FROM evidence_items WHERE occurrence_id = :oid FOR UPDATE"), {"oid": t["occurrence_id"]})
            lock_acquired.set()
            # Generous margin for the OTHER thread's real HTTP request to
            # reach its own FOR UPDATE and genuinely block on this lock --
            # not required for correctness (the lock guarantees ordering
            # regardless of timing), only to make sure this test actually
            # exercises the blocked/losing path instead of finishing before
            # the HTTP request even starts.
            time.sleep(0.4)
            conn.execute(
                text(
                    "INSERT INTO decision_records (id, tenant_id, project_id, occurrence_id, actor_user_id, actor_role, outcome, manifest_json, reviewed_manifest_digest, created_at) "
                    "VALUES (:id, :tid, :pid, :oid, :uid, 'approver', 'Approve', CAST('{}' AS JSON), :digest, now())"
                ),
                {"id": winning_decision_id, "tid": t["tenant_id"], "pid": t["project_id"], "oid": t["occurrence_id"], "uid": t["user_id"], "digest": digest},
            )
            txn.commit()
        finally:
            conn.close()

    def _real_http_loser():
        lock_acquired.wait(timeout=5)
        http_response["resp"] = client.post(
            f"/orgs/{t['tenant_id']}/projects/{t['project_id']}/occurrences/{t['occurrence_id']}/decisions",
            json={"outcome": "Approve", "manifest_digest": digest},
            headers={"Idempotency-Key": "app-level-race-key"},
        )

    thread_a = threading.Thread(target=_raw_sql_winner)
    thread_b = threading.Thread(target=_real_http_loser)
    thread_b.start()
    thread_a.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    assert not thread_a.is_alive() and not thread_b.is_alive(), "one of the threads did not finish -- the lock likely never blocked as expected"
    resp = http_response.get("resp")
    assert resp is not None, "the real HTTP request never completed"
    # This is the actual assertion under test: WITHOUT the flush-inside-try
    # fix, the IntegrityError from this exact scenario would escape
    # uncaught (500). WITHOUT the tenant-context-restore fix, the
    # conflict handler's own `other_root` lookup would see zero rows under
    # RLS and fall through to the bare re-raise (also a 500). Only with
    # BOTH fixes does the real endpoint return the clean, deterministic 409
    # every other conflict path in this codebase already gives.
    assert resp.status_code == 409, resp.text
    assert winning_decision_id in resp.text, "the 409 must name the decision that actually won, not a generic failure"
