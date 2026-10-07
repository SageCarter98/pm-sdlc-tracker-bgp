from datetime import datetime, timezone
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
)
from app.rule_engine import (
    _LEGACY_SATISFYING_STATUS,
    RuleValidationError,
    StatusDefinition,
    TemplateSchema,
    evaluate_condition,
    status_satisfies,
    validate_template_schema,
)

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
    blocker_level: str
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
    # An ISO-8601 string, not a datetime: rule_engine._compare compares
    # date facts as text, and a datetime against a string threshold would
    # raise TypeError and fail closed every time.
    as_at: str | None = None,
) -> list[EvidenceItem]:
    """REQ-016/017: every applicable rule on this gate, for this class and
    this occurrence's trigger type, becomes its own EvidenceItem plus a
    first EvidenceRevision -- never shared with any other occurrence.

    `as_at` is DEC07's "supplied 'as at' timestamp": applicability may now
    compare dates (gte/lte), and a rule must never read the clock itself,
    so the caller passes the moment this seeding represents. Omitted, a
    date-comparing applicability rule fails closed like any unknown
    fact."""
    gate = next((g for g in schema.gates if g.gate_id == gate_id), None)
    if gate is None:
        return []

    created: list[EvidenceItem] = []
    for rule in gate.rules:
        if class_id not in rule.class_ids or rule.occurrence_type != trigger:
            continue
        if rule.applicability is not None and not evaluate_condition(
            rule.applicability, {"class_id": class_id}, as_at=as_at
        ):
            continue

        item = EvidenceItem(
            tenant_id=tenant_id,
            project_id=project_id,
            occurrence_id=occurrence.id,
            gate_id=gate_id,
            rule_id=rule.rule_id,
            evidence_kind=rule.evidence_kind,
            required=rule.blocker_level != "advisory",
            blocker_level=rule.blocker_level,
            permitted_role_ids=rule.permitted_role_ids,
            status=schema.initial_status(),
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
                status=schema.initial_status(),
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
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"class_id '{payload.class_id}' is not declared by this template version",
        )

    for member in payload.members:
        exists = (
            db.query(Membership)
            .filter(
                Membership.tenant_id == tenant_id, Membership.user_id == member.user_id, Membership.active.is_(True)
            )
            .one_or_none()
        )
        if exists is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"user '{member.user_id}' has no active membership in this organisation",
            )

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

        db.add(
            ProjectMembership(
                tenant_id=tenant_id, project_id=project.id, user_id=membership.user_id, role=membership.role
            )
        )
        for member in payload.members:
            if member.user_id == membership.user_id:
                continue
            db.add(
                ProjectMembership(
                    tenant_id=tenant_id, project_id=project.id, user_id=member.user_id, role=member.role.value
                )
            )

        occurrences: list[GateOccurrence] = []
        evidence_items: list[EvidenceItem] = []
        for gate in _gates_applicable_to_class(schema, payload.class_id):
            has_routine_rule = any(
                payload.class_id in rule.class_ids and rule.occurrence_type == "routine" for rule in gate.rules
            )
            if not has_routine_rule:
                continue  # a gate with only triggered rules gets no automatic occurrence (REQ-016)

            occurrence = GateOccurrence(
                tenant_id=tenant_id,
                project_id=project.id,
                gate_id=gate.gate_id,
                sequence=1,
                trigger="routine",
                due_at=None,
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
                    as_at=datetime.now(timezone.utc).isoformat(),
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    # No db.refresh() -- see app/db.py's SessionLocal docstring
    # (expire_on_commit=False): every field here was already set in Python
    # before commit, and projects is RLS-protected, so a post-commit
    # refresh would run with no tenant context left and raise.
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


@router.get("/orgs/{tenant_id}/projects/{project_id}/occurrences", response_model=list[OccurrenceOut])
def list_occurrences(
    tenant_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> list[GateOccurrence]:
    """Return the project-scoped gate occurrences in display order.

    The webapp gate dashboard calls this function directly so it shares the
    same project-membership and tenant scoping as the JSON API rather than
    reimplementing an occurrence query in the page route.
    """
    _get_owned_project_or_404(db, tenant_id, project_id)
    _require_project_member(db, project_id, membership.user_id)
    return (
        db.query(GateOccurrence)
        .filter(GateOccurrence.tenant_id == tenant_id, GateOccurrence.project_id == project_id)
        .order_by(GateOccurrence.gate_id, GateOccurrence.sequence)
        .all()
    )


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


def _require_permitted_to_attest(
    item: EvidenceItem, pm: ProjectMembership, membership: Membership, schema: TemplateSchema
) -> None:
    """REQ-032/TST-032: `permitted_role_ids` says WHO MAY ATTEST an item, and
    this is where that is enforced.

    It was previously declared in the template, validated against the
    schema's declared roles (rule_engine's "references undeclared role(s)"),
    consulted as a my-work visibility filter -- and then never checked when a
    revision was actually submitted, so any project member could mark a hard,
    required, approver-only item Complete. Probed and confirmed 2026-10-04
    before this fix. Separation of duties for DECISIONS is a different
    control (decisions.py's _check_separation_of_duties); this is about who
    may supply evidence, not who may approve a gate.

    Two exemptions, owner-approved 2026-10-04 and each pinned by its own test
    in test_permitted_role_enforcement.py so neither widens silently:

    1. The explicitly assigned owner always may -- assignment is itself an
       authorised act by someone who had the authority to make it, and the
       assignee is exactly the person being asked to act.
    2. A tenant administrator always may -- they already administer the
       tenant, and this product's assignment workflow has an admin writing
       the first revision in order to set an owner at all.

    Fails closed: an item declaring no permitted roles admits nobody but
    those two exemptions. The schema requires at least one
    (`permitted_role_ids: list[str] = Field(min_length=1)`), so that state is
    unreachable through validation -- but a legacy or hand-edited row must
    not become a free-for-all."""
    if item.owner_user_id is not None and item.owner_user_id == membership.user_id:
        return
    if membership.role == Role.TENANT_ADMINISTRATOR:
        return

    declared = item.permitted_role_ids or []
    # At vocabulary 4 a declared role carries its own `attests` capability,
    # so being named in permitted_role_ids is necessary but no longer
    # sufficient -- the template must also say the role attests at all.
    # Below 4 this is bit-identical: role_lookup() synthesises a definition
    # for every bare string and RoleDefinition.attests defaults True, so no
    # vocabulary 1-3 template can lose an attester here. Pinned by
    # test_role_vocabulary_backcompat.py and by the vocabulary-1 cases in
    # this function's own suite.
    definition = schema.role_lookup().get(pm.role)
    if definition is not None and definition.attests and pm.role in declared:
        return

    # The restriction is only enforceable against roles the platform can
    # actually ASSIGN. Project membership roles come from the fixed `Role`
    # enum, NOT from the bound template's declared `roles` -- so a framework
    # naming its own roles (agile.json/agile.v3.json declare product_owner,
    # developer, facilitator; none assignable) has permitted_role_ids that no
    # project member's role can ever match. Enforcing strictly there would
    # make every item in such a framework attestable only by a tenant
    # administrator or the assigned owner, which is not a narrowing this
    # change is entitled to make.
    #
    # So: enforce where the declared roles are assignable, and fall back to
    # membership-only where none of them is -- deliberately, visibly, and
    # recorded as its own defect-register row ("declared role vocabulary is
    # not honoured"), which is the DEC07 status/outcome vocabulary gap in a
    # different field and needs the same indirection treatment to fix
    # properly. This fallback is the one place this control fails open; it is
    # pinned by test_an_unassignable_role_vocabulary_falls_back_to_membership.
    #
    # At vocabulary 4 that indirection EXISTS: declared roles are assignable
    # project roles (see the member-role validation in create_project), so a
    # custom-role framework is no longer locked out and the fallback is
    # neither needed nor wanted -- a role the rule does not name must be
    # refused there rather than waved through (spec G6).
    if schema.vocabulary_version < 4 and not (set(declared) & {role.value for role in Role}):
        return

    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"your project role '{pm.role}' is not permitted to submit evidence for this item "
        f"(permitted roles: {sorted(declared)})",
    )


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
            as_at=datetime.now(timezone.utc).isoformat(),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A concurrent request already created this occurrence's sequence -- retry"
        ) from None
    except Exception:
        db.rollback()
        raise

    # No db.refresh() -- see create_project above, same reasoning
    # (gate_occurrences is RLS-protected too).
    return CreateOccurrenceResponse(
        occurrence=OccurrenceOut.model_validate(occurrence),
        evidence_items=[EvidenceItemOut.model_validate(e) for e in evidence_items],
    )


