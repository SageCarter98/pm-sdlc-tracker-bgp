# Build Governance Platform

Multi-tenant SaaS for running the KenAddme PM and SDLC gate frameworks (and other
governance frameworks) inside a tenant's own projects: templates, evidence,
exceptions, decisions, export/import.

**Status (2026-09-18): backend work packages WP01, WP03–WP10 and WP12 are built**
-- identity/MFA/invitations, PostgreSQL RLS tenant isolation, versioned templates
with a declarative rule interpreter, projects/evidence with append-only revision
history, exceptions/decisions (idempotent, separation-of-duties enforced via an
authenticated compensating review, concurrency-safe), hash-chain integrity
checkpoints, open-format export/import (full revision and decision history
preserved across re-export), essential-journey backend support, and operational
hardening (secrets off hardcoded literals, MFA secrets encrypted at rest,
security logging, CI dependency/secret scanning). **No frontend exists yet**
(DEC04, the frontend stack decision, is unresolved) -- there is no UI, only the
FastAPI backend and its OpenAPI schema (`GET /docs` once the app is running).
See `app/main.py`'s own module docstring for the fullest up-to-date summary of
what each work package added, and `TRACKER.md` for how this maps to gate
evidence. Do not treat this as production-ready: it runs against synthetic
fixtures only (Directive Section 18) and several architectural decisions
(DEC04 frontend, DEC05 decision durability, DEC07 rule vocabulary, DEC08
performance budgets, DEC11 key custody) remain open -- see each one's mention
in `app/`'s docstrings and `docs/blueprint/Blueprint_Working_Source.md`
Section 7 before treating anything gated on them as settled.

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
`docs/blueprint/Blueprint_Working_Source.md` Section 7. **DEC01 (named delivery
lead and independent reviewer) is resolved** (delivery lead: Freston Kenny
Adedeme; independent reviewer: Milton, who now also holds read access to this
repository and is named in `.github/CODEOWNERS`) — but naming the reviewer,
and giving him access, is not the same as a completed review: no code in this
repository has actually been reviewed by Milton yet (tracker item #124 stays
"Not started" until that happens; see `TRACKER.md`'s "Named roles" section).
DEC02–DEC12 remain otherwise as the Blueprint records them.

## Repository layout

```
docs/blueprint/     Approved blueprint pack v0.2 (spec, requirements, interface,
                     architecture, delivery plan) — read-only reference, not
                     modified by implementation work.
docs/wp02/           Discovery/assurance documents (threat model, privacy
                     assessment, data retention policy, assurance plan, data
                     inventory) drafted for WP02 -- not independently reviewed.
backend/             FastAPI + PostgreSQL + SQLAlchemy/Alembic service.
                     Identity/MFA, tenancy (RLS), templates, projects,
                     evidence, decisions, integrity, export/import, drafts.
                     No frontend (DEC04) -- see backend/app/main.py.
fixtures/synthetic/  Synthetic-only tenant/user/framework fixtures for local
                     development and tests (Directive Section 18, Blueprint
                     Section 6.1). Never point this at a real database with
                     real tenants.
.github/workflows/   CI: pytest (including live-Postgres RLS/concurrency
                     suites), pip-audit, gitleaks secret scan (REQ-046/REQ-009).
TRACKER.md           How this project's PM/SDLC gate tracking works, and the
                     full, dated history of what each work package built.
```

## Build instructions

Requires Python 3.12 and a local PostgreSQL instance (16+; CI runs against
`postgres:16`). Unlike WP01's original skeleton, **the application now needs a
real database** — most of the test suite and every RLS/tenant-isolation
guarantee depend on it.

### 1. Install dependencies

```
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on Linux/macOS
pip install -r requirements.txt
```

### 2. Create the database and the two Postgres roles (REQ-007)

Two roles are required, not one: `bgp_owner` (runs migrations, owns the
tables) and `bgp_app` (what the running application connects as). Postgres
exempts a table's owner from that table's own RLS policies unless `FORCE ROW
LEVEL SECURITY` is set — keeping them separate means the app role can never be
that exemption. Edit the two placeholder passwords in
`backend/scripts/setup_postgres_dev.sql` first, then, connected as the
`postgres` superuser:

```
psql -U postgres -h localhost -f scripts/setup_postgres_dev.sql
```

This creates the `bgp_dev` database and the two roles, but does **not** create
any tables — table creation, RLS policies and `bgp_app`'s per-table grants are
all handled by Alembic migrations (run as `bgp_owner`) in the next step, so
they can never drift out of sync with the schema the way a one-time setup
script would.

A third role, `bgp_backup` (`BYPASSRLS`, read-only, used only by
`scripts/restore_drill.py`'s `pg_dump` step — never imported by the running
app), is optional and only needed if you intend to run that restore drill; it
is not created by `setup_postgres_dev.sql`.

### 3. Configure environment variables

Copy the values below into `backend/.env` (gitignored — never commit real
values here), replacing every `CHANGE-ME-*` placeholder with the passwords you
set in step 2:

```
BGP_DATABASE_URL=postgresql+psycopg2://bgp_app:CHANGE-ME-APP@localhost:5432/bgp_dev
BGP_MIGRATION_DATABASE_URL=postgresql+psycopg2://bgp_owner:CHANGE-ME-OWNER@localhost:5432/bgp_dev
BGP_BACKUP_DATABASE_URL=postgresql+psycopg2://bgp_backup:CHANGE-ME-BACKUP@localhost:5432/bgp_dev

# Required for a PERSISTENT dev database (see "Persistent keys" below).
# Omit both and the app still runs, but generates a new random key each
# process start -- fine for a throwaway/in-memory-style dev loop, but it
# means every restart makes existing sessions AND existing users' encrypted
# MFA secrets undecryptable. Generate real values with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
BGP_SESSION_SECRET_KEY=<paste a token_urlsafe(32) value here>
BGP_MFA_ENCRYPTION_KEY=<paste a Fernet.generate_key() value here>
```

See `backend/app/core/config.py` for every setting's full docstring and
default.

### 4. Apply migrations and run the app

```
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

`GET /healthz` and `GET /status` are unauthenticated liveness/version checks.
Everything else requires a session — start at `POST /auth/register` and
`POST /auth/login`, then see `GET /docs` for the full OpenAPI schema. Login
for an MFA-enrolled account is now two steps (`POST /auth/login` then
`POST /auth/mfa/login-verify`) — see `app/routers/auth.py` and
`app/routers/mfa.py`'s docstrings.

### 5. Run tests

```
cd backend
pytest -q                              # everything -- unit tests always run;
                                        # live-Postgres RLS/concurrency suites
                                        # self-skip (not fail) if BGP_DATABASE_URL/
                                        # BGP_MIGRATION_DATABASE_URL don't
                                        # resolve to a reachable database.
pytest -q -k "not tenant_isolation_rls and not decision_concurrency"
                                        # unit/integration tests only, no
                                        # database required at all (SQLite
                                        # in-memory).
```

A skipped Postgres-only test is **not the same claim as a passed one** — check
the pytest summary line for a nonzero `skipped` count, and don't read a
"unit tests pass" run as proof the live-Postgres guarantees (RLS isolation,
row-locking, the SELECT+INSERT-only append-only grants) actually hold. No
linting or formatting is configured yet (tracker item #120 stays "In
progress" for that reason).

### Persistent keys (read this before using a database that survives a restart)

`BGP_SESSION_SECRET_KEY` and `BGP_MFA_ENCRYPTION_KEY` default to a fresh
random value generated **per process start** if unset. That's a safe default
for a throwaway dev loop (restarting just logs everyone out — an honest
failure mode, not a leaked or guessable shared key), but it is actively wrong
for a persistent `bgp_dev` database: every restart with a new random
`BGP_MFA_ENCRYPTION_KEY` makes every previously-enrolled user's stored MFA
secret permanently undecryptable (Fernet has no key-rotation/re-encryption
path yet — see `app/security.py`'s `encrypt_mfa_secret` docstring), and a new
`BGP_SESSION_SECRET_KEY` invalidates every existing session cookie. Set both
explicitly in `backend/.env` (step 3) the first time you create a database
you intend to keep using.

## Known limitations

- **No frontend** (DEC04 unresolved) — REQ-033's guided-form back-navigation
  and REQ-039's timezone display/translation are frontend-only concerns this
  backend cannot satisfy alone.
- **Decision durability** (DEC05) is unresolved — a decision commits
  atomically to this single local Postgres instance only; no
  synchronous-replication or pending-receipt semantics exist.
- **Integrity checkpoint custody** is enforced by RLS in the same Postgres
  instance, not a genuinely separate system — see
  `app/models.py`'s `IntegrityCheckpoint` docstring for exactly what this
  does and does not prove.
- **BGP_Development_Review_Findings_v1.0.pdf** findings BGP-F01–F04 (session-
  bound MFA, an authenticated compensating review, decision-check
  concurrency, and export/import history preservation) are fixed as of
  2026-09-17 — see `TRACKER.md` for each fix's detail and the tests that
  prove it. That review, like this README, was authored by an AI agent, not
  independently reviewed — see the Authority and scope section above.
- No CI run has been deliberately broken (e.g. a reintroduced tenant leak,
  or a reverted lock) to prove a relevant check actually goes red, not only
  that it currently passes.

## Requirement ledger

The authoritative, versioned requirement ledger is
`docs/blueprint/Requirements_Catalogue.json` (58 requirements, 23 acceptance
cases, 7 prototype remediation findings, 14 work packages, 12 decisions).
Identifiers are stable across revisions — see Blueprint Section 8 for the
change-control rule before editing it.
