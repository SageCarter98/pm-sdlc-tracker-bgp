# Governance tracking for this project

This project is registered under the KenAddme IT Links PM Framework v1.1 and
SDLC Framework v1.2 (mandatory institutional governance on this machine,
independent of what this repository builds).

- Classification: **PM Class A — Strategic / High Risk**, **SDLC Class 3 —
  High**. Rationale is recorded on the tracker project record (sensitive
  personal/organisation data, identity and MFA, multi-tenant isolation,
  cybersecurity risk, billing, 14 work packages across 8+ role leads — not
  Class 4, since nothing here is safety-significant or critical-infrastructure).
- Tracked in the `tracker_<slug>` MySQL database via
  `~/.claude/skills/pm-sdlc-tracker/tracker_cli.py`, project id 1.
- Check current gate status with:
  ```
  python "%USERPROFILE%\.claude\skills\pm-sdlc-tracker\tracker_cli.py" --project-dir "C:\Projects\PM_SDLC Tracker" status
  ```

## What's been verified so far (2026-09-15)

SDLC G1 (Requirements baseline): 7 of 12 items Complete, backed by specific
evidence in `docs/blueprint/` (requirements catalogue, NFRs, journeys,
acceptance criteria, traceability). The remaining 5 are **In progress**, not
Complete, because:

- No Public/Internal/Confidential/Restricted data classification scheme exists
  yet in the pack.
- Requirements have only owner adoption (APR-001, a single chat instruction) —
  the blueprint itself says this is not an independent or stakeholder review.
- No explicit requirement-quality-rule review is documented.
- The DEC01–DEC12 open-question log has accountable roles and gate-linked
  deadlines but no named individuals or calendar dates.

PM Gates 1–2 and SDLC G0 remain mostly **Not started** in the tracker: the
documents that would evidence intake/authorisation (Project Directive v1.2,
the earlier `file.zip`/`2.zip` referenced in Blueprint Section 8) are not
present in this repository, so they cannot be verified from here — do not
mark them Complete without locating and checking those source documents.

## Named roles (2026-09-15)

**DEC01 (named delivery lead and independent reviewer) is resolved**: delivery
lead is Freston Kenny Adedeme; independent reviewer is Milton. Recorded on the
tracker project record (`project-manager`) and evidence item G0.03 (id 86,
"Named sponsor, delivery lead and technical owner" — In progress: lead and
reviewer named, sponsor and technical owner still open).

Naming the reviewer is not the same as a completed review — Milton's
independence from delivery work and role acceptance haven't been separately
confirmed, and no review has actually happened yet. Don't infer review sign-off
occurred just because the role is now named; track each actual review as its
own evidence update when it happens.

## Work packages built so far (2026-09-16)

- **WP01** (repository/delivery controls) and **WP03** (identity/membership,
  local prototype) are committed and tested against SQLite. G3 items #115
  (source control) and #119 (tests) marked Complete; #121 (CI results) and
  #126 (deviation log) are In progress. **#124 (AI-generated code reviewed by
  a competent human) is deliberately left Not started — Milton has not
  reviewed any of this code yet. Don't let anything here be treated as
  accepted until he has.**
