import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import attachments, auth, decisions, drafts, exports, integrity, mfa, orgs, projects, templates
from app.webapp.router import router as webapp_router

_telemetry_logger = logging.getLogger("bgp.telemetry")
_started_at = datetime.now(timezone.utc)

app = FastAPI(
    title="Build Governance Platform",
    description=(
        "Local prototype: identity/sessions/MFA/invitations (WP03), "
        "PostgreSQL RLS tenant isolation (WP04), versioned templates with a "
        "declarative rule interpreter (WP05), projects/evidence revisions "
        "with atomic occurrence seeding (WP06), exceptions/decisions with "
        "idempotent, append-only recording (WP07), hash-chain integrity "
        "checkpoints with incident-blocking (WP08), open-format tenant "
        "export/import (WP09 -- full evidence revision history and full "
        "decision/exception/compensating-review content, since BGP-F04; "
        "decisions/exceptions/audit/integrity-receipts/compensating-reviews "
        "stay historical-only, never re-created as live rows on import, "
        "but ARE preserved and re-emitted on a later export of the "
        "importing tenant -- see ImportedHistoricalRecord), and "
        "essential-journey backend support "
        "(WP10 -- My work with reason/direct-action, save/resume drafts, "
        "plain-language blocker explanations and a permitted-outcomes "
        "confirmation summary), and a first real frontend (WP11, 2026-09-20 "
        "-- DEC04 resolved: server-rendered HTML via app/webapp/, same-"
        "origin, reusing this same session cookie; login/MFA, an org "
        "picker, and the five essential journeys are real pages now -- "
        "REQ-039's timezone display/translation remains a frontend gap "
        "this first increment does not close). DEC05 (decision durability mechanism) is "
        "still unresolved -- decisions here commit atomically to a single "
        "local Postgres instance only, and the integrity checkpoint's "
        "custody is enforced by this same instance's RLS, not by a "
        "genuinely separate system (see IntegrityCheckpoint's docstring). "
        "See docs/blueprint/ Section 6 for the delivery sequence. Session "
        "mechanism is the same signed cookie used since WP03 -- DEC04 "
        "(2026-09-20) kept it as-is rather than introducing a new one. "
        "WP12: secrets moved off hardcoded literals and MFA "
        "secrets are now encrypted at rest, security logging covers "
        "auth/MFA/invitation events, and CI now runs dependency and "
        "secret scans (REQ-045/046/047) -- REQ-043's numeric performance "
        "budgets remain DEC08-gated, and a real 99.5% monthly-availability "
        "baseline needs production traffic history this prototype has "
        "never had; only the measurement mechanism (below) is built. "
        "2026-09-17: BGP_Development_Review_Findings_v1.0.pdf's BGP-F01-F04 "
        "fixed -- login only issues a real session after a session-bound "
        "second-factor check (app/routers/mfa.py's login-verify), a "
        "compensating review is now an authenticated action from the "
        "reviewer's own session (CompensatingReview), decision commits and "
        "evidence-revision writes take coordinated row locks plus two "
        "partial unique indexes close the remaining races (see "
        "decisions.py's _compute_readiness/_require_decision_authority "
        "docstrings), and export/import gained per-row source_id stability "
        "and full historical preservation described above. BGP-F05 "
        "(README) fixed the same day. See TRACKER.md for details and the "
        "tests proving each one."
    ),
    version="0.1.0-bgp-remediation",
)

app.include_router(auth.router)
app.include_router(mfa.router)
app.include_router(orgs.router)
app.include_router(templates.router)
app.include_router(projects.router)
app.include_router(decisions.router)
app.include_router(integrity.router)
app.include_router(exports.router)
app.include_router(drafts.router)
app.include_router(attachments.router)
app.include_router(webapp_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def _telemetry_middleware(request: Request, call_next):
    """WP12/REQ-043: 'publish measurements' half -- structured per-request
    latency/status telemetry, one of the items Blueprint Sec.5.7's minimum
    telemetry list names explicitly. This logs; it does not aggregate,
    alert, or compute an actual 99.5% monthly-availability figure, which
    needs real traffic history over real time that a local dev instance
    restarted on demand can never honestly produce. The numeric API p95 /
    render budgets REQ-043 also asks to be 'approved' stay DEC08-gated,
    same shape of limitation as DEC05/DEC04 elsewhere in this project."""
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    _telemetry_logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
        },
    )
    return response


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}


@app.get("/status")
def status_report() -> dict:
    """WP12/REQ-043: minimal operational status -- version, environment,
    and process uptime. Not a substitute for real monitoring (no
    aggregation, no alerting, no historical retention of its own); a
    starting point for whatever real telemetry pipeline a production
    deployment would need, which doesn't exist yet."""
    now = datetime.now(timezone.utc)
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": app.version,
        "started_at": _started_at.isoformat(),
        "uptime_seconds": round((now - _started_at).total_seconds(), 1),
    }
