# Build Governance Platform Development Blueprint

Requirements specification, interface specification and technical architecture

Version 0.2 | 15 September 2026 | Owner approved development baseline

This blueprint translates the approved Project Directive v1.2 into implementable requirements, user journeys, engineering contracts and a linked work plan. It supports the authorised local development and synthetic-data prototypes. The user has approved the stated requirements and design proposals for development under APR-001 in Section 9. Unspecified choices remain open; production commitments retain their governing approvals.

| Record | Value |
| --- | --- |
| Authority | Owner approval for development initiation in Directive v1.2 Section 18. |
| Implementation state | Not started or not verified in this pack. No runtime test result or independent approval is asserted. |
| Scope | 58 derived requirements, 23 directive acceptance cases, seven prototype remediation items, 14 work packages and 12 decision records with outstanding inputs identified. |
| Companion | Build_Governance_Platform_Implementation_Tracker_v0.2_Approved.xlsx |
| Control | Directive v1.2 governs. A conflict is raised as a decision; it is never silently resolved by weakening a requirement. |


## 1 How to use the blueprint

Read Sections 2 and 3 for the owner-approved product behaviour. Use Sections 4 to 7 to design and implement it. The workbook contains editable owners, status, due dates, test results and evidence links. Documented is different from implemented: all acceptance and remediation records begin unverified.

The requirement catalogue is a derived starting specification. Each row includes the directive section, work package and test reference. Owner adoption is recorded in Section 9. Required independent reviewers must still check every mandatory directive and governing-framework obligation; the 23 acceptance cases are not the entire compliance floor. AC15 provides traceability, not a substitute for each requirement’s specific test.

## 2 Product scope and user responsibilities

The first usable increment lets a tenant choose an approved starter, create a project, assign evidence, resolve blockers and deliberately record a decision. Its initial discovery audience is small agencies and consultancies. Enterprise-scale assumptions, paid services and a universal rules language are not implied.

| Role | Working responsibility | Authority boundary |
| --- | --- | --- |
| Contributor | Prepare assigned evidence and respond to corrections. | Cannot approve solely because they uploaded evidence. |
| Approver | Review the bound evidence and decide permitted progression. | Requires current role, project scope, MFA and separation checks. |
| Sponsor | See project readiness, conditions and administrator access. | Receives only explicitly granted approval powers. |
| Assurance reviewer | Inspect evidence, decisions and exports. | Read-only unless separately assigned another role. |
| Tenant administrator | Manage membership and approved templates. | Cannot edit history; non-member project access is logged. |
| Platform operator | Maintain service under recorded operational controls. | No routine evidence access or decision-edit authority. Policy DEC11 remains open. |


### 2.1 Scope boundaries

Mandatory first-release capabilities include guided template authoring, identity and isolation, versioned evidence, valid exception handling, immutable decisions, complete export/import, mobile and accessibility support, reliable draft saving and tested recovery. Attachments, digests, practice projects and billing are conditional work packages. Billing must be accepted before charging customers. Optional work cannot displace mandatory assurance.

### 2.2 Common business rules

An evidence percentage never passes a gate. Hold, Redirect and Terminate are recorded outcomes, not approvals. An allowed conditional approval grants only stated activities and requires an owner and deadline. Class-floor exclusions require valid authority; expired exceptions cease satisfying requirements. A zero denominator displays No applicable evidence, not 100% completion.

Tenant configuration may rename labels and express supported policy choices. It cannot remove identity attribution, immutable decisions, audit recording, export or platform security. External mutable URLs preserve a reference, not proof that the target content has remained unchanged.

## 3 Requirements specification

Requirement IDs remain stable when wording changes. TST IDs below are planned tests, not results. Must applies to the first release; Conditional means mandatory controls apply when the optional capability is enabled. Stated implementation proposals are adopted by APR-001; unresolved alternatives and missing details remain subject to the named decisions.

### Identity

REQ-001 Must

Register organisations and verified users; create an explicit organisation membership before project access.

Verification TST-001: A verified member reaches only their organisation; an unverified or unrelated account is denied.

Directive v1.2 §5.1, 5.4, 9 | WP03 | AC01 AC02 AC21

REQ-002 Must

Require MFA for approval authority and provide accessible setup and verified recovery without elevating rights.

Verification TST-002: An approver without MFA cannot submit; recovery restores access only after identity checks and MFA re-enrolment.

Directive v1.2 §5.4, 7.3 | WP03 | AC14 AC21

REQ-003 Must

Resolve active tenant from authenticated server session; verify membership when switching organisations.

Verification TST-003: Changing a URL, request body or cookie tenant claim cannot grant another tenant; expired membership denies access.

Directive v1.2 §5.1 | WP03 | AC02 AC14

REQ-004 Must

Enforce project membership and template role permissions at each service operation.

Verification TST-004: Contributor, approver and assurance users receive only allowed reads and writes.

Directive v1.2 §5.4 | WP03 | AC14 AC16

REQ-005 Must

Record and show tenant-administrator access to projects outside their membership to the sponsor.

Verification TST-005: The access event identifies actor, project and time and is visible to the sponsor.

Directive v1.2 §5.4 | WP03 | AC14

REQ-006 Must

Enforce separation of duties; any permitted override records approved compensating review and independent reviewer.

Verification TST-006: Self-only approval is rejected unless the scoped override is valid; an empty reviewer note cannot satisfy it.

Directive v1.2 §5.4 | WP07 | AC14

### Tenancy

REQ-007 Must

Put tenant IDs on all owned rows and enforce PostgreSQL RLS through a restricted application role.

