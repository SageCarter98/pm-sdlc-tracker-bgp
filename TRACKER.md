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
  actually executed**, because this repo has no git remote to push to and
  trigger GitHub Actions. REQ-009's "blocking CI check" clause stays an open
  gap until a real CI run is observed passing (and, ideally, failing on a
  reintroduced leak) — don't round that part up to Complete from the local
  config alone.
- **WP05** (templates and declarative rule interpreter) is committed and
  tested against SQLite: the Sec.5.5 rule vocabulary (equality/membership/
  bounded-all-any only, no eval/exec, max nesting depth 5, a fixed
  prohibited-facts list blocking things like `disable_audit`), template
  create/fork/import/publish with publish-time immutability, and three
  neutral fictional framework fixtures (not real KenAddme content — DEC03
  licensing is still unresolved, so REQ-014's neutral-starter fallback
  applies). 41 passed, 6 skipped (same Postgres-gated WP04 suite as before —
  WP05 adds an RLS policy for templates but that's equally unverified until
  Postgres is set up).
- **DEC07 (rule vocabulary/third framework) is still open** — WP05
  implements the schema shape Sec.5.5 already approved, but the "exact
  vocabulary and limits" the blueprint reserves for DEC07 are this
  session's working choices, not a technical-lead sign-off. Don't treat the
  prohibited-facts list or the depth-5 limit as settled without that review.
- Still Not started across WP03/WP04/WP05: #124 (AI-generated code reviewed
  by a human). Three work packages in, zero of them reviewed by Milton.

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
