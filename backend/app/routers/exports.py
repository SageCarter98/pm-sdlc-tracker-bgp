"""WP09: REQ-030 (complete open-format export, lossless clean-instance
re-import without privilege transfer) and REQ-031 (own-data export/history
always available). Blueprint Sec.5.6.

Scope decision, made explicit rather than silently assumed: only *current
state* is re-created as live rows on import (templates/versions, projects/
memberships, occurrences, evidence items -- each importing as a single
fresh baseline revision). decisions/exceptions/audit/integrity_receipts
export as read-only historical sections but are NOT re-inserted as live
governance rows. Recreating a live DecisionRecord/ExceptionRecord
attributed to its *original* historical actor is exactly what Blueprint
Sec.5.6 warns against ("Legacy missing attribution is labelled as missing;
it is never reconstructed as a verified approval") -- those tables also
have NOT NULL actor columns that a genuinely unmatched historical actor
cannot honestly satisfy. Whether/how re-establishing live decision history
on import should work is a real product question, not resolved here.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership, require_role
from app.models import (
    AuditEvent,
    DecisionRecord,
    EvidenceItem,
    EvidenceRevision,
    ExceptionRecord,
    ExportJob,
    GateOccurrence,
    ImportedActorProvenance,
    ImportJob,
    IntegrityCheckpoint,
    Membership,
    Project,
    ProjectMembership,
    Role,
    Template,
    TemplateVersion,
    User,
)
from app.routers.projects import _get_owned_project_or_404  # noqa: F401  (re-exported for symmetry, not used directly here)

router = APIRouter(tags=["export-import"])

FORMAT_VERSION = 1
SECURITY_EXCLUSIONS = [
    "users.password_hash", "users.mfa_secret", "mfa_recovery_codes.code_hash",
    "invitations.token_hash", "session cookies/tokens",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_dt(value: str | None) -> datetime | None:
    """Inverse of _jsonable for datetime fields -- an archive is plain JSON,
    so every timestamp round-trips as an ISO string and must be parsed back
    before reaching the ORM (SQLite's DateTime type rejects a bare string
    outright; Postgres would silently accept it via psycopg2's adapter,
    which would have hidden this on the one dialect this project otherwise
    insists on testing everything against live -- caught here instead by
    running the SQLite suite too)."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _digest(payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_archive(db: Session, tenant_id: str, requesting_user_id: str) -> dict:
    actor_ids: set[str] = {requesting_user_id}

    templates_out = []
    for t in db.query(Template).filter(Template.tenant_id == tenant_id).all():
        versions = db.query(TemplateVersion).filter(TemplateVersion.template_id == t.id).order_by(TemplateVersion.version_number).all()
        for v in versions:
            if v.created_by_user_id:
                actor_ids.add(v.created_by_user_id)
        templates_out.append({
            "id": t.id, "name": t.name,
            "versions": [
                {
                    "id": v.id, "version_number": v.version_number, "schema_json": v.schema_json,
                    "status": v.status, "created_by_actor_id": v.created_by_user_id,
                    "published_at": _jsonable(v.published_at),
                }
                for v in versions
            ],
        })

    projects_out = []
    for p in db.query(Project).filter(Project.tenant_id == tenant_id).all():
        actor_ids.add(p.owner_user_id)
        members = db.query(ProjectMembership).filter(ProjectMembership.project_id == p.id).all()
        for m in members:
            actor_ids.add(m.user_id)
        occs_out = []
        for o in db.query(GateOccurrence).filter(GateOccurrence.project_id == p.id).all():
            items_out = []
            for i in db.query(EvidenceItem).filter(EvidenceItem.occurrence_id == o.id).all():
                if i.owner_user_id:
                    actor_ids.add(i.owner_user_id)
                items_out.append({
                    "id": i.id, "gate_id": i.gate_id, "rule_id": i.rule_id, "evidence_kind": i.evidence_kind,
                    "required": i.required, "blocker_level": i.blocker_level, "permitted_role_ids": i.permitted_role_ids,
                    "status": i.status, "owner_actor_id": i.owner_user_id,
                    "due_date": _jsonable(i.due_date), "completed_date": _jsonable(i.completed_date), "reference": i.reference,
                })
            occs_out.append({
                "id": o.id, "gate_id": o.gate_id, "sequence": o.sequence, "trigger": o.trigger,
                "due_at": _jsonable(o.due_at), "evidence_items": items_out,
            })
        projects_out.append({
            "id": p.id, "name": p.name, "template_version_id": p.template_version_id, "class_id": p.class_id,
            "owner_actor_id": p.owner_user_id,
            "members": [{"actor_id": m.user_id, "role": m.role} for m in members],
            "occurrences": occs_out,
        })

    decisions_out = []
    for d in db.query(DecisionRecord).filter(DecisionRecord.tenant_id == tenant_id).all():
        actor_ids.add(d.actor_user_id)
        decisions_out.append({
            "id": d.id, "project_id": d.project_id, "occurrence_id": d.occurrence_id,
            "actor_actor_id": d.actor_user_id, "actor_role": d.actor_role, "outcome": d.outcome,
            "reviewed_manifest_digest": d.reviewed_manifest_digest, "supersedes_decision_id": d.supersedes_decision_id,
            "reason": d.reason, "created_at": _jsonable(d.created_at),
        })

    exceptions_out = []
    for e in db.query(ExceptionRecord).filter(ExceptionRecord.tenant_id == tenant_id).all():
        actor_ids.add(e.approving_user_id)
        actor_ids.add(e.owner_user_id)
        exceptions_out.append({
            "id": e.id, "evidence_item_id": e.evidence_item_id, "reason": e.reason, "safeguards": e.safeguards,
            "approving_actor_id": e.approving_user_id, "owner_actor_id": e.owner_user_id,
            "starts_at": _jsonable(e.starts_at), "expires_at": _jsonable(e.expires_at), "status": e.status,
            "revoked_at": _jsonable(e.revoked_at),
        })

    audit_out = []
    for a in db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id).all():
        actor_ids.add(a.actor_user_id)
        audit_out.append({
            "id": a.id, "project_id": a.project_id, "occurrence_id": a.occurrence_id, "decision_id": a.decision_id,
            "actor_actor_id": a.actor_user_id, "event_type": a.event_type, "detail": a.detail, "sequence": a.sequence,
            "created_at": _jsonable(a.created_at),
        })

    receipts_out = [
        {
            "id": c.id, "project_id": c.project_id, "from_sequence": c.from_sequence, "to_sequence": c.to_sequence,
            "event_count": c.event_count, "chain_digest": c.chain_digest, "created_at": _jsonable(c.created_at),
        }
        for c in db.query(IntegrityCheckpoint).filter(IntegrityCheckpoint.tenant_id == tenant_id).all()
    ]

    actors_out = [{"id": a.id, "email": a.email} for a in db.query(User).filter(User.id.in_(actor_ids)).all()]

    sections = {
        "actors": actors_out, "templates": templates_out, "projects": projects_out,
        "decisions": decisions_out, "exceptions": exceptions_out, "audit": audit_out,
        "integrity_receipts": receipts_out,
    }
    manifest = {
        "format_version": FORMAT_VERSION,
        "exported_at": _now().isoformat(),
        "source_tenant_id": tenant_id,
        "exported_by_actor_id": requesting_user_id,
        "security_exclusions": SECURITY_EXCLUSIONS,
        "section_digests": {k: _digest(v) for k, v in sections.items()},
    }
    return {"manifest": manifest, **sections}


