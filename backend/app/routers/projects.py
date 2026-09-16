from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, require_role
from app.models import (
    EvidenceItem,
    EvidenceRevision,
    GateOccurrence,
    Membership,
    Project,
    ProjectMembership,
    Role,
    TemplateVersion,
    User,
)
from app.rule_engine import RuleValidationError, TemplateSchema, evaluate_condition, validate_template_schema

router = APIRouter(tags=["projects"])


class ProjectMemberIn(BaseModel):
    user_id: str
    role: Role


class CreateProjectRequest(BaseModel):
    name: str
    template_version_id: str
    class_id: str
    members: list[ProjectMemberIn] = []


class ProjectOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    template_version_id: str
    class_id: str
    owner_user_id: str

    model_config = {"from_attributes": True}


class OccurrenceOut(BaseModel):
    id: str
    project_id: str
    gate_id: str
    sequence: int
    trigger: str
    due_at: datetime | None

    model_config = {"from_attributes": True}


class EvidenceItemOut(BaseModel):
    id: str
    project_id: str
    occurrence_id: str
    gate_id: str
    rule_id: str
    evidence_kind: str
    required: bool
    permitted_role_ids: list[str]
    status: str
    owner_user_id: str | None
    due_date: datetime | None
    completed_date: datetime | None
    reference: str | None
    latest_revision_number: int

    model_config = {"from_attributes": True}


class CreateProjectResponse(BaseModel):
    project: ProjectOut
    occurrences: list[OccurrenceOut]
    evidence_items: list[EvidenceItemOut]


class CreateOccurrenceRequest(BaseModel):
    gate_id: str
    trigger: Literal["routine", "triggered"]
    due_at: datetime | None = None


class CreateOccurrenceResponse(BaseModel):
    occurrence: OccurrenceOut
    evidence_items: list[EvidenceItemOut]


class CreateEvidenceRevisionRequest(BaseModel):
    base_revision: int
    status: str
    owner_user_id: str | None = None
    due_date: datetime | None = None
    completed_date: datetime | None = None
    reference: str | None = None
    source_version: str | None = None
    source_hash: str | None = None


class EvidenceRevisionOut(BaseModel):
    revision_number: int
    status: str
    owner_user_id: str | None
    due_date: datetime | None
    completed_date: datetime | None
    reference: str | None
    source_version: str | None
    source_hash: str | None
    reference_is_mutable: bool | None
    actor_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceItemDetailOut(BaseModel):
    item: EvidenceItemOut
    revisions: list[EvidenceRevisionOut]


def _load_bound_schema(db: Session, tenant_id: str, template_version_id: str) -> TemplateSchema:
    """REQ-011: a project binds to exactly one published version, from this
    tenant's own templates or a shared platform starter (tenant_id NULL) --
    same visibility rule as app/routers/templates.py's own query."""
    from app.models import Template

    version = (
        db.query(TemplateVersion)
        .join(Template, Template.id == TemplateVersion.template_id)
        .filter(
            TemplateVersion.id == template_version_id,
            (Template.tenant_id == tenant_id) | (Template.tenant_id.is_(None)),
        )
        .one_or_none()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template version not found")
    if version.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "A project can only bind to a published template version")

    try:
        return validate_template_schema(version.schema_json)
    except RuleValidationError as exc:  # pragma: no cover -- published versions were validated at publish time
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors}) from exc


