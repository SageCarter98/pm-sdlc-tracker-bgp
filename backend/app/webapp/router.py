"""WP11 page routes. See app/webapp/__init__.py for scope. Every handler
below calls the same functions app/routers/*.py's JSON endpoints call --
see that module's docstring for why."""

import json
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_session_mfa_verified, require_mfa, require_role
from app.models import Role
from app.routers import attachments as attachments_router
from app.routers import auth as auth_router
from app.routers import decisions as decisions_router
from app.routers import drafts as drafts_router
from app.routers import exports as exports_router
from app.routers import integrity as integrity_router
from app.routers import mfa as mfa_router
from app.routers import orgs as orgs_router
from app.routers import projects as projects_router
from app.routers import templates as templates_router
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


def _find_rule(schema, gate_id: str, rule_id: str):
    """Look up one rule's own definition (guidance/evidence_example, both
    optional) from the project's bound template schema -- the only place
    that text lives, since a rule is tenant-authored, not a KenAddme fixed
    catalogue entry. Returns None if not found (e.g. a rule removed from a
    later template version); pages must treat that as "no guidance", not
    an error."""
    for gate in schema.gates:
        if gate.gate_id != gate_id:
            continue
        for rule in gate.rules:
            if rule.rule_id == rule_id:
                return rule
    return None


def _find_gate(schema, gate_id: str):
    return next((g for g in schema.gates if g.gate_id == gate_id), None)


def _safe_next(next: str) -> str:
    """REQ-038: an invited user reaches the intended project after sign-in,
    not a generic org picker -- but `next` is the first redirect target in
    this app that ever comes from a query string / form field instead of
    being hardcoded, so it must be constrained to this app's own /ui/ pages
    or it becomes an open-redirect vector. Anything else (empty, absolute,
    protocol-relative '//host/...') falls back to the existing default."""
    if next and next.startswith("/ui/") and not next.startswith("//"):
        return next
    return "/ui/orgs"


router = APIRouter(prefix="/ui", tags=["webapp"])
templates = Jinja2Templates(directory="app/templates")


def _render(request: Request, name: str, **context):
    context.setdefault("current_user", None)
    context.setdefault("flash", None)
    context.setdefault("errors", None)
    return templates.TemplateResponse(request, name, context)


def _describe_condition(cond: dict | None) -> str:
    """UI08: a rule's `conditions` is Sec.5.5 structured data (rule_engine.py's
    Condition), not a string -- this renders it as plain language so a
    template author reads "what this means" without parsing JSON, same
    philosophy as decisions.py's own blocker_explanations."""
    if not cond:
        # None (never set on this rule) or Jinja's Undefined (the schema
        # dict has no "conditions" key at all -- true for every rule built
        # without a condition, since the add-rule handler below only sets
        # the key when a condition was actually configured) both mean the
        # same thing here: this rule has no condition.
        return "Always required (no condition)"
    op = cond.get("op")
    if op == "eq":
        return f"{cond.get('fact')} = {cond.get('value')!r}"
    if op == "in":
        return f"{cond.get('fact')} is one of {cond.get('value')!r}"
    if op in ("all", "any"):
        parts = [_describe_condition(c) for c in cond.get("conditions") or []]
        joiner = " AND " if op == "all" else " OR "
        return "(" + joiner.join(parts) + ")"
    # DEC07 Q10's additions. The guided form builder below still only
    # *creates* eq/in (+ one all/any wrapper) -- these arrive via Advanced
    # JSON or import -- but they must still READ back in plain language:
    # without this, a perfectly valid rule rendered as "Unrecognised
    # condition shape", which is actively misleading rather than merely
    # unhelpful. Offering them in the guided builder is the separate UI
    # pass DEC07 itself anticipates ("another thing the guided authoring UI
    # has to explain to a beginner").
    if op == "not":
        inner = cond.get("conditions") or []
        return f"NOT {_describe_condition(inner[0])}" if inner else "NOT (empty)"
    if op == "gte":
        return f"{cond.get('fact')} is at least {cond.get('value')!r}"
    if op == "lte":
        return f"{cond.get('fact')} is at most {cond.get('value')!r}"
    if op == "count":
        parts = [_describe_condition(c) for c in cond.get("conditions") or []]
        wording = {"gte": "at least", "lte": "at most", "eq": "exactly"}.get(cond.get("compare"), "?")
        return f"{wording} {cond.get('value')} of [" + ", ".join(parts) + "]"
    return "Unrecognised condition shape -- edit via Advanced JSON"


def _conditional_outcome_ids(db, tenant_id: str, project_id: str) -> list[str]:
    """Which of a template's declared outcomes mean "approve, with
    conditions attached". The decide form needs this because its conditions
    fieldset -- and the ConditionsIn it builds on submit -- used to key on
    the literal "Approve with conditions", so a vocabulary-3 template's own
    `conditional_approving` outcome collected no conditions and was then
    denied by `_outcome_eligibility` for "missing deadline or condition
    owner". Resolved through `outcome_lookup()`, the same indirection the
    status list already goes through. Returns [] when the bound template
    declares no such outcome."""
    project = projects_router._get_owned_project_or_404(db, tenant_id, project_id)
    schema = projects_router._load_bound_schema(db, tenant_id, project.template_version_id)
    return [d.id for d in schema.outcome_lookup().values() if d.kind == "conditional_approving"]


def _bgp_status_id(entry):
    """A status/decision-outcome entry is either a bare string (vocabulary
    1/2) or a structured object with an `id` (DEC07 vocabulary 3). Without
    this, Jinja's `join` filter stringifies the dict and renders its repr
    straight into the page."""
    return entry["id"] if isinstance(entry, dict) else entry