Verification TST-007: Missing tenant context returns no owned records; application roles cannot bypass RLS or act as table owners.

Directive v1.2 §5.1 | WP04 | AC02

REQ-008 Must

Reset tenant context across pooled transactions and enforce isolation in workers, files, caches, search and exports.

Verification TST-008: Reuse a connection between two tenants and run mixed-tenant jobs; no data crosses boundaries.

Directive v1.2 §5.1, 5.5 | WP04 | AC02

REQ-009 Must

Run an adversarial cross-tenant suite as a blocking CI check and demonstrate detection of a seeded leak.

Verification TST-009: A deliberately weakened policy or service query causes the suite to fail; repaired code passes.

Directive v1.2 §5.1, 12 | WP04 | AC02

### Templates

REQ-010 Must

Version framework templates containing tracks, gates, classification, role, status, decision and applicability schemes.

Verification TST-010: Three distinct framework fixtures represent expected classes, roles and gates without application code changes.

Directive v1.2 §5.2 | WP05 | AC09 AC13

REQ-011 Must

Make published versions immutable; bind each project to one version and approve explicit migrations.

Verification TST-011: Publishing v2 leaves a v1 project unchanged; migration logs impact, approver and both versions.

Directive v1.2 §5.2 | WP05 | AC13

REQ-012 Must

Provide guided authoring, fork, blank creation and schema-validated JSON import and export.

Verification TST-012: A tenant builds and runs a template without JSON; malformed or unsupported imports explain the failing field.

Directive v1.2 §5.2, 7, 9 | WP05 | AC08 AC09

REQ-013 Must

Restrict configurable rules to a versioned declarative vocabulary; prohibit executable code and invariant overrides.

Verification TST-013: Rule validation rejects arbitrary expressions, unknown operators, cycles and attempts to disable audit or export.

Directive v1.2 §5.2.1 | WP05 | AC09

REQ-014 Must

Include KenAddme only after licensing clearance; otherwise supply a neutral starter.

Verification TST-014: Release manifest records template provenance and licensing decision; unresolved content is excluded.

Directive v1.2 §5.2, 9, 14 | WP05 | AC01 AC09

### Projects

REQ-015 Must

Create a project with name, template binding, class, owner and explicit members; seed applicable evidence.

Verification TST-015: Creation commits project and required items together, or neither when seeding fails.

Directive v1.2 §2.4, 5.2, 9 | WP06 | AC01

REQ-016 Must

Represent every routine and triggered gate review as a separate occurrence with due date and evidence snapshot.

Verification TST-016: Two routine reviews and a triggered review preserve separate evidence and decisions.

Directive v1.2 §5.2.1, 11 | WP06 | AC12

### Evidence

REQ-017 Must

Track evidence status, owner, due date, completion date and reference; retain immutable revisions and change attribution.

Verification TST-017: Editing creates a new revision; prior actor, time and values remain available.

Directive v1.2 §5.3, 5.5, 9 | WP06 | AC10 AC11

REQ-018 Must

Validate completion against the resulting record on every update; do not allow removal of required evidence while Complete.

Verification TST-018: A patch clearing a mandatory reference from a completed item is rejected or explicitly transitions it out of Complete.

Directive v1.2 §5.3.2 | WP06 | AC11

REQ-019 Must

Bind approved evidence to source versions or hashes where available; disclose mutable-reference limitations.

Verification TST-019: The approval manifest preserves exact local revision and available source version; an unversioned URL is labelled.

Directive v1.2 §5.3.1 | WP06 | AC04 AC10

### Exceptions

REQ-020 Must

Validate not-applicable classifications against rules and class floor; validate exceptions by authority, scope and expiry.

Verification TST-020: A typed status alone cannot exclude an item; expired, revoked and unrelated exceptions are rejected.

Directive v1.2 §5.3.2 | WP07 | AC03 AC11

REQ-021 Must

Reassess affected gates when exceptions expire or evidence changes; preserve earlier decisions.

Verification TST-021: An expired exception changes current readiness and triggers reassessment without rewriting history.

Directive v1.2 §5.3.1, 5.3.2 | WP07 | AC10 AC11

### Decisions

REQ-022 Must

Permit approval only with satisfied requirements; conditional approval needs allowed conditions, owner, deadline and activity limits.

Verification TST-022: Missing deadline or unresolved critical blocker denies conditional approval and records the attempt.

Directive v1.2 §5.3.2 | WP07 | AC03 AC11

REQ-023 Must

Record decisions append-only with authenticated authority, server time, occurrence, template and evidence manifest.

Verification TST-023: Requests cannot supply an authoritative actor or timestamp; resulting records include all required bindings.

Directive v1.2 §5.3.1 | WP07 | AC04 AC10

REQ-024 Must

Recheck authority and reviewed revision atomically; prevent stale approval and duplicate retry decisions.

Verification TST-024: Concurrent evidence or membership changes reject stale commits; repeated identical keys return one decision.

Directive v1.2 §5.3.1 | WP07 | AC10

REQ-025 Must

Support superseding corrections only; record a reason and original-decision link.

Verification TST-025: Every application role is denied UPDATE or DELETE of decisions; a new correction retains the original.

Directive v1.2 §5.3 | WP07 | AC04 AC12

### Integrity

REQ-026 Must

Detect privileged tampering using separately controlled verification material, with defined custody and verification frequency.

Verification TST-026: Alter stored history in a controlled test; independent verification detects it within the approved interval.

Directive v1.2 §5.3.1 | WP08 | AC04

REQ-027 Must

Block approval acknowledgements for affected integrity failures, preserve evidence and trigger incident handling.

