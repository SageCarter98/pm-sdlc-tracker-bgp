"""REQ-026/027: hash-chain tamper detection over AuditEvent rows, folded
into permanently unmodifiable IntegrityCheckpoint rows (see that model's
docstring in app/models.py for exactly what this mechanism does and does
not defend against -- read it before treating a clean verify_integrity()
result as a stronger guarantee than it actually is).
"""

import hashlib
import json

from sqlalchemy.orm import Session

from app.models import AuditEvent, IntegrityCheckpoint, IntegrityIncident, WormAnchorReceipt
from app.worm_anchor import WormAnchorStore

GENESIS_DIGEST = "0" * 64


def _canonical_event(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "project_id": event.project_id,
        "occurrence_id": event.occurrence_id,
        "decision_id": event.decision_id,
        "actor_user_id": event.actor_user_id,
        "event_type": event.event_type,
        "detail": event.detail,
        "sequence": event.sequence,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _fold_chain(prev_digest: str, events: list[AuditEvent]) -> str:
    digest = prev_digest
    for event in events:
        payload = json.dumps({"prev": digest, "event": _canonical_event(event)}, sort_keys=True, default=str)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest


def checkpoint_new_events(db: Session, tenant_id: str, project_id: str) -> IntegrityCheckpoint | None:
    """DEC05 G1: identical folding logic to take_checkpoint below, but does
    NOT commit -- it only queries, folds, and db.add()s the new checkpoint,
    leaving the commit to the caller. This is what lets
    app/routers/decisions.py's _record_decision fold a decision's own audit
    event into a checkpoint in the SAME transaction as the decision itself
    (DEC05 s"Candidate A+"'s synchronous acknowledgement half), rather than
    the old model of a separate, later, manually-triggered checkpoint.

    Callers on live Postgres MUST hold
    `pg_advisory_xact_lock(hashtext(project_id))` before calling this --
    two concurrent callers for the SAME project would otherwise both read
    the same "latest checkpoint" and each fold from it, producing two
    checkpoints with overlapping sequence ranges instead of one serialized
    chain. See app/routers/decisions.py for where that lock is taken.

    Returns None if there is nothing new to checkpoint."""
    # app/db.py's SessionLocal is autoflush=False -- a caller's own
    # just-added, not-yet-flushed AuditEvent (e.g. decisions.py's
    # "decision_recorded"/"decision_denied" rows, added immediately before
    # calling this) would otherwise be invisible to the query below, which
    # runs a real SELECT against the database, not against the session's
    # in-memory pending objects.
    db.flush()
    latest = (
        db.query(IntegrityCheckpoint)
        .filter(IntegrityCheckpoint.project_id == project_id)
        .order_by(IntegrityCheckpoint.to_sequence.desc())
        .first()
    )
    prev_digest = latest.chain_digest if latest else GENESIS_DIGEST
    from_sequence = latest.to_sequence if latest else None

    q = db.query(AuditEvent).filter(AuditEvent.project_id == project_id)
    if from_sequence is not None:
        q = q.filter(AuditEvent.sequence > from_sequence)
    events = q.order_by(AuditEvent.sequence).all()
    if not events:
        return None

    checkpoint = IntegrityCheckpoint(
        tenant_id=tenant_id,
        project_id=project_id,
        from_sequence=from_sequence,
        to_sequence=events[-1].sequence,
        event_count=len(events),
        chain_digest=_fold_chain(prev_digest, events),
    )
    db.add(checkpoint)
    return checkpoint


def take_checkpoint(db: Session, tenant_id: str, project_id: str) -> IntegrityCheckpoint | None:
    """The pre-existing manual, admin-triggered checkpoint endpoint's
    implementation (app/routers/integrity.py) -- unchanged in behavior
    since DEC05: still useful for backfilling any audit events that don't
    go through _record_decision's own synchronous checkpointing."""
    checkpoint = checkpoint_new_events(db, tenant_id, project_id)
    db.commit()
    # No db.refresh() -- see app/db.py's SessionLocal docstring
    # (expire_on_commit=False): every field here was already set in Python
    # before commit, and integrity_checkpoints is RLS-protected, so a
    # post-commit refresh would run with no tenant context left and raise
    # (found 2026-09-20 building WP11's first real end-to-end usage).
    return checkpoint


def verify_integrity(db: Session, tenant_id: str, project_id: str) -> dict:
    """Re-derives every checkpoint's chain digest from the AuditEvent rows
    currently in the table and compares. A mismatch -- content changed,
    rows deleted, or reordered (sequence, not insertion order, drives the
    fold) -- opens an IntegrityIncident and stops at the first failing
    checkpoint. Returns {"ok", "incident", "checked_checkpoints"}."""
    checkpoints = (
        db.query(IntegrityCheckpoint)
        .filter(IntegrityCheckpoint.project_id == project_id)
        .order_by(IntegrityCheckpoint.to_sequence)
        .all()
    )
    prev_digest = GENESIS_DIGEST
    for i, cp in enumerate(checkpoints):
        q = db.query(AuditEvent).filter(AuditEvent.project_id == project_id)
        if cp.from_sequence is not None:
            q = q.filter(AuditEvent.sequence > cp.from_sequence)
        q = q.filter(AuditEvent.sequence <= cp.to_sequence)
        events = q.order_by(AuditEvent.sequence).all()

        recomputed = _fold_chain(prev_digest, events)
        if recomputed != cp.chain_digest or len(events) != cp.event_count:
            incident = IntegrityIncident(
                tenant_id=tenant_id,
                project_id=project_id,
                detail={
                    "checkpoint_id": cp.id,
                    "checkpoint_index": i,
                    "expected_digest": cp.chain_digest,
                    "recomputed_digest": recomputed,
                    "expected_event_count": cp.event_count,
                    "recomputed_event_count": len(events),
                },
            )
            db.add(incident)
            db.commit()  # No db.refresh() -- see checkpoint creation above, same reasoning.
            return {"ok": False, "incident": incident, "checked_checkpoints": len(checkpoints)}
        prev_digest = cp.chain_digest

    return {"ok": True, "incident": None, "checked_checkpoints": len(checkpoints)}


def has_open_incident(db: Session, project_id: str) -> IntegrityIncident | None:
    return (
        db.query(IntegrityIncident)
        .filter(IntegrityIncident.project_id == project_id, IntegrityIncident.status == "open")
        .first()
    )


def verify_against_anchor(db: Session, worm_store: WormAnchorStore, tenant_id: str, project_id: str) -> dict:
    """DEC05 G3: cross-checks each checkpoint's DB-stored chain_digest
    against its externally-anchored WORM copy (app/worm_anchor.py,
    scripts/anchor_worm.py). This is the check verify_integrity() above
    cannot do: verify_integrity re-derives a checkpoint's digest from
    AuditEvent rows in the SAME database -- a rewrite that changes an audit
    event's content and its own checkpoint's chain_digest together, self-
    consistently, re-derives clean under verify_integrity every time.
    Comparing against a copy held OUTSIDE this Postgres instance entirely is
    what catches that (see IntegrityCheckpoint's own docstring, app/
    models.py, and the DEC05 design spec s4.3 for the full rationale).

    A checkpoint with no receipt yet (anchor_worm.py hasn't reached it) is
    skipped, not treated as a mismatch -- anchoring is asynchronous by
    design (DEC05's own "Candidate A+" wording: only the chain-link-at-
    commit is synchronous). Returns {"ok", "incident", "checked_checkpoints"}
    -- checked_checkpoints counts only checkpoints that actually had an
    anchor to compare against."""
    checkpoints = (
        db.query(IntegrityCheckpoint)
        .filter(IntegrityCheckpoint.project_id == project_id)
        .order_by(IntegrityCheckpoint.to_sequence)
        .all()
    )
    checked = 0
    for cp in checkpoints:
        receipt = db.query(WormAnchorReceipt).filter(WormAnchorReceipt.checkpoint_id == cp.id).one_or_none()
        if receipt is None:
            continue
        checked += 1
        anchored = json.loads(worm_store.read(receipt.anchor_key))
        if anchored["chain_digest"] != cp.chain_digest:
            incident = IntegrityIncident(
                tenant_id=tenant_id,
                project_id=project_id,
                detail={
                    "check": "verify_against_anchor",
                    "checkpoint_id": cp.id,
                    "anchor_key": receipt.anchor_key,
                    "anchored_digest": anchored["chain_digest"],
                    "db_digest": cp.chain_digest,
                },
            )
            db.add(incident)
            db.commit()  # No db.refresh() -- see checkpoint creation above, same reasoning.
            return {"ok": False, "incident": incident, "checked_checkpoints": checked}

    return {"ok": True, "incident": None, "checked_checkpoints": checked}