templates.env.globals["describe_condition"] = _describe_condition
templates.env.filters["tojson"] = lambda value, indent=2: json.dumps(value, indent=indent, default=str)
templates.env.filters["bgp_status_id"] = _bgp_status_id


# ---------------------------------------------------------------- Login/MFA


@router.get("/login")
def login_form(request: Request, next: str = ""):
    return _render(request, "login.html", next=next)


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    resp = RedirectResponse(url=_safe_next(next), status_code=303)
    try:
        result = auth_router.login(auth_router.LoginRequest(email=email, password=password), resp, db)
    except HTTPException as exc:
        return _render(request, "login.html", errors=[exc.detail], email=email, next=next)
    if result.get("mfa_required"):
        resp.headers["location"] = (
            f"/ui/mfa/login-verify?next={quote(next, safe='')}" if next else "/ui/mfa/login-verify"
        )
    return resp


@router.get("/mfa/login-verify")
def mfa_login_verify_form(request: Request, next: str = ""):
    return _render(request, "mfa_login_verify.html", next=next)


@router.post("/mfa/login-verify")
def mfa_login_verify_submit(
    request: Request, code: str = Form(...), next: str = Form(""), db: Session = Depends(get_db)
):
    from fastapi import HTTPException

    resp = RedirectResponse(url=_safe_next(next), status_code=303)
    preauth_cookie = request.cookies.get(mfa_router.PREAUTH_SESSION_COOKIE)
    try:
        mfa_router.login_verify(
            mfa_router.LoginVerifyRequest(code=code),
            resp,
            db,
            bgp_preauth=preauth_cookie,
        )
    except HTTPException as exc:
        return _render(request, "mfa_login_verify.html", errors=[exc.detail], next=next)
    return resp


@router.get("/register")
def register_form(request: Request, next: str = ""):
    return _render(request, "register.html", next=next)


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    if password != confirm_password:
        return _render(
            request,
            "register.html",
            errors=["The two passwords you entered do not match."],
            email=email,
            next=next,
        )
    try:
        auth_router.register(auth_router.RegisterRequest(email=email, password=password), db)
    except HTTPException as exc:
        return _render(request, "register.html", errors=[exc.detail], email=email, next=next)
    resp = RedirectResponse(url=_safe_next(next), status_code=303)
    login_result = auth_router.login(auth_router.LoginRequest(email=email, password=password), resp, db)
    if login_result.get("mfa_required"):  # pragma: no cover -- a brand-new account never has MFA enabled yet
        resp.headers["location"] = (
            f"/ui/mfa/login-verify?next={quote(next, safe='')}" if next else "/ui/mfa/login-verify"
        )
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
    rendered = _render(
        request,
        "mfa_enrolled.html",
        current_user=user,
        recovery_codes=out.recovery_codes,
    )
    # mfa_router.verify() bumps token_version (BGP-F01) and reissues the
    # session cookie with mfa_verified=True on `resp` -- but this handler
    # renders mfa_enrolled.html directly (to show recovery codes) rather
    # than returning `resp` itself, unlike every other cookie-mutating
    # handler in this file. Without copying the cookie across, the browser
    # keeps its now-stale pre-enrolment session (old token_version), and
    # the very next request gets silently logged out by page_current_user's
    # token_version check -- found 2026-09-20 driving this through a real
    # browser (the same class of bug WP11's own docstring warns about).
    for cookie_header in resp.headers.getlist("set-cookie"):
        rendered.headers.append("set-cookie", cookie_header)
    return rendered


# ------------------------------------------------------- Invitation landing


@router.get("/invitations/accept")
def invitation_accept_page(request: Request, token: str, db: Session = Depends(get_db)):
    """REQ-038: the essential invited-user journey. Deliberately GET-only
    for rendering, never accepting on GET (an accept is a state-changing
    action -- see decide_page/decide_submit's own GET-preview/POST-commit
    split for the same reasoning) -- if not signed in yet, this renders a
    landing page whose sign-in/register links carry `next` back to this
    exact URL (see _safe_next) so completing sign-in returns the user here
    automatically instead of dropping them at the generic org picker."""
    user = page_current_user(request, db)
    next_url = f"/ui/invitations/accept?token={token}"
    return _render(request, "invitation_accept.html", current_user=user, token=token, next=next_url)


