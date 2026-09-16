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

`Membership.role` (`backend/app/models.py` line 80) is a free-text `String(30)` column — the
six roles above are not yet enforced as a fixed enumeration anywhere in the schema or validated
role set. `app/rule_engine.py`'s `TemplateSchema.roles` is a template-defined list, not
necessarily this fixed platform role table — the two are related but not proven identical.
**Gap, not rounded up**: confirming that every code path which checks a user's role actually
draws from this exact six-role table (and rejects anything else) has not been verified as part of
this document and should be checked when WP06/WP07's authorization logic (Project/Decision
routes) is built, since none of that exists yet to check.
