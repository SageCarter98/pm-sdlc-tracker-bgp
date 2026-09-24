# Defect register (SDLC G3.12)

Structured register of known defects found and fixed since the first BGP-F0x
review, closing the gap tracker item #126 named: prior write-ups in
`TRACKER.md` describe each fix in narrative form but never as one register
with consistent owner/commit/test/closure fields per finding. This file is
the register; `TRACKER.md` remains the fuller narrative record — see there
for complete technical detail on any row.

A defect is added here once it is found, and a row's `Status`/`Closure date`
are only updated once tests demonstrate the fix (never on the fix commit
existing alone). No row here is a gate decision.

| ID | Description | Severity | Discovered | Fix commit(s) | Reviewer (real, checked) | Test evidence | Status | Closure date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BGP-F01 | `POST /auth/login` issued a full session for an MFA-enabled account before the second factor was checked | High (auth bypass) | 2026-09-17 (`BGP_Development_Review_Findings_v1.0.pdf`) | `b1fb402` | Not reviewed by Milton | `test_identity.py` (2 new MFA-session tests) | Closed | 2026-09-17 |
| BGP-F02 | Compensating review's reviewer/note were caller-supplied, so the deciding actor could self-approve | High (separation of duties) | 2026-09-17 (same PDF) | `b1fb402` | Not reviewed by Milton | `test_decisions.py` (2 new compensating-review tests); `test_wp07_tenant_isolation_rls.py` (3 new RLS tests) | Closed | 2026-09-17 |
| BGP-F03 | No lock/constraint stopped two concurrent decisions or evidence revisions from both passing readiness checks before either committed | High (concurrency/integrity) | 2026-09-17 (same PDF) | `b1fb402` | Not reviewed by Milton | `test_bgp_f03_decision_concurrency.py` (4 tests, live Postgres, raw-SQL lock proofs) | Closed (raw-SQL level only — see BGP-F03 follow-up) | 2026-09-17 |
| BGP-F04 | Export/import silently dropped evidence-revision history, compensating reviews, and original author/timestamp provenance on re-export | High (audit-trail integrity) | 2026-09-17 (same PDF) | `b1fb402` | Not reviewed by Milton | `test_export_import.py` (new round-trip and corrupted-archive tests) | Closed | 2026-09-17 |
| BGP-F05 | README described the WP01-only skeleton, not the real WP01/WP03–WP10/WP12 build | Low (documentation) | 2026-09-17 (same PDF) | `b1fb402` | Not reviewed by Milton | N/A (documentation) | Closed | 2026-09-17 |
| BGP-F01 follow-up | `POST /auth/mfa/enroll` overwrote the live MFA secret immediately, leaving a zero-second-factor window during factor replacement | High (auth bypass window) | 2026-09-18 (`BGP_Follow_Up_Review_Findings_v1.0.pdf`) | `b8bb22a` (PR [#3](https://github.com/SageCarter98/pm-sdlc-tracker-bgp/pull/3)) | MiltonBello15 — `APPROVED` on commit `b8bb22a`, checked via `gh pr view --json reviews` | `test_hardening.py` (+2: expiry, old-factor-still-works) | Closed | 2026-09-19 |
| BGP-F02 follow-up | Separation-of-duties check derived "preparer" from the reassignable `owner_user_id` field instead of who actually submitted the revision | High (separation of duties bypass) | 2026-09-18 (same PDF) | `b8bb22a` (PR #3) | MiltonBello15 — `APPROVED` on `b8bb22a` | `test_clearing_or_reassigning_ownership_cannot_defeat_separation_of_duties` | Closed | 2026-09-19 |
| BGP-F03 follow-up | Remaining unlocked reads (approver membership, exception rows) on the decision-commit path, plus tenant context lost after `db.rollback()` in the conflict handler | High (concurrency/RLS) | 2026-09-18 (same PDF) | `b8bb22a` (PR #3) | MiltonBello15 — `APPROVED` on `b8bb22a` | `test_decisions.py`, `test_integrity.py` fixture rewrites | Closed at the raw-SQL/lock level; the missing app-level HTTP test the review specifically asked for was the gap closed separately below | 2026-09-19 |
| BGP-F04 follow-up | Re-export lost the original author identity and creation timestamp for an imported evidence revision, substituting the importer and import time | Medium (audit-trail provenance) | 2026-09-18 (same PDF) | `b8bb22a` (PR #3) | MiltonBello15 — `APPROVED` on `b8bb22a` | `test_unmatched_revision_author_and_timestamp_survive_reexport` | Closed | 2026-09-19 |
| BGP-F03 app-level test gap | No test drove a real HTTP request through the actual decision endpoint into a genuine lock conflict — only raw-SQL/direct-table tests existed, which the follow-up review named as insufficient | Medium (test-coverage gap, not a code defect) | 2026-09-19 (found while addressing it) | `ac7f0f1` (PR [#4](https://github.com/SageCarter98/pm-sdlc-tracker-bgp/pull/4)) | MiltonBello15 — `APPROVED` on `ac7f0f1` | `test_bgp_f03_followup_app_level_concurrency.py` (real `TestClient` + real Postgres, deterministic lock-based conflict) | Closed | 2026-09-19 |
| Org-bootstrap RLS ordering | `get_active_membership`, `create_org`, and `accept_invitation` set Postgres tenant RLS context (`SET LOCAL app.tenant_id`) after the RLS-protected query instead of before — against real Postgres, nobody could create an org, and no existing member could pass membership resolution | High (availability/correctness — fail-closed RLS blocking legitimate access, not a data exposure) | 2026-09-19 (found writing the BGP-F03 app-level test above) | `ac7f0f1` (PR #4); migration `0014_org_bootstrap_rls_fix.py` | MiltonBello15 — `APPROVED` on `ac7f0f1` | `test_bgp_f03_followup_app_level_concurrency.py` (exercises `get_active_membership`'s fixed ordering indirectly); full suite (132 passed) | Closed | 2026-09-19 |
| IPA01 | `TRACKER.md`'s WP11/WP13/WP14/WP15 headings reuse Blueprint Sec.6 WP numbers already assigned to different deliverables (WP11=usability/accessibility, WP13=independent acceptance/release, WP14=optional/paid capabilities) — confirmed by direct comparison against the Blueprint's own WP table, which also showed WP11 collides too, not just WP13-15 as first reported | Medium (delivery traceability) | 2026-09-22 (`BGP_Implementation_Plan_Alignment_Findings_v1.0.docx`, BGP-IPA-001) | `5e00405` (`docs/wp_identifier_mapping.md`) | Not reviewed by Milton | N/A (documentation) — mapping table cross-checked against `docs/blueprint/Blueprint_Working_Source.md` line 730 | Submitted for review | pending |
| IPA02 | Mandatory frontend journeys (UI08 guided template authoring, UI09 export/import, membership revocation/role-change) remain API-only or missing, blocked on open DEC07/DEC06/DEC12 | High | 2026-09-22 (same document) | None — blocked on open decisions, not a code task | N/A | N/A | Open | pending |
| IPA03 | `decide_submit` (`backend/app/webapp/router.py` line 578) generates a fresh `uuid.uuid4()` idempotency key on every submission instead of preserving a stable request identity, so a lost response cannot be safely recovered by resubmitting (REQ-035) | High (release-relevant) | 2026-09-22 (same document) | None yet | N/A | N/A | Open | pending |
| IPA04 | Decision durability (DEC05) remains unimplemented; no independent fault/recovery/usability/accessibility/security assurance has been performed | High (explicitly release-blocking) | 2026-09-22 (same document) | None — needs named decision owners (DEC05/08/11) and real assurance activity, not a code fix | N/A | N/A | Open | pending |
| IPA05 | `README.md` claimed linting was unconfigured (stale since PR#5 added Ruff to CI, 2026-09-20) and listed "No frontend" under known gaps (stale since WP11/WP13, 2026-09-20/21) | Medium (documentation) | 2026-09-22 (same document) | `5e00405` (`README.md`) | Not reviewed by Milton | N/A (documentation) — grep-confirmed both claims are removed and replaced with the accurate current state, including honest open sub-findings (IPA02/03/04) | Closed | 2026-09-24 |
| REQ-020 validation gap | **Superseded same day, see resolution below.** Initial finding claimed REQ-020 had no implementation anywhere in `backend/app/`, based on grepping the literal string "Not applicable" -- the wrong search. The real mechanism is `ExceptionRecord` (authority/scope/expiry-checked), and `test_exception_excuses_a_hard_blocker_and_revocation_reinstates_it` already proved most of REQ-020's actual verify text. | Medium (was: traceability gap; corrected: test-coverage gap only) | 2026-09-24 | `backend/tests/test_decisions.py` (2 new tests, no production code changed) | Not reviewed by Milton | Both new tests independently verified to fail when the behavior they check is removed (temporarily broke `_exception_is_currently_valid`'s expiry check and the exception-scoping query, confirmed each test failed, reverted -- `git diff` on `decisions.py` is empty) | Closed | 2026-09-24 |

**Still open, honestly, per the source reviews' own language** (not claimed
closed anywhere in this register):
- BGP-F05 follow-up (clean-setup verification): migrations applied and the
  suite passed, but against the existing dev checkout, not a genuinely fresh
  clone with an empty database — see `TRACKER.md`.
- No CI run has ever been deliberately broken (e.g. a reintroduced tenant
  leak) to prove a relevant check actually goes red, for any finding above.
- **IPA02, IPA03, IPA04** (rows above, from BGP-IPA-001 2026-09-22): none of
  these are code-fixable in a documentation pass. IPA02 needs DEC06/07/12
  resolved before the missing UI can be built; IPA03 needs an actual
  idempotency-key/recovery-flow implementation; IPA04 needs named decision
  owners for DEC05/08/11 plus real independent assurance work. Do not close
  any of the three without that underlying work actually happening first.
- ~~REQ-020 validation gap~~ -- Closed 2026-09-24. See the corrected row above:
  this was a misdiagnosis (searched for the wrong terminology), not a real
  code gap. The actual gap was 2 missing tests, now added.
