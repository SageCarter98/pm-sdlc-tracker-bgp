# Frontend development requirements (extracted)

Extracted 2026-09-17 from `Blueprint_Working_Source.md` (owner-approved under APR-001,
2026-09-15) — Sections 2, 3 (Usability/Accessibility), 4, 5.1, and the DEC register. It is a
reference extract, not a new approval — the blueprint itself remains the authoritative source;
if this drifts from it, the blueprint wins.

**2026-09-20 update:** "No frontend code exists yet" (below) is now stale — WP11 resolved DEC04
and built a real server-rendered frontend for UI01/UI03/UI04/UI06; WP13 added UI02/UI05/UI07/UI10.
See `TRACKER.md`'s WP11/WP13 entries. There is also now a separate, later, owner-approved
frontend requirements document at `BGP_Frontend_Requirements_v1.1_FE-APR-001.md` (FE-APR-001,
2026-09-20) — a numbered FE-001..FE-102 supplement, not a replacement, of the REQ/UI identifiers
this extract already uses. Where the two describe the same screen, prefer the newer FE-APR-001
document; where they conflict, that document's own provenance note flags it rather than picking
a side silently.

## 1. What's already decided, and what isn't (read this first)

**DEC04 (Frontend and API session architecture)** — approved: a browser interface talking to a
same-origin API, modular FastAPI backend. **Not yet selected**: the frontend framework itself,
the session mechanism (the backend's cookie-based session in `app/security.py` is explicitly
"a prototype signed cookie, not the DEC04-approved design"), and pinned dependency versions.
Accountable role: Technical lead, due Project Gate 3 / Software G2. **Do not start real
frontend implementation work without this being resolved first** — choosing a framework
unilaterally would be making DEC04's call without the named authority, the same category of
thing this project has avoided doing for DEC05/DEC07/DEC08 throughout the backend build.

**DEC08 (Usability sample and performance budgets)** — approved: a 90% unaided task-completion
target *per user group* (not pooled), plus a 20-minute onboarding target. **Not yet selected**:
actual sample sizes, device profiles, network profile, and the numeric API p95 / slow-device
render budgets REQ-043 also depends on. Accountable: UX and technical leads.

**Component boundary (Blueprint §5.1)** — the web interface's authority is explicitly limited:

| Web interface owns | Web interface does NOT own |
| --- | --- |
| Forms, readable summaries, local interaction state (drafts, filters, nav state) | Approval authority, tenant trust, or durable decision acknowledgement |

Concretely: the frontend renders what the backend's preview/decision endpoints already computed
and validated (blockers, permitted outcomes, manifest digests) — it must never itself decide
whether an approval is valid, compute readiness, or fabricate a decision outcome client-side.
Every mutating action the frontend takes must round-trip through the backend's own validation
(already true of every endpoint built in WP03-WP12; the frontend's job is to present that
faithfully, not to duplicate or second-guess it).

## 2. The ten screens (Blueprint §4.1)

Verbatim from the blueprint, with the backend endpoint(s) that already support each one noted
where they exist.

| Screen | Inputs and primary action | States and safeguards | Backend support (built) |
| --- | --- | --- | --- |
| **UI01** Sign in and invitation | Email, credential, MFA; accept invitation after sign-in. | Expired invitation: request another. Wrong organisation: explain and deny. Recovery has a verified path. | `POST /auth/register`, `/auth/login`, `/auth/mfa/enroll`, `/auth/mfa/verify`, `/auth/mfa/recover`, `POST /invitations/accept` (WP03) |
| **UI02** First project | Starter, project name, class and owner; Create project. | Show concise starter explanation. Atomic create; retry cannot create duplicate projects. | `POST /orgs/{tenant_id}/projects` (WP06) — atomic seeding already proven (`test_seeding_failure_leaves_no_project_row`) |
| **UI03** My work | Filter by project and due state; Open task. | Empty: explain no assigned work. Revoked access: remove entry. Do not expose restricted titles. | `GET /orgs/{tenant_id}/my-work` (WP06, enriched WP10 with `reason`/`direct_action`/`project_name`) |
| **UI04** Evidence editor | Status, owner, due date, reference and notes; Save draft or Submit. | Saved/Saving/Not saved. Invalid reference points to field. Concurrent change preserves draft for review. | `PUT /orgs/{tenant_id}/drafts/{key}` for the Save-draft half (WP10); `POST /orgs/{tenant_id}/evidence/{item_id}/revisions` for Submit (WP06) — both optimistic-concurrency, `base_revision` |
| **UI05** Gate readiness | Mandatory items, exclusions, conditions; Review decision. | Explain each blocker and permitted fix. Show reassessment flags and actual reviewed revision. | `POST /orgs/{tenant_id}/projects/{id}/occurrences/{id}/preview` (WP07, enriched WP10 with `blocker_explanations` + `permitted_outcomes`) |
| **UI06** Decision summary | Outcome, conditions, owner and deadline; Confirm decision. | Show exact evidence manifest and permitted next activity. Stale revision requires fresh review. | `POST .../decisions` (Idempotency-Key + `manifest_digest` staleness check, WP07); `GET /orgs/{tenant_id}/decisions/{id}` for retrieval-after-timeout |
| **UI07** History | Occurrence and decision filters; View record or Start correction. | Historical records are read-only. Correction creates superseding record with reason. | `POST /orgs/{tenant_id}/decisions/{id}/superseding` (WP07) — no listing/filter endpoint built yet, only get-by-id |
| **UI08** Template authoring | Guided tracks, gates, classes and rules; Validate then Publish. | Preview applicability. Unknown rules show actionable errors. Published version cannot be edited. | `POST /orgs/{tenant_id}/templates`, `.../import`, `.../fork`, `.../versions/{id}/publish` (WP05) — field-level validation errors already returned |
| **UI09** Export and import | Scope, format and archive; Generate export or Validate import. | Explain queued/ready/expired download states. Import preview warns about unmapped actors. | `POST /orgs/{tenant_id}/exports`, `/imports/validate`, `/imports/{id}/commit` (WP09) — synchronous in this prototype, no queued/expiring state exists yet to reflect |
| **UI10** Membership and account | Invites, roles, MFA and preferences; Save permitted change. | Role escalation checked on server. Removing approval authority invalidates stale attempts. | `POST /orgs/{tenant_id}/invitations`, `GET /orgs/{tenant_id}/access-review` (WP12) — no "remove member" or "change my preferences" endpoint built yet |

