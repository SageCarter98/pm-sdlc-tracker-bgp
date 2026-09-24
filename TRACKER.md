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
  and `alembic upgrade head` since WP04. **Update 2026-09-17: pushed to the
  private remote (`origin`, `github.com/SageCarter98/pm-sdlc-tracker-bgp`,
  created 2026-09-16) and the resulting CI run is real and green** — run
  [35185824036](https://github.com/SageCarter98/pm-sdlc-tracker-bgp/actions/runs/35185824036):
  `pytest -q` (112/112 at that commit), including the
  adversarial cross-tenant suite, passed on a real GitHub Actions runner
  against a real Postgres service container, not just locally. REQ-009's
  "blocking CI check" clause is now genuinely satisfied — this closes the
  gap flagged since WP04. (The first attempt, run 35185489159, failed at
  the secret-scan step for an unrelated reason — a `gitleaks-action`
  git-diff-range bug on a repo's first-ever push, not a leaked secret; see
  the WP12 entry below and the CI fix commit `6f58cc6` for the full
  account.) Still not demonstrated live: a run failing red on a
  reintroduced leak — the local `test_seeded_leak_in_rls_policy_is_detected`
  proves the suite itself catches it, but no CI run has been deliberately
  broken to watch it go red end-to-end.
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
- **WP10** (essential user journeys) — built 2026-09-17. Depends on
  WP03+WP06+WP07 (blueprint §6), all real. Genuinely mixed scope, checked
  against the blueprint before writing code rather than assumed: REQ-032/
  034/036/037 are backend-buildable; REQ-033 (guided-form back-navigation
  preserving input) and REQ-039's display half (timezone rendering,
  translation structure) are frontend-only concerns — **no frontend exists
  yet, DEC04 is still unresolved**, same shape of honest limitation as
  WP08's DEC05 gate, just a different open decision. Built what's
  buildable, named what isn't, same as every WP so far.

  - **REQ-034** (save/resume drafts): new `drafts` table (migration
    `0008_wp10_drafts`) + `app/routers/drafts.py`. Owner-scoped per user
    within a tenant (never visible to another user, even a tenant
    administrator) — enforced at the application layer, not RLS, since
    the existing `app.tenant_id` session variable only expresses
    tenant-level scoping; a second session variable for per-user scoping
    was judged not worth the complexity for a same-tenant,
    non-adversarial-within-tenant requirement. Same optimistic-concurrency
    `base_revision` pattern as evidence revisions.
  - **REQ-036/037** (plain-language blockers + permitted-progression
    confirmation summary): `app/routers/decisions.py`'s preview endpoint
    now returns `blocker_explanations` (plain-language reason +
    corrective-action API call per blocker) and `permitted_outcomes`
    (every outcome current readiness would allow, not just the one
    outcome the caller happened to query) — additive fields, nothing
    existing changed shape.
  - **REQ-032** (My work: project, reason, deadline, state, direct
    action): `GET /my-work` now wraps each item with `project_name`,
    `reason` ("why is this yours"), and `direct_action` (the literal next
    API call) — `deadline`/`state` were already on the item
    (`due_date`/`status`).
  - **REQ-035** (pending vs. confirmed approvals, retrieve outcome after
    timeout): already substantially satisfied by WP07 (Idempotency-Key +
    `GET /decisions/{id}`) — verified, not rebuilt. One honest gap not
    rounded up: there is no live "Pending" decision status distinct from
    "committed", because that distinction is DEC05 Candidate B's own
    concept (pending intent + durable receipt) — same DEC05 gate as
    WP07/WP08's durability gaps, not a WP10 omission.

  103/103 backend tests passing (+9: 4 draft tests, 1 preview-enrichment
  test, 1 my-work-enrichment test, 3 live-Postgres isolation on `drafts`).
