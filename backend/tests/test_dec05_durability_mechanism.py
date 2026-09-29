"""DEC05 (docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md,
Candidate A+, accepted by delivery lead 2026-09-27 -- NOT an independent
Operations/security sign-off) durability mechanism:

- G1: a decision's own audit event is folded into a new IntegrityCheckpoint
  in the SAME transaction as the decision commit
  (app/routers/decisions.py's _checkpoint_this_project,
  app/integrity.py's checkpoint_new_events).
- G2: every checkpoint gets an asynchronous, externally-custodied WORM
  anchor copy (app/worm_anchor.py, scripts/anchor_worm.py).
- G3: an independent job cross-checks the DB's own checkpoints against
  their external anchors (app/integrity.py's verify_against_anchor,
  scripts/verify_against_anchor.py) -- catching a self-consistent DB-side
  rewrite that same-instance re-derivation (verify_integrity, WP08) cannot,
  by design, detect.

Full rationale: docs/superpowers/specs/2026-09-29-dec05-durability-
mechanism-design.md.

Same live-Postgres requirement as every other IPA02/WP13+ test needing real
RLS, advisory-lock, or database-role-boundary behavior the SQLite `client`
fixture cannot provide -- and this file additionally needs bgp_backup
(WORM anchoring's own tests read receipts written by app-role sessions,
consistent with every other test file using this skip pattern).
"""

import json
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

try:
    _owner_engine = create_engine(settings.migration_database_url, future=True)
    with _owner_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    _app_engine = create_engine(settings.database_url, future=True)
    with _app_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    _backup_engine = create_engine(settings.backup_database_url, future=True)
    with _backup_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    POSTGRES_AVAILABLE = True
except OperationalError:
    POSTGRES_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app/bgp_backup not configured"
)

# expire_on_commit=False, same as app/db.py's own SessionLocal and for the
# identical reason (see that module's docstring): a post-commit attribute
# access on an ORM object returned from an RLS-protected table would
# otherwise trigger a re-SELECT with no tenant context left (SET LOCAL ends
# at commit) and raise ObjectDeletedError, as if the just-committed row had
# vanished -- found writing this file's own G3 tamper-detection test.
_TestSession = sessionmaker(bind=_app_engine, future=True, expire_on_commit=False) if POSTGRES_AVAILABLE else None


@pytest.fixture()
def pg_client():
    from fastapi.testclient import TestClient

    from app.main import app

    assert app.dependency_overrides == {}, "DEC05 exercises real transactions/locks -- the SQLite fixture cannot"
    return TestClient(app)


def _setup_project(pg_client):
    """Same shape as test_dec08_performance_budgets.py's own helper --
    unique-per-call emails since real Postgres persists accounts across
    separate test functions in this same file, unlike the SQLite `client`
    fixture (truncated per test)."""
    from tests.conftest import enable_mfa, register_and_login
    from tests.test_projects import (
        _create_org_as_admin,
        _create_project,
        _invite_and_accept,
        _publish_standard_template,
    )

    admin_email = f"{uuid.uuid4()}@example.com"
    approver_email = f"{uuid.uuid4()}@example.com"

    tenant_id = _create_org_as_admin(pg_client, admin_email)
    enable_mfa(pg_client)
    admin_id = pg_client.get("/auth/me").json()["id"]

    approver_id = _invite_and_accept(pg_client, tenant_id, approver_email, "approver")
    enable_mfa(pg_client)

    register_and_login(pg_client, admin_email)
    version_id, _ = _publish_standard_template(pg_client, tenant_id)
    created = _create_project(
        pg_client, tenant_id, version_id, "Standard-High", members=[{"user_id": approver_id, "role": "approver"}]
    ).json()
    return tenant_id, created, admin_id, approver_id


def _hold(pg_client, tenant_id, project_id, occurrence_id, key):
    """Hold bypasses the hard-blocker denial and separation-of-duties check
    (decisions.py only runs that check for Approve outcomes) -- same reason
    test_dec08_performance_budgets.py's decision-write test uses it: it
    exercises the real decision-commit code path without needing full
    evidence completion first."""
    preview = pg_client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/preview", json={})
    assert preview.status_code == 200, preview.text
    return pg_client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": preview.json()["manifest_digest"]},
        headers={"Idempotency-Key": key},
    )


def _checkpoints(tenant_id, project_id):
    from app.models import IntegrityCheckpoint

    with _TestSession() as db:
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        return (
            db.query(IntegrityCheckpoint)
            .filter(IntegrityCheckpoint.project_id == project_id)
            .order_by(IntegrityCheckpoint.to_sequence)
            .all()
        )