Verification TST-027: Injected mismatch denies new acknowledgements in affected scope and produces an incident record.

Directive v1.2 §5.3.1 | WP08 | AC04

### Recovery

REQ-028 Must

Meet zero acknowledged-decision loss within the approved failure envelope, including interpretation records.

Verification TST-028: Fault tests reconcile all acknowledged IDs and associated manifests after supported failures.

Directive v1.2 §10 | WP08 | AC07

REQ-029 Must

Restore ordinary data with RPO at most one hour and service within eight hours; test quarterly in clean environments.

Verification TST-029: Restore drill measures latest recoverable ordinary write and service recovery including integrity reconciliation.

Directive v1.2 §6, 10 | WP08 | AC07

### Export

REQ-030 Must

Provide complete open-format tenant export and lossless clean-instance re-import without privilege transfer.

Verification TST-030: Compare record IDs, counts, revisions, hashes and relationships after import; imported actors do not receive live credentials.

Directive v1.2 §5.3, 9, 12 | WP09 | AC05

REQ-031 Must

Keep own-data export, audit history and MFA available on all tiers, including billing disputes.

Verification TST-031: A read-only billing state permits authorised exports and history access but denies ordinary writes.

Directive v1.2 §5.3, 8 | WP09 | AC05 AC14

### Usability

REQ-032 Must

Provide role-specific My work with project, reason, deadline, state and a direct action.

Verification TST-032: Each persona finds their assigned action while unrelated assignments stay hidden.

Directive v1.2 §7.1 | WP10 | AC16

REQ-033 Must

Provide short guided forms, field examples, clear errors and reversible navigation without losing valid input.

Verification TST-033: Back navigation and invalid fields preserve all valid responses.

Directive v1.2 §7.1 | WP10 | AC17

REQ-034 Must

Save and resume drafts with truthful Saving, Saved and Not saved states under a declared shared-device policy.

Verification TST-034: Interrupt a save and reload within the supported boundary; saved data returns and unsaved data is not misrepresented.

Directive v1.2 §7.2 | WP10 | AC18

REQ-035 Must

Distinguish pending from confirmed approvals; retrieve outcome after timeout and handle concurrent edits explicitly.

Verification TST-035: Drop the response after commit; recovery displays the existing decision without creating another.

Directive v1.2 §7.2 | WP10 | AC18

REQ-036 Must

Explain blockers in plain language and link to their corrective action without exposing restricted information.

Verification TST-036: A newcomer identifies the missing item and reaches the permitted correction without external documentation.

Directive v1.2 §7.1 | WP10 | AC19

REQ-037 Must

Show evidence, conditions and permitted progression in a deliberate approval confirmation summary.

Verification TST-037: Users explain the action permitted before submitting; opening a page or email never approves anything.

Directive v1.2 §7.3 | WP10 | AC20

REQ-038 Must

Support invitation landing, accessible MFA and recovery as part of the essential task journey.

Verification TST-038: An invited user reaches the intended project after sign-in and can recover without a control bypass.

Directive v1.2 §7.3 | WP03 | AC21

REQ-039 Must

Use unambiguous dates and visible time zones; support translation structure and consistent tenant terminology.

Verification TST-039: UTC storage and user-zone display agree across daylight-saving and boundary cases; labels retain decision meanings.

Directive v1.2 §7.5 | WP10 | AC23

REQ-041 Must

Meet twenty-minute unaided onboarding; baseline inclusive per-group testing with approved 90% task completion.

Verification TST-041: Record sample sizes, assistance, device profiles and each group result; do not conceal a failing group in a pooled average.

Directive v1.2 §2.4, 7.6 | WP11 | AC01 AC22

REQ-042 Must

Block release for critical approval misunderstanding until corrected and retested.

Verification TST-042: Observed misunderstanding is logged as a release blocker with repeat-test evidence after the fix.

Directive v1.2 §7.6 | WP11 | AC20

### Accessibility

REQ-040 Must

Meet WCAG 2.2 AA with no open A or AA failure; support all mandatory tasks on phones and with assistive technology.

Verification TST-040: Automated checks plus keyboard, screen-reader, focus, contrast and zoom reviews pass essential journeys.

Directive v1.2 §7, 10 | WP11 | AC06 AC22

### Operations

REQ-043 Must

Baseline 99.5% monthly availability and publish measurements; approve API and slow-device render budgets.

Verification TST-043: Approved measurement definitions, traffic profile and numeric performance budgets are tested and reported.

Directive v1.2 §7, 10 | WP12 | AC15

REQ-046 Must

Remediate critical vulnerabilities within seven calendar days and high within thirty; acknowledge S1 within one hour.

Verification TST-046: Service procedures assign on-call responsibility and track due times, escalation and remediation evidence.

Directive v1.2 §3.4, 10 | WP12 | AC15

REQ-047 Must

Review access quarterly and maintain security logs with minimised personal data and defined retention.

Verification TST-047: Access-review and log-retention samples demonstrate ownership, revocation and restricted access.

Directive v1.2 §6, 10 | WP12 | AC15

### Security

REQ-044 Must

Threat-model tenancy, template escalation, evidence/audit abuse, enumeration, attachments and billing; perform privacy assessment.

Verification TST-044: Independent reviewers record threats, mitigations, residual risks and data-handling decisions.

Directive v1.2 §6, 11 | WP02 | AC15

REQ-045 Must

Use approved secret storage and rotation; encrypt transit and stored database/object data with separately held key material.

Verification TST-045: Review configuration and rotation evidence; tests deny plaintext and unauthorised secret access.

Directive v1.2 §6 | WP12 | AC15

