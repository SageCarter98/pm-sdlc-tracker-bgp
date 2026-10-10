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
     **Gap closed 2026-09-28** (commit `6842447`): `orgs.py` now has
     `POST /orgs/{tenant_id}/memberships/{membership_id}/role` and
     `.../revoke`, both `require_role(Role.TENANT_ADMINISTRATOR)`-gated and
     refused (409) if they would leave the tenant with zero active
     administrators; `settings.html` exposes them as inline per-row forms.
     FE-017 ("removed membership invalidates stale actions") is now covered
     by this project's own revoke path, not just by relying on some other
     membership change happening elsewhere.
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
   resolve. (Membership revocation/role-change, the third item this section
   used to group with UI08/UI09, was built 2026-09-28 — see the WP13-15
   entry below; it did not depend on any open DEC.)

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

## Xlsx tracker completed: Requirements (58) and Acceptance (23) sheets (2026-09-24)

Finished the xlsx companion tracker, filling the two sheets scoped out of the
previous pass -- these needed genuine per-item test verification against a
specific `TST-XXX` claim, not transcription from already-established WP-level
evidence.

**Result**: of 58 requirements, 34 Pass, 8 Partial, 16 Not tested. Of 23
acceptance criteria (each a boolean AND over several requirements), 7 Pass,
10 Partial, 6 Not tested. Every non-blank cell cites a real source: a commit,
a test file/function name, a grep result run this session, or an explicit
"not built" finding -- nothing was marked Pass on the strength of its parent
work package being marked Complete.

**The one that mattered**: doing this at the individual-requirement level
(not the work-package level) caught something the earlier Remediation-sheet
pass had missed. TR03 ("Unverified exclusions", covering REQ-020 and
REQ-021) had been marked "Pass" on the strength of REQ-021's real fix
(live exception re-validation). Checking REQ-020 on its own -- "Validate
not-applicable classifications against rules and class floor" -- found
**zero occurrences of that logic anywhere in `backend/app/`**, grep-confirmed.
It is not unverified, it is unbuilt. Corrected: TR03 downgraded to "Partial
(REQ-021 holds, REQ-020 unbuilt)" in the Remediation sheet, and a new
`REQ-020 validation gap` row added to `docs/DEFECT_REGISTER.md` (Open,
Medium, needs an actual implementation in `app/rule_engine.py` or
`app/routers/decisions.py` before it can close). This is exactly the kind
of miss coarser roll-ups produce -- worth remembering before trusting any
WP- or gate-level "Complete" without checking what it's actually built from.

Other notable Partial/Not-tested findings surfaced this pass (all now on
record in the Requirements sheet and cross-referenced to existing open
items where one exists):
- **REQ-035** (pending/confirmed decision recovery): Not tested --
  reconfirms IPA03 at the requirement level, not just the webapp-route level.
- **REQ-038** (invitation landing): Partial -- MFA/recovery are real, but
  `accept_invitation` has no matching HTML template; grep-confirmed no
  invitation-landing page exists anywhere in `backend/app/templates/`.
- **REQ-024** (atomic authority recheck): Partial -- ties directly to
  IPA04's remaining concurrency gap (exception/membership/reviewer-authority
  reads not locked), not a new finding but now visible at the requirement
  level too.
- **REQ-012** (guided template authoring): Partial -- the backend
  (fork/import/create-blank) is real and tested; the guided-authoring UI
  (UI08) is the same open gap as IPA02.

Both `docs/DEFECT_REGISTER.md` rows for IPA01 and IPA05 also had their "Fix
commit(s)" field corrected from "not yet committed" to the real commit
(`5e00405`) now that the previous session's changes were actually pushed.

Tracker item **#99 (G1.08)** evidence updated. The xlsx is now a complete,
checked, six-sheet linked-work-item structure -- what remains open is
independent review of `docs/wp_identifier_mapping.md` and actually fixing
the handful of gaps this pass found or reconfirmed (REQ-020, REQ-035,
REQ-038, REQ-024), not further transcription work.

## REQ-020 "fixed" -- turned out to be a misdiagnosis, not a code gap (2026-09-24)

Asked to fix REQ-020 ("Validate not-applicable classifications against rules
and class floor"), which the previous pass had marked "Not tested" /
"genuinely unbuilt" after grepping for the literal string "Not applicable"
and finding nothing.

**First hypothesis, discarded before writing any code**: that a "hard"
blocker-level evidence item (the class floor) should never be waivable via
`ExceptionRecord`, since that's the only mechanism in this codebase that
excludes an item from blocking. Before implementing that, checked for
existing tests on the exception path and found
`test_exception_excuses_a_hard_blocker_and_revocation_reinstates_it`
(`backend/tests/test_decisions.py`) -- an existing, passing, deliberately
named test asserting the *opposite*: a valid, authority-approved exception
**correctly** excuses even a hard blocker, and revoking it correctly
reinstates the block. Waiving a class-floor item via a scoped, time-bound,
authority-checked exception is the intended design (matches real-world
governance practice, not a bug) -- would have broken working, tested,
intentional behaviour to "fix" this.

**Re-reading REQ-020's own verify text** (`docs/blueprint/Requirements_Catalogue.json`,
not just its paraphrased description) settled it: "A typed status alone
cannot exclude an item; expired, revoked and unrelated exceptions are
rejected." Checked each clause against the actual code and tests:
- *Revoked exceptions rejected*: already tested (the test above).
- *Expired exceptions rejected*: `_exception_is_currently_valid` re-checks
  `expires_at` against server time on every read -- but no test proved this
  for an exception that was valid at creation and later expired with time
  passing, only that `create_exception` refuses an already-expired one up
  front. Missing test, not missing code.
- *Unrelated exceptions rejected*: structurally guaranteed by
  `ExceptionRecord.evidence_item_id` scoping the lookup query -- but nothing
  proved this end-to-end either.

**Fix**: added exactly those two tests to `backend/tests/test_decisions.py`
-- `test_exception_that_has_expired_over_time_no_longer_excuses_the_blocker`
(directly rewinds an `ExceptionRecord.expires_at` into the past via the same
direct-DB-manipulation pattern `test_hardening.py` already uses for expired
MFA replacement windows, then re-checks readiness) and
`test_exception_scoped_to_one_item_does_not_excuse_a_different_item` (creates
an exception for the S1 item, confirms the S2 item in the same project still
blocks). **Verified both tests actually catch what they claim**, not just
pass by coincidence: temporarily removed the expiry check and separately
broadened the exception-scoping query to project-wide, confirmed each
change made the corresponding new test fail, then reverted -- `git diff` on
`backend/app/routers/decisions.py` is empty; no production code changed.
Full suite: 155/155 passing (was 153, +2).

**Corrected records**: REQ-020 (Requirements sheet) and TR03 (Remediation
sheet) both moved back to "Pass" in the xlsx, with the corrected reasoning
in place of the original (wrong) "unbuilt" claim; AC03 and AC11 (Acceptance
sheet) recomputed now that REQ-020 no longer drags them down (both now
"Partial" instead of worse, still correctly limited by REQ-022's separate,
real activity-limits gap). `docs/DEFECT_REGISTER.md`'s REQ-020 row marked
superseded/Closed with the corrected story, not deleted -- the earlier wrong
entry stays visible as history, per this project's own "preserve dated
history, don't delete it" rule.

**Worth remembering**: a per-requirement verification pass is itself not
immune to producing a false negative -- searching for the wrong terminology
(a literal status string) instead of reading the requirement's own verify
text first cost an extra round trip here. Read the acceptance/verify text
before concluding something is unbuilt, not just the requirement's
paraphrased description.

## REQ-035, REQ-038 fixed; REQ-024 corrected and its one real gap closed (2026-09-25)

Continued from the prior session's own punch list ("the handful of gaps this
pass found or reconfirmed (REQ-020, REQ-035, REQ-038, REQ-024)" -- REQ-020
was already closed as a misdiagnosis, see above). All three remaining items
resolved this session; full backend suite 161/161 (was 155) after all three.

**REQ-035 / IPA03 (pending-decision recovery) -- fixed.** `decide_submit`
(`app/webapp/router.py`) generated a fresh `uuid.uuid4()` idempotency key on
every POST, which defeated `create_decision`'s own idempotency check at the
UI layer: if a response was dropped after the server committed and the
browser resubmitted the identical form, the fresh key made it look like a
brand-new request, landing on decisions.py's "Occurrence already has
decision ..." 409 instead of showing the decision that had, in fact, just
been recorded -- exactly the gap REQ-035's own verify text names ("Drop the
response after commit; recovery displays the existing decision without
creating another"). Fixed: `decide_page` (GET) now mints one idempotency key
per render, embedded in a hidden form field (`templates/decide.html`);
`decide_submit` (POST) uses that value instead of generating its own. A
re-render after a denial/error (`_render_error`) mints a **fresh** key --
reusing the denied one would make a genuinely different follow-up attempt
(e.g. picking a different outcome after seeing why the first was denied)
collide with decisions.py's "Idempotency-Key already used for a different
request" check instead of being processed as new. New
`backend/tests/test_req035_decision_recovery.py` (2 tests, live Postgres):
resubmitting the identical rendered form returns the same decision id, not
a duplicate, and is confirmed to be the same DB row (not two rows that
happen to render identically, via `GET .../decisions`); a fresh page load
mints a different key. `test_wp11_webapp_rls.py`'s existing decide-recovery
test and `test_wp13_webapp_new_pages.py`'s history test both needed the new
required `idempotency_key` field added to their POSTs -- updated, still
pass.

**REQ-038 (invitation landing) -- fixed.** MFA/recovery were already real;
the actual gap was that `accept_invitation` (`app/routers/orgs.py`) had no
`/ui` page at all -- an invited user holding a token had nowhere to go.
Built: `GET/POST /ui/invitations/accept` + `templates/invitation_accept.html`,
deliberately GET-renders/POST-commits (same split as `decide_page`/
`decide_submit` -- an accept is a state-changing action and must never
happen on a GET). A signed-out visitor's landing page links to
`/ui/login`/`/ui/register` carrying a new `next` parameter set to the
landing page's own URL; `login_submit`/`register_submit`/
`mfa_login_verify_submit` all now redirect to `next` (via a new
`_safe_next` helper -- constrained to same-app `/ui/` paths only, since this
is the first redirect target in the app that ever comes from a query
string/form field rather than being hardcoded, and an unconstrained one
would be an open-redirect vector) instead of always landing on the generic
org picker, satisfying REQ-038's own verify text ("An invited user reaches
the intended project after sign-in"). A signed-in acceptance redirects
straight into that organisation's `my-work` page; an expired/reused/
wrong-email token renders the landing page's own honest error (reusing
`accept_invitation`'s existing error text), not a crash. The invite-creation
flash message in `settings.html` now shares the actual landing URL, not
just the bare token, so an admin has something directly clickable to send
out-of-band (still no mail infra -- WP03 gap, unchanged). New
`backend/tests/test_req038_invitation_landing.py` (3 tests, live Postgres):
sign-out-then-register-via-`next` lands back on the invitation page and then
on the org's settings (role correctly non-admin); GET is confirmed to have
no side effect (`/me/orgs` checked before and after, membership only
appears after the POST); a reused token shows the honest "already used"
error rather than an unhandled exception.

**REQ-024 (atomic authority recheck) -- the prior note was wrong on 2 of 3
counts; the 1 real count is now fixed too.** The 2026-09-24 pass linked
REQ-024 to IPA04 and wrote: "exception validity, tenant membership and
compensating-reviewer authority are read without equivalent coordinated
(locked) protection on the decision-commit path" -- without re-checking
that claim against the code that was actually there. Reading
`app/routers/decisions.py` directly found:
- **Exception validity**: already `FOR UPDATE`-locked --
  `_exception_is_currently_valid(db, exc, lock=True)`, called from
  `_compute_readiness(..., lock=True)` inside `_record_decision`. Added by
  `b8bb22a` (BGP-F03 follow-up, 2026-09-18/19) -- **before** the 2026-09-24
  note was even written.
- **Compensating-reviewer authority**: also already locked --
  `_check_separation_of_duties`'s two `.with_for_update()` calls on the
  reviewer's tenant `Membership` and `ProjectMembership` rows. Same
  `b8bb22a` commit.
- **Tenant membership**: this part was real. `app/deps.py`'s
  `get_active_membership` checks the caller's own tenant-level `Membership`
  exactly once, unlocked, before the route handler even runs --
  `_require_decision_authority` locked the caller's `ProjectMembership` but
  never re-checked their tenant `Membership` at commit time. A concurrent
  removal of the caller from the organisation entirely (not just this
  project) between that initial check and the eventual commit could
  previously still ride through to a recorded decision.

This is the second time a same-day tracker note has overclaimed a gap
without checking the code first (the first was REQ-020, above) -- worth
treating as a pattern: **re-verify a prior session's own "still open" note
against the actual code before either fixing it or forwarding it**, the same
discipline already applied to external review documents.

Fixed the one real piece: `_require_decision_authority` now also locks and
rechecks the caller's tenant `Membership` row (`Membership.active`), same
fixed lock order as the rest of this path (project membership, then this,
then evidence). New
`test_bgp_f03_decision_concurrency.py::test_tenant_membership_lock_blocks_a_concurrent_writer`
(live Postgres, same lock-blocking technique as the sibling
ProjectMembership/evidence-item proofs already in that file) -- the
fixture there was extended with a real `memberships` row for exactly this.
A sequential SQLite test would have proven nothing here (the pre-existing,
unlocked `get_active_membership` check already catches a deactivation that
happens *before* a request starts; only the live-Postgres lock proves the
*concurrent* case this fix actually closes) -- considered and deliberately
not written, rather than added for the sake of a test that would pass
whether or not the fix existed.

All three of REQ-024's own verify-text clauses now hold with passing tests:
evidence changes (existing), membership changes (ProjectMembership existing
+ tenant Membership new), repeated idempotency keys (existing,
`test_decisions.py`'s "same idempotency key must return the same decision"
test).

**Records corrected**: Requirements sheet -- REQ-024, REQ-035, REQ-038 all
moved to "Pass" with the corrected/new evidence above (REQ-024's cell keeps
the existing Milton-approved PR#3/#4 citation for the locks that were
already right, since that citation remains true; the new tenant-Membership
lock is separately noted as not yet reviewed). Acceptance sheet -- AC10,
AC18, AC21 (the criteria REQ-024/REQ-035/REQ-038 each roll up into) all
moved to "Pass" accordingly. `docs/DEFECT_REGISTER.md` gets three new rows:
IPA03 (Closed), a new "REQ-038 invitation landing gap" row (Closed, not
itself an IPA-numbered finding), and a "REQ-024 concurrency note, partially
wrong" row (Closed) that documents the correction, not just the fix. IPA02
and IPA04 are untouched and stay open, correctly -- IPA04's broader "no
independent assurance has been performed" claim is not satisfied by closing
one of its narrower, code-fixable sub-pieces.

Not independently reviewed by Milton -- same standing caveat as every other
fix in this project. Nothing pushed this session (local commit only, same
"push is a separate, explicit ask" rule as always).

## kenAddme named owner for the six DEC items blocking IPA02/IPA04 (2026-09-25)

User said "Use kenAddme, the collaborator as the lead to close these gaps"
(IPA02 and IPA04). **What this session actually did, and what it deliberately
did not do:**

Filled the previously-blank "Named owner" column (Decisions sheet,
`docs/blueprint/Build_Governance_Platform_Implementation_Tracker_v0.2_Approved.xlsx`)
for **DEC05, DEC06, DEC07, DEC08, DEC11, DEC12** with kenAddme -- the same
pattern DEC01 already uses (that row names Freston Kenny Adedeme as delivery
lead and MiltonBello15 as independent reviewer, both verified as real,
active GitHub participants via `gh pr view`, not just accepted on paper).
kenAddme is likewise a real, active collaborator: `APPROVED` reviews on PR#5,
PR#6 and PR#7, independently checked via `gh pr view --json reviews` in the
2026-09-22 BGP-HR-001 backfill session, not merely named.

**This is an ownership assignment, not a decision.** Each of the six cells
says so explicitly and names what's still actually missing:
- **DEC05** (Operations and security leads): Candidate A vs. B, covered
  failure scenarios, custody -- still unspecified.
