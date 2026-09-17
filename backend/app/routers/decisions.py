import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, require_mfa
from app.integrity import has_open_incident
from app.models import (
    AuditEvent,
    DecisionRecord,
    EvidenceItem,
    ExceptionRecord,
    GateOccurrence,
    IdempotencyRecord,
    Membership,
    Project,
    ProjectMembership,
    User,
)
from app.rule_engine import TemplateSchema, validate_template_schema
from app.routers.projects import _get_owned_project_or_404, _load_bound_schema, _require_project_member

router = APIRouter(tags=["decisions"])

DECISION_AUTHORITY_ROLES = {"approver", "sponsor", "tenant_administrator"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _next_audit_sequence(db: Session, project_id: str) -> int:
    """Prototype scope, same caveat as GateOccurrence.sequence
    (app/routers/projects.py): read-max-then-insert, enforced only by
    whatever serialisation the surrounding transaction provides -- not
    retried automatically under a genuine concurrent race."""
    current_max = db.query(func.max(AuditEvent.sequence)).filter(AuditEvent.project_id == project_id).scalar()
    return (current_max or 0) + 1


def _get_occurrence_or_404(db: Session, project_id: str, occurrence_id: str) -> GateOccurrence:
    occurrence = (
        db.query(GateOccurrence)
        .filter(GateOccurrence.id == occurrence_id, GateOccurrence.project_id == project_id)
        .one_or_none()
    )
    if occurrence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Occurrence not found")
    return occurrence


def _exception_is_currently_valid(db: Session, exc: ExceptionRecord) -> bool:
    """REQ-020: never trust `status` alone. Re-check expiry against server
    time and re-check the approving actor still holds an active,
    authorising membership -- a role change or deactivation after the
    exception was granted silently invalidates it, exactly as intended."""
    if exc.status != "active":
        return False
    now = _now()
    if not (_as_utc(exc.starts_at) <= now <= _as_utc(exc.expires_at)):
        return False
    approver_membership = (
        db.query(Membership)
        .filter(Membership.tenant_id == exc.tenant_id, Membership.user_id == exc.approving_user_id, Membership.active.is_(True))
        .one_or_none()
    )
    return approver_membership is not None and approver_membership.role in DECISION_AUTHORITY_ROLES


def _compute_readiness(db: Session, project: Project, occurrence: GateOccurrence) -> dict:
    """Returns {manifest, manifest_digest, hard_blockers, conditional_blockers,
    advisory_unsatisfied} -- always computed fresh against current evidence
    and exception state, never cached. This *is* REQ-021's reassessment
    mechanism: there is no stored 'readiness' to go stale and no background
    job to trigger, because nothing here is ever read from a cache."""
    items = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.occurrence_id == occurrence.id)
        .order_by(EvidenceItem.id)
        .all()
    )

    hard_blockers, conditional_blockers, advisory_unsatisfied = [], [], []
    for item in items:
        if item.status == "Complete":
            continue
        if item.blocker_level == "advisory":
            advisory_unsatisfied.append(item.id)
            continue
        excepted = any(
            _exception_is_currently_valid(db, exc)
            for exc in db.query(ExceptionRecord).filter(ExceptionRecord.evidence_item_id == item.id).all()
        )
        if excepted:
            continue
        (hard_blockers if item.blocker_level == "hard" else conditional_blockers).append(item.id)

    manifest = {
        "template_version_id": project.template_version_id,
        "evidence": [{"item_id": i.id, "revision_number": i.latest_revision_number} for i in items],
    }
    return {
        "manifest": manifest,
        "manifest_digest": _digest(manifest),
        "hard_blockers": hard_blockers,
        "conditional_blockers": conditional_blockers,
        "advisory_unsatisfied": advisory_unsatisfied,
    }


class ConditionsIn(BaseModel):
    conditions: list[str]
    owner_user_id: str
    deadline: datetime


class SeparationOverrideIn(BaseModel):
    reviewer_user_id: str
    note: str