### Data

REQ-048 Must

Define retention floor, legal hold and authorised disposal; preserve actor attribution within retention and clarify decision retention.

Verification TST-048: Policy review resolves retention conflicts before implementation; hold blocks eligible disposal and records its basis.

Directive v1.2 §5.3, 5.5 | WP02 | AC15

### Delivery

REQ-049 Must

Maintain source control, migrations, code review, reproducible checks and dependency/licence inventory.

Verification TST-049: A clean checkout builds using pinned configuration and migrations; review and inventory are attached to the build.

Directive v1.2 §11, 16.5 | WP01 | AC15

### Assurance

REQ-050 Must

Obtain independent penetration testing before general availability; validate accessibility, acceptance and release evidence.

Verification TST-050: Independent findings and residual-risk decisions accompany the release recommendation.

Directive v1.2 §6, 11 | WP13 | AC02 AC06 AC15

### Governance

REQ-051 Must

Maintain requirement-to-task-to-test evidence, named responsibilities, change control and recurring Class A reviews.

Verification TST-051: Every mandatory item has an owner or explicit vacancy and linked evidence; no status alone grants release.

Directive v1.2 §11, 14, 18 | WP01 | AC15

REQ-052 Must

Use only synthetic data for initial work; remain within approved scope and external-commitment limits.

Verification TST-052: Review environments and data fixtures; production, budget and supplier decisions are separately recorded.

Directive v1.2 §15, 18 | WP01 | AC15

REQ-057 Must

Fund and schedule independent assurance and benefits review; Class A benefits review is interim at three months and formal at six.

Verification TST-057: Approved plan identifies assurance capacity and protected benefits-review effort without inventing allocations.

Directive v1.2 §3.4, 11 | WP02 | AC15

### Attachments

REQ-053 Conditional

If enabled, scan, cap, encrypt and version uploads; isolate object access and use short-lived signed download URLs.

Verification TST-053: Malicious or unscanned objects are quarantined; cross-tenant signing fails; old versions and export are retained.

Directive v1.2 §5.5, 9 | WP14 | AC02 AC05

### Notifications

REQ-054 Conditional

If enabled, provide grouped routine reminders, task links and completion suppression with permission-filtered content.

Verification TST-054: Completed work generates no routine reminder; revoked users receive no protected task content.

Directive v1.2 §7.4, 9 | WP14 | AC23

### Practice

REQ-055 Conditional

If enabled, use resettable fictional practice projects isolated from live reports, decisions and exports.

Verification TST-055: Resetting a practice project cannot affect real records and practice decisions never enter live metrics.

Directive v1.2 §7.4 | WP14 | AC23

### Billing

REQ-056 Conditional

Before paid signup, implement tiering, grace periods, read-only downgrade and contracted deletion policy; never store card data.

Verification TST-056: Payment tokens only; billing failure preserves export and does not directly delete data.

Directive v1.2 §6, 8, 9 | WP14 | AC14

### Release

REQ-058 Must

Obtain named release authorisation, tested migration/rollback, runbooks, monitoring and operational handover before production.

Verification TST-058: Release checklist links to actual approver decisions and rehearsals; unmet critical evidence prevents release.

Directive v1.2 §11, 15 | WP13 | AC15

## 4 Interface specification

### 4.1 Navigation and page structure

Use a persistent organisation selector, My work, Projects and a labelled account menu. Show template administration only to authorised users. A project page uses Overview, Evidence, Reviews and History; Export is available from the project or organisation record. Keep the active organisation visible while editing or approving. On a phone, stack the content in this order: title and context, next action, blockers, supporting details. Navigation labels remain stable across tenant templates.

Every screen has one descriptive heading and an obvious primary action. Use text labels with icons, never colour alone for status. Focus moves to validation summaries and returns to the originating control when a dialog closes. Do not use drag-and-drop as the sole interaction. Support zoom and reflow, labelled fields, keyboard operation, visible focus and screen-reader announcements for save and submission outcomes.

| Screen | Inputs and primary action | States and safeguards |
| --- | --- | --- |
| UI01 Sign in and invitation | Email, credential, MFA; accept invitation after sign-in. | Expired invitation: request another. Wrong organisation: explain and deny. Recovery has a verified path. |
| UI02 First project | Starter, project name, class and owner; Create project. | Show concise starter explanation. Atomic create; retry cannot create duplicate projects. |
| UI03 My work | Filter by project and due state; Open task. | Empty: explain no assigned work. Revoked access: remove entry. Do not expose restricted titles. |
| UI04 Evidence editor | Status, owner, due date, reference and notes; Save draft or Submit. | Saved/Saving/Not saved. Invalid reference points to field. Concurrent change preserves draft for review. |
| UI05 Gate readiness | Mandatory items, exclusions, conditions; Review decision. | Explain each blocker and permitted fix. Show reassessment flags and actual reviewed revision. |
| UI06 Decision summary | Outcome, conditions, owner and deadline; Confirm decision. | Show exact evidence manifest and permitted next activity. Stale revision requires fresh review. |
| UI07 History | Occurrence and decision filters; View record or Start correction. | Historical records are read-only. Correction creates superseding record with reason. |
| UI08 Template authoring | Guided tracks, gates, classes and rules; Validate then Publish. | Preview applicability. Unknown rules show actionable errors. Published version cannot be edited. |
| UI09 Export and import | Scope, format and archive; Generate export or Validate import. | Explain queued/ready/expired download states. Import preview warns about unmapped actors. |
| UI10 Membership and account | Invites, roles, MFA and preferences; Save permitted change. | Role escalation checked on server. Removing approval authority invalidates stale attempts. |