class ExportJobOut(BaseModel):
    id: str
    status: str
    format_version: int
    archive_digest: str
    archive: dict
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_job(cls, job: ExportJob) -> "ExportJobOut":
        return cls(
            id=job.id, status=job.status, format_version=job.format_version,
            archive_digest=job.archive_digest, archive=job.archive_json, created_at=job.created_at,
        )


@router.post("/orgs/{tenant_id}/exports", response_model=ExportJobOut, status_code=status.HTTP_201_CREATED)
def create_export(
    tenant_id: str, db: Session = Depends(get_db), membership: Membership = Depends(get_active_membership)
) -> ExportJobOut:
    """REQ-031: any active member can export -- own-data export is not role
    or billing-tier gated (billing tiers aren't built yet, WP14; this
    endpoint has no gate to add one to when they are, which is itself the
    honest state to leave it in until that requirement exists to enforce)."""
    archive = _build_archive(db, tenant_id, membership.user_id)
    job = ExportJob(
        tenant_id=tenant_id, requested_by_user_id=membership.user_id,
        archive_json=archive, archive_digest=_digest(archive),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return ExportJobOut.from_job(job)


@router.get("/orgs/{tenant_id}/exports/{job_id}", response_model=ExportJobOut)
def get_export(
    tenant_id: str, job_id: str, db: Session = Depends(get_db), _membership: Membership = Depends(get_active_membership)
) -> ExportJobOut:
    job = db.query(ExportJob).filter(ExportJob.id == job_id, ExportJob.tenant_id == tenant_id).one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export job not found")
    return ExportJobOut.from_job(job)


class ValidateImportRequest(BaseModel):
    archive: dict


class ImportJobOut(BaseModel):
    id: str
    status: str
    validation_report: dict | None
    commit_report: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/orgs/{tenant_id}/imports/{job_id}", response_model=ImportJobOut)
def get_import(
    tenant_id: str, job_id: str, db: Session = Depends(get_db), _membership: Membership = Depends(get_active_membership)
) -> ImportJobOut:
    job = db.query(ImportJob).filter(ImportJob.id == job_id, ImportJob.tenant_id == tenant_id).one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")
    return ImportJobOut.model_validate(job)


def _match_actor(db: Session, tenant_id: str, email: str | None) -> User | None:
    if not email:
        return None
    return (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.tenant_id == tenant_id, Membership.active.is_(True), User.email == email)
        .one_or_none()
    )