class PreviewRequest(BaseModel):
    outcome: str | None = None


class PreviewResponse(BaseModel):
    occurrence_id: str
    manifest_digest: str
    hard_blockers: list[str]
    conditional_blockers: list[str]
    advisory_unsatisfied: list[str]
    outcome_allowed: bool | None = None
    outcome_denial_reason: str | None = None


class DecisionRequest(BaseModel):
    outcome: str
    manifest_digest: str
    conditions: ConditionsIn | None = None
    separation_override: SeparationOverrideIn | None = None


class SupersedingRequest(DecisionRequest):
    reason: str


class DecisionOut(BaseModel):
    id: str
    occurrence_id: str
    actor_user_id: str
    actor_role: str
    outcome: str
    reviewed_manifest_digest: str
    supersedes_decision_id: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


def _outcome_eligibility(schema: TemplateSchema, outcome: str, readiness: dict, conditions: ConditionsIn | None) -> tuple[bool, str | None]:
    if outcome not in schema.decision_outcomes:
        return False, f"'{outcome}' is not a decision outcome declared by this template version"

    if outcome in ("Hold", "Redirect", "Terminate"):
        return True, None  # Blueprint Sec.2.2: recorded outcomes, not approvals -- no blocker requirement

    if readiness["hard_blockers"]:
        return False, "unresolved hard blocker(s) deny any approval outcome"

    if outcome == "Approve":
        if readiness["conditional_blockers"]:
            return False, "unresolved conditional blocker(s) -- use 'Approve with conditions' or resolve them first"
        return True, None

    if outcome == "Approve with conditions":
        if conditions is None:
            return False, "missing deadline or condition owner"  # TST-022 wording, covers the whole missing-conditions case
        if not conditions.conditions or not conditions.owner_user_id:
            return False, "missing deadline or condition owner"
        if _as_utc(conditions.deadline) <= _now():
            return False, "missing deadline or condition owner"
        return True, None

    return False, f"outcome '{outcome}' is declared by the template but not handled by this prototype's decision logic"


def _check_separation_of_duties(db: Session, project_id: str, occurrence: GateOccurrence, actor_user_id: str, override: SeparationOverrideIn | None) -> None:
    """REQ-006: self-only approval is rejected unless a valid, non-empty
    compensating-review override names an independent reviewer."""
    required_items = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.occurrence_id == occurrence.id, EvidenceItem.blocker_level != "advisory")
        .all()
    )
    preparers = {i.owner_user_id for i in required_items if i.owner_user_id is not None}
    if not preparers or preparers != {actor_user_id}:
        return  # not a self-only-approval situation

    if override is None or not override.note.strip():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Self-only approval requires a compensating review override with a non-empty note (REQ-006)")
    if override.reviewer_user_id == actor_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The compensating reviewer must be independent of the deciding actor")
    reviewer_pm = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == project_id, ProjectMembership.user_id == override.reviewer_user_id)
        .one_or_none()
    )
    if reviewer_pm is None or reviewer_pm.role not in DECISION_AUTHORITY_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The compensating reviewer must hold approval authority on this project")


def _require_decision_authority(db: Session, project_id: str, user: User) -> ProjectMembership:
    pm = _require_project_member(db, project_id, user.id)
    if pm.role not in DECISION_AUTHORITY_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role does not permit recording decisions")
    if pm.role in DECISION_AUTHORITY_ROLES and not user.mfa_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "MFA is required for this role before deciding (REQ-002)")
    return pm