### 4.2 Detailed essential journeys

Journey A Start a project

A verified user enters an organisation, chooses a licensed starter and enters a project name. The service validates class and membership, creates a bound project and seeds evidence in one transaction. The next page shows the first occurrence and a single next action. The onboarding test includes account and MFA steps where the chosen role requires them.

Journey B Supply evidence

The contributor opens an assigned task from My work, sees an example and adds a reference. Saving produces a new draft revision only after acknowledgement. Submit checks the full resulting record. A failing field is explained without discarding valid input. Reopening restores the server-saved draft within the declared policy.

Journey C Make a decision

The approver opens readiness, resolves or reviews blockers and requests a decision preview. The summary names the occurrence, evidence revisions, outcome, conditions and permitted progression. Confirm submits the preview revision token and idempotency key. A stale preview returns to review; an unknown network outcome triggers lookup rather than blind resubmission.

Journey D Correct a record

An authorised user selects Start correction from a historical decision. The interface asks for a reason and displays the original. The new decision references the original and follows the same authority and evidence checks. Both records remain visible; the current projection points to the superseding record.

Journey E Author a framework

An administrator starts from blank or forks a permitted starter, adds tracks and gate definitions, assigns supported class rules and role powers, then validates. A preview shows required and excluded evidence for each class. Publication creates an immutable version. Moving a live project requires a separate migration review.

### 4.3 Interaction language and failure behaviour

| Condition | Suggested message | Action |
| --- | --- | --- |
| Missing evidence | The test report is missing. Add its reference before approval. | Open the evidence item. |
| Concurrent edit | This evidence changed while you were reviewing it. Review the latest version. | Keep draft; refresh the comparison. |
| Unconfirmed save | Your changes have not been saved. Check your connection and try again. | Retry draft save without claiming success. |
| Unknown decision outcome | We are checking whether your decision was recorded. | Retrieve by idempotency key. |
| Expired exception | This exception expired. New approval requires valid evidence or an authorised exception. | Open the exception record. |
| No applicable evidence | No evidence items apply under the approved rules. A gate decision is still required. | Open the decision review. |


### 4.4 Usability study protocol

Run formative sessions before selecting the final frontend. Recruit beginners, contributors, client approvers and administrators, including disabled users and older-phone users. Use synthetic fixtures and record task completion, time, assistance, mistaken approvals and recovery failures. DEC08 must baseline sample sizes, device profiles and the approved 90% unaided completion threshold separately for each group. The twenty-minute onboarding target remains mandatory. Do not claim statistical confidence from a small convenience sample.

Critical misunderstanding of what approval permits is a release blocker. Re-test corrected journeys with users who did not learn the earlier interface. Report keyboard and screen-reader journey results separately from automated checks. Translation languages follow discovery; date and timezone clarity is mandatory immediately.

## 5 Technical architecture

### 5.1 Approved component boundaries

Use a modular FastAPI service with a PostgreSQL transactional store and SQLAlchemy/Alembic migrations, consistent with the directive’s proposed backend. Keep identity, tenancy, templates, evidence, decisions and export modules distinct within one initial service. A worker handles scheduled reassessment, export and optional notifications. A browser interface talks to a same-origin API; final frontend, session mechanism and pinned dependency versions remain DEC04. This architecture is owner approved for development; deployability remains to be demonstrated.

| Component | Owns | Does not own |
| --- | --- | --- |
| Web interface | Forms, readable summaries, local interaction state. | Approval authority, tenant trust or durable decision acknowledgement. |
| Identity and tenancy | Verified session, current membership, MFA and project access. | Tenant-supplied assertions of authority. |
| Rule interpreter | Validated declarative policy and deterministic readiness calculation. | Arbitrary tenant code or platform invariants. |
| Evidence and decisions | Transactional revisions, occurrence state, manifest and append-only outcome. | Editing historical decisions. |
| Audit and verification | Status events, protected checkpoints and verification jobs. | Declaring data untampered solely because a hash is stored beside it. |
| Worker | Scoped exports, reassessments and scheduled tasks. | Unscoped database access. |
| Object storage if enabled | Quarantined uploads and immutable file versions. | Unauthorised public evidence links. |


### 5.2 Data model

Use opaque identifiers, server timestamps in UTC, foreign keys and tenant-scoped uniqueness. Auth identities may be global; memberships are tenant scoped. Each tenant-owned child carries tenant_id, and composite parent references prevent cross-tenant relationships even when an application passes an incorrect ID. Deletion cascades must not erase decision or audit history.

| Entity | Key fields and relationship | Required constraint |
| --- | --- | --- |
| Tenant / User / Membership | Membership joins user and tenant; status, permissions version. | Active membership required; identities are not transferred by import. |
| Project / ProjectMembership | Project binds tenant, template version and class; members carry roles. | Tenant-scoped parent keys; membership changes bump authority revision. |
| Template / TemplateVersion | Version owns class, role, status and decision schemes. | Published immutable; uniqueness on tenant/template/version. |
| GateDefinition / ArtefactRule | Gate and evidence definitions inside a version. | Rules reference known IDs and supported operators only. |
| GateOccurrence | Project, definition, sequence, trigger, due time, readiness revision. | Unique project/definition/occurrence; repeated reviews are distinct. |
| EvidenceItem / EvidenceRevision | Stable item plus immutable values, source reference and actor revision. | Append revisions; current pointer cannot destroy old content. |
| ExceptionRecord | Scope, approving actor, owner, safeguards, start, expiry, revocation. | Never inferred from display status; validate at decision time. |
| DecisionRecord / Manifest | Occurrence, actor, authority snapshot, outcome, reviewed revision, supersedes. | Append-only; manifest binds exact evidence and template version. |
| AuditEvent / Checkpoint | Actor, before/after, sequence, event digest and independent checkpoint reference. | Protect ordering and completeness; separate verification custody. |
| IdempotencyRecord | Tenant, actor, operation, key, request digest, outcome reference. | Unique scoped key; same key with altered request conflicts. |
| Draft / ExportJob / ImportJob | Owner, tenant, schema version, status, error and expiry. | Draft is not a decision; jobs require fresh authorisation. |
| AttachmentVersion optional | Object key, hash, scan status, classification and retention. | Downloads only after clean scan and authorised signing. |


