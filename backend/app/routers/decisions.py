import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, get_session_mfa_verified, require_mfa
from app.integrity import has_open_incident
from app.models import (
    AuditEvent,
    CompensatingReview,
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


def _compute_readiness(db: Session, project: Project, occurrence: GateOccurrence, *, lock: bool = False) -> dict:
    """Returns {manifest, manifest_digest, hard_blockers, conditional_blockers,
    advisory_unsatisfied} -- always computed fresh against current evidence
    and exception state, never cached. This *is* REQ-021's reassessment
    mechanism: there is no stored 'readiness' to go stale and no background
    job to trigger, because nothing here is ever read from a cache.

    BGP-F03: `lock=True` (decision-commit callers only, never preview/review
    -- locking there would only cost concurrent readers correctness they
    don't need) takes `SELECT ... FOR UPDATE` on these evidence rows,
    ordered by id -- the same fixed order create_evidence_revision locks a
    single row in (app/routers/projects.py), so two transactions can only
    ever wait on each other, never deadlock. A concurrent evidence write for
    an item in THIS occurrence now blocks until this transaction commits or
    rolls back, so the readiness this function returns cannot go stale
    between being read here and the decision committing -- closing the
    'evidence changed between readiness evaluation and commit' race the
    manifest_digest staleness check alone could not (that check only
    catches a change that had already committed before this call started,
    not one racing it). A no-op on SQLite (no FOR UPDATE support there) --
    this project's real concurrency guarantee is proved against live
    Postgres, see test_bgp_f03_decision_concurrency.py."""
    query = db.query(EvidenceItem).filter(EvidenceItem.occurrence_id == occurrence.id).order_by(EvidenceItem.id)
    if lock:
        query = query.with_for_update()
    items = query.all()

    hard_blockers, conditional_blockers, advisory_unsatisfied = [], [], []
    blocker_explanations = []
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
        blocker_explanations.append({
            "item_id": item.id,
            "gate_id": item.gate_id,
            "blocker_level": item.blocker_level,
            # REQ-036: plain language, no restricted information (item id
            # and gate/kind are already scoped to a project this caller is
            # a member of by the time this function runs).
            "explanation": (
                f"Gate {item.gate_id}: a {item.blocker_level} '{item.evidence_kind}' item "
                f"(currently '{item.status}') has not been marked Complete."
            ),
            "corrective_action": f"POST /orgs/{{tenant_id}}/evidence/{item.id}/revisions with status 'Complete' and a reference",
        })

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
        "blocker_explanations": blocker_explanations,
    }


class ConditionsIn(BaseModel):
    conditions: list[str]
    owner_user_id: str
    deadline: datetime


class SeparationOverrideIn(BaseModel):
    """BGP-F02: identifies a CompensatingReview row the independent reviewer
    already created from their OWN session (POST .../compensating-reviews)
    -- the deciding actor can no longer just name a colleague and a note
    themselves."""

    review_id: str


class CompensatingReviewIn(BaseModel):
    note: str


class CompensatingReviewOut(BaseModel):
    id: str
    occurrence_id: str
    reviewer_user_id: str
    manifest_digest: str
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PreviewRequest(BaseModel):
    outcome: str | None = None


class BlockerExplanation(BaseModel):
    item_id: str
    gate_id: str
    blocker_level: str
    explanation: str
    corrective_action: str


class PreviewResponse(BaseModel):
    occurrence_id: str
    manifest_digest: str
    hard_blockers: list[str]
    conditional_blockers: list[str]
    advisory_unsatisfied: list[str]
    blocker_explanations: list[BlockerExplanation]
    # REQ-037: 'show... permitted progression in a deliberate approval
    # confirmation summary' -- every outcome the template declares that
    # current readiness would allow right now, not just the one outcome
    # (if any) the caller happened to ask about below.
    permitted_outcomes: list[str]
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


def _permitted_outcomes(schema: TemplateSchema, readiness: dict) -> list[str]:
    """REQ-037's confirmation-summary list. Deliberately more lenient than
    _outcome_eligibility for 'Approve with conditions': that outcome is
    structurally reachable whenever no hard blocker exists, even before
    the caller has actually supplied conditions -- the summary's job is to
    tell the user which *paths* are open, not to pre-validate a specific
    conditions payload they haven't written yet."""
    permitted = []
    for outcome in schema.decision_outcomes:
        if outcome in ("Hold", "Redirect", "Terminate"):
            permitted.append(outcome)
        elif readiness["hard_blockers"]:
            continue
        elif outcome == "Approve" and not readiness["conditional_blockers"]:
            permitted.append(outcome)
        elif outcome == "Approve with conditions":
            permitted.append(outcome)
    return permitted


