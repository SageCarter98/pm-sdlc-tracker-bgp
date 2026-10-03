# DEC07 vocabulary indirection — design spec

Status: **approved** 2026-10-03 (PR #14, `APPROVED` by kenAddme; REQ-018 interpretation ruled by owner in session)
Owner: this session, spec on branch `SageCarter98/dec07-vocabulary-indirection-spec`
Implementation: not started; no code branch cut, by design (see §7)
Tracker rows this closes evidence toward (not the whole row):
`docs/DEFECT_REGISTER.md` `DEC07-Q11 vocabulary indirection`; closes DEC07 Q12

## 1. Context

Building DEC07 Q11/Q12's third framework fixture (PR #12, `f55e5c7`) was
run as a spike first, on Q11's own reasoning that an agile no-gate
framework "is more likely to surface real gaps in the rule/data model than
a second gate-based framework would — that is the point of choosing it."

It surfaced six, recorded as the `DEC07-Q11 vocabulary indirection` row.
The short version: **a template declares its own vocabulary and the engine
honours almost none of it.**

1. `TemplateSchema.statuses` is read by **no** readiness path. Readiness
   matches the literal `"Complete"` (`routers/decisions.py:125`,
   `routers/projects.py:532`).
2. The authoring UI nonetheless *offers* the declared list
   (`webapp/router.py:443,527,574`), so a user picks "Met", receives a
   `201`, and readiness still reports "has not been marked Complete".
3. An undeclared status (`"Bananas"`) is accepted `201`; `statuses`
   constrains nothing.
4. REQ-018's "no Complete without a reference" is keyed to the same
   literal (`routers/projects.py:649`), so a required hard item can reach a
   done-meaning status with **no reference at all**.
5. `_outcome_eligibility` / `_permitted_outcomes` match the Blueprint's
   five English outcome words, so a template declaring "Increment
   accepted" gets `permitted_outcomes: []` and a `422`.
6. `evaluate_condition` has **exactly one call site** in the application
   (`routers/projects.py:189`, on `rule.applicability`). A rule's
   `conditions` tree is validated for depth, the 200-node cap and the
   operator vocabulary, then never walked for readiness. `required_fields`
   has no consumers at all.

A seventh, found while writing this spec: **seeding hardcodes
`status="Not started"`** (`routers/projects.py:204,218`). The platform
itself writes a status the agile template never declares.

### Why this survived six work packages

**REQ-010 is a Must**: "Version framework templates containing tracks,
gates, classification, role, **status**, **decision** and applicability
schemes." But its verification, **TST-010**, only requires that "three
distinct framework fixtures represent expected classes, roles and gates
without application code changes" — *classes, roles, gates*. Status and
decision schemes are in the requirement and absent from its test. Three
fixtures were built, all declaring `"Complete"` and the Blueprint's outcome
words, so nothing ever exercised the difference.

This spec treats that as the root cause worth fixing, not just its
symptoms: the test that was meant to prove generality tested a narrower
claim than the requirement made.

### Constraints inherited, not chosen

- **REQ-011**: published template versions are immutable; a project binds
  to one version. So nothing may be migrated or rewritten in place.
- **REQ-013**: configurable rules restricted to a *versioned declarative
  vocabulary*; no executable code. `vocabulary_version` is the existing
  mechanism.
- **DEC07 Q10**: "Stamp `vocabulary_version` on every template version so
  old templates evaluate identically forever, regardless of later
  vocabulary changes", and "rules must be pure functions of project state
  plus a supplied 'as at' timestamp — no external calls, no wall-clock
  reads inside the rule itself."
- **REQ-018**'s own text contains the word "Complete" ("do not allow
  removal of required evidence while Complete"). Read as a **state
  concept, not a mandated string literal** — see the recorded ruling
  below, which settles this.

### Decisions taken by the owner in session, 2026-10-03

1. `conditions` **is** to be evaluated, **narrowly**: facts limited to the
   occurrence's own evidence-item states. No project-state fact pipeline.
2. Status and outcome semantics declared as **structured entries**, with
   plain strings still accepted.
3. Backward compatibility via **bumping `vocabulary_version` to 3**, not a
   second version field and not shape inference.
4. `required_fields` stays **advisory** and out of scope.
5. A satisfying status may carry `requires_exception`.
6. **Q12 stays open until this work lands.**
7. **REQ-018 interpretation, ruled 2026-10-03 (owner, in session):**
   "Complete is a state concept not a literal." This is the recorded
   interpretation decision §8 required before implementation, and it is
   what licenses G3. Consequence, stated so nobody has to re-derive it: the
   literal string `"Complete"` carries no special meaning in a v3 template,
   and a framework's own completion word is as valid as the Blueprint's.
   The string retains its meaning for vocabulary 1 and 2 templates only,
   via normalisation (§4.1), which is a compatibility mechanism rather
   than a statement about the requirement.

## 2. Goals

- G1. A v3 template's declared statuses genuinely drive readiness; the
  literal `"Complete"` disappears from every readiness path.
- G2. A v3 template's declared decision outcomes are genuinely recordable;
  the Blueprint's five English words disappear from eligibility logic.
- G3. REQ-018's control keys on *semantics* (`satisfies`), so it cannot be
  walked past by a framework whose completion word differs.
- G4. A status not declared by the bound template is **rejected**, not
  stored.
- G5. `rule.conditions` is evaluated for readiness against evidence state,
  making DEC07 Q10's `count`/`not`/`gte`/`lte` operators load-bearing
  rather than decorative.
- G6. Every already-published template (vocabulary 1 and 2) evaluates
  **identically** to today, with no migration and no backfill.
- G7. The initial status of a seeded item comes from the template, not a
  literal.
- G8. TST-010's gap is closed: generality is tested for statuses and
  decisions, not only classes, roles and gates.

## 3. Non-goals / explicitly out of scope this pass

- **`required_fields` enforcement.** There is no mechanism to *supply*
  named fields; enforcing it means designing an evidence-payload shape.
  Separate work. It stays advisory and will be documented as such in
  `rule_engine.py` so the next reader does not assume otherwise.
- **A project-state fact pipeline** (dates, class attributes, derived
  counts). This was the "Full" option and is its own work package.
- **`permitted_role_ids` enforcement.** Recorded as an *unverified lead*
  in the register — it appears consulted only for my-work routing
  (`routers/projects.py:527`) and not on revision submission. Must be
  probed before it is designed; not bundled here.
- **The guided authoring form offering the full operator set.** The
  separate UI pass DEC07 already anticipates.
- **Changing any already-published template.** Forbidden by REQ-011.
- **Retrofitting the agile fixture in place.** It is published at
  vocabulary 2 and immutable; it gets a *new version* instead (§7).

## 4. Architecture

### 4.1 Status semantics

`TemplateSchema.statuses` becomes `list[str | StatusDefinition]`:

```python
class StatusDefinition(BaseModel):
    id: str = Field(max_length=30)       # see §5 on the column width
    satisfies: bool = False
    requires_exception: bool = False
    initial: bool = False
```

Normalisation happens once, at validation, into an internal lookup
`dict[str, StatusDefinition]`. A plain string normalises per
`vocabulary_version`:

- **v1 / v2**: `satisfies = (id == "Complete")`, `initial =
  (id == "Not started")`. This is exactly today's behaviour, expressed as
  data rather than as a literal in a branch. **This is what makes G6 true
  without a migration.**
- **v3**: a plain string normalises to `satisfies=False, initial=False`.
  Semantics must be stated, never guessed.

v3 validation rules:

- Exactly **one** entry with `initial: true`.
- At least **one** entry with `satisfies: true` — a template whose items
  can never be satisfied is a template nobody can finish, and that is an
  authoring error worth catching at publish time rather than discovering
  at a gate.
- `requires_exception: true` is only meaningful with `satisfies: true`;
  the combination `satisfies=False, requires_exception=True` is rejected
  rather than silently ignored.
- Every `id` unique, and ≤ 30 characters (§5).

### 4.2 Outcome semantics

`decision_outcomes` becomes `list[str | OutcomeDefinition]`:

```python
class OutcomeDefinition(BaseModel):
    id: str
    kind: Literal["approving", "conditional_approving", "recording"]
```

The three kinds carry exactly the behaviour `_outcome_eligibility`
currently hardcodes:

| kind | Blueprint equivalent | Requires |
| --- | --- | --- |
| `approving` | `Approve` | no hard **and** no conditional blockers |
| `conditional_approving` | `Approve with conditions` | no hard blockers; conditions payload with owner + future deadline |
| `recording` | `Hold`, `Redirect`, `Terminate` | nothing; recorded outcomes, not approvals |

Plain-string normalisation for v1/v2 reproduces the current mapping
exactly: `Approve` → `approving`, `Approve with conditions` →
`conditional_approving`, `Hold`/`Redirect`/`Terminate` → `recording`. Any
other plain string at v1/v2 normalises to **no kind**, preserving today's
honest refusal ("declared by the template but not handled by this
prototype's decision logic") rather than quietly inventing a semantics for
it.

At v3, every outcome must declare its `kind`; a plain string is
**rejected**.

That is deliberately *asymmetric* with statuses, where a v3 plain string is
accepted and normalises to non-satisfying (§4.1). The reason: a
non-satisfying status is a perfectly ordinary thing to declare ("Not met",
"In progress"), so the safe default is meaningful and silence is harmless.
An outcome with no `kind`, by contrast, is unusable — it can never be
recorded — so accepting it would only let an author publish a template
containing a decision outcome that 422s at the moment someone tries to use
it. Rejecting at publish time turns a gate-day surprise into an authoring
error.

### 4.3 Readiness

`_compute_readiness` (`routers/decisions.py`) stops comparing to
`"Complete"`. It resolves the bound schema's status lookup and asks
`status_def.satisfies`. Two consequences worth stating:

- An **unknown** status (possible only on legacy rows, since §4.6 rejects
  new ones) is treated as **not satisfying** — fail closed, consistent
  with the engine's existing unknown-fact rule.
- `requires_exception` statuses satisfy readiness **only** when a valid
  `ExceptionRecord` covers the item, reusing the existing
  `_exception_is_currently_valid` path (REQ-020). Without this, adding a
  satisfying status would be a legitimate-looking route around a hard
  blocker — the precise failure mode this spec exists to close, so it must
  not be reintroduced by the fix.

`routers/projects.py:532`'s own `== "Complete"` (the my-work progress
count) resolves through the same lookup, so the two cannot drift.

### 4.4 Conditions evaluation

A rule's `conditions` is evaluated when readiness is computed, against a
fact dict built from **the occurrence's own evidence items** and nothing
else:

```
fact "item:<rule_id>"  ->  "satisfied" | "unsatisfied" | "not_applicable"
```

Rules, derived from the narrow-scope decision:

- **The namespace is closed.** Only `item:` facts exist. An unknown fact
  fails closed, as today.
- **Same-occurrence only.** A rule cannot read another occurrence's or
  another project's evidence — that would make a sprint-2 check depend on
  sprint-1 answers, which REQ-016 exists to prevent.
- **Purity holds.** The fact dict is derived from committed rows plus the
  supplied `as_at`; no clock read inside a rule, no external call. DEC07
  Q10's requirement is preserved verbatim.
- **No cycles.** An item's own satisfaction may not depend on its own
  `conditions` result. Enforced by evaluating conditions over *stored
  statuses only*, never over other items' freshly-derived condition
  results — a single pass, no fixpoint, no ordering dependence.
- **Interaction with status.** Both must hold: an item counts as satisfied
  when its status `satisfies` **and** its `conditions` evaluate true.
  `conditions` can only ever *withhold* satisfaction, never grant it. This
  keeps the human attestation necessary and makes the machine check an
  additional gate rather than a replacement — important because the human
  statement is the auditable act.
- At v1/v2, `conditions` is **not** evaluated (G6).

### 4.5 REQ-018

`routers/projects.py:649` becomes: reject when the incoming status
`satisfies`, the item is `required`, and no reference is supplied. Keyed on
semantics, so the agile fixture's "Met" is caught exactly as "Complete" is
today — closing sub-finding 4.

### 4.6 Revision validation

`create_evidence_revision` rejects a status the bound template version does
not declare (`422`), closing sub-finding 3. This is the one change that can
break an existing caller, so §7 addresses it.

### 4.7 `vocabulary_version` 3

`OPERATORS_BY_VOCABULARY_VERSION` gains version 3 with the **same operator
set as 2** — this bump is about semantics, not operators. The version is
the single knob pinning evaluation behaviour, per DEC07's own words. The
docstring will say plainly that v3 changes status/outcome/condition
semantics and not the operator vocabulary, so the next reader is not left
inferring it.

## 5. Data model / migration changes

**No migration, and no schema change to any table.** This is a deliberate
property, not luck: `EvidenceItem.status` is already a free string, and
every existing row belongs to a project bound to a v1/v2 template version,
whose normalisation (§4.1) reproduces today's meaning. REQ-011's
immutability is what makes this safe.

One real constraint discovered while writing this spec, and the reason
`StatusDefinition.id` is capped: **`EvidenceItem.status` and
`EvidenceRevision.status` are `String(30)`** (`models.py:327,356`). A
template declaring a 40-character status would validate happily and then
fail at revision time with a database error. Validation must reject
`len(id) > 30` at publish time. (The agile fixture's longest, "Waived for
this increment", is 27 — it fits, but only barely, which is exactly why
this needs a guard rather than a comment.)

## 6. Testing plan

- **The seven `test_gap_*` tests in `test_dec07_q11_agile_fixture.py` are
  rewritten, not deleted.** Each becomes its positive counterpart against a
  v3 fixture: declared statuses drive readiness, an undeclared status is
  rejected, REQ-018 catches "Met" without a reference, declared outcomes
  are recordable. Their docstrings already instruct this ("Update the
  assertion; do not restore the old behaviour"), so this is the plan those
  tests were written to serve.
- **Back-compat is tested directly, not assumed.** The three existing
  fixtures (`standard`, `regulated`, `lightweight`, all v1/v2) must produce
  byte-identical readiness and identical permitted outcomes before and
  after. This is G6's only real proof.
- **New: a v3 agile fixture** that actually completes an item and records
  an "Increment accepted" decision end to end — the thing Q12 asks for.
- **Conditions evaluation**: an item whose status satisfies but whose
  `conditions` are false stays unsatisfied; the `count(...)`-of-items rule
  from DEC07 Q10's own motivating example works; a cross-occurrence fact
  reference fails closed.
- **TST-010's gap (G8)**: extend `test_framework_fixtures.py` so fixture
  distinctness covers **status and outcome schemes**, not just classes,
  roles and gate counts. This is what would have caught the whole defect.
- **Adversarial**: a `requires_exception` status without a valid exception
  does **not** satisfy readiness; a 31-character status is rejected at
  publish; a v3 template with two `initial` statuses is rejected; a v3
  template with no satisfying status is rejected.
- Every new assertion is to be watched failing before its implementation,
  per this project's existing practice.

## 7. Rollout

1. Ship the schema, normalisation and validation with v3 **accepted but
   unused** — no fixture or template declares it yet. Back-compat tests
   prove v1/v2 behaviour is untouched.
2. Re-point readiness, REQ-018 and outcome eligibility through the lookup.
   Still no behaviour change, because every existing template is v1/v2.
3. Publish **version 2 of the agile template** at `vocabulary_version: 3`
   with real semantics. The v1 fixture file stays as it is — immutable per
   REQ-011, and still the artefact the characterization tests described.
4. Rewrite the `test_gap_*` tests against the v3 version; **Q12 closes
   here**, and not before.
5. Lift the validation fixture's `validation_fixture` flag only if the
   owner decides it has "passed its own review" (Q12's wording). That is a
   governance decision, not part of this implementation.

**The one caller-visible risk is §4.6.** Rejecting undeclared statuses is
correct but is a behaviour change for any existing client sending an
arbitrary string. Mitigation: it applies only to projects bound to a v3
template version, of which there are none until step 3. No existing caller
can be broken by steps 1-2.

## 8. Risks / open questions carried forward, not silently resolved

- ~~**REQ-018's "Complete" is being read as a concept, not a literal.**~~
  **RESOLVED 2026-10-03** by owner ruling — see §1 decision 7. Kept here
  rather than deleted, because this spec's whole argument for G3 rests on
  that interpretation, and a future reader is entitled to see that it was
  raised as a genuine risk, put to the owner, and answered, rather than
  assumed by whoever wrote the code.
- **`conditions` can only withhold, never grant** (§4.4). Defensible — it
  keeps the human attestation load-bearing — but it does mean a fully
  automatable check still needs a person to assert it. If the owner wants
  machine-only satisfaction, that is a different design and a governance
  question about what an auditable act is.
- **Only `satisfies` is modelled, not a general status state machine.**
  No "which transitions are legal" concept. Deliberate: nothing in the
  requirements asks for it, and REQ-017's immutable-revision model already
  records every transition. Flagged because a reviewer might expect one.
- **TST-010's requirement-vs-verification mismatch is wider than this
  spec.** G8 closes it for statuses and decisions. Nobody has checked
  whether other REQ/TST pairs have the same shape of gap — worth a pass,
  not in scope here.
- **`required_fields` stays inert** (§3) and the register row stays open
  for it. Documented, not fixed.
- **This spec is not a gate decision** and does not satisfy any PM or
  SDLC gate. It closes evidence toward the register row and Q12 only.
