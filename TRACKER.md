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

**Still honestly open**: no CI run has been deliberately broken to prove a
relevant check goes red (same gap named after the CI-green milestone
above). `#124` stays Not started — none of this was reviewed by Milton.
Committed locally? — not yet; only edited this session, no commit or push
requested.

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
