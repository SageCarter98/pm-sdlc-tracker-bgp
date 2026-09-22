"""WP15: evidence attachments (FE-097/098, conditional capability,
REQ-053). Same authorisation model as evidence revisions themselves
(app/routers/projects.py's create_evidence_revision) -- any current project
member may upload or list attachments for an evidence item; there is no
separate per-role gate here that revisions don't already have.

Immutable and versioned exactly like EvidenceRevision: an uploaded file
that scans clean (or a scanner isn't configured) supersedes the current
"active" one, same append-only lineage as EvidenceRevision. An upload that
scans "infected" is still recorded (never silently discarded) but is
quarantined -- `status="rejected"`, and it never becomes active or
supersedes whatever was active before it.

Download is refused for anything that isn't scan_status="clean" -- see
EvidenceAttachment's own docstring in app/models.py for exactly what each
scan_status/status value means and why "error" is never treated as safe."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.attachment_scanner import scanner
from app.attachment_storage import attachment_store
from app.core.config import settings
from app.db import get_db
from app.deps import get_active_membership
from app.models import EvidenceAttachment, EvidenceItem, Membership
from app.routers.projects import _require_project_member

router = APIRouter(tags=["attachments"])


class AttachmentOut(BaseModel):
    id: str
    evidence_item_id: str
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    scan_status: str
    status: str
    uploaded_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _get_evidence_item_or_404(db: Session, tenant_id: str, evidence_item_id: str) -> EvidenceItem:
    item = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.id == evidence_item_id, EvidenceItem.tenant_id == tenant_id)
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence item not found")
    return item


@router.get("/orgs/{tenant_id}/evidence/{evidence_item_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(
    tenant_id: str,
    evidence_item_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> list[EvidenceAttachment]:
    item = _get_evidence_item_or_404(db, tenant_id, evidence_item_id)
    _require_project_member(db, item.project_id, membership.user_id)
    return (
        db.query(EvidenceAttachment)
        .filter(EvidenceAttachment.evidence_item_id == item.id)
        .order_by(EvidenceAttachment.created_at)
        .all()
    )


@router.post(
    "/orgs/{tenant_id}/evidence/{evidence_item_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    tenant_id: str,
    evidence_item_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> EvidenceAttachment:
    item = _get_evidence_item_or_404(db, tenant_id, evidence_item_id)
    _require_project_member(db, item.project_id, membership.user_id)

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Uploaded file is empty")
    if len(data) > settings.attachment_max_size_bytes:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"File exceeds the {settings.attachment_max_size_bytes} byte limit",
        )

    # Scanned BEFORE deciding version lineage: an infected result must
    # never supersede whatever was previously active (see EvidenceAttachment's
    # own docstring). "unavailable"/"error"/"clean" all promote normally --
    # only a real, parsed "not clean" result quarantines instead.
    scan_status = scanner.scan(file.filename or "upload", data)
    storage_key, checksum = attachment_store.save(tenant_id, data)

    if scan_status == "infected":
        new_status = "rejected"
    else:
        new_status = "active"
        current = (
            db.query(EvidenceAttachment)
            .filter(EvidenceAttachment.evidence_item_id == item.id, EvidenceAttachment.status == "active")
            .one_or_none()
        )
        if current is not None:
            current.status = "superseded"

    attachment = EvidenceAttachment(
        tenant_id=tenant_id,
        evidence_item_id=item.id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        checksum_sha256=checksum,
        storage_key=storage_key,
        scan_status=scan_status,
        status=new_status,
        uploaded_by_user_id=membership.user_id,
    )
    db.add(attachment)
    db.commit()
    # No db.refresh() -- see app/db.py's SessionLocal docstring
    # (expire_on_commit=False): every field here was already set in Python
    # before commit, and evidence_attachments is RLS-protected, so a
    # post-commit refresh would run with no tenant context left and raise.

    if scan_status == "infected":
        # The row above is already committed -- quarantined and visible in
        # the attachment list, not silently dropped -- but the immediate
        # caller must see this as a failure, not a successful upload.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This file was flagged as infected and has been quarantined. It will not become the active evidence attachment.",
        )
    return attachment


@router.get("/orgs/{tenant_id}/attachments/{attachment_id}/download")
def download_attachment(
    tenant_id: str,
    attachment_id: str,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> Response:
    attachment = (
        db.query(EvidenceAttachment)
        .filter(EvidenceAttachment.id == attachment_id, EvidenceAttachment.tenant_id == tenant_id)
        .one_or_none()
    )
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    item = _get_evidence_item_or_404(db, tenant_id, attachment.evidence_item_id)
    _require_project_member(db, item.project_id, membership.user_id)

    if attachment.scan_status != "clean":
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"This file cannot be downloaded (scan status: {attachment.scan_status})",
        )

    data = attachment_store.read(attachment.storage_key)
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )
