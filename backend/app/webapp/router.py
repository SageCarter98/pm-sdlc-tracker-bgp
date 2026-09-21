"""WP11 page routes. See app/webapp/__init__.py for scope. Every handler
below calls the same functions app/routers/*.py's JSON endpoints call --
see that module's docstring for why."""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_session_mfa_verified, require_mfa
from app.routers import auth as auth_router
from app.routers import decisions as decisions_router
from app.routers import drafts as drafts_router
from app.routers import mfa as mfa_router
from app.routers import orgs as orgs_router
from app.routers import projects as projects_router
from app.webapp.auth import page_current_user, page_membership


def _reset_tenant_context(db: Session, tenant_id: str) -> None:
    """Any query issued after an exception caught mid-request must not
    assume app.tenant_id is still set: decisions.py's own _deny() helper
    (a legitimate control -- it commits an audit trail for a denied
    decision, e.g. BGP-F02's separation-of-duties check, before raising)
    ends the transaction SET LOCAL was scoped to, same as every other
    instance of this root cause found 2026-09-20 building WP11. The
    existing JSON API never hit this because it has nothing left to query
    once it catches an HTTPException -- it just lets FastAPI render the
    error. This webapp layer is the first caller that needs to keep
    reading the database afterward (to re-render the page), so it is the
    first place obligated to re-establish context before doing so."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})


router = APIRouter(prefix="/ui", tags=["webapp"])
templates = Jinja2Templates(directory="app/templates")


def _render(request: Request, name: str, **context):
    context.setdefault("current_user", None)
    context.setdefault("flash", None)
    context.setdefault("errors", None)
    return templates.TemplateResponse(request, name, context)


# ---------------------------------------------------------------- Login/MFA


@router.get("/login")
def login_form(request: Request):
    return _render(request, "login.html")


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    resp = RedirectResponse(url="/ui/orgs", status_code=303)
    try:
        result = auth_router.login(auth_router.LoginRequest(email=email, password=password), resp, db)
    except HTTPException as exc:
        return _render(request, "login.html", errors=[exc.detail], email=email)
    if result.get("mfa_required"):
        resp.headers["location"] = "/ui/mfa/login-verify"
    return resp


@router.get("/mfa/login-verify")
def mfa_login_verify_form(request: Request):
    return _render(request, "mfa_login_verify.html")


@router.post("/mfa/login-verify")
def mfa_login_verify_submit(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    from fastapi import HTTPException

    resp = RedirectResponse(url="/ui/orgs", status_code=303)
    preauth_cookie = request.cookies.get(mfa_router.PREAUTH_SESSION_COOKIE)
    try:
        mfa_router.login_verify(
            mfa_router.LoginVerifyRequest(code=code),
            resp,
            db,
            bgp_preauth=preauth_cookie,
        )
    except HTTPException as exc:
        return _render(request, "mfa_login_verify.html", errors=[exc.detail])
    return resp


@router.get("/register")
def register_form(request: Request):
    return _render(request, "register.html")


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    if password != confirm_password:
        return _render(
            request,
            "register.html",
            errors=["The two passwords you entered do not match."],
            email=email,
        )
    try:
        auth_router.register(auth_router.RegisterRequest(email=email, password=password), db)
    except HTTPException as exc:
        return _render(request, "register.html", errors=[exc.detail], email=email)
    resp = RedirectResponse(url="/ui/orgs", status_code=303)
    login_result = auth_router.login(auth_router.LoginRequest(email=email, password=password), resp, db)
    if login_result.get("mfa_required"):  # pragma: no cover -- a brand-new account never has MFA enabled yet
        resp.headers["location"] = "/ui/mfa/login-verify"
    return resp


@router.post("/logout")
def logout_submit(db: Session = Depends(get_db)):
    resp = RedirectResponse(url="/ui/login", status_code=303)
    auth_router.logout(resp)
    return resp


@router.get("/mfa/enroll")
def mfa_enroll_form(request: Request, db: Session = Depends(get_db)):
    user = page_current_user(request, db)
    if user is None:
        return RedirectResponse("/ui/login", status_code=303)
    mfa_verified = get_session_mfa_verified(request.cookies.get("bgp_session"))
    out = mfa_router.enroll(user=user, mfa_verified=mfa_verified, db=db)
    secret = out.provisioning_uri.split("secret=")[1].split("&")[0]
    return _render(
        request,
        "mfa_enroll.html",
        current_user=user,
        secret=secret,
        provisioning_uri=out.provisioning_uri,
    )


@router.post("/mfa/enroll/verify")
def mfa_enroll_verify_submit(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    from fastapi import HTTPException

    user = page_current_user(request, db)
    if user is None:
        return RedirectResponse("/ui/login", status_code=303)
    resp = RedirectResponse(url="/ui/orgs", status_code=303)
    try:
        out = mfa_router.verify(mfa_router.VerifyRequest(code=code), resp, user=user, db=db)
    except HTTPException as exc:
        return _render(request, "mfa_enroll.html", current_user=user, errors=[exc.detail])
    return _render(
        request,
        "mfa_enrolled.html",
        current_user=user,
        recovery_codes=out.recovery_codes,
    )


# --------------------------------------------------------------- Org picker


@router.get("/orgs")
def orgs_picker(request: Request, db: Session = Depends(get_db)):
    user = page_current_user(request, db)
    if user is None:
        return RedirectResponse("/ui/login", status_code=303)
    my_orgs = orgs_router.my_orgs(user=user, db=db)
    return _render(request, "orgs_picker.html", current_user=user, orgs=my_orgs)


@router.post("/orgs")
def create_org_submit(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    from fastapi import HTTPException

    user = page_current_user(request, db)
    if user is None:
        return RedirectResponse("/ui/login", status_code=303)
    try:
        tenant = orgs_router.create_org(orgs_router.CreateOrgRequest(name=name), user=user, db=db)
    except HTTPException as exc:
        my_orgs = orgs_router.my_orgs(user=user, db=db)
        return _render(
            request,
            "orgs_picker.html",
            current_user=user,
            orgs=my_orgs,
            errors=[exc.detail],
        )
    return RedirectResponse(f"/ui/orgs/{tenant.id}/my-work", status_code=303)


# -------------------------------------------------------------------- Pages


def _require_page_membership(request: Request, db: Session, tenant_id: str):
    """Common guard for every /ui/orgs/{tenant_id}/... page: returns
    (user, membership) or a RedirectResponse to send back instead. Callers
    do `guard = _require_page_membership(...); if isinstance(guard, RedirectResponse): return guard`."""
    user = page_current_user(request, db)
    if user is None:
        return RedirectResponse("/ui/login", status_code=303)
    membership = page_membership(db, tenant_id, user)
    if membership is None:
        return RedirectResponse("/ui/orgs", status_code=303)
    return user, membership


@router.get("/orgs/{tenant_id}/my-work")
def my_work_page(
    request: Request,
    tenant_id: str,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard
    items = projects_router.my_work(tenant_id, status_filter=status_filter, db=db, membership=membership)
    return _render(
        request,
        "my_work.html",
        current_user=user,
        tenant_id=tenant_id,
        items=items,
        status_filter=status_filter,
    )


@router.get("/orgs/{tenant_id}/evidence/{evidence_item_id}")
def evidence_form_page(
    request: Request,
    tenant_id: str,
    evidence_item_id: str,
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard
    try:
        detail = projects_router.get_evidence_item(tenant_id, evidence_item_id, db=db, membership=membership)
    except HTTPException as exc:
        return _render(
            request,
            "my_work.html",
            current_user=user,
            tenant_id=tenant_id,
            items=[],
            errors=[exc.detail],
        )

    project = projects_router._get_owned_project_or_404(db, tenant_id, detail.item.project_id)
    schema = projects_router._load_bound_schema(db, tenant_id, project.template_version_id)

    draft = None
    try:
        draft = drafts_router.get_draft(tenant_id, evidence_item_id, db=db, membership=membership)
    except HTTPException:
        draft = None

    saved = request.query_params.get("saved")
    flash = {"draft": "Draft saved.", "submitted": "Revision submitted."}.get(saved)

    return _render(
        request,
        "evidence_form.html",
        current_user=user,
        tenant_id=tenant_id,
        item=detail.item,
        revisions=detail.revisions,
        statuses=schema.statuses,
        draft=draft,
        flash=flash,
    )


@router.post("/orgs/{tenant_id}/evidence/{evidence_item_id}/draft")
def evidence_save_draft(
    request: Request,
    tenant_id: str,
    evidence_item_id: str,
    status_value: str = Form(alias="status"),
    reference: str = Form(""),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        existing = drafts_router.get_draft(tenant_id, evidence_item_id, db=db, membership=membership)
        base_revision = existing.revision
    except HTTPException:
        base_revision = 0

    drafts_router.save_draft(
        tenant_id,
        evidence_item_id,
        drafts_router.SaveDraftRequest(
            base_revision=base_revision,
            form_data={"status": status_value, "reference": reference},
        ),
        db=db,
        membership=membership,
    )
    return RedirectResponse(f"/ui/orgs/{tenant_id}/evidence/{evidence_item_id}?saved=draft", status_code=303)


@router.post("/orgs/{tenant_id}/evidence/{evidence_item_id}/submit")
def evidence_submit_revision(
    request: Request,
    tenant_id: str,
    evidence_item_id: str,
    status_value: str = Form(alias="status"),
    reference: str = Form(""),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    detail = projects_router.get_evidence_item(tenant_id, evidence_item_id, db=db, membership=membership)
    # Fetched up front, not inside the except block below: create_evidence_
    # revision's IntegrityError path does its own db.rollback(), which ends
    # the transaction app.tenant_id was SET LOCAL on -- a query against an
    # RLS-protected table (projects) issued AFTER that rollback would see
    # nothing and raise a confusing second error masking the real one
    # (found 2026-09-20, WP11, the same root cause as the fix in
    # create_evidence_revision itself).
    project = projects_router._get_owned_project_or_404(db, tenant_id, detail.item.project_id)
    schema = projects_router._load_bound_schema(db, tenant_id, project.template_version_id)
    payload = projects_router.CreateEvidenceRevisionRequest(
        base_revision=detail.item.latest_revision_number,
        status=status_value,
        reference=reference or None,
    )
    try:
        projects_router.create_evidence_revision(tenant_id, evidence_item_id, payload, db=db, membership=membership)
    except HTTPException as exc:
        return _render(
            request,
            "evidence_form.html",
            current_user=user,
            tenant_id=tenant_id,
            item=detail.item,
            revisions=detail.revisions,
            statuses=schema.statuses,
            draft=None,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    try:
        drafts_router.discard_draft(tenant_id, evidence_item_id, db=db, membership=membership)
    except HTTPException:
        pass

    return RedirectResponse(
        f"/ui/orgs/{tenant_id}/evidence/{evidence_item_id}?saved=submitted",
        status_code=303,
    )


@router.get("/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide")
def decide_page(
    request: Request,
    tenant_id: str,
    project_id: str,
    occurrence_id: str,
    db: Session = Depends(get_db),
):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    occurrence = decisions_router._get_occurrence_or_404(db, project_id, occurrence_id)
    preview = decisions_router.preview_decision(
        tenant_id,
        project_id,
        occurrence_id,
        decisions_router.PreviewRequest(outcome=None),
        db=db,
        membership=membership,
    )
    return _render(
        request,
        "decide.html",
        current_user=user,
        tenant_id=tenant_id,
        project_id=project_id,
        occurrence=occurrence,
        preview=preview,
    )


@router.post("/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide")
def decide_submit(
    request: Request,
    tenant_id: str,
    project_id: str,
    occurrence_id: str,
    outcome: str = Form(...),
    manifest_digest: str = Form(...),
    condition_items: str = Form(""),
    condition_owner_user_id: str = Form(""),
    condition_deadline: str = Form(""),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    mfa_verified = get_session_mfa_verified(request.cookies.get("bgp_session"))

    conditions = None
    if outcome == "Approve with conditions":
        conditions = decisions_router.ConditionsIn(
            conditions=[c.strip() for c in condition_items.replace(",", "\n").splitlines() if c.strip()],
            owner_user_id=condition_owner_user_id,
            deadline=datetime.fromisoformat(condition_deadline) if condition_deadline else datetime.min,
        )

    payload = decisions_router.DecisionRequest(outcome=outcome, manifest_digest=manifest_digest, conditions=conditions)

    def _render_error(detail):
        _reset_tenant_context(db, tenant_id)
        occurrence = decisions_router._get_occurrence_or_404(db, project_id, occurrence_id)
        preview = decisions_router.preview_decision(
            tenant_id,
            project_id,
            occurrence_id,
            decisions_router.PreviewRequest(outcome=None),
            db=db,
            membership=membership,
        )
        return _render(
            request,
            "decide.html",
            current_user=user,
            tenant_id=tenant_id,
            project_id=project_id,
            occurrence=occurrence,
            preview=preview,
            errors=[str(detail)],
        )

    try:
        mfa_gated_user = require_mfa(user=user, membership=membership, mfa_verified=mfa_verified)
    except HTTPException as exc:
        return _render_error(exc.detail)

    try:
        decision = decisions_router.create_decision(
            tenant_id,
            project_id,
            occurrence_id,
            payload,
            db=db,
            user=mfa_gated_user,
            mfa_verified=mfa_verified,
            idempotency_key=str(uuid.uuid4()),
        )
    except HTTPException as exc:
        return _render_error(exc.detail)

    return _render(
        request,
        "decision_summary.html",
        current_user=user,
        tenant_id=tenant_id,
        decision=decision,
    )
