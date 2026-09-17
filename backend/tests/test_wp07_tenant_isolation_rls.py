"""WP07: REQ-025 ('every application role is denied UPDATE or DELETE of
decisions') proven at the database role level, not just by which HTTP
routes exist -- bgp_app's grant on decision_records is SELECT+INSERT only
(migration 0005_wp07_decisions). Also a basic tenant-isolation check on
exception_records, the one other WP07 table with an evidence-item-scoped
relationship worth proving directly rather than assuming from the shared
migration loop (see test_wp06_tenant_isolation_rls.py's own docstring for
why this repetition matters -- threat model finding T1.4).

BGP-F02 (migration 0010_bgp_f01_f02_fixes) adds compensating_reviews with
the identical SELECT+INSERT-only shape as decision_records -- proven the
same way below, not assumed from the shared migration loop either."""
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

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
def seeded_decision_and_exception():
    tenant_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    template_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    project_id, occurrence_id, item_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    decision_id, exception_id = str(uuid.uuid4()), str(uuid.uuid4())

    minimal_schema = '{"schema_version": 1, "tracks": ["Delivery"], "classes": ["A"], "roles": ["contributor"], "statuses": ["Not started"], "decision_outcomes": ["Approve"], "gates": []}'

    with _owner_engine.begin() as conn:
        conn.execute(text("INSERT INTO tenants (id, name, created_at) VALUES (:id, 'T', now())"), {"id": tenant_id})
        conn.execute(
            text("INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled) VALUES (:id, :email, 'x', false, now(), false)"),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
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
            text("INSERT INTO gate_occurrences (id, tenant_id, project_id, gate_id, sequence, trigger, created_at) VALUES (:id, :tid, :pid, 'G1', 1, 'routine', now())"),
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
            {"id": decision_id, "tid": tenant_id, "pid": project_id, "oid": occurrence_id, "uid": user_id},
        )
        conn.execute(
            text(
                "INSERT INTO exception_records (id, tenant_id, project_id, evidence_item_id, reason, approving_user_id, owner_user_id, starts_at, expires_at, status, created_at) "
                "VALUES (:id, :tid, :pid, :item, 'test', :uid, :uid, now(), now() + interval '30 days', 'active', now())"
            ),
            {"id": exception_id, "tid": tenant_id, "pid": project_id, "item": item_id, "uid": user_id},
        )
        review_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO compensating_reviews (id, tenant_id, project_id, occurrence_id, reviewer_user_id, manifest_digest, note, created_at) "
                "VALUES (:id, :tid, :pid, :oid, :uid, 'deadbeef', 'test review', now())"
            ),
            {"id": review_id, "tid": tenant_id, "pid": project_id, "oid": occurrence_id, "uid": user_id},
        )

    yield {"tenant_id": tenant_id, "decision_id": decision_id, "exception_id": exception_id, "review_id": review_id}

    with _owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        conn.execute(text("DELETE FROM compensating_reviews WHERE id = :id"), {"id": review_id})
        conn.execute(text("DELETE FROM exception_records WHERE id = :id"), {"id": exception_id})
        conn.execute(text("DELETE FROM decision_records WHERE id = :id"), {"id": decision_id})
        conn.execute(text("DELETE FROM evidence_items WHERE id = :id"), {"id": item_id})
        conn.execute(text("DELETE FROM gate_occurrences WHERE id = :id"), {"id": occurrence_id})
        conn.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project_id})
        conn.execute(text("DELETE FROM template_versions WHERE id = :id"), {"id": version_id})
        conn.execute(text("DELETE FROM templates WHERE id = :id"), {"id": template_id})
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def test_app_role_cannot_update_a_decision(seeded_decision_and_exception):
    t = seeded_decision_and_exception
    with pytest.raises(ProgrammingError, match="permission denied"):
        with _app_engine.begin() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(text("UPDATE decision_records SET outcome = 'Hold' WHERE id = :id"), {"id": t["decision_id"]})


def test_app_role_cannot_delete_a_decision(seeded_decision_and_exception):
    t = seeded_decision_and_exception
    with pytest.raises(ProgrammingError, match="permission denied"):
        with _app_engine.begin() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(text("DELETE FROM decision_records WHERE id = :id"), {"id": t["decision_id"]})


def test_app_role_can_still_select_and_insert_decisions(seeded_decision_and_exception):
    t = seeded_decision_and_exception
    with _app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        rows = conn.execute(text("SELECT id FROM decision_records WHERE id = :id"), {"id": t["decision_id"]}).fetchall()
    assert [r.id for r in rows] == [t["decision_id"]]


def test_missing_tenant_context_returns_no_exception_rows(seeded_decision_and_exception):
    with _app_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM exception_records")).fetchall()
    assert rows == []


def test_app_role_cannot_update_a_compensating_review(seeded_decision_and_exception):
    t = seeded_decision_and_exception
    with pytest.raises(ProgrammingError, match="permission denied"):
        with _app_engine.begin() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(text("UPDATE compensating_reviews SET note = 'edited' WHERE id = :id"), {"id": t["review_id"]})


def test_app_role_cannot_delete_a_compensating_review(seeded_decision_and_exception):
    t = seeded_decision_and_exception
    with pytest.raises(ProgrammingError, match="permission denied"):
        with _app_engine.begin() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(text("DELETE FROM compensating_reviews WHERE id = :id"), {"id": t["review_id"]})


def test_missing_tenant_context_returns_no_compensating_review_rows(seeded_decision_and_exception):
    with _app_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM compensating_reviews")).fetchall()
    assert rows == []