- **WP12** (operations and hardening) — built 2026-09-17. Depends on
  WP04+WP08 (blueprint §6), both real. Scoped against the blueprint before
  coding, same discipline as every WP since WP08: REQ-045/046/047 are
  backend/CI-buildable; REQ-043's numeric performance-budget *approval* is
  DEC08-gated, and a real 99.5% monthly-availability baseline needs
  production traffic history this local prototype has never had and can't
  honestly fabricate — only the measurement mechanism was built.

  - **REQ-045** closes two real, previously-named gaps directly:
    `app/security.py`'s hardcoded session-signing key (threat model
    finding, `docs/wp02/threat_model_and_privacy_assessment.md` §7) is now
    `settings.session_secret_key`, env-overridable with a safe
    random-per-process default -- no more literal secret committed to
    source. `users.mfa_secret` (same threat model doc's privacy section,
    "stored in the clear... flagged, not mitigated") is now Fernet-encrypted
    at rest with a *separately held* key (`settings.mfa_encryption_key`,
    a different env var than the database credentials) -- migration
    `0009_wp12_hardening` widens the column from 64 to 255 chars for the
    ciphertext. Named gap, not silently left: rotating `mfa_encryption_key`
    today would make every already-enrolled user's secret undecryptable —
    there is one active key and no re-encryption path.
  - **REQ-046** (partial — detection, not the SLA-tracking process): CI
    now runs `pip-audit` and a secret scan (`gitleaks`) on every push —
    this was flagged as missing since WP03/WP04 (`#120`/G3.06: "No...
    secret scan or dependency/security scan configured yet"). **Running it
    for real immediately found 14 known vulnerabilities** across
    `cryptography` (the package this very WP12 pass had just pinned),
    `pytest`, and `starlette` — not hypothetical, an actual `pip-audit`
    run against this repo's real pins. Fixed: `cryptography` 43.0.3→50.0.1,
    `pytest` 8.3.3→9.1.1, `fastapi` 0.115.0→0.141.1 (pulling a patched
    `starlette` 1.6.0, now pinned directly too) — full suite re-run clean
    at each step, 112/112 passing after. The actual remediation-SLA
    tracking/on-call process REQ-046 also asks for (7-day critical/30-day
    high/1-hour S1 ack) needs a named on-call owner and a real
    vulnerability-disclosure pipeline this prototype doesn't have — not
    invented here. **Update 2026-09-17**: pushed and both scans ran for
    real on GitHub Actions (run 35185824036, green) — the secret-scan step
    needed one follow-up fix first (`gitleaks-action`'s git-diff-range
    logic breaks on a repo's very first push; switched to scanning the
    working tree directly, commit `6f58cc6`), found and fixed the same day
    it was pushed, not left broken.
  - **REQ-047** (partial): new `security_log_events` table (global, no
    RLS — same precedent as `users`/`mfa_recovery_codes`, since
    login/register/MFA events are tenant-agnostic; app-layer self-scoping
    only, own-data per REQ-031) logs register/login success+failure/MFA
    verify-failed/MFA-enabled/MFA-recovery-used/invitation-created/
    invitation-accepted — `GET /auth/security-log`. New
    `GET /orgs/{tenant_id}/access-review` lists full tenant membership
    (including inactive/revoked) for periodic review — the mechanism, not
    the quarterly cadence itself (same honest split as WP08's checkpoint-
    frequency note). Retention stays as proposed in
    `docs/wp02/data_retention_policy.md`, not automatically enforced (no
    scheduler exists, a gap named since WP01).
  - **REQ-043** (partial): a telemetry middleware logs structured
    per-request latency/status (one Blueprint §5.7 minimum-telemetry item)
    and `GET /status` reports version/environment/uptime. Explicitly not a
    monitoring platform — no aggregation, alerting, or historical
    retention of its own.

  112/112 backend tests passing (+9: 7 hardening tests, 2 status/telemetry
  tests).
- **DEC07 (rule vocabulary/third framework) is still open** — WP05
  implements the schema shape Sec.5.5 already approved, but the "exact
  vocabulary and limits" the blueprint reserves for DEC07 are this
  session's working choices, not a technical-lead sign-off. Don't treat the
  prohibited-facts list or the depth-5 limit as settled without that review.
- Still Not started across WP03/WP04/WP05/WP06/WP07/WP08/WP09/WP10/WP12:
  #124 (AI-generated code reviewed by a human). Ten work packages in, zero
  of them reviewed by Milton.

## BGP-F01/BGP-F02 remediation (2026-09-17)

`BGP_Development_Review_Findings_v1.0.pdf` (an AI-authored source review,
explicitly not an independent human sign-off — see "Named roles" above,
same "naming is not reviewing" point) flagged five open findings. Fixed the
two High findings the user asked to fix first, per the report's own
recommended order (BGP-F03/F04/F05 remain open):

- **BGP-F01 (session-bound MFA)**: `POST /auth/login` no longer issues a
  full `bgp_session` cookie for an MFA-enabled account by itself — an
  account with MFA enrolled gets a short-lived pre-auth cookie and
  `mfa_required: true`; only `POST /auth/mfa/login-verify` (new endpoint,
  checks the TOTP code against that pre-auth cookie) issues the real
  session, and only that session carries `mfa_verified: true`.
  `require_mfa`/`_require_decision_authority` now gate on that session
  claim AND the live `users.mfa_enabled` flag, never the account flag
  alone. New `users.token_version` (migration `0010_bgp_f01_f02_fixes`,
  applied to live `bgp_dev`) is bumped on factor verification and on
  recovery, invalidating every other previously-issued session token for
  that user immediately — `app/deps.py`'s `get_current_user` checks it on
  every request. `POST /auth/mfa/enroll` now refuses to replace an already-
  enrolled factor unless the calling session itself already passed a
  second-factor check (password-only cannot overwrite an existing factor).
- **BGP-F02 (real compensating review)**: `SeparationOverrideIn` no longer
  takes a `reviewer_user_id`/`note` the deciding actor could just type
  themselves. New `POST .../occurrences/{id}/compensating-reviews`
  (new `compensating_reviews` table, same migration) records the review as
  an authenticated, MFA-verified action from the REVIEWER's own session,
  bound to the occurrence and the evidence manifest digest at review time.
  `_check_separation_of_duties` re-validates all of it fresh at
  decision-commit time — occurrence match, manifest freshness (a changed
  manifest makes an old review stale, not valid), reviewer independence,
  and the reviewer's still-active decision authority (mirrors
  `_exception_is_currently_valid`'s existing "re-check, never trust a
  stored flag" pattern). `decision_records.separation_override_review_id`
  traces a decision back to the specific review row.

116 backend tests passing on SQLite (was 112, +4: 2 MFA-session tests in
`test_identity.py`, 2 compensating-review tests in `test_decisions.py`;
one existing separation-of-duties test rewritten to use the real flow).
Plus 3 new live-Postgres RLS tests on `compensating_reviews`
(`test_wp07_tenant_isolation_rls.py`, same SELECT+INSERT-only /
tenant-isolation shape proven for `decision_records`) — all verified
against real `bgp_dev`, migration `0010` applied there. Committed locally,
not yet pushed.

**Honestly still open**: BGP-F03 (decision-check concurrency), BGP-F04
(export/import history loss) and BGP-F05 (stale README) are untouched by
this pass. `#124` stays Not started — this fix was written by the same
agent as the rest of the codebase, not reviewed by Milton.

## BGP-F03/F04/F05 remediation (2026-09-17, same day) — user said "proceed with them"

- **BGP-F03 (decision-check concurrency)**: `decisions.py`'s
  `_compute_readiness(lock=True)` now takes `SELECT ... FOR UPDATE` on an
  occurrence's evidence rows (ordered by id, so it can never deadlock
  against `create_evidence_revision`'s single-row lock added the same way)
  before a decision reads readiness and commits — closing the "evidence
  changed between readiness evaluation and commit" race for real, not just
  via the pre-existing manifest-digest staleness check (which only catches
  a change that had already committed *before* the read started, not one
  racing it). `_require_decision_authority` similarly locks the caller's
  `ProjectMembership` row. Two new partial unique indexes (migration
  `0011_bgp_f03_concurrency`) — one root (non-superseding) decision per
  occurrence, one supersession per decision — close the "two concurrent
  requests both pass every check before either commits" race at the
  database level; `_record_decision` catches the resulting `IntegrityError`
  and re-derives the same deterministic 409 the up-front check would have
  given, never a bare 500. `create_evidence_revision` got the identical
  defence for `uq_evidence_revision_item_number`. No revoke-membership
  endpoint exists yet in this codebase, so the "revoke authority mid-flight"
  scenario BGP-F03 names is proven by locking the row directly with raw SQL
  in the new test file rather than through a real HTTP endpoint — an
  honestly-scoped substitute, not a claim that endpoint exists.

  New `backend/tests/test_bgp_f03_decision_concurrency.py` (4 tests, live
  Postgres only): two lock-blocking proofs (a second session's write
  provably blocks, via a short `lock_timeout` rather than real threads) and
  two DB-constraint proofs (a second root decision / second supersession is
  refused by Postgres itself). 95 SQLite + 31 live-Postgres tests passing
  overall after this pass (was 92 + 27).

- **BGP-F04 (export/import history loss)**: every exportable live-recreated
  table (templates, versions, projects, occurrences, evidence items) now
  carries a `source_id` (migration `0012_bgp_f04_export_import`) — NULL for
  a natively-created row (its own `id` is its stable source id), set on
  import to the archive's original id and never touched again, so identity
  survives `id` regenerating on every hop. Evidence items export their FULL
  revision history (not just current state), each revision's own
  `source_version`/`source_hash` included. Decisions export their full
  `manifest_json`/`conditions_json`/compensating-review linkage; a new
  `compensating_reviews` archive section covers BGP-F02's table. Imported
  decisions/exceptions/audit events/integrity receipts/compensating reviews
  are now preserved in `ImportedHistoricalRecord` — read-only, never live
  rows (Blueprint Sec.5.6's warning against reconstructing an unattributed
  historical record as a verified approval still holds) — and re-emitted on
  a LATER export of the importing tenant, closing the actual bug: this
  content used to be visible in the archive that was imported and then
  silently gone from every export afterwards. `commit_import`'s malformed-
  archive path now raises a clean 422 (`KeyError`/`ValueError`/`TypeError`
  caught explicitly) instead of an unhandled 500, with the same
  transactional rollback as before leaving no partially-created project.

  New tests in `test_export_import.py`: full revision history + source
  hashes surviving one import; a conditional decision + compensating
  review + exception + superseding decision all surviving a SECOND export
  of the importing tenant, keyed by the same `source_id` as the original,
  with only the live-row references (`project_id`) remapped; a corrupted
  archive (digest recomputed after tampering, so it passes validation)
  rejected cleanly at commit with no partial state. One real bug caught by
  these tests before landing: the commit path never added evidence items to
  `id_map`, so every historical exception/decision referencing an evidence
  item was silently skipped as a "broken reference" — fixed same session.

- **BGP-F05 (stale README)**: rewritten to describe the actual WP01/WP03-
  WP10/WP12 build (not the WP01-only skeleton), the real two-role (+backup)
  Postgres setup with migrations, the `BGP_SESSION_SECRET_KEY`/
  `BGP_MFA_ENCRYPTION_KEY` persistence gotcha named explicitly (a fresh
  random key each restart quietly makes every enrolled user's MFA secret
  undecryptable), real test commands (with the "a skip is not a pass"
  caveat), and the DEC01 status correction (resolved -- lead and reviewer
  named -- but still not an actual completed review by Milton, which the
  README previously didn't say and needed to). `app/main.py`'s own
  module docstring updated to match, since the README points there for the
  fullest up-to-date summary.

Committed (`b1fb402`) and pushed to `origin/master` same session (user said
"commit" then "push it"). Real CI run confirmed green on this exact commit:
[35283094768](https://github.com/SageCarter98/pm-sdlc-tracker-bgp/actions/runs/35283094768)
— migrations 0010–0012 applied cleanly against a fresh Postgres service
container, the full pytest suite (including the live-Postgres RLS/
concurrency suites) passed, `pip-audit` and the secret scan both came back
clean.

**Still honestly open**: no CI run has been deliberately broken to prove a
relevant check goes red (same gap named after the earlier CI-green
milestone). `#124` stays Not started — none of this was reviewed by
Milton.

## Milton given repository access; BGP follow-up review remediation (2026-09-18)

Milton (`MiltonBello15`) was added as a GitHub collaborator on
`SageCarter98/pm-sdlc-tracker-bgp` with **read** access, and named in a new
`.github/CODEOWNERS` (PR #1) so PRs can require his review once branch
protection turns that on (not done here — a separate repo-settings action).
This gives him the means to actually review; it is still not itself a
review, and `#124` is unaffected until he does one. **Evidence honesty
note**: a chat claim that "Milton locally reviewed the codebase and
accepted" was NOT recorded here without something checkable (a PR approval,
signed note, dated comment) — see this session's own conversation. If/when
that record exists, cite it here and re-open the `#124` status.

A NEW review landed the same day: `BGP_Follow_Up_Review_Findings_v1.0.pdf`
(18 September, also AI-authored — "a source review, not an independent
human sign-off", same as the 17 September one) re-inspected the BGP-F01–F05
fixes from `b1fb402` and found all four High findings **partially
resolved**, plus F05 "substantially addressed, verification pending". Fixed
the four remaining gaps:

- **BGP-F01 follow-up (factor-replacement window)**: `POST /auth/mfa/enroll`
  used to overwrite the LIVE `mfa_secret` and set `mfa_enabled=False`
  immediately, so an already-enrolled account had zero second-factor
  protection for the entire window between starting and completing a
  replacement — a password-only session could get a full session AND
  replace the pending secret during that window. New `users.pending_mfa_secret`
  / `pending_mfa_created_at` (migration `0013_bgp_followup_f01_f04`) stage
  the proposed secret without touching the active factor at all; only a
  successful `POST /auth/mfa/verify` atomically promotes it (and bumps
  `token_version` as before). An abandoned or expired (10 minutes,
  `PENDING_MFA_MAX_AGE_SECONDS`) replacement is rejected and cleared,
  leaving the original factor completely untouched — never silently
  extended or accepted late. `POST /auth/mfa/recover` also clears any
  pending secret, so a stale in-flight replacement can't outlive a recovery.
- **BGP-F02 follow-up (preparation from attribution, not the owner field)**:
  `_check_separation_of_duties` used to derive "who prepared this evidence"
  from the live, reassignable `EvidenceItem.owner_user_id` — clearing it or
  handing it to a colleague who never touched the evidence let the real
  preparer approve alone. Now derived from `EvidenceRevision.actor_user_id`
  (immutable, set once to whoever actually called the endpoint) for the
  revision each item is currently at. New test
  `test_clearing_or_reassigning_ownership_cannot_defeat_separation_of_duties`
  proves both the cleared-ownership and reassigned-ownership bypasses are
  closed. This changed what several EXISTING test fixtures needed to do:
  `_record_one_approval` (`test_integrity.py`) and two tests in
  `test_decisions.py` were setting `owner_user_id` to approver2 while admin
  was the one actually calling the revision endpoint — exactly the loophole
  just closed — so those fixtures now have approver2 genuinely log in and
  submit the revision themselves.
- **BGP-F03 follow-up (remaining unlocked reads; flush outside the conflict
  handler)**: `_exception_is_currently_valid` and `_compute_readiness` now
  lock the approver's `Membership` row and the `ExceptionRecord` rows (same
  fixed lock order: evidence, then exceptions, then approver membership)
  when called from the decision-commit path; `_check_separation_of_duties`
  unconditionally locks the compensating reviewer's `Membership` and
  `ProjectMembership` rows (it only ever runs from that path). Separately,
  `_record_decision`'s `db.flush()` — which is what can actually hit
  migration `0011`'s partial unique indexes — used to run BEFORE the
  `try/except IntegrityError` block, so a losing concurrent decision could
  surface as a bare unhandled 500 instead of the deterministic conflict
  response every other path gives; it's inside the try block now. Also
  fixed: `db.rollback()` inside that handler ends the transaction
  `get_active_membership`'s `SET LOCAL app.tenant_id` applied to, so the
  winner-lookup queries that follow were running with NO tenant context —
  under `FORCE ROW LEVEL SECURITY` that hides every row, silently falling
  through to the "unrecognised conflict" re-raise instead of the correct
  conflict response. Tenant context is now reapplied immediately after
  rollback. **Honestly still open, per the follow-up review's own
  suggestion**: no NEW application-level (through the real HTTP endpoints,
  two genuinely overlapping requests) Postgres test was written to prove
  this specific fix end-to-end — the existing `test_bgp_f03_decision_concurrency.py`
  proves the underlying locks/constraints work via raw SQL and direct table
  access, which the follow-up review correctly noted doesn't exercise the
  application's transaction/HTTP-error paths themselves. Not claimed as
  closed.
- **BGP-F04 follow-up (author identity and timestamp lost on re-export)**:
  `commit_import`'s `EvidenceRevision` construction now restores the
  original `created_at` instead of defaulting to import time, and new
  `evidence_revisions.source_actor_id`/`source_actor_email` (same migration)
  preserve the archive's original author identity as historical provenance,
  independent of the live `actor_user_id` FK (which still falls back to the
  importer for an unmatched author, same as before — that FK is for
  referential integrity only now, never read back as "who really did
  this"). Re-export prefers `source_actor_id`/email over the live FK, and
  the exported `actors` section carries these preserved identities
  alongside real local users — never turned into a live account, matched by
  email on a future import exactly like `ImportedActorProvenance` already
  does elsewhere. New test
  `test_unmatched_revision_author_and_timestamp_survive_reexport` proves an
  unmatched author's identity and original creation time both survive an
  export → import → re-export round trip instead of silently becoming the
  importer / the import time.
- **BGP-F05 follow-up (clean-setup verification)**: `alembic upgrade head`
  (0012 → 0013) applied cleanly against the real `bgp_dev` Postgres
  instance, and the full test suite passed against it (131 passed, 0
  skipped/failed — see below). **Not claimed as the full verification the
  follow-up review actually asked for**: this reused the existing dev
  checkout/venv/database rather than a genuinely fresh clone with a brand
  new empty database, which is what "follow the README from a clean
  checkout" means. Honestly still open.

131 backend tests passing (was 116 SQLite + 31 Postgres = 147 counted
separately before; this count is the full combined `pytest -q` run against
real `bgp_dev`, 0 skipped) — +2 new tests in `test_hardening.py` for the
factor-replacement window (expiry, and old-factor-still-works), +1 in
`test_decisions.py` for the ownership-bypass closure, +1 in
`test_export_import.py` for the author/timestamp round trip, plus the one
pre-existing `test_hardening.py` MFA-encryption test updated for the new
`pending_mfa_secret` staging field. `pip-audit -r requirements.txt`: no
known vulnerabilities. Live-Postgres RLS suites (`test_tenant_isolation_rls.py`
and the WP06–WP10 variants) and `test_bgp_f03_decision_concurrency.py` all
still pass unchanged against real `bgp_dev` with migration `0013` applied.

**Honestly still open**: the two items named above (an application-level
Postgres concurrency test for the F03 fix; a genuinely clean-checkout setup
verification for F05), no CI run for this commit yet (the workflow runs on
push), and `#124` — none of this was reviewed by Milton either.

## WP11: DEC04 resolved, first frontend increment (2026-09-20)

**DEC04 (frontend framework, session mechanism) resolved**: server-rendered
HTML via FastAPI + Jinja2, same-origin, reusing the existing signed-cookie
session exactly as-is — no new session mechanism, no SPA framework, no
build step. Resolved at the explicit direction of the project's delivery
lead (Freston Kenny Adedeme) in this session, not an independent
technical-lead sign-off at Gate 3/G2 as the Blueprint's own decision log
describes — same caveat shape as APR-001 and DEC01's "naming is not
reviewing." New code lives under `app/webapp/` (page routes) and
`app/templates/`/`app/static/` (Jinja templates, CSS, one small JS file for
error-summary focus management) — see `app/webapp/__init__.py`'s docstring
for the reuse pattern (every page calls the SAME functions the JSON API
uses, passing real values instead of `Depends()` placeholders, so there is
exactly one implementation of any business rule, never two that could
drift).

**Scope of this first increment**: login/register/MFA enrol+verify, an org
picker (new `GET /me/orgs` endpoint + migration `0015`'s narrow
self-lookup RLS policy — the ordinary per-tenant policy structurally can't
answer "which tenants am I in" in one query), and the five essential
journeys — My work, a guided evidence-revision form with save-as-draft,
blocker explanations, decision recording, and a decision summary. **Not**
in scope: template-authoring UI, invitation-management UI, export/import
UI — those remain API-only. No usability study, no manual screen-reader
walkthrough, no formal WCAG 2.2 AA audit — real gaps, not claimed done.

**What building and actually driving this through a real browser against
real Postgres found** (nothing before this ever combined "a genuine
multi-step user session" with "RLS actually enforced" the way a real
frontend does by construction):

- **15 of 18 `db.refresh()` calls across the codebase were silently broken
  against real Postgres.** `expire_on_commit=False` (set 2026-09-19 for the
  org-bootstrap RLS fix) made every one of them both unnecessary AND
  actively harmful: `SET LOCAL app.tenant_id` ends with the commit that
  precedes the refresh, so the refresh's re-query runs under RLS with no
  context and raises `InvalidRequestError`. This affected `create_template`
  /`import_template`/`fork_template`/`update_draft`/`publish_version`,
  `create_project`, `create_occurrence`, `save_draft`, both export/import
  job-creation paths, both integrity checkpoint/incident paths, and
  `accept_invitation` (still broken after migration 0014's ordering fix,
  which only fixed the INSERT itself). The other 3 (`users`/`tenants`
  refreshes) were merely unnecessary, not broken — those tables carry no
  RLS. All 18 removed; see each file's own "No db.refresh()" comment.
- **`create_evidence_revision`'s own success path re-queried the DB (via
  `get_evidence_item`) AFTER its `db.commit()`** — same root cause, one
  level deeper: not a stale-attribute refresh but a fresh query, still
  running with no tenant context. Fixed by building the full response from
  data read *before* the commit.
- **The webapp's own decide-submission error handler had the identical bug
  one layer up**: re-querying the occurrence/project after catching an
  `HTTPException` from `decisions.py`'s `_deny()` helper — which is a
  *correct* control (it commits an audit trail for a denied decision,
  e.g. BGP-F02's separation-of-duties check, before raising) that no
  existing JSON endpoint ever exposed, because none of them have anything
  left to query once they catch an exception — they just let FastAPI
  render the error. The webapp layer is the first caller that needs to
  keep reading the database afterward to re-render a page, so it's the
  first place obligated to re-establish context first
  (`_reset_tenant_context` in `app/webapp/router.py`).

None of this was caught by the existing 132-test suite: the SQLite suite
has no RLS to break against, and every existing live-Postgres suite seeds
data via raw SQL as `bgp_owner`, bypassing these exact code paths. Two new
regression tests (`test_wp11_webapp_rls.py`) drive the real `/ui` routes
against real Postgres through the actual failure conditions (a successful
revision submission whose response depends on the post-commit read; a
denied decision whose error page depends on re-established context) —
closing a verification gap, not just the two bugs it happened to find.
Full suite: 137 passing (was 132).

Visual design: server-rendered semantic HTML per Blueprint Sec.4.2/4.3
(skip link, one `<h1>` per page, visible focus rings, status always
text-plus-color never color alone, accessible error-summary with focus
management on load), built as a real design system in `app/static/style.css`
rather than left at browser defaults — informed by the `kad-frontend-
engineering` and `emil-design-eng` skills (screen states mapped: loading
implicit in server rendering, empty state on My work, validation failure,
denied access via redirect-to-login; interactive feedback via
transform-only transitions and `scale(0.97)` press feedback, never
`transition: all`). Verified responsive down to a 375px mobile viewport
(table rows collapse to labelled stacked cards).

**Honestly still open**: template-authoring/invitation/export UI (API-only,
as before); a real usability study (Blueprint Sec.4.4 protocol); a manual
screen-reader walkthrough; a formal automated WCAG audit (attempted via
Playwright + axe-core this session — the sandbox's headless browser could
not reach localhost reliably, so this was verified by hand in a real
Chrome session instead: login, MFA, My work, guided form + save/submit,
blockers, decision recording and recovery from a denied decision, at both
desktop and a simulated 375px width). WP11's own tracker items (#128-148
under G4, and the PM-track equivalents) are not touched by this entry —
this is implementation, not a gate decision.

## WP13: design-system reskin + 4 more real pages (2026-09-20)

**Trigger**: `stitch_buildgovernanceplatform_webapp.zip` arrived (a Stitch
UI-mockup package: 10 screens x desktop+mobile, a design-tokens/component-
library spec, and a genuinely new, owner-approved requirements document —
`FE-APR-001` v1.1, "Okay, approve all draft in it, just finished personal
review"). That document is now filed at
`docs/blueprint/BGP_Frontend_Requirements_v1.1_FE-APR-001.md`; its own
provenance note there records what it does and doesn't change relative to
the existing `docs/blueprint/frontend_requirements.md` extract and this
project's real DEC state. The mockup HTML/CSS itself was **not** imported —
it's a static Tailwind-CDN package with Google-hosted placeholder images,
fabricated crypto hashes/org names and internal codes (`FE-APR-001`,
`GOV-SEC-BNDRY`) rendered to end users, none of it appropriate to ship
as-is into a same-origin, no-build-step, no-external-CDN frontend (DEC04).

**What this WP actually did**:

1. **Reconciled one design-token set** into `app/static/style.css`'s
   existing `:root` custom properties (kept WP11's architecture; updated
   values) — the Slate/Emerald/Amber/Rose governance-state palette from the
   Stitch package's `DESIGN.md` prose (cited WCAG contrast ratios), cross-
   checked against its `complete_frontend_specification_token_bundle.md`
   CSS bundle where they overlap (the two disagreed in places; this file's
   own header records which one won). Sharper radii (4/6/8px), a Cobalt-600
   focus ring per the WP13 component contract, monochrome slate-900 primary
   buttons (an institutional/audit-tool choice, not a marketing brand
   color), tabular-figure numeric styling, and three new honest components:
   a three-slot blocker banner (rule/violation id, root cause, remediation —
   using the real `BlockerExplanation` fields already returned by
   `decisions.py`'s `preview_decision`, not the mockup's fabricated
   "POL-SDLC-SEC-09"-style codes), an SoD callout box, and an immutable-
   manifest-summary treatment. Applied to `decide.html`/`decision_summary.html`
   (the two pages with real blocker/manifest/outcome data to show); the
   other 8 existing templates inherit the new tokens without markup changes.
   `decide.html` also now shows the manifest digest to the user before
   confirmation (FE-048) — it was previously only a hidden form field.
2. **Four new real pages**, following `app/webapp/router.py`'s existing
   pattern exactly (`_require_page_membership` guard, call the same
   functions the JSON routers use, `_reset_tenant_context` after any caught
   `HTTPException`):
   - **UI02 First project creation** (`/ui/orgs/{tenant_id}/projects/new`) —
     lists published starters via a new `GET /orgs/{tenant_id}/templates/published`
     endpoint, creates via the existing `projects_router.create_project`.
   - **UI05 Gate readiness dashboard** (`/ui/orgs/{tenant_id}/projects/{project_id}/gates`) —
     needed a new `GET /orgs/{tenant_id}/projects/{project_id}/occurrences`
     list endpoint (read-only, membership-gated, same shape as
     `integrity.py`'s `list_checkpoints`/`list_incidents`; nothing like it
     existed before — every prior occurrence read was single-occurrence).
     Reuses `decisions_router.preview_decision` per occurrence, same call
     `decide_page` already made one at a time. Deliberately does **not**
     compute or display a completion percentage (FE-043/044).
   - **UI07 Audit history & supersession tracker** (`/ui/orgs/{tenant_id}/projects/{project_id}/history`) —
     needed a new `GET /orgs/{tenant_id}/projects/{project_id}/decisions`
     list endpoint (`decisions.py` only had single-decision lookup by id
     before). Combined with the existing checkpoint/incident lists for one
     project timeline; supersession chains drawn from each decision's own
     `supersedes_decision_id`, no new field.
   - **UI10 Account, membership & separation settings**
     (`/ui/orgs/{tenant_id}/settings`) — own profile/MFA status for anyone;
     tenant administrators additionally see `orgs_router.access_review`'s
     full roster and a form posting to the existing `create_invitation`.
     **Real, honestly-flagged gap**: there is no revoke-membership or
     change-role endpoint anywhere in `orgs.py` yet, so no such control was
     added to the page — the template says so directly rather than faking
     one. FE-017 ("removed membership invalidates stale actions") is
     therefore still only partially covered by this project.
   - Every direct call into a role-gated router function
     (`Depends(require_role(...))`) had its role check explicitly
     re-invoked in the webapp layer (e.g.
     `require_role(Role.TENANT_ADMINISTRATOR, Role.APPROVER)(membership=membership)`
     before `create_project`) — calling a FastAPI route function directly
     bypasses its own `Depends()` defaults entirely, so skipping this step
     would have let any active member create a project or send an
     invitation regardless of role. Caught before merge, not after.
3. **Deliberately not built**: UI08 (template authoring/rule builder) stays
   API-only — blocked on **DEC07** (rule vocabulary), still open. UI09
   (export/import) stays API-only — touches **DEC06**/**DEC12** (retention/
   disposal, import provenance), both still open. This matches WP11's own
   stated scope boundary; FE-APR-001 lists all ten screens as "approved"
   but explicitly disclaims inventing decisions FE-APR-001 itself didn't
   resolve.

**Tests**: `test_wp13_webapp_new_pages.py`, same live-Postgres-only pattern
as `test_wp11_webapp_rls.py` — project creation happy path and a rejected-
class path that leaves no partial project, the gate dashboard rendering a
real unresolved hard blocker and linking into the existing decide route, a
recorded decision showing up in project history, and the settings page
proven to hide admin-only controls from a non-admin member (and show them
to the admin) via two independent sessions against real RLS. Full suite:
142 passing (was 137) — all against real Postgres, not the SQLite fixture
(`assert app.dependency_overrides == {}` guards this the same way WP11's
tests do).

**Not touched by this entry**: no gate decision was recorded by this work —
per this project's standing rule (see below), that stays a named authority's
manual `tracker_cli.py gate` action regardless of how much evidence this WP
adds.

**Real defect found and fixed via an actual browser walkthrough, same
discipline as WP11's own two RLS-context bugs**: `mfa_enroll_verify_submit`
(`app/webapp/router.py`) called `mfa_router.verify()` with a `RedirectResponse`
to carry the reissued, `token_version`-bumped session cookie (BGP-F01's own
mechanism), but then returned a *different* Response object
(`_render(..., "mfa_enrolled.html", ...)`, needed to actually show the
recovery codes instead of redirecting) — so the Set-Cookie header was built
and then silently discarded. The browser kept its stale pre-enrolment
cookie; the very next request was silently logged out by
`page_current_user`'s `token_version` check. Every *other* cookie-mutating
handler in this file correctly returns the same response object it set
cookies on (`login_submit`, `mfa_login_verify_submit`, `register_submit`,
`logout_submit`) — this was the one handler that needed to render different
content on success and missed carrying the cookie across. Fixed by copying
`resp.headers.getlist("set-cookie")` onto the rendered response. New
regression test `test_mfa_enrolment_keeps_the_session_usable_afterward`
(live Postgres) — confirmed it fails without the fix (reverted the router
change, test failed) and passes with it. This bug predates WP13 (it's part
of WP11's original enrol/verify flow) but was only found now because this
was the first time anyone actually drove MFA enrolment through a real
browser session end-to-end rather than through the JSON API or a test
client that doesn't notice a discarded cookie the same way a real browser
does. Full suite: 143 passing (was 142).

## WP14: in-product requirement guidance on tenant-authored gates/rules (2026-09-21)

User asked for the "what to do / evidence to provide" guidance pattern built
into the external KenAddme tracker (same day, see `~/.claude/skills/pm-sdlc-tracker/`)
brought into BGP's own product UI -- explicitly for BGP's actual customers
using their own configurable gates, not the fixed KenAddme institutional
catalogue. The two are unrelated: a tenant's gates/rules come from their own
authored template (`app/rule_engine.py`), never from KenAddme's Gate 1-7/G0-G6
numbering.

**Schema (`app/rule_engine.py`)**: two new optional fields, purely additive,
no cross-reference validation, never evaluated by `evaluate_condition` --
`GateDefinition.description` (gate purpose) and `Rule.guidance` /
`Rule.evidence_example` (per-rule "what to do" / "evidence to provide").
Absent on any template authored before this existed; those render with no
guidance block, not a broken one (proven by
`test_evidence_form_omits_guidance_block_when_template_has_none`).

**Rendering**: `evidence_form.html` (the rule's own guidance, next to the
exact item a contributor is completing) and `gate_dashboard.html` (the
gate's purpose, next to each occurrence row) via a new collapsed-by-default
`<details class="guidance">` component in `app/static/style.css`, matching
this project's existing accessible-disclosure conventions. Wired in
`app/webapp/router.py`'s `evidence_form_page`/`gate_dashboard_page` via two
new small helpers, `_find_rule`/`_find_gate`, that look the definition up
from the project's own bound template schema (`_load_bound_schema`, already
loaded on both pages) -- no new endpoint, no new DB column, no change to
readiness/blocker logic.

Updated the `lightweight.json` synthetic framework fixture with real example
guidance text so the feature has visible, testable data (`regulated.json`/
`standard.json` left untouched -- authoring guidance for every fixture
wasn't asked for).

New `test_wp14_requirement_guidance.py` (live Postgres): guidance renders
when the template supplies it (both pages), and renders nothing when it
doesn't. Also verified live in a real browser end-to-end (register -> org ->
template with guidance -> project -> evidence item and gate dashboard both
showing the real text). Full suite: 146 passing (was 143).

## WP15 Phase 1: evidence attachments (2026-09-21)

FE-097/098 (conditional capability, REQ-053) -- user asked for uploaded
files as evidence, then explicitly agreed to a staged plan before any code:
Phase 1 (schema, local storage, upload/download with scanning stubbed
`unavailable`), Phase 2 (a real scanner, still an open choice -- ClamAV vs.
a cloud API, not decided here), Phase 3 was already covered by Phase 1's
own frontend wiring.

**Built**: `evidence_attachments` (migration `0016_wp15_evidence_attachments`,
applied to live `bgp_dev`) -- same tenant-owned RLS shape as every evidence
table since WP06. `app/attachment_storage.py`'s `AttachmentStore` interface
with one implementation, local disk under `backend/var/` (gitignored,
`BGP_ATTACHMENT_STORAGE_ROOT` overridable) -- deliberately not object
storage; nothing else in this stack uses it, and the app is still
local-prototype/synthetic-data stage. `storage_key` is always server-
generated (tenant_id + uuid4), never the client's filename -- no path-
traversal surface. `app/routers/attachments.py`: upload/list/download,
same authorisation model as evidence revisions (any current project
member, via the existing `_require_project_member`). Immutable and
versioned like `EvidenceRevision` -- a new upload marks the prior `active`
row `superseded`, never overwrites. A conservative, explicitly-flagged
placeholder size limit (20MB, `BGP_ATTACHMENT_MAX_SIZE_BYTES`) since no DEC
has actually set one -- same honesty as DEC08's numeric gaps.

**The one property that matters most**: `download_attachment` refuses
anything whose `scan_status != "clean"`. No scanner is wired up yet, so
`scan_status` defaults to `"unavailable"` and **every attachment uploaded
this phase is permanently undownloadable** -- that is FE-097's own
acceptance check ("unscanned/malicious files cannot be downloaded")
enforced from the first line of code that can serve a file, not a gap
deferred to Phase 2. Phase 2 only has to make `scan_status` reach
`"clean"`; the refusal logic doesn't change.

**Frontend**: `evidence_form.html` gets an "Attachments" table (filename,
size, active/superseded status, scan status, uploader/date) and a plain
upload form, using the same `.pill` components the rest of the app already
uses. The section's own hint text says outright that downloads don't work
yet, rather than shipping a dead link.

**Tests**: `test_wp15_evidence_attachments.py` (live Postgres) -- upload
succeeds then download 423s, a second upload supersedes (not overwrites)
the first, an empty file is rejected, and a same-shape-as-WP04 tenant-
isolation leak proof (tenant B cannot download tenant A's attachment even
knowing its real id). Verified live in a real browser end-to-end (the
extension couldn't access a native file picker without the user sharing a
folder, so the real multipart form was submitted via the page's own
same-origin `fetch`, exercising the identical server code path -- flash
message, attachment row and honest "not yet retrievable" scan-status pill
all confirmed rendering). Full suite: 150 passing (was 146).

**Explicitly not built** (at the time, Phase 1 only): any scanner
integration, and no evidence-rule schema change requiring an attachment
for a given evidence_kind -- uploads stay supplementary to the existing
reference field, not a replacement for it (still true after Phase 2).

## WP15 Phase 2: Cloudmersive scanner integration (2026-09-21)

User chose a cloud API over self-hosted ClamAV, then asked which vendor to
recommend. Recommended and used **Cloudmersive** over VirusTotal
specifically because VirusTotal's standard API shares submitted files with
a multi-vendor corpus -- a poor fit for a platform whose entire design is
about not letting tenant data cross boundaries it shouldn't; Cloudmersive's
scan stays between this app and them. User obtained a key and added it to
`backend/.env` as `BGP_CLOUDMERSIVE_API_KEY` (gitignored, never committed;
verified present by checking for the line, never by printing its value).

**Built**: `app/attachment_scanner.py` -- `Scanner` interface, one
implementation (`CloudmersiveScanner`) calling `POST
https://api.cloudmersive.com/virus/scan/file` (`Apikey` header, multipart
field `inputFile`, JSON `{"CleanResult": bool, "FoundViruses": [...]}` --
confirmed against Cloudmersive's own docs before writing the client, not
assumed from memory). Returns `"clean"`/`"infected"`/`"error"`/`"unavailable"`
-- a failed or unparseable call is `"error"`, never silently `"clean"`.

**`app/routers/attachments.py` reworked**: scanning now happens before
version-lineage decisions, not after. `"clean"`/`"unavailable"`/`"error"`
all promote the new upload to `active` and supersede the prior one, same
as Phase 1. A confirmed `"infected"` result does the opposite: the row is
still committed (quarantined, visible in the attachment list -- nothing
this project does silently discards a record of what happened) but gets
`status="rejected"`, never becomes `active`, and never touches whatever
was active before it. The upload call itself then returns 422 so the
immediate caller sees a clear rejection, not a false success.

**Frontend**: `evidence_form.html`'s attachment table now shows a real
"Download" link when `scan_status == "clean"`, and "Not downloadable"
otherwise; the `rejected`/`infected` states get the danger pill instead of
the neutral/warning ones Phase 1 used for everything non-clean.

**Tests**: `test_wp15_evidence_attachments.py` now force-monkeypatches the
scanner to `"unavailable"` (an autouse fixture) so it keeps deterministically
testing that real, still-current pathway regardless of whether a key happens
to be configured locally; added a hermetic fake-scanner test proving an
infected upload quarantines without touching the active version. New
`test_wp15_cloudmersive_scanner.py` (skipped without a configured key) hits
the **real** Cloudmersive API: a harmless file scans clean and downloads
byte-for-byte correctly; the industry-standard EICAR test string (not real
malware -- the standard payload every AV engine is built to flag) is
correctly detected, quarantined, and blocked from download. Also verified
live in a real browser: a real-scanned clean file got a working Download
link with correct byte content; the earlier Phase-1-era upload (scanned
before this key existed) correctly stayed `unavailable` rather than being
retroactively rescanned. Full suite: 153 passing (was 150).

## BGP-HR-001 and BGP-IPA-001: review register widened, 5 new findings logged (2026-09-22)

Two governance records landed at the repo root: `BGP_Human_Code_Review_Approval_Record_v1.0_Approved.docx`
(BGP-HR-001) and `BGP_Implementation_Plan_Alignment_Findings_v1.0.docx` (BGP-IPA-001, an AI-assisted
assessment against the approved blueprint, inspected commit `0b284c6fb95c`). Neither document's
claims were taken on faith -- every material claim was independently re-checked against live
GitHub/repo state before this tracker was touched:

- `gh pr view --json reviews` for PRs 3-7 confirmed every final-head `APPROVED` review BGP-HR-001
  cites (PR3 `b8bb22a3f384`/MiltonBello15, PR4 `ac7f0f1068ce`/MiltonBello15, PR5 `0966b1b750b9`/
  MiltonBello15+kenAddme, PR6 `4562f299426f`/kenAddme, PR7 `fa87b817996c`/kenAddme), and confirmed
  PR6's earlier commit `06662fe8193c` (MiltonBello15 approval + kenAddme's later-dismissed review)
  is correctly excluded from the register, not double-counted.
- `gh run view --job --log` on run `35670396664` / job `106565331468` confirmed BGP-IPA-001's exact
  cited figures: `151 passed, 2 skipped, 24 warnings`, `73 files already formatted`, Ruff
  `All checks passed!`, dependency scan and secret scan both clean.
- Grepped `backend/app/webapp/router.py` line 578 and confirmed `decide_submit` really does
  `idempotency_key=str(uuid.uuid4())` fresh on every call -- BGP-IPA-001's IPA03 finding is real,
  not a documentation artefact.
- Grepped `README.md` lines 193/212 and confirmed the "lint unconfigured" and "No frontend" claims
  are both still there and both now stale -- IPA05 is real; **README.md itself was not fixed by
  this pass**, only flagged (see #125 below).
- Grepped this file's own `## WP13` / `## WP14` / `## WP15` headings and confirmed the drift IPA01
  flags: Blueprint Sec.6 assigns WP13=independent acceptance/release and WP14=optional/paid, but
  this file uses WP13/WP14/WP15 for frontend pages/guidance/attachments instead, with no recorded
  mapping back to the blueprint's own numbering.
- One thing neither document's own claims could settle: both cite `BGP-CR-001, Collaborator Review
  Closure Record v1.0, 18 September 2026` as a historical companion file. **No such file exists
  anywhere in this repository.** Not fabricated or assumed benign -- flagged as a real gap.

**Tracker items updated** (`pm-sdlc-tracker` DB, project id 1; overall completion 8.2% -> 9.4%):

- **#124 (SDLC G3.10)** stays Complete; evidence widened from PR#3/#4 only to the full PR3-7
  register above. Still explicitly scoped -- not a standing guarantee for a future unreviewed PR.
- **#116 (SDLC G3.02)** Not started -> Complete: PR/commit/reviewer/CI-check linkage now recorded
  for PRs 3-7.
- **#120 (SDLC G3.06)** In progress -> Complete: lint+format are now configured and green in CI
  (closing the exact gap open since WP12/2026-09-17). Caveat kept in the tracker note: the 2
  skipped tests are Cloudmersive's live-scanner module, which skips without a key/reachable setup
  CI doesn't provide -- this green run is not a live-scanner pass.
- **#121 (SDLC G3.07)** In progress -> Complete: CI run history is genuinely retained on GitHub
  Actions now, not just a local run.
- **#126 (SDLC G3.12)** stays In progress: IPA01-IPA05 logged as a second, separate open-findings
  set alongside the original BGP-F0x set. Still no single merged deviation register with owner/
  commit/test-ID/closure-date columns -- that gap is what keeps this In progress.
- **#125 (SDLC G3.11)** stays In progress: IPA05's README-staleness finding added to notes; README
  itself is not yet corrected.
- **#99 (SDLC G1.08)** downgraded Complete -> In progress: IPA01's WP-identifier drift is a real
  break in the REQ-to-WP traceability chain for the WP13+ increments, confirmed above by grep, not
  just asserted by the document.
- **PM Gate 4.04 (#43)** and **PM Gate 4.07 (#46)**, plus **SDLC G4.06 (#133)** and **SDLC G4.19
  (#146)**: all Not started -> In progress. BGP-HR-001 explicitly names itself as PM Gate 4
  supporting evidence, and the PR-level author/reviewer separation (SageCarter98 authoring,
  MiltonBello15/kenAddme approving, verified live) is real, partial evidence for these items. None
  marked Complete -- each still has a real, stated gap (e.g. #46 needs all work packages accepted,
  not just PRs 3-7; #133 needs owner/retest-status fields these two documents don't carry).

**Not touched by this pass**: the rest of the PM track (still 0%; these two documents don't speak
to PM Gates 1-3/5-7), SDLC G4 durability (IPA04 is explicitly release-blocking and remains
genuinely unaddressed -- two review-evidence documents cannot close it), and #122 (SBOM/licence
inventory -- neither document adds evidence there).

## IPA01/IPA05 closed; three tracker items corrected after finding docs/ files that existed but weren't checked (2026-09-24)

Asked to "note and close the findings" of BGP-IPA-001. Checked current code/docs
against each of the 5 findings first (none were honestly closable as first
found) and confirmed the scope with the user: docs-only work, no new code.

**IPA05 (README contradictory status) -- Closed.** `README.md` still said
linting was unconfigured and listed "No frontend" under known gaps -- both
stale since 2026-09-20. Fixed: removed both claims, added accurate current
notes on the partial frontend (now cross-referencing IPA02), the decision-
recovery gap (IPA03), the durability/assurance gap (IPA04), and a corrected,
honest account of the BGP-F0x/follow-up fix history (see below). Grep-confirmed
both stale strings are gone.

**IPA01 (WP-identifier drift) -- documentation half closed, review half open.**
Wrote `docs/wp_identifier_mapping.md`: for every `TRACKER.md` heading that
reuses a Blueprint Sec.6 WP number (WP11, WP13, WP14, plus the unassigned
WP15), it records what was actually built, the true Blueprint anchor, the
real requirement IDs, the authorization reference, and the acceptance
evidence. **Checking the Blueprint's WP table directly (not just
TRACKER.md's headings) found the drift is worse than BGP-IPA-001 itself
said**: Blueprint WP11 ("Usability and accessibility") is also
number-shadowed by the frontend-build increment TRACKER.md calls "WP11" --
BGP-IPA-001 only named WP13/14/15. Like every other AI-drafted document in
this project, the mapping is not independently reviewed yet -- tracker item
#99 stays "In progress," not "Complete."

**IPA02, IPA03, IPA04 -- stay open, correctly.** None of these three can be
closed by a documentation pass: IPA02 needs DEC06/DEC07/DEC12 resolved
before the missing UI can be built; IPA03 needs an actual stable-idempotency-
key/recovery-flow implementation (`decide_submit` still generates a fresh
`uuid.uuid4()` on every call, reconfirmed this session); IPA04 needs named
decision owners for DEC05/DEC08/DEC11 plus real independent assurance work
that no agent session can perform on its own. Recorded as open rows in
`docs/DEFECT_REGISTER.md` alongside IPA01/IPA05, not silently dropped.

**Three tracker items corrected** after this pass turned up real `docs/`
files from commit `92dda7e` (PR#5, 2026-09-19, reviewed and approved by both
MiltonBello15 and kenAddme) that a prior backfill session (2026-09-22) never
checked for -- the same class of miss the evidence-honesty discipline exists
to catch, just running in the other direction this time (undercounting real
progress, not overcounting it):

- **#126 (G3.12)**: `docs/DEFECT_REGISTER.md` already existed since
  2026-09-19 -- a real structured register (ID/severity/discovered/fix-
  commit/reviewer/test-evidence/status/closure-date) covering all 5 BGP-F0x
  findings and their 6 follow-up-review fixes. Spot-checked 2026-09-24:
  migration `0014_org_bootstrap_rls_fix.py` and every cited test function
  exist and pass (12/12 targeted, 1/1 app-level concurrency, **full suite
  153/153 against real Postgres**, run this session). Moved Not-actually-
  In-progress -> **Complete**; the 5 new IPA0x rows were added to the same
  register (Open/Submitted-for-review/Closed as appropriate, matching the
  paragraphs above).
- **#122 (G3.08)**: `docs/dependency_licence_inventory.md` already existed
  (pip-licenses-generated, honestly caveated UNKNOWN-license entries,
  psycopg2-binary's LGPL flagged). Stays In progress correctly -- no SBOM
  format, no CI enforcement -- but the evidence citation was stale and is
  now corrected.
- **#125 (G3.11)**: `docs/api-reference.md` already existed, pointing at the
  live OpenAPI schema (`GET /docs`/`/redoc`) plus a regenerable
  `docs/openapi.json` snapshot. Stays In progress correctly -- still no
  architecture diagram or operational runbook -- but the prior note ("no
  separate API reference exists") was simply wrong.

## Approved xlsx companion tracker filled: Work packages, Decisions, Remediation (2026-09-24)

`docs/blueprint/Build_Governance_Platform_Implementation_Tracker_v0.2_Approved.xlsx`
has sat with every execution-status column blank since its 2026-09-15 baseline
(flagged in tracker item #99's evidence). Asked to update it; scoped with the
user to the 3 sheets with solid, already-verified evidence (Work packages,
Decisions, Remediation -- 33 rows) rather than the 58-row Requirements and
23-row Acceptance sheets, which need genuine per-item `TST-XXX` test
verification, not transcription -- left blank for a dedicated future pass
rather than filled carelessly.

**Work packages (14 rows).** WP01-WP10 and WP12/WP14 filled with real
Status/Evidence, several citing the specific PR and reviewer where one
exists (e.g. WP03's MFA hardening: MiltonBello15, PR#3). **The honest
surprise**: filling this sheet required cross-checking against
`docs/wp_identifier_mapping.md` (IPA01), which showed Blueprint's *actual*
WP11 ("Usability and accessibility" -- participant protocol, accessible
journey results) and WP13 ("Independent acceptance and release" -- pen
test, user acceptance, release/rollback records) have **never been done at
all**. TRACKER.md's own "WP11"/"WP13" headings are unrelated frontend-build
increments that happen to reuse those numbers. Both recorded as
**Not started** in the xlsx, not rounded up just because *something*
numbered similarly exists elsewhere.

**Decisions (12 rows, 2 changed).** DEC01 and DEC04 moved from "Partly
decided" to **"Decided"**, each with a Named owner filled in for the first
time: DEC01 (Freston Kenny Adedeme as delivery lead; MiltonBello15 as
independent reviewer, now backed by real APPROVED PR reviews, not just a
named appointment) and DEC04 (the frontend/session architecture actually
built 2026-09-20). DEC02/03/05/06/07/08/09/10/11 correctly left
"Partly decided" -- still genuinely open per DEC05/08/11's own appearance in
IPA04.

**Remediation (7 rows, TR01-TR07 -- the original prototype findings,
distinct from the later BGP-F0x set in `docs/DEFECT_REGISTER.md`).** TR01,
TR02, TR03 and TR05 marked "Pass" with real test/code citations. TR04 marked
"Partial" -- REQ-022's activity-limits gap on conditional approval, named
since WP07 (2026-09-16), is still genuinely open. TR06 left "Not tested" --
no specific check of HTML/Markdown control consistency has been done, and
guessing "Pass" would have been fabrication. TR07 marked "Partial" -- the
integrity/restore foundation is real and tested, but it remains a single
local Postgres instance, not production infrastructure. **Reviewer left
blank on every TR row** since none were independently reviewed -- the
sheet's own `Verification` formula (`Pass` AND evidence AND reviewer all
required) correctly computes "Unverified" for all 7 as a result, which is
the honest state, not a formula quirk to work around.

Tracker item **#99 (G1.08)** evidence updated to reflect this. Full
technical trace of each row's evidence lives in this document's history
above and in `docs/DEFECT_REGISTER.md`; the xlsx itself now carries the
condensed, structured version.

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
