from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, require_role
from app.models import Membership, Role, Template, TemplateVersion
from app.rule_engine import RuleValidationError, validate_template_schema

router = APIRouter(prefix="/orgs/{tenant_id}/templates", tags=["templates"])


class CreateTemplateRequest(BaseModel):
    name: str
    schema_json: dict | None = None  # None => blank starter draft (REQ-012)


class ImportTemplateRequest(BaseModel):
    name: str
    schema_json: dict


class UpdateDraftRequest(BaseModel):
    schema_json: dict


class TemplateVersionOut(BaseModel):
    id: str
    template_id: str
    version_number: int
    status: str
    schema_json: dict

    model_config = {"from_attributes": True}


class TemplateOut(BaseModel):
    id: str
    tenant_id: str | None
    name: str

    model_config = {"from_attributes": True}


_BLANK_SCHEMA = {
    "schema_version": 1,
    "tracks": ["Delivery"],
    "classes": ["Draft"],
    "roles": ["contributor", "approver"],
    "statuses": ["Not started", "Complete"],
    "decision_outcomes": ["Approve", "Hold"],
    "gates": [
        {"gate_id": "G1", "name": "Intake", "sequence": 1, "class_ids": ["Draft"], "rules": []}
    ],
}


def _visible_templates_query(db: Session, tenant_id: str):
    """App-level tenant scoping, independent of RLS: own tenant's templates
    plus shared platform starters (tenant_id IS NULL). RLS (WP04/WP05
    migrations) enforces the same rule again at the database layer against
    Postgres; this filter is what actually runs in the SQLite test suite,
    which has no RLS to fall back on."""
    return db.query(Template).filter(or_(Template.tenant_id == tenant_id, Template.tenant_id.is_(None)))


def _get_owned_template_or_404(db: Session, tenant_id: str, template_id: str) -> Template:
    template = _visible_templates_query(db, tenant_id).filter(Template.id == template_id).one_or_none()
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return template


def _require_own_template(template: Template, tenant_id: str) -> None:
    """Shared starters (tenant_id None) are readable/forkable by anyone but
    not directly editable/publishable by a tenant that doesn't own them."""
    if template.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot modify a template this organisation does not own")


@router.get("", response_model=list[TemplateOut])
def list_templates(
    tenant_id: str, db: Session = Depends(get_db), _membership: Membership = Depends(get_active_membership)
) -> list[Template]:
    return _visible_templates_query(db, tenant_id).all()


@router.post("", response_model=TemplateVersionOut, status_code=status.HTTP_201_CREATED)
def create_template(
    tenant_id: str,
    payload: CreateTemplateRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)),
) -> TemplateVersion:
    """REQ-012: blank creation. A JSON body is accepted here too, but this
    is the 'guided authoring'/blank path -- AC08 requires a tenant can reach
    the same result without ever hand-editing JSON, which the blank default
    below satisfies."""
    schema_data = payload.schema_json or _BLANK_SCHEMA
    try:
        validate_template_schema(schema_data)
    except RuleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors}) from exc

    template = Template(tenant_id=tenant_id, name=payload.name)
    db.add(template)
    db.flush()
    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        schema_json=schema_data,
        status="draft",
        created_by_user_id=membership.user_id,
    )
    db.add(version)
    db.commit()
    # No db.refresh() -- see app/db.py's SessionLocal docstring
    # (expire_on_commit=False): every field here was already set in Python
    # before commit, and template_versions is RLS-protected, so a
    # post-commit refresh would run with no tenant context left and raise.
    return version


@router.post("/import", response_model=TemplateVersionOut, status_code=status.HTTP_201_CREATED)
def import_template(
    tenant_id: str,
    payload: ImportTemplateRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)),
) -> TemplateVersion:
    """REQ-012: schema-validated JSON import; malformed input explains the
    failing field rather than a single opaque failure."""
    try:
        validate_template_schema(payload.schema_json)
    except RuleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors}) from exc

    template = Template(tenant_id=tenant_id, name=payload.name)
    db.add(template)
    db.flush()
    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        schema_json=payload.schema_json,
        status="draft",
        created_by_user_id=membership.user_id,
    )
    db.add(version)
    db.commit()
    # No db.refresh() -- see create_template above, same reasoning.
    return version


@router.post(
    "/{template_id}/versions/{version_id}/fork",
    response_model=TemplateVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def fork_template(
    tenant_id: str,
    template_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)),
) -> TemplateVersion:
    """REQ-012: fork -- from a tenant's own template or a shared starter."""
    source_template = _get_owned_template_or_404(db, tenant_id, template_id)
    source_version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.id == version_id, TemplateVersion.template_id == source_template.id)
        .one_or_none()
    )
    if source_version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template version not found")

    new_template = Template(
        tenant_id=tenant_id,
        name=f"{source_template.name} (fork)",
        forked_from_version_id=source_version.id,
    )
    db.add(new_template)
    db.flush()
    new_version = TemplateVersion(
        template_id=new_template.id,
        version_number=1,
        schema_json=source_version.schema_json,
        status="draft",
        created_by_user_id=membership.user_id,
    )
    db.add(new_version)
    db.commit()
    # No db.refresh() -- see create_template above, same reasoning.
    return new_version


@router.get("/{template_id}/versions/{version_id}", response_model=TemplateVersionOut)
def get_template_version(
    tenant_id: str,
    template_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(get_active_membership),
) -> TemplateVersion:
    template = _get_owned_template_or_404(db, tenant_id, template_id)
    version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.id == version_id, TemplateVersion.template_id == template.id)
        .one_or_none()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template version not found")
    return version


@router.put("/{template_id}/versions/{version_id}", response_model=TemplateVersionOut)
def update_draft(
    tenant_id: str,
    template_id: str,
    version_id: str,
    payload: UpdateDraftRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)),
) -> TemplateVersion:
    template = _get_owned_template_or_404(db, tenant_id, template_id)
    _require_own_template(template, tenant_id)
    version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.id == version_id, TemplateVersion.template_id == template.id)
        .one_or_none()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template version not found")
    if version.status == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Published versions are immutable (REQ-011)")

    try:
        validate_template_schema(payload.schema_json)
    except RuleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors}) from exc

    version.schema_json = payload.schema_json
    db.commit()
    # No db.refresh() -- see create_template above, same reasoning.
    return version


@router.post("/{template_id}/versions/{version_id}/publish", response_model=TemplateVersionOut)
def publish_version(
    tenant_id: str,
    template_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> TemplateVersion:
    """REQ-011: publishing is immutable and irreversible in this prototype --
    there is no unpublish endpoint. A later change must be a new version."""
    template = _get_owned_template_or_404(db, tenant_id, template_id)
    _require_own_template(template, tenant_id)
    version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.id == version_id, TemplateVersion.template_id == template.id)
        .one_or_none()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template version not found")
    if version.status == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already published")

    try:
        validate_template_schema(version.schema_json)
    except RuleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors}) from exc

    version.status = "published"
    version.published_at = datetime.now(timezone.utc)
    db.commit()
    # No db.refresh() -- see create_template above, same reasoning.
    return version
