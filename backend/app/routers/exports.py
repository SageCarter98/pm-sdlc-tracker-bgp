"""WP09: REQ-030 (complete open-format export, lossless clean-instance
re-import without privilege transfer) and REQ-031 (own-data export/history
always available). Blueprint Sec.5.6.

Scope decision, made explicit rather than silently assumed: only *current
state* is re-created as LIVE rows on import (templates/versions, projects/
memberships, occurrences, evidence items -- each importing its full
revision history, not just a single fresh baseline revision, since
BGP-F04). decisions/exceptions/audit/integrity_receipts/compensating_reviews
export with full content (manifest, conditions, compensating-review
linkage) but are NOT re-inserted as live governance rows on import.
Recreating a live DecisionRecord/ExceptionRecord attributed to its
*original* historical actor is exactly what Blueprint Sec.5.6 warns against
("Legacy missing attribution is labelled as missing; it is never
reconstructed as a verified approval") -- those tables also have NOT NULL
actor columns that a genuinely unmatched historical actor cannot honestly
satisfy. Whether/how re-establishing live decision history on import should
work is a real product question, not resolved here.

BGP-F04 (2026-09-17): before this fix, that historical content was kept
only inside the ImportJob row's own archive_json -- present in the archive
that was imported, but silently absent from every export the importing
tenant made afterwards (an export only ever queried the LIVE governance
tables). It is now preserved in `ImportedHistoricalRecord`, read-only, and
re-emitted by _build_archive on every later export -- see that model's
docstring and HISTORICAL_KINDS below. Every exportable live-recreated
table also now carries a stable `source_id` (models.py's Template.source_id
docstring) so identity survives id regeneration across export -> import ->
export hops.
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
    CompensatingReview,
    DecisionRecord,
    EvidenceItem,
    EvidenceRevision,
    ExceptionRecord,
    ExportJob,
    GateOccurrence,
    ImportedActorProvenance,
    ImportedHistoricalRecord,
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

# BGP-F04: kinds stored in imported_historical_records -- also the archive
# section each kind's entries live in (see _build_archive/HISTORICAL_KINDS).
HISTORICAL_KINDS = {
    "decisions": "decision",
    "exceptions": "exception",
    "audit": "audit_event",
    "integrity_receipts": "integrity_receipt",
    "compensating_reviews": "compensating_review",
}

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
    """BGP-F04: every exportable table now carries a `source_id` alongside
    `id` (`source_id or id` -- NULL means this row was created natively
    here, so its own id IS the stable source id; see models.py's
    Template.source_id docstring). Evidence items export their FULL
    revision history, not just current state. Decisions export their full
    manifest/conditions/compensating-review linkage. `compensating_reviews`
    is exported as its own section. Historical content from a PRIOR import
    (imported_historical_records) is merged into the matching section
    verbatim, so it survives an export -> import -> export chain instead
    of silently disappearing after one hop."""
    actor_ids: set[str] = {requesting_user_id}
    # BGP-F04 follow-up: revisions carrying preserved historical provenance
    # (EvidenceRevision.source_actor_id -- an author that either couldn't be
    # matched at import, or was, but whose original identity is still owed
    # to future re-exports either way) are NOT real local users and cannot
    # go through the `actors_out` User query below. Collected separately and
    # merged into that section afterwards.
    historical_actors: dict[str, str | None] = {}

    templates_out = []
    for t in db.query(Template).filter(Template.tenant_id == tenant_id).all():
        versions = db.query(TemplateVersion).filter(TemplateVersion.template_id == t.id).order_by(TemplateVersion.version_number).all()
        for v in versions:
            if v.created_by_user_id:
                actor_ids.add(v.created_by_user_id)
        templates_out.append({
            "id": t.id, "source_id": t.source_id or t.id, "name": t.name,
            "versions": [
                {
                    "id": v.id, "source_id": v.source_id or v.id,
                    "version_number": v.version_number, "schema_json": v.schema_json,
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
                revisions = (
                    db.query(EvidenceRevision)
                    .filter(EvidenceRevision.evidence_item_id == i.id)
                    .order_by(EvidenceRevision.revision_number)
                    .all()
                )
                for r in revisions:
                    # BGP-F04 follow-up: only add the live actor_user_id to
                    # the actors section when it is a REAL attribution (no
                    # source_actor_id recorded -- this revision was created
                    # directly in this instance, never imported). An
                    # imported, unmatched revision's actor_user_id is the
                    # importer, whose own real actor row is already present
                    # from their own activity; re-declaring it here would
                    # not be wrong, but source_actor_id below is what
                    # subsequent readers must treat as this revision's
                    # actual author.
                    if r.source_actor_id is None:
                        actor_ids.add(r.actor_user_id)
                    else:
                        historical_actors[r.source_actor_id] = r.source_actor_email
                    if r.owner_user_id:
                        actor_ids.add(r.owner_user_id)
                items_out.append({
                    "id": i.id, "source_id": i.source_id or i.id,
                    "gate_id": i.gate_id, "rule_id": i.rule_id, "evidence_kind": i.evidence_kind,
                    "required": i.required, "blocker_level": i.blocker_level, "permitted_role_ids": i.permitted_role_ids,
                    "status": i.status, "owner_actor_id": i.owner_user_id,
                    "due_date": _jsonable(i.due_date), "completed_date": _jsonable(i.completed_date), "reference": i.reference,
                    # BGP-F04: full history, not just current state -- each
                    # revision's own source_version/source_hash included.
                    "revisions": [
                        {
                            "revision_number": r.revision_number, "status": r.status,
                            "owner_actor_id": r.owner_user_id, "due_date": _jsonable(r.due_date),
                            "completed_date": _jsonable(r.completed_date), "reference": r.reference,
                            "source_version": r.source_version, "source_hash": r.source_hash,
                            # BGP-F04 follow-up: prefer the preserved
                            # original identity over the live FK -- see
                            # EvidenceRevision.source_actor_id's docstring
                            # and the actor_ids loop above. created_at is
                            # now always the true original time too, since
                            # commit_import restores it instead of letting
                            # it default to import time.
                            "actor_actor_id": r.source_actor_id if r.source_actor_id is not None else r.actor_user_id,
                            "created_at": _jsonable(r.created_at),
                        }
                        for r in revisions
                    ],
                })
            occs_out.append({
                "id": o.id, "source_id": o.source_id or o.id,
                "gate_id": o.gate_id, "sequence": o.sequence, "trigger": o.trigger,
                "due_at": _jsonable(o.due_at), "evidence_items": items_out,
            })
        projects_out.append({
            "id": p.id, "source_id": p.source_id or p.id,
            "name": p.name, "template_version_id": p.template_version_id, "class_id": p.class_id,
            "owner_actor_id": p.owner_user_id,
            "members": [{"actor_id": m.user_id, "role": m.role} for m in members],
            "occurrences": occs_out,
        })

    compensating_reviews_out = []
    for r in db.query(CompensatingReview).filter(CompensatingReview.tenant_id == tenant_id).all():
        actor_ids.add(r.reviewer_user_id)
        compensating_reviews_out.append({
            "id": r.id, "source_id": r.id, "occurrence_id": r.occurrence_id,
            "reviewer_actor_id": r.reviewer_user_id, "manifest_digest": r.manifest_digest,
            "note": r.note, "created_at": _jsonable(r.created_at),
        })

    decisions_out = []
    for d in db.query(DecisionRecord).filter(DecisionRecord.tenant_id == tenant_id).all():
        actor_ids.add(d.actor_user_id)
        if d.separation_override_reviewer_id:
            actor_ids.add(d.separation_override_reviewer_id)
        decisions_out.append({
            # BGP-F04: decisions are never live-recreated on import (see
            # module docstring), so every row this query returns is always
            # native to this tenant -- source_id is always its own id.
            "id": d.id, "source_id": d.id, "project_id": d.project_id, "occurrence_id": d.occurrence_id,
            "actor_actor_id": d.actor_user_id, "actor_role": d.actor_role, "outcome": d.outcome,
            "manifest_json": d.manifest_json, "reviewed_manifest_digest": d.reviewed_manifest_digest,
            "conditions_json": d.conditions_json, "supersedes_decision_id": d.supersedes_decision_id,
            "reason": d.reason,
            "separation_override_review_id": d.separation_override_review_id,
            "separation_override_reviewer_actor_id": d.separation_override_reviewer_id,
            "separation_override_note": d.separation_override_note,
            "created_at": _jsonable(d.created_at),
        })

    exceptions_out = []
    for e in db.query(ExceptionRecord).filter(ExceptionRecord.tenant_id == tenant_id).all():
        actor_ids.add(e.approving_user_id)
        actor_ids.add(e.owner_user_id)
        exceptions_out.append({
            "id": e.id, "source_id": e.id, "evidence_item_id": e.evidence_item_id, "reason": e.reason, "safeguards": e.safeguards,
            "approving_actor_id": e.approving_user_id, "owner_actor_id": e.owner_user_id,
            "starts_at": _jsonable(e.starts_at), "expires_at": _jsonable(e.expires_at), "status": e.status,
            "revoked_at": _jsonable(e.revoked_at),
        })

    audit_out = []
    for a in db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id).all():
        actor_ids.add(a.actor_user_id)
        audit_out.append({
            "id": a.id, "source_id": a.id, "project_id": a.project_id, "occurrence_id": a.occurrence_id, "decision_id": a.decision_id,
            "actor_actor_id": a.actor_user_id, "event_type": a.event_type, "detail": a.detail, "sequence": a.sequence,
            "created_at": _jsonable(a.created_at),
        })

    receipts_out = [
        {
            "id": c.id, "source_id": c.id, "project_id": c.project_id, "from_sequence": c.from_sequence, "to_sequence": c.to_sequence,
            "event_count": c.event_count, "chain_digest": c.chain_digest, "created_at": _jsonable(c.created_at),
        }
        for c in db.query(IntegrityCheckpoint).filter(IntegrityCheckpoint.tenant_id == tenant_id).all()
    ]

    sections = {
        "templates": templates_out, "projects": projects_out,
        "decisions": decisions_out, "exceptions": exceptions_out, "audit": audit_out,
        "integrity_receipts": receipts_out, "compensating_reviews": compensating_reviews_out,
    }

    # BGP-F04: fold in historical content from a PRIOR import so it survives
    # this export too -- each entry is re-emitted exactly as it was first
    # exported (payload_json), never regenerated or reinterpreted.
    for section, kind in HISTORICAL_KINDS.items():
        for ihr in db.query(ImportedHistoricalRecord).filter(ImportedHistoricalRecord.tenant_id == tenant_id, ImportedHistoricalRecord.kind == kind).all():
            sections[section].append(ihr.payload_json)
            for key in ("actor_actor_id", "owner_actor_id", "approving_actor_id", "reviewer_actor_id", "separation_override_reviewer_actor_id"):
                value = ihr.payload_json.get(key)
                if value:
                    actor_ids.add(value)

    actors_out = [{"id": a.id, "email": a.email} for a in db.query(User).filter(User.id.in_(actor_ids)).all()]
    # BGP-F04 follow-up: append preserved historical identities alongside
    # real local users -- these ids are NEVER local User rows (never
    # matched, or matched-but-superseded-by-a-later-import identity), so a
    # future import's email-based matching is the only way they could ever
    # resolve to a live account, exactly as REQ-030 requires ("do not
    # confer login or approval rights").
    actors_out.extend({"id": source_id, "email": email} for source_id, email in historical_actors.items())
    sections["actors"] = actors_out

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
    # No db.refresh() -- see app/db.py's SessionLocal docstring
    # (expire_on_commit=False): every field here was already set in Python
    # before commit, and export_jobs is RLS-protected, so a post-commit
    # refresh would run with no tenant context left and raise.
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
    # No db.refresh() -- see the export job creation above, same reasoning
    # (import_jobs is RLS-protected too).
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
    # BGP-F04 follow-up: id -> email from the archive's own actors section,
    # so EvidenceRevision.source_actor_email can be set from the SAME
    # source used for matching, not re-derived some other way.
    archive_actor_emails: dict[str, str | None] = {}

    try:
        for a in archive.get("actors", []):
            local = _match_actor(db, tenant_id, a.get("email"))
            actor_map[a["id"]] = local.id if local else None
            archive_actor_emails[a["id"]] = a.get("email")
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
        counts = {
            k: 0 for k in (
                "templates", "template_versions", "projects", "project_memberships",
                "gate_occurrences", "evidence_items", "evidence_revisions",
            )
        }
        historical_counts = {k: 0 for k in HISTORICAL_KINDS.values()}
        skipped_historical = 0

        for t in archive.get("templates", []):
            new_tpl_id = str(uuid.uuid4())
            id_map[t["id"]] = new_tpl_id
            db.add(Template(id=new_tpl_id, tenant_id=tenant_id, name=t["name"], source_id=t.get("source_id", t["id"])))
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
                    source_id=v.get("source_id", v["id"]),
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
                source_id=p.get("source_id", p["id"]),
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
                    source_id=o.get("source_id", o["id"]),
                ))
                db.flush()
                counts["gate_occurrences"] += 1

                for i in o.get("evidence_items", []):
                    new_iid = str(uuid.uuid4())
                    id_map[i["id"]] = new_iid
                    owner = resolve(i.get("owner_actor_id"), required=False)
                    due_date = _parse_dt(i.get("due_date"))
                    completed_date = _parse_dt(i.get("completed_date"))

                    # BGP-F04: full revision history when the archive has one;
                    # a single synthetic revision-1 from current state
                    # otherwise, for backward compatibility with an archive
                    # exported before this fix.
                    revisions_in = i.get("revisions") or [{
                        "revision_number": 1, "status": i["status"], "owner_actor_id": i.get("owner_actor_id"),
                        "due_date": i.get("due_date"), "completed_date": i.get("completed_date"),
                        "reference": i.get("reference"), "source_version": None, "source_hash": None,
                        "actor_actor_id": None,
                    }]
                    latest_revision_number = max(r["revision_number"] for r in revisions_in)

                    db.add(EvidenceItem(
                        id=new_iid, tenant_id=tenant_id, project_id=new_pid, occurrence_id=new_oid,
                        gate_id=i["gate_id"], rule_id=i["rule_id"], evidence_kind=i["evidence_kind"],
                        required=i["required"], blocker_level=i["blocker_level"], permitted_role_ids=i["permitted_role_ids"],
                        status=i["status"], owner_user_id=owner, due_date=due_date,
                        completed_date=completed_date, reference=i.get("reference"),
                        latest_revision_number=latest_revision_number,
                        source_id=i.get("source_id", i["id"]),
                    ))
                    db.flush()
                    counts["evidence_items"] += 1

                    for r in sorted(revisions_in, key=lambda rev: rev["revision_number"]):
                        source_created_at = _parse_dt(r.get("created_at"))
                        db.add(EvidenceRevision(
                            tenant_id=tenant_id, evidence_item_id=new_iid, revision_number=r["revision_number"],
                            status=r["status"], owner_user_id=resolve(r.get("owner_actor_id"), required=False),
                            due_date=_parse_dt(r.get("due_date")), completed_date=_parse_dt(r.get("completed_date")),
                            reference=r.get("reference"), source_version=r.get("source_version"), source_hash=r.get("source_hash"),
                            # A revision's own recorded actor -- unmatched
                            # falls back to the importer, same discipline as
                            # every other required actor here, never invented.
                            # This FK is for referential integrity only; it
                            # is never read back as "who really did this"
                            # once source_actor_id (below) is set.
                            actor_user_id=resolve(r.get("actor_actor_id"), required=True),
                            # BGP-F04 follow-up: the archive's own actor id,
                            # preserved as historical provenance independent
                            # of the live FK above -- see EvidenceRevision.
                            # source_actor_id's docstring. Set even when the
                            # actor WAS matched, so re-export always has a
                            # stable identity to report regardless of
                            # whether a later re-import's matching differs.
                            source_actor_id=r.get("actor_actor_id"),
                            source_actor_email=archive_actor_emails.get(r.get("actor_actor_id")),
                            # BGP-F04 follow-up: restore the ORIGINAL
                            # creation time instead of letting the column
                            # default to "now" (import time) -- an archive
                            # with no created_at (pre-follow-up export, or
                            # the single synthetic revision-1 fallback
                            # above) still falls back to now, which is the
                            # honest answer when no original time exists.
                            created_at=source_created_at if source_created_at is not None else _now(),
                        ))
                        counts["evidence_revisions"] += 1

        # BGP-F04: decisions/exceptions/audit events/integrity receipts/
        # compensating reviews are preserved as read-only historical content
        # (ImportedHistoricalRecord -- never live rows, see module
        # docstring) so a LATER export of this tenant can include them
        # again. Only the live-row references inside each payload
        # (project_id/occurrence_id/evidence_item_id) are remapped to the
        # ids just created above; id/source_id and any decision-to-decision
        # or decision-to-review link stay exactly as first exported.
        remap_fields = ("project_id", "occurrence_id", "evidence_item_id")
        for section, kind in HISTORICAL_KINDS.items():
            for entry in archive.get(section, []):
                source_id = entry.get("source_id", entry.get("id"))
                if source_id is None:
                    skipped_historical += 1
                    continue
                already = (
                    db.query(ImportedHistoricalRecord)
                    .filter(
                        ImportedHistoricalRecord.tenant_id == tenant_id,
                        ImportedHistoricalRecord.kind == kind,
                        ImportedHistoricalRecord.source_id == source_id,
                    )
                    .one_or_none()
                )
                if already is not None:
                    continue  # already preserved by an earlier import of this same source record

                payload = dict(entry)
                broken_reference = False
                for field in remap_fields:
                    if payload.get(field) is not None:
                        remapped = id_map.get(payload[field])
                        if remapped is None:
                            broken_reference = True
                            break
                        payload[field] = remapped
                if broken_reference:
                    # Refers to a project/occurrence/evidence item that
                    # isn't in THIS archive -- cannot be linked to anything
                    # live here. Skipped, not fabricated, and not allowed to
                    # abort the whole import the way a broken STRUCTURAL
                    # reference (e.g. a project's template_version) does --
                    # historical enrichment is optional, core data is not.
                    skipped_historical += 1
                    continue

                db.add(ImportedHistoricalRecord(
                    tenant_id=tenant_id, import_job_id=job.id, kind=kind, source_id=source_id, payload_json=payload,
                ))
                historical_counts[kind] += 1

        job.status = "committed"
        job.committed_at = _now()
        job.commit_report = {
            "counts": counts,
            "historical_counts": historical_counts,
            "skipped_historical_broken_references": skipped_historical,
            "rows_created": sum(counts.values()) + sum(historical_counts.values()),
            "unmatched_actor_count": sum(1 for v in actor_map.values() if v is None),
            "id_map_size": len(id_map),
        }
        db.commit()
    except (KeyError, ValueError, TypeError) as exc:
        # BGP-F04 verification point 4: a corrupted or malformed archive is
        # rejected cleanly -- never an unhandled 500 -- and the rollback
        # above (same try block) leaves no partially-created project behind.
        db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Import failed: archive is malformed or references missing content ({exc})",
        )
    except Exception:
        db.rollback()
        raise

    # No db.refresh() -- see the export/import job creation above, same
    # reasoning (import_jobs is RLS-protected too).
    return ImportJobOut.model_validate(job)
