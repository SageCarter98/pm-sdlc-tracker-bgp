# Role vocabulary indirection — design

**Status:** awaiting owner review (written 2026-10-04). Not approved, not started.
**Supersedes nothing.** Sibling of `2026-10-03-dec07-vocabulary-indirection-design.md`.
**Register row closed by this work:** "Declared role vocabulary is not honoured (the DEC07 gap, in `roles`)".

---

## 1 Problem

A framework template declares its own `roles`, and every rule's `permitted_role_ids`
must reference them — validated in `rule_engine.py` ("references undeclared role(s)").
But the engine does not honour that vocabulary anywhere it matters:

1. **Project membership roles come from a fixed platform enum.** `models.Role`
   (`contributor`, `approver`, `sponsor`, `assurance_reviewer`,
   `tenant_administrator`) is what `POST /orgs/{tenant_id}/projects` accepts for a
   member. A template declaring `developer` cannot have anyone assigned to it —
   the request is refused 422 by the platform enum, not by any framework rule.
2. **Decision authority is keyed to hardcoded role names.**
   `decisions.py:33` holds `DECISION_AUTHORITY_ROLES = {"approver", "sponsor",
   "tenant_administrator"}`, consulted at `:98`, `:506`, `:516` and `:544` — who may
   decide a gate, and who counts as an independent compensating reviewer under
   REQ-006.

Measured across the shipped fixtures on 2026-10-04:

| fixture | declared roles | platform-assignable |
| --- | --- | --- |
| `standard`, `lightweight`, `regulated` | contributor, approver, sponsor, assurance_reviewer | all |
| **`agile.json`, `agile.v3.json`** | product_owner, developer, facilitator | **none** |

So for a framework that brings its own role names, `permitted_role_ids` can never
match any member's role, and no declared role can ever decide a gate. This is the
same defect class as DEC07-Q11 — a declared vocabulary validated and then ignored —
in the one remaining field of REQ-010's list.

### 1.1 What is already in place, and why this is the remainder

