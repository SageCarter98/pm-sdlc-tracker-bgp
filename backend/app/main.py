from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title="Build Governance Platform",
    description=(
        "WP01 skeleton only. No identity, tenancy, template, evidence or "
        "decision endpoints exist yet — see docs/blueprint/ Section 6 for "
        "the delivery sequence."
    ),
    version="0.1.0-wp01",
)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}
