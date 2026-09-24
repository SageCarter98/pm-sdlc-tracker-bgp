# Work-package identifier mapping (IPA01)

Closure-evidence draft for **IPA01** ("Work package identifiers have drifted"),
`BGP_Implementation_Plan_Alignment_Findings_v1.0.docx` (BGP-IPA-001,
2026-09-22). Maps each `TRACKER.md` increment heading that reuses a
Blueprint Section 6 WP number to what the Blueprint actually assigned that
number to, and to what the increment actually built.

**Status: drafted, not independently reviewed.** Per the same discipline
applied to every other AI-drafted document in this project (see
`docs/wp02/README.md`, `docs/wp02/threat_model_and_privacy_assessment.md`),
this closes the *documentation* half of IPA01 but not the *review* half —
tracker item #99 (SDLC G1.08) stays "In progress" until a named reviewer
checks this mapping, the same way #97/#109 stayed "Submitted for review"
rather than "Complete" after drafting.

## The collision, precisely

Blueprint Section 6 (`docs/blueprint/Blueprint_Working_Source.md`, table at
line 730) assigns exactly 14 work packages, WP01–WP14, each with its own
dependency list and deliverable. `TRACKER.md` reuses three of those numbers
— WP11, WP13, WP14 — for later increments whose actual deliverable has
**nothing to do with** what the Blueprint assigned to that number. This is
worse than BGP-IPA-001 itself stated: that document names WP13/WP14/WP15;
checking the Blueprint table directly (not just TRACKER.md's own headings)
shows **WP11 collides too**.

| Blueprint # | Blueprint's actual assignment (Sec. 6) | Built? | What `TRACKER.md` uses that number for instead |
| --- | --- | --- | --- |
| WP11 | Usability and accessibility — participant protocol, accessible journey results, remediation evidence | **Not built** | "WP11 (frontend, DEC04 resolved)" — building the frontend pages themselves, not testing an existing one for usability/accessibility |
| WP13 | Independent acceptance and release — penetration test, user acceptance, release and rollback records | **Not built** | "WP13: design-system reskin + 4 more real pages" |
| WP14 | Optional and paid capabilities — attachments, reminders, practice and billing | **Partially built, under a different number** (see below) | "WP14: in-product requirement guidance on tenant-authored gates/rules" — a capability with no REQ ID in the 58-item catalogue at all |

Blueprint WP12 is the last number `TRACKER.md` uses consistently with its
Blueprint meaning ("Operations and hardening"). Everything from WP11 onward
in `TRACKER.md` is a same-number-different-thing collision, an
unassigned-number reuse (WP15), or new scope with no Blueprint WP or REQ
anchor at all.

## Increment-by-increment mapping

| `TRACKER.md` heading (date) | What was actually built | True Blueprint anchor | Requirement IDs | Authorization reference | Dependencies (actual) | Acceptance evidence |
| --- | --- | --- | --- | --- | --- | --- |
| "WP11: frontend, DEC04 resolved" (2026-09-20) | Server-rendered FastAPI+Jinja2 pages for UI01/UI03/UI04/UI06 | The **frontend half of Blueprint WP10** ("Essential user journeys" — WP10 itself was built backend-only in 2026-09-17, see WP10 entry) | REQ-032, REQ-034, REQ-036, REQ-037 (WP10's own); REQ-033, REQ-039 (flagged frontend-only when WP10 shipped backend-only) | DEC04 resolution — a single owner chat instruction, not an independent or stakeholder review (same pattern as APR-001/FE-APR-001) | WP03, WP06, WP07 (Blueprint WP10's own dependency list) | `test_wp11_webapp_rls.py`; 137/137 passing; browser walkthrough same session |
| "WP13: design reskin + 4 more real pages" (2026-09-20) | UI02/UI05/UI07/UI10 pages; design tokens reconciled from a Stitch mockup zip into `app/static/style.css` | Continuation of the same frontend build as "WP11" above — still implementing Blueprint's UI01–UI10 interface spec (Sec. 4), not Blueprint WP13 | UI02, UI05, UI07, UI10 (Sec. 4); FE-001..FE-102 (FE-APR-001 catalogue) | `docs/blueprint/BGP_Frontend_Requirements_v1.1_FE-APR-001.md` — a single owner chat approval ("Okay, approve all draft in it, just finished personal review"), a **separate** authorization from the original Directive v1.2/Blueprint v0.2 | The "WP11" frontend increment above | `test_wp13_webapp_new_pages.py`; 143/143 passing; browser walkthrough found and fixed 3 real bugs same session |
| "WP14: in-product requirement guidance" (2026-09-21) | Renders template-authored guidance text on evidence/gate pages | **No Blueprint WP or REQ anchor.** Closest adjacent concept is WP05's "guided authoring contract" deliverable, but this specific capability (rendering guidance to the *evidence submitter*, not the template author) is not itemized in the 58-REQ catalogue | None identified | None beyond an in-session "start WP14" instruction — no dated approval record like FE-APR-001 exists for this scope addition | Template/rule authoring (WP05); the frontend pages above | `test_wp14_requirement_guidance.py`; 146/146 passing; browser walkthrough same session |
| "WP15 Phase 1: evidence attachments" (2026-09-21) | `evidence_attachments` table, upload/download API+UI, permanently-undownloadable-until-scanned gate | **Blueprint WP14's actual attachments deliverable** (REQ-053) — correctly scoped content, filed under the wrong/unassigned number | REQ-053 (Conditional: "If enabled, scan, cap, encrypt and version uploads...") | User explicitly asked for uploaded evidence, then agreed to a staged Phase 1/2/3 plan before code — an in-session instruction, not a dated formal approval | WP06/WP07 (matches Blueprint WP14's own dependency list: WP07 WP09 WP10) | `test_wp15_evidence_attachments.py`; 150/150 passing; browser walkthrough same session |
| "WP15 Phase 2: Cloudmersive scanner" (2026-09-21) | Real virus-scanning integration completing REQ-053's "scan" clause | Same anchor as Phase 1 — REQ-053 | REQ-053 | User chose Cloudmersive over VirusTotal (data-boundary rationale), obtained and configured the API key — in-session decision | WP15 Phase 1 | `test_wp15_cloudmersive_scanner.py` (real API, EICAR test string detected); 153/153 passing; browser walkthrough same session |

## What this does and does not close

**Closes**: the traceability gap of "what does each later `TRACKER.md`
heading actually correspond to" — every increment above now has a stated
REQ/Blueprint anchor (or an explicit "none exists" where that's the honest
answer, e.g. WP14's guidance feature).

**Does not close**:
- Blueprint's real WP11 (usability/accessibility testing) and real WP13
  (penetration test, user acceptance, release/rollback records) have **not
  been done** — they are not merely mislabeled, they are outstanding work,
  now harder to see because their numbers are shadowed by unrelated
  increments in `TRACKER.md`. Tracked separately as **IPA02**
  (frontend journeys) and **IPA04** (durability/independent assurance,
  release-blocking) in BGP-IPA-001 — this mapping does not substitute for
  either.
- Independent review of this mapping itself, per IPA01's own closure
  evidence requirement.
- Renaming or renumbering anything already shipped — this is a mapping
  record, not a proposal to relitigate what `TRACKER.md` already calls
  things.
