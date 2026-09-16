from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth, mfa, orgs, templates

app = FastAPI(
    title="Build Governance Platform",
    description=(
        "Local prototype: identity/sessions/MFA/invitations (WP03), "
        "PostgreSQL RLS tenant isolation (WP04, unverified without live "
        "Postgres), and versioned templates with a declarative rule "
        "interpreter (WP05). No projects, evidence, exceptions or decisions "
        "yet -- see docs/blueprint/ Section 6 for the delivery sequence. "
        "Session mechanism is a prototype signed cookie, not the "
        "DEC04-approved design."
    ),
    version="0.1.0-wp05",
)

app.include_router(auth.router)
app.include_router(mfa.router)
app.include_router(orgs.router)
app.include_router(templates.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}