@router.post("/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/preview", response_model=PreviewResponse)
def preview_decision(
    tenant_id: str,
    project_id: str,
    occurrence_id: str,
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> PreviewResponse:
    project = _get_owned_project_or_404(db, tenant_id, project_id)
    _require_project_member(db, project_id, membership.user_id)
    occurrence = _get_occurrence_or_404(db, project_id, occurrence_id)
    schema = _load_bound_schema(db, tenant_id, project.template_version_id)
    readiness = _compute_readiness(db, project, occurrence)

    outcome_allowed = outcome_denial_reason = None
    if payload.outcome:
        outcome_allowed, outcome_denial_reason = _outcome_eligibility(schema, payload.outcome, readiness, None)

    return PreviewResponse(
        occurrence_id=occurrence_id,
        manifest_digest=readiness["manifest_digest"],
        hard_blockers=readiness["hard_blockers"],
        conditional_blockers=readiness["conditional_blockers"],
        advisory_unsatisfied=readiness["advisory_unsatisfied"],
        outcome_allowed=outcome_allowed,
        outcome_denial_reason=outcome_denial_reason,
    )


def _record_decision(
    db: Session,
    *,
    tenant_id: str,
    project: Project,
    occurrence: GateOccurrence,
    membership: ProjectMembership,
    payload: DecisionRequest,
    supersedes_decision_id: str | None,
    reason: str | None,
    idempotency_key: str,
) -> DecisionOut:
    operation = "supersede_decision" if supersedes_decision_id else "create_decision"
    request_fingerprint = {
        "occurrence_id": occurrence.id,
        "outcome": payload.outcome,
        "manifest_digest": payload.manifest_digest,
        "conditions": payload.conditions.model_dump(mode="json") if payload.conditions else None,
        "separation_override": payload.separation_override.model_dump() if payload.separation_override else None,
        "supersedes_decision_id": supersedes_decision_id,
        "reason": reason,
    }
    request_digest = _digest(request_fingerprint)

    existing = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.actor_user_id == membership.user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.request_digest != request_digest:
            raise HTTPException(status.HTTP_409_CONFLICT, "Idempotency-Key already used for a different request")
        if existing.outcome_status == "denied":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, existing.denial_reason)
        decision = db.get(DecisionRecord, existing.outcome_decision_id)
        return DecisionOut.model_validate(decision)

    # REQ-027: an open integrity incident on this project blocks every new
    # decision, not just ones touching the affected evidence -- the
    # blueprint's own wording ("affected scope") would let this be scoped
    # more narrowly once verify_integrity() can localise which occurrence(s)
    # a checkpoint mismatch actually covers; today a checkpoint spans a
    # whole project's audit trail, so project-wide is the honest scope,
    # not an arbitrarily broader block than necessary.
    open_incident = has_open_incident(db, project.id)
    if open_incident is not None:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"Project has an open integrity incident ({open_incident.id}) -- new decisions are blocked until it is resolved (REQ-027)",
        )

    if supersedes_decision_id is None:
        # Only reached on a genuinely new request (no idempotency match
        # above) -- a retried request for an already-recorded decision
        # returns that decision above instead of hitting this check.
        already_decided = db.query(DecisionRecord).filter(DecisionRecord.occurrence_id == occurrence.id).first()
        if already_decided is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Occurrence already has decision {already_decided.id} -- use POST /decisions/{{id}}/superseding to correct it",
            )

    schema = _load_bound_schema(db, tenant_id, project.template_version_id)
    readiness = _compute_readiness(db, project, occurrence)

    def _deny(reason_text: str, http_status: int) -> None:
        db.add(
            IdempotencyRecord(
                tenant_id=tenant_id,
                actor_user_id=membership.user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                outcome_status="denied",
                denial_reason=reason_text,
            )
        )
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                project_id=project.id,
                occurrence_id=occurrence.id,
                actor_user_id=membership.user_id,
                event_type="decision_denied",
                detail={"reason": reason_text, "outcome": payload.outcome},
                sequence=_next_audit_sequence(db, project.id),
            )
        )
        db.commit()
        raise HTTPException(http_status, reason_text)

    if payload.manifest_digest != readiness["manifest_digest"]:
        _deny("Submitted manifest_digest is stale -- evidence changed since preview, fetch a new preview and retry", status.HTTP_409_CONFLICT)

    allowed, denial_reason = _outcome_eligibility(schema, payload.outcome, readiness, payload.conditions)
    if not allowed:
        _deny(denial_reason, status.HTTP_422_UNPROCESSABLE_ENTITY)

    if payload.outcome in ("Approve", "Approve with conditions"):
        try:
            _check_separation_of_duties(db, project.id, occurrence, membership.user_id, payload.separation_override)
        except HTTPException as exc:
            _deny(str(exc.detail), exc.status_code)

    decision = DecisionRecord(
        tenant_id=tenant_id,
        project_id=project.id,
        occurrence_id=occurrence.id,
        actor_user_id=membership.user_id,
        actor_role=membership.role,
        outcome=payload.outcome,
        manifest_json=readiness["manifest"],
        reviewed_manifest_digest=readiness["manifest_digest"],
        conditions_json=payload.conditions.model_dump(mode="json") if payload.conditions else None,
        supersedes_decision_id=supersedes_decision_id,
        reason=reason,
        separation_override_reviewer_id=payload.separation_override.reviewer_user_id if payload.separation_override else None,
        separation_override_note=payload.separation_override.note if payload.separation_override else None,
    )
    db.add(decision)
    db.flush()
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            project_id=project.id,
            occurrence_id=occurrence.id,
            decision_id=decision.id,
            actor_user_id=membership.user_id,
            event_type="decision_recorded",
            detail={"outcome": payload.outcome, "supersedes": supersedes_decision_id},
            sequence=_next_audit_sequence(db, project.id),
        )
    )
    db.add(
        IdempotencyRecord(
            tenant_id=tenant_id,
            actor_user_id=membership.user_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            outcome_status="created",
            outcome_decision_id=decision.id,
        )
    )
    db.commit()
    db.refresh(decision)
    return DecisionOut.model_validate(decision)


