# Threat model and privacy assessment (REQ-044)

**Status: drafted 2026-09-16, not independently reviewed.** See [README.md](README.md) for what
that means. This document is authored against the code actually in the repository as of this
date (WP01/WP03/WP04/WP05), plus the design already approved for later work packages in
`docs/blueprint/Blueprint_Working_Source.md`. Where a threat targets a component that does not
exist yet, it is marked **planned surface** and carries no test evidence — it exists so the
threat isn't forgotten by the time that work package starts, not to claim it's mitigated already.

REQ-044 (blueprint line 440-446) requires threat-modelling **tenancy, template escalation,
evidence/audit abuse, enumeration, attachments and billing**, plus a privacy assessment. Each is
covered below in its own section.

## 1. Tenancy

| # | Threat | Mitigation (as built) | Residual risk |
| --- | --- | --- | --- |
| T1.1 | A request forges or guesses another tenant's ID to read/write its rows. | PostgreSQL RLS on every tenant-owned table (`memberships`, `invitations`, `tenant_access_events`, and templates' tenant-scoped rows since WP05), enforced through the restricted `bgp_app` role — not application-layer filtering alone. Verified against live Postgres 2026-09-16 (`backend/tests/test_tenant_isolation_rls.py`, 7 tests incl. `test_cross_tenant_row_is_invisible_even_by_direct_id`). | RLS policies only exist for the tables built so far. Every future tenant-owned table (Project, GateOccurrence, EvidenceItem, DecisionRecord, etc. — WP06/WP07) must repeat this pattern; nothing enforces that structurally yet except code review discipline. |
| T1.2 | A pooled/reused database connection carries tenant A's context into a request for tenant B. | `SET LOCAL app.tenant_id` inside each transaction; Postgres clears `LOCAL` settings at transaction end regardless of pooling. Verified: `test_pooled_connection_reset_between_tenants`. | Only the app's own connection pool is verified this way. Any future background worker, cache, or search index (blueprint's own REQ-008 lists these explicitly) needs its own equivalent context-reset discipline — **planned surface**, no worker/cache/search component exists yet. |
| T1.3 | The application role bypasses or disables RLS (misconfiguration, compromised app credentials, bad migration). | `bgp_app` is a separate, restricted role from `bgp_owner` (table owner); `NOBYPASSRLS`; `FORCE ROW LEVEL SECURITY` set on every tenant-owned table so even ownership drift wouldn't create an exemption. Verified: `test_app_role_cannot_disable_row_level_security`, `test_app_role_cannot_alter_or_drop_the_table`. | For `bgp_app` specifically: none identified beyond what's already tested. See **T1.6** below for a real, distinct finding about the *owner* role that this line does not cover. |
| T1.4 | A weakened or missing RLS policy goes unnoticed because the test suite always passes trivially (no real leak to catch). | `test_seeded_leak_in_rls_policy_is_detected` (added 2026-09-16) deliberately weakens the `memberships` policy, proves the leak is observable through `bgp_app`, then restores and re-verifies. | Only exercised for `memberships`. The same seeded-leak proof should be repeated for `invitations`, `tenant_access_events`, and templates' tenant-scoped tables before WP04/WP05 evidence is treated as fully proven — **open follow-up**, not done in this pass. |
| T1.5 | Cross-tenant enumeration via non-DB channels (URL structure, error messages, timing). | Blueprint §5.3 API contract states responses "must not disclose another tenant's object existence" and specifies 404 for absent-or-concealed. Not yet implemented or tested — **planned surface**; current API surface (`app/routers/`) is auth/org/mfa/templates only, no cross-tenant-guessable object routes exist yet to test against. | Real risk once Project/GateOccurrence/EvidenceItem routes (WP06+) exist. Revisit this threat when those routers are built. |
| T1.6 | **Confirmed, not hypothetical — found 2026-09-17.** `bgp_owner` (the migration/table-owner role) was, in the live dev database, an actual Postgres superuser (`rolsuper=true`), despite `setup_postgres_dev.sql` specifying `NOSUPERUSER`. A superuser unconditionally bypasses RLS regardless of `FORCE ROW LEVEL SECURITY` — meaning every "even the table owner can't tamper" claim made anywhere in this project since WP04 was **untested and false** for `bgp_owner` specifically, until this was caught while building WP08's `integrity_checkpoints` (a test that should have been impossible to pass, passed). `bgp_app`'s restrictions (T1.3, GRANT-based, not RLS-based) were never affected. | `ALTER ROLE bgp_owner NOSUPERUSER` (2026-09-17). Verified via `pg_roles.rolsuper` directly, and via re-running every owner-role RLS test (which then correctly started failing until their fixtures were fixed to set `app.tenant_id` per tenant — see TRACKER.md 2026-09-17 for the full account). New tests added: `test_wp08_tenant_isolation_rls.py`'s owner-cannot-tamper suite exercises this specifically. | How this role became superuser in the first place was never root-caused (created outside an agent session, via pgAdmin, by the user) — nothing currently *prevents* a role from being handed superuser by mistake again. No automated check exists that would catch this drifting back; periodically re-running `SELECT rolname, rolsuper FROM pg_roles` against the small, fixed set of expected roles is a cheap manual check worth doing occasionally, not yet automated into CI. |

## 2. Template escalation

`app/rule_engine.py` (WP05) is the only place tenant-authored content is interpreted as logic.

| # | Threat | Mitigation (as built) | Residual risk |
| --- | --- | --- | --- |
| T2.1 | A tenant-authored template rule executes arbitrary code. | The rule vocabulary has no expression/eval field at all — `Condition` only supports `eq`/`in`/`all`/`any` over declared facts (Pydantic-validated, `rule_engine.py` lines 44-81). Nothing in the module ever calls `eval`/`exec` or a template engine on tenant input. Verified: `test_rejects_unknown_operator`. | None identified for the current vocabulary. If the vocabulary is ever extended (DEC07 is still open per `WP05` commit notes), any new operator must be re-reviewed against this same "no expression field" property. |
| T2.2 | A rule references a platform-invariant fact to disable a control it shouldn't be able to touch (e.g. `bypass_mfa`, `disable_audit`). | `PROHIBITED_FACTS` set, checked in a Pydantic field validator (`rule_engine.py` lines 27-35, 54-59). Verified: `test_rejects_prohibited_fact`. | The prohibited-facts list is a fixed enumeration maintained by hand. It must be revisited every time a new platform invariant is added elsewhere in the codebase — nothing cross-checks the list against, say, the set of invariants described in blueprint §2.2 automatically. |
| T2.3 | Unbounded or deeply nested rule conditions cause a denial-of-service on template validation/evaluation. | `MAX_CONDITION_DEPTH = 5`, enforced in `Rule._bounded_depth`. Verified: `test_rejects_excessive_nesting`. | Depth limit of 5 is this session's working choice per WP05's own commit notes, not a technical-lead-approved figure (DEC07 open). |
| T2.4 | A published template is edited after the fact, letting a tenant retroactively change what a prior decision was actually evaluated against. | `TemplateVersion.status` transitions to published are treated as immutable at the router level (`app/routers/templates.py`); uniqueness constraint on `(template_id, version_number)`. Verified: `test_edit_draft_then_publish_then_edit_rejected`. | Immutability is enforced in application code, not a DB trigger/constraint (documented as a known simplification in `models.py`'s `TemplateVersion` docstring) — a direct DB write by a future internal tool could bypass it. Revisit once any admin/internal tooling is built. |

## 3. Evidence / audit abuse

**Planned surface — no EvidenceItem, EvidenceRevision, AuditEvent, or Checkpoint tables exist
yet** (blueprint §5.2; scheduled for WP06/WP07/WP08). Recorded here so the threat isn't
forgotten, not because it's mitigated:

- A contributor could try to self-approve evidence they uploaded — blueprint §2 explicitly denies
  this authority boundary ("Cannot approve solely because they uploaded evidence"); must be
  enforced server-side when the Evidence/Decision routers are built, not left to UI hiding alone.
- Audit history must be append-only with protected ordering (blueprint §5.2 `AuditEvent /
  Checkpoint`: "event digest and independent checkpoint reference") — this needs its own
  tamper-evidence design before WP08, not an afterthought bolted onto WP06/WP07.
- Deletion cascades must not erase decision or audit history (blueprint §5.2, stated as a
  required constraint) — every future foreign key from a tenant-owned child table needs this
  checked explicitly at migration-review time.

## 4. Enumeration

Covered partly under T1.5 above (tenant enumeration). Additional identifier-enumeration surface:

- User/tenant IDs are UUIDv4 (`_uuid` helper in `models.py`), not sequential integers — resists
  naive incrementing enumeration by construction.
- Invitation tokens are stored as `token_hash`, never the raw token, and are unique
  (`Invitation.token_hash`, `models.py` line 97) — a leaked database row can't be replayed as a
  live invitation token.
- No rate-limiting exists yet on any auth or invitation-accept endpoint — **planned surface**,
  open gap for brute-force/timing-based enumeration of valid emails via login or invitation
  accept. Should be scoped before WP03's identity surface is considered release-ready (ties to
  G4.04 "security... testing" in the tracker, not yet started).

## 5. Attachments

**Planned surface — WP14 (Optional and paid capabilities), not built.** Blueprint §5.2
`AttachmentVersion` already specifies "Downloads only after clean scan and authorised signing"
and a `classification` field. No threat analysis beyond restating that requirement is useful
until the component exists; revisit at WP14 kickoff.

## 6. Billing

**Planned surface — WP14, not built.** Blueprint §2.1: "Billing must be accepted before charging
customers." No payment integration exists in this codebase. Revisit at WP14 kickoff — likely
threats (stored-card handling, webhook forgery, plan-tier privilege escalation) are standard for
whatever payment processor is chosen and should be modelled against that processor's actual
integration surface, not guessed at generically now.

## 7. Cross-cutting finding: hardcoded session signing key

Not one of REQ-044's six named categories, but found while grounding this document in the actual
code and too concrete to leave unrecorded: `app/security.py` line 12 hardcodes
`_SESSION_SERIALIZER = URLSafeTimedSerializer(secret_key="local-synthetic-prototype-key")`. Every
session token this prototype issues is signed with a fixed, source-committed key — anyone with
read access to this repository can forge a valid session token for any `user_id`. The code
comment already says this is WP01/WP03 prototype-only and that rotation/secure storage are
REQ-045/DEC11, not settled yet — this document is not raising a new fact, just making sure it's
tracked as a threat-model line item rather than only a code comment. **Must be resolved before
any environment other than a local synthetic-data prototype uses this code** (ties to REQ-045,
WP12, and G4.04 in the tracker — none started).

## Privacy assessment

Scope: personal data actually collected by the code that exists today (Tenant/User/Membership/
Invitation/MfaRecoveryCode — WP03; Template/TemplateVersion carry no personal data beyond an
optional `created_by_user_id` reference — WP05).

| Data element | Where | Purpose | Notes |
| --- | --- | --- | --- |
| Email address | `users.email` | Login identifier, notifications (not yet built) | Unique, required. Also stored unhashed in `invitations.email` for pending invites. |
| Password hash | `users.password_hash` | Authentication | Hashed at rest (see `app/routers/auth.py`); never logged or returned in any response schema (`UserOut` excludes it). |
| MFA secret | `users.mfa_secret` | TOTP-based MFA (REQ-002) | Stored in the clear in this prototype (`String(64)` column, no encryption-at-column marker) — **flagged, not mitigated**: production secret storage/rotation is explicitly REQ-045, assigned to WP12, not WP03. Do not treat current storage as production-ready. |
| MFA recovery codes | `mfa_recovery_codes.code_hash` | Account recovery | Hashed, single-use (`used_at`), consuming one forces re-enrolment — matches REQ-002's "recovery restores access only after identity checks and MFA re-enrolment". |
| Tenant-access audit trail | `tenant_access_events` | REQ-005: record tenant-administrator access outside their membership, visible to the sponsor | Retains `actor_user_id` — a personal-data linkage that must respect whatever retention floor `data_retention_policy.md` sets once that's independently reviewed. |

Data-handling decisions still open, explicitly not decided by this document (per REQ-044's own
verification text, these are for independent reviewers to record, not for a drafting pass to
settle):

1. Whether `mfa_secret` needs column-level encryption before this leaves prototype status (WP12
   scope, REQ-045) — flagged above, not resolved here.
2. Retention period for `tenant_access_events` and other audit-adjacent tables — see
   `data_retention_policy.md`, itself still pending review.
3. Whether invitation email addresses for never-accepted, expired invitations should be purged
   on a schedule, or retained for abuse-pattern detection — no decision recorded either way.