### 5.3 Approved API contracts

The route shapes below are the owner-approved application interfaces. All owned-object routes enforce session tenant and project access. Use bounded pagination and server validation. Responses must not disclose another tenant’s object existence. Auth and CSRF controls depend on the approved session ADR. Status codes: 401 unauthenticated, 403 forbidden, 404 absent or concealed, 409 stale/conflicting state, 422 invalid input, 503 required durable path unavailable.

| Method and route | Payload or result | Control |
| --- | --- | --- |
| POST /api/projects | name, template_version_id, class_id; returns project and first occurrence. | Idempotent creation; atomic seeding. |
| GET /api/my-work | cursor, filter; permitted tasks and next actions. | Membership scoped, paginated. |
| POST /api/projects/{id}/occurrences | gate_definition_id, trigger, due_at. | Authorised creator; sequence allocated transactionally. |
| POST /api/evidence/{id}/revisions | base_revision, status, owner, reference and dates. | Optimistic concurrency; validate resulting record. |
| PUT /api/drafts/{id} | base_revision, supported form data. | Owner scoped; server save state only after commit. |
| POST /api/occurrences/{id}/preview | proposed outcome and conditions. | Returns readiness revision, blockers and manifest digest. |
| POST /api/occurrences/{id}/decisions | preview_revision, manifest_digest, conditions; Idempotency-Key header. | Atomic authority/readiness recheck; durable acknowledgement. |
| GET /api/decision-requests/{key} | recorded, pending or absent outcome. | Tenant and actor scoped recovery after timeout. |
| POST /api/decisions/{id}/superseding | reason, new preview and outcome. | Same authority controls; no UPDATE or DELETE endpoint. |
| POST /api/exceptions | scope, safeguards, owner, expiry and approving workflow. | No self-asserted approval. |
| POST /api/templates/{id}/publish | draft_revision and validation receipt. | Immutable version; authorisation and schema checks. |
| POST /api/projects/{id}/migrations | new_version_id, impact and authorisation. | Explicit migration; historical bindings preserved. |
| POST /api/exports | scope and format version; returns job. | Complete own-data export even in billing read-only mode. |
| POST /api/imports/validate | archive; returns schema, provenance and mapping report. | Quarantine and no authority activation. |
| POST /api/imports/{id}/commit | validated revision and approved mappings. | Atomic or resumable staged import; reconciliation required. |


### 5.4 Decision transaction contract

1. Authenticate, require MFA, resolve tenant, verify project membership and acquire the relevant occurrence/version lock.

2. Look up the tenant/actor/operation idempotency key. Return its recorded outcome for an identical request; reject changed payload reuse.

3. Re-read approval role, membership revision, template binding and separation rules. Concurrent authority changes must participate in compatible locking or serialisable validation.

4. Recompute applicability and active exceptions using server time. Compare submitted preview and evidence revisions with current state; reject stale state.

5. Construct the manifest, enforce blockers and validate conditional owner, deadline and permitted activities.

6. Append the decision, immutable manifest, audit event and idempotency outcome atomically. Denied attempts create a separate authorised audit event; a rollback must not silently erase the refusal record.

7. Complete the durability mechanism selected by DEC05 before returning recorded success. If independent receipt completion is required, retain Pending and reconcile idempotently; never label it approved early.

8. Return decision ID, occurrence ID, timestamp, reviewed revision and explicit outcome. If the response is lost, the client retrieves the outcome rather than creating a second decision.

9. On later evidence change or exception expiry, flag current readiness for reassessment while preserving the historical decision. An audit mismatch blocks new acknowledgements and opens an incident.

DEC05 must choose a realizable acknowledgement mechanism. Candidate A uses synchronous durable replication for the approved failure domains plus independently protected integrity checkpoints. Candidate B uses a pending intent and independently durable receipt, with a reconciler that finalises only after receipt verification. Do not combine their success semantics casually. A stored hash chain alone neither prevents privileged rewriting nor proves disaster durability.

### 5.5 Rule interpreter contract

Approved rule schema: version, rule_id, class_ids, occurrence_type, evidence_kind, applicability, required_fields, permitted_role_ids, blocker_level and conditions. Permitted operators are equality, membership and bounded all/any over declared facts. No arbitrary scripts, network lookups or unbounded recursion. Validation rejects unknown keys and invalid references. The exact vocabulary and limits require DEC07 approval.

Evaluate in this order: platform invariants; project/template/class applicability; evidence completeness; valid exclusions; role and separation constraints; hard blockers; conditional-approval limits. Unknown facts fail closed for decisions and produce actionable errors. Store the interpreter version and rule result with the manifest so a later engine change cannot silently reinterpret history.

### 5.6 Export and import contract

