"""REQ-026/027: hash-chain tamper detection over AuditEvent rows, folded
into permanently unmodifiable IntegrityCheckpoint rows (see that model's
docstring in app/models.py for exactly what this mechanism does and does
not defend against -- read it before treating a clean verify_integrity()
result as a stronger guarantee than it actually is).
"""
import hashlib
import json

from sqlalchemy.orm import Session

from app.models import AuditEvent, IntegrityCheckpoint, IntegrityIncident

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


def take_checkpoint(db: Session, tenant_id: str, project_id: str) -> IntegrityCheckpoint | None:
    """Folds every AuditEvent since the last checkpoint into one digest and
    appends a new checkpoint row -- INSERT only, the row can never be
    UPDATEd or DELETEd afterward (migration 0006_wp08_integrity.py).
    Returns None if there is nothing new to checkpoint."""
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
    db.commit()
    db.refresh(checkpoint)
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
            db.commit()
            db.refresh(incident)
            return {"ok": False, "incident": incident, "checked_checkpoints": len(checkpoints)}
        prev_digest = cp.chain_digest

    return {"ok": True, "incident": None, "checked_checkpoints": len(checkpoints)}


def has_open_incident(db: Session, project_id: str) -> IntegrityIncident | None:
    return (
        db.query(IntegrityIncident)
        .filter(IntegrityIncident.project_id == project_id, IntegrityIncident.status == "open")
        .first()
    )
