from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth, decisions, mfa, orgs, projects, templates

app = FastAPI(
    title="Build Governance Platform",
    description=(
        "Local prototype: identity/sessions/MFA/invitations (WP03), "
        "PostgreSQL RLS tenant isolation (WP04), versioned templates with a "
        "declarative rule interpreter (WP05), projects/evidence revisions "
        "with atomic occurrence seeding (WP06), and exceptions/decisions "
        "with idempotent, append-only recording (WP07). DEC05 (decision "
        "durability mechanism) is still unresolved -- decisions here commit "
        "atomically to a single local Postgres instance only, nothing more. "
        "See docs/blueprint/ Section 6 for the delivery sequence. Session "
        "mechanism is a prototype signed cookie, not the DEC04-approved "
        "design."
    ),
    version="0.1.0-wp07",
)

app.include_router(auth.router)
app.include_router(mfa.router)
app.include_router(orgs.router)
app.include_router(templates.router)
app.include_router(projects.router)
app.include_router(decisions.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}