@router.post("/invitations/accept")
def invitation_accept_submit(request: Request, token: str = Form(...), db: Session = Depends(get_db)):
    from fastapi import HTTPException

    user = page_current_user(request, db)
    next_url = f"/ui/invitations/accept?token={token}"
    if user is None:
        return RedirectResponse(f"/ui/login?next={next_url}", status_code=303)
    try:
        membership = orgs_router.accept_invitation(orgs_router.AcceptInvitationRequest(token=token), user=user, db=db)
    except HTTPException as exc:
        return _render(
            request,
            "invitation_accept.html",
            current_user=user,
            token=token,
            next=next_url,
            errors=[exc.detail],
        )
    # REQ-038: reaches the intended project (its organisation's own work
    # list) after sign-in, not a generic landing page.
    return RedirectResponse(f"/ui/orgs/{membership.tenant_id}/my-work", status_code=303)


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
    rule = _find_rule(schema, detail.item.gate_id, detail.item.rule_id)

    draft = None
    try:
        draft = drafts_router.get_draft(tenant_id, evidence_item_id, db=db, membership=membership)
    except HTTPException:
        draft = None

    saved = request.query_params.get("saved")
    flash = {"draft": "Draft saved.", "submitted": "Revision submitted.", "uploaded": "File uploaded."}.get(saved)
    attachments = attachments_router.list_attachments(tenant_id, evidence_item_id, db=db, membership=membership)

    return _render(
        request,
        "evidence_form.html",
        current_user=user,
        tenant_id=tenant_id,
        item=detail.item,
        revisions=detail.revisions,
        statuses=list(schema.status_lookup()),
        draft=draft,
        flash=flash,
        rule=rule,
        attachments=attachments,
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
            statuses=list(schema.status_lookup()),
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


@router.post("/orgs/{tenant_id}/evidence/{evidence_item_id}/attachments")
async def evidence_upload_attachment(
    request: Request,
    tenant_id: str,
    evidence_item_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        detail = projects_router.get_evidence_item(tenant_id, evidence_item_id, db=db, membership=membership)
        await attachments_router.upload_attachment(tenant_id, evidence_item_id, file, db=db, membership=membership)
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = projects_router.get_evidence_item(tenant_id, evidence_item_id, db=db, membership=membership)
        project = projects_router._get_owned_project_or_404(db, tenant_id, detail.item.project_id)
        schema = projects_router._load_bound_schema(db, tenant_id, project.template_version_id)
        attachments = attachments_router.list_attachments(tenant_id, evidence_item_id, db=db, membership=membership)
        return _render(
            request,
            "evidence_form.html",
            current_user=user,
            tenant_id=tenant_id,
            item=detail.item,
            revisions=detail.revisions,
            statuses=list(schema.status_lookup()),
            draft=None,
            rule=_find_rule(schema, detail.item.gate_id, detail.item.rule_id),
            attachments=attachments,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    return RedirectResponse(
        f"/ui/orgs/{tenant_id}/evidence/{evidence_item_id}?saved=uploaded",
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
        conditional_outcomes=[
            o for o in _conditional_outcome_ids(db, tenant_id, project_id) if o in preview.permitted_outcomes
        ],
        idempotency_key=str(uuid.uuid4()),
    )


@router.post("/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decide")
def decide_submit(
    request: Request,
    tenant_id: str,
    project_id: str,
    occurrence_id: str,
    outcome: str = Form(...),
    manifest_digest: str = Form(...),
    idempotency_key: str = Form(...),
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

    # Resolved through the bound template's own vocabulary, not the
    # literal "Approve with conditions" -- otherwise a vocabulary-3
    # template's `conditional_approving` outcome collects no conditions
    # here and is denied downstream for "missing deadline or condition
    # owner". For a v1/v2 template the legacy outcome map resolves
    # "Approve with conditions" to `conditional_approving`, so exactly the
    # outcome this used to match still matches.
    conditional_outcomes = _conditional_outcome_ids(db, tenant_id, project_id)

    conditions = None
    if outcome in conditional_outcomes:
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
            conditional_outcomes=[o for o in conditional_outcomes if o in preview.permitted_outcomes],
            errors=[str(detail)],
            # REQ-035/IPA03: a fresh key here, not the one that just failed --
            # this is a re-rendered form the user may resubmit with genuinely
            # different content (e.g. a different outcome after a denial), and
            # reusing the failed key would make that legitimate new attempt
            # collide with the denied one ("Idempotency-Key already used for a
            # different request") instead of being processed as new.
            idempotency_key=str(uuid.uuid4()),
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
            # REQ-035/IPA03: this key comes from the rendered form (a hidden
            # field set once per decide.html render, see decide_page/
            # _render_error above), not a fresh uuid generated on every POST.
            # A fresh-every-call key defeated create_decision's own
            # idempotency check at the UI layer: if the response is dropped
            # after the server commits and the browser resubmits the SAME
            # rendered form, it now replays the SAME key, so
            # decisions.py's existing-record match returns the decision
            # already recorded instead of racing into the "already decided"
            # 409 (which decide_submit could only have shown as a confusing
            # error, not the actual outcome).
            idempotency_key=idempotency_key,
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


# ------------------------------------------------------------- New project


def _admin_members(db: Session, tenant_id: str, membership, exclude_user_id: str | None = None):
    """Only fetched for a tenant_administrator -- access_review is gated on
    that role (orgs.py's own require_role(TENANT_ADMINISTRATOR) dependency,
    replicated explicitly here since a direct function call bypasses
    FastAPI's DI and its Depends()-expressed role check)."""
    if Role(membership.role) is not Role.TENANT_ADMINISTRATOR:
        return []
    rows = orgs_router.access_review(tenant_id, db=db, _membership=membership)
    return [m for m in rows if m.active and m.user_id != exclude_user_id]


def _access_review_rows(db: Session, tenant_id: str, membership):
    """Settings' own membership table needs the full audit trail (active
    AND revoked) -- unlike _admin_members' active-only, self-excluding list
    used for project_new's member picker, this must keep showing a row after
    it's revoked (REQ-047's access-review point is confirming past
    revocations actually took effect, not hiding the evidence of them)."""
    if Role(membership.role) is not Role.TENANT_ADMINISTRATOR:
        return []
    return orgs_router.access_review(tenant_id, db=db, _membership=membership)


def _render_settings(request: Request, db: Session, tenant_id: str, user, membership, **extra):
    return _render(
        request,
        "settings.html",
        current_user=user,
        tenant_id=tenant_id,
        membership=membership,
        members=_access_review_rows(db, tenant_id, membership),
        is_admin=Role(membership.role) is Role.TENANT_ADMINISTRATOR,
        **extra,
    )


@router.get("/orgs/{tenant_id}/projects/new")
def project_new_form(request: Request, tenant_id: str, db: Session = Depends(get_db)):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard
    starters = templates_router.list_published_versions(tenant_id, db=db, _membership=membership)
    return _render(
        request,
        "project_new.html",
        current_user=user,
        tenant_id=tenant_id,
        starters=starters,
        members=_admin_members(db, tenant_id, membership, user.id),
        can_create=Role(membership.role) in (Role.TENANT_ADMINISTRATOR, Role.APPROVER),
    )


@router.post("/orgs/{tenant_id}/projects/new")
def project_new_submit(
    request: Request,
    tenant_id: str,
    name: str = Form(...),
    template_version_id: str = Form(...),
    class_id: str = Form(...),
    member_user_id: str = Form(""),
    member_role: str = Form(""),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    def _render_form_error(detail: str):
        _reset_tenant_context(db, tenant_id)
        return _render(
            request,
            "project_new.html",
            current_user=user,
            tenant_id=tenant_id,
            starters=templates_router.list_published_versions(tenant_id, db=db, _membership=membership),
            members=_admin_members(db, tenant_id, membership, user.id),
            can_create=Role(membership.role) in (Role.TENANT_ADMINISTRATOR, Role.APPROVER),
            errors=[detail],
        )

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
    except HTTPException as exc:
        return _render_form_error(exc.detail)

    members: list = []
    if member_user_id.strip():
        if not member_role.strip():
            return _render_form_error("Choose a role for the additional member.")
        # NOT coerced through Role() any more. At vocabulary 4 a member's
        # project role is one the bound template declares, so coercing here
        # would reject every valid v4 role before create_project could see
        # it -- and create_project's own 422 names the permitted set for
        # the actual binding, which is a better error than this one was.
        members.append(projects_router.ProjectMemberIn(user_id=member_user_id, role=member_role.strip()))

    payload = projects_router.CreateProjectRequest(
        name=name, template_version_id=template_version_id, class_id=class_id, members=members
    )
    try:
        projects_router.create_project(tenant_id, payload, db=db, membership=membership)
    except HTTPException as exc:
        return _render_form_error(exc.detail if isinstance(exc.detail, str) else str(exc.detail))

    # FE-024: after creation, one clear next action -- My work, not an
    # intermediate confirmation screen.
    return RedirectResponse(f"/ui/orgs/{tenant_id}/my-work", status_code=303)


# --------------------------------------------------- Gate readiness dashboard


@router.get("/orgs/{tenant_id}/projects/{project_id}/gates")
def gate_dashboard_page(request: Request, tenant_id: str, project_id: str, db: Session = Depends(get_db)):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    project = projects_router._get_owned_project_or_404(db, tenant_id, project_id)
    schema = projects_router._load_bound_schema(db, tenant_id, project.template_version_id)
    occurrences = projects_router.list_occurrences(tenant_id, project_id, db=db, membership=membership)

    rows = []
    for occ in occurrences:
        preview = decisions_router.preview_decision(
            tenant_id,
            project_id,
            occ.id,
            decisions_router.PreviewRequest(outcome=None),
            db=db,
            membership=membership,
        )
        rows.append({"occurrence": occ, "preview": preview, "gate": _find_gate(schema, occ.gate_id)})

    return _render(
        request,
        "gate_dashboard.html",
        current_user=user,
        tenant_id=tenant_id,
        project_id=project_id,
        project=project,
        rows=rows,
    )


# ------------------------------------------------ Audit history & supersession


@router.get("/orgs/{tenant_id}/projects/{project_id}/history")
def project_history_page(request: Request, tenant_id: str, project_id: str, db: Session = Depends(get_db)):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    project = projects_router._get_owned_project_or_404(db, tenant_id, project_id)
    decisions = decisions_router.list_decisions(tenant_id, project_id, db=db, membership=membership)
    checkpoints = integrity_router.list_checkpoints(tenant_id, project_id, db=db, _membership=membership)
    incidents = integrity_router.list_incidents(tenant_id, project_id, db=db, _membership=membership)

    decisions_by_id = {d.id: d for d in decisions}
    superseded_by = {d.supersedes_decision_id: d.id for d in decisions if d.supersedes_decision_id}

    return _render(
        request,
        "project_history.html",
        current_user=user,
        tenant_id=tenant_id,
        project_id=project_id,
        project=project,
        decisions=decisions,
        decisions_by_id=decisions_by_id,
        superseded_by=superseded_by,
        checkpoints=checkpoints,
        incidents=incidents,
    )


# --------------------------------------------------------------- Org settings


@router.get("/orgs/{tenant_id}/settings")
def settings_page(request: Request, tenant_id: str, db: Session = Depends(get_db)):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    return _render(
        request,
        "settings.html",
        current_user=user,
        tenant_id=tenant_id,
        membership=membership,
        members=_access_review_rows(db, tenant_id, membership),
        is_admin=Role(membership.role) is Role.TENANT_ADMINISTRATOR,
    )


@router.post("/orgs/{tenant_id}/settings/invitations")
def settings_invite_submit(
    request: Request,
    tenant_id: str,
    email: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    def _render_settings_error(detail: str):
        _reset_tenant_context(db, tenant_id)
        return _render_settings(request, db, tenant_id, user, membership, errors=[detail])

    try:
        require_role(Role.TENANT_ADMINISTRATOR)(membership=membership)
    except HTTPException as exc:
        return _render_settings_error(exc.detail)

    try:
        role_enum = Role(role)
    except ValueError:
        return _render_settings_error("Unrecognised role.")

    try:
        invite = orgs_router.create_invitation(
            tenant_id, orgs_router.InviteRequest(email=email, role=role_enum), db=db, membership=membership
        )
    except HTTPException as exc:
        return _render_settings_error(exc.detail)

    _reset_tenant_context(db, tenant_id)
    return _render_settings(
        request,
        db,
        tenant_id,
        user,
        membership,
        # REQ-038: share the actual landing URL, not just the bare token --
        # no mail infra exists in this prototype (WP03 gap, tracked), so an
        # admin still has to copy this out-of-band, but the recipient now
        # gets a link straight to the invitation_accept page instead of
        # needing to know its URL shape themselves.
        flash=(
            f"Invitation created for {email}. Share this link out-of-band (no mail infra in this "
            f"prototype): /ui/invitations/accept?token={invite.token}"
        ),
    )


@router.post("/orgs/{tenant_id}/settings/memberships/{membership_id}/revoke")
def settings_revoke_submit(request: Request, tenant_id: str, membership_id: str, db: Session = Depends(get_db)):
    """IPA02: the UI counterpart to orgs.py's revoke_membership -- settings.html
    used to say no such control existed at all."""
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR)(membership=membership)
    except HTTPException as exc:
        return _render_settings(request, db, tenant_id, user, membership, errors=[exc.detail])

    try:
        orgs_router.revoke_membership(tenant_id, membership_id, db=db, actor=membership)
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        return _render_settings(request, db, tenant_id, user, membership, errors=[exc.detail])

    _reset_tenant_context(db, tenant_id)
    return _render_settings(request, db, tenant_id, user, membership, flash="Membership revoked.")


@router.post("/orgs/{tenant_id}/settings/memberships/{membership_id}/role")
def settings_role_submit(
    request: Request,
    tenant_id: str,
    membership_id: str,
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    """IPA02: the UI counterpart to orgs.py's change_membership_role -- same
    gap settings_revoke_submit closes for revocation."""
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR)(membership=membership)
    except HTTPException as exc:
        return _render_settings(request, db, tenant_id, user, membership, errors=[exc.detail])

    try:
        role_enum = Role(role)
    except ValueError:
        return _render_settings(request, db, tenant_id, user, membership, errors=["Unrecognised role."])

    try:
        orgs_router.change_membership_role(
            tenant_id, membership_id, orgs_router.RoleChangeRequest(role=role_enum), db=db, actor=membership
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        return _render_settings(request, db, tenant_id, user, membership, errors=[exc.detail])

    _reset_tenant_context(db, tenant_id)
    return _render_settings(request, db, tenant_id, user, membership, flash="Role updated.")


# --------------------------------------------------------- Export & import


def _render_export_import(request: Request, db: Session, tenant_id: str, user, membership, **extra):
    return _render(
        request,
        "export_import.html",
        current_user=user,
        tenant_id=tenant_id,
        membership=membership,
        is_admin=Role(membership.role) is Role.TENANT_ADMINISTRATOR,
        exports=exports_router.list_exports(tenant_id, db=db, _membership=membership),
        imports=exports_router.list_imports(tenant_id, db=db, _membership=membership),
        **extra,
    )


@router.get("/orgs/{tenant_id}/export-import")
def export_import_page(request: Request, tenant_id: str, db: Session = Depends(get_db)):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard
    return _render_export_import(request, db, tenant_id, user, membership)


@router.post("/orgs/{tenant_id}/export-import/exports")
def export_import_create_export(request: Request, tenant_id: str, db: Session = Depends(get_db)):
    """REQ-031: any active member, no role gate -- same as exports.py's own
    create_export."""
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    exports_router.create_export(tenant_id, db=db, membership=membership)
    _reset_tenant_context(db, tenant_id)
    return _render_export_import(request, db, tenant_id, user, membership, flash="Export created.")


@router.get("/orgs/{tenant_id}/export-import/exports/{job_id}/download")
def export_import_download(request: Request, tenant_id: str, job_id: str, db: Session = Depends(get_db)):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        job = exports_router.get_export(tenant_id, job_id, db=db, _membership=membership)
    except HTTPException as exc:
        return _render_export_import(
            request,
            db,
            tenant_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    # DEC08 (Q16): "asynchronous; must begin streaming within 2 s" -- a
    # StreamingResponse over exports_router._iter_archive_json sends bytes
    # as the archive is serialized, instead of a Response(content=...)
    # that waits for one complete json.dumps() string before anything is
    # sent. Content is byte-for-byte identical to the previous behaviour.
    return StreamingResponse(
        exports_router._iter_archive_json(job.archive),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="bgp-export-{tenant_id}-{job.id}.json"'},
    )


@router.post("/orgs/{tenant_id}/export-import/imports/validate")
async def export_import_validate_submit(
    request: Request,
    tenant_id: str,
    archive_text: str = Form(""),
    archive_file: UploadFile | None = None,
    db: Session = Depends(get_db),
):
    """FE-070: validated in quarantine (exports.py's validate_import creates
    an ImportJob row, nothing live) before any commit is possible."""
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR)(membership=membership)
    except HTTPException as exc:
        return _render_export_import(request, db, tenant_id, user, membership, errors=[exc.detail])

    raw: str | None = None
    if archive_file is not None and archive_file.filename:
        raw = (await archive_file.read()).decode("utf-8", errors="replace")
    elif archive_text.strip():
        raw = archive_text

    if not raw:
        return _render_export_import(
            request,
            db,
            tenant_id,
            user,
            membership,
            errors=["Choose an archive file or paste archive JSON to validate."],
        )

    try:
        archive = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _render_export_import(request, db, tenant_id, user, membership, errors=[f"Not valid JSON: {exc}"])
    if not isinstance(archive, dict):
        return _render_export_import(
            request, db, tenant_id, user, membership, errors=["Archive must be a JSON object."]
        )

    exports_router.validate_import(
        tenant_id, exports_router.ValidateImportRequest(archive=archive), db=db, membership=membership
    )
    _reset_tenant_context(db, tenant_id)
    return _render_export_import(
        request, db, tenant_id, user, membership, flash="Archive validated -- see the report below before committing."
    )


@router.post("/orgs/{tenant_id}/export-import/imports/{job_id}/commit")
def export_import_commit_submit(request: Request, tenant_id: str, job_id: str, db: Session = Depends(get_db)):
    """FE-072: explicit, separate commit action -- never implied by
    validation alone."""
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR)(membership=membership)
    except HTTPException as exc:
        return _render_export_import(request, db, tenant_id, user, membership, errors=[exc.detail])

    try:
        exports_router.commit_import(tenant_id, job_id, db=db, membership=membership)
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        return _render_export_import(
            request,
            db,
            tenant_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    _reset_tenant_context(db, tenant_id)
    return _render_export_import(
        request, db, tenant_id, user, membership, flash="Import committed -- see the reconciliation report below."
    )


# ------------------------------------------------- UI08: guided template authoring


def _parse_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _clone_schema(schema_json: dict) -> dict:
    """Every guided edit below mutates a fresh copy, never the ORM-tracked
    dict in place -- update_draft always receives a brand-new object, the
    same way every other caller of it (Advanced JSON, the JSON API) does."""
    return json.loads(json.dumps(schema_json))


def _build_condition(rows: list[tuple[str, str, str]], combinator: str) -> dict | None:
    """UI08's guided condition builder, bounded on purpose: up to 3 flat
    eq/in tests, optionally wrapped in one level of all/any. Sec.5.5's full
    vocabulary allows deeper nesting (up to MAX_CONDITION_DEPTH); reaching
    for that from a plain HTML form (DEC04: no SPA, no client-side
    condition tree) is what the Advanced JSON box below is for -- this
    covers the common case without hand-edited JSON, not every case."""
    leaves: list[dict] = []
    for fact, op, value in rows:
        fact = fact.strip()
        if not fact or op not in ("eq", "in"):
            continue
        if op == "eq":
            leaves.append({"op": "eq", "fact": fact, "value": value.strip()})
        else:
            leaves.append({"op": "in", "fact": fact, "value": _parse_csv(value)})
    if not leaves:
        return None
    if combinator in ("all", "any") and len(leaves) > 1:
        return {"op": combinator, "conditions": leaves}
    return leaves[0]


def _render_template_list(request: Request, db: Session, tenant_id: str, user, membership, **extra):
    rows = []
    for t in templates_router.list_templates(tenant_id, db=db, _membership=membership):
        versions = templates_router.list_template_versions(tenant_id, t.id, db=db, _membership=membership)
        rows.append({"template": t, "latest": versions[-1] if versions else None})
    return _render(
        request,
        "templates_list.html",
        current_user=user,
        tenant_id=tenant_id,
        rows=rows,
        can_author=Role(membership.role) in (Role.TENANT_ADMINISTRATOR, Role.APPROVER),
        **extra,
    )


@router.get("/orgs/{tenant_id}/templates")
def templates_list_page(request: Request, tenant_id: str, db: Session = Depends(get_db)):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard
    return _render_template_list(request, db, tenant_id, user, membership)


@router.post("/orgs/{tenant_id}/templates")
def templates_create_submit(request: Request, tenant_id: str, name: str = Form(...), db: Session = Depends(get_db)):
    """REQ-012/AC08: blank guided creation -- no JSON typed by the caller at
    all, same as create_template's own blank-default path."""
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
    except HTTPException as exc:
        return _render_template_list(request, db, tenant_id, user, membership, errors=[exc.detail])

    try:
        version = templates_router.create_template(
            tenant_id, templates_router.CreateTemplateRequest(name=name, schema_json=None), db=db, membership=membership
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        return _render_template_list(
            request,
            db,
            tenant_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    _reset_tenant_context(db, tenant_id)
    return RedirectResponse(
        f"/ui/orgs/{tenant_id}/templates/{version.template_id}/versions/{version.id}", status_code=303
    )


@router.post("/orgs/{tenant_id}/templates/import")
def templates_import_submit(
    request: Request, tenant_id: str, name: str = Form(...), schema_text: str = Form(...), db: Session = Depends(get_db)
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
    except HTTPException as exc:
        return _render_template_list(request, db, tenant_id, user, membership, errors=[exc.detail])

    try:
        schema_json = json.loads(schema_text)
    except json.JSONDecodeError as exc:
        return _render_template_list(request, db, tenant_id, user, membership, errors=[f"Not valid JSON: {exc}"])

    try:
        version = templates_router.import_template(
            tenant_id,
            templates_router.ImportTemplateRequest(name=name, schema_json=schema_json),
            db=db,
            membership=membership,
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_list(request, db, tenant_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return RedirectResponse(
        f"/ui/orgs/{tenant_id}/templates/{version.template_id}/versions/{version.id}", status_code=303
    )


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/fork")
def templates_fork_submit(
    request: Request, tenant_id: str, template_id: str, version_id: str, db: Session = Depends(get_db)
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
    except HTTPException as exc:
        return _render_template_list(request, db, tenant_id, user, membership, errors=[exc.detail])

    try:
        new_version = templates_router.fork_template(tenant_id, template_id, version_id, db=db, membership=membership)
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        return _render_template_list(
            request,
            db,
            tenant_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    _reset_tenant_context(db, tenant_id)
    return RedirectResponse(
        f"/ui/orgs/{tenant_id}/templates/{new_version.template_id}/versions/{new_version.id}", status_code=303
    )


def _render_template_editor(
    request: Request, db: Session, tenant_id: str, template_id: str, version_id: str, user, membership, **extra
):
    from fastapi import HTTPException

    try:
        template = templates_router._get_owned_template_or_404(db, tenant_id, template_id)
        version = templates_router.get_template_version(
            tenant_id, template_id, version_id, db=db, _membership=membership
        )
    except HTTPException as exc:
        return _render_template_list(
            request,
            db,
            tenant_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )
    versions = templates_router.list_template_versions(tenant_id, template_id, db=db, _membership=membership)
    is_admin_or_approver = Role(membership.role) in (Role.TENANT_ADMINISTRATOR, Role.APPROVER)
    return _render(
        request,
        "template_editor.html",
        current_user=user,
        tenant_id=tenant_id,
        template=template,
        version=version,
        versions=versions,
        can_author=is_admin_or_approver,
        is_editable=(version.status == "draft" and is_admin_or_approver),
        can_publish=(version.status == "draft" and Role(membership.role) is Role.TENANT_ADMINISTRATOR),
        **extra,
    )


@router.get("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}")
def template_editor_page(
    request: Request, tenant_id: str, template_id: str, version_id: str, db: Session = Depends(get_db)
):
    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard
    return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership)


def _require_editable_draft(db: Session, tenant_id: str, template_id: str, version_id: str, membership):
    """Shared precondition for every guided-mutation route below: must be
    this tenant's own template (not a shared starter -- _require_own_template),
    and REQ-011 immutability means a published version is never a mutation
    target, guided or otherwise. Raises HTTPException the caller already
    knows how to turn into an error render."""
    from fastapi import HTTPException, status

    template = templates_router._get_owned_template_or_404(db, tenant_id, template_id)
    templates_router._require_own_template(template, tenant_id)
    version = templates_router.get_template_version(tenant_id, template_id, version_id, db=db, _membership=membership)
    if version.status == "published":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Published versions are immutable (REQ-011) -- fork this version to make changes."
        )
    return template, version


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/metadata")
def template_metadata_submit(
    request: Request,
    tenant_id: str,
    template_id: str,
    version_id: str,
    tracks: str = Form(...),
    classes: str = Form(...),
    roles: str = Form(...),
    statuses: str = Form(...),
    decision_outcomes: str = Form(...),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
        _, version = _require_editable_draft(db, tenant_id, template_id, version_id, membership)
    except HTTPException as exc:
        return _render_template_editor(
            request,
            db,
            tenant_id,
            template_id,
            version_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    schema = _clone_schema(version.schema_json)
    schema["tracks"] = _parse_csv(tracks)
    schema["classes"] = _parse_csv(classes)
    schema["roles"] = _parse_csv(roles)
    schema["statuses"] = _parse_csv(statuses)
    schema["decision_outcomes"] = _parse_csv(decision_outcomes)

    try:
        templates_router.update_draft(
            tenant_id,
            template_id,
            version_id,
            templates_router.UpdateDraftRequest(schema_json=schema),
            db=db,
            membership=membership,
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return _render_template_editor(
        request, db, tenant_id, template_id, version_id, user, membership, flash="Template metadata updated."
    )


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates")
def template_add_gate_submit(
    request: Request,
    tenant_id: str,
    template_id: str,
    version_id: str,
    gate_id: str = Form(...),
    name: str = Form(...),
    sequence: int = Form(...),
    class_ids: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
        _, version = _require_editable_draft(db, tenant_id, template_id, version_id, membership)
    except HTTPException as exc:
        return _render_template_editor(
            request,
            db,
            tenant_id,
            template_id,
            version_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    schema = _clone_schema(version.schema_json)
    schema["gates"].append(
        {"gate_id": gate_id, "name": name, "sequence": sequence, "class_ids": class_ids, "rules": []}
    )

    try:
        templates_router.update_draft(
            tenant_id,
            template_id,
            version_id,
            templates_router.UpdateDraftRequest(schema_json=schema),
            db=db,
            membership=membership,
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return _render_template_editor(
        request, db, tenant_id, template_id, version_id, user, membership, flash=f"Gate '{gate_id}' added."
    )


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/{gate_id}/remove")
def template_remove_gate_submit(
    request: Request, tenant_id: str, template_id: str, version_id: str, gate_id: str, db: Session = Depends(get_db)
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
        _, version = _require_editable_draft(db, tenant_id, template_id, version_id, membership)
    except HTTPException as exc:
        return _render_template_editor(
            request,
            db,
            tenant_id,
            template_id,
            version_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    schema = _clone_schema(version.schema_json)
    schema["gates"] = [g for g in schema["gates"] if g["gate_id"] != gate_id]

    try:
        templates_router.update_draft(
            tenant_id,
            template_id,
            version_id,
            templates_router.UpdateDraftRequest(schema_json=schema),
            db=db,
            membership=membership,
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return _render_template_editor(
        request, db, tenant_id, template_id, version_id, user, membership, flash=f"Gate '{gate_id}' removed."
    )


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/{gate_id}/rules")
def template_add_rule_submit(
    request: Request,
    tenant_id: str,
    template_id: str,
    version_id: str,
    gate_id: str,
    rule_id: str = Form(...),
    class_ids: list[str] = Form(default=[]),
    occurrence_type: str = Form(...),
    evidence_kind: str = Form(...),
    permitted_role_ids: list[str] = Form(default=[]),
    blocker_level: str = Form(...),
    guidance: str = Form(""),
    evidence_example: str = Form(""),
    cond_combinator: str = Form("single"),
    cond1_fact: str = Form(""),
    cond1_op: str = Form(""),
    cond1_value: str = Form(""),
    cond2_fact: str = Form(""),
    cond2_op: str = Form(""),
    cond2_value: str = Form(""),
    cond3_fact: str = Form(""),
    cond3_op: str = Form(""),
    cond3_value: str = Form(""),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
        _, version = _require_editable_draft(db, tenant_id, template_id, version_id, membership)
    except HTTPException as exc:
        return _render_template_editor(
            request,
            db,
            tenant_id,
            template_id,
            version_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    schema = _clone_schema(version.schema_json)
    gate = next((g for g in schema["gates"] if g["gate_id"] == gate_id), None)
    if gate is None:
        return _render_template_editor(
            request, db, tenant_id, template_id, version_id, user, membership, errors=[f"Gate '{gate_id}' not found."]
        )

    conditions = _build_condition(
        [(cond1_fact, cond1_op, cond1_value), (cond2_fact, cond2_op, cond2_value), (cond3_fact, cond3_op, cond3_value)],
        cond_combinator,
    )
    new_rule = {
        "version": 1,
        "rule_id": rule_id,
        "class_ids": class_ids,
        "occurrence_type": occurrence_type,
        "evidence_kind": evidence_kind,
        "permitted_role_ids": permitted_role_ids,
        "blocker_level": blocker_level,
        "guidance": guidance or None,
        "evidence_example": evidence_example or None,
    }
    if conditions is not None:
        new_rule["conditions"] = conditions
    gate.setdefault("rules", []).append(new_rule)

    try:
        templates_router.update_draft(
            tenant_id,
            template_id,
            version_id,
            templates_router.UpdateDraftRequest(schema_json=schema),
            db=db,
            membership=membership,
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return _render_template_editor(
        request,
        db,
        tenant_id,
        template_id,
        version_id,
        user,
        membership,
        flash=f"Rule '{rule_id}' added to gate '{gate_id}'.",
    )


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/gates/{gate_id}/rules/{rule_id}/remove")
def template_remove_rule_submit(
    request: Request,
    tenant_id: str,
    template_id: str,
    version_id: str,
    gate_id: str,
    rule_id: str,
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
        _, version = _require_editable_draft(db, tenant_id, template_id, version_id, membership)
    except HTTPException as exc:
        return _render_template_editor(
            request,
            db,
            tenant_id,
            template_id,
            version_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    schema = _clone_schema(version.schema_json)
    gate = next((g for g in schema["gates"] if g["gate_id"] == gate_id), None)
    if gate is None:
        return _render_template_editor(
            request, db, tenant_id, template_id, version_id, user, membership, errors=[f"Gate '{gate_id}' not found."]
        )
    gate["rules"] = [r for r in gate.get("rules", []) if r["rule_id"] != rule_id]

    try:
        templates_router.update_draft(
            tenant_id,
            template_id,
            version_id,
            templates_router.UpdateDraftRequest(schema_json=schema),
            db=db,
            membership=membership,
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return _render_template_editor(
        request, db, tenant_id, template_id, version_id, user, membership, flash=f"Rule '{rule_id}' removed."
    )


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/raw")
def template_raw_edit_submit(
    request: Request,
    tenant_id: str,
    template_id: str,
    version_id: str,
    schema_text: str = Form(...),
    db: Session = Depends(get_db),
):
    """The escape hatch: full nested all/any conditions, applicability, or
    any other schema shape the guided forms above don't cover. Still goes
    through update_draft's real validation -- never a bypass, just a
    different input method for the same validated write."""
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)
        _require_editable_draft(db, tenant_id, template_id, version_id, membership)
    except HTTPException as exc:
        return _render_template_editor(
            request,
            db,
            tenant_id,
            template_id,
            version_id,
            user,
            membership,
            errors=[exc.detail if isinstance(exc.detail, str) else str(exc.detail)],
        )

    try:
        schema_json = json.loads(schema_text)
    except json.JSONDecodeError as exc:
        return _render_template_editor(
            request, db, tenant_id, template_id, version_id, user, membership, errors=[f"Not valid JSON: {exc}"]
        )

    try:
        templates_router.update_draft(
            tenant_id,
            template_id,
            version_id,
            templates_router.UpdateDraftRequest(schema_json=schema_json),
            db=db,
            membership=membership,
        )
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return _render_template_editor(
        request, db, tenant_id, template_id, version_id, user, membership, flash="Schema replaced via Advanced JSON."
    )


@router.post("/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}/publish")
def template_publish_submit(
    request: Request, tenant_id: str, template_id: str, version_id: str, db: Session = Depends(get_db)
):
    from fastapi import HTTPException

    guard = _require_page_membership(request, db, tenant_id)
    if isinstance(guard, RedirectResponse):
        return guard
    user, membership = guard

    try:
        require_role(Role.TENANT_ADMINISTRATOR)(membership=membership)
    except HTTPException as exc:
        return _render_template_editor(
            request, db, tenant_id, template_id, version_id, user, membership, errors=[exc.detail]
        )

    try:
        templates_router.publish_version(tenant_id, template_id, version_id, db=db, membership=membership)
    except HTTPException as exc:
        _reset_tenant_context(db, tenant_id)
        detail = exc.detail
        errors = detail["errors"] if isinstance(detail, dict) and "errors" in detail else [str(detail)]
        return _render_template_editor(request, db, tenant_id, template_id, version_id, user, membership, errors=errors)

    _reset_tenant_context(db, tenant_id)
    return _render_template_editor(
        request,
        db,
        tenant_id,
        template_id,
        version_id,
        user,
        membership,
        flash="Published. This version is now immutable (REQ-011) and available as a project starter.",
    )
