from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth, mfa, orgs

app = FastAPI(
    title="Build Governance Platform",
    description=(
        "WP03 local prototype: identity, sessions, MFA, invitations and "
        "membership only. No templates, evidence, exceptions, decisions or "
        "tenant-isolation (RLS) enforcement yet -- see docs/blueprint/ "
        "Section 6 for the delivery sequence. Session mechanism is a "
        "prototype signed cookie, not the DEC04-approved design."
    ),
    version="0.1.0-wp03",
)

app.include_router(auth.router)
app.include_router(mfa.router)
app.include_router(orgs.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}