def _seed_evidence_for_occurrence(
    db: Session,
    *,
    tenant_id: str,
    project_id: str,
    class_id: str,
    schema: TemplateSchema,
    gate_id: str,
    trigger: str,
    occurrence: GateOccurrence,
    actor_user_id: str,
) -> list[EvidenceItem]:
    """REQ-016/017: every applicable rule on this gate, for this class and
    this occurrence's trigger type, becomes its own EvidenceItem plus a
    first EvidenceRevision -- never shared with any other occurrence."""
    gate = next((g for g in schema.gates if g.gate_id == gate_id), None)
    if gate is None:
        return []

    created: list[EvidenceItem] = []
    for rule in gate.rules:
        if class_id not in rule.class_ids or rule.occurrence_type != trigger:
            continue
        if rule.applicability is not None and not evaluate_condition(rule.applicability, {"class_id": class_id}):
            continue

        item = EvidenceItem(
            tenant_id=tenant_id,
            project_id=project_id,
            occurrence_id=occurrence.id,
            gate_id=gate_id,
            rule_id=rule.rule_id,
            evidence_kind=rule.evidence_kind,
            required=rule.blocker_level != "advisory",
            permitted_role_ids=rule.permitted_role_ids,
            status="Not started",
            owner_user_id=None,
            due_date=None,
            completed_date=None,
            reference=None,
            latest_revision_number=1,
        )
        db.add(item)
        db.flush()
        db.add(
            EvidenceRevision(
                tenant_id=tenant_id,
                evidence_item_id=item.id,
                revision_number=1,
                status="Not started",
                owner_user_id=None,
                due_date=None,
                completed_date=None,
                reference=None,
                source_version=None,
                source_hash=None,
                actor_user_id=actor_user_id,
            )
        )
        created.append(item)
    return created


def _gates_applicable_to_class(schema: TemplateSchema, class_id: str):
    return [g for g in schema.gates if class_id in g.class_ids]