def test_decision_commit_folds_its_own_audit_event_into_a_checkpoint_atomically(pg_client):
    """G1: no separate manual /integrity/checkpoint call is made here at
    all -- if the decision's own commit didn't already checkpoint it,
    verify_integrity would have nothing to check (checked_checkpoints==0)
    and this would trivially "pass" for the wrong reason, so this also
    asserts a checkpoint actually exists."""
    tenant_id, created, _admin_id, _approver_id = _setup_project(pg_client)
    project_id = created["project"]["id"]
    occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")

    decision = _hold(pg_client, tenant_id, project_id, occurrence_id, "dec05-g1-0")
    assert decision.status_code == 201, decision.text

    checkpoints = _checkpoints(tenant_id, project_id)
    assert len(checkpoints) == 1
    assert checkpoints[0].event_count == 1

    verify = pg_client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    assert verify.status_code == 200, verify.text
    assert verify.json()["ok"] is True
    assert verify.json()["checked_checkpoints"] == 1


def test_denied_decision_also_gets_its_audit_event_checkpointed(pg_client):
    tenant_id, created, _admin_id, _approver_id = _setup_project(pg_client)
    project_id = created["project"]["id"]
    occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")

    pg_client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/preview", json={})
    denied = pg_client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": "sha256:deliberately-stale"},
        headers={"Idempotency-Key": "dec05-g1-denied"},
    )
    assert denied.status_code == 409, denied.text

    checkpoints = _checkpoints(tenant_id, project_id)
    assert len(checkpoints) == 1
    assert checkpoints[0].event_count == 1

    verify = pg_client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    assert verify.json()["ok"] is True


def test_two_decisions_same_project_produce_nonoverlapping_reverifiable_checkpoints(pg_client):
    tenant_id, created, _admin_id, _approver_id = _setup_project(pg_client)
    project_id = created["project"]["id"]
    s1 = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    s3 = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S3")

    first = _hold(pg_client, tenant_id, project_id, s1, "dec05-nonoverlap-0")
    second = _hold(pg_client, tenant_id, project_id, s3, "dec05-nonoverlap-1")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    checkpoints = _checkpoints(tenant_id, project_id)
    assert len(checkpoints) == 2
    assert checkpoints[0].to_sequence < checkpoints[1].from_sequence + 1 <= checkpoints[1].to_sequence
    assert checkpoints[1].from_sequence == checkpoints[0].to_sequence

    verify = pg_client.post(f"/orgs/{tenant_id}/projects/{project_id}/integrity/verify")
    assert verify.json()["ok"] is True
    assert verify.json()["checked_checkpoints"] == 2


def test_advisory_lock_serializes_concurrent_checkpoint_attempts():
    """Proves the actual Postgres primitive _checkpoint_this_project relies
    on serializes concurrent access -- same lock-blocking technique as
    test_bgp_f03_decision_concurrency.py (session A holds, session B with a
    short lock_timeout must fail while A holds it, then succeed once A
    releases), avoiding real threads' flakiness under CI scheduling
    jitter."""
    project_id = str(uuid.uuid4())

    session_a = _app_engine.connect()
    txn_a = session_a.begin()
    session_a.execute(text("SELECT pg_advisory_xact_lock(hashtext(:pid))"), {"pid": project_id})

    session_b = _app_engine.connect()
    txn_b = session_b.begin()
    session_b.execute(text("SET LOCAL lock_timeout = '200ms'"))
    with pytest.raises(OperationalError):
        session_b.execute(text("SELECT pg_advisory_xact_lock(hashtext(:pid))"), {"pid": project_id})
    txn_b.rollback()

    txn_a.commit()  # releases the advisory lock (transaction-scoped)
    session_a.close()

    session_c = _app_engine.connect()
    txn_c = session_c.begin()
    session_c.execute(text("SELECT pg_advisory_xact_lock(hashtext(:pid))"), {"pid": project_id})
    txn_c.commit()
    session_c.close()
    session_b.close()


def test_anchor_worm_anchors_once_and_is_a_noop_on_rerun(pg_client):
    from app.models import WormAnchorReceipt
    from app.worm_anchor import LocalWormAnchorStore
    from scripts.anchor_worm import anchor_unanchored_checkpoints

    tenant_id, created, _admin_id, _approver_id = _setup_project(pg_client)
    project_id = created["project"]["id"]
    occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    decision = _hold(pg_client, tenant_id, project_id, occurrence_id, "dec05-anchor-0")
    assert decision.status_code == 201, decision.text

    with tempfile.TemporaryDirectory() as tmp:
        store = LocalWormAnchorStore(root=tmp)

        with _TestSession() as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            first_count = anchor_unanchored_checkpoints(db, store, tenant_id)
        assert first_count == 1

        with _TestSession() as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            receipts = db.query(WormAnchorReceipt).filter(WormAnchorReceipt.project_id == project_id).all()
            assert len(receipts) == 1
            written = json.loads(store.read(receipts[0].anchor_key))
            checkpoint = _checkpoints(tenant_id, project_id)[0]
            assert written["chain_digest"] == checkpoint.chain_digest
            assert Path(tmp, receipts[0].anchor_key).exists()

        with _TestSession() as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            second_count = anchor_unanchored_checkpoints(db, store, tenant_id)
        assert second_count == 0

        with _TestSession() as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            receipts_after = db.query(WormAnchorReceipt).filter(WormAnchorReceipt.project_id == project_id).all()
            assert len(receipts_after) == 1