class MyWorkItemOut(BaseModel):
    """REQ-032: 'role-specific My work with project, reason, deadline,
    state and a direct action.' Wraps EvidenceItemOut with the three
    fields that requirement names beyond what the item already carries
    (deadline = due_date, state = status -- both already on the item)."""

    item: EvidenceItemOut
    project_id: str
    project_name: str
    reason: str
    due_date: datetime | None
    status: str
    direct_action: str


@router.get("/orgs/{tenant_id}/my-work", response_model=list[MyWorkItemOut])
def my_work(
    tenant_id: str,
    cursor: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> list[MyWorkItemOut]:
    """Blueprint Sec.5.3 GET /api/my-work: permitted tasks and next actions,
    membership scoped, paginated. 'Permitted' here means: assigned directly
    to this user, or unassigned but within a project this user belongs to
    with a role the rule permits (rule.permitted_role_ids). TST-032:
    'Each persona finds their assigned action while unrelated assignments
    stay hidden' -- the query below is the hiding half; `reason` and
    `direct_action` below are the finding half, so a future frontend (none
    exists yet, DEC04) doesn't have to re-derive 'why is this mine' or
    'what do I do about it' from raw evidence-item fields itself."""
    my_project_ids = [
        pid
        for (pid,) in db.query(ProjectMembership.project_id)
        .filter(ProjectMembership.user_id == membership.user_id)
        .all()
    ]
    my_pm_by_project = {
        pm.project_id: pm.role
        for pm in db.query(ProjectMembership).filter(ProjectMembership.project_id.in_(my_project_ids)).all()
    }
    projects_by_id = {p.id: p for p in db.query(Project).filter(Project.id.in_(my_project_ids)).all()}
    project_names = {pid: p.name for pid, p in projects_by_id.items()}

    # Deferred, because app/routers/decisions.py imports FROM this module
    # at import time (`_load_bound_schema` and friends), so a module-level
    # import here would be circular. Imported rather than reimplemented on
    # purpose: readiness and this endpoint disagreeing about what
    # "satisfied" means is exactly the defect being fixed here.
    from app.routers.decisions import _conditions_hold, _evidence_facts

    # DEC07: my_work spans projects, so resolve each item's status against
    # ITS OWN bound template version. One schema would silently apply one
    # framework's vocabulary to another's items.
    schema_by_project: dict[str, TemplateSchema] = {}
    status_lookup_by_project: dict[str, dict[str, StatusDefinition]] = {}
    facts_by_occurrence: dict[str, dict[str, str]] = {}

    def _schema_for(item: EvidenceItem) -> TemplateSchema:
        if item.project_id not in schema_by_project:
            # Reuse the Project row already loaded above (project_names'
            # source) instead of re-querying it per item.
            project_row = projects_by_id[item.project_id]
            schema_by_project[item.project_id] = _load_bound_schema(db, tenant_id, project_row.template_version_id)
        return schema_by_project[item.project_id]

    def _status_lookup_for(item: EvidenceItem) -> dict[str, StatusDefinition]:
        # Mirrors schema_by_project: normalise once per project, not once
        # per item -- status_lookup() rebuilds the whole dict from the
        # schema's declared statuses every call.
        if item.project_id not in status_lookup_by_project:
            status_lookup_by_project[item.project_id] = _schema_for(item).status_lookup()
        return status_lookup_by_project[item.project_id]

    def _satisfies(item: EvidenceItem) -> bool:
        """The SAME question `_compute_readiness` answers, asked the same
        way -- `status_satisfies` plus the rule's condition tree. It
        deliberately does NOT look for a valid ExceptionRecord, so a
        `requires_exception` status reads as unsatisfied here; that is
        fail-closed and only ever understates what the owner has left to
        do. Claiming satisfaction readiness disagrees with would be the
        fail-open direction: telling the assigned owner to stand down on
        the very item blocking the gate."""
        schema = _schema_for(item)
        if not status_satisfies(_status_lookup_for(item).get(item.status)):
            return False
        # Condition evaluation is vocabulary 3 only (G6), so for every
        # v1/v2 project this returns above without the sibling query below.
        if schema.vocabulary_version < 3:
            return True
        rules_by_id = {rule.rule_id: rule for gate in schema.gates for rule in gate.rules}
        if item.occurrence_id not in facts_by_occurrence:
            siblings = db.query(EvidenceItem).filter(EvidenceItem.occurrence_id == item.occurrence_id).all()
            facts_by_occurrence[item.occurrence_id] = _evidence_facts(siblings, _status_lookup_for(item))
        return _conditions_hold(item, rules_by_id, facts_by_occurrence[item.occurrence_id], True)

    def _pending_exception(item: EvidenceItem) -> bool:
        """True when the item's status is one the template says satisfies
        only with an approved exception -- so the action text can say that
        instead of either claiming done or demanding a new revision."""
        definition = _status_lookup_for(item).get(item.status)
        return definition is not None and definition.satisfies and definition.requires_exception

    q = db.query(EvidenceItem).filter(EvidenceItem.tenant_id == tenant_id, EvidenceItem.project_id.in_(my_project_ids))
    if status_filter:
        q = q.filter(EvidenceItem.status == status_filter)
    if cursor:
        q = q.filter(EvidenceItem.id > cursor)
    q = q.order_by(EvidenceItem.id).limit(limit)

    results: list[MyWorkItemOut] = []
    for item in q.all():
        if item.owner_user_id == membership.user_id:
            reason = "You are the assigned owner of this evidence item."
        elif item.owner_user_id is None and my_pm_by_project.get(item.project_id) in item.permitted_role_ids:
            reason = f"Unassigned, and your role ('{my_pm_by_project.get(item.project_id)}') is permitted to act on it."
        else:
            continue

        if _satisfies(item):
            direct_action = f"No action needed -- already '{item.status}'."
        elif _pending_exception(item):
            direct_action = (
                f"'{item.status}' counts only once an exception is approved for this item -- "
                f"it still blocks until then."
            )
        else:
            direct_action = (
                f"POST /orgs/{tenant_id}/evidence/{item.id}/revisions with a satisfying status and a reference"
            )

        results.append(
            MyWorkItemOut(
                item=EvidenceItemOut.model_validate(item),
                project_id=item.project_id,
                project_name=project_names.get(item.project_id, ""),
                reason=reason,
                due_date=item.due_date,
                status=item.status,
                direct_action=direct_action,
            )
        )
    return results


@router.get("/orgs/{tenant_id}/evidence/{evidence_item_id}", response_model=EvidenceItemDetailOut)
def get_evidence_item(
    tenant_id: str,
    evidence_item_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> EvidenceItemDetailOut:
    item = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id)
        .one_or_none()
    )
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
                reference_is_mutable=(
                    None if r.reference is None else (r.source_version is None and r.source_hash is None)
                ),
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
    accepted as-given, never inferred from the reference string's shape.

    BGP-F03: the item row is locked FOR UPDATE (a no-op on SQLite) before
    the base_revision check -- the same fixed lock order (evidence rows,
    single-row here) that decisions.py's _compute_readiness(lock=True)
    uses for its multi-row lock, so the two can only ever wait on each
    other, never deadlock. This closes the read-then-write race for
    base_revision itself (two concurrent submissions with the same
    base_revision now serialise: the second sees the FIRST's committed
    latest_revision_number once it acquires the lock, and its own
    base_revision check -- now correctly comparing against fresh data --
    rejects it with the existing 409, before it ever reaches the insert)
    and, together with decisions.py's matching lock, closes the
    'evidence changed between a decision's readiness read and its commit'
    race from the other side."""
    item = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id)
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence item not found")
    pm = _require_project_member(db, item.project_id, membership.user_id)
    # Loaded BEFORE the attest check rather than after the 409 below: the
    # check now resolves declared role capability through the bound
    # template, and its 403 must keep preceding the staleness 409 it has
    # always preceded.
    project_row = db.query(Project).filter(Project.id == item.project_id).one()
    schema = _load_bound_schema(db, tenant_id, project_row.template_version_id)
    _require_permitted_to_attest(item, pm, membership, schema)

    if payload.base_revision != item.latest_revision_number:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"base_revision {payload.base_revision} is stale -- current is {item.latest_revision_number}",
        )

    status_lookup = schema.status_lookup()

    definition = status_lookup.get(payload.status)
    if definition is None and schema.vocabulary_version >= 3:
        # Spec Sec.4.6 rejects a status the bound template never declared,
        # and Sec.7 states the containment for it explicitly: "it applies
        # only to projects bound to a v3 template version, of which there
        # are none until step 3. No existing caller can be broken by steps
        # 1-2." This gate is that containment. Without it, every v1/v2
        # caller sending an arbitrary status string starts getting a 422 --
        # an undocumented G6 breach the spec specifically ruled out, and a
        # pointless one, because an undeclared status already fails closed
        # in readiness (it can never satisfy) rather than being trusted.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"status '{payload.status}' is not declared by this project's template version "
            f"(declared: {sorted(status_lookup)})",
        )

    # REQ-018, keyed on what the status MEANS rather than on the literal
    # "Complete" -- except for the one case vocabulary indirection cannot
    # cover without becoming the v3 gate above: a v1/v2 template that never
    # declares "Complete" resolves it to no definition, so
    # `definition.satisfies` has nothing to go on. Pre-DEC07 the check was
    # an unconditional `payload.status == "Complete"` that ignored the
    # template entirely, so it DID demand a reference for that literal
    # regardless of declaration. The second clause below restores exactly
    # that, and only below vocabulary 3 -- at v3+ the gate above has already
    # rejected an undeclared status outright, so `definition.satisfies` is
    # the sole source of truth there.
    needs_reference = (definition is not None and definition.satisfies) or (
        schema.vocabulary_version < 3 and payload.status == _LEGACY_SATISFYING_STATUS
    )
    if needs_reference and item.required and not payload.reference:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot mark a required item Complete without a reference (REQ-018)"
        )

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
    try:
        db.flush()
    except IntegrityError:
        # BGP-F03 defense-in-depth: with the lock above this should already
        # be unreachable in practice (the second writer's base_revision
        # check now runs against fresh data and rejects it first) -- kept
        # so a genuine collision on uq_evidence_revision_item_number is
        # still a clean, deterministic 409, never a bare 500, as the
        # required correction ('deterministic outcomes, not unhandled
        # database errors') asks for generally, not only for decisions.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"base_revision {payload.base_revision} is stale -- current is {item.latest_revision_number}",
        )

    # Built from a query issued BEFORE db.commit() below, not
    # get_evidence_item's usual post-request re-query: SET LOCAL
    # app.tenant_id only lasts for this transaction, so a query issued
    # after commit would run under RLS with no context and silently see
    # nothing -- exactly what get_evidence_item's own trailing call used to
    # do here (found 2026-09-20, WP11: the first thing that ever drove this
    # endpoint through a real browser instead of raw JSON/SQLite hit it).
    # db.flush() above already made the new revision visible to this same-
    # transaction query without needing a commit first.
    revisions = (
        db.query(EvidenceRevision)
        .filter(EvidenceRevision.evidence_item_id == item.id)
        .order_by(EvidenceRevision.revision_number)
        .all()
    )
    result = EvidenceItemDetailOut(
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
                reference_is_mutable=(
                    None if r.reference is None else (r.source_version is None and r.source_hash is None)
                ),
                actor_user_id=r.actor_user_id,
                created_at=r.created_at,
            )
            for r in revisions
        ],
    )
    db.commit()
    return result