Approved open archive: manifest.json with format version and checksums, templates.json, projects.json, occurrences.json, evidence-revisions.json, decisions.json, audit.json, actors.json and optional attachments. Include stable source identifiers, supersession links, classifications, exceptions and available integrity receipts. Exclude passwords, session tokens, recovery secrets and private signing keys. Document these security exclusions in the export manifest.

Import validates archive sizes, paths, hashes, schema and tenant bindings in quarantine. Historical actors are mapped to provenance records, not silently created as authorised users. Reconcile counts, IDs, digests and links before making imported data visible. Legacy missing attribution is labelled as missing; it is never reconstructed as a verified approval. The current operator remains responsible for verifying source authenticity.

### 5.7 Recovery and operational contract

Ordinary data recovery aims at one-hour RPO and eight-hour service restoration. Acknowledged decisions and their interpretation records require zero loss within the approved failure envelope. DEC05 must specify process, node, zone, storage and regional scenarios, exclusions, custody, required availability and how success is acknowledged. Quarterly restore drills start in clean environments, reconcile records and then resume approval processing.

Minimum telemetry records errors, latency, queue age, draft save failures, decision-pending age, denied approvals, integrity failures, backup age and restore results without unnecessary personal content. Define S1 ownership and acknowledgement, vulnerability deadlines and quarterly access reviews. Numeric API p95 and page/render budgets remain DEC08; no load-capacity claim is made in this blueprint.

## 6 Delivery sequence and verification

Stage A may start under Directive Section 18: repository, synthetic fixtures, requirements, design options and local isolated prototypes. Stage B integrates identity, RLS, templates, evidence and decision workflows against approved baselines. Stage C proves integrity, export, recovery and usability. Stage D requires independent assurance and the release authority. Work-package dependencies are sequencing constraints, not assigned dates or a committed schedule.

| Package | Depends on | Deliverable |
| --- | --- | --- |
| WP01 Repository and delivery controls | None | Controlled repository, build instructions, synthetic fixtures, requirement ledger |
| WP02 Discovery and assurance decisions | WP01 | Market, roles, data inventory, assurance plan, privacy and threat reviews |
| WP03 Identity and membership | WP01 | Registration, sessions, MFA, invitations, project permissions |
| WP04 Tenant isolation | WP03 | RLS migrations, restricted roles, pooled-session and worker isolation tests |
| WP05 Templates and rule interpreter | WP01 WP02 | Three framework fixtures, rule schema, immutable publication, guided authoring contract |
| WP06 Projects and evidence revisions | WP04 WP05 | Atomic project seeding, evidence history, recurring occurrences |
| WP07 Decisions and exceptions | WP06 WP03 | Atomic revision checks, scoped exceptions, append-only decisions |
| WP08 Integrity and recovery | WP07 WP02 | Independent verification path, fault tests, restore drill |
| WP09 Export and import | WP06 WP07 | Versioned archive, permission-safe import, round-trip reconciliation |
| WP10 Essential user journeys | WP03 WP06 WP07 | My work, guided forms, saves, blockers, decision summary |
| WP11 Usability and accessibility | WP10 | Participant protocol, accessible journey results, remediation evidence |
| WP12 Operations and hardening | WP04 WP08 | Secrets, monitoring, vulnerability handling, performance and recovery readiness |
| WP13 Independent acceptance and release | WP09 WP11 WP12 | Penetration test, user acceptance, release and rollback records |
| WP14 Optional and paid capabilities | WP07 WP09 WP10 | Attachments, reminders, practice and billing; no paid signup before billing acceptance |


### 6.1 First working increment

Use two fictional tenants, each with a sponsor, contributor and approver. Create a neutral template, one project and one gate occurrence. Add required evidence, show a blocker, reject an unauthorised or stale decision, then record an authorised decision and a superseding correction. Export the record. Demonstrate no cross-tenant access. Label the increment as a local prototype until durability, independent assurance and release requirements are evidenced.

### 6.2 Test fixtures and execution

Maintain fixtures for: missing reference on Complete; expired exception; conditional approval without a deadline; author attempting sole approval; tenant B object ID submitted by tenant A; evidence edited during preview; membership revoked during submission; timeout after commit; corrupted audit history; template v2 published while project remains on v1; and three separate review occurrences. Add coverage for optional attachments and billing only when enabled.

TST-001 to TST-058 in the workbook contain requirement-specific expected results. AC01 to AC23 retain the directive wording. Map actual automated and human-test reports to their evidence cells and record the tested source revision and environment. A passing test without evidence or reviewer is not verified closure. The workbook calculates completion only for a recorded pass with an evidence reference and reviewer; it does not grant a project gate approval.

### 6.3 Prototype remediation

| Finding | Implementation links | Package |
| --- | --- | --- |
| TR01 Open routes and missing tenancy | REQ-001 REQ-002 REQ-003 REQ-004 REQ-007 REQ-008 | WP03 WP04 |
| TR02 Overwritten decisions and typed authority | REQ-016 REQ-023 REQ-025 | WP06 WP07 |
| TR03 Unverified exclusions | REQ-020 REQ-021 | WP07 |
| TR04 Incomplete conditional approval checks | REQ-022 | WP07 |
| TR05 Evidence reference can be cleared | REQ-018 | WP06 |
| TR06 Inconsistent HTML and Markdown controls | REQ-016 REQ-022 REQ-037 | WP06 WP07 WP10 |
| TR07 Prototype database and delivery foundation | REQ-007 REQ-029 REQ-049 | WP01 WP04 WP08 |


## 7 Decision dispositions and remaining responsibilities

Named people, budget and dates have not been supplied. Role labels below identify responsibility to assign, not accepted appointments. Initial local prototypes can explore open decisions; no unselected vendor, region or durability guarantee is treated as approved.

