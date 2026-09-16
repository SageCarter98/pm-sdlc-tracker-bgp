# Data retention, legal hold and disposal policy (REQ-048)

**Status: drafted 2026-09-16, not independently reviewed.** See [README.md](README.md).

REQ-048 (blueprint line 458-464): "Define retention floor, legal hold and authorised disposal;
preserve actor attribution within retention and clarify decision retention." Verification
TST-048: "Policy review resolves retention conflicts before implementation; hold blocks eligible
disposal and records its basis."

This is a **policy proposal** for independent review, not an implemented control. No
retention-enforcement code (scheduled purge job, legal-hold flag, disposal audit) exists yet
anywhere in the repository — that is correctly out of scope for WP02, which is discovery and
decisions, not implementation. Implementation belongs to whichever work package owns each table
once it's built (WP03/WP04 for what exists today; WP06/WP07/WP08 for Project/Evidence/Decision/
Audit tables).

## Proposed retention floors, by table (tables that exist today)

| Table | Proposed retention floor | Rationale |
| --- | --- | --- |
| `users` | Life of account + a proposed 30-day post-deletion grace window before hard delete, to allow accidental-deletion recovery. | No blueprint-mandated figure found; this is a proposed default, explicitly flagged for independent review, not a settled number. |
| `memberships` | Same as `users` — deactivate (`active=false`) rather than delete on removal, preserving historical attribution. | `Membership.active` already exists as a soft-delete flag (`models.py` line 81); retention policy should formalise that this flag, not row deletion, is the removal mechanism. |
| `invitations` | Proposed: purge unaccepted invitations 90 days after `expires_at`. Accepted invitations retained indefinitely alongside the resulting membership, since they document how access was granted. | No blueprint figure found for this specific case; proposed default only. |
| `mfa_recovery_codes` | Retain used and unused codes for the life of the associated user's MFA enrolment (do not purge early — REQ-002 requires audit of recovery use). | Ties to REQ-002's re-enrolment-after-use requirement, which needs the history of which code was consumed and when. |
| `templates` / `template_versions` | Published versions retained indefinitely (immutability requirement, REQ-011) — a project may reference a version years later. Draft (unpublished) versions: no floor proposed yet, pending REQ-018 ("evidence reference can be cleared", tracker TR05) review. | Blueprint §5.2: "Published immutable"; deletion of a published version that a project still references would violate REQ-011's own guarantee. |
| `tenant_access_events` | Proposed: minimum 12 months, matching typical security-log retention norms — **not a blueprint-stated figure**, flagged for independent confirmation. | REQ-005's own audit purpose (sponsor visibility into out-of-membership access) is undermined by short retention; no blueprint number was found to defer to instead. |

## Tables not yet built (planned surface, WP06-WP09)

Retention floors for `EvidenceItem`/`EvidenceRevision`, `DecisionRecord`/`Manifest`,
`AuditEvent`/`Checkpoint`, and `ExceptionRecord` are **not proposed here** — inventing numbers for
tables that don't exist yet would be exactly the kind of unverifiable claim this project's
governance process exists to prevent. What the blueprint does already settle for these, and what
this policy must respect once they're built:

- **Decision retention** (REQ-048's own phrase, blueprint §5.2 `DecisionRecord`): "Append-only";
  no UPDATE or DELETE endpoint exists in the approved API contract (§5.3) — meaning decision
  retention is effectively indefinite by design, not a policy choice this document needs to make.
- **Actor attribution preserved within retention** (REQ-048's own phrase): every audit-adjacent
  table already carries an actor reference in its planned schema (`AuditEvent`: "Actor,
  before/after..."; `DecisionRecord`: "actor, authority snapshot..."). The policy constraint is:
  whatever retention floor is eventually set for these tables, actor attribution must not be
  stripped or anonymised before that floor expires — anonymising early would defeat the audit
  purpose these tables exist for.
- **Deletion cascades must not erase decision or audit history** (blueprint §5.2, stated as a
  required constraint on the data model generally) — this must be checked at migration-review
  time for every future foreign key from a tenant-owned child table into these, not assumed.

## Legal hold (proposed mechanism, not yet built)

Blueprint §5.2 lists `ExceptionRecord` with "start, expiry, revocation" fields but no explicit
legal-hold flag anywhere in the current data model. Proposed for independent review when WP07 is
scoped: a hold should be modelled as its own record (actor, scope, basis, start, and either an
expiry or explicit revocation) that **blocks disposal for the rows in its scope regardless of
their own retention floor having passed** — matching TST-048's verification text exactly ("hold
blocks eligible disposal and records its basis"). Not designing the full schema for this now;
flagging the requirement so it isn't lost by the time WP07 starts.

## Open questions for independent review

1. Are the proposed floors above (30-day grace, 90-day invitation purge, 12-month access-event
   retention) acceptable, or does KenAddme governance / applicable law set a different floor?
   None of these numbers come from the blueprint — they are this drafting pass's proposals only.
2. Should `mfa_secret` (flagged separately in `threat_model_and_privacy_assessment.md` as stored
   in the clear) be subject to a *shorter* retention/rotation cycle than the rest of the user
   record, independent of REQ-045's broader secrets-storage work?
3. Who is the accountable owner for actually building and running disposal jobs once retention
   floors are approved — this document proposes floors, it does not assign implementation
   ownership.
