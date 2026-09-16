# Assurance plan (REQ-057)

**Status: drafted 2026-09-16, not independently reviewed.** See [README.md](README.md).

REQ-057 (blueprint line 496-510): "Fund and schedule independent assurance and benefits review;
Class A benefits review is interim at three months and formal at six." Verification TST-057:
"Approved plan identifies assurance capacity and protected benefits-review effort without
inventing allocations."

That verification text is a direct instruction against exactly the failure mode this document
must avoid: **this plan identifies what needs scheduling and who the named roles are; it does not
invent budget figures, hours, or capacity commitments that haven't actually been approved.** Where
a number would be needed and none has been approved, that is stated as an open gap, not filled in.

## Named roles (per DEC01, resolved 2026-09-15)

- **Delivery lead**: Freston Kenny Adedeme.
- **Independent reviewer**: Milton. Per `TRACKER.md`'s own caveat (recorded 2026-09-15): naming
  Milton as reviewer is not the same as confirming his independence from delivery work, or his
  role acceptance — neither has been separately confirmed as of this document's drafting.
- **Sponsor** and **technical owner**: still unnamed (tracker item G0.03, id 86, "In progress").
  This plan cannot schedule sponsor-dependent assurance activities (e.g. Gate decisions requiring
  Sponsor concurrence for PM Class A per the PM Framework) with a real date until that name exists.

## Independent assurance activities this project requires

Per the blueprint's own work-package table (§6) and requirements catalogue:

| Activity | Owning work package | Required by | Status |
| --- | --- | --- | --- |
| Independent threat/privacy review (this WP02 draft) | WP02 | REQ-044 | Drafted, awaiting Milton's review. |
| Independent penetration test before general availability | WP13 | REQ-050 | Not started — WP13 depends on WP09, WP11, WP12, none of which are built yet. No pen-test vendor, budget, or date exists; this plan does not invent one. |
| Independent/specialist QA for verification testing (Class 3 SDLC requirement, per `~/.claude/frameworks/KenAddme_SDLC_Framework_v1.2.md` G4 approver rules) | WP13/G4 | SDLC G4.04, G4.09 | Not started. |
| Independent verification path for integrity/recovery (separate from the operational build) | WP08 | Blueprint §6 WP08 deliverable | Not started — WP08 depends on WP07 and WP02 (this document). |

## Benefits review schedule (Class A: interim at 3 months, formal at 6)

The blueprint gives the *cadence* (3-month interim, 6-month formal) but not a start date — this
project has no recorded go-live or "clock start" date yet (no PM Gate has been decided; see
`tracker status`, all PM gates "Not yet held"). This plan therefore states the rule, not a
calculated calendar date:

- **Interim benefits review**: due 3 months after whichever date the Sponsor/Project Authority
  formally treats as this project's start (most likely PM Gate 2, "Project authorisation" —
  currently 0/12 items complete, decision "Not yet held"). **No date is calculated here because
  that anchor hasn't happened yet** — calculating one now would be inventing an allocation the
  verification text explicitly warns against.
- **Formal benefits review**: due 6 months after the same anchor.
- Once a Gate 2 decision is recorded, this document (or the tracker's own gate/exception
  fields) should be updated with the two actual calendar dates that follow from it.

## Assurance capacity — the "protected effort" requirement

TST-057 asks the plan to "identify assurance capacity... without inventing allocations." As of
2026-09-16, this project has:

- One delivery lead (also currently the sole committer/author of all code).
- One named independent reviewer (Milton), whose *availability and capacity* (hours/week,
  competing commitments) has not been discussed or recorded anywhere this document could find.

**Open gap, not filled in**: there is currently no protected, scheduled time allocated for
Milton's review work, for the eventual penetration test, or for independent QA. This plan cannot
responsibly assign a number of hours or a percentage of anyone's time without that having been
actually agreed — doing so would violate TST-057's own verification criterion. The concrete next
action is for the delivery lead and Sponsor (once named) to agree a real allocation, which this
document should then be updated to record — not for a drafting pass to guess one.

## Funding

No budget has been recorded anywhere in this repository or the blueprint pack for pen-testing,
independent QA, or reviewer time. REQ-052 (blueprint line 496-502, WP01) already requires staying
"within approved scope and external-commitment limits" and that "production, budget and supplier
decisions are separately recorded" — consistent with that, this document does not propose a
budget figure. Funding is an open item for the Sponsor once named.
