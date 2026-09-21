# API reference (SDLC G3.11)

The authoritative, always-current API reference is the OpenAPI schema FastAPI
generates from the code itself — not this file. Two ways to read it:

- **Interactive**: run the app (`uvicorn app.main:app --reload` from
  `backend/`) and open `GET /docs` (Swagger UI) or `GET /redoc`.
- **Static snapshot**: `docs/openapi.json`, regenerated with:

  ```
  cd backend && python -c "
  import json
  from app.main import app
  json.dump(app.openapi(), open('../docs/openapi.json', 'w'), indent=2)
  "
  ```

  Regenerate after any router change — this snapshot is a point-in-time
  export (46 paths as of 2026-09-19), not a live document, and nothing in CI
  currently checks it against the actual running schema.

**What this is not**: a hand-written data dictionary, architecture diagram,
or operational runbook. Those remain the honest gap `TRACKER.md` and item
`#125` already record — inline module docstrings (`app/main.py` and each
router) are the closest thing to architecture documentation that exists
today.
