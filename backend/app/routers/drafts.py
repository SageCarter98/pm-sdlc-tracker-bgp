"""WP10/REQ-034: save and resume drafts. See Draft's docstring in
app/models.py for scope -- this is the storage primitive, not the
truthful-Saving/Saved/Not-saved UI state itself (frontend concern, DEC04
unresolved)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_membership
from app.models import Draft, Membership

router = APIRouter(tags=["drafts"])


class DraftOut(BaseModel):
    draft_key: str
    form_data: dict
    revision: int

    model_config = {"from_attributes": True}


class SaveDraftRequest(BaseModel):
    base_revision: int
    form_data: dict


def _own_draft_or_404(db: Session, tenant_id: str, user_id: str, draft_key: str) -> Draft:
    draft = (
        db.query(Draft)
        .filter(Draft.tenant_id == tenant_id, Draft.user_id == user_id, Draft.draft_key == draft_key)
        .one_or_none()
    )
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No draft found")
    return draft


@router.get("/orgs/{tenant_id}/drafts", response_model=list[DraftOut])
def list_drafts(
    tenant_id: str, db: Session = Depends(get_db), membership: Membership = Depends(get_active_membership)
) -> list[Draft]:
    """Own drafts only, regardless of tenant role -- a draft is never
    visible to anyone but the user who saved it (Blueprint Sec.5.2: 'Owner
    scoped'), including tenant administrators."""
    return db.query(Draft).filter(Draft.tenant_id == tenant_id, Draft.user_id == membership.user_id).order_by(Draft.updated_at.desc()).all()


@router.get("/orgs/{tenant_id}/drafts/{draft_key}", response_model=DraftOut)
def get_draft(
    tenant_id: str, draft_key: str, db: Session = Depends(get_db), membership: Membership = Depends(get_active_membership)
) -> Draft:
    return _own_draft_or_404(db, tenant_id, membership.user_id, draft_key)


@router.put("/orgs/{tenant_id}/drafts/{draft_key}", response_model=DraftOut)
def save_draft(
    tenant_id: str,
    draft_key: str,
    payload: SaveDraftRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_active_membership),
) -> Draft:
    """Upsert with optimistic concurrency, same base_revision pattern as
    evidence revisions (app/routers/projects.py) -- base_revision=0 creates
    a new draft; any other value must match the current revision exactly,
    or this is a 409 (two tabs/devices editing the same draft, not a
    silent last-write-wins)."""
    existing = (
        db.query(Draft)
        .filter(Draft.tenant_id == tenant_id, Draft.user_id == membership.user_id, Draft.draft_key == draft_key)
        .one_or_none()
    )
    if existing is None:
        if payload.base_revision != 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "base_revision 0 required to create a new draft")
        draft = Draft(tenant_id=tenant_id, user_id=membership.user_id, draft_key=draft_key, form_data=payload.form_data, revision=1)
        db.add(draft)
    else:
        if payload.base_revision != existing.revision:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"base_revision {payload.base_revision} is stale -- current is {existing.revision}",
            )
        existing.form_data = payload.form_data
        existing.revision += 1
        draft = existing

    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/orgs/{tenant_id}/drafts/{draft_key}", status_code=status.HTTP_204_NO_CONTENT)
def discard_draft(
    tenant_id: str, draft_key: str, db: Session = Depends(get_db), membership: Membership = Depends(get_active_membership)
) -> None:
    draft = _own_draft_or_404(db, tenant_id, membership.user_id, draft_key)
    db.delete(draft)
    db.commit()