**Gaps this table surfaces, not previously tracked as such**: no history-listing/filter endpoint
(UI07 needs more than the single `GET .../decisions/{id}` built so far), no queued/expiring
export-download lifecycle (UI09 assumes async job states the current synchronous export doesn't
have), no membership-removal or account-preferences endpoint (UI10). None of these block backend
work already done; they're real backend gaps a frontend build against UI07/09/10 will hit.

## 3. The five essential journeys (Blueprint §4.2)

**Journey A — Start a project.** Verified user enters an org, chooses a licensed starter, enters
a project name. Service validates class + membership, creates a bound project, seeds evidence —
one transaction. Next page shows the first occurrence and a single next action. Onboarding
includes account/MFA steps where the role requires them.

**Journey B — Supply evidence.** Contributor opens an assigned task from My work, sees an
example, adds a reference. Saving produces a new draft revision only after acknowledgement.
Submit checks the full resulting record. A failing field is explained without discarding valid
input. Reopening restores the server-saved draft within the declared policy.

**Journey C — Make a decision.** Approver opens readiness, resolves/reviews blockers, requests a
decision preview. Summary names the occurrence, evidence revisions, outcome, conditions, and
permitted progression. Confirm submits the preview revision token + idempotency key. A stale
preview returns to review; an unknown network outcome triggers lookup, not blind resubmission.

**Journey D — Correct a record.** Authorised user selects Start correction from a historical
decision. Interface asks for a reason, shows the original. New decision references the original,
follows the same authority/evidence checks. Both records stay visible; current projection points
to the superseding record.

**Journey E — Author a framework.** Administrator starts blank or forks a permitted starter, adds
tracks/gate definitions, assigns class rules and role powers, validates. Preview shows required
and excluded evidence per class. Publication creates an immutable version. Moving a live project
to it requires a separate migration review.

Journeys A, B, C, D map directly onto backend flows already built and tested (WP06/WP07). Journey
E maps onto WP05's template router. None of the five need new backend capability to build a
frontend against — they need the frontend itself, which doesn't exist.

## 4. Interaction language (Blueprint §4.3) — exact wording, not to be improvised per-screen

| Condition | Message | Action |
| --- | --- | --- |
| Missing evidence | "The test report is missing. Add its reference before approval." | Open the evidence item. |
| Concurrent edit | "This evidence changed while you were reviewing it. Review the latest version." | Keep draft; refresh the comparison. |
| Unconfirmed save | "Your changes have not been saved. Check your connection and try again." | Retry draft save without claiming success. |
| Unknown decision outcome | "We are checking whether your decision was recorded." | Retrieve by idempotency key. |
| Expired exception | "This exception expired. New approval requires valid evidence or an authorised exception." | Open the exception record. |
| No applicable evidence | "No evidence items apply under the approved rules. A gate decision is still required." | Open the decision review. |

The backend already returns the structured data each of these needs (e.g.
`blocker_explanations`/`permitted_outcomes` from `preview`, 409 on stale `manifest_digest` or
draft `base_revision`) — the frontend's job is to surface it in this exact phrasing, not invent
its own wording per screen.

## 5. Navigation and design constraints (Blueprint §4.1 prose)

- Persistent organisation selector, My work, Projects, labelled account menu. Template
  administration visible only to authorised users.
- Project page: Overview, Evidence, Reviews, History tabs. Export available from project or org
  record.
- Keep the active organisation visible while editing or approving.
- Phone layout order: title/context → next action → blockers → supporting details.
- Navigation labels stay stable across different tenant templates (don't let a tenant's own
  framework vocabulary leak into the platform chrome).