- **WP04** (tenant isolation via PostgreSQL RLS): migrations, restricted-role
  grants and the adversarial cross-tenant test suite (REQ-007/008/009) are
  now **verified against real local Postgres (2026-09-16)**, not just
  written — `alembic upgrade head` applied cleanly to `bgp_dev`
  (`bgp_owner`/`bgp_app` roles created via
  `backend/scripts/setup_postgres_dev.sql` + `reset_dev_passwords.ps1`), and
  the full backend suite is 48/48 passing, including all 6 previously-skipped
  RLS tests. A 7th test, `test_seeded_leak_in_rls_policy_is_detected`, was
  added the same day to satisfy REQ-009's "demonstrate detection of a seeded
  leak" clause directly: it commits a deliberately permissive policy, proves
  bgp_app can then see cross-tenant rows, restores the real policy, and
  re-verifies isolation before finishing (loud `pytest.fail` if the restore
  itself doesn't fully take, never a silent leftover weakened policy).
  `.github/workflows/ci.yml` has provisioned a Postgres service, both roles
  and `alembic upgrade head` since WP04 — **that wiring has still never
  actually executed**. A private GitHub remote (`origin`,
  `github.com/SageCarter98/pm-sdlc-tracker-bgp`) was created 2026-09-16, but
  nothing has been pushed yet (deliberate — pushing is a separate, more
  consequential decision than creating the remote). REQ-009's "blocking CI
  check" clause stays an open gap until a real CI run is observed passing
  (and, ideally, failing on a reintroduced leak) — don't round that part up
  to Complete from the local config alone.
- **WP05** (templates and declarative rule interpreter) is committed and
  tested: the Sec.5.5 rule vocabulary (equality/membership/bounded-all-any
  only, no eval/exec, max nesting depth 5, a fixed prohibited-facts list
  blocking things like `disable_audit`), template create/fork/import/publish
  with publish-time immutability, and three neutral fictional framework
  fixtures (not real KenAddme content — DEC03 licensing is still unresolved,
  so REQ-014's neutral-starter fallback applies). Its RLS policy for
  templates is included in the same 48/48-passing live-Postgres verification
  recorded above for WP04.
- **WP02 (Discovery and assurance decisions) — built 2026-09-16, retroactively.**
  WP05 lists `WP01 WP02` as its dependencies (blueprint §6), but WP02 had
  never been done when WP05 was built — a real, unflagged sequencing
  deviation, only caught when directly asked "is the implementation plan
  being followed?" on 2026-09-16. Closed out per the user's instruction to
  follow the plan: five documents drafted under `docs/wp02/` (see
  `docs/wp02/README.md` for the index) covering REQ-044 (threat model +
  privacy assessment, incl. one new finding — a hardcoded session-signing key
  in `app/security.py`, already flagged in-code as prototype-only but now
  also tracked as a threat-model line item), REQ-048 (retention/legal-hold
  policy proposal — proposed floors explicitly marked as unconfirmed
  defaults, not blueprint-mandated figures), REQ-057 (assurance plan — states
  the Class A 3/6-month benefits-review cadence but does **not** invent a
  budget or capacity number, per that requirement's own verification text),
  the data classification scheme flagged missing since 2026-09-15
  (G1.06), and a market/roles consolidation. **None of this is
  independently reviewed** — tracker items #97 and #109 moved to "Submitted
  for review", #105 stays "In progress" (it has real open inputs: no Sponsor
  named yet to approve budget, no Gate 2 decision yet to anchor benefits-
  review dates). Same discipline as everywhere else in this project: drafted
  by an AI assistant is not the same as reviewed by Milton.
- **WP06** (projects and evidence revisions) — built 2026-09-16, same session
  as WP02, continuing the recovered implementation-plan order (depends on
  WP04+WP05, both real by this point). New tables: `projects`,
  `project_memberships`, `gate_occurrences`, `evidence_items`,
  `evidence_revisions` (migration `0004_wp06_projects`, same RLS policy
  shape as WP04, applied and verified against live `bgp_dev`). Implements
  REQ-015 (atomic project creation — a monkeypatched mid-seed failure test,
  `test_seeding_failure_leaves_no_project_row`, proves zero rows persist on
  a partial failure, not just that the happy path works), REQ-016 (routine
  vs. triggered gate reviews are separate `GateOccurrence` rows with their
  own evidence, never shared — a gate with only triggered rules gets no
  automatic occurrence at project creation), REQ-017 (evidence edits are
  INSERT-only new `EvidenceRevision` rows, never UPDATEs, each carrying
  `actor_user_id`), REQ-018 (a required item cannot be marked Complete
  without a reference — since every revision replaces the full record
  rather than patching one field, this is the only way REQ-018's "do not
  allow removal of required evidence while Complete" can be violated, so
  blocking it there is sufficient), and REQ-019 (`source_version`/
  `source_hash` accepted as explicitly disclosed fields, never inferred by
  sniffing the reference string). 61/61 backend tests passing (13 new: 9 in
  `test_projects.py`, 4 in `test_wp06_tenant_isolation_rls.py` extending the
  WP04 seeded-leak proof to the `projects` table specifically, per the
  threat model's own T1.4 follow-up). **Known scope gaps, not rounded up**:
  concurrent-occurrence-creation races are handled by the DB unique
  constraint (a losing request gets 409) but not retried automatically, and
  the seeded-leak proof was only repeated for `projects`, not the other
  four new tables, which share the same migration-generated policy but
  aren't independently re-verified.
- **WP07** (decisions and exceptions) — built 2026-09-16, same session,
  continuing the recovered plan order (depends on WP06+WP03, both real).
  New tables: `exception_records`, `decision_records`, `idempotency_records`,
  `audit_events` (migration `0005_wp07_decisions`; also backfills
  `evidence_items.blocker_level`, which WP06 had collapsed into a single
  `required` bool — REQ-022's conditional-approval logic needs the
  hard/conditional/advisory distinction back). New router
  `app/routers/decisions.py`. Implements REQ-020/021 (exceptions: authority,
  scope and expiry are all re-checked live against server time and current
  role membership at every readiness computation — never read from a typed
  `status` field alone; revocation preserves the row rather than deleting
  it), REQ-022 (conditional approval requires owner + a future deadline +
  at least one condition; a hard blocker denies any approval outcome,
  conditions can only defer a *conditional* blocker), REQ-023/024
  (idempotent, append-only decision recording — an `Idempotency-Key` header
  + `(tenant, actor, operation, key)` uniqueness makes a retried identical
  request return the original decision rather than erroring or duplicating;
  a changed payload under the same key is a 409, not a silent overwrite),
  REQ-025 (decisions are correctable only via a new superseding row with a
  mandatory reason — enforced not just by which routes exist but at the
  **database role level**: `bgp_app`'s grant on `decision_records` is
  SELECT+INSERT only, no UPDATE/DELETE, proven live against Postgres in
  `test_wp07_tenant_isolation_rls.py`), and REQ-006 (separation of duties —
  a decision where the sole preparer of every required item is also the
  decider is rejected unless a named, independent, non-empty-noted
  compensating reviewer is supplied). REQ-021's "reassess... trigger
  reassessment" requirement is satisfied by construction rather than by a
  worker: readiness (blockers, manifest digest) is recomputed fresh on
  every preview/decide call, so there is nothing cached that could go
  stale or need an explicit trigger. 74/74 backend tests passing (+13 from
  WP07: 9 functional, 4 live-Postgres role/isolation proofs).

  **Explicitly not implemented, not rounded up**: Blueprint Sec.5.4 step 7
  (durability) depends on **DEC05**, which is still an open architectural
  decision (candidate synchronous-replication vs. pending-intent-plus-
  receipt semantics) — this pass commits atomically to the single local
  Postgres instance and nothing more; a 201 response here does not carry
  DEC05's eventual durability guarantee, whichever candidate gets chosen.
  REQ-022's "activity limits" on conditional approval are not enforced
  (no route yet restricts what a conditionally-approved project may do).
  The full Sec.5.2 `AuditEvent`/`Checkpoint` tamper-evidence design (event
  digest, independent checkpoint custody — REQ-026/027) is WP08's job, not
  built here; `audit_events` in this pass is a plain append-only log.
- **WP08** (integrity and recovery) — built 2026-09-17. Depends on
  WP07+WP02 (blueprint §6), both real. Before writing any code, checked
  whether REQ-026/027/028/029 were actually buildable: REQ-026 ("detect
  privileged tampering... with defined custody"), REQ-028 (zero
  acknowledged-decision loss) and REQ-029 (backup/restore with RPO/RTO
  targets) all trace to **DEC05**, still an open architectural decision
  assigned to Operations/Security leads — the blueprint itself warns
  (line 704) "a stored hash chain alone neither prevents privileged
  rewriting nor proves disaster durability." User's call: build what's
  genuinely testable now, flag the DEC05-gated remainder honestly rather
  than skip the whole work package or fake full compliance.

  **Built and verified live against Postgres**:
  - REQ-026/027: `integrity_checkpoints` (hash-chain over `audit_events`,
    migration `0006_wp08_integrity`) + `integrity_incidents`, new module
    `app/integrity.py`, new router `app/routers/integrity.py`. An open
    incident blocks new decisions project-wide (REQ-027,
    `app/routers/decisions.py`, HTTP 423). `integrity_checkpoints` is
    genuinely append-only to **every** role including `bgp_owner` (an
    explicit `USING (false)` RLS policy on UPDATE/DELETE — see below for
    why "just omit the policy" didn't work).
  - REQ-028 (partial, honestly scoped): `test_decision_commit_failure_leaves_no_partial_state`
    proves a crash at commit time never leaves a torn DecisionRecord/
    AuditEvent/IdempotencyRecord. This proves **local** atomicity only —
    it says nothing about node/zone/region failure domains, which stay
    DEC05's job.
  - REQ-029: `backend/scripts/restore_drill.py` — a real, runnable backup →
    restore-into-clean-database → reconciliation drill, actually executed
    2026-09-17 against live `bgp_dev`: backup 1.18s, restore 4.14s, row
    counts matched across 16 tables, hash-chain re-verified against every
    project in the restored copy. One expected, understood "MISMATCH" in
    that last check: 12 leftover checkpoints from
    `test_wp08_tenant_isolation_rls.py`'s fixture carry a fabricated
    `chain_digest='original-digest'` with zero matching `audit_events` —
    `verify_integrity()` correctly flags that as inconsistent; it is not a
    restore defect. **Honest limits**: single local Postgres instance,
    near-empty database — proves the mechanism works end to end, not a
    production-scale RPO/RTO number, and covers none of DEC05's
    multi-node/zone/region failure domains.

  **A significant bug found and fixed while building this, worth its own
  line**: `bgp_owner` had been created as an actual Postgres **superuser**
  (`rolsuper=true`) at some point outside this session's control — despite
  `setup_postgres_dev.sql` specifying `NOSUPERUSER`. A superuser
  unconditionally bypasses RLS regardless of `FORCE ROW LEVEL SECURITY`,
  which silently meant every "even the table owner can't tamper" claim
  this project had been making since WP04 was **untested and false** for
  the owner role specifically (bgp_app's restrictions, which are
  GRANT-based not RLS-based, were unaffected and remained real). Found via
  `integrity_checkpoints`' own test failing in a way that shouldn't have
  been possible. Fixed: `ALTER ROLE bgp_owner NOSUPERUSER`. Fixing it broke
  18 other tests whose fixtures had never actually needed
  `SET app.tenant_id` before owner-role inserts, because bgp_owner's
  (buggy) superuser status was silently covering for it — all fixed
  properly (each tenant's rows seeded under its own
  `SET LOCAL app.tenant_id`, matching the app's own correct pattern in
  `app/deps.py`, not the plain session-level `SET` the fixtures had used
  before, which itself risked leaking a stale tenant context across pooled
  connections between tests). Also found, separately: an RLS policy that
  simply *omits* an UPDATE/DELETE policy does **not** deny those
  commands under FORCE — Postgres falls back to the SELECT policy's USING
  clause. An explicit `USING (false)` policy was required to actually
  deny. And separately again, while building the REQ-029 drill: a
  correctly-RLS-restricted `bgp_owner` cannot be dumped by `pg_dump` at
  all (no per-row tenant context) — required a new dedicated
  `bgp_backup` role (`BYPASSRLS`, `pg_read_all_data`, `CREATEDB`, nothing
  else) created via pgAdmin, which itself needed two follow-up fixes for
  PG16-specific inheritance behavior (`ALTER ROLE ... INHERIT` doesn't
  retroactively fix an already-granted membership's `inherit_option` —
  needed `GRANT ... WITH INHERIT TRUE` instead). Every one of these was a
  real, previously-invisible correctness gap that only surfaced from
  actually running things against live Postgres rather than trusting the
  migration code's intent — the whole reason this project insists on
  live-Postgres verification instead of taking WP04-08's RLS claims on
  faith.

  84/84 backend tests passing after all of the above (was 81 before WP08's
  own 10 new tests, net after the fixture fixes).
- **WP09** (export and import) — built 2026-09-17. Depends on WP06+WP07
  (blueprint §6), both real. New tables `export_jobs`, `import_jobs`,
  `imported_actor_provenance` (migration `0007_wp09_export_import`, same
  RLS shape as WP06/07, applied and verified live), new router
  `app/routers/exports.py`.

  **Deliberate scope decision, made explicit rather than silently
  assumed**: only *current state* (templates/versions, projects/
  memberships, occurrences, evidence items — each recreated as a single
  fresh baseline revision) is re-created as live rows on import.
  Decisions, exceptions, audit events and integrity checkpoints export as
  read-only historical sections in the archive but are **not** re-inserted
  as live governance rows. Rationale: Blueprint Sec.5.6 warns "legacy
  missing attribution is labelled as missing; it is never reconstructed as
  a verified approval" — recreating a *live* `DecisionRecord`/
  `ExceptionRecord` under its original historical actor is exactly that
  reconstruction, and those tables' actor columns are NOT NULL in a way a
  genuinely unmatched historical actor can't honestly satisfy without
  either fabricating an actor or relaxing a constraint that exists for
  good reason. Whether/how live decision history should carry across an
  import is a real product question, left open rather than decided here.

  REQ-030 ("lossless clean-instance re-import without privilege
  transfer"): every imported row gets a fresh id (never reuses the
  archive's original ids); imported actors are matched to real local users
  only by e-mail via `ImportedActorProvenance`, re-checked live at commit
  time (not trusted from the earlier validate() report, same discipline as
  `decisions.py`'s stale-manifest check); an unmatched actor on a NOT-NULL
  column falls back to the importing user, never a fabricated identity —
  proven by `test_unmatched_actor_falls_back_to_importer_not_fabricated`.
  Each archive section carries its own sha256 digest in the manifest,
  making the archive self-verifying without needing the original
  `ExportJob` row (important since import may happen on a different,
  fresh instance) — `test_tampered_archive_is_rejected_at_validation`
  proves a single-field edit is caught. REQ-031 (own-data export always
  available): export has no role gate beyond active membership and no
  billing-tier gate to remove later, since billing tiers aren't built yet
  (WP14) — correctly nothing to gate on, not an oversight.

  A real bug caught by running the SQLite suite, not just live Postgres:
  the first draft passed exported timestamps (serialized to ISO strings
  for JSON transport) straight back into the ORM on import without
  parsing them back to `datetime` objects. SQLite's DateTime type rejects
  a bare string outright and caught this immediately; Postgres would have
  silently accepted the string via psycopg2's adapter, masking the bug on
  the one dialect this project otherwise insists on testing live — a
  concrete case for why both test paths matter, not just Postgres.

  94/94 backend tests passing (+10: 7 functional, 3 live-Postgres
  isolation on `export_jobs`).
- **DEC07 (rule vocabulary/third framework) is still open** — WP05
  implements the schema shape Sec.5.5 already approved, but the "exact
  vocabulary and limits" the blueprint reserves for DEC07 are this
  session's working choices, not a technical-lead sign-off. Don't treat the
  prohibited-facts list or the depth-5 limit as settled without that review.
- Still Not started across WP03/WP04/WP05/WP06/WP07/WP08/WP09: #124
  (AI-generated code reviewed by a human). Eight work packages in, zero of
  them reviewed by Milton.

## Rules for updating this tracker as work proceeds

1. Draft candidate evidence matches, then **verify each one against the actual
   file/commit/PR before writing a status**, never on a paraphrase.
2. Complete requires a specific, locatable, checked evidence reference.
   Partial or unverifiable stays "In progress" with an honest note.
3. **Never record a gate `decision` from code or documents alone.** A gate
   decision is the named authority's action (Sponsor/Project Authority per the
   PM Framework; delivery lead/independent reviewer sign-off per SDLC), taken
   manually via `tracker_cli.py gate` — naming DEC01's roles is not a gate
   decision and doesn't substitute for one.