@router.post(
    "/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decisions",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(
    tenant_id: str,
    project_id: str,
    occurrence_id: str,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_mfa),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> DecisionOut:
    """Blueprint Sec.5.4 steps 1-6, 8: authenticate/MFA (dependency), resolve
    project membership and authority, idempotency check, recompute
    readiness against current state and reject stale manifests, construct
    and append the decision atomically. Step 7 (DEC05 durability) is
    explicitly not implemented -- see DecisionRecord's docstring."""
    project = _get_owned_project_or_404(db, tenant_id, project_id)
    membership = _require_decision_authority(db, project_id, user)
    occurrence = _get_occurrence_or_404(db, project_id, occurrence_id)

    return _record_decision(
        db,
        tenant_id=tenant_id,
        project=project,
        occurrence=occurrence,
        membership=membership,
        payload=payload,
        supersedes_decision_id=None,
        reason=None,
        idempotency_key=idempotency_key,
    )


@router.get("/orgs/{tenant_id}/decisions/{decision_id}", response_model=DecisionOut)
def get_decision(
    tenant_id: str,
    decision_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> DecisionOut:
    """Sec.5.4 step 8: 'If the response is lost, the client retrieves the
    outcome rather than creating a second decision.'"""
    decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id, DecisionRecord.tenant_id == tenant_id).one_or_none()
    if decision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decision not found")
    _require_project_member(db, decision.project_id, membership.user_id)
    return DecisionOut.model_validate(decision)


@router.post(
    "/orgs/{tenant_id}/decisions/{decision_id}/superseding",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
)
def supersede_decision(
    tenant_id: str,
    decision_id: str,
    payload: SupersedingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_mfa),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> DecisionOut:
    """REQ-025: 'support superseding corrections only'. The original row is
    never touched -- this only ever INSERTs a new DecisionRecord with
    supersedes_decision_id set. A reason is mandatory."""
    if not payload.reason.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A reason is required to supersede a decision")

    original = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id, DecisionRecord.tenant_id == tenant_id).one_or_none()
    if original is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decision not found")

    already_superseded = db.query(DecisionRecord).filter(DecisionRecord.supersedes_decision_id == decision_id).first()
    if already_superseded is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Decision {decision_id} was already superseded by {already_superseded.id} -- supersede that one instead",
        )

    project = _get_owned_project_or_404(db, tenant_id, original.project_id)
    membership = _require_decision_authority(db, project.id, user)
    occurrence = _get_occurrence_or_404(db, project.id, original.occurrence_id)

    return _record_decision(
        db,
        tenant_id=tenant_id,
        project=project,
        occurrence=occurrence,
        membership=membership,
        payload=payload,
        supersedes_decision_id=decision_id,
        reason=payload.reason,
        idempotency_key=idempotency_key,
    )