@router.post("/orgs/{tenant_id}/imports/validate", response_model=ImportJobOut, status_code=status.HTTP_201_CREATED)
def validate_import(
    tenant_id: str,
    payload: ValidateImportRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR)),
) -> ImportJobOut:
    """Blueprint Sec.5.6: 'Import validates archive sizes, paths, hashes,
    schema and tenant bindings in quarantine.' Nothing here writes to any
    live table except the ImportJob (quarantine) row itself."""
    archive = payload.archive
    manifest = archive.get("manifest") if isinstance(archive, dict) else None
    errors: list[str] = []

    if not manifest:
        errors.append("archive has no 'manifest' section")
    elif manifest.get("format_version") != FORMAT_VERSION:
        errors.append(f"unsupported format_version {manifest.get('format_version')!r} (this instance supports {FORMAT_VERSION})")

    section_digests = (manifest or {}).get("section_digests", {})
    for section, expected in section_digests.items():
        actual = _digest(archive.get(section, []))
        if actual != expected:
            errors.append(f"section '{section}': digest mismatch (archive may be corrupted or hand-edited)")

    actor_matches = []
    for a in archive.get("actors", []) if isinstance(archive.get("actors"), list) else []:
        local = _match_actor(db, tenant_id, a.get("email"))
        actor_matches.append({"source_actor_id": a.get("id"), "email": a.get("email"), "matched_local_user_id": local.id if local else None})

    report = {
        "ok": not errors,
        "errors": errors,
        "format_version": (manifest or {}).get("format_version"),
        "section_counts": {k: len(archive.get(k, []) or []) for k in section_digests},
        "actor_matches": actor_matches,
        "unmatched_actor_count": sum(1 for m in actor_matches if m["matched_local_user_id"] is None),
    }

    job = ImportJob(
        tenant_id=tenant_id, requested_by_user_id=membership.user_id, archive_json=archive,
        validation_report=report, status=("validated" if report["ok"] else "rejected"), validated_at=_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return ImportJobOut.model_validate(job)


@router.post("/orgs/{tenant_id}/imports/{job_id}/commit", response_model=ImportJobOut, status_code=status.HTTP_201_CREATED)
def commit_import(
    tenant_id: str, job_id: str, db: Session = Depends(get_db), membership: Membership = Depends(require_role(Role.TENANT_ADMINISTRATOR))
) -> ImportJobOut:
    """REQ-030: 'lossless clean-instance re-import without privilege
    transfer.' Every row gets a fresh id (never reuses the archive's
    original ids, avoiding any collision with existing data and making
    'clean instance' vs. 'same instance re-import' behave identically).
    Actor references resolve to a real local user only via
    ImportedActorProvenance (matched by email, re-checked live here, not
    trusted from the earlier validate() report); an unmatched actor on a
    NOT-NULL column falls back to the importing user, never a fabricated
    or reused identity -- see this module's docstring for why decisions/
    exceptions/audit/integrity_receipts stay historical-only and are not
    recreated as live rows at all."""
    job = db.query(ImportJob).filter(ImportJob.id == job_id, ImportJob.tenant_id == tenant_id).one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")
    if job.status == "committed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already committed")
    if job.status != "validated":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Job must be validated before committing (current status: {job.status})")

    archive = job.archive_json
    actor_map: dict[str, str | None] = {}

    try:
        for a in archive.get("actors", []):
            local = _match_actor(db, tenant_id, a.get("email"))
            actor_map[a["id"]] = local.id if local else None
            db.add(ImportedActorProvenance(
                tenant_id=tenant_id, import_job_id=job.id, source_actor_id=a["id"],
                source_email=a.get("email"), matched_local_user_id=local.id if local else None,
            ))

        def resolve(source_actor_id: str | None, *, required: bool) -> str | None:
            if source_actor_id is None:
                return membership.user_id if required else None
            resolved = actor_map.get(source_actor_id)
            if resolved is not None:
                return resolved
            return membership.user_id if required else None

        id_map: dict[str, str] = {}
        counts = {k: 0 for k in ("templates", "template_versions", "projects", "project_memberships", "gate_occurrences", "evidence_items")}

        for t in archive.get("templates", []):
            new_tpl_id = str(uuid.uuid4())
            id_map[t["id"]] = new_tpl_id
            db.add(Template(id=new_tpl_id, tenant_id=tenant_id, name=t["name"]))
            db.flush()
            counts["templates"] += 1
            for v in t.get("versions", []):
                new_ver_id = str(uuid.uuid4())
                id_map[v["id"]] = new_ver_id
                db.add(TemplateVersion(
                    id=new_ver_id, template_id=new_tpl_id, version_number=v["version_number"],
                    schema_json=v["schema_json"], status=v["status"],
                    created_by_user_id=resolve(v.get("created_by_actor_id"), required=False),
                    published_at=_parse_dt(v.get("published_at")),
                ))
                counts["template_versions"] += 1
        db.flush()

        for p in archive.get("projects", []):
            new_tvid = id_map.get(p["template_version_id"])
            if new_tvid is None:
                raise ValueError(f"project {p['id']} references template_version {p['template_version_id']!r} not present in this archive's templates section")
            new_pid = str(uuid.uuid4())
            id_map[p["id"]] = new_pid
            db.add(Project(
                id=new_pid, tenant_id=tenant_id, name=p["name"], template_version_id=new_tvid,
                class_id=p["class_id"], owner_user_id=resolve(p.get("owner_actor_id"), required=True),
            ))
            db.flush()
            counts["projects"] += 1

            for m in p.get("members", []):
                local_uid = actor_map.get(m["actor_id"])
                if local_uid:
                    db.add(ProjectMembership(tenant_id=tenant_id, project_id=new_pid, user_id=local_uid, role=m["role"]))
                    counts["project_memberships"] += 1
                # else: no live user to attach an unmatched historical member to -- correctly omitted, not silently invented.

            for o in p.get("occurrences", []):
                new_oid = str(uuid.uuid4())
                id_map[o["id"]] = new_oid
                db.add(GateOccurrence(
                    id=new_oid, tenant_id=tenant_id, project_id=new_pid, gate_id=o["gate_id"],
                    sequence=o["sequence"], trigger=o["trigger"], due_at=_parse_dt(o.get("due_at")),
                ))
                db.flush()
                counts["gate_occurrences"] += 1

                for i in o.get("evidence_items", []):
                    new_iid = str(uuid.uuid4())
                    owner = resolve(i.get("owner_actor_id"), required=False)
                    due_date = _parse_dt(i.get("due_date"))
                    completed_date = _parse_dt(i.get("completed_date"))
                    db.add(EvidenceItem(
                        id=new_iid, tenant_id=tenant_id, project_id=new_pid, occurrence_id=new_oid,
                        gate_id=i["gate_id"], rule_id=i["rule_id"], evidence_kind=i["evidence_kind"],
                        required=i["required"], blocker_level=i["blocker_level"], permitted_role_ids=i["permitted_role_ids"],
                        status=i["status"], owner_user_id=owner, due_date=due_date,
                        completed_date=completed_date, reference=i.get("reference"), latest_revision_number=1,
                    ))
                    db.flush()
                    counts["evidence_items"] += 1
                    db.add(EvidenceRevision(
                        tenant_id=tenant_id, evidence_item_id=new_iid, revision_number=1, status=i["status"],
                        owner_user_id=owner, due_date=due_date, completed_date=completed_date,
                        reference=i.get("reference"), actor_user_id=membership.user_id,
                    ))

        job.status = "committed"
        job.committed_at = _now()
        job.commit_report = {
            "counts": counts,
            "rows_created": sum(counts.values()),
            "unmatched_actor_count": sum(1 for v in actor_map.values() if v is None),
            "id_map_size": len(id_map),
        }
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(job)
    return ImportJobOut.model_validate(job)
