# Build Governance Platform

Multi-tenant SaaS for running the KenAddme PM and SDLC gate frameworks (and other
governance frameworks) inside a tenant's own projects: templates, evidence,
exceptions, decisions, export/import.

**Status: WP01 (Repository and delivery controls) in progress. No identity,
tenancy, template, evidence or decision code exists yet.** Do not treat anything
in `backend/` as more than a build/CI skeleton. See `docs/blueprint/` for the
approved specification and `TRACKER.md` for how implementation progress is
governed and tracked.

## Authority and scope

- Controlling directive: *Build Governance Platform Project Directive v1.2
  Approved* (14 September 2026). Not included in this repository; referenced by
  `docs/blueprint/Blueprint_Working_Source.md` Section 8.
- Development-baseline approval: APR-001, 15 September 2026 (owner chat
  instruction — explicitly **not** an independent-review certificate; see
  Blueprint Section 9).
- This repository proceeds only under Directive v1.2 Section 18: local
  development, **synthetic fixtures only**, no real personal, client or
  payment data, no production commitment.

Twelve decisions (DEC01–DEC12) are only partly resolved — see
`docs/blueprint/Blueprint_Working_Source.md` Section 7. Notably **DEC01 (named
delivery lead and independent reviewer) is still open**, so no work here
carries independent review sign-off yet.

## Repository layout

```
docs/blueprint/     Approved blueprint pack v0.2 (spec, requirements, interface,
                     architecture, delivery plan) — read-only reference, not
                     modified by implementation work.
backend/             FastAPI service skeleton (DEC04 approved stack: FastAPI +
                     PostgreSQL + SQLAlchemy/Alembic). Health check only so far.
fixtures/synthetic/  Synthetic-only tenant/user fixtures for local development
                     and tests (Directive Section 18, Blueprint Section 6.1).
                     Never point this at a real database with real tenants.
.github/workflows/   Reproducible CI checks (REQ-049).
TRACKER.md           How this project's PM/SDLC gate tracking works.
```

## Build instructions

Requires Python 3.11+ and a local PostgreSQL instance for later work packages;
WP01 itself needs no database.

```
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest
```

`GET /healthz` is the only endpoint. Everything else (identity, tenancy,
templates, evidence, decisions) is WP03 onward per
`docs/blueprint/Blueprint_Working_Source.md` Section 6.

## Requirement ledger

The authoritative, versioned requirement ledger is
`docs/blueprint/Requirements_Catalogue.json` (58 requirements, 23 acceptance
cases, 7 prototype remediation findings, 14 work packages, 12 decisions).
Identifiers are stable across revisions — see Blueprint Section 8 for the
change-control rule before editing it.
