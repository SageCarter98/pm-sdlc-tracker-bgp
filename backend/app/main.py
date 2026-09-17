from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth, decisions, exports, integrity, mfa, orgs, projects, templates

app = FastAPI(
    title="Build Governance Platform",
    description=(
        "Local prototype: identity/sessions/MFA/invitations (WP03), "
        "PostgreSQL RLS tenant isolation (WP04), versioned templates with a "
        "declarative rule interpreter (WP05), projects/evidence revisions "
        "with atomic occurrence seeding (WP06), exceptions/decisions with "
        "idempotent, append-only recording (WP07), hash-chain integrity "
        "checkpoints with incident-blocking (WP08), and open-format tenant "
        "export/import (WP09 -- current-state only; decisions/exceptions/"
        "audit export as historical read-only sections, not re-created as "
        "live rows on import). DEC05 (decision durability mechanism) is "
        "still unresolved -- decisions here commit atomically to a single "
        "local Postgres instance only, and the integrity checkpoint's "
        "custody is enforced by this same instance's RLS, not by a "
        "genuinely separate system (see IntegrityCheckpoint's docstring). "
        "See docs/blueprint/ Section 6 for the delivery sequence. Session "
        "mechanism is a prototype signed cookie, not the DEC04-approved "
        "design."
    ),
    version="0.1.0-wp09",
)

app.include_router(auth.router)
app.include_router(mfa.router)
app.include_router(orgs.router)
app.include_router(templates.router)
app.include_router(projects.router)
app.include_router(decisions.router)
app.include_router(integrity.router)
app.include_router(exports.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}
