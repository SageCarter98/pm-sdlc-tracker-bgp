<!--
Provenance note (added 2026-09-20, WP13): this document's body is the
owner-approved FE-APR-001 v1.1 frontend requirements catalogue as it arrived
in stitch_buildgovernanceplatform_webapp.zip (delivered alongside a Stitch
UI-mockup design package for the same ten screens). It is reproduced
verbatim below -- no wording, numbering or approval content changed.

This document's own Section 1 says it did not audit the current repository
and that DEC01-DEC12 "may have later resolutions -- use the current decision
record". Cross-checking that against this project's real state as of WP13:
DEC04 (frontend framework/session architecture) IS now resolved -- WP11
(2026-09-20, commit 06662fe) built a server-rendered FastAPI+Jinja2 frontend,
same-origin, reusing the existing signed-cookie session, at the delivery
lead's explicit direction. DEC07 (rule vocabulary/third framework) and DEC06
(retention/disposal policy) remain open per TRACKER.md, which is why UI08
(template authoring) and parts of UI09/UI10 stay API-only in WP13 -- see
TRACKER.md's WP13 entry.

Relationship to the existing docs/blueprint/frontend_requirements.md: that
file is a plain reference extract of the Blueprint v0.2 pack ("not a new
approval"). This FE-APR-001 document is a separate, later, owner-approved
supplement -- it "supplements, rather than replaces" the blueprint's own
REQ/UI/TST/AC/WP identifiers (its own Section 1). Where the two describe the
same screen, this is the more current source; where they conflict, resolve
it explicitly rather than picking one silently (this project's standing
rule -- see the root CLAUDE.md governance section).
-->

# Build Governance Platform Complete Frontend Requirements List

**Version:** 1.1
**Date:** 20 September 2026
**Project:** PM/SDLC Tracker — Build Governance Platform
**Document status:** Owner approved frontend requirements baseline for development
**Approval record:** FE-APR-001 — personal review and approval recorded on 20 September 2026
**Controlling baseline:** Development Blueprint v0.2 Approved, implementing Project Directive v1.2
**Companion:** BGP_Frontend_Blueprint_Assessment_v1.0.md

## 1 Purpose and completeness boundary

This document supplies the consolidated frontend requirements list requested for the Build Governance Platform. It covers the ten approved screens, five essential journeys, access boundaries, interface states, API interactions, accessibility, mobile use, performance, optional capabilities and verification evidence. It is a requirements catalogue, not source code, finished visual artwork or a certificate that implementation is complete.

The approved Development Blueprint v0.2 was directly read for this document, including its requirement catalogue, UI01–UI10, journeys, API contracts and approval record APR-001. This resolves the earlier assessment's inability to verify exact screen contents. The supplied local directive copy still identifies itself as v1.0 Draft despite the attachment listing naming v1.2 Approved; it is not substituted for the controlling baseline.

"Complete" means coverage of the frontend scope established by the reviewed blueprint, with implementation refinements and remaining decisions explicitly identified. It does not mean unspecified technology selections, business policies or numeric budgets have been invented or approved. Current repository implementation and later decision closures were not audited for this document.

## 2 Requirement notation

Each row gives a stable frontend identifier, source/status, required behaviour and an observable acceptance check. All checks are planned and unverified in this document.

- **B — Baseline:** directly restates or decomposes the approved blueprint. Mandatory unless explicitly conditional.
- **D — Derived and adopted:** implementation detail needed to make baseline behaviour precise, now owner approved under FE-APR-001 and mandatory within its stated scope. The D label preserves its origin; it no longer means draft or awaiting owner adoption.
- **C — Conditional:** required only when its optional capability is enabled; enabling it requires the relevant scope decision.
- **Decision dependency:** an unresolved value or choice in the reviewed baseline, not permission to guess. Check the latest decision register for subsequent closure.

References such as R017 mean blueprint REQ-017; S4.1 means blueprint Section 4.1. A baseline TST identifier has the same numeric suffix as its REQ identifier. Frontend checks below supplement, not replace, those system tests.

## 3 Roles and authority boundaries

| Role | Frontend responsibilities | Authority restriction |
| --- | --- | --- |
| Contributor | Find assigned work, prepare evidence, save drafts, respond to corrections | Evidence authorship alone never grants approval authority |
| Approver | Review readiness, evidence and conditions; deliberately submit permitted decisions | Requires current membership, project scope, role, MFA and separation checks |
| Sponsor | View readiness, conditions and non-member administrator access events | Approval powers exist only when explicitly assigned |
| Assurance reviewer | Inspect in-scope evidence, decisions and exports | Read-only unless separately granted another role |
| Tenant administrator | Manage permitted membership and template functions | Cannot change history; access outside project membership is logged |
| Platform operator | Operational access only under the approved policy | No routine tenant-evidence access or decision-edit authority |

These are responsibilities, not hardcoded tenant role names. Template-defined roles map to server-enforced capabilities. Every operation must be checked by the server; client-side visibility is only a usability measure. An account holding multiple roles must still satisfy separation rules for the specific decision.

## 4 Approved screen inventory

Supporting registration, recovery, project listing and settings views may be routes, steps or dialogs within this inventory. They do not silently rename UI01–UI10 or expand the product into a general task-management system.

| ID and screen | Inputs or displayed information | Primary actions | Required states and controls |
| --- | --- | --- | --- |
| UI01 Sign in and invitation | Email, credential, MFA, invitation context | Sign in; accept invitation after authentication; verified recovery | Invalid credentials, expired invitation, wrong organisation, denied membership, MFA setup/recovery |
| UI02 First project | Starter, project name, class, owner and explicit members | Create project | Starter explanation, validation, creation pending, atomic success/failure, safe retry |
| UI03 My work | Project/due filters, assigned task, reason, deadline, state | Open task | Loading, no assignments, filtered-empty result, revoked access, paginated results |
| UI04 Evidence editor | Status, owner, due/completion dates, reference, notes and revisions | Save draft; submit | Saving/Saved/Not saved, invalid fields, concurrent edit, read-only history |
| UI05 Gate readiness | Occurrence, mandatory items, exclusions, conditions, blockers and reviewed revision | Review decision | Blocked, ready for review, no applicable evidence, reassessment needed, access denied |
| UI06 Decision summary | Outcome, evidence manifest, conditions, owner, deadline, permitted activities | Confirm decision | Preview loading, invalid conditions, stale preview, pending, recorded, unknown outcome, integrity/durability block |
| UI07 History | Occurrence/decision filters, immutable records and supersession links | View record; start correction | Loading, empty, restricted, historical, superseded/current distinction |
| UI08 Template authoring | Tracks, gates, classes, roles, statuses, decisions and supported rules | Validate; preview; publish; fork/import/export | Draft, invalid rule, valid preview, publishing, immutable published version, migration review |
| UI09 Export and import | Scope, format, archive, validation/mapping and reconciliation reports | Generate export; validate import; commit authorised import | Queued, processing, ready, expired, failed, invalid archive, unmapped actors, reconciliation |
| UI10 Membership and account | Invitations, roles, MFA, preferences and membership state | Save permitted change | Pending invitation, validation, permission denial, revoked authority, recovery, session expiry |

## 5 Navigation and shared interface requirements

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-001 | B S4.1 | Provide persistent organisation context, My work, Projects and a labelled account menu | All authenticated screens expose the active organisation and permitted navigation |
| FE-002 | B S4.1 | Provide project Overview, Evidence, Reviews and History, with Export from project or organisation records | Each destination opens in the correct organisation/project context |
| FE-003 | B S4.1 | Show template administration only to authorised users | Unauthorised users see no actionable administration entry; direct routes remain server protected |
| FE-004 | B S4.1 | Give every screen a descriptive heading and an obvious primary action | A reviewer can identify purpose and next action without interpreting icons alone |
| FE-005 | B R036, S4.1 | Prioritise current outstanding work and use progressive disclosure | Initial gate view shows blockers and next action before secondary detail |
| FE-006 | B R039, S4.1 | Keep navigation labels stable while respecting tenant terminology in domain content | Different templates do not change navigation meaning or mislabel decisions |
| FE-007 | D R003, R008 | On organisation change, clear prior scoped state and ignore late responses from the old context | Switching while a request is in flight cannot display the previous tenant's results |
| FE-008 | D R038 | Preserve a safe intended destination through authentication; reject external or unauthorised redirects | Invitation/deep link reaches only an authorised local destination after sign-in |
| FE-009 | D R033 | Handle refresh, back/forward navigation and invalid routes predictably | Valid routes restore context; invalid routes explain recovery without disclosing restricted titles |

## 6 Identity and membership

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-010 | B R001 | Support organisation registration, user verification and explicit membership before project access | Unverified or unrelated accounts cannot reach protected project data |
| FE-011 | B R002, R038 | Provide accessible TOTP enrolment, challenge and verified recovery | Approval cannot proceed without required MFA; recovery requires checks and re-enrolment |
| FE-012 | B R038, UI01 | Accept invitations only after authentication and verification of intended organisation | Expired or wrong-organisation invitation explains the problem and offers a permitted recovery path |
| FE-013 | B R003 | Request tenant switching through authenticated server membership checks | Altering client tenant values grants no access; expired membership is rejected |
| FE-014 | B R004, UI10 | Render reads, edits, invitations and role changes according to current scoped capabilities | Contributor, approver and assurance scenarios expose only permitted operations |
| FE-015 | B R005 | Surface administrator access outside project membership to the sponsor | Sponsor can inspect actor, project and server timestamp for the access event |
| FE-016 | B R006 | Explain separation-of-duty restrictions and collect allowed compensating review details | Self-only approval is refused unless the server validates a scoped override and independent reviewer |
| FE-017 | B R024 | Treat removed membership or approval authority as invalidating stale actions | Revocation during review prevents submission and yields a clear access-change message |
| FE-018 | D R002, R034 | Define logout, expiry, recovery-token handling and sensitive-data cleanup under the session/shared-device policy | After logout, another user cannot recover protected state through back navigation or retained drafts |
| FE-019 | D R044 | Use safe authentication errors and retry guidance without confirming unrelated accounts or tenants | Enumeration scenarios produce no protected account or tenant details |
| FE-020 | B R039, UI10 | Allow permitted account preferences, including display timezone | Saved preference is applied consistently without changing authoritative UTC timestamps |

## 7 Project creation and assigned work

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-021 | B R014, R015 | Explain available licensed starters; use the neutral fallback when clearance is absent | Unlicensed KenAddme content is not offered as an approved starter |
| FE-022 | B R015, UI02 | Capture name, template version, class, owner and explicit members, with server validation | Created project has the reviewed binding and applicable seeded evidence |
| FE-023 | B R015, S5.3 | Treat project creation as atomic and idempotent | Seeding failure creates no partial project; retry creates no duplicate |
| FE-024 | B S4.2 Journey A | After creation, show the first occurrence and a single clear next action | New user reaches useful work without optional configuration |
| FE-025 | B R032, UI03 | Show scoped assignments with project, reason, deadline, state and direct action | Each persona finds their own required action; restricted titles remain hidden |
| FE-026 | B UI03, S5.3 | Provide project/due-state filters and bounded pagination for My work | Filters match returned scope; empty assignments and no filter matches are understandable |
| FE-027 | B R016 | Represent routine and triggered reviews as distinct occurrences | Two routine reviews and a triggered review retain separate due dates, evidence and decisions |
| FE-028 | D R015, R017 | Validate project/evidence field lengths, formats and permitted choices against the API schema | Empty required values, invalid classes and over-limit input produce field-level errors; no invented client-only limits |

## 8 Evidence, drafts and revision handling

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-029 | B R017, UI04 | Edit evidence status, owner, due/completion dates, reference and notes as permitted | Saved values match the resulting server record and attribution |
| FE-030 | B R017 | Preserve immutable revisions and expose revision history | Prior values, actor and time remain available after an edit |
| FE-031 | B R018 | Validate the entire resulting record when marking or retaining Complete | Clearing a required reference cannot leave an invalid item Complete |
| FE-032 | B R019 | Display exact local revision and available source version/hash; label mutable references | An unversioned URL is not represented as proof of unchanged external content |
| FE-033 | B R033 | Use short guided forms, examples and clear validation without discarding valid input | Invalid submission and back navigation preserve valid entered fields |
| FE-034 | B R034 | Distinguish Saving, Saved and Not saved truthfully | Saved appears only after server acknowledgement; interrupted requests do not claim success |
| FE-035 | B R034 | Resume server-saved drafts within the declared retention/shared-device boundary | Reopening restores acknowledged draft data only to an authorised user |
| FE-036 | B R035, UI04 | On concurrent change, retain the draft and require review of the newer revision | Stale submission does not silently overwrite another user's edit |
| FE-037 | D R033, R034 | Warn before navigation discards unacknowledged edits, consistent with security cleanup | User can remain and retry or deliberately discard; no promise of recovery beyond policy |
| FE-038 | D R019, R044 | Treat evidence URLs and notes as untrusted content | Unsafe schemes and executable markup cannot run in the interface; no credentials are embedded in links |
| FE-039 | B S5.2 | Keep draft saving distinct from submitted evidence and governance decisions | A saved draft alone does not satisfy an evidence requirement or create an approval |

## 9 Readiness, exceptions and decision workflow

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-040 | B R020, UI05 | Show required evidence, applicable exclusions and their server-evaluated reasons | A typed status alone cannot remove an item from readiness checks |
| FE-041 | B R020 | Validate exception scope, authority, safeguards, owner and expiry through the approved workflow | Expired, revoked, unrelated or self-asserted exceptions do not satisfy requirements |
| FE-042 | B R021 | Show reassessment when evidence changes or an exception expires | Current readiness changes while the historical decision remains intact |
| FE-043 | B S2.2 | Never treat a completion percentage as gate approval | A fully complete evidence list still requires an explicit authorised decision |
| FE-044 | B S2.2, S4.3 | Display No applicable evidence for a zero denominator | The interface does not display 100% or imply automatic approval |
| FE-045 | B R036 | Explain blockers in plain language with permitted corrective links | User can identify the missing requirement without exposure of restricted details |
| FE-046 | B R022 | Distinguish Approve, conditional approval, Hold, Redirect and Terminate according to template meanings | Hold/Redirect/Terminate are not presented as permission to progress |
| FE-047 | B R022 | For allowed conditional approval, require conditions, owner, deadline and activity limits | Missing deadline or unresolved critical blocker prevents confirmation |
| FE-048 | B R037, UI06 | Display exact occurrence, reviewed evidence manifest, outcome, conditions and permitted progression before confirmation | User can explain what the decision authorises; opening a page/email never records it |
| FE-049 | B R024 | Submit the reviewed revision and manifest digest, not a reconstructed optimistic snapshot | Evidence or authority changes cause stale review rejection and a fresh preview |
| FE-050 | B R024, R035 | Use a scoped idempotency key and retrieve an unknown outcome before any new submission | Lost response after commit resolves to the existing decision, not a duplicate |
| FE-051 | B R023, R028 | Show Recorded only after the required durable acknowledgement | Success contains authoritative decision ID, occurrence, timestamp and outcome; pending is not approved |
| FE-052 | B R027 | Show an actionable integrity/durability restriction without bypass controls | Affected acknowledgement is blocked; reload or client state changes cannot override it |
| FE-053 | B R023 | Display server-attributed actor, time, authority and version bindings | User-entered names/times cannot impersonate the authoritative decision record |
| FE-054 | D R024 | Prevent repeat clicks while retaining safe outcome recovery | Rapid clicks, refresh and timeout do not create multiple logical decisions |

## 10 History and corrections

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-055 | B R023, R025, UI07 | Provide immutable history with occurrence and decision filters | Original records remain readable and distinct across recurring reviews |
| FE-056 | B R025 | Permit corrections only by a new superseding decision with reason and original link | No role sees a supported edit/delete action for a recorded decision |
| FE-057 | B S4.2 Journey D | Run correction through the same preview, authority, MFA, separation and evidence checks | Authorised correction preserves both records and shows the current superseding projection |
| FE-058 | B R017, R026 | Expose permitted before/after audit information without claiming integrity from display alone | Visible history matches server records; verification status is not inferred from a local hash |

## 11 Template authoring and migration

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-059 | B R010, R012 | Support blank creation, permitted starter forks and guided editing without requiring JSON knowledge | Administrator builds and runs a template through the guided interface |
| FE-060 | B R010, UI08 | Configure tracks, gates, classes, roles, statuses, decisions and applicability schemes | Three approved framework fixtures work without hardcoded tenant rules |
| FE-061 | B R013, S5.5 | Limit rules to approved declarative operators and vocabulary | Unknown keys, cycles, invalid references, executable code and invariant overrides are rejected |
| FE-062 | B R012 | Support schema-validated template JSON import/export as an advanced path | Invalid import identifies the failing field and does not partially publish |
| FE-063 | B UI08, S4.2 | Preview required and excluded evidence for each class before publication | Preview reflects server rule evaluation, including unresolved errors |
| FE-064 | B R011 | Publish immutable versions, preserving existing project bindings | Publishing v2 leaves v1 projects unchanged; changes require a new draft/version |
| FE-065 | B R011, S5.3 | Make project migration a separate impact review and authorised action | Migration records old/new version and approver without rewriting past decision bindings |
| FE-066 | B R013, S2.2 | Never offer configuration that disables attribution, audit, immutable decisions, export or security | Template edits cannot remove platform invariants |

## 12 Export, import and data policy

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-067 | B R030, UI09 | Allow authorised complete open-format export with explicit scope and format version | Export includes required relationships, revisions and history rather than only the visible page |
| FE-068 | B UI09 | Show queued, processing, ready, failed and expired export states | Refresh restores job state; expired download offers an authorised regeneration path |
| FE-069 | B R031 | Keep own-data export, audit history and MFA accessible on every tier | Billing read-only mode blocks ordinary writes but preserves these authorised functions |
| FE-070 | B R030, S5.6 | Validate import in quarantine and show schema, provenance, mapping and reconciliation results | Invalid archive cannot be committed; checks cover paths, limits, hashes and tenant bindings |
| FE-071 | B R030, DEC12 | Explain unmapped actors and preserve historical provenance without activating credentials | Historical actors receive no live access; missing legacy attribution is labelled, not invented |
| FE-072 | B S5.3, S5.6 | Require explicit authorised import commit and report reconciliation | Imported records are not presented as ready before counts, IDs, links and digests reconcile |
| FE-073 | B R048 | Respect retention, legal hold and authorised disposal policies in relevant controls | Held data cannot be disposed of; attribution remains for the required period; decision history is not casually deleted |
| FE-074 | D R048 | Explain irreversible disposal scope and require deliberate confirmation only where policy permits disposal | User sees affected scope and legal-hold restrictions; no enabled control precedes DEC06 resolution |

## 13 Accessibility, responsive design and content

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-075 | B R040 | Meet the project's WCAG 2.2 AA target with no open Level A/AA failure at release | Automated and human reviews cover all tenant-facing screens and essential journeys |
| FE-076 | B R040, S4.1 | Support every mandatory action on a phone | Registration, evidence, decisions, correction, templates and export/import complete on approved phone profiles |
| FE-077 | B S4.1 | On phones, order content as title/context, next action, blockers, then supporting details | Responsive views preserve meaning and actions without obscured controls |
| FE-078 | B S4.1 | Provide labelled fields, keyboard operation and visible focus; do not depend on drag-and-drop | Keyboard-only users complete all mandatory tasks and equivalent reorder actions |
| FE-079 | B S4.1 | Move focus to validation summaries and return it to the originating control after dialogs | Error/dialog tests show predictable focus and no keyboard traps |
| FE-080 | B S4.1 | Announce save and submission results to assistive technology and pair status colour with text | Screen-reader users distinguish Saving, Not saved, Pending and Recorded |
| FE-081 | B R040 | Support contrast, zoom and reflow review | Approved zoom and viewport tests preserve readable content and reachable actions |
| FE-082 | B R039 | Use unambiguous dates, visible timezones and translation-ready strings | UTC and displayed times agree across date boundaries; untranslated structural strings are identifiable |
| FE-083 | B R039, S4.1 | Preserve tenant terminology without changing the meaning of governance outcomes | Renamed labels still explain what approval, hold and conditions permit |
| FE-084 | D R040 | Define accessible component variants for buttons, fields, tables, dialogs, notices and pagination | Reusable components pass documented keyboard, focus, label and state checks |
| FE-085 | D R033, R040 | Document visual tokens and responsive rules rather than relying on individual developer choices | Typography, spacing, colours and component states are consistent across the ten screens |
| FE-086 | B R041, R042 | Verify 90% unaided completion separately per user group and twenty-minute onboarding; block critical approval misunderstanding | Results record group, task, time, assistance and failures; corrected critical misunderstandings are retested |

## 14 Integration, security and reliability

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-087 | B S5.1, DEC04 | Use the approved same-origin API boundary; frontend owns presentation, not authority or durability | No client-only rule grants membership, approval or durable success |
| FE-088 | B S5.3 | Map 401, 403, concealed 404, 409, 422 and 503 to safe, actionable states | Invalid session, denial, missing record, conflict, field error and unavailable durable path are distinguishable without leakage |
| FE-089 | D R008, R044 | Scope caches and requests by authenticated context; discard stale responses and protected data after access loss | Cross-tenant and revocation tests show no stale titles, records or downloads |
| FE-090 | D R044, R045 | Keep secrets out of bundles, logs, browser URLs and error reports; implement session/CSRF handling according to DEC04 | Built assets and telemetry contain no secrets; mutation protection matches the approved authentication design |
| FE-091 | D R034, R035 | Treat network failure as uncertainty, not success; offer bounded recovery and preserve permitted input | Slow/offline tests never mark unsaved drafts Saved or unconfirmed decisions Recorded |
| FE-092 | D R044 | Do not queue offline approvals or automatically replay authority-changing operations | Reconnection requires fresh verification of decision outcome and current permissions |
| FE-093 | B R043, DEC08 | Measure render/page-weight and API budgets against approved traffic, device and network profiles | Numeric thresholds are recorded and enforced in CI; no unmeasured performance claim is made |
| FE-094 | B S5.7 | Report draft-save failures, pending-decision age and interface errors with minimal personal data | Diagnostics support investigation without capturing credentials or evidence content unnecessarily |
| FE-095 | D R049, R058 | Handle frontend/API version incompatibility safely during deployments | Unsupported payload/version yields a controlled recovery path, not silent data loss or incorrect approval |
| FE-096 | B R049 | Use controlled source, pinned dependencies, code review and reproducible frontend checks | Clean checkout builds and runs documented checks with the recorded toolchain |

## 15 Conditional capabilities

These do not displace mandatory journeys or assurance. Controls become mandatory when the corresponding optional capability is enabled.

| ID | Basis | Requirement | Acceptance check |
| --- | --- | --- | --- |
| FE-097 | C R053 | Show upload limits, classification restrictions, progress, quarantine and scan outcomes | Disabled or disallowed upload is blocked; unscanned/malicious files cannot be downloaded |
| FE-098 | C R053 | Show immutable attachment versions and use authorised short-lived downloads | Replacing a file preserves prior versions within policy; expired links cannot bypass authorisation |
| FE-099 | C R054 | Provide grouped routine reminders, permission-filtered task links and completion suppression | Completed tasks generate no routine reminder; revoked users receive no protected content |
| FE-100 | C R055 | Clearly label resettable fictional practice projects and isolate their outcomes | Practice reset affects no real record; practice decisions appear in no live report/export |
| FE-101 | C R056 | Explain tiers, limits, grace period and read-only downgrade before paid signup | Billing failure never directly deletes data and preserves export, history and MFA |
| FE-102 | C R056 | Use the selected compliant payment flow without platform handling of card data | Platform interface/API stores only allowed payment references and subscription status |

Risks/change registers, saved report views, printable gate packs and per-item comments are not promoted into mandatory scope by this list. Their inclusion and detailed fields require an explicit project scope decision. Exception handling needed for valid decisions is already mandatory above, irrespective of an optional general-purpose register.

## 16 Approved API interaction map

These route shapes are copied from Blueprint v0.2 Section 5.3; they are contracts, not a claim that endpoints exist in the current repository. The payload summaries are not complete schemas.

| Frontend use | Approved route | Essential client behaviour |
| --- | --- | --- |
| Create project | `POST /api/projects` | Send name, template_version_id, class_id; handle atomic/idempotent creation |
| My work | `GET /api/my-work` | Send cursor/filter and display only returned permitted tasks |
| Create review occurrence | `POST /api/projects/{id}/occurrences` | Send gate_definition_id, trigger, due_at; accept server sequence |
| Submit evidence revision | `POST /api/evidence/{id}/revisions` | Include base_revision and changed values; handle stale conflict |
| Save draft | `PUT /api/drafts/{id}` | Include base_revision and supported form data; Saved only after commit acknowledgement |
| Preview decision | `POST /api/occurrences/{id}/preview` | Send outcome/conditions; retain returned readiness revision and manifest digest |
| Confirm decision | `POST /api/occurrences/{id}/decisions` | Send reviewed revision/digest/conditions with Idempotency-Key |
| Recover unknown outcome | `GET /api/decision-requests/{key}` | Handle recorded, pending and absent without blind duplicate submission |
| Correct decision | `POST /api/decisions/{id}/superseding` | Send reason, new preview and outcome; preserve original |
| Exception workflow | `POST /api/exceptions` | Send scope, safeguards, owner, expiry and approving workflow; never self-assert authority |
| Publish template | `POST /api/templates/{id}/publish` | Send draft revision and validation receipt |
| Migrate project template | `POST /api/projects/{id}/migrations` | Send new version, impact and authorisation |
| Export | `POST /api/exports` | Send scope/format version; track job state |
| Validate import | `POST /api/imports/validate` | Upload archive for validation and mapping report |
| Commit import | `POST /api/imports/{id}/commit` | Send validated revision and approved mappings |

Contract gaps to resolve before affected integration: auth/MFA/recovery routes, membership CRUD, project/detail/list reads, evidence/history reads, template draft editing/validation, job polling/downloads, preferences, attachment and billing interfaces. Their exact route names are not specified here because the reviewed API table does not supply them.

Also reconcile owner/member assignment with the project-create contract, which lists only name/template/class; specify how the proposed decision outcome is bound to a preview because the decision payload summary omits it; define draft creation/listing and lookup-after-reload semantics. Do not silently add fields or change the approved routes without contract review.

*WP13 note: the actual repository routes differ from this table (which is copied from the blueprint document, not the code) — e.g. project creation is `POST /orgs/{tenant_id}/projects`, not `POST /api/projects`. See `app/routers/*.py` for the real, implemented contract.*

## 17 Required state behaviour

| Situation | Display and recovery | Forbidden behaviour |
| --- | --- | --- |
| Initial loading | Named loading state and retained safe context | Showing stale tenant content or misleading zeros |
| Empty result | Explain no assignments, no matches or no records; offer permitted next action | Presenting emptiness as a system failure |
| Invalid input | Field errors and focusable summary; retain valid input | Clearing the form or claiming success |
| Draft save fails | Not saved; safe retry under draft policy | Saved without acknowledgement |
| Concurrent edit | Explain newer revision; retain draft for comparison | Silent overwrite or automatic merge of approval-critical values |
| Stale decision preview | Require fresh review of changed evidence/authority | Reusing the old confirmation as consent to new evidence |
| Unknown decision outcome | Explain checking; retrieve by request key | Blindly generating a new decision request |
| Decision pending | Show pending/reconciliation status | Calling it recorded or approved |
| Expired exception | Explain invalidity and permitted corrective path | Continuing to count it as satisfied |
| Session/access loss | Safe authentication or denial flow with scoped cleanup | Showing protected cached content or bypassing MFA |
| Integrity/durability unavailable | Explain temporary block and support/retry path | Optimistic success or client override |
| Billing read-only | Explain limits and retain authorised export/history/security | Deleting records or paywalling protected functions |

## 18 Decisions and design deliverables still requiring confirmation

The following were unresolved or partly decided in Blueprint v0.2. They may have later resolutions; use the current decision record rather than assume they remain open today.

| Decision | Frontend dependency | Required recorded output |
| --- | --- | --- |
| DEC01 | Responsible delivery and independent review | Named people accepting the relevant roles |
| DEC02 | Signup regions and privacy content | Geography, hosting/residency policy and approved notices |
| DEC03 | Starter catalogue | Licensing clearance or neutral starter selection |
| DEC04 | Framework, sessions and build | Framework, session/CSRF mechanism, pinned versions and supported browser matrix |
| DEC05 | Decision success and pending states | Selected durability mechanism, supported failure envelope and recovery semantics |
| DEC06 | Draft/data persistence and disposal UI | Retention periods, shared-device policy, legal hold and decision-record policy |
| DEC07 | Guided rules editor | Vocabulary, bounds and three approved framework fixtures |
| DEC08 | Usability and performance acceptance | Sample sizes, devices, networks, numeric budgets and measurement methods |
| DEC09 | Delivery commitment | Staffing, estimates, dates and capacity; not supplied by this list |
| DEC10 | Optional paid interface | Processor, limits, pricing, grace and contracted deletion policy |
| DEC11 | Operator controls | Break-glass scope, authorisation, tenant visibility and custody |
| DEC12 | Real-data import | Per-import authorisation, provenance mapping and reconciliation evidence |

Implementation design deliverables: reviewed layouts for UI01–UI10 and phone variants; reusable component/state catalogue; complete API schemas and error envelope; field constraints; route/permission matrix; accessibility test matrix; translation language decision; and traceability ledger. This document specifies their required coverage but does not pretend finished artwork or unresolved numeric values already exist.

*WP13 note: DEC04 is now resolved (WP11, 2026-09-20) — see the provenance note at the top of this document. DEC01–DEC03, DEC05–DEC12 remain open per TRACKER.md as of this writing.*

## 19 Verification and handover checklist

| Test group | Required scenarios | Linked frontend requirements |
| --- | --- | --- |
| Journey A | Register/verify, MFA where required, choose starter, create project, first occurrence; duplicate retry and seeding failure | FE-010–028 |
| Journey B | Assigned evidence, valid reference, draft interruption/resume, required reference removal and concurrent edit | FE-025–039 |
| Journey C | Blocked, allowed and conditional decisions; invalid exception; self-only approval; authority revocation; stale preview; response lost after commit | FE-040–054 |
| Journey D | Superseding correction, reason, fresh checks and preserved history | FE-055–058 |
| Journey E | Blank/fork authoring, three framework fixtures, invalid rules, publication and explicit migration | FE-059–066 |
| Data portability | Export during billing restriction; invalid archives; actor mapping; round-trip reconciliation | FE-067–074 |
| Inclusive use | Beginners, contributors, client approvers and administrators; disabled and older-phone users; keyboard and screen-reader tests | FE-075–086 |
| Isolation and recovery | Two fictional tenants; manipulated identifiers; switch during request; logout/back navigation; network failure and pending outcomes | FE-007–020, FE-087–096 |
| Optional scope | Upload quarantine/versioning, reminder suppression, practice reset and billing downgrade when enabled | FE-097–102 |

For each FE row, maintain implementation location, responsible person or explicit vacancy, linked baseline requirement, test ID, result, evidence reference, tested source revision/environment and reviewer. An empty evidence cell means unverified, not passed. A single UI test cannot prove server isolation, persistence, backup recovery or decision durability.

Release evidence must include the project-mandated independent assurance, accessibility/usability results, security testing, migration/rollback, monitoring and operational handover under REQ-044–052 and REQ-057–058. These are shared system obligations; they are not satisfied by a frontend checklist alone. Production requires the named release authority. FE-APR-001 records document and requirement approval only; it issues no test pass or production release approval.

## 20 Explicit exclusions

The first release is not a scheduler, resource planner, issue tracker or full document-management system. Native mobile applications, federated sign-on, repository/issue-tracker integrations and AI-generated evidence or assessments remain outside first-release scope. Outbound webhooks and other future/optional features require separate scope and interface decisions. Translation-ready structure does not commit to particular languages. Backup administration is not added as a new tenant screen merely because system recovery is mandatory.

## 21 Source and revision record

Primary source directly reviewed: Build_Governance_Platform_Development_Blueprint_v0.2_Approved.pdf, dated 15 September 2026, 24 pages, owner approval APR-001. Relevant coverage: Section 2 roles/scope; Section 3 REQ-001–058; Section 4 UI01–UI10 and journeys; Section 5 architecture/API/data contracts; Section 6 work packages/testing; Section 7 decisions; Section 9 approval boundaries.

Supplementary source: supplied 03-Build_Governance_Platform_Project_Directive_v1.0.docx, internally Version 1.0 Draft. Where it conflicts with the approved blueprint, including its earlier treatment of guided authoring, this catalogue follows the approved blueprint and flags the source-version mismatch. The controlling Directive v1.2 itself was not directly read in this turn.

The earlier assessment remains a separate historical assessment. This new document adds direct verification of the blueprint's actual screen and interaction content; it does not overwrite that assessment or claim a current repository audit.

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 20 September 2026 | Created a separate consolidated frontend catalogue with 102 identified requirements, ten screen specifications, API mappings, acceptance checks, conditional scope and decision dependencies |
| 1.1 | 20 September 2026 | Recorded the user's completed personal review and approval of all draft content under FE-APR-001; adopted derived requirements; preserved conditional scope, unresolved selections and separate verification/release controls |

## 22 Owner approval record

**Record:** FE-APR-001
**Decision:** Approved for frontend requirements baseline and development use
**Date:** 20 September 2026
**Authority:** The user, continuing the project-owner approval recorded in the approved blueprint
**Review basis:** Personal review reported complete by the user

Recorded instruction:

> Okay, approve all draft in it, just finished personal review

**Approved scope:** the owner adopts all draft content in this document: FE-001–FE-102, the derived implementation refinements previously marked D, screen coverage for UI01–UI10, role boundaries, API interaction mappings, state behaviour, acceptance checks, required design deliverables and the verification/handover checklist. No defined draft requirement remains awaiting this owner's adoption.

Baseline requirements retain their existing authority. Derived requirements become adopted frontend obligations within their stated scope. Conditional requirements FE-097–FE-102 are approved as conditional controls; this approval does not activate optional attachments, reminders, practice projects or paid capabilities. Scope exclusions remain unchanged.

The API-gap resolution work and decision-management requirements are approved. Approval of the need to select or specify something does not supply the missing selection, route, schema, value, named person or evidence. DEC01–DEC12 dependencies, contract gaps and incomplete design assets remain explicit until their actual resolutions are recorded. Previously completed resolutions may be linked from the current project records; none are assumed here.

**Development and evidence boundaries:** use this approved supplement to plan and implement frontend work within the existing authorised project stages and prerequisites. It does not waive independent review, authorise expenditure or external commitments, certify source code, mark tests passed, close implementation findings, or authorise production deployment. All implementation and verification results remain unverified in this document unless supported by separate evidence.

This is a faithful record of the user's instruction, not a fabricated signature, independent-review certificate or committee decision. The original approval scope and conditional boundaries remain visible for audit.

**Change control and impact:** version 1.1 changes approval status and adopts the existing draft requirements; it does not alter their technical wording, renumber the 102 requirements, select technologies, invent budgets or set delivery dates. The adopted derived requirements may require implementation and testing effort; estimates and assignments remain to be recorded through the existing delivery process.

Future changes must preserve requirement identifiers and record the change, reason, authority and affected implementation/tests. Conflicts with the controlling directive or blueprint require an explicit resolution rather than silent weakening. Version 1.1 supersedes version 1.0 of this frontend requirements document only; the separate assessment and institutional frameworks are not modified.
