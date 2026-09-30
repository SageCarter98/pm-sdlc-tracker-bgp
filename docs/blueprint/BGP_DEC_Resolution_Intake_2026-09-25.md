# DEC resolution intake — DEC05, DEC06, DEC07, DEC08, DEC11, DEC12

Staged 2026-09-25 so kenAddme (named owner, see the Decisions sheet in
`Build_Governance_Platform_Implementation_Tracker_v0.2_Approved.xlsx`) can
supply the actual missing content for the six decisions currently blocking
BGP-IPA-001's IPA02 and IPA04 findings (`docs/DEFECT_REGISTER.md`).

**How this gets used**: fill in the `>` answer lines below (delete the `>`
placeholder text, keep your own text), or just dictate the answers in
conversation. Once an item has a real answer, it gets transcribed into:
- the xlsx Decisions sheet's `Current position` / `Status` / `Decision
  record` / `Approval date` columns for that DEC row,
- `TRACKER.md` with the same evidence-honesty discipline as everywhere else
  in this project (a decision recorded here is checked against what's
  actually written below, not assumed).

**What this is not**: a PM/SDLC gate decision. Nothing here substitutes for
a `tracker_cli.py gate` action — those stay a named human authority's
separate, manual step regardless of how these six items resolve. A blank
item stays "Partly decided"/blocked exactly as before; there's no pressure
to fill in every line at once.

---

## DEC05 — Durability failure envelope and mechanism
**Responsible role**: Operations and security leads
**Blocks**: IPA04 (decision durability), REQ-026/027/028/029, WP08's remaining scope

Blueprint's own framing (Sec. 5.3.1 / Sec. 7): "Candidate A uses synchronous
durable replication for the approved failure domains plus independently
protected integrity checkpoints. Candidate B uses a pending intent and
independently durable receipt, with a reconciler that finalises only after
receipt verification. Do not combine their success semantics casually."

1. Candidate A or Candidate B (or a named third option)?
   > _answer here_
2. Which failure scenarios are actually covered — process crash, node
   failure, zone failure, storage failure, regional failure? Any explicit
   exclusions?
   > _answer here_
3. Who holds custody of the durability/integrity-verification mechanism
   (must it be independent of the app's own database role, per the WP08
   `bgp_owner`-was-a-superuser finding)?
   > _answer here_
4. Required availability target (if any numeric SLA is being set here)?
   > _answer here_
5. How is "success" acknowledged to the caller — synchronous ack once
   durable, or a Pending state reconciled later?
   > _answer here_

## DEC06 — Retention, disposal and attribution
**Responsible role**: Privacy reviewer and owner
**Blocks**: IPA02 (partly — data-persistence/disposal UI), REQ-048

1. Retention period(s) — same for every record type, or different per
   category (evidence, decisions, audit events, attachments)?
   > _answer here_
2. How does retention/disposal coexist with REQ-025's "decisions are never
   UPDATE/DELETE-able" guarantee — is there a genuine permanent-record
   exception, and if so for which tables?
   > _answer here_
3. Legal-hold mechanism — how is a hold placed, who can place one, what
   does it override?
   > _answer here_
4. Attribution/disposal control specifics not already covered above?
   > _answer here_

## DEC07 — Rule vocabulary and three frameworks
**Responsible role**: Technical lead
**Blocks**: IPA02 (UI08 guided template authoring), WP05's remaining scope

1. Is the current vocabulary (`eq`/`in`/`all`/`any` over declared facts, max
   condition depth 5, no eval/exec) approved as-is, or does it need to
   change? (Depth 5 is currently just this project's own working default,
   never signed off.)
   > _answer here_
2. What is the third permitted framework fixture (beyond the two already
   built as neutral synthetic fixtures under `fixtures/synthetic/frameworks/`)?
   > _answer here_
3. What is that third framework's permitted use/scope — full parity with
   the other two, or something narrower?
   > _answer here_

## DEC08 — Usability sample and performance budgets
**Responsible role**: UX and technical leads
**Blocks**: IPA04 (assurance), REQ-040/041/043, AC22

1. Sample size per user group (beginner / contributor / client approver /
   administrator), including disabled and older-device users?
   > _answer here_
2. Device and network profiles to test against (e.g., a specific
   older-phone spec, a constrained-connection profile)?
   > _answer here_
3. Numeric API p95 latency budget?
   > _answer here_
4. Numeric page/render budget?
   > _answer here_

## DEC11 — Operator access and key custody
**Responsible role**: Security lead and owner
**Blocks**: IPA04 (assurance), integrity-checkpoint custody model

1. Break-glass scope — what, specifically, can an operator do in an
   emergency that they cannot do routinely?
   > _answer here_
2. Approval path required before break-glass access is granted?
   > _answer here_
3. Tenant-visibility rule for operators (none routinely, per the blueprint
   — anything to add for the break-glass case)?
   > _answer here_
4. Independent key-custody arrangement — who holds keys separately from
   the operator role itself?
   > _answer here_

## DEC12 — Migration of legacy tracker records
**Responsible role**: Data owner
**Status**: policy already "Decided" (provenance-preserving, never invent
missing actors/approvals) — what's missing is the actual named Data owner
for real imports going forward.

1. Is kenAddme the actual Data owner for this purpose, or is this role held
   by someone else (kenAddme was named as tracker "owner" for coordination,
   which is not the same as being the substantive Data owner the policy
   requires)?
   > _answer here_
2. If/when a real (non-synthetic) import is planned, what authorisation
   and reconciliation evidence will accompany it?
   > _answer here_