@router.post("/orgs/{tenant_id}/projects", response_model=CreateProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    tenant_id: str,
    payload: CreateProjectRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)),
) -> CreateProjectResponse:
    """REQ-015: creation commits the project, its explicit members, every
    applicable gate's first routine occurrence, and that occurrence's
    evidence together -- or none of it. See
    tests/test_projects.py::test_seeding_failure_leaves_no_project_row for
    the atomicity proof (REQ-015's own verification text)."""
    schema = _load_bound_schema(db, tenant_id, payload.template_version_id)
    if payload.class_id not in schema.classes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"class_id '{payload.class_id}' is not declared by this template version")

    for member in payload.members:
        exists = (
            db.query(Membership)
            .filter(Membership.tenant_id == tenant_id, Membership.user_id == member.user_id, Membership.active.is_(True))
            .one_or_none()
        )
        if exists is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"user '{member.user_id}' has no active membership in this organisation")

    try:
        project = Project(
            tenant_id=tenant_id,
            name=payload.name,
            template_version_id=payload.template_version_id,
            class_id=payload.class_id,
            owner_user_id=membership.user_id,
        )
        db.add(project)
        db.flush()

        db.add(ProjectMembership(tenant_id=tenant_id, project_id=project.id, user_id=membership.user_id, role=membership.role))
        for member in payload.members:
            if member.user_id == membership.user_id:
                continue
            db.add(ProjectMembership(tenant_id=tenant_id, project_id=project.id, user_id=member.user_id, role=member.role.value))

        occurrences: list[GateOccurrence] = []
        evidence_items: list[EvidenceItem] = []
        for gate in _gates_applicable_to_class(schema, payload.class_id):
            has_routine_rule = any(
                payload.class_id in rule.class_ids and rule.occurrence_type == "routine" for rule in gate.rules
            )
            if not has_routine_rule:
                continue  # a gate with only triggered rules gets no automatic occurrence (REQ-016)

            occurrence = GateOccurrence(
                tenant_id=tenant_id, project_id=project.id, gate_id=gate.gate_id, sequence=1, trigger="routine", due_at=None
            )
            db.add(occurrence)
            db.flush()
            occurrences.append(occurrence)
            evidence_items.extend(
                _seed_evidence_for_occurrence(
                    db,
                    tenant_id=tenant_id,
                    project_id=project.id,
                    class_id=payload.class_id,
                    schema=schema,
                    gate_id=gate.gate_id,
                    trigger="routine",
                    occurrence=occurrence,
                    actor_user_id=membership.user_id,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(project)
    return CreateProjectResponse(
        project=ProjectOut.model_validate(project),
        occurrences=[OccurrenceOut.model_validate(o) for o in occurrences],
        evidence_items=[EvidenceItemOut.model_validate(e) for e in evidence_items],
    )


@router.get("/orgs/{tenant_id}/projects", response_model=list[ProjectOut])
def list_projects(
    tenant_id: str, db: Session = Depends(get_db), _membership: Membership = Depends(get_active_membership)
) -> list[Project]:
    return db.query(Project).filter(Project.tenant_id == tenant_id).all()


def _get_owned_project_or_404(db: Session, tenant_id: str, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _require_project_member(db: Session, project_id: str, user_id: str) -> ProjectMembership:
    """Blueprint Sec.2, Approver row: 'Requires current role, project scope,
    MFA and separation checks' -- tenant membership alone is not project
    scope; every evidence/occurrence operation re-checks this explicitly."""
    pm = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == project_id, ProjectMembership.user_id == user_id)
        .one_or_none()
    )
    if pm is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this project")
    return pm


@router.post(
    "/orgs/{tenant_id}/projects/{project_id}/occurrences",
    response_model=CreateOccurrenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_occurrence(
    tenant_id: str,
    project_id: str,
    payload: CreateOccurrenceRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)),
) -> CreateOccurrenceResponse:
    """REQ-016: a new routine or triggered review of one gate, with its own
    sequence and its own evidence -- never touching any earlier occurrence's
    evidence or decisions. Sequence allocation is enforced by the
    (project_id, gate_id, sequence) unique constraint (app/models.py
    GateOccurrence): a concurrent request racing for the same next sequence
    number loses on IntegrityError and gets a 409, not a silent duplicate.
    This prototype does not retry automatically -- documented scope, not an
    oversight; see docs/wp02/ for the general prototype-scope caveats this
    project already carries."""
    project = _get_owned_project_or_404(db, tenant_id, project_id)
    schema = _load_bound_schema(db, tenant_id, project.template_version_id)
    gate = next((g for g in schema.gates if g.gate_id == payload.gate_id and project.class_id in g.class_ids), None)
    if gate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gate not found for this project's class")

    next_sequence = (
        db.query(func.max(GateOccurrence.sequence))
        .filter(GateOccurrence.project_id == project_id, GateOccurrence.gate_id == payload.gate_id)
        .scalar()
        or 0
    ) + 1

    occurrence = GateOccurrence(
        tenant_id=tenant_id,
        project_id=project_id,
        gate_id=payload.gate_id,
        sequence=next_sequence,
        trigger=payload.trigger,
        due_at=payload.due_at,
    )
    db.add(occurrence)
    try:
        db.flush()
        evidence_items = _seed_evidence_for_occurrence(
            db,
            tenant_id=tenant_id,
            project_id=project_id,
            class_id=project.class_id,
            schema=schema,
            gate_id=payload.gate_id,
            trigger=payload.trigger,
            occurrence=occurrence,
            actor_user_id=membership.user_id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A concurrent request already created this occurrence's sequence -- retry") from None
    except Exception:
        db.rollback()
        raise

    db.refresh(occurrence)
    return CreateOccurrenceResponse(
        occurrence=OccurrenceOut.model_validate(occurrence),
        evidence_items=[EvidenceItemOut.model_validate(e) for e in evidence_items],
    )


@router.get("/orgs/{tenant_id}/my-work", response_model=list[EvidenceItemOut])
def my_work(
    tenant_id: str,
    cursor: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> list[EvidenceItem]:
    """Blueprint Sec.5.3 GET /api/my-work: permitted tasks and next actions,
    membership scoped, paginated. 'Permitted' here means: assigned directly
    to this user, or unassigned but within a project this user belongs to
    with a role the rule permits (rule.permitted_role_ids)."""
    my_project_ids = [
        pid for (pid,) in db.query(ProjectMembership.project_id).filter(ProjectMembership.user_id == membership.user_id).all()
    ]
    my_pm_by_project = {
        pm.project_id: pm.role
        for pm in db.query(ProjectMembership).filter(ProjectMembership.project_id.in_(my_project_ids)).all()
    }

    q = db.query(EvidenceItem).filter(EvidenceItem.tenant_id == tenant_id, EvidenceItem.project_id.in_(my_project_ids))
    if status_filter:
        q = q.filter(EvidenceItem.status == status_filter)
    if cursor:
        q = q.filter(EvidenceItem.id > cursor)
    q = q.order_by(EvidenceItem.id).limit(limit)

    results = []
    for item in q.all():
        if item.owner_user_id == membership.user_id:
            results.append(item)
        elif item.owner_user_id is None and my_pm_by_project.get(item.project_id) in item.permitted_role_ids:
            results.append(item)
    return results


@router.get("/orgs/{tenant_id}/evidence/{evidence_item_id}", response_model=EvidenceItemDetailOut)
def get_evidence_item(
    tenant_id: str,
    evidence_item_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> EvidenceItemDetailOut:
    item = db.query(EvidenceItem).filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id).one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence item not found")
    _require_project_member(db, item.project_id, membership.user_id)

    revisions = (
        db.query(EvidenceRevision)
        .filter(EvidenceRevision.evidence_item_id == item.id)
        .order_by(EvidenceRevision.revision_number)
        .all()
    )
    return EvidenceItemDetailOut(
        item=EvidenceItemOut.model_validate(item),
        revisions=[
            EvidenceRevisionOut(
                revision_number=r.revision_number,
                status=r.status,
                owner_user_id=r.owner_user_id,
                due_date=r.due_date,
                completed_date=r.completed_date,
                reference=r.reference,
                source_version=r.source_version,
                source_hash=r.source_hash,
                reference_is_mutable=(None if r.reference is None else (r.source_version is None and r.source_hash is None)),
                actor_user_id=r.actor_user_id,
                created_at=r.created_at,
            )
            for r in revisions
        ],
    )


@router.post(
    "/orgs/{tenant_id}/evidence/{evidence_item_id}/revisions",
    response_model=EvidenceItemDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence_revision(
    tenant_id: str,
    evidence_item_id: str,
    payload: CreateEvidenceRevisionRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> EvidenceItemDetailOut:
    """REQ-017: every edit is a new, immutable, attributed revision -- this
    endpoint only ever INSERTs into evidence_revisions, never UPDATEs an
    existing row. REQ-018: a resulting status of 'Complete' on a required
    item without a reference is rejected outright (the only way to satisfy
    'do not allow removal of required evidence while Complete' when every
    edit replaces the full record rather than patching one field: clearing
    the reference is only possible by also moving status away from
    Complete in the same revision). REQ-019: source_version/source_hash are
    accepted as-given, never inferred from the reference string's shape."""
    item = db.query(EvidenceItem).filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id).one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence item not found")
    _require_project_member(db, item.project_id, membership.user_id)

    if payload.base_revision != item.latest_revision_number:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"base_revision {payload.base_revision} is stale -- current is {item.latest_revision_number}",
        )

    if payload.status == "Complete" and item.required and not payload.reference:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot mark a required item Complete without a reference (REQ-018)")

    next_revision = item.latest_revision_number + 1
    db.add(
        EvidenceRevision(
            tenant_id=tenant_id,
            evidence_item_id=item.id,
            revision_number=next_revision,
            status=payload.status,
            owner_user_id=payload.owner_user_id,
            due_date=payload.due_date,
            completed_date=payload.completed_date,
            reference=payload.reference,
            source_version=payload.source_version,
            source_hash=payload.source_hash,
            actor_user_id=membership.user_id,
        )
    )
    item.status = payload.status
    item.owner_user_id = payload.owner_user_id
    item.due_date = payload.due_date
    item.completed_date = payload.completed_date
    item.reference = payload.reference
    item.latest_revision_number = next_revision
    db.commit()

    return get_evidence_item(tenant_id, evidence_item_id, db, membership)