class CreateExceptionRequest(BaseModel):
    reason: str
    safeguards: str | None = None
    owner_user_id: str
    starts_at: datetime
    expires_at: datetime


class ExceptionOut(BaseModel):
    id: str
    evidence_item_id: str
    reason: str
    safeguards: str | None
    approving_user_id: str
    owner_user_id: str
    starts_at: datetime
    expires_at: datetime
    status: str
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


@router.post(
    "/orgs/{tenant_id}/evidence/{evidence_item_id}/exceptions",
    response_model=ExceptionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_exception(
    tenant_id: str,
    evidence_item_id: str,
    payload: CreateExceptionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_mfa),
) -> ExceptionOut:
    """REQ-020: authority, scope and expiry are all validated up front, not
    left to be inferred later from a typed status."""
    item = db.query(EvidenceItem).filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id).one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence item not found")
    membership = _require_decision_authority(db, item.project_id, user)

    if _as_utc(payload.expires_at) <= _as_utc(payload.starts_at):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "expires_at must be after starts_at")
    if _as_utc(payload.expires_at) <= _now():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot create an exception that is already expired")

    owner_pm = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == item.project_id, ProjectMembership.user_id == payload.owner_user_id)
        .one_or_none()
    )
    if owner_pm is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "owner_user_id must be a member of this project")

    exc = ExceptionRecord(
        tenant_id=tenant_id,
        project_id=item.project_id,
        evidence_item_id=item.id,
        reason=payload.reason,
        safeguards=payload.safeguards,
        approving_user_id=membership.user_id,
        owner_user_id=payload.owner_user_id,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
    )
    db.add(exc)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            project_id=item.project_id,
            actor_user_id=membership.user_id,
            event_type="exception_created",
            detail={"evidence_item_id": item.id},
            sequence=_next_audit_sequence(db, item.project_id),
        )
    )
    db.commit()
    db.refresh(exc)
    return ExceptionOut.model_validate(exc)


@router.post("/orgs/{tenant_id}/exceptions/{exception_id}/revoke", response_model=ExceptionOut)
def revoke_exception(
    tenant_id: str,
    exception_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_mfa),
) -> ExceptionOut:
    """REQ-021: revocation never deletes the row -- the fact that an
    exception existed and was later revoked stays visible."""
    exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id, ExceptionRecord.tenant_id == tenant_id).one_or_none()
    if exc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exception not found")
    membership = _require_decision_authority(db, exc.project_id, user)

    if exc.status == "revoked":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already revoked")

    exc.status = "revoked"
    exc.revoked_at = _now()
    exc.revoked_by_user_id = membership.user_id
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            project_id=exc.project_id,
            actor_user_id=membership.user_id,
            event_type="exception_revoked",
            detail={"exception_id": exc.id},
            sequence=_next_audit_sequence(db, exc.project_id),
        )
    )
    db.commit()
    db.refresh(exc)
    return ExceptionOut.model_validate(exc)


@router.get("/orgs/{tenant_id}/evidence/{evidence_item_id}/exceptions", response_model=list[ExceptionOut])
def list_exceptions(
    tenant_id: str,
    evidence_item_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> list[ExceptionRecord]:
    item = db.query(EvidenceItem).filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id).one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence item not found")
    _require_project_member(db, item.project_id, membership.user_id)
    return db.query(ExceptionRecord).filter(ExceptionRecord.evidence_item_id == item.id).order_by(ExceptionRecord.created_at).all()