def test_verify_against_anchor_catches_a_self_consistent_db_side_rewrite_that_verify_integrity_cannot(pg_client):
    """G3's whole reason to exist. A "rogue DBA" who rewrites an audit
    event's content AND recomputes its checkpoint's chain_digest to match,
    consistently, within the same Postgres instance re-derives clean under
    verify_integrity() every time -- that is exactly the gap
    IntegrityCheckpoint's own docstring (app/models.py) names, and DDL
    (ALTER TABLE ... NO FORCE ROW LEVEL SECURITY) is something REVOKE/RLS
    cannot take from the table owner, so bgp_owner really can do this.
    Comparing against a copy held OUTSIDE this Postgres instance is what
    catches it."""
    from app.integrity import GENESIS_DIGEST, _fold_chain, verify_against_anchor, verify_integrity
    from app.models import AuditEvent
    from app.worm_anchor import LocalWormAnchorStore
    from scripts.anchor_worm import anchor_unanchored_checkpoints

    tenant_id, created, _admin_id, _approver_id = _setup_project(pg_client)
    project_id = created["project"]["id"]
    occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")
    decision = _hold(pg_client, tenant_id, project_id, occurrence_id, "dec05-tamper-0")
    assert decision.status_code == 201, decision.text

    with tempfile.TemporaryDirectory() as tmp:
        store = LocalWormAnchorStore(root=tmp)
        with _TestSession() as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            anchored_count = anchor_unanchored_checkpoints(db, store, tenant_id)
        assert anchored_count == 1

        # Rogue-DBA simulation: as bgp_owner (the table owner -- DDL rights
        # RLS cannot take away), temporarily lift integrity_checkpoints'
        # normally-unconditional UPDATE deny, then rewrite the audit event
        # AND its checkpoint's chain_digest together, self-consistently.
        with _owner_engine.begin() as owner_conn:
            owner_conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            event_row = (
                owner_conn.execute(text("SELECT * FROM audit_events WHERE project_id = :pid"), {"pid": project_id})
                .mappings()
                .one()
            )
            checkpoint_row = (
                owner_conn.execute(
                    text("SELECT * FROM integrity_checkpoints WHERE project_id = :pid"), {"pid": project_id}
                )
                .mappings()
                .one()
            )

            owner_conn.execute(
                text("UPDATE audit_events SET detail = :detail WHERE id = :id"),
                {"detail": json.dumps({"tampered": True}), "id": event_row["id"]},
            )
            tampered_event = AuditEvent(
                id=event_row["id"],
                tenant_id=event_row["tenant_id"],
                project_id=event_row["project_id"],
                occurrence_id=event_row["occurrence_id"],
                decision_id=event_row["decision_id"],
                actor_user_id=event_row["actor_user_id"],
                event_type=event_row["event_type"],
                detail={"tampered": True},
                sequence=event_row["sequence"],
                created_at=event_row["created_at"],
            )
            # This project's very first (and only) event -- genesis digest,
            # same as checkpoint_new_events would have used originally.
            recomputed_digest = _fold_chain(GENESIS_DIGEST, [tampered_event])

            owner_conn.execute(text("ALTER TABLE integrity_checkpoints NO FORCE ROW LEVEL SECURITY"))
            owner_conn.execute(text("DROP POLICY integrity_checkpoints_no_update ON integrity_checkpoints"))
            owner_conn.execute(
                text("UPDATE integrity_checkpoints SET chain_digest = :digest WHERE id = :id"),
                {"digest": recomputed_digest, "id": checkpoint_row["id"]},
            )
            owner_conn.execute(
                text("CREATE POLICY integrity_checkpoints_no_update ON integrity_checkpoints FOR UPDATE USING (false)")
            )
            owner_conn.execute(text("ALTER TABLE integrity_checkpoints FORCE ROW LEVEL SECURITY"))

        # Same-instance re-derivation is blind to this by construction.
        with _TestSession() as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            same_instance = verify_integrity(db, tenant_id, project_id)
        assert same_instance["ok"] is True

        # The external-anchor cross-check is not. Read .detail while the
        # session is still open -- a plain Session() (unlike app/db.py's
        # SessionLocal) expires attributes on commit, and this incident was
        # committed inside verify_against_anchor itself.
        with _TestSession() as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            anchor_check = verify_against_anchor(db, store, tenant_id, project_id)
            assert anchor_check["ok"] is False
            assert anchor_check["incident"] is not None
            assert anchor_check["incident"].detail["db_digest"] == recomputed_digest