| Decision | Accountable role and deadline | Approved position and remaining input |
| --- | --- | --- |
| DEC01 Named delivery lead and independent reviewer | Sponsor; Before relying on their authority | Approved responsibility structure. Named delivery and independent-review appointments and their acceptance remain required. |
| DEC02 Market, region and residency | Sponsor and privacy reviewer; Project Gate 2 / Software G1 | Approved initial focus on small agencies and consultancies. Geography, hosting region and residency remain to be selected. |
| DEC03 Template and platform licensing | Owner; Project Gate 2 / Software G1 | Approved licensing-clearance requirement and neutral-starter fallback. No licence or third-party permission is granted by this approval. |
| DEC04 Frontend and API session architecture | Technical lead; Project Gate 3 / Software G2 | Approved modular FastAPI, PostgreSQL, SQLAlchemy/Alembic and same-origin web architecture. Frontend framework, session mechanism and pinned versions remain to be selected. |
| DEC05 Durability failure envelope and mechanism | Operations and security leads; Project Gate 3 / Software G2 | Approved zero-loss objective within an explicit failure envelope and independent integrity verification. Candidate A versus B, covered failures and custody remain to be selected. |
| DEC06 Retention, disposal and attribution | Privacy reviewer and owner; Before retention implementation | Approved retention review, attribution and disposal controls. Retention periods and the permanent-record conflict remain to be resolved before implementation. |
| DEC07 Rule vocabulary and three frameworks | Technical lead; Before guided authoring implementation | Approved declarative rule schema and evaluation order in Section 5.5. Vocabulary limits, third framework and its permitted use remain to be specified. |
| DEC08 Usability sample and performance budgets | UX and technical leads; G1 protocol; G2 technical budgets | Approved 90% unaided task completion separately for each user group and twenty-minute onboarding. Sample sizes, devices, network profile and numeric performance budgets remain to be specified. |
| DEC09 Budget, capacity and delivery estimate | Sponsor; Before scope extension or external commitment | Approved work-package sequence and responsibility roles. Actual staffing, funding, estimates and dates remain to be supplied; no spending commitment is created. |
| DEC10 Payment, free-tier and grace policy | Sponsor; Before paid capabilities | Approved payment controls and no-card-data boundary. Processor, tier limits and grace periods remain to be selected before paid use. |
| DEC11 Operator access and key custody | Security lead and owner; Policy G1; mechanism G2 | Approved no routine operator evidence access and no decision-edit authority. Break-glass scope, approval path, tenant visibility and independent key custody remain to be specified. |
| DEC12 Migration of legacy tracker records | Data owner; Before importing real records | Approved provenance-preserving migration policy; never invent missing actors or approvals. Any real-data import still requires data-owner authorisation and reconciliation evidence. |


### 7.1 Follow through after owner approval

Owner review of the 58 requirements, screen journeys and stated engineering proposals is approved under APR-001. Complete required independent reviews, assign architecture ADR owners and delivery roles, supply the first time-boxed estimate, and record each governing gate decision. Keep all seven prototype findings open until code and evidence demonstrate correction. The development-initiation approval does not supply missing independent reviews.

## 8 Source and version record

Primary source: Build Governance Platform Project Directive v1.2 Approved, dated 14 September 2026, especially Sections 5 to 7, 9 to 12 and 16 to 18. Governing sources: KenAddme IT Links Project Management Framework v1.1 and Software Development and Engineering Framework v1.2, supplied in file.zip. Prototype source: tracker_api.py and supporting tracker editions in files 2.zip. This pack does not modify those source files.

Blueprint v0.2 supersedes v0.1 as the owner-approved development baseline under APR-001. Directive v1.2 remains unchanged. The JSON requirement catalogue and Markdown working copy in the download bundle are editable reference sources. Maintain stable identifiers across revisions. The Excel workbook owns execution status and evidence links; approved document baselines own requirement wording. Reconcile changes through a recorded change decision.



## 9 Owner approval record

APR-001 | 15 September 2026 | Approved for development baseline use

Authority: the user in this conversation, continuing the owner approval recorded in Directive v1.2. The instruction was: “I’ve gone through the pending reviews, quite ok, approve them”. This is a recorded instruction, not a fabricated signature or independent-review certificate.

### What is approved

The owner adopts REQ-001 to REQ-058, UI01 to UI10 and the five essential journeys; the stated architecture, data model, API, rule, export and operational contracts; the verification approach; and WP01 to WP14 with their dependencies. The remediation plans for TR01 to TR07 are approved for execution, not closed as fixed. The 90% per-group usability target is now adopted alongside the twenty-minute onboarding target.

### How the pending decisions are treated

Section 7 records a disposition for all twelve decision items. DEC01 to DEC11 are partly decided: stated policies and proposals are approved, while absent names, values, permissions or selections remain visible. DEC12 is decided at policy level; each actual import still needs its own authorisation and evidence. Approval of a set of alternatives does not select an alternative.

### Development and release boundaries

Proceed with the already-authorised repository foundation, synthetic fixtures and local prototypes under Directive v1.2 Section 18. Use this baseline for subsequent work when its prerequisites and governing gates are met. This record does not assert Class A committee quorum, independent review, funding, licence clearance, test success, remediation completion or production release. No test, evidence or work-package completion value has been changed to imply otherwise.

### Change control

Version 0.2 records owner adoption and decision dispositions, without changing the controlling directive or requirement identifiers. Future choices must name the selected option or value, responsible person, date and supporting evidence. Requirement or contract changes need a recorded change decision. The companion tracker records implementation progress separately from this approval.