- **DEC06** (Privacy reviewer and owner): actual retention periods, the
  permanent-record conflict -- still unspecified.
- **DEC07** (Technical lead): rule vocabulary limits, the third permitted
  framework -- still unspecified.
- **DEC08** (UX and technical leads): sample sizes, device/network
  profiles, numeric performance budgets -- still unspecified.
- **DEC11** (Security lead and owner): break-glass scope, approval path,
  independent key custody -- still unspecified.
- **DEC12** (Data owner): already "Decided" at the policy level (see its own
  row) -- what's missing is a named Data owner to actually authorise and
  reconcile any real import, which kenAddme is now that named owner for.

Status/Decision record/Approval date columns were deliberately left
untouched for all six -- filling Named owner does not manufacture the
decision content, and this session did not fabricate any of it.
`docs/DEFECT_REGISTER.md`'s IPA02 and IPA04 rows updated with a pointer to
this assignment (still Open -- an owner name doesn't close either row).
Tracker item **#131 (SDLC G4.04)**, the direct match for IPA04, got its
`owner` field set to kenAddme with the same caveat; status stays "Not
started" -- unchanged, since no actual assurance work has happened.

**Worth surfacing, not silently accepted**: one name across six structurally
distinct specialist roles (operations, security, privacy, technical, UX,
data) spanning DEC05/06/07/08/11/12 is a lot of hats for one collaborator
whose only established track record in this project is PR-approval
comments. Recording the assignment is a legitimate, reversible admin action
-- but it does not by itself demonstrate kenAddme has the standing or
intent to actually specify six quite different technical/privacy/security
decisions. If that's not the intended scope, the fix is to name different
owners per decision (or per domain), not to leave this assignment as
substituting for the substance.

## DEC05/06/07/08/11/12 answered by kenAddme, accepted by delivery lead (2026-09-27)

`BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.pdf` arrived — kenAddme's
substantive answers to the six DEC items the 2026-09-25 entry above named
them owner of. User said to use it "as the answers." **What this session
actually did, and what it deliberately did not do:**

Transcribed the PDF into `docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md`
(a plain markdown rendering of the same content, checked against the PDF
page by page, not paraphrased) and, per the original intake document's own
"how this gets used" instructions, into the xlsx Decisions sheet
(`docs/blueprint/Build_Governance_Platform_Implementation_Tracker_v0.2_Approved.xlsx`,
Current position/Status/Decision record/Approval date columns) for all six
rows. Status moved from "Partly decided" to "Decided" for DEC05/06/07/08/11
(DEC06/12 already carried real content; DEC12 was already "Decided" and is
now refined with the specific data-owner/controller-vs-processor split and
the import evidence checklist). This follows the exact same pattern already
established for DEC01/DEC04 in this file — the delivery lead accepting
content in conversation is what moves a DEC row's Status, and that has
never been treated as a substitute for an independent role sign-off.

**Same caveat as DEC01/DEC04, stated explicitly again here**: marking these
"Decided" reflects the delivery lead's (Freston Kenny Adedeme's) acceptance
of kenAddme's answer, not an independent sign-off by each item's actually
responsible role — Operations/security leads (DEC05), Privacy reviewer/owner
(DEC06), Technical lead (DEC07), UX/technical leads (DEC08), Security
lead/owner (DEC11). The answer document itself flags two of its own
recommendations as not fully settled, and those flags are carried forward
verbatim rather than smoothed over:

- **DEC05**: the accepted answer is "Candidate A+," a synthesis of
  synchronous durable replication plus an independent hash-chain anchor —
  not literally Candidate A or Candidate B as the blueprint originally
  posed the choice. This changes what Operations/security leads are
  actually being asked to confirm at review.
- **DEC11 Q19**: the tenant-visibility default for break-glass access
  (pre-approval, with a life-safety/legal-compulsion carve-out) is
  presented by the answer document itself as "Security lead/owner's call to
  make, not a settled fact" — a genuine privacy-vs-incident-response-speed
  trade-off, not a resolved one.

**What did not change and was deliberately left alone**: `docs/DEFECT_REGISTER.md`'s
IPA02 and IPA04 rows stay **Open** — updated to point at the new answer
content, but neither closed, because content answers are not the same as
built UI (IPA02, at the time of this entry: UI08/UI09/membership-revocation
still don't exist — see 2026-09-28 below for membership-revocation/role-change
being built since) or performed assurance work (IPA04: the durability
mechanism isn't implemented, and no WCAG audit/usability sessions/
independent security review/restore drill against the new numeric targets
has happened). Tracker item **#131** (SDLC G4.04, security/privacy/
performance/accessibility/resilience testing) stays "Not started" — content
answers are not test evidence. **No `tracker_cli.py gate` action was taken
and none of this substitutes for one** — same rule as every other DEC/
ownership update in this file.

Not independently reviewed by Milton. Nothing pushed this session (the new
`.md` file and the xlsx edit are local only, same "push is a separate,
explicit ask" rule as always).

## Membership revocation/role-change built, closing one of IPA02's three sub-gaps (2026-09-28)

Built the UI10 gap this file and `docs/DEFECT_REGISTER.md`'s IPA02 row have
both flagged since WP13 (2026-09-22): `settings.html` had documented "there
is no revoke-membership or change-role control here yet" as an honest gap
rather than a faked control, and IPA02 named "membership revocation/
role-change" as one of three still-unbuilt frontend pieces (alongside UI08
guided template authoring and UI09 export/import).

**What was built**, branch `wp13-15-frontend-evidence`, commit `6842447`:

1. `backend/app/routers/orgs.py` — two new endpoints, both
   `require_role(Role.TENANT_ADMINISTRATOR)`-gated:
   - `POST /orgs/{tenant_id}/memberships/{membership_id}/role` — changes a
     member's role; refused (409) if the target is the tenant's only active
     administrator and the new role isn't `tenant_administrator`, so a role
     change can never leave a tenant with zero admins.
   - `POST /orgs/{tenant_id}/memberships/{membership_id}/revoke` — sets
     `active = False` (row preserved, never deleted — same pattern
     REQ-021's exception-revoke already used, so `access_review`'s "includes
     inactive memberships too" claim stays true against a real revocation,
     not just a seeded-inactive test row); same only-active-admin 409 guard.
   - Both log a `security_event` (`membership_role_changed` /
     `membership_revoked`) with actor, target, tenant, and old/new role.
   - `AccessReviewEntryOut` gained a `membership_id` field — the UI needs it
     to address the row; `access_review`'s existing output shape otherwise
     unchanged.
2. `backend/app/webapp/router.py` — two new page-layer POST handlers
   following the file's existing pattern (`_require_page_membership` guard,
   call the router function directly, `_reset_tenant_context` after any
   caught `HTTPException`); `settings_invite_submit` was simplified in the
   same pass (no behaviour change, just deduplicating the RLS-context
   handling the new handlers also needed).
3. `backend/app/templates/settings.html` — the roster table gained an
   "Actions" column: an inline role-change `<select>` + submit per active
   row, and a revoke button; revoked rows show `—` instead. The old
   "no such control" hint paragraph was removed since it's no longer true.

**Real defects found and fixed via this work, not just written against a
spec**: two RLS-context bugs in the new webapp handlers' revoke/role/
invite-success paths, caught while writing `test_ipa02_membership_settings_ui.py`
against real RLS the same way WP11/WP13's own prior entries describe — not
found by inspection alone.

**Tests**: `test_ipa02_membership_revocation.py` (10, API-layer: role
change, revoke, the only-active-admin 409 guard on both endpoints,
double-revoke conflict, non-admin forbidden) and
`test_ipa02_membership_settings_ui.py` (6, webapp-layer: the same paths
through the actual HTML forms, including a non-admin never seeing the
Actions column). Full suite: **177 passing** (was 171), run against the
project's own `.venv` — `.venv/Scripts/python.exe -m pytest -q`, exit 0,
`483.85s`. `ruff check .` — all checks passed; `ruff format --check .` — 77
files already formatted.

**What this does and does not close**:
- `TRACKER.md`'s own UI10 gap note (above, in the WP13-15 entry) — closed;
  edited in place this session rather than left contradicting current code.
- `docs/DEFECT_REGISTER.md`'s **IPA02 row — stays Open**, edited to record
  that membership-revocation/role-change is the one of its three named
  sub-gaps now built; UI08 (blocked on DEC07) and UI09 (blocked on
  DEC06/DEC12) are unaffected by this work and remain unbuilt. IPA02 as a
  row does not close until all three exist.
- **No `tracker_cli.py gate` action was taken and none of this substitutes
  for one** — same rule as every other entry in this file. This is an
  evidence-item-level update, not a gate decision, and not independent
  review sign-off (not reviewed by Milton).

Pushed to `origin/wp13-15-frontend-evidence` (`ad14d31..6842447`) this
session — unlike the DEC-intake entry immediately above, this one was an
explicit push request, not left local.

## UI09 export/import built, closing a second of IPA02's three sub-gaps (2026-09-28)

Same session as the membership-revocation entry above; user said "go on with
it, finish it" after being shown the remaining IPA02 candidates. UI09
(export/import) was picked over UI08 (template authoring) as the more
contained build -- it wraps `app/routers/exports.py`'s existing
create_export/validate_import/commit_import, which WP09/BGP-F04 already
built and hardened; UI08 is a real rule-builder UI, not just forms over an
existing endpoint.

**What was built**, branch `wp13-15-frontend-evidence`:

