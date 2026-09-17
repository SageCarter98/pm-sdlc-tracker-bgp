from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, require_role
from app.integrity import take_checkpoint, verify_integrity
from app.models import IntegrityCheckpoint, IntegrityIncident, Membership, Role
from app.routers.projects import _get_owned_project_or_404

router = APIRouter(tags=["integrity"])


class CheckpointOut(BaseModel):
    id: str
    project_id: str
    from_sequence: int | None
    to_sequence: int
    event_count: int
    chain_digest: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    id: str
    project_id: str
    detail: dict
    status: str
    detected_at: datetime
    resolved_at: datetime | None
    resolved_by_user_id: str | None
    resolution_note: str | None

    model_config = {"from_attributes": True}


class VerifyResponse(BaseModel):
    ok: bool
    checked_checkpoints: int
    incident: IncidentOut | None


class ResolveIncidentRequest(BaseModel):
    resolution_note: str


@router.post(
    "/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoint",
    response_model=CheckpointOut | None,
    status_code=status.HTTP_201_CREATED,
)
def create_checkpoint(
    tenant_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> CheckpointOut | None:
    """REQ-026: 'defined custody and verification frequency' -- this is the
    custody action (fold new audit events into a new unmodifiable
    checkpoint). This prototype has no scheduler; running it on a real
    cadence (see TRACKER.md) is an operational follow-up, not built here."""
    _get_owned_project_or_404(db, tenant_id, project_id)
    checkpoint = take_checkpoint(db, tenant_id, project_id)
    return CheckpointOut.model_validate(checkpoint) if checkpoint else None


@router.post("/orgs/{tenant_id}/projects/{project_id}/integrity/verify", response_model=VerifyResponse)
def run_verification(
    tenant_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> VerifyResponse:
    """REQ-026's verification half. On failure this also satisfies REQ-027's
    'trigger incident handling' -- see the IntegrityIncident this returns,
    and app/routers/decisions.py for how an open one blocks new decisions."""
    _get_owned_project_or_404(db, tenant_id, project_id)
    result = verify_integrity(db, tenant_id, project_id)
    return VerifyResponse(
        ok=result["ok"],
        checked_checkpoints=result["checked_checkpoints"],
        incident=IncidentOut.model_validate(result["incident"]) if result["incident"] else None,
    )


@router.get("/orgs/{tenant_id}/projects/{project_id}/integrity/checkpoints", response_model=list[CheckpointOut])
def list_checkpoints(
    tenant_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(get_active_membership),
) -> list[IntegrityCheckpoint]:
    _get_owned_project_or_404(db, tenant_id, project_id)
    return (
        db.query(IntegrityCheckpoint)
        .filter(IntegrityCheckpoint.project_id == project_id)
        .order_by(IntegrityCheckpoint.to_sequence)
        .all()
    )


@router.get("/orgs/{tenant_id}/projects/{project_id}/integrity/incidents", response_model=list[IncidentOut])
def list_incidents(
    tenant_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(get_active_membership),
) -> list[IntegrityIncident]:
    _get_owned_project_or_404(db, tenant_id, project_id)
    return (
        db.query(IntegrityIncident)
        .filter(IntegrityIncident.project_id == project_id)
        .order_by(IntegrityIncident.detected_at)
        .all()
    )


@router.post("/orgs/{tenant_id}/integrity/incidents/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(
    tenant_id: str,
    incident_id: str,
    payload: ResolveIncidentRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> IncidentOut:
    """No 'security lead' platform role exists yet (blueprint Sec.2's table
    doesn't define one) -- resolution is scoped to tenant_administrator for
    now, with a mandatory note, as the closest fit. Revisit if/when a
    dedicated assurance/security role is added."""
    if not payload.resolution_note.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A resolution note is required")

    incident = (
        db.query(IntegrityIncident)
        .filter(IntegrityIncident.id == incident_id, IntegrityIncident.tenant_id == tenant_id)
        .one_or_none()
    )
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    if incident.status == "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already resolved")

    incident.status = "resolved"
    incident.resolved_by_user_id = membership.user_id
    incident.resolution_note = payload.resolution_note
    incident.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incident)
    return IncidentOut.model_validate(incident)