def _check_separation_of_duties(
    db: Session,
    tenant_id: str,
    project_id: str,
    occurrence: GateOccurrence,
    actor_user_id: str,
    manifest_digest: str,
    override: SeparationOverrideIn | None,
) -> CompensatingReview | None:
    """REQ-006/BGP-F02: self-only approval is rejected unless `override`
    names a CompensatingReview row -- and that row is re-validated here,
    fresh, every time, never trusted as still good just because it exists:
    it must be for this exact occurrence, its manifest_digest must match
    what the decision is being made against right now (a changed evidence
    manifest since the review means a stale review, not a valid one), the
    reviewer must be independent of the decider, and the reviewer must
    currently hold active, non-revoked decision authority (the same
    'active membership + authorising role' re-check REQ-020's exception
    validity already uses, see _exception_is_currently_valid)."""
    required_items = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.occurrence_id == occurrence.id, EvidenceItem.blocker_level != "advisory")
        .all()
    )
    preparers = {i.owner_user_id for i in required_items if i.owner_user_id is not None}
    if not preparers or preparers != {actor_user_id}:
        return None  # not a self-only-approval situation

    if override is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Self-only approval requires an independent compensating review (REQ-006) -- "
            "have another approver record one via POST .../compensating-reviews first",
        )

    review = (
        db.query(CompensatingReview)
        .filter(CompensatingReview.id == override.review_id, CompensatingReview.tenant_id == tenant_id, CompensatingReview.project_id == project_id)
        .one_or_none()
    )
    if review is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Compensating review not found for this project")
    if review.occurrence_id != occurrence.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That compensating review was recorded for a different occurrence")
    if review.manifest_digest != manifest_digest:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "That compensating review is stale -- evidence has changed since it was recorded; have the reviewer record a fresh one",
        )
    if review.reviewer_user_id == actor_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The compensating reviewer must be independent of the deciding actor")

    reviewer_membership = (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.user_id == review.reviewer_user_id, Membership.active.is_(True))
        .one_or_none()
    )
    if reviewer_membership is None or reviewer_membership.role not in DECISION_AUTHORITY_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The compensating reviewer no longer holds active approval authority")
    reviewer_pm = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == project_id, ProjectMembership.user_id == review.reviewer_user_id)
        .one_or_none()
    )
    if reviewer_pm is None or reviewer_pm.role not in DECISION_AUTHORITY_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The compensating reviewer no longer holds approval authority on this project")

    return review