- One descriptive heading and one obvious primary action per screen.
- Text labels with icons — never colour alone for status.
- Focus moves to validation summaries on error, returns to the originating control when a dialog
  closes.
- No drag-and-drop as the *sole* interaction for anything.
- Zoom/reflow support, labelled fields, keyboard operation, visible focus, screen-reader
  announcements for save/submit outcomes.

## 6. Usability, accessibility and release-blocking requirements

| Req | Requirement | Verification | WP |
| --- | --- | --- | --- |
| REQ-032 | Role-specific My work: project, reason, deadline, state, direct action | Each persona finds their assigned action; unrelated assignments stay hidden | WP10 (backend done) |
| REQ-033 | Short guided forms, field examples, clear errors, reversible navigation without losing valid input | Back navigation and invalid fields preserve all valid responses | WP10 — **frontend-only, not built** |
| REQ-034 | Save/resume drafts with truthful Saving/Saved/Not-saved states | Interrupt a save, reload within policy; saved data returns, unsaved data not misrepresented | WP10 (backend save/resume primitive done; truthful *state display* is frontend) |
| REQ-035 | Distinguish pending from confirmed approvals; retrieve outcome after timeout; handle concurrent edits explicitly | Drop the response after commit; recovery shows the existing decision, not a duplicate | WP07 (backend done) — no live "Pending" status exists (DEC05-gated) |
| REQ-036 | Explain blockers in plain language, link to corrective action, no restricted info exposed | Newcomer identifies the missing item and reaches the correction without external docs | WP10 (backend done: `blocker_explanations`) |
| REQ-037 | Deliberate approval confirmation summary: evidence, conditions, permitted progression | User can explain the action permitted before submitting; opening a page/email never approves anything | WP10 (backend done: `permitted_outcomes`) |
| REQ-038 | Invitation landing, accessible MFA and recovery as part of the essential journey | Invited user reaches the intended project after sign-in, can recover without a control bypass | WP03 (backend done) |
| REQ-039 | Unambiguous dates, visible time zones, translation structure, consistent tenant terminology | UTC storage and user-zone display agree across DST/boundary cases; labels retain decision meanings | WP10 — UTC storage done; **display/i18n is frontend-only, not built** |
| REQ-040 | WCAG 2.2 AA, no open A/AA failure; all mandatory tasks work on phones + assistive tech | Automated checks + keyboard/screen-reader/focus/contrast/zoom review pass essential journeys | WP11 — **frontend-only, not built** |
| REQ-041 | 20-minute unaided onboarding; inclusive per-group testing, 90% completion (DEC08 baselines the sample) | Record sample sizes, assistance, device profiles, per-group result — no concealing a failing group in a pooled average | WP11 — needs DEC08 + a real frontend + real participants |
| REQ-042 | Block release for critical approval misunderstanding until corrected and retested | Observed misunderstanding logged as a release blocker with repeat-test evidence after the fix | WP11 |

**REQ-042 is worth flagging on its own**: "critical misunderstanding of what approval permits is
a release blocker" — this is a hard gate, not a nice-to-have. The confirmation-summary content
this document's §4 and §6 (REQ-037) describe exists specifically to prevent that misunderstanding
class; the frontend's rendering of it is where this requirement actually gets satisfied or
missed.

## 7. Usability study protocol (Blueprint §4.4)

- Run formative sessions **before** selecting the final frontend framework, not after.
- Recruit beginners, contributors, client approvers, administrators — including disabled users
  and older-phone users.
- Use synthetic fixtures (already exist: `fixtures/synthetic/`). Record task completion, time,
  assistance given, mistaken approvals, recovery failures.
- DEC08 must baseline sample sizes, device profiles, and the 90% threshold per group before this
  can run for real.
- Report keyboard/screen-reader journey results **separately** from automated accessibility
  checks — a passing automated scan is not evidence of a passing manual journey.
- Translation languages follow market discovery (DEC02); date/timezone clarity is mandatory
  immediately, not deferred.
- Re-test corrected journeys with users who did not learn the earlier (broken) interface — a
  participant who already learned a workaround isn't a valid test of whether the fix works for a
  newcomer.

## 8. What this means for sequencing

1. **DEC04 must be resolved first** (framework/session-mechanism selection, Technical lead
   authority) — not something to default into while building.
2. Once resolved, the ten screens (§2) and five journeys (§3) can be built directly against the
   backend surface that already exists — most of the hard validation/state logic (blockers,
   permitted outcomes, staleness, idempotency, draft concurrency) is already server-side and
   tested; the frontend's job per the component boundary (§1) is presentation and local state,
   not re-deriving those decisions.
3. The backend gaps surfaced in §2's table (history listing/filter, export job lifecycle states,
   membership removal, account preferences) will need small backend additions alongside the
   frontend work that first needs them — not a blocking prerequisite, but worth expecting.
4. REQ-033/039(display)/040/041/042 cannot be satisfied by backend work at all — they only
   become buildable once a frontend exists, and REQ-041's usability testing additionally needs
   DEC08 resolved first.