`permitted_role_ids` was entirely unenforced until 2026-10-04 (PR #16, `e735e71`),
and attachment upload until PR #17 (`3c2696d`). Those fixes made the restriction
real *where the declared roles happen to be platform roles*, and deliberately fall
back to membership-only where none of an item's declared roles is assignable —
because enforcing strictly there would have made every item in a custom-role
framework attestable only by a tenant administrator or the assigned owner. That
fallback is this spec's remaining fail-open path, pinned by
`test_an_unassignable_role_vocabulary_falls_back_to_membership`.

## 2 Requirement alignment

- **REQ-010 (Must)** — "Version framework templates containing tracks, gates,
  classification, **role**, status, decision and applicability schemes." A versioned
  role scheme is explicitly required. This work closes an unmet Must; it is not new
  scope. DEC07 closed the status and decision schemes of the same sentence.
- **REQ-013 (Must)** — "Restrict configurable rules to a versioned declarative
  vocabulary; prohibit executable code and invariant overrides." Role capabilities
  are declarative data (booleans on a declared id), never expressions, and are
  versioned by `vocabulary_version` like every other vocabulary change.
- **REQ-015 (Must)** — "Create a project with name, template binding, class, owner
  and explicit members." Unchanged: members stay explicit. Only the permitted *value*
  of a member's role widens, and only for a v4 binding.
- **REQ-006 (separation of duties)** — preserved and strengthened: the compensating
  reviewer test stops keying on hardcoded English role names and starts keying on
  what the bound template says carries decision authority.
- **Blueprint §2 authority model** — the six product roles are the platform's
  authority model, with authority boundaries stated per role ("Approver … requires
  current role, project scope, MFA and separation checks"; "Contributor … cannot
  approve solely because they uploaded evidence"). They are *not* framework
  vocabulary. §4 below states the invariant that keeps them intact.

### 2.1 Unverifiable, recorded rather than claimed

REQ-010 maps to **WP05 "Templates and rule interpreter"**, acceptance criteria
**AC08 and AC09**. Those criteria are defined in **Directive v1.2, which is not
present in this repository**, so this design has **not** been checked against them.
Owner instructed on 2026-10-04 to proceed on the Blueprint alone rather than locate
the Directive first. Treat alignment with AC08/AC09 as unverified, not as satisfied.

A related observation, recorded so the pattern is not missed a second time: WP05 is
nominally delivered while a REQ-010 element — the role scheme — was never
implemented. That is the same requirement-versus-verification mismatch TST-010 had
for statuses and decisions (the root cause DEC07's Task 8 closed). It warrants its
own defect-register row, and nobody has checked whether other REQ/TST pairs share
the shape.

## 3 Goals

- **G1** A template may declare roles with semantics: which may supply evidence,
  and which may decide a gate.
- **G2** `permitted_role_ids` resolves against the bound template's declared roles,
  with no platform-enum dependency, for a v4 binding.
- **G3** `DECISION_AUTHORITY_ROLES` is replaced by declared capability at all four
  call sites.
- **G4** A member may be assigned any role the bound template version declares.
- **G5** Vocabulary 1–3 behaviour is bit-identical (the G6 obligation DEC07
  established, renumbered here as G5 to avoid collision).
- **G6** The unassignable-role fallback becomes unnecessary for v4 bindings and is
  scoped to `vocabulary_version < 4` rather than deleted.
- **G7** No migration and no table change.

### 3.1 Non-goals

- Tenant-level `Membership.role` stays the fixed platform enum. It gates MFA
  (`ROLES_REQUIRING_MFA`) and endpoint-level `require_role`, which are platform
  concerns; a tenant exists before any template is bound, so there is nothing to
  resolve a declared role against at that point.
- No change to `applicability` (still the one live `evaluate_condition` call site
  whose fact is never supplied — its own open register row).
- No change to `required_fields` (still inert — its own open register row).
- No rebinding of existing projects to a v4 template version. A project binds one
  immutable template version (REQ-015, `models.py:242`) and there is no rebind path,
  so a member's declared role cannot be invalidated by a later version.

## 4 The binding invariant

> **A declared role narrows authority within the Blueprint's model. It never grants
> authority the holder's tenant role lacks.**

Concretely: a template-declared role with `decides: true` makes its holder *eligible*
to decide a gate. It does not let them reach the decision endpoint. That still
requires a tenant role of `tenant_administrator` or `approver`
(`require_role` on the decision route) and MFA where
`ROLES_REQUIRING_MFA` demands it. The practical effect is an **intersection**:
decision authority = (tenant role permits it) AND (bound template's declared role
says this role decides).

The code already behaves this way, because the endpoint guard precedes any project
role check. Relying on that implicitly is how the two defects fixed on 2026-10-04
arose, so this becomes an explicit, separately tested constraint rather than an
emergent property.

**Fail closed:** a role whose definition cannot be resolved decides nothing and
attests nothing; a template declaring no decider is invalid (§5.2).

## 5 Design

### 5.1 Schema

`roles` accepts structured entries alongside plain strings:

```json
"roles": [
  {"id": "product_owner", "attests": true, "decides": true},
  {"id": "developer", "attests": true},
  {"id": "facilitator", "attests": true}
]
```

- `attests` defaults **true**; `decides` defaults **false**. Supplying evidence is
  the common case; granting approval is the deliberate act.
- Plain strings keep parsing and normalise per `vocabulary_version`, exactly as
  statuses and outcomes do.
- A `_LEGACY_ROLE_CAPABILITIES` map gives vocabulary 1–3 today's meaning:
  `approver`, `sponsor` and `tenant_administrator` decide; every declared role
  attests. This reproduces `DECISION_AUTHORITY_ROLES` exactly and is what G5 pins.

### 5.2 Validation (vocabulary 4)

Mirroring the status rules DEC07 established:

- Role ids capped at **30 characters** — `ProjectMembership.role` is `String(30)`.
- No duplicate role ids.
- **At least one role with `decides: true`.** A template whose gates nobody can
  approve is broken, not valid — symmetric with "at least one status with
  `satisfies: true`".
- `permitted_role_ids` must reference declared role ids (unchanged, already enforced).
- **Every id in a rule's `permitted_role_ids` must reference a role with
  `attests: true`.** Without this, a template could nominate a role to supply
  evidence and simultaneously declare that it cannot — a self-contradiction that
  would be resolved silently at runtime by the `attests` check refusing everyone the
  rule names. Rejecting it at publish time removes the contradiction class instead
  of leaving it to be debugged later. (This is why §5.3's attest check tests both
  conditions: the conjunction is belt-and-braces once validation holds, and the
  `attests` half is what protects a legacy or hand-edited row.)

As with DEC07's I1 fix, the length and duplicate checks apply to any entry that
arrives **structured**, at any vocabulary version — a structured entry cannot exist
in a template published before this work, so gating those two checks behind v4
protects nothing.

### 5.3 Resolution

`TemplateSchema.role_lookup() -> dict[str, RoleDefinition]` joins `status_lookup()`
and `outcome_lookup()` in `rule_engine.py`, keyed by role id, order-preserving,
serving v1–3 through the legacy map.

- **Attest** — `_require_permitted_to_attest` (`routers/projects.py`) resolves the
  submitter's project role through `role_lookup()` and requires
  `definition.attests` **and** membership of the item's `permitted_role_ids`. The two
  existing exemptions — assigned `owner_user_id`, tenant administrator — stay
  unchanged, each already pinned by its own test.
- **Decide** — `DECISION_AUTHORITY_ROLES` is deleted. Its four call sites
  (`decisions.py:98`, `:506`, `:516`, `:544`) ask the bound schema whether the role
  decides. **Tenant administrators keep decision authority unconditionally**, the
  same carve-out the attest path has, so a template cannot lock its owner out of its
  own gates.

### 5.4 Membership assignment

`POST /orgs/{tenant_id}/projects`'s member `role` field becomes a validated string
rather than a platform-enum-typed field, and the accepted set depends on the bound
version — this is the whole of the change, stated explicitly because "validated
string" alone is ambiguous:

- **`vocabulary_version >= 4`** — accepted values are exactly the ids the bound
  version's `role_lookup()` declares. An undeclared role is refused **422** naming
  the declared list, mirroring the undeclared-status refusal.
- **`vocabulary_version < 4`** — accepted values are exactly the platform `Role`
  enum, as today. Existing callers see no change whatsoever, which is what makes
  this safe to ship before any v4 template exists.

The field therefore stops being typed by the platform enum at the schema layer and
starts being validated against the binding at the handler layer, where the bound
schema is already loaded (`_load_bound_schema`, used a few lines away for class
validation).

`ProjectMembership.role` is already `String(30)` with no database enum, so **no
migration** — the same reason DEC07 needed none.

### 5.5 Rollout

Staged as DEC07 §7 was:

1. v4 ships **accepted but unused**. `VOCABULARY_VERSION` stays **2**; v4 is
   reachable only by `POST /templates/import` followed by publish. Nothing changes
   for any existing tenant.
2. An `agile.v4.json` fixture declares v4 and gives the agile framework real role
   semantics — the first artefact to exercise it, as `agile.v3.json` was for
   statuses and outcomes. `agile.json` and `agile.v3.json` stay untouched (REQ-011).
3. Bumping `VOCABULARY_VERSION` is a separate, deliberate decision, not part of this
   work. Note the standing limitation it would expose: the guided authoring UI cannot
   author structured vocabulary of any kind (its own open register row).

## 6 Testing

- **Golden back-compat (G5)** — the vocabulary 1–3 decision-authority and attest
  behaviour pinned before anything changes, in the shape of
  `test_dec07_vocabulary_backcompat.py`. These must stay green through every task.
- **Declared decider** — a v4 role with `decides: true`, held by someone whose
  tenant role permits deciding, records a decision.
- **Declared non-decider refused** — a v4 role with `decides` absent is refused,
  even for a project member whose tenant role would otherwise allow it.
- **The §4 invariant** — a `decides: true` role whose holder's tenant role lacks
  authority is still refused. This is the test that proves the design narrows rather
  than widens, and it must fail if the endpoint guard is ever reordered after the
  project-role check.
- **Compensating reviewer** — REQ-006's independent reviewer resolves through
  declared capability, with a v4 template whose decider role is not called
  "approver".
- **Validation** — 30-character cap, duplicate ids, and the at-least-one-decider
  rule, each at a default vocabulary version for structured entries.
- **Assignment** — a declared role is assignable; an undeclared one is refused 422
  naming the declared list; a v1–3 binding still accepts exactly the platform enum.
- **Fallback scoping (G6)** — the unassignable-role fallback still applies below v4
  and does **not** apply at v4.

Suite execution: this machine cannot run the suite in one process (3.46 GB RAM).
Run two test files per pytest process; the perf-budget file alone. See the project's
chunked-sweep note.

## 7 Risks

- **Authorization change.** This touches who may decide a gate. The §4 invariant and
  its dedicated test are the primary control; the golden back-compat tests are the
  secondary one. Every task's review should treat a weakened assertion here as a
  blocker rather than a style note.
- **A fourth vocabulary version.** `OPERATORS_BY_VOCABULARY_VERSION` and the
  `>= 3` gates acquire a `>= 4` sibling. DEC07 left a known wart: v3's content rules
  and wording are applied to every higher version, so a v4 template currently emits
  v3 phrasing alongside the correct error. That should be tidied as part of this
  work, not left to compound.
- **Unverified acceptance criteria.** §2.1. If the Directive is located later and
  AC08/AC09 contradict this design, the spec changes and the work stops.

## 8 Decisions

1. **Scope is attest + decide** — owner, 2026-10-04. Attest-only would leave a
   custom-role framework able to nominate evidence suppliers but nobody to approve
   its gates, and the register row half-open.
2. **Tenant roles stay platform-fixed** — they gate MFA and endpoint access, and
   predate any template binding.
3. **Structured role entries, not a separate capability map, and not a
   maps-to-platform-role alias** — owner, 2026-10-04. The capability map would make
   the `roles` list stop being the source of truth, which is how the original defect
   happened; the alias approach would make the framework's vocabulary cosmetic and
   leak platform concepts into framework definitions.
4. **Proceed without Directive v1.2** — owner, 2026-10-04, with AC08/AC09 recorded
   unverified (§2.1).
