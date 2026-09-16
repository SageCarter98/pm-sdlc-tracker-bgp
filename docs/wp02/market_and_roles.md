# Market and roles

**Status: consolidation of already owner-approved content, drafted 2026-09-16.** See
[README.md](README.md). Unlike the other WP02 documents, this one makes no new claims — the
blueprint's owner (APR-001, 2026-09-15) already approved a market statement and role table in
`docs/blueprint/Blueprint_Working_Source.md` §2. This document exists so WP02 has its own
locatable evidence reference for the "market, roles" half of its deliverable line, instead of
that approval only being findable by reading the blueprint end to end.

## Market

> "The first usable increment lets a tenant choose an approved starter, create a project, assign
> evidence, resolve blockers and deliberately record a decision. Its initial discovery audience is
> small agencies and consultancies. Enterprise-scale assumptions, paid services and a universal
> rules language are not implied."
>
> — `Blueprint_Working_Source.md` §2, owner-approved via APR-001 (§9).

No additional market analysis (competitor review, pricing research, etc.) has been performed as
part of this WP02 pass — none was requested by REQ-044/048/057, and the blueprint's own market
statement above is already the owner's approved scope boundary. If a fuller market analysis is
wanted, that's a distinct piece of work this document does not attempt.

## Roles

Reproduced from `Blueprint_Working_Source.md` §2 exactly (not restated from memory):

| Role | Working responsibility | Authority boundary |
| --- | --- | --- |
| Contributor | Prepare assigned evidence and respond to corrections. | Cannot approve solely because they uploaded evidence. |
| Approver | Review the bound evidence and decide permitted progression. | Requires current role, project scope, MFA and separation checks. |
| Sponsor | See project readiness, conditions and administrator access. | Receives only explicitly granted approval powers. |
| Assurance reviewer | Inspect evidence, decisions and exports. | Read-only unless separately assigned another role. |
| Tenant administrator | Manage membership and approved templates. | Cannot edit history; non-member project access is logged. |
| Platform operator | Maintain service under recorded operational controls. | No routine evidence access or decision-edit authority. Policy DEC11 remains open. |

### What's actually implemented against this table so far

**Correction (2026-09-16, later pass): the claim originally written here was wrong** — it said
`Membership.role` was unvalidated free text. That's inaccurate. `app/models.py` defines a
`Role(str, enum.Enum)` with five of the six roles above (`contributor`, `approver`, `sponsor`,
`assurance_reviewer`, `tenant_administrator` — `platform_operator` is deliberately excluded, with
a comment explaining it's out of tenant scope, no membership row, deferred to WP12). Every write
path that sets a membership's role goes through this enum at the API boundary first:
`InviteRequest.role: Role` (`app/routers/orgs.py` line 31) is a Pydantic-typed field, so an
invalid role value is rejected before it ever reaches the database — both the initial
tenant-creator assignment (`Role.TENANT_ADMINISTRATOR.value`, line 69) and invitation acceptance
(`invitation.role`, line 120, itself only ever set from a validated `Role` at invite time) go
through it. `Membership.role`'s underlying column is still `String(30)` (no DB-level CHECK
constraint), but that's a storage detail, not an unenforced role set — the enforcement is real,
just at the application layer rather than the schema layer.

`app/rule_engine.py`'s `TemplateSchema.roles` is a separate, template-defined list (a template
author declares which of *their* framework's roles a rule permits) — related to but not required
to be identical to this fixed five-role platform enum, and that's correct: a tenant-authored
governance framework's roles (e.g. "Technical Lead", "QA Lead") are a different concept from the
platform's own membership/authority roles. Not a gap; noting it so the distinction isn't
conflated later.

This correction was found while starting WP06 and re-reading `app/deps.py`/`app/models.py`
closely enough to wire project-role checks — a reminder that a document marked "drafted, not
independently reviewed" can still contain plain errors, not just open judgment calls, and those
get fixed the moment they're found rather than left for the eventual review to catch.