1. `backend/app/routers/exports.py` -- two new read-only list endpoints
   that did not exist before (only get-by-id existed): `GET
   /orgs/{tenant_id}/exports` (any active member, matching create_export's
   own gate; summary shape only -- `archive_digest` etc, never the full
   `archive_json`, since a tenant's whole archive is not what a history list
   needs) and `GET /orgs/{tenant_id}/imports` (same gate as the existing
   get_import -- any active member, not admin-only; reuses `ImportJobOut` as
   its own response shape since validation/commit reports are small
   counts/errors, not a full data dump, so there was no reason to strip them
   out the way exports' archive is stripped).
2. `backend/app/webapp/router.py` -- new `/ui/orgs/{tenant_id}/export-import`
   page plus four action routes (create export, download an export as a
   file, validate an import from a pasted textarea or an uploaded file,
   commit a validated import), following the exact same pattern as every
   other page in this file (`_require_page_membership` guard, explicit
   `require_role(...)()` re-invocation for admin-only actions, `_reset_
   tenant_context` after every mutating call including the SUCCESS path --
   `db.commit()` ends the `SET LOCAL` scope the same way a caught
   exception's rollback does, so this was needed even where nothing failed).
   Download streams the archive as `application/json` with a
   `Content-Disposition: attachment` header built from the existing
   `get_export` JSON function, not a new storage mechanism.
3. `backend/app/templates/export_import.html` (new) + a new "Export &
   import" link in `base.html`'s primary nav. Honestly labelled, not
   glossed over: FE-068's queued/processing/expired states don't exist to
   show (exports are synchronous in this prototype, no background worker,
   same WP01 scope limit noted since WP09) and FE-073/FE-074's retention/
   legal-hold/disposal controls are deliberately absent (DEC06 has an
   accepted design but no built enforcement mechanism -- see IPA04; FE-074's
   own rule is that no such control precedes that). FE-071's unmapped-actor
   explanation and FE-072's explicit, separate commit step are both shown
   inline in the validation/commit report display.

**Verified two ways, not just by the test suite**: 6 new tests
(`test_ui09_export_import.py`, live-Postgres-only, same pattern as the
membership-revocation tests) covering the create/download round trip, both
input methods (pasted text and an uploaded file), admin-only gating on
validate/commit, a malformed-JSON paste showing an honest parse error
instead of a raw 500, and a non-admin seeing export history but not the
import form. Full suite: **183 passing** (was 177). Ruff clean and
formatted. Separately, a real HTTP walkthrough against a running dev server
(`uvicorn`, port 8000) exercised the whole flow twice -- once via curl
(register, create org, create export, download and verify its
`manifest.source_tenant_id`, validate a pasted archive into a second org,
commit it, confirm the malformed-JSON error path and the nav link) while
the `claude-in-chrome` browser extension was not yet connected, then again
through the actual rendered browser once it connected: registered, created
an org, clicked through the nav link, created an export, downloaded it,
pasted an archive via an in-page `fetch` (same session cookies) into the
textarea, validated, expanded the validation report inline (FE-071 text
visible), committed, and expanded the reconciliation report (FE-072,
`.manifest-summary` counts table) -- all rendered correctly, same visual
language as the rest of the app, no console errors observed. This is the
same "verify via a live browser walkthrough, not just TestClient" discipline
WP11/WP13's own entries describe, and it did not surface a bug this time
(unlike WP11/WP13, which each found one) -- stated honestly rather than
implying every walkthrough finds something.

**Incidental finding, not itself part of this build**: DEC07 (rule
vocabulary/third framework -- UI08's own named content blocker) was already
moved to "Decided" on 2026-09-27 (see that dated entry above), alongside
DEC06/DEC08/DEC11/DEC12 -- it was simply never revisited when picking which
UI09/UI08 gap to build next. This means UI08's remaining blocker, same as
UI09's was before this session, is now **only the build itself**, not an
open decision -- worth knowing before assuming UI08 needs another decision
round before it can start.

**What this does and does not close**:
- `docs/DEFECT_REGISTER.md`'s **IPA02 row -- stays Open**. Two of its three
  named sub-gaps (membership-revocation/role-change, export/import) are now
  built; UI08 (guided template authoring) is the one remaining piece, and
  it is unaffected by this session's work.
- **No `tracker_cli.py gate` action was taken** -- same rule as every other
  entry in this file. Not independently reviewed by Milton.

Not pushed as of this entry -- this session's commit/push requests have so
far been separate, explicit asks each time (see the membership-revocation
entry above), and this UI09 work had not yet had one at the time this entry
was written. **Update**: user then said "yes, commit and push it" -- committed
`dc4ae11` and pushed to `origin/wp13-15-frontend-evidence` (`2d0a27e..dc4ae11`)
later the same session.

## UI08 guided template authoring built, closing IPA02's last sub-gap (2026-09-28)

Same session again; user said "go on and build it" after the UI09 push.
UI08 is the last of IPA02's three named sub-gaps (guided template authoring,
UI09 export/import, membership revocation/role-change) -- the other two both
closed earlier this session.

**Scoping decision, made explicit before writing any code**: `app/rule_
engine.py` still implements only the pre-DEC07 vocabulary (eq/in/all/any,
depth 5) -- its own docstring says "DEC07 ... is still open", which is now
stale (DEC07 was Decided 2026-09-27, see that entry above: adds `not`,
`gte`/`lte`, `count(...)`; tightens to a 200-node cap, a hard evaluation
timeout, and a `vocabulary_version` stamp per template version). Implementing
DEC07's actual vocabulary additions is real backend work, separate from and
larger than "build the UI08 page" -- conflating the two would have meant
either silently shipping a guided UI that claims to support a vocabulary the
engine doesn't actually have, or quietly expanding scope into rule-engine
changes nobody asked for this session. Built UI08 against the vocabulary the
engine **actually implements today** (eq/in/all/any) and flagged the DEC07
implementation gap here instead of touching rule_engine.py at all.

**What was built**, branch `wp13-15-frontend-evidence`, not yet committed as
of this entry:

1. `backend/app/routers/templates.py` -- one new read-only endpoint, `GET
   /orgs/{tenant_id}/templates/{template_id}/versions` (only get-by-id
   existed before; the guided page needs a template's full version history
   to show which draft is current and which versions are already published).
2. `backend/app/webapp/router.py` -- a `/ui/orgs/{tenant_id}/templates` list
   page (create blank / import JSON / fork, per REQ-012) and a
   `/ui/orgs/{tenant_id}/templates/{template_id}/versions/{version_id}`
   guided editor: structured forms for classification (tracks/classes/
   roles/statuses/decision_outcomes), add/remove gate, add/remove rule --
   with permitted-role and applicable-class pickers sourced from the
   template's own declared roles/classes (checkboxes, not free-typed
   strings, so a rule can't reference an undeclared role or class), and a
   bounded guided condition builder (up to 3 flat eq/in tests, optionally
   combined with one level of AND/OR) that covers the vocabulary's common
   case without hand-written JSON. None of this is a new mutation path --
   every guided action fetches the current draft's schema, mutates a cloned
   copy in Python, and calls the SAME `update_draft` the JSON API and the
   Advanced JSON box both use, so guided edits get exactly the same Sec.5.5
   validation as everything else, never a shortcut around it.
3. **Deliberate scope boundary, not an oversight**: the guided condition
   builder does not expose `applicability` (a rule's separate, rarer
   "does this rule even apply" field) -- grepped every fixture and test
   schema in the repo first and found it unused anywhere, so building a
   guided UI for a field nothing actually uses would have been speculative.
   It is still reachable through the Advanced JSON escape hatch if ever
   needed. Nested conditions beyond one level of AND/OR are the same --
   Advanced JSON, not a recursive form (DEC04: no SPA, no client-side
   condition tree; every guided action here is a plain HTML form + a full
   page reload, same as every other webapp page in this project).
4. `backend/app/templates/templates_list.html` and `template_editor.html`
   (both new) + a new "Templates" nav link in `base.html`.

**Two real bugs found and fixed while writing the tests, not just the
feature itself**:
1. `_describe_condition` (the plain-language condition renderer) crashed
   with a Jinja `UndefinedError` for any rule with no `conditions` key at
   all -- which is every rule built via the guided add-rule form without a
   condition, since the handler only sets the key when a condition was
   actually configured. Jinja's dot-access on a dict with no such key
   returns its own `Undefined` sentinel, not Python `None`, so the
   function's `if cond is None` check never caught it. This would also
   have broken on any *imported or advanced-JSON* rule that simply omits
   `conditions` (fully valid per the Pydantic model), not just guided-form
   rules -- a real, broader gap, not a guided-UI-only edge case. Fixed by
   checking `if not cond` instead, which is true for `None` and for
   `Undefined` alike.
2. A test wrongly assumed removing the only gate in a template should
   succeed. It doesn't, and shouldn't: `TemplateSchema.gates` carries
   `Field(min_length=1)` (a template with zero gates is meaningless), so
   `update_draft` correctly rejects it with the same validation every other
   path gets. This is the guided UI correctly inheriting a real invariant,
   not a bug -- the test was corrected to add a second gate before removing
   the first, and to separately assert the honest rejection when only one
   gate exists.

**Tests**: `test_ui08_template_authoring.py` (10, live-Postgres-only, same
pattern as the IPA02/UI09 webapp tests) -- admin-only visibility, blank
draft creation, guided add-gate/add-rule with both a single condition and an
`any`-combined pair (asserted against the actual persisted `Condition` JSON
shape, not just page text), remove-rule/remove-gate (including the
min-gates-1 rejection above), publish making a version immutable and
offering Fork, Advanced JSON replace plus its malformed-JSON error path,
non-admin denial on every mutating action, and metadata update + import via
the list page. Ruff clean and formatted.

**What this does and does not close**:
- `docs/DEFECT_REGISTER.md`'s **IPA02 row -- Closed, 2026-09-29**: all three
  named sub-gaps are now built (membership-revocation/role-change,
  export/import, guided template authoring), on the same "built, not just
  answered" basis the register's other closures use (IPA03's own precedent).
  Carried forward as a caveat, not a reopening condition: the guided UI is
  real and validated, but rule_engine.py's DEC07 vocabulary additions
  (`not`/`gte`/`lte`/`count`, the 200-node cap, the evaluation timeout,
  `vocabulary_version` stamping) are NOT built. That is a separate, real gap
  this session did not touch -- stated explicitly in the register's own row
  so closing IPA02 is never later misread as "DEC07 is fully implemented."
- **No `tracker_cli.py gate` action was taken.** Not independently reviewed
  by Milton.

## DEC08 API-layer latency budgets built and CI-enforced, one of IPA04's DEC08 sub-parts (2026-09-29)

Same branch, next session. IPA02 is fully closed now (previous entry), so
this moves to IPA04's remaining named pieces -- DEC08, DEC05, DEC11 -- per
`TRACKER.md:1152`'s own framing ("IPA04 needs named decision owners for
DEC05/DEC08/DEC11 plus real independent assurance work"). DEC08 answered
three numeric budget families (reads, ordinary writes, decision writes) plus
render-timing/page-weight budgets and an async export-streaming budget --
its own words: "enforced in CI as a blocking budget check, not a dashboard
someone reads occasionally."

**Scoping decision, made explicit before writing any code**: DEC08 names
three separate things (server-side API latency, browser render-timing/
page-weight, and export-streaming). Only the first is buildable honestly
right now:
- API latency: real, measurable today via `TestClient` against live
  Postgres -- server time at origin, excluding client network, which is
  exactly DEC08's own stated scope for this part.
- Render-timing (LCP/INP/CLS) and page-weight budgets need a Lighthouse-CI-
  style harness under an emulated Fast-3G/mid-range-Android profile. This
  project has no such tooling wired up -- a separate, larger addition, not
  something an API test can measure.
- Export-streaming ("must begin streaming within 2s") assumes an async
  worker queue. `exports.py`'s own docstring says exports are synchronous in
  this prototype (WP01's own scope limit, no worker exists) -- there is no
  "begin streaming" moment to measure, so a check against that premise would
  test something that doesn't exist rather than something real.

Built only the first piece. Flagged, not faked, that the other two remain
open.

**What was built**, branch `wp13-15-frontend-evidence`, commit `2e9ee9e`:

1. `backend/tests/test_dec08_performance_budgets.py` -- three tests, each
   against real Postgres (skips honestly if unavailable, same as every other
   IPA02/WP13+ webapp/API test in this suite): read budget (gate-view/
   dashboard `my-work`, p95<=300ms/p99<=800ms, n=40 samples), ordinary-write
   budget (evidence revision creation, p95<=500ms, n=30), decision-write
   budget (Hold-then-supersede chain on one occurrence, exercising the real
   idempotency-check/manifest-revalidation/coordinated-lock/append-only-
   insert path, p95<=800ms/p99<=1.5s, n=20).
2. `.github/workflows/ci.yml` -- a dedicated named step running just this
   file, after the full `pytest -q` run. Same reasoning as the existing
   Dependency/Secret-scan steps getting their own names despite being
   conceptually "more checks already covered": a budget breach shows up by
   step name in the Actions UI, not buried as "some test in the suite
   failed."

Ran against the actual live-Postgres setup this session (not skipped): all
three passed on the first run, so the budgets hold today, not just in
theory. Full suite 196/196, Ruff clean.

**What this does and does not close**:
- `docs/DEFECT_REGISTER.md`'s **IPA04 row -- stays Open.** Only one of
  DEC08's three named sub-parts is built; DEC05's durability mechanism and
  the independent assurance activities (WCAG audit, usability sessions,
  independent security review, restore-drill) are untouched. Row text
  updated to name the commit and the two still-unbuilt DEC08 sub-parts
  explicitly, so this is never later misread as "DEC08 is done."
- **No `tracker_cli.py gate` action was taken.** Not independently reviewed
  by Milton.

## DEC05 durability mechanism built, IPA04's DEC05 sub-part (2026-09-29)

Same branch, next session. Resumed from a prior session's approved design
(`docs/superpowers/specs/2026-09-29-dec05-durability-mechanism-design.md`) --
that spec's own s1 first cross-referenced DEC05's five numbered sub-answers
against what already existed in this codebase (WP08's `app/integrity.py`
hash chain, the `bgp_backup` role, `scripts/restore_drill.py`) before
naming what was actually missing: an app-layer synchronous chain-link at
decision-commit time, and an external, independently-custodied anchor for
tamper-evidence (the exact gap `IntegrityCheckpoint`'s own docstring in
`app/models.py` already named: "Genuine independence from a rogue DBA
needs verification material with custody OUTSIDE this Postgres instance
entirely").

**What was built**, branch `wp13-15-frontend-evidence`, commit `1a450f0`:

1. **G1 -- synchronous chain-link at commit** (`app/integrity.py`'s
   `checkpoint_new_events`, refactored out of the existing `take_checkpoint`
   so the pre-existing manual admin endpoint is unchanged in behavior;
   `app/routers/decisions.py`'s new `_checkpoint_this_project`, called from
   both `_record_decision`'s success path and its `_deny` path). A decision
   or denial's own audit event is folded into a new `IntegrityCheckpoint` in
   the SAME transaction as the decision/denial commit -- `pg_advisory_
   xact_lock(hashtext(project_id))` (Postgres-only, skipped on the SQLite
   test fixture) serializes two concurrent decisions on the same project so
   neither reads a stale "latest checkpoint."
2. **G2 -- external WORM anchor** (`app/worm_anchor.py`'s
   `WormAnchorStore`/`LocalWormAnchorStore`, same interface-then-swap-
   backend shape as `app/attachment_storage.py`; `backend/scripts/
   anchor_worm.py`, manually-run same as `restore_drill.py`; new
   `worm_anchor_receipts` table, migration `0017_dec05_worm_anchor.py` --
   a separate table rather than a column on `integrity_checkpoints`,
   because a nullable-column UPDATE policy permissive enough for that one
   column would be exactly as permissive about `chain_digest` on the same
   row, undermining WP08's existing zero-UPDATE-ever guarantee; see the
   design spec s4.2 and `WormAnchorReceipt`'s own docstring for the full
   reasoning, including why this table carries no tamper-evidence weight
   of its own).
3. **G3/G4 -- independent verification** (`app/integrity.py`'s new
   `verify_against_anchor`, cross-checking each checkpoint's DB-stored
   `chain_digest` against its WORM-anchored copy; `backend/scripts/
   verify_against_anchor.py`, run as `bgp_backup` -- reused, no new role,
   same reasoning `restore_drill.py` already established; new scheduled
   `.github/workflows/integrity-verify.yml`, daily cron matching DEC05
   s4's "at least daily", plus `workflow_dispatch` -- the first time
   `bgp_backup` runs anywhere but a developer's own machine, a real gap
   this closes as a side effect, same precedent as DEC08's own dedicated
   CI step).

**A real bug found and fixed while building this, worth recording**:
`app/db.py`'s `SessionLocal` is `autoflush=False` -- `checkpoint_new_events`
queries `AuditEvent` rows with a fresh `SELECT`, which does not see a
caller's own just-`db.add()`'d, not-yet-flushed audit event. The first
version of this code silently checkpointed zero events on every decision
(no error, just `checkpoint_new_events` returning `None`) until
`test_dec05_durability_mechanism.py`'s very first test caught it. Fixed by
an explicit `db.flush()` at the top of `checkpoint_new_events` itself, so
every caller gets the fix rather than needing to remember it.

**A second, pre-existing test that broke as a direct, expected
consequence** (not a regression in the new code, a stale assumption in old
test text): `test_integrity.py::test_checkpoint_and_verify_clean_when_
untampered` asserted the manual `.../integrity/checkpoint` endpoint's own
response had `event_count == 1` -- true before DEC05, when that endpoint
was the only thing that ever checkpointed anything. Now the decision's own
commit already checkpointed that event, so the manual call correctly finds
nothing new and returns `None`. Fixed to assert the checkpoint via `GET
.../checkpoints` instead of the now-empty manual-call response; the
sibling no-op test updated with the same honest note. Both pass, 6/6.

**Testing** (`backend/tests/test_dec05_durability_mechanism.py`, live-
Postgres-only, 6 tests, all passing): decision commit folds its own audit
event atomically; a denied decision's audit event is also folded; two
decisions on different occurrences in the same project produce non-
overlapping, independently-reverifiable checkpoints; the
`pg_advisory_xact_lock` primitive actually blocks a second session while
held (lock-blocking proof, same technique as `test_bgp_f03_decision_
concurrency.py`, avoiding real-thread flakiness); `anchor_worm.py`'s core
function anchors once and no-ops on rerun; and the test that is this
work's actual point -- a simulated rogue-DBA rewrite (as `bgp_owner`,
temporarily lifting `integrity_checkpoints`' normally-unconditional UPDATE
deny via `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY`, DDL rights RLS
cannot take from a table owner) that changes an audit event's content and
recomputes its checkpoint's `chain_digest` to match, self-consistently --
`verify_integrity`'s same-instance re-derivation is proven blind to it
(`ok: True`, exactly as the design predicted), while `verify_against_
anchor`'s cross-check against the untouched external copy catches it
(`ok: False`, opens an `IntegrityIncident`).

**Verification honestly incomplete tonight**: this machine's full
`pytest -q` suite (196+ tests) could not be run to completion -- six
consecutive attempts (the full suite twice, a five-file targeted slice
once, `test_decisions.py` alone three times) were killed by the harness's
own low-memory guard, not by a test failure (`FreePhysicalMemory` sampled
between 79 MB and 440 MB of 3.6 GB total across attempts, with `Memory
Compression` alone holding over 1 GB). Every test that ran before each
kill passed, with the sole exception of the one real regression above,
found and fixed. What IS independently confirmed, each run to completion:
`test_dec05_durability_mechanism.py` (6/6), `test_integrity.py` (6/6,
post-fix), `ruff check .` and `ruff format --check` clean on every
changed/new file, and the migration applying cleanly to the real dev
database. The full-suite run is the concrete next check this session did
not complete -- do not read "DEC05 is built" as "the full suite was
reconfirmed green tonight."

**What this does and does not close**:
- `docs/DEFECT_REGISTER.md`'s **IPA04 row -- stays Open.** The durability
  mechanism itself is now built (all three of G1-G4), but IPA04 also names
  the independent fault/recovery/usability/accessibility/security
  assurance activities (WCAG audit, usability sessions, independent
  security review, a restore-drill against DEC05's numeric RPO/RTO
  targets) -- none of which this or any prior session has performed, and
  none of which an agent session can perform on its own or claim from a
  document alone. Real cross-zone/cross-region replication (DEC05 s2/s4's
  numeric availability targets) also remains untouched -- no multi-node
  Postgres infrastructure exists in this prototype; named in the design
  spec's own non-goals, not silently dropped.
- **No `tracker_cli.py gate` action was taken.** Not independently
  reviewed by Milton or by Operations/security leads (DEC05's own named
  approvers) -- the delivery-lead acceptance of kenAddme's DEC05 answer
  (2026-09-27) is not that independent sign-off, and building the
  mechanism the answer specifies is not either.

## Full suite reconfirmed, one transient failure root-caused, not a code regression (2026-09-30)

Same branch, next session. Picked up exactly where the DEC05 entry above left
off: "the full-suite run is the concrete next check this session did not
complete." Ran it to completion this time (`pytest -q`, this repo's own
`.venv`, live Postgres): **199 passed, 3 failed, 939.69s** -- the run
completed instead of being OOM-killed like every attempt the prior session
made, but not clean.

All three failures were in `test_dec08_performance_budgets.py`, all budget
misses, not errors: read p95 341ms (budget 300ms), ordinary-write p95 837ms
(budget 500ms), decision-write p95 1095ms (budget 800ms).

**Investigated per `superpowers:systematic-debugging` before touching
anything** -- the read-budget test (`GET .../my-work`) and the ordinary-write
test (an evidence revision) don't call any DEC05 code path at all, which
argues against "DEC05 made the checkpoint step slow" as the sole
explanation; only the decision-write test exercises `_checkpoint_this_project`.
**Hypothesis**: these are transient, this specific memory-starved machine's
own resource contention (3.6GB total RAM, `FreePhysicalMemory` at 233MB and
falling before the run even started, `Memory Compression` alone holding
1.4GB) landing on this particular file, not a durable latency cost DEC05
added to the request path. **Tested minimally**: re-ran
`test_dec08_performance_budgets.py` alone, same machine, same live Postgres,
immediately after the full run finished (free memory had only recovered to
289MB, so not a "machine was idle" confound) -- **3/3 passed**, comfortably,
in 24.87s. That includes the decision-write test, the one test that
genuinely does exercise the new checkpoint code on every iteration --
confirming the checkpoint mechanism's real steady-state overhead does not
by itself blow the 800ms budget.

**Conclusion, not "incomplete investigation" rounded up to "fine"**: the
failure is specific to running the entire ~200-test suite in one long-lived
process on this severely memory-constrained dev machine, immediately
following `test_dec05_durability_mechanism.py`'s own heavy work in the same
run (real local-disk WORM writes, a rogue-DBA `ALTER TABLE ... NO FORCE ROW
LEVEL SECURITY` DDL test) -- not a regression in DEC05's actual latency
contribution to the decision-commit path. **Deliberately not "fixed"**:
did not loosen DEC08's numeric budgets (kenAddme's own accepted answer, not
this session's to weaken) and did not add a retry/skip to the test to paper
over it -- the honest record is that this machine can produce a false-red
budget check under load, which is worth knowing before ever reading a local
full-suite red on this specific file as "the code regressed" without
re-checking in isolation first. **Not yet known**: whether GitHub Actions'
own runners (far more RAM than this box) would ever reproduce this inside
`ci.yml`'s `pytest -q` step that runs before the file's dedicated step --
untested, no CI run exists on this branch yet to check against.

Ruff not re-run this session (no code changed). `docs/DEFECT_REGISTER.md`'s
IPA04 row's evidence text updated to point here instead of calling the
full-suite recheck "honestly incomplete" -- it is now complete, with this
transient-failure explanation attached, not silently marked green.

## Restore drill run against DEC05's actual numeric targets; a real reconciliation-reporting gap found and fixed (2026-09-30)

User said "proceed with IPA04" -- of everything IPA04 still names (WCAG
audit, usability sessions, independent security review, the restore-drill
against DEC05's numeric RPO/RTO targets, real cross-zone/region
replication), the restore-drill is the one piece that's concrete,
executable, and doesn't require a human participant or an independent
reviewer's own judgment -- `backend/scripts/restore_drill.py` already
existed (built WP08, 2026-09-17) but its docstring still cited REQ-029's
original 1h-RPO placeholder, written before DEC05 had an actual accepted
answer.

**Updated the script's docstring** to cite DEC05's real accepted numbers
(RPO 0 in-region / <=5 min cross-region, RTO 8 hours, "quarterly restore
test into a clean environment" -- DEC05's own words, this script is that
drill) instead of the stale unresolved-REQ-029 framing, and to state
plainly that the in-region/cross-region RPO figures need real replication
infrastructure this single-Postgres-instance prototype doesn't have and
this drill can't exercise either way (same non-goal already named in the
DEC05 design spec).

**Ran it for real** against live `bgp_dev`: backup 2.37s, restore 20.85s
into a genuinely fresh database -- both trivially inside the 8h RTO
target on this near-empty dev database (not a production-scale proof, see
the script's own "Honest limits" section). Row counts matched across all
16 tenant-owned tables.

**Then the reconciliation step reported `MISMATCH`** on the hash-chain
re-verification -- investigated per `superpowers:systematic-debugging`
rather than assumed benign or silently ignored, since IPA04/DEC05 both
treat a chain mismatch as exactly the kind of thing that must not be
rounded past ("a chain mismatch is treated as an S1 incident, acknowledged
within 1 hour"). Wrote a one-off read-only diagnostic script (not
committed, scratch use only) to identify every mismatching project
individually rather than trust the aggregate flag. **Root cause, confirmed
by grep against the actual source, not inferred**: all 141 of the
mismatches (out of 175 projects checked) trace to one single known
artifact -- `backend/tests/test_wp08_tenant_isolation_rls.py`'s own raw-SQL
fixture, which inserts an `IntegrityCheckpoint` row with
`chain_digest='original-digest'` (not a real 64-hex-char sha256 digest,
zero backing `AuditEvent` rows) to test the RLS policy directly, bypassing
the real checkpoint pipeline entirely. Because that table's append-only
guarantee means no role can ever UPDATE or DELETE such a row afterward
(by design, `app/models.py`'s own `IntegrityCheckpoint` docstring), every
run of that one test across every session that has ever used this shared,
never-reset `bgp_dev` has left one more behind -- 141 of them as of today,
confirmed to be the sole and exact explanation (zero mismatches had any
other shape once these were excluded).

**This is a real, if minor, finding in its own right, not just an
explanation to write off**: `restore_drill.py`'s binary
Reconciliation OK/MISMATCH signal was already permanently red on this
database and would stay that way forever, silently swallowing any future,
genuinely new integrity incident inside the same undifferentiated
"MISMATCH" bucket -- exactly the false-negative risk a quarterly assurance
drill exists to prevent. **Fixed** (not just documented): `restore_drill.py`
now classifies each mismatching project by digest *shape* -- a real chain
digest is always 64 lowercase hex characters (`app/integrity.py`'s own
`hashlib.sha256(...).hexdigest()`/`GENESIS_DIGEST`), so anything else is
provably fixture/instrumentation data regardless of which test produced it,
not a hardcoded match against one literal string. Output now reports
"known test-fixture artifact(s)" and "UNEXPLAINED mismatch(es)" as separate
counts; only a nonzero unexplained count fails the drill. **Deliberately
not attempted**: deleting or otherwise cleaning up the 141 rows -- doing so
would require bypassing the exact append-only guarantee (FORCE RLS,
no UPDATE/DELETE policy, not even for `bgp_owner`) that this whole
mechanism exists to enforce, working against the system's own design
rather than around a real problem in it.

Re-ran after the fix: **0 unexplained mismatches, reported OK** -- the
first genuinely trustworthy "Reconciliation OK" this drill has produced
since the fixture-pollution count passed 1. Ruff clean and formatted.
No test imports or calls this script (grep-confirmed), so this change
carries zero risk to the test suite.

**What this does and does not close**: this is the restore-drill sub-piece
of IPA04's remaining list, done for real against DEC05's actual accepted
target, not just the pre-DEC05 REQ-029 placeholder. **Still open as of this
entry, named explicitly**: an automated WCAG pass (attempted again
immediately after this entry, see below), real usability sessions
(Blueprint Sec.4.4 protocol -- kenAddme named as reviewer immediately after
this entry too, see below), and an independent security review -- the
latter needs a named, competent human reviewer independent of whoever
wrote the code (same boundary tracker item #124 has named since
2026-09-17), which no amount of agent work substitutes for. Real
cross-zone/cross-region replication remains a named non-goal of this
prototype, not silently dropped. **No `tracker_cli.py gate` action taken.**

## kenAddme named reviewer for usability sessions; automated WCAG pass retried and succeeded, one real fix (2026-09-30)

User said "KenAddme shold be the useability sessions revewer" and, in the
same turn, "And retry the WCAG AGAIN" -- two separate asks, handled in order.

**Usability-sessions ownership**: recorded kenAddme (already the named
owner for DEC05/06/07/08/11/12 since 2026-09-25 -- real, active,
`APPROVED` reviews on PR#5/#6/#7 per `gh pr view`) as named reviewer for
the Blueprint Sec.4.4 usability-testing protocol, on tracker item **#131
(SDLC G4.04)** -- the same item IPA04's DEC05/08/11 owner assignment
already used, since no separate usability-specific evidence item exists in
this project's seeded checklist (only #94/G1.03, "NFRs defined" at the
requirements stage, names "usability" as a term, and that's a different
gate). `docs/DEFECT_REGISTER.md`'s IPA04 row and this file both updated
with a pointer to the assignment. **Flagged, not silently accepted, same
discipline as 2026-09-25's own note**: usability testing is yet another
structurally distinct skill (running real sessions with real participants
against Blueprint Sec.4.4's protocol) beyond the six DEC decisions already
on kenAddme's plate, and beyond the PR-approval track record that
established kenAddme as real and active -- recording the assignment is not
the same as it having been discharged, and does not by itself demonstrate
standing to run a usability study. Status stays "Not started"; this is an
ownership assignment only, same as every prior one in this project.

**Automated WCAG pass, retried**: the browser-based route failed exactly
the same way it always has on this session -- Playwright MCP didn't
connect at session start, and `claude-in-chrome` returned "extension is not
connected" when tried again just now, not just the tab-churn WP08-era
failure. Rather than retry the identical failing path a third time,
switched approach: axe-core running against real server-rendered HTML via
`jsdom` (Node.js DOM emulation, no browser needed at all) -- a standard
technique for structural/semantic accessibility linting (the same
mechanism `jest-axe` uses). Built real data through the JSON API (register,
MFA-enrol two users, create an org, invite+accept an approver, publish the
standard template, create a project with a pending decision) against the
locally running dev server, then fetched the actual rendered HTML for
**16 distinct real, authenticated, populated `/ui` pages** -- every page
type in the app: login, register, MFA enrol, invitation-accept, orgs list,
templates list + guided editor, project creation, gate dashboard, both
roles' my-work queues, the decide page, evidence detail, history, settings,
export/import. Ran axe-core's `wcag2a`/`wcag2aa`/`wcag21a`/`wcag21aa`/
`wcag22aa` rule sets against each.

**Honest limit of this method, stated up front, not after the fact**:
jsdom has no real layout/paint engine, so `color-contrast` (and any other
rule needing actual computed geometry) reports "incomplete" on every page,
not "pass" -- this method cannot and does not claim to check contrast,
focus-ring visibility, or responsive reflow; those still need either a
real browser or a human. What it DOES reliably check, and what actually
ran: alt text, form-label association, ARIA role/attribute validity,
heading order, landmark structure, duplicate/invalid ids, link/button
accessible names, language attributes, table headers -- real WCAG A/AA
success criteria, just the subset a DOM-only tool can evaluate.

**Result: zero violations across all 16 pages.** One real "incomplete"
finding beyond the universal color-contrast one, investigated rather than
dismissed: `mfa_enroll.html`'s manual-entry setup-key `<p>` carried
`aria-label="Manual entry setup key"` on an element/role combination ARIA
doesn't reliably support naming on (`aria-prohibited-attr`, impact
"serious") -- meaning a screen-reader user might never hear that label,
degrading a security-critical enrollment step. **Fixed**: replaced the
unsupported `aria-label` with a `.visually-hidden` prefix span (new,
generic utility class added to `app/static/style.css` -- the standard
clip-based hidden-but-announced technique, not `display:none`, which
screen readers also skip), same visible text, now reliably read by
assistive tech regardless of role support. Re-scanned that page alone
after the fix: the finding is gone; re-ran all 16 pages after: 0
violations, 0 unexpected incomplete findings, confirmed clean.
`grep`-confirmed no test asserts on the old markup; targeted MFA tests
(`test_hardening.py`, `test_identity.py`, 8 tests) still pass; Ruff clean.

**What this is and is not**: a real, completed, first-ever-successful
automated accessibility pass across every current page type in this app
(the WP11-era Playwright+axe attempt never got past a connectivity
failure) -- not the full WCAG 2.2 AA audit IPA04 names, which per its own
verify text also needs a manual keyboard/screen-reader walkthrough and
zoom/reflow check (WP11's own entry already covers a partial manual pass;
this is the automated leg specifically, done for real for the first time)
and, for full "no open A/AA failure at release" sign-off, human judgment
this tool cannot supply. `docs/DEFECT_REGISTER.md` updated with this as
new evidence on the IPA04 row -- **row stays Open**: usability sessions
and independent security review remain unperformed. Dev server and
scratch capture/scan scripts (not committed; scratchpad-only) both cleaned
up at the end of this work. **No `tracker_cli.py gate` action taken.**

## REQ-047 retention enforcement: the disposal sweep, and the retention floors approved to enable it (2026-10-01)

Same session as the WP12/REQ-043 performance-budget work above (PR #9,
merged `1d2fff4`). Picked the longest-standing named gap in this file as
the next buildable item: "retention is not automatically enforced (no
scheduler exists, a gap named since WP01)", restated verbatim in
`app/models.py`'s own `SecurityLogEvent` docstring.

**Blocked first, then unblocked by a real approval, not by assumption.**
`docs/wp02/data_retention_policy.md` carried "Status: drafted 2026-09-16,
not independently reviewed", and three of its floors are explicitly
flagged in its own text as non-blueprint proposals ("None of these numbers
come from the blueprint -- they are this drafting pass's proposals only").
Building an automated job that permanently deletes rows on unreviewed
numbers would have been a gate decision through the back door, so this
was raised rather than coded around. Freston Kenny Adedeme reviewed the
floors in-session and approved them as proposed (30-day post-deletion
grace, 90-day unaccepted-invitation purge, 12-month access-event
retention). That approval is now recorded in the policy doc's own Status
block, **scoped honestly**: it covers the numbers, it is not an
independent security/privacy review of the document, and the doc's open
questions 2 and 3 stay open. **No `tracker_cli.py gate` action taken.**

**Built**: `backend/scripts/retention_sweep.py`, dry-run by default
(`--apply` required to delete), following the `scripts/anchor_worm.py` /
`restore_drill.py` precedent for manually-run maintenance (this prototype
still has no scheduler, and this pass did not invent one).

**The design decision that actually mattered, and it was measured, not
reasoned**: `invitations` and `tenant_access_events` carry FORCE ROW LEVEL
SECURITY (migration `0002_wp04_rls.py`), which applies to the table owner
too, with a fail-closed tenant policy. Verified against the live dev
database before writing the sweep: connected as `bgp_owner` with no
`app.tenant_id` set, `SELECT count(*)` on both tables returns **0** --
so the obvious implementation (one cross-tenant bulk `DELETE`) would have
deleted **nothing, silently, with no error**. The sweep therefore iterates
tenant by tenant setting `app.tenant_id`, exactly as every other
RLS-scoped query in this codebase does. **Deliberately rejected**:
granting BYPASSRLS to a maintenance role, or adding a retention-specific
RLS policy -- either would punch a hole in the precise tenant-isolation
control REQ-007/008 and the REQ-009 adversarial suite exist to defend, to
save a loop. `tests/test_req047_retention_sweep.py`'s first test pins that
fail-closed premise, so the loop can't be "optimised" away later without
the guard failing first.

**Index decision, also measured rather than assumed by symmetry** —
migration `0018_req047_retention_index.py`: `EXPLAIN` on the real database
showed the two RLS'd tables already ride their existing `tenant_id`
indexes with the timestamp as a cheap filter over one tenant's rows (Index
Scan, cost 8.31 / 8.17), so **no** index was added there; but
`security_log_events` (no RLS, no tenant predicate to narrow on) was a
`Seq Scan` at cost 126.94 and growing unbounded, so it got
`ix_security_log_events_created_at` — re-measured after: Index Scan, cost
**4.30**. An initial instinct to index all three timestamp columns was
wrong and the measurement caught it.

**Scoped out, named rather than silently skipped**: the approved `users`
30-day grace window is **not enforced**, because it is not enforceable —
this app has no account-deletion mechanism at all (no `deleted_at`, no
deletion endpoint), so no deletion event exists for a grace window to run
from; building that feature was not in this pass's scope. `memberships`
removal is already `active=false` (which IS the policy's stated
mechanism). `mfa_recovery_codes` is retain-don't-purge by policy, so no
action is the correct action. Published template versions, decisions,
audit events and checkpoints stay indefinite by design.
`security_log_events` is swept on the same 12-month floor even though the
policy's table never names it — an **inference** from that model's own
docstring pointing at the policy, flagged in both the script docstring and
the policy doc for confirmation at next review, not folded into the
approval as if covered.

**Verified**: 7 new tests pass (floor boundaries both directions, accepted
invitations retained regardless of age, dry-run deletes nothing,
idempotent re-run, and a cross-tenant test proving sweeping tenant A
leaves tenant B's equally-eligible rows alone). Full suite re-run. Ruff
clean and formatted. The script was run for real in **dry-run** against
the live dev database -- 1114 tenants in 8.7s, reporting 10 eligible
invitations and 7 eligible access events. **`--apply` was deliberately
not run**: that would delete 17 real rows from the shared dev database,
which this pass was not asked to do, so the apply path's evidence is its
tests against purpose-made fixture rows, not a live disposal. Stated
plainly rather than implied as fully exercised.

**Also still missing, from the policy's own list**: a legal-hold flag
(nothing currently blocks a disposal that a hold should block) and a
durable per-row disposal audit record (the sweep reports counts to its
output only). Both recorded in the policy doc as remaining gaps.

1. Draft candidate evidence matches, then **verify each one against the actual
   file/commit/PR before writing a status**, never on a paraphrase.
2. Complete requires a specific, locatable, checked evidence reference.
   Partial or unverifiable stays "In progress" with an honest note.
3. **Never record a gate `decision` from code or documents alone.** A gate
   decision is the named authority's action (Sponsor/Project Authority per the
   PM Framework; delivery lead/independent reviewer sign-off per SDLC), taken
   manually via `tracker_cli.py gate` — naming DEC01's roles is not a gate
   decision and doesn't substitute for one.

## DEC07 Q10: the resolved rule vocabulary, versioned so old templates never shift (2026-10-02)

Next buildable item after REQ-047 (PR #10, merged `f802604`): DEC07 Q10's
answer had been recorded since 2026-09-27 but never implemented, and
`rule_engine.py`'s own module docstring still read "DEC07 ... is still
open". Merged as PR #11 (`d75a963`), commit `c419365` — `rule_engine.py`,
`routers/templates.py`, `routers/projects.py`, `webapp/router.py`, and a
new `tests/test_dec07_rule_vocabulary.py` (+682/-18 over 5 files).

**Implemented exactly the answered list, and nothing past it.** Sec.5.5's
`eq`/`in`/`all`/`any` stand; added `not`, `gte`/`lte` and `count(...)`
with a comparison; applied both tightenings (a 200-node cap alongside the
existing depth-5 limit, and a hard evaluation timeout). DEC07 closes with
"Resist adding anything beyond this", so `count`'s comparison reuses
`eq`/`gte`/`lte` rather than introducing a fourth comparison form.

**The part needing a mechanism rather than an operator was
`vocabulary_version`.** Templates are immutable once published (REQ-011),
so every already-published version's `schema_json` simply lacks the key
and validates as vocabulary 1 — the exact operator set it was authored
against. That is what makes DEC07's "old templates evaluate identically
forever" true with **no migration and no backfill**. Validation gates it
both directions: a vocabulary-1 template naming `not` is rejected, and an
unknown version is rejected rather than assumed forward-compatible.
Stamped on the blank guided-authoring starter only — deliberately **not**
on import, `update_draft` or fork/copy, since those carry an
externally-authored or inherited schema and re-stamping would let an
export/import hop silently re-pin a template's semantics.

**Two interpretations flagged rather than buried.** "Cap total condition
nodes at 200" is read as applicability + conditions summed per rule (the
stricter reading, since bounding evaluation cost is the stated purpose).
And `as_at` is passed as an ISO-8601 **string**, not a `datetime`:
template JSON has no date type, so a rule's threshold is always text, and
a `datetime` compared against a string threshold would raise `TypeError`
and fail closed every time — making date rules silently useless. The
boundary that follows is stated in `_compare`'s docstring rather than left
to be discovered: a full timestamp sorts after the bare date it falls on,
so `lte` against a bare date excludes that day.

**Purity kept, per DEC07's own requirement.** `as_at` is applied *over*
the facts dict, not under it, so tenant-influenced project state cannot
shadow the evaluation timestamp. The rule itself reads no clock;
`time.monotonic` is the timeout's own bookkeeping and cannot change any
rule's result. The timeout is a deadline checked at each node — not
`signal.alarm` (Unix-only) or a worker thread — because this runs inside
a request on Windows dev and Linux CI alike, and it **raises** rather than
returning `False`: a rule that cannot be evaluated in budget is an
operational anomaly, not a readiness answer, and the one production caller
already rolls its transaction back on exception.

**How vocabulary gating is actually enforced**: a new
`Condition.operators_used()` walks the whole tree (nested conditions
included, so a v2 operator cannot hide inside a `count`'s children) and
`Rule.operators_used()` unions applicability and conditions. `compare` is
deliberately excluded from that set — its values are words of `count`'s
own shape and `count` itself is already gated, so counting them
separately would reject `count` at every version. Documented in the
method's docstring rather than left implicit.

**Scoped out, named rather than silently skipped**: the guided form
builder still only *creates* `eq`/`in` — offering the rest is the separate
UI pass DEC07 anticipates. But `webapp`'s `_describe_condition` now
renders the new operators in plain language, because a valid rule arriving
via Advanced JSON or import previously read back as "Unrecognised
condition shape", which is misleading rather than merely unhelpful.
**DEC07 Q11/Q12's third framework fixture is not in here** and remains
unbuilt.

**Verified**: 38 tests collected and passing in the new file; full suite
**249 passed, 0 failed, 0 skipped** (900s). Zero skips matters — it means
the 32 live-Postgres RLS/concurrency tests actually ran rather than
self-skipping. The two earlier attempts at that run were OOM-killed on
this machine, so the work was held uncommitted until a complete run
existed rather than committed on a partial result. Ruff check and format
clean across 90 files. CI `backend` check SUCCESS on PR #11.

**Review state, recorded because this file has had to record the opposite
before**: PR #11 carries an actual `APPROVED` review from kenAddme
(`gh pr view 11 --json reviews`), not the `COMMENTED`-only admin-merge
pattern EC-202 documents and that previously forced three tracker items
back down to "In progress". This is a genuine human approval of this
change, and nothing more than that — not an SDLC gate decision. **No
`tracker_cli.py gate` action taken.**

## DEC07 Q11/Q12: the third framework fixture, and the gap it found (2026-10-03)

Next item after Q10 (PR #11, `c419365`). Q11 asked for a third framework
fixture *structurally different* from the two gate-based ones already
built — "an agile Definition-of-Ready / Definition-of-Done framework with
no gates at all", recurring per-increment checks, unnumbered — on the
stated reasoning that "if the rule engine and data model survive that
without a special case, the model is genuinely general." Q12 asked for
full parity on the model: tracks, items, rules, roles, statuses,
decisions.

**Run as a spike before a build, deliberately.** Writing the fixture first
would have meant guessing whether it fit. The probe (throwaway, deleted)
imported a candidate through the real API — import, publish, project
creation, evidence seeding, a second increment, readiness, a decision — and
the answer changed the shape of the work.

**What survived, and it is more than expected.** Recurrence needs no new
model concept: each sprint is occurrence 2, 3, ... of the same check set,
and `create_occurrence` already allocates it with its own evidence, which
`GateOccurrence`'s own docstring had anticipated ("the second routine
review of the same gate is sequence 2"). Unnumbered ids work because
`gate_id`/`rule_id` are free strings. The fixture also became the first
real consumer of Q10's vocabulary (`not`, `count(...)`, at
`vocabulary_version: 2`), so it now doubles as a regression canary for
that work.

**What did not survive — a template's declared vocabulary is not
honoured.** Five sub-findings, verified by probe and then by reading the
code, now recorded as the `DEC07-Q11 vocabulary indirection` row in
`docs/DEFECT_REGISTER.md`: `TemplateSchema.statuses` is read by no
readiness path (readiness matches the literal `"Complete"`); the authoring
UI nonetheless *offers* the declared list, so a user picks "Met", gets a
201, and readiness still says "has not been marked Complete"; an
undeclared status is accepted outright; REQ-018's "no Complete without a
reference" control is keyed to the same literal, so a required item can
carry an unreferenced done-meaning status; and `_outcome_eligibility`
matches the Blueprint's five English outcome words, so declared outcomes
422 with `permitted_outcomes: []`.

**And a sixth, wider than the other five, found while tracing the
fixture's own rules.** `evaluate_condition` has exactly one call site in
the whole application (`routers/projects.py:189`, on
`rule.applicability`). A rule's `conditions` tree — the part saying what
must actually be true — is validated for depth, the 200-node cap and the
operator vocabulary, then never walked by any readiness path, and
`required_fields` has no consumers beyond its one declaring line. So
readiness is decided entirely by the human-set `status` string, and all of
Q10's machinery currently governs a tree nothing evaluates for readiness.
Proven by probe rather than grep alone: the fixture's
`definition-of-done.checks-pass` condition is satisfiable (True when fed
`automated_checks_passing`) but False under the only facts any call site
supplies (`{class_id}`) — and the blocker clears anyway, on status alone.
The satisfiable-when-fed half is deliberate: it rules out the reading that
the condition is merely malformed.

That sixth finding changes the honest headline. This is not just "the
status and outcome words are hardcoded" — it is that a substantial part of
the approved declarative rule schema (`conditions`, `required_fields`, and
`statuses`) is inert: validated rigorously, then never consulted. It has
the largest bearing of the six on REQ-013's "configurable rules" claim and
should be read before the fix is scoped.

Severity stated split rather than rounded: every readiness path fails
**closed**, so no unready decision is approved — none of this is a gate
bypass. The REQ-018 sub-finding is the sharpest individual edge, because
the evidence record itself ends up in exactly the unreferenced-"done"
state that control exists to forbid.

**One lead recorded as a lead, not a finding.** `permitted_role_ids`
appears to be consulted only for my-work routing
(`routers/projects.py:527`), not enforced when a revision is submitted
(`create_evidence_revision` checks project membership only). If that is
right, any project member can satisfy an item the framework restricts to a
named role. Read from code and never probed, so it is written down as a
lead for its own piece of work rather than asserted here — claiming a
control gap on code reading alone is the thing this file's own history
says not to do.

**Why the fixture shipped before the fix.** The alternative — fix the
vocabulary indirection first — would have meant designing against a
description of the gap instead of a reproducible demonstration of it. So
this commit is the fixture plus the finding; generalising the
status/outcome vocabularies is its own piece of work, carrying the same
backward-compatibility obligation `vocabulary_version` established in Q10,
and needs its own design rather than being improvised here.

**The characterization tests are labelled as such, loudly.** Five
`test_gap_*` tests pin the current *wrong* behaviour so the fix lands as a
deliberate, visible change to one file rather than a silent diff. The
module docstring and every one of those docstrings says plainly that they
are not a spec to preserve and are expected to be rewritten. A test
asserting a defect is dangerous precisely when nobody can tell that is
what it is.

**Two model concessions, recorded rather than smoothed over.** `gates`
cannot be empty (`min_length=1`), so the three recurring check sets are
expressed *as* gates — "no gates at all" holds in the framework's language
but not in the model's. And `GateDefinition.sequence` is required, so
1/2/3 are supplied for checks that are not an ordered run (ready and done
recur per story, increment-review per increment). Both are in the
fixture's own `_meta`, not just here.

**Q12 is NOT satisfied, and is recorded that way.** The fixture reaches
parity on tracks, items, rules and roles — not on statuses or decisions,
which Q12's "full parity on the model" names explicitly. Q12 stays open
until the vocabulary work lands; it must not be logged as
answered-and-built on the strength of this commit.

**Q12's "not a shipped starter" is enforced in code, not just asserted.**
`scripts/seed_starter_frameworks.py` seeds every `*.json` in the fixtures
directory as a shared `tenant_id=NULL` platform starter, so dropping the
file in would have published the agile fixture to every tenant — the exact
thing Q12 forbids until its own review passes. The script now skips any
fixture flagged `_meta.validation_fixture`, after validating it (so a
validation fixture still fails loudly on a schema regression), and
`test_framework_fixtures.py` asserts the flag the script keys on is
present so the two cannot drift.

**One latent test trap fixed in passing.** `test_framework_fixtures.py`
asserted `len(set(gate_counts)) == 3`. A fourth fixture with 2 gates would
have given `{2, 2, 4, 6}` → a set of size 3 → **passing while colliding**,
for entirely the wrong reason. The distinctness assertions are now tied to
`len(FIXTURE_FILES)`, so a collision fails instead of hiding. The agile
fixture has three check sets independently of this (story-level ready,
story-level done, increment-level review are genuinely different
cadences), not three to satisfy an assertion.

**Verified**: 13 new tests in `test_dec07_q11_agile_fixture.py`, 21
passing across it and `test_framework_fixtures.py`; Ruff check and format
clean. All 13 were watched failing before the fixture existed, so they are
known to test the fixture rather than pass vacuously. The seed script's
guard was verified by a read-only replay of its per-fixture decision
branch — **the script itself was not executed against a database this
session**, which is stated here rather than implied.

**Full suite: every test passes, by chunked execution.** All **264
collected tests ran and passed, 0 failed**, across 8 sequential chunks of
5 test files covering all 37 test files in the suite (63/42/43/28/45/20/16/7).
Chunking was not a convenience: this machine cannot complete a
single-process full run (see below), and chunks stay inside its memory.
The perf-budget file sits in chunk 2 and passed there with the rest.

**The one run that did complete in a single process is recorded too,
because the honest version is messier than "green".** It finished **260
passed, 2 failed** (603s), both failures in
`test_dec08_performance_budgets.py` — taken before the two sixth-finding
tests existed, which is the whole of the 262-vs-264 difference. Those same
budget tests pass **3/3 in isolation** (24s), **9/9 immediately after the
heaviest neighbour** `test_dec05_durability_mechanism.py` (52s), and again
in chunk 2 above. The failures never reproduced in any targeted form.

The two failures' assertion text was **never captured**, and that is a gap
in this evidence rather than something to paper over: the first run's
output was piped through `tail`, which discarded the detail, and **two
subsequent attempts to re-run with the detail captured were both
OOM-killed by the operating system** — the second after only two tests.
Retrying stopped there rather than continuing to hammer the same failing
action.

What makes the contention reading evidenced rather than assumed: this
machine has **3.46 GB of total RAM with 0.41 GB free (88% used)**,
measured this session. On that machine, running the full suite (32
live-Postgres tests, plus Postgres itself, plus an editor and two agent
processes) means assertions of the form `p95 <= 300 ms` are measuring
memory pressure, not request handling. The run that died after two tests
is the clearest evidence the pressure is ambient rather than accumulated
by the suite — it never reached most of the new tests. Same conclusion the
2026-09-30 entry reached about the same file.

Two things deliberately **not** claimed. First, that the 2 failures are
diagnosed: they are *un-diagnosed*, with a well-evidenced mechanism.
Second, that the 12 added tests contributed nothing — they do add load
ahead of latency-sensitive tests, and that cannot be ruled out from here.

**Correcting something stated earlier in this session's own working
notes**: CI does *not* isolate the budget tests. `.github/workflows/ci.yml`
runs the full suite at line 66 and the budget file again at line 75, and
that second step's own comment says it is for *visibility by step name*
("already part of the full suite above (so a breach already fails the
build)"). So a genuine budget breach fails CI, and a CI red on those two
tests must be treated as real rather than waved through as local
contention.

**No gate decision.** Evidence items and this narrative only — no
`tracker_cli.py gate` action taken, and the DEC07-Q11 register row is a
finding, not an approval.

## DEC07 vocabulary indirection fixed: a template's own words now govern readiness; Q12 closed (2026-10-04)

The `DEC07-Q11 vocabulary indirection` finding logged the day before
(2026-10-03, `docs/DEFECT_REGISTER.md`) is now fixed, originally across
thirteen commits on `SageCarter98/dec07-vocabulary-indirection-impl`
against the spec and plan at
`docs/superpowers/specs/2026-10-03-dec07-vocabulary-indirection-design.md`
and `docs/superpowers/plans/2026-10-03-dec07-vocabulary-indirection.md`:
`ee9472b`, `3b8e710`, `cd83fdb`, `28747f3`, `faede1a`, `a834f64`,
`802abc4`, `c7852aa`, `55831e3`, `9546229`, `c2ca1a7`, `02649e0`, and
`6a0aaf7` (the commit carrying this entry, added in a small follow-up
commit once its own SHA existed).

**Correction, 2026-10-04 (closing pass): "thirteen commits" is stale --
it counted only the original implementation and stopped at the paragraph's
own writing.** A whole-branch review after this entry was written raised
2 blocking and 8 important findings; closing them took four more commits
(`8f6c065` fixing a stale BGP-F03-follow-up fixture the sweep below found,
`c9cc5fc` recording that fix's own SHA, `7123fa7` withdrawing this
section's earlier wrong root-cause claim for that same red, and `5ed8f3b`
closing the review's remaining C1/I1-I8 findings), plus this entry's own
documentation commit. `git log --oneline 8e9ebfa..HEAD` run after that
commit landed counts **eighteen** commits total, not thirteen -- the
number belongs to the whole branch's history, not to one task's slice of
it, and restating a stale count here would be exactly the kind of
rounding this register exists to catch.

**What changed, in one sentence.** `statuses` and `decision_outcomes` now
accept structured entries that carry their own meaning — `satisfies`,
`requires_exception`, `initial` on a status; `kind` (`approving` /
`conditional_approving` / `recording`) on an outcome — and every readiness
and eligibility path asks the bound template what a word means instead of
comparing it to a hardcoded English literal.

**Five of the six sub-findings are closed, and one half of the sixth.**
(Corrected 2026-10-04, closing pass: this previously read "Six of the six
sub-findings are closed; the seventh thing the row named is not" — the
register names exactly **six** sub-findings, not seven, and
`required_fields` is explicitly *inside* sub-finding (6), not a separate
item; the very next paragraph here already said so, so the headline
contradicted its own section. Fixed to match what the register and the
rest of this entry actually say.) Sub-findings (1)-(5) — statuses unread
by readiness, the authoring UI offering a list that did nothing, undeclared
statuses stored without complaint, REQ-018 keyed to the literal, declared
outcomes unrecordable — are all closed. Sub-finding (6) had two halves:
`rule.conditions` never being evaluated, which is now closed, and
`required_fields` having no consumers, which is **still open**. Spec §1
decision 4 put `required_fields` out of scope deliberately, and nothing in
this plan gave it a consumer: `grep -rn required_fields backend/app/`
still returns exactly one line, `app/rule_engine.py:218`, the field
declaration itself. The register row's Status cell says so, and the
characterization test for it was deliberately **kept as a gap test**
(`test_required_fields_remains_declared_but_inert`) rather than rewritten
as a positive one. The plan's own Step 7 commit message had claimed all
seven characterization tests "became positive counterparts"; that was
corrected to six before the commit was made, because a governance record
does not get to round up.

**DEC07 Q12 is closed, and this is its evidence.**
`fixtures/synthetic/frameworks/agile.v3.json` is a new validation fixture
declaring `"vocabulary_version": 3`, its own statuses (`Not met` initial,
`Met` satisfying, `Waived` satisfying-but-`requires_exception`) and its own
three outcomes. `test_declared_decision_outcomes_can_now_be_recorded`
drives it through preview and a committed decision on the outcome
"Increment accepted" — the assertion Q12's "full parity on the model
including statuses and decisions" was waiting for.

**`agile.json` was NOT edited, and that is the point.** It is published and
immutable under REQ-011, and it is the artefact that demonstrated the gap;
editing or deleting it would delete the evidence.
`test_the_v1_fixture_is_retained_and_still_fails_closed` asserts it still
behaves exactly as the finding described — "Met" stores happily and still
blocks — which is also G6's proof at the fixture level.

**The v3 fixture is not a verbatim copy, and the reason is worth
recording.** Its `gate_id`s, `rule_id`s, `required_fields` lists and every
guidance string are byte-identical to `agile.json` (checked
programmatically: the two files are identical once the vocabulary block and
`conditions` are removed). But its condition trees had to be retranslated.
Condition evaluation at vocabulary 3 reads a deliberately **closed** fact
namespace — only `item:<rule_id>`, values `"satisfied"`/`"unsatisfied"`,
scoped to one occurrence — and unknown facts fail closed. `agile.json`'s
trees reference project-state facts (`has_acceptance_criteria`,
`automated_checks_passing`, `peer_reviewed`, `increment_demonstrated`) that
nothing supplies, so copying them into a v3 file would have made four of
its nine rules **permanently unclearable by any status**. One tree was
retranslated faithfully — `definition-of-ready.acceptance-criteria` now
requires at least two of its sibling DoR checks satisfied — and the other
four are set to `null`, an honestly inert condition in preference to one
that is unsatisfiable by construction. Recorded in the fixture's own
`_meta.conditions_note`; a project-state fact pipeline is its own work
package.

**The REQ-018 interpretation ruling that licensed this.** Spec §1 decision
7 records an owner ruling, in session on 2026-10-03: *"Complete is a state
concept not a literal."* That is the recorded interpretation decision the
spec's §8 required before implementation, and it is what licenses G3 —
REQ-018's "do not allow a required item to be Complete without a
reference" now keys on `satisfies`, so a framework whose completion word is
"Met" is caught by it exactly as one saying "Complete" is. The literal
string keeps its meaning for vocabulary 1 and 2 templates only, through
normalisation, which is a compatibility mechanism and not a statement
about the requirement.

**Back-compat was the constraint the design was built around, and it is
tested, not asserted.** `VOCABULARY_VERSION` — the stamp every new
guided-authoring draft gets — stays deliberately at **2**, per spec §7
rollout step 1: vocabulary 3 ships accepted but not default, because the
guided authoring form can only emit comma-separated strings and would
produce invalid v3. A template reaches v3 only by declaring it in its own
JSON, which `agile.v3.json` is currently the only artefact to do, and it is
a validation fixture that `seed_starter_frameworks.py` never seeds to a
tenant. `backend/tests/test_dec07_vocabulary_backcompat.py` (10 tests,
written before any production change and green through every task) pins
the v1/v2 side: `Not started` seeding, the literal `Complete` clearing a
blocker, `Approve` staying permitted, and an inline vocabulary-2 template
whose populated `conditions` are **false** still satisfying on status
alone.

**TST-010's own verification gap is closed too, and it is the root cause.**
TST-010 asked for fixtures with distinct "classes, roles and gates".
REQ-010 also requires templates to version their *status* and *decision*
schemes, and nothing ever asserted the fixtures differed in those — so
three fixtures that all declared `"Complete"` and the Blueprint's outcome
words satisfied the verification for six work packages while leaving this
defect invisible. `test_fixtures_differ_in_status_and_outcome_schemes_too`
in `backend/tests/test_framework_fixtures.py` now asserts the omitted half.
It is not decorative: with `agile.v3.json` excluded, the set of satisfying
status words across every other fixture is exactly `{"Complete"}` and the
assertion fails (checked by running it both ways).

One honest consequence of adding the fixture, recorded rather than
smoothed: `test_fixtures_have_distinct_classes_roles_and_gate_counts` now
counts `DISTINCT_FRAMEWORK_FILES`, which excludes `agile.v3`. That is by
construction, not a weakening — the v3 fixture is required to keep every
`gate_id` and `rule_id` identical to `agile.json`, so it *cannot* add a
distinct class set, role set or gate count, and counting it would have
forced a structural difference the fixture is specifically forbidden to
have. The collision-detecting form of that assertion (tied to a file count,
not a hardcoded 3) is unchanged for the four real frameworks.

**A new High finding, logged not fixed.** Generalising outcomes by declared
`kind` (`55831e3`) left REQ-006's separation-of-duties gate keyed to the
Blueprint's literal words: `_record_decision` runs
`_check_separation_of_duties` only inside `if payload.outcome in
("Approve", "Approve with conditions")`, immediately below an
`_outcome_eligibility` call that now resolves the outcome by `kind`. So a
template-declared `approving` outcome reaches a committed approval without
the self-only-approval check. This is confirmed by a paired pin rather than
by reading the code. In `backend/tests/test_decisions.py`,
`test_full_approval_flow_with_separation_of_duties_override` shows the
identical self-only-approval state under `"Approve"` refused **403**; in
`backend/tests/test_dec07_q11_agile_fixture.py`,
`test_declared_decision_outcomes_can_now_be_recorded` shows it under
`"Increment accepted"` committing **201** —
that test now also asserts the precondition explicitly (every hard item's
latest revision authored by the deciding actor), so it cannot pass
vacuously and it goes red when the gap is fixed. Logged as its own open row
("DEC07 SoD outcome literal", High, Open) in `docs/DEFECT_REGISTER.md`. It
was found while writing Task 8's decision test; no task of this plan
covered it, and Task 8 had no mandate to change `decisions.py` and did not.

**Verified.** `test_dec07_q11_agile_fixture.py` 16 tests,
`test_framework_fixtures.py` 10, `test_dec07_vocabulary_backcompat.py` 10 —
36 passing together. Ruff `check` and `format` both clean across 98 files.
Non-vacuity was probed, not assumed: with the fixture's own
`vocabulary_version` temporarily flipped 3 → 2,
`test_rule_conditions_are_now_evaluated_for_readiness` fails at exactly its
second-half assertion (the summary item must block again once a sibling
regresses, *despite its own satisfying status*) — which is the half that
distinguishes real condition evaluation from a test that would pass either
way.

**Full suite: 320 collected; this task's own chunked runs reported 319/320,
but that number is corrected below by an independent sweep that found a
second failure and a wrong root-cause claim for the first.** Nine sequential
chunks of 5 test files covered all 44 test files; the chunk totals sum to
320, matching `pytest --collect-only -q` exactly, so no chunk silently
skipped files. Chunking is not a convenience — this machine has 3.46 GB RAM
and cannot complete a single-process run (two earlier attempts were
OOM-killed). Both perf-budget files (`test_dec08_performance_budgets.py` in
chunk 3, `test_wp12_render_and_export_budgets.py` in chunk 8) passed in
*this task's own* chunking of that run.

**The controller ran its own independent chunked sweep of `c9cc5fc` and
measured 318 passed, 2 failed — the collected count (320) matches exactly,
the pass count does not, and both reds needed correcting.**

One red is environmental, not a defect:
`test_dec08_performance_budgets.py::test_read_budget_gate_dashboard_and_my_work`
failed while sharing a pytest process (123.87s) and passed 3/3 run alone
(14.44s) — the same memory-contention pattern recorded elsewhere in this
file for this machine, not a budget regression.

The other red, in
`backend/tests/test_bgp_f03_followup_app_level_concurrency.py`,
`test_real_endpoint_returns_clean_409_not_500_when_it_loses_the_race`, **was
caused by Task 3 of this same plan — the paragraph previously here, calling
it pre-existing and reproducing it at pristine `02649e0`, was wrong and is
withdrawn.** `02649e0` is this branch's own Task 7 commit, not a pristine
baseline: reproducing the failure there shows only that it predates Task 8,
not that it predates the work. A bisect in a throwaway worktree found the
test passing at the merge-base `8e9ebfa`, passing at Task 1 (`3b8e710`) and
Task 2 (`faede1a`), and failing from Task 3 (`802abc4`) onward through
`c7852aa` and `c2ca1a7` (Tasks 4 and 6).

The cause is in the fixture, which seeds a template declaring
`"statuses": ["Not started"]` and then seeds the evidence row directly as
`'Complete'` — a status that template never declares. Before `a834f64`
readiness compared the literal and cleared it; Task 3 made readiness ask the
template instead, so an undeclared status now fails closed — this is
**intended behaviour, Ruling 11** (readiness must not honour a status its
template never declared; see the spec's section 7 step 3), not a bug to
revert. The defect was that the fixture itself had gone stale: it declared
`["Not started"]` only, while directly seeding `'Complete'`, so the item was
a hard blocker and the test's
`assert preview.json()["hard_blockers"] == []` failed before the race it
exists to test was ever exercised.

**Why seven task reviews missed it: this file is in no task's regression
set.** It needs live Postgres and is skipped entirely without it, and
nothing in the plan's eight tasks named it as a file to re-check — it took
a full chunked sweep outside any single task's scope to surface it. That is
the process gap worth recording, not a review that looked at this file and
missed the defect.

**Fixed in `8f6c065`**: `minimal_schema` now declares `"Complete"` alongside
`"Not started"` (plain string; `vocabulary_version` defaults to 1, which
`TemplateSchema.status_lookup()` auto-resolves via
`rule_engine._LEGACY_SATISFYING_STATUS` to `satisfies=True`, matching what
the fixture always needed to assert). The `hard_blockers == []` precondition
assertion was kept, not weakened or removed — it is load-bearing, since
without it a readiness change could silently make the race untestable. A
sibling search covered every other test that seeds or posts a status
against a schema that might not declare it (raw-SQL seeding into
`evidence_items` across the whole suite is limited to this file,
`test_bgp_f03_decision_concurrency.py`, and `test_wp07_tenant_isolation_rls.py`
— the other two either never route the seeded row through readiness or
already use a status their own schema declares) plus every fixture JSON
under `fixtures/synthetic/frameworks/` and every inline `"statuses"` schema
literal in the test suite; the only other schema declaring `["Not started"]`
only is `test_bgp_f03_decision_concurrency.py`'s, which drives its
`'Complete'` writes through raw `UPDATE` statements proving lock behaviour
and never through `_compute_readiness`, so it was never exposed to this
gap. `test_bgp_f03_followup_app_level_concurrency.py` (1 test) and
`test_bgp_f03_decision_concurrency.py` (5 tests) both re-run green after the
fix.

**No gate decision.** Evidence documents, fixtures and tests only — no
`tracker_cli.py` invocation of any kind and no `tracker_cli.py gate`
action. The register rows above are findings and closures of findings, not
approvals; a gate decision remains a named human authority's sign-off.

## Whole-branch review closing pass: C1/I1-I8 and the M-item log (2026-10-04)

A full whole-branch review of this branch (after the entry above) raised 2
blocking and 8 important findings against the vocabulary-indirection work.
A fix wave addressed most of them in an earlier, uncommitted session that a
usage limit cut off before it tested, documented or committed anything.
This entry finishes that wave: verifies what was already fixed, finishes
what was missing, tests, and commits (`5ed8f3b`, plus this documentation
commit). Per-finding disposition:

- **C1 (REQ-006 separation-of-duties bypass) — fixed, verified, and its
  register row closed.** Already correct in the uncommitted work;
  confirmed by reading the diff. Full detail, including the corrected
  reachability claim, is in `docs/DEFECT_REGISTER.md`'s "DEC07 SoD outcome
  literal" row (now Closed, 2026-10-04).
- **I1 (30-char cap bypassable at default vocabulary) — fixed, verified.**
  Already correct and broader than the original finding asked (covers
  statuses AND decision outcomes, gated on a structured entry OR
  `vocabulary_version >= 3`). Confirmed by reading `rule_engine.py:480-515`.
- **I2 (vacuous guard test) — fixed, verified.**
  `test_an_unknown_future_vocabulary_version_is_rejected` now uses
  `max(OPERATORS_BY_VOCABULARY_VERSION) + 1` and asserts the specific
  rejection message, so it actually exercises the unknown-version path
  rather than vocabulary 3's content rules.
- **I3 (`my_work._satisfies` fail-open) — fixed, verified.** Uses the
  shared `status_satisfies` predicate plus condition evaluation via
  `_conditions_hold`/`_evidence_facts`, and a new `_pending_exception`
  helper gives the action text an honest third state (satisfies, but only
  once an exception is approved) instead of collapsing it into "no action
  needed".
- **I4(b) (undeclared-status 422 containment) — fixed, verified.** Gated
  at `projects.py:716` behind `schema.vocabulary_version >= 3`, restoring
  spec §7's explicit containment rather than recording the deviation as an
  accepted exception.
- **I4(c) (agile.json's seeded status silently changed) — now recorded
  and pinned, not just noted.** `routers/projects.py` seeding every item
  from `TemplateSchema.initial_status()` means `agile.json` (vocabulary 2,
  no `"Not started"` declared) now seeds `'Not met'` instead of the old
  literal. Recorded as an accepted G6 consequence in
  `docs/DEFECT_REGISTER.md`'s DEC07-Q11 open-items list, and pinned by
  `test_dec07_q11_agile_fixture.py::test_the_v1_fixture_seeds_its_own_first_declared_status`.
- **I5 (stale "fallback is defensive" comment) — fixed, verified.**
  `rule_engine.py`'s `initial_status()` now says the fallback is live and
  names `agile.json` as the case that exercises it.
- **I6 (TRACKER.md rounds 5½/6 up to 6/6, invents a seventh item, and
  undercounts the commits) — fixed in this entry.** Headline corrected to
  "Five of the six sub-findings are closed, and one half of the sixth."
  The "thirteen commits" claim corrected with a dated note explaining why
  it was stale and what the real total is (eighteen, `git log --oneline
  8e9ebfa..HEAD` after this commit).
- **I7 (measurable falsehood: 30-char cap claimed to force "Waived")  —
  fixed, verified.** Both `agile.v3.json`'s `_meta.status_id_note` and the
  matching test comment now say the real reason (a shorter id, available
  because it's a new version) and state plainly that the v1 string (25
  chars) was already compliant.
- **I8 (webapp cannot record a v3 `conditional_approving` outcome) —
  fixed; test coverage was missing and has been added.** The production
  fix (both `webapp/router.py`'s `_conditional_outcome_ids` and
  `decide.html`'s fieldset resolving through `outcome_lookup()`'s declared
  `kind`) was already correct in the uncommitted work. No test exercised
  it end-to-end, so one was added:
  `test_dec07_webapp_statuses.py::test_decide_page_offers_conditions_for_a_declared_conditional_outcome`
  drives a real v3 `conditional_approving` outcome ("Accept with
  follow-ups") through the actual `/ui` decide GET (asserts the fieldset
  renders) and POST (asserts the decision commits, not "missing deadline
  or condition owner") against the plain SQLite test client — the RLS-only
  code this project's webapp tests otherwise gate on Postgres for is a
  no-op there (`db.get_bind().dialect.name == "postgresql"` guards every
  `SET LOCAL`), so this did not need a live-Postgres fixture.
- **M2/M3 (committed review scaffolding in test comments) — fixed.**
  Stripped "REVIEW FOCUS n", "Amendment 2" and "fix round x/5" references
  from `test_dec07_rule_vocabulary.py`, `test_dec07_status_semantics.py`,
  `test_dec07_conditions_evaluation.py`, `test_dec07_revision_validation.py`,
  and `test_dec07_readiness_semantics.py`. The last of those also had a
  comment (on `V2_TEMPLATE`) and a docstring (on
  `test_an_expired_exception_does_not_satisfy_on_the_locked_commit_path`)
  describing `_outcome_eligibility` as not yet object-aware and the real
  fix as landing in a "NEXT task" — Task 5 (`55831e3`) had already landed
  that fix by the time this branch reached its current HEAD, so both were
  corrected to state the real, current reason this one test keeps a
  vocabulary-2 fixture (nobody rewrote it once the fix landed, and there
  is no need to).
- **M4 (stale "one production caller" claim) — fixed, verified.**
  `RuleEvaluationTimeout`'s docstring now names both production callers
  (`routers/projects.py` and `_conditions_hold` in `routers/decisions.py`,
  reached from readiness) and states plainly that the exception is caught
  nowhere — fail-closed, not a handled error path.
- **M1, M5-M9, M11, the `blocker_explanations` two-cause wording gap, and
  the pre-existing `applicability` latent gap — logged, not fixed, per
  the review's own instruction.** Recorded as a new bullet list in
  `docs/DEFECT_REGISTER.md` directly under the DEC07-Q11 open-items
  section. None of these block what this branch set out to do; none is
  claimed fixed.

**A real regression found and fixed while finishing this wave, not
pre-existing and not part of the original findings list:**
`test_dec07_outcome_semantics.py::test_an_approving_outcome_can_actually_be_recorded`
started failing once C1's fix was applied — correctly. Its single-admin
project made the deciding admin the evidence's sole preparer, so C1's now-
working self-only-approval check denied the decision 403 where the test
expected 201. Rewritten with a second project member (an `approver` who
never touched the evidence) as the decider, which is the ordinary,
non-self-only approval path this test was always meant to exercise — the
self-only-denial case has its own dedicated pin,
`test_dec07_q11_agile_fixture.py::test_a_declared_approving_outcome_is_refused_for_a_self_only_approver`.

**Verified.** Every DEC07/webapp/project/template/fixture test file this
branch touches was run, two files per pytest process (this machine's
3.46GB RAM OOMs a single full-suite process): `test_dec07_webapp_statuses.py`
(4), `test_decisions.py` + `test_dec07_outcome_semantics.py` (21, after the
regression above was fixed), `test_dec07_q11_agile_fixture.py` +
`test_dec07_rule_vocabulary.py` (56), `test_dec07_status_semantics.py` +
`test_dec07_vocabulary_backcompat.py` (24), `test_dec07_readiness_semantics.py`
+ `test_dec07_conditions_evaluation.py` (11), `test_dec07_revision_validation.py`
+ `test_dec07_webapp_statuses.py` (12), `test_projects.py` +
`test_framework_fixtures.py` (20), `test_templates.py` +
`test_ui08_template_authoring.py` (20), `test_wp13_webapp_new_pages.py` (6,
against real Postgres — available and used this session, not skipped).
All green. `ruff check` and `ruff format --check` both clean across the
full `app`/`tests` tree.

**No gate decision.** Evidence documents, fixtures and tests only — no
`tracker_cli.py` invocation of any kind and no `tracker_cli.py gate`
action. The register rows above (and in `docs/DEFECT_REGISTER.md`) are
findings and closures of findings, not approvals; a gate decision remains
a named human authority's sign-off.

## Declared role vocabulary honoured: REQ-010's role scheme, the last field of its own list (2026-10-07)

The sibling of DEC07's status/outcome work, in the one remaining field of
REQ-010's list. A template could declare its own `roles` and
`permitted_role_ids` had to reference them — but **project membership roles
came from a fixed platform enum** (`models.Role`), so for any framework that
brought its own role names (`agile.json`, `agile.v3.json`: product_owner,
developer, facilitator) `permitted_role_ids` could never match any member's
role. `docs/DEFECT_REGISTER.md`'s "Declared role vocabulary is not honoured"
row is now **Closed**; the design spec is `1391069`
(`docs/superpowers/specs/2026-10-04-role-vocabulary-indirection-design.md`)
and the seven-task plan is `346950b`.

**What shipped, in commit order.**

- `6347078`, `b15b449` — golden pins written BEFORE any behaviour changed,
  so a published vocabulary 1-3 template's role behaviour could not shift
  quietly underneath this work. These are what make the back-compat claims
  below checkable rather than asserted.
- `47b900c` — `RoleDefinition` (`id`, `attests` defaulting true, `decides`
  defaulting false), `TemplateSchema.role_lookup()` normalising mixed
  strings and objects exactly as `status_lookup()` does, and vocabulary 4's
  own validation rules (including §5.2's at-least-one-decider).
- `1435a5c`, `6205009` — decision authority becomes the **intersection** of
  tenant permission and declared capability. The second commit is the
  tenant half, and it is a deliberate tightening: before it, a member whose
  PROJECT role was `approver` but whose TENANT role was only `contributor`
  — a pairing an admin can create today — could decide. That is the
  privilege-escalation path spec Sec.4's intersection exists to close.
- `00d474f` — the attest path resolves declared capability through the bound
  template at both call sites: evidence revisions and **attachment upload**,
  which supersedes the active attachment and so carries the same control.
- `b646822` — declared roles become assignable project roles. `ProjectMemberIn.role`
  stops being `Role`-typed and `create_project` validates against the
  binding instead: at vocabulary 4 the permitted set is what the template
  declares, below 4 it stays exactly the platform enum.
- `489cde7` — `fixtures/synthetic/frameworks/agile.v4.json`, and the
  narrowing invariant proved end to end.

**The invariant the conversational design had missed, and that the
Blueprint forced.** Blueprint Sec.2's six product roles are the platform
authority model, not framework vocabulary. So a declared role **narrows**
authority within that model and must never grant authority the holder's
tenant role lacks — spec Sec.4. `test_role_invariant.py` proves it on a
genuinely READY gate using the real manifest digest from preview, and pins
the refusal's detail string, so the 403 cannot be readiness, a stale digest
or the MFA dependency wearing a 403 ('contributor' is not in
`ROLES_REQUIRING_MFA`, so that path is not even engaged).

**Back-compat is structural, not asserted.** `role_lookup()` synthesises a
`RoleDefinition` for every bare string and `attests` defaults true, so no
vocabulary 1-3 template can lose an attester. Below vocabulary 4 the
legacy branch answers deciding authority WITHOUT regard to declaration,
testing the project role against `rule_engine._LEGACY_DECIDING_ROLES`
directly — which is what keeps `lightweight.json` (declares
`["contributor", "approver"]`, never written to enumerate `sponsor`)
working for a tenant sponsor who held authority before this work.

**Vocabulary 4 ships accepted but unused.** `rule_engine.VOCABULARY_VERSION`
remains **2**, unchanged by this work, exactly as it remained 2 when
vocabulary 3 shipped. That constant is the stamp every new guided-authoring
draft gets (`routers/templates.py`'s `_BLANK_SCHEMA`), and the metadata
form still emits plain comma-separated strings, so bumping it would make a
vocabulary the authoring UI cannot express the default for all new
templates. A template that explicitly declares `"vocabulary_version": 4`
validates and behaves per v4 in full; it is simply not the default. The
only v4 artefact in the repository is `agile.v4.json`, which carries
`_meta.validation_fixture: true` and is therefore skipped by
`scripts/seed_starter_frameworks.py` — the flag is the mechanism, not a
filename list, which is why the new fixture needed no change to that script.

**Two things went beyond the plan, deliberately, and are recorded as such.**

1. **The UI that fronts project membership.** The plan's Task 5 named only
   `ProjectMemberIn` and the `role=member.role.value` line. Loosening the
   type exposed a form that then contradicted the API it fronts:
   `webapp/router.py` coerced the submitted role through `Role(member_role)`
   and rendered "Unrecognised role", so every valid v4 role was rejected
   before `create_project` could see it; and `project_new.html` offered a
   hardcoded `<select>` of the five platform roles, every one of which a v4
   binding refuses, with no way to name a declared one. Both fixed —
   `PublishedVersionOut` gained `member_roles` so the form's hint states
   what the chosen binding actually accepts, and the field is now a text
   input matching the idiom the class field on the same form already
   established. Leaving it would have shipped an API-only feature behind a
   form that could not reach it.
2. **A test bug of this session's own making, pinned rather than papered
   over.** The first draft of the webapp tests switched back to the admin
   with `_register_and_login_ui` — but that posts `/ui/register`, and
   registering a taken email leaves the session as whoever it already was,
   so the rest of the test ran as the member and read an unrelated page.
   Added a real `_login_ui` helper and an explicit assertion that
   `/auth/me` is the invited member, so the same mistake fails loudly next
   time instead of passing against the wrong page.

**One wart tidied.** The `>= 3` validation blocks apply v3's content rules
to every higher vocabulary — correct — but said "vocabulary 3 requires..."
regardless of what the author declared, sending someone who wrote
vocabulary 4 looking for a mistake in a version they are not using. The
version *gates* are unchanged; only the wording now names the declared
version. `test_dec07_status_semantics.py` needed no edit, because its cases
declare `vocabulary_version=3` and so still correctly read "vocabulary 3".

**Two items recorded Open rather than closed, honestly.**

- **WP05 was nominally delivered while REQ-010's role scheme was never
  implemented** — the same requirement-versus-verification shape TST-010
  had for statuses and decisions. The instance is now fixed; what stays
  open is that **nobody has checked whether other REQ/TST pairs share that
  shape**. That audit has not been run and is not claimed.
- **AC08/AC09 remain unverified.** They reference Directive v1.2, which is
  not in this repository (spec §2.1). This work closes a register row and
  an unmet REQ-010 Must; it is **not** claimed to satisfy WP05's acceptance
  criteria, because the document those criteria are written against cannot
  be read here to check them.

**Verified: the whole suite, chunked.** Run two files per pytest process
(this machine's 3.46GB RAM OOM-kills a single full-suite process, and as of
2026-10-04 so do 5- and 3-file chunks), with
`test_dec08_performance_budgets.py` run alone because its measurements are
load-dependent: **25 chunks, 379 tests, all green, no failures, no errors
and no skips**, plus the perf budgets 3 passed on their own. Nothing was
skipped for want of Postgres this session -- real Postgres with
`bgp_owner`/`bgp_app`/`bgp_backup` was available and used, so the RLS,
durability and webapp files genuinely ran rather than skipping green.
`ruff check` and `ruff format` clean across the full `app`/`tests` tree.

Of those 379, this work's own additions are 30 tests across five new files
(`test_role_vocabulary_backcompat.py` 4, `test_role_semantics.py` 11,
`test_role_decision_authority.py` 9, `test_role_assignment.py` 5,
`test_role_invariant.py` 1), plus `test_permitted_role_enforcement.py`
extended from 9 to 11, `test_wp13_webapp_new_pages.py` by 2, and
`test_framework_fixtures.py` updated for the sixth fixture.

**No gate decision.** Evidence documents, fixtures, code and tests only —
no `tracker_cli.py` invocation of any kind and no `tracker_cli.py gate`
action. The register rows above are findings and closures of findings, not
approvals; a gate decision remains a named human authority's sign-off.

## IPA04's stale DEC08 sub-part claim corrected; what actually keeps it Open (2026-10-07)

Housekeeping with a real finding in it, done immediately after PR #18
merged (`de06592`, CI run `37700760348` success, and — worth noting for the
first time in this project's history — a genuine `APPROVED` review from
kenAddme on commit `09c4da5`, checked via `gh pr view --json reviews`
rather than inferred from "merged", per the EC-202 precedent that every
previously sampled PR carried only `COMMENTED`).

**The finding.** `docs/DEFECT_REGISTER.md`'s IPA04 row — the only High,
explicitly release-blocking row still Open — listed two of DEC08's three
numeric sub-parts as unbuilt:

> render-timing (LCP/INP/CLS) and page-weight budgets (need a
> Lighthouse-CI-style harness this project doesn't have) and the async
> export-streaming budget (exports.py is synchronous in this prototype per
> WP01's own scope limit, so there's no "begin streaming" moment to
> measure yet)

**Both were built on 2026-10-01 in `5e9baf5` (PR #9) and the row was never
updated.** Verified against primary sources rather than the row's own
prose, which is the whole point:

- `tools/perf-budgets/` exists and is committed — `check.mjs` (16.9 KB),
  `package.json`, `package-lock.json`, README — and is driven by a
  **blocking** CI step, "Render-timing and page-weight budgets (DEC08
  Q14/Q16)" in `.github/workflows/ci.yml`, alongside the Node-setup and
  dev-server-health steps it needs. Measured with real headless Chrome via
  Lighthouse, not simulated.
- The export budget's premise no longer holds. `exports.py`'s download
  endpoint streams incrementally through `_iter_archive_json` and a real
  `StreamingResponse`, so the "begin streaming" moment exists and is
  measured by `test_wp12_render_and_export_budgets.py` (2 tests, live
  Postgres): one proving `_iter_archive_json` yields more than one chunk
  and matches `json.dumps`, one proving the download does not buffer the
  whole body first.

So all three of REQ-043's numeric sub-parts are enforced, each in the only
place able to measure it. The identical stale claim was also sitting in
`backend/tests/test_dec08_performance_budgets.py`'s own docstring, where it
was actively misleading — a reader of that file would have concluded the
other two sub-parts did not exist — and is corrected in the same commit to
name where each one IS enforced.

**This changes nothing about IPA04's Status, and the row says so
explicitly.** It stays **Open**. What keeps it open is the assurance half,
untouched by this edit and not performable by an agent:

- the manual WCAG audit (keyboard, screen reader, zoom, colour contrast —
  the 2026-09-30 axe-core/jsdom pass found 0 violations after one real fix
  but cannot evaluate paint-dependent rules, as that writeup states);
- an independent security review;
- usability sessions (kenAddme named reviewer 2026-09-30 — an assignment,
  not a performance);
- real cross-zone/cross-region replication, a named non-goal of the DEC05
  design spec rather than an omission.

**Why this matters beyond one row.** This is the exact failure mode
`CLAUDE.md`'s backfill note describes — real work shipped, the governance
record never caught up — and it was sitting in a High release-blocking row,
where a stale "still unbuilt" list is worse than no list: it invites
re-doing work already done, and it misrepresents readiness in the direction
of under-claiming while the row's headline over-claims what remains. Found
by checking the row against the repository, which is the only way these
surface.

**No gate decision.** A register correction and a docstring correction,
both evidence-backed. No `tracker_cli.py` invocation of any kind.

## The REQ/TST verification audit, run: one real defect, one false alarm refused (2026-10-07)

`docs/DEFECT_REGISTER.md`'s WP05 row asked a question it did not answer:
REQ-010 named four schemes and TST-010 asserted three, so **do other
REQ/TST pairs share that shape?** That audit is now run. The answer is yes,
and it found one probed defect, one thing worse than first recorded, and
one apparent high-severity hole that turned out not to be one.

**Method.** All 58 entries in `docs/blueprint/Requirements_Catalogue.json`,
each requirement's own enumerated list against its own `verify` text. 45
enumerate three or more items. A mechanical word-overlap pass flagged 34 as
missing two or more — but that pass counts a synonym as a gap, so it was
used only to rank candidates, and every top candidate was then read and
judged against the primary text. That distinction matters: the mechanical
output alone would have produced four confident-looking findings that are
not real.

**1. REQ-010 is worse than the register said.** Its text names **seven**
schemes — tracks, gates, classification, role, status, decision,
applicability — and TST-010 verifies three ("classes, roles and gates").
The register row recorded "four things vs three" from memory of the
conversation; reading the catalogue says seven vs three. The role scheme is
now implemented (PR #18); `applicability` and `tracks` remain unverified by
TST-010's own text.

**2. REQ-017 — a genuine match, and it yielded a real defect.** REQ-017
requires tracking evidence status, owner, due date, completion date and
reference; TST-017 verifies only the revision/attribution half ("Editing
creates a new revision; prior actor, time and values remain available") and
never asserts the five fields. Following the field list into the code found
that `CreateEvidenceRevisionRequest` defaults `owner_user_id`, `due_date`,
`completed_date` and `reference` to `None`, and `routers/projects.py`
assigns all four to the item unconditionally.

Probed, not assumed. After setting owner=`1f0f3339...` and
due=`2026-12-01`, a revision sending only `{base_revision, status,
reference}` left the item at **owner=`None`, due=`None`**. The append-only
history is intact — revision 2 still holds both — so this is current-state
loss, not audit-trail loss. Two consequences: REQ-017's own field list is
silently dropped by a routine status update, and
`_require_permitted_to_attest`'s first exemption reads
`item.owner_user_id`, so an owner who posts a status update clears their
own ownership and loses that exemption next time.

**Recorded, deliberately not fixed.** `EvidenceItem`'s docstring says the
item fields "always mirror the latest EvidenceRevision", so mirroring
`None` may be the intended append-only semantic — each revision a complete
statement — rather than a bug. But the API offers no way to say "keep the
current owner" and nothing documents that every revision must re-send these
fields. Which of the two it is (a missing partial-update semantic, or an
undocumented complete-statement contract) is an owner's design call, so it
is in the register with its probe evidence instead of being changed
unilaterally. The probe itself was throwaway and is **not** committed, on
purpose: a test asserting today's behaviour would pin in whichever semantic
turns out to be the unintended one.

**3. REQ-008 looked like the worst of them and is not a defect.** A
*tenant-isolation* requirement naming workers, files, caches, search and
exports, whose TST-008 verifies only pooled-connection reuse and
mixed-tenant jobs. On the mechanical ranking this was the top security
candidate. On checking the code it is **vacuous by absence**: every named
surface that exists is covered — files by
`test_wp15_evidence_attachments.py`'s cross-tenant download refusal plus
the handler's own `tenant_id` filter, exports by
`test_wp09_tenant_isolation_rls.py` (2 tests) — and the three uncovered
ones **do not exist in this codebase at all**. Grep for
redis/memcached/cachetools/lru_cache, celery/rq/BackgroundTasks, and
tsvector/to_tsquery/ILIKE returns nothing, and no such dependency is
declared. Written down as absence, not as a hole, and explicitly not
rounded up — this is the row where the audit was most tempted to overclaim.

**4. REQ-023, REQ-015, REQ-044 — document-level narrowness, not gaps.**
REQ-023's verify ends in a catch-all ("include all required bindings").
REQ-015's field list is covered in practice by `test_projects.py` though its
verify text asserts only atomicity. REQ-044 matches the shape but is an
assurance requirement already inside IPA04's "no independent assurance
performed", not a separate code gap.

**What is left, and why the WP05 row stays Open.** A decision on the
REQ-017 finding, and whether TST-008's and TST-010's verify *text* should be
corrected to name which surfaces they cover — so a future reader can tell
"covered" from "does not exist". Neither is done, so the row is updated with
the audit's result rather than closed.

**No gate decision.** An audit, a probe, and two register writes. No
`tracker_cli.py` invocation of any kind.

## The REQ-017 finding, decided and fixed: a revision is a complete statement (2026-10-10)

The REQ/TST audit above left exactly one thing for an owner rather than an
agent: **which of two readings the owner/due/completed clearing actually
was** — a missing partial-update semantic, or an undocumented
complete-statement contract. The audit deliberately refused to pick, and
deliberately committed no test, because a test asserting the *current*
behaviour would have pinned in whichever semantic turned out to be
unintended.

**The decision (owner, 2026-10-08): the second.** `EvidenceItem` mirroring
the latest `EvidenceRevision` is intended. A revision *is* a whole statement
of the item's state, and `None` legitimately means "no owner"/"no date". So
the mirroring was never the defect. The defect was that
`CreateEvidenceRevisionRequest` let a caller **omit** those fields and still
receive a 201 — losing ownership and dates by accident rather than by
instruction.

**The fix is therefore a contract, not a behaviour change.** The four
mirrored fields (`owner_user_id`, `due_date`, `completed_date`, `reference`)
are now **required and still nullable**: clearing stays available to a caller
who says so, and omitting is refused 422 naming the field.
`source_version` and `source_hash` stay optional — they are recorded on the
revision and never mirrored onto the item, so they are outside the contract,
and a test pins that they were not swept into it. The contract is documented
on the request model itself, which is the half of the register row's
complaint that documentation rather than code had to answer.

**Making the fields required immediately found a second, live defect — the
more serious one.** `webapp/router.py`'s evidence-submit handler, UI04's
Submit button and the endpoint's actual production caller, built its payload
from `status` and `reference` alone. So **every browser evidence submission
had been clearing the item's owner and both dates**, which makes the
register row's "silent" rating understated: this was not a latent API
sharp edge, it was the default path. The form now restates the owner and
dates it does not itself edit. Worth naming plainly: a required-field
contract converted a silent production data loss into a loud failure within
one test run, which is the whole argument for the owner's choice over a
`None`-means-keep patch.

**Nine tests, written RED first** (`test_revision_complete_statement.py`;
the five omission cases returned 201 and mirrored `None` before the change —
the probe the register row recorded, now committed as a test). Both
directions are covered, not just the refusal: each of the four fields
parametrised separately so a default silently reappearing on any one of them
fails on its own; a refused revision leaves owner, due date and
`latest_revision_number` untouched (a refusal that still mutated would be
worse than the defect it replaces); an explicit `null` **still clears**, so
the fix is not a narrowing dressed up as validation; a complete revision
carries owner and dates forward, which is REQ-017's actual requirement; and
the UI submit path keeps the owner and due date while still applying the
`reference` its form does edit.

**The breaking change was settled across the suite, not suppressed.** ~47
request literals in 13 existing test files plus the one production call site
were made explicit. The transform was checked mechanically rather than by
eye: parsing every dict literal in all 14 modified test files, old versus
new, and normalising away mirrored keys whose value is exactly `None`, leaves
the two sides **identical** — so no test's subject changed, every added value
is an explicit statement of what that payload was already getting by
default.

**Verified: the whole suite, chunked.** Two files per pytest process (3.46GB
RAM): **26 chunks, 387 passed, no skips**. One red, and it is **not** this
change — `test_dec08_performance_budgets.py::test_decision_write_budget_hold_and_supersede`
breached its latency budget while sharing a process with `test_decisions.py`,
the load-dependent false-red this file already documents above ("this machine
can produce a false-red budget check under load", with the standing
instruction to run that file alone). Re-run alone per that protocol: **3
passed in 27s**, against 212s for the paired chunk — so 388 distinct tests
green. The budget was not loosened and no retry or skip was added, matching
how the earlier instance was handled. `ruff check` and `ruff format` clean.

**`docs/openapi.json` regenerated, and what that exposed.** The contract
change is a router change, and `docs/api-reference.md` carries a standing
instruction to regenerate the snapshot after any such change. Doing so moved
it from **46 paths / 58 schemas to 92 paths / 84 schemas** — nothing removed.
Only a few of those are this change; the rest is three weeks of accumulated
drift from WP11/WP13/WP15, IPA02 and UI09 that nobody regenerated for. That
drift is not a side effect worth hiding: it is direct evidence for the
caveat tracker item **#125** already carries, that nothing in CI checks the
snapshot against the live schema. #125's evidence citation is corrected to
the new counts and **stays In progress** — the regeneration fixes the
staleness, not the gap, and the same drift recurs on the next router change.
Its closing evidence would be a CI step that fails when snapshot and live
schema disagree, plus the architecture/data/operational docs that still do
not exist.

**Register effects.** The REQ-017 row moves to **Closed (2026-10-10)** with
the decision, the fix, the second defect it found, and the test evidence.
The **WP05 REQ/TST row stays Open**, narrowed: its REQ-017 arm is now
decided and fixed, so what remains is the documentation half — whether
TST-008's and TST-010's verify *text* should name which surfaces they cover,
plus TST-010's two still-unverified schemes (`applicability`, `tracks`).

**No gate decision.** One evidence-item evidence correction (#125, status
unchanged at In progress) and two register writes. No `tracker_cli.py gate`
invocation, and none is implied by a green suite.

### CI result on this branch, and two things it settled (2026-10-10)

Run `38064789545` on `121422d`: **green**, every step including the blocking
render-timing/page-weight budgets, the dependency-vulnerability scan and the
secret scan. `pytest -q`: **386 passed, 2 skipped** in 185s.

**1. The DEC08 false-red does not reproduce on GitHub's runners — an open
question above, now answered.** The note on the earlier instance said
plainly: "**Not yet known**: whether GitHub Actions' own runners (far more
RAM than this box) would ever reproduce this inside `ci.yml`'s `pytest -q`
step". They do not. CI ran the **entire suite in one long-lived process** —
the exact shape that OOM-kills this dev box — and
`test_decision_write_budget_hold_and_supersede` passed inside it, then
passed again in its dedicated step (3 passed in **4.12s**, against 27s
running alone locally and 212s for the paired local chunk). So the red seen
locally is confirmed machine-local, and the budget numbers themselves have
real headroom on the runner. This is the evidence the earlier note said was
missing; it is **not** a licence to dismiss a future CI red on that file,
which would mean something different entirely.

**2. CI never exercises the live malware scanner — the 2 skips, and they are
not from this change.** Both are `test_wp15_cloudmersive_scanner.py`, whose
module-level `pytestmark` skips on `not settings.cloudmersive_api_key`.
**`BGP_CLOUDMERSIVE_API_KEY` is never referenced in `.github/workflows/ci.yml`
at all**, so it is never set there — grep confirms. It *is* configured on this
dev machine, which is why the local chunked sweep reported **zero** skips and
388 passed while CI reports 386 + 2. Same 388 tests collected either way; the
difference is entirely those two.

What that means, stated plainly rather than filed as a counting curiosity:
**the EICAR detection-and-quarantine path is only ever proven on one
developer's machine.** The attachment scanner is the control that keeps an
infected upload from becoming a downloadable active attachment — adjacent to
REQ-046 and to the attachment-authorisation row above — and CI silently
skips its only live test instead of failing or warning. A reader of a green
CI run would reasonably assume otherwise. **Not fixed here** (out of this
branch's scope, and it needs a decision about whether to hold a scanner
credential in CI secrets or to add a mocked-transport test that at least
pins the quarantine logic). Recorded so the next person does not discover it
the way this branch did — by reconciling two test counts.

## REQ-010's last two schemes probed: `applicability` is fine, `tracks` is inert (2026-10-10)

The REQ/TST audit left one question of its own unanswered — REQ-010 names
**seven** schemes (tracks, gates, classification, role, status, decision,
applicability) and TST-010 verifies three, so were the two never-checked ones
honoured or not? Probed now, and they **split**, which is why both halves are
written down rather than one headline.

**`applicability` is honoured — no defect.** It is a real rule-level
`Condition` (`rule_engine.py`'s `Rule.applicability`), evaluated against
`class_id` at project creation (`routers/projects.py`: `if
rule.applicability is not None and not evaluate_condition(rule.applicability,
{"class_id": class_id}, as_at=as_at)`), counted in the node budget alongside
`conditions`, and covered by DEC07's `as_at` fail-closed path for
date-comparing rules. Recorded explicitly so nobody spends the probe again:
this one was a false lead, and it is the second time this audit's mechanical
ranking pointed somewhere real work was already done.

**`tracks` is inert — the third field of REQ-010's list to fail the same way**
as statuses (DEC07-Q11) and roles. Required of the author
(`tracks: list[str] = Field(min_length=1)`, and `tracks: str = Form(...)` in
the guided form), validated, echoed in the editor, rendered on the version
page — and **consumed by nothing**. Exhaustive grep of `backend/app/` returns
exactly **8** references, every one of them declaration, parse or display.
There is no `track_lookup()` beside `status_lookup()`/`outcome_lookup()`/
`role_lookup()`. **`GateDefinition` has no `track` field at all.**
`models.py` carries no track column on any table. No validation
cross-references gates against declared tracks the way `permitted_role_ids`
is checked against declared `roles`.

**Two shipped fixtures assert a structure the engine cannot represent:**
`standard.json` declares `["Delivery", "Assurance"]` across 4 gates;
`regulated.json` declares `["Delivery", "Assurance", "Compliance"]` across 6.
A gate cannot be assigned to any of them, so a multi-track framework
collapses to a flat gate list.

**Rated Low, deliberately below its two siblings, and the reason matters.**
Statuses broke readiness evaluation; roles failed attestation authority
**open**. `tracks` drives no behaviour at all — nothing is mis-evaluated, no
control is bypassed, no gate decision is affected, no data is lost. It is a
required field that is inert. What keeps it off Negligible is specific: this
product exists to run the PM (Gates 1-7) and SDLC (G0-G6) sequences **side by
side** — the PM Framework's own Appendix I reconciles exactly two tracks, and
the `pm-sdlc-tracker` CLI renders a `track` column — so the one structure the
product is built to express is the structure a template cannot currently
express. Recorded as functional/representational, **not** as a control
failure, and not inflated to match the siblings it resembles.

**Not fixed, and for the same reason the role vocabulary was a two-step job.**
Binding gates to tracks changes the **versioned template contract**, and
template versions are immutable under REQ-011, so a naive required `track` on
`GateDefinition` would invalidate every already-published template. The two
honest options are a `vocabulary_version`-gated optional `track` (the
mechanism DEC07 and the role work both used), or a decision that `tracks` is
presentational metadata and should be **documented as such rather than
implemented** — a legitimate and much cheaper answer. Which it is, is an
owner's design call, exactly as the REQ-017 row was.

**No test committed, deliberately.** There is no behaviour to assert, and a
test pinning today's state would assert that a required field does nothing —
pinning in the gap if the answer turns out to be the gated binding.
Independent confirmation that TST-010 never covered this: all 15 `tracks`
occurrences across `backend/tests/` are fixture literals satisfying the
required field; not one asserts track behaviour.

**What this does NOT close, and why the WP05 row stays Open.** All seven of
REQ-010's schemes are now accounted for (six honoured, one not), so the
audit's own question is answered. What remains is the documentation half
alone: whether TST-008's and TST-010's verify *text* should be corrected to
name which surfaces they cover. **That is not an agent's edit to make.**
`docs/blueprint/Requirements_Catalogue.json` is an approved, controlled
blueprint artefact (APR-001, 2026-09-15); correcting a requirement's verify
text changes an approved document and needs the owner's authority, not a
convenient in-place fix. Flagged, not done.

**Merge note on PR #19.** Approved by `kenAddme` and merged as `1e05b31`.
Recorded precisely: that is the **delivery lead's** approval — the authority
who instructed the work — and **not** the independent review. `TRACKER.md`'s
own "Named roles" names Milton as independent reviewer, and the PM
Framework's Section 3.3 bars self-approval, so every register row's
"Not reviewed" cell stays as written. A merged PR with an APPROVED review is
not independent assurance and must not be cited as satisfying one.

**No gate decision.** A probe and two register writes.