def _require_decision_authority(db: Session, project_id: str, user: User, mfa_verified: bool) -> ProjectMembership:
    """BGP-F03: locks the caller's ProjectMembership row FOR UPDATE (a
    no-op on SQLite) instead of using the shared, unlocked
    _require_project_member -- read-only paths (preview, get_decision,
    list_exceptions) must not pay for or hold this lock, but every path
    that goes on to actually commit a decision-adjacent write should
    participate in the same 'authority is re-read inside protection'
    guarantee _compute_readiness's lock=True gives evidence. Always
    acquired before any evidence-row lock in the same request (fixed lock
    order: membership, then evidence -- see _compute_readiness's docstring)
    so two concurrent decision-committing transactions can only ever wait
    on each other, never deadlock."""
    pm = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == project_id, ProjectMembership.user_id == user.id)
        .with_for_update()
        .one_or_none()
    )
    if pm is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this project")
    if pm.role not in DECISION_AUTHORITY_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role does not permit recording decisions")
    # BGP-F01: session-bound, same reasoning as app/deps.py's require_mfa --
    # user.mfa_enabled alone (an account-level flag) is not evidence this
    # session ever completed a second-factor check.
    if not (mfa_verified and user.mfa_enabled):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "MFA verification is required for this session before deciding (REQ-002)")
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
        blocker_explanations=readiness["blocker_explanations"],
        permitted_outcomes=_permitted_outcomes(schema, readiness),
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
    # BGP-F03: locked -- see _compute_readiness's docstring. Held from here
    # through the commit below, so nothing can change these evidence items
    # out from under this decision between reading them and committing.
    readiness = _compute_readiness(db, project, occurrence, lock=True)

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

    compensating_review = None
    if payload.outcome in ("Approve", "Approve with conditions"):
        try:
            compensating_review = _check_separation_of_duties(
                db, tenant_id, project.id, occurrence, membership.user_id, readiness["manifest_digest"], payload.separation_override
            )
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
        # BGP-F02: sourced from the verified CompensatingReview row, never
        # from client-supplied reviewer_user_id/note again.
        separation_override_review_id=compensating_review.id if compensating_review else None,
        separation_override_reviewer_id=compensating_review.reviewer_user_id if compensating_review else None,
        separation_override_note=compensating_review.note if compensating_review else None,
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
    try:
        db.commit()
    except IntegrityError:
        # BGP-F03: a concurrent request for the SAME occurrence/decision won
        # the race and committed first -- this is exactly the case the
        # upfront idempotency/already-decided/already-superseded checks
        # above could not catch, because both requests passed them before
        # either had committed. Never let this surface as a bare 500;
        # re-derive which real-DB guarantee actually fired (the same three
        # this function already checks up front: uq_idempotency_scope,
        # and, live-Postgres only, the partial unique indexes from
        # migration 0011_bgp_f03_concurrency) and answer exactly
        # as if that check had caught it originally.
        db.rollback()

        winner = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.tenant_id == tenant_id,
                IdempotencyRecord.actor_user_id == membership.user_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
            .one_or_none()
        )
        if winner is not None:
            if winner.request_digest != request_digest:
                raise HTTPException(status.HTTP_409_CONFLICT, "Idempotency-Key already used for a different request")
            if winner.outcome_status == "denied":
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, winner.denial_reason)
            won_decision = db.get(DecisionRecord, winner.outcome_decision_id)
            return DecisionOut.model_validate(won_decision)

        if supersedes_decision_id is None:
            other_root = db.query(DecisionRecord).filter(DecisionRecord.occurrence_id == occurrence.id).first()
            if other_root is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Occurrence already has decision {other_root.id} -- use POST /decisions/{{id}}/superseding to correct it",
                )
        else:
            other_supersession = (
                db.query(DecisionRecord).filter(DecisionRecord.supersedes_decision_id == supersedes_decision_id).first()
            )
            if other_supersession is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Decision {supersedes_decision_id} was already superseded by {other_supersession.id} -- supersede that one instead",
                )

        raise  # an unrecognised integrity conflict -- surface it rather than guessing
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
    mfa_verified: bool = Depends(get_session_mfa_verified),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> DecisionOut:
    """Blueprint Sec.5.4 steps 1-6, 8: authenticate/MFA (dependency), resolve
    project membership and authority, idempotency check, recompute
    readiness against current state and reject stale manifests, construct
    and append the decision atomically. Step 7 (DEC05 durability) is
    explicitly not implemented -- see DecisionRecord's docstring."""
    project = _get_owned_project_or_404(db, tenant_id, project_id)
    membership = _require_decision_authority(db, project_id, user, mfa_verified)
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
    mfa_verified: bool = Depends(get_session_mfa_verified),
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
    membership = _require_decision_authority(db, project.id, user, mfa_verified)
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
    mfa_verified: bool = Depends(get_session_mfa_verified),
) -> ExceptionOut:
    """REQ-020: authority, scope and expiry are all validated up front, not
    left to be inferred later from a typed status."""
    item = db.query(EvidenceItem).filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id).one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence item not found")
    membership = _require_decision_authority(db, item.project_id, user, mfa_verified)

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
    mfa_verified: bool = Depends(get_session_mfa_verified),
) -> ExceptionOut:
    """REQ-021: revocation never deletes the row -- the fact that an
    exception existed and was later revoked stays visible."""
    exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id, ExceptionRecord.tenant_id == tenant_id).one_or_none()
    if exc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exception not found")
    membership = _require_decision_authority(db, exc.project_id, user, mfa_verified)

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


@router.post(
    "/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/compensating-reviews",
    response_model=CompensatingReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_compensating_review(
    tenant_id: str,
    project_id: str,
    occurrence_id: str,
    payload: CompensatingReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_mfa),
    mfa_verified: bool = Depends(get_session_mfa_verified),
) -> CompensatingReviewOut:
    """REQ-006/BGP-F02: the independent reviewer's OWN authenticated,
    MFA-verified action -- `reviewer_user_id` below is always this caller's
    own id, never a name someone else typed. Binds to the CURRENT evidence
    manifest (`_compute_readiness` freshly, not a client-supplied digest) so
    a later evidence change makes this review stale automatically; see
    _check_separation_of_duties, which re-validates all of this again at
    decision-commit time rather than trusting this row indefinitely."""
    if not payload.note.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A review note is required")
    project = _get_owned_project_or_404(db, tenant_id, project_id)
    membership = _require_decision_authority(db, project_id, user, mfa_verified)
    occurrence = _get_occurrence_or_404(db, project_id, occurrence_id)
    readiness = _compute_readiness(db, project, occurrence)

    review = CompensatingReview(
        tenant_id=tenant_id,
        project_id=project_id,
        occurrence_id=occurrence.id,
        reviewer_user_id=membership.user_id,
        manifest_digest=readiness["manifest_digest"],
        note=payload.note,
    )
    db.add(review)
    db.flush()
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            project_id=project.id,
            occurrence_id=occurrence.id,
            actor_user_id=membership.user_id,
            event_type="compensating_review_recorded",
            detail={"review_id": review.id},
            sequence=_next_audit_sequence(db, project.id),
        )
    )
    db.commit()
    db.refresh(review)
    return CompensatingReviewOut.model_validate(review)
