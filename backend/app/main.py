from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth, decisions, drafts, exports, integrity, mfa, orgs, projects, templates

app = FastAPI(
    title="Build Governance Platform",
    description=(
        "Local prototype: identity/sessions/MFA/invitations (WP03), "
        "PostgreSQL RLS tenant isolation (WP04), versioned templates with a "
        "declarative rule interpreter (WP05), projects/evidence revisions "
        "with atomic occurrence seeding (WP06), exceptions/decisions with "
        "idempotent, append-only recording (WP07), hash-chain integrity "
        "checkpoints with incident-blocking (WP08), open-format tenant "
        "export/import (WP09 -- current-state only; decisions/exceptions/"
        "audit export as historical read-only sections, not re-created as "
        "live rows on import), and essential-journey backend support "
        "(WP10 -- My work with reason/direct-action, save/resume drafts, "
        "plain-language blocker explanations and a permitted-outcomes "
        "confirmation summary). No frontend exists yet (DEC04 unresolved) "
        "-- REQ-033's guided-form navigation and REQ-039's timezone "
        "display/translation are frontend-only concerns this backend "
        "cannot satisfy alone. DEC05 (decision durability mechanism) is "
        "still unresolved -- decisions here commit atomically to a single "
        "local Postgres instance only, and the integrity checkpoint's "
        "custody is enforced by this same instance's RLS, not by a "
        "genuinely separate system (see IntegrityCheckpoint's docstring). "
        "See docs/blueprint/ Section 6 for the delivery sequence. Session "
        "mechanism is a prototype signed cookie, not the DEC04-approved "
        "design."
    ),
    version="0.1.0-wp10",
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


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}
