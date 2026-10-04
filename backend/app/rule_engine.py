"""Declarative rule vocabulary, Blueprint Sec.5.5. REQ-013: restrict
configurable rules to a versioned declarative vocabulary; prohibit
executable code and invariant overrides. Nothing in this module ever
evaluates a string as code -- conditions are structured data, walked by
_evaluate_condition, not passed to eval/exec or a template engine.

DEC07 Q10 (docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md
lines 119-132) resolved the vocabulary: Sec.5.5's eq/in/all/any approved
as-is, plus three additions (`not`, `gte`/`lte`, `count(...)` with a
comparison) and two tightenings (a 200-node cap alongside the depth-5
limit, and a hard evaluation timeout). It also requires rules to be pure
functions of project state plus a supplied "as at" timestamp, and a
`vocabulary_version` stamped on every template version "so old templates
evaluate identically forever, regardless of later vocabulary changes".

DEC07 closes with "Resist adding anything beyond this", so: no operator
here goes beyond that list, and `count`'s comparison reuses eq/gte/lte
rather than introducing a fourth comparison form.

DEC07 Q11's third framework fixture (a no-gate agile DoR/DoD framework) is
separate work and not implemented here.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_CONDITION_DEPTH = 5

# DEC07 tightening 1: "cap total condition nodes at 200 in addition to the
# depth-5 limit".
MAX_CONDITION_NODES = 200

# DEC07 tightening 2: "add a hard evaluation timeout". Defence in depth
# rather than the primary bound -- a tree already capped at depth 5 and 200
# nodes evaluates in microseconds, so a budget this generous should never
# be reached by a well-formed rule. Enforced as a deadline checked at every
# node (see _evaluate), not via signal.alarm (Unix-only) or a worker
# thread: this runs inside a request on both Windows dev and Linux CI.
EVALUATION_TIMEOUT_SECONDS = 1.0

# The vocabulary this build evaluates and authors against. Bumping this is
# the mechanism DEC07 asks for: a template stamped with an older version
# keeps being validated against exactly the operators that existed then,
# so adding to the vocabulary later cannot change how it behaves.
#
# Deliberately staying at 2, NOT 3, even though vocabulary 3 is fully
# implemented below (StatusDefinition/OutcomeDefinition, the lookups, and
# every v3 validation rule). Spec Sec.7 rollout step 1 requires v3 ship
# "accepted but unused -- no fixture or template declares it yet". This
# constant is the stamp every new guided-authoring draft gets
# (routers/templates.py's _BLANK_SCHEMA), so bumping it would make v3 the
# default for all new templates before the guided authoring UI can emit
# valid v3 vocabulary (its metadata form only produces plain
# comma-separated strings -- see webapp/router.py's _parse_csv use). A
# template that explicitly declares "vocabulary_version": 3 still
# validates and behaves per v3 in full; it is simply not the default.
# Do not "helpfully" bump this until the authoring UI can express v3.
VOCABULARY_VERSION = 2

# Sec.5.5: "Permitted operators are equality, membership and bounded all/any
# over declared facts. No arbitrary scripts, network lookups or unbounded
# recursion." DEC07 Q10 added the rest, gated by vocabulary version.
OPERATORS_BY_VOCABULARY_VERSION: dict[int, set[str]] = {
    1: {"eq", "in", "all", "any"},
    2: {"eq", "in", "all", "any", "not", "gte", "lte", "count"},
    # Vocabulary 3 adds NO operators. The bump carries semantics instead:
    # structured status/outcome entries (StatusDefinition/OutcomeDefinition
    # below) and evaluation of a rule's `conditions` tree. Stated here
    # because "same set as 2" otherwise looks like a copy-paste slip.
    3: {"eq", "in", "all", "any", "not", "gte", "lte", "count"},
}
ALLOWED_OPERATORS = OPERATORS_BY_VOCABULARY_VERSION[VOCABULARY_VERSION]

# Leaf operators (take `fact` + `value`) vs branch operators (take nested
# `conditions`). `count` is a branch that additionally carries its own
# comparison against a target.
_LEAF_OPERATORS = {"eq", "in", "gte", "lte"}
_COUNT_COMPARISONS = {"eq", "gte", "lte"}

# The reserved fact name carrying DEC07's "supplied 'as at' timestamp".
# Rules read it like any other fact; nothing in project state can shadow it
# (see evaluate_condition).
AS_AT_FACT = "as_at"

# Facts/keys a rule must never be able to name -- doing so would let a
# tenant-authored template turn off the platform's own invariants, which
# REQ-013 explicitly forbids regardless of who authored the rule.
PROHIBITED_FACTS = {
    "disable_audit",
    "disable_export",
    "bypass_review",
    "bypass_mfa",
    "grant_approval",
    "eval",
    "exec",
}


class RuleValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class RuleEvaluationTimeout(Exception):
    """DEC07's "hard evaluation timeout" fired. Deliberately an exception
    rather than a silent False: a rule that cannot be evaluated inside its
    budget is an operational anomaly, not a readiness answer.

    There are TWO production callers of `evaluate_condition`, and they are
    not equally covered:

      * `app/routers/projects.py` (rule applicability at project creation)
        rolls its whole transaction back if evaluation raises -- a
        behaviour tests/test_projects.py pins independently.
      * `_conditions_hold` in `app/routers/decisions.py`, reached from
        readiness and, since I3's fix, from `my_work`
        (`app/routers/projects.py`) too. On the decision-commit path that
        transaction is likewise rolled back; on `/preview` and on
        `my_work` -- a GET that writes nothing -- there is nothing to roll
        back.

    This exception is caught NOWHERE, so either caller surfaces it as an
    unhandled 500 rather than a structured error. That is fail-closed -- no
    readiness answer is produced and no decision commits -- but it is not a
    handled error path, and calling it one would overstate it."""


class Condition(BaseModel):
    """A single leaf test, or a bounded branch over nested conditions.
    There is no "expression" field anywhere in this model -- there is
    nothing here capable of representing arbitrary code."""

    op: Literal["eq", "in", "all", "any", "not", "gte", "lte", "count"]
    fact: str | None = None
    value: Any | None = None
    conditions: list["Condition"] | None = None
    # `count` only: how its tally of satisfied sub-conditions is compared
    # against `value`. Reuses the approved comparison words rather than
    # adding new ones, per DEC07's "resist adding anything beyond this".
    compare: Literal["eq", "gte", "lte"] | None = None

    @field_validator("fact")
    @classmethod
    def _fact_not_prohibited(cls, v: str | None) -> str | None:
        if v is not None and v in PROHIBITED_FACTS:
            raise ValueError(f"fact '{v}' is a platform invariant and cannot be referenced by a rule")
        return v

    @model_validator(mode="after")
    def _shape_matches_operator(self) -> "Condition":
        if self.op != "count" and self.compare is not None:
            raise ValueError(f"operator '{self.op}' does not take 'compare'")

        if self.op in _LEAF_OPERATORS:
            if self.fact is None:
                raise ValueError(f"operator '{self.op}' requires 'fact'")
            if self.conditions is not None:
                raise ValueError(f"operator '{self.op}' does not take nested 'conditions'")
        elif self.op == "not":
            # Unary by design: `not` over a list would silently need an
            # implied all/any between the negated parts, which the author
            # should have to state explicitly.
            if not self.conditions or len(self.conditions) != 1:
                raise ValueError("operator 'not' requires exactly one nested condition")
            if self.fact is not None:
                raise ValueError("operator 'not' does not take 'fact' directly")
        elif self.op == "count":
            if not self.conditions:
                raise ValueError("operator 'count' requires a non-empty 'conditions' list")
            if self.fact is not None:
                raise ValueError("operator 'count' does not take 'fact' directly")
            if self.compare is None:
                raise ValueError("operator 'count' requires 'compare' (one of eq, gte, lte)")
            # bool is a subclass of int in Python, so `count >= True` would
            # pass a naive isinstance check.
            if isinstance(self.value, bool) or not isinstance(self.value, int):
                raise ValueError("operator 'count' requires an integer 'value' to compare its tally against")
        else:  # all / any
            if not self.conditions:
                raise ValueError(f"operator '{self.op}' requires a non-empty 'conditions' list")
            if self.fact is not None:
                raise ValueError(f"operator '{self.op}' does not take 'fact' directly")
        return self

    def depth(self) -> int:
        if not self.conditions:
            return 1
        return 1 + max(c.depth() for c in self.conditions)

    def node_count(self) -> int:
        """Total nodes in this tree, this one included -- the quantity
        DEC07's 200-node cap bounds."""
        if not self.conditions:
            return 1
        return 1 + sum(c.node_count() for c in self.conditions)

    def operators_used(self) -> set[str]:
        """Every operator appearing anywhere in this tree, for vocabulary
        gating. `compare` is not included: its values (eq/gte/lte) are
        words of the `count` operator's own shape, and `count` itself is
        already gated -- counting them separately would reject `count` at
        every version."""
        used = {self.op}
        for child in self.conditions or ():
            used |= child.operators_used()
        return used


Condition.model_rebuild()


class Rule(BaseModel):
    """Sec.5.5 approved rule schema fields, exactly, plus two optional
    plain-language fields (guidance, evidence_example) a template author
    may fill in so a contributor sees "what to do" / "evidence to provide"
    help next to the requirement itself -- purely descriptive, never
    evaluated, never affecting readiness/blocker logic. Absent on any
    template authored before this existed; the frontend simply shows
    nothing for those, same graceful-absence handling as everywhere else
    guidance text is optional in this project."""

    version: int
    rule_id: str
    class_ids: list[str] = Field(min_length=1)
    occurrence_type: str
    evidence_kind: str
    applicability: Condition | None = None
    required_fields: list[str] = Field(default_factory=list)
    permitted_role_ids: list[str] = Field(min_length=1)
    blocker_level: Literal["hard", "conditional", "advisory"]
    conditions: Condition | None = None
    guidance: str | None = None
    evidence_example: str | None = None

    @model_validator(mode="after")
    def _bounded_depth_and_size(self) -> "Rule":
        for cond in (self.applicability, self.conditions):
            if cond is not None and cond.depth() > MAX_CONDITION_DEPTH:
                raise ValueError(f"rule '{self.rule_id}': condition nesting exceeds max depth {MAX_CONDITION_DEPTH}")

        # DEC07's words are "cap total condition nodes at 200". Read as the
        # total this rule evaluates -- applicability and conditions summed,
        # not each tree separately -- since bounding evaluation cost is the
        # stated purpose. Flagged as an interpretation: the stricter of the
        # two readings, so two 150-node trees in one rule is 300 and over.
        total_nodes = sum(c.node_count() for c in (self.applicability, self.conditions) if c is not None)
        if total_nodes > MAX_CONDITION_NODES:
            raise ValueError(
                f"rule '{self.rule_id}': {total_nodes} total condition nodes exceeds max {MAX_CONDITION_NODES}"
            )
        return self

    def operators_used(self) -> set[str]:
        used: set[str] = set()
        for cond in (self.applicability, self.conditions):
            if cond is not None:
                used |= cond.operators_used()
        return used


class GateDefinition(BaseModel):
    gate_id: str
    name: str
    sequence: int
    class_ids: list[str] = Field(min_length=1)
    rules: list[Rule] = Field(default_factory=list)
    description: str | None = None  # optional plain-language gate purpose; see Rule.guidance


# EvidenceItem.status / EvidenceRevision.status are String(30)
# (app/models.py). A longer id validates happily and then fails at
# revision time as a database error, so it is rejected here instead.
MAX_STATUS_ID_LENGTH = 30

# DecisionRecord.outcome is String(30) too (app/models.py), with the same
# consequence one step later: a longer declared outcome id validates, is
# offered in the UI, and then fails at decision-commit time as a database
# error.
MAX_OUTCOME_ID_LENGTH = 30

# v1/v2 templates declare bare strings. These two maps are what make
# "old templates evaluate identically forever" (DEC07 Q10) true with no
# migration: today's hardcoded literals, expressed as data.
_LEGACY_SATISFYING_STATUS = "Complete"
_LEGACY_INITIAL_STATUS = "Not started"
_LEGACY_OUTCOME_KINDS = {
    "Approve": "approving",
    "Approve with conditions": "conditional_approving",
    "Hold": "recording",
    "Redirect": "recording",
    "Terminate": "recording",
}


class StatusDefinition(BaseModel):
    """One evidence status plus what it MEANS, so readiness can ask the
    template instead of matching an English word."""

    # No max_length here: enforcing it on the Pydantic field would raise
    # BEFORE the explicit vocabulary>=3 loop in _cross_references_resolve
    # ever ran (status_lookup() constructs this model earlier), which (a)
    # surfaced Pydantic's generic length message instead of the intended
    # "imposed by EvidenceItem.status" explanation, and (b) aborted the
    # whole validator on the first offending structured entry, destroying
    # REQ-012's one-error-per-problem aggregation. One enforcement point
    # only -- the explicit loop over declared ids, gated behind v3 so a
    # published v1/v2 template is never newly rejected (G6).
    id: str = Field(min_length=1)
    satisfies: bool = False
    # A satisfying status that must be justified by a valid ExceptionRecord
    # (REQ-020) rather than freely chosen. Without this, declaring an extra
    # satisfying status would be a route around a hard blocker.
    requires_exception: bool = False
    initial: bool = False


class OutcomeDefinition(BaseModel):
    """`kind` carries exactly the three behaviours _outcome_eligibility
    hardcodes today for the Blueprint's five words."""

    id: str = Field(min_length=1)
    kind: Literal["approving", "conditional_approving", "recording"]


def status_satisfies(definition: "StatusDefinition | None") -> bool:
    """The single answer to "does this status satisfy on its own?", shared
    by every caller that asks (readiness, the condition-fact pass, and
    my_work's assigned-action text) so they cannot drift apart.

    Two deliberate properties:

      * `None` -- a status the bound template does not declare, reachable
        for rows written before this template version -- fails CLOSED.
      * a `requires_exception` status is never "directly" satisfying: it
        has to be justified by a valid ExceptionRecord (REQ-020), which
        this function has no database access to check, so it withholds
        satisfaction and leaves the exception lookup to the caller that
        can do it.
    """
    return definition is not None and definition.satisfies and not definition.requires_exception


class TemplateSchema(BaseModel):
    """REQ-010: version framework templates containing tracks, gates,
    classification, role, status, decision and applicability schemes."""

    schema_version: int = 1
    # DEC07: "Stamp vocabulary_version on every template version so old
    # templates evaluate identically forever, regardless of later
    # vocabulary changes." Defaulting to 1 is what makes that true without
    # a migration or a backfill: every version published before this field
    # existed is immutable (REQ-011), so its stored schema_json simply
    # lacks the key and validates as vocabulary 1 -- exactly the operator
    # set it was authored against.
    vocabulary_version: int = 1
    tracks: list[str] = Field(min_length=1)
    classes: list[str] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    statuses: list[str | StatusDefinition] = Field(min_length=1)
    decision_outcomes: list[str | OutcomeDefinition] = Field(min_length=1)
    gates: list[GateDefinition] = Field(min_length=1)

    def status_lookup(self) -> dict[str, StatusDefinition]:
        """Normalise mixed strings/objects into one lookup. Plain strings
        resolve per vocabulary_version -- that is the whole back-compat
        mechanism (G6)."""
        out: dict[str, StatusDefinition] = {}
        for entry in self.statuses:
            if isinstance(entry, StatusDefinition):
                out[entry.id] = entry
                continue
            if self.vocabulary_version <= 2:
                out[entry] = StatusDefinition(
                    id=entry,
                    satisfies=(entry == _LEGACY_SATISFYING_STATUS),
                    initial=(entry == _LEGACY_INITIAL_STATUS),
                )
            else:
                out[entry] = StatusDefinition(id=entry)
        return out

    def outcome_lookup(self) -> dict[str, OutcomeDefinition]:
        """An outcome with no resolvable kind is OMITTED, not defaulted --
        preserving today's honest refusal for a v1/v2 template declaring
        an outcome this prototype never handled."""
        out: dict[str, OutcomeDefinition] = {}
        for entry in self.decision_outcomes:
            if isinstance(entry, OutcomeDefinition):
                out[entry.id] = entry
                continue
            kind = _LEGACY_OUTCOME_KINDS.get(entry)
            if kind is not None:
                out[entry] = OutcomeDefinition(id=entry, kind=kind)
        return out

    def initial_status(self) -> str:
        """G7: the status a seeded item starts in comes from the template,
        never from a literal in the seeding code."""
        for definition in self.status_lookup().values():
            if definition.initial:
                return definition.id
        # This fallback is LIVE, not defensive: routers/projects.py seeds
        # every evidence item and its first revision from this method, so a
        # v1/v2 template that omits "Not started" entirely now seeds its
        # first declared status instead. `fixtures/synthetic/frameworks/
        # agile.json` is exactly that case -- vocabulary 2, declaring
        # ['Not met', 'Met', 'Waived for this increment'] -- and its
        # projects seed 'Not met' where they used to seed the literal
        # 'Not started'. That is a recorded, accepted vocabulary-1/2
        # behaviour change (docs/DEFECT_REGISTER.md, the DEC07-Q11 row's G6
        # exceptions), pinned by the agile-fixture seeding test in
        # backend/tests/test_dec07_q11_agile_fixture.py. Unreachable for v3
        # (validated to have exactly one initial status) and for any v1/v2
        # template that does declare "Not started" (the three gate-based
        # fixtures all do).
        return next(iter(self.status_lookup()))

    @model_validator(mode="after")
    def _cross_references_resolve(self) -> "TemplateSchema":
        errors: list[str] = []
        class_set, role_set = set(self.classes), set(self.roles)
        seen_gate_ids: set[str] = set()
        seen_rule_ids: set[str] = set()

        permitted_operators = OPERATORS_BY_VOCABULARY_VERSION.get(self.vocabulary_version)
        if permitted_operators is None:
            errors.append(
                f"vocabulary_version {self.vocabulary_version} is not a vocabulary this build knows "
                f"(known: {sorted(OPERATORS_BY_VOCABULARY_VERSION)})"
            )
            permitted_operators = set()

        for gate in self.gates:
            if gate.gate_id in seen_gate_ids:
                errors.append(f"duplicate gate_id '{gate.gate_id}'")
            seen_gate_ids.add(gate.gate_id)

            unknown_classes = set(gate.class_ids) - class_set
            if unknown_classes:
                errors.append(f"gate '{gate.gate_id}' references undeclared class(es) {sorted(unknown_classes)}")

            for rule in gate.rules:
                if rule.rule_id in seen_rule_ids:
                    errors.append(f"duplicate rule_id '{rule.rule_id}'")
                seen_rule_ids.add(rule.rule_id)

                unknown_role_ids = set(rule.permitted_role_ids) - role_set
                if unknown_role_ids:
                    errors.append(f"rule '{rule.rule_id}' references undeclared role(s) {sorted(unknown_role_ids)}")

                unknown_rule_classes = set(rule.class_ids) - class_set
                if unknown_rule_classes:
                    errors.append(
                        f"rule '{rule.rule_id}' references undeclared class(es) {sorted(unknown_rule_classes)}"
                    )

                # Covers applicability and conditions alike -- a rule can
                # gate its own relevance on an operator just as easily as
                # its readiness test.
                beyond_vocabulary = rule.operators_used() - permitted_operators
                if beyond_vocabulary:
                    errors.append(
                        f"rule '{rule.rule_id}' uses operator(s) {sorted(beyond_vocabulary)} "
                        f"not in vocabulary_version {self.vocabulary_version}"
                    )

        status_defs = list(self.status_lookup().values())
        declared_ids = [entry.id if isinstance(entry, StatusDefinition) else entry for entry in self.statuses]
        for definition in status_defs:
            if definition.requires_exception and not definition.satisfies:
                errors.append(f"status '{definition.id}': requires_exception is meaningless without satisfies")

        declared_outcome_ids = [
            entry.id if isinstance(entry, OutcomeDefinition) else entry for entry in self.decision_outcomes
        ]

        # Why the duplicate-id and length-cap checks are conditional at all
        # (G6): spec Sec.5 enforces the length cap "at publish time", not on
        # every re-read, and routers/projects.py re-validates a template's
        # stored schema_json on every single project binding. Neither check
        # existed before this task, so a published, immutable (REQ-011)
        # v1/v2 template that happens to carry a duplicate or an
        # over-length id must keep validating exactly as it always did.
        #
        # That protection is only needed for PLAIN STRINGS. `statuses` and
        # `decision_outcomes` were `list[str]` before this branch, so a
        # STRUCTURED entry cannot occur in any already-published template --
        # gating it behind v3 protected nothing and left a real hole, since
        # a structured entry is accepted at ANY vocabulary version while
        # every v3 rule sat behind the version check: routers/projects.py
        # then writes initial_status() straight into EvidenceItem.status
        # (String(30)), and a decision writes an outcome id into
        # DecisionRecord.outcome (String(30)). So: enforce on every declared
        # id as soon as the template carries a structured entry of that
        # kind, or declares vocabulary 3.
        has_structured_status = any(isinstance(entry, StatusDefinition) for entry in self.statuses)
        has_structured_outcome = any(isinstance(entry, OutcomeDefinition) for entry in self.decision_outcomes)

        if self.vocabulary_version >= 3 or has_structured_status:
            if len(declared_ids) != len(set(declared_ids)):
                errors.append("duplicate status id declared")
            for status_id in declared_ids:
                if len(status_id) > MAX_STATUS_ID_LENGTH:
                    errors.append(
                        f"status '{status_id}' exceeds the {MAX_STATUS_ID_LENGTH}-character limit "
                        f"imposed by EvidenceItem.status"
                    )

        if self.vocabulary_version >= 3 or has_structured_outcome:
            if len(declared_outcome_ids) != len(set(declared_outcome_ids)):
                errors.append("duplicate decision outcome id declared")
            for outcome_id in declared_outcome_ids:
                if len(outcome_id) > MAX_OUTCOME_ID_LENGTH:
                    errors.append(
                        f"decision outcome '{outcome_id}' exceeds the {MAX_OUTCOME_ID_LENGTH}-character limit "
                        f"imposed by DecisionRecord.outcome"
                    )

        # These three are genuinely about what vocabulary 3 MEANS, not about
        # a storage limit, so they stay keyed to the declared version.
        if self.vocabulary_version >= 3:
            if sum(1 for d in status_defs if d.initial) != 1:
                errors.append("vocabulary 3 requires exactly one status with initial: true")
            if not any(d.satisfies for d in status_defs):
                errors.append("vocabulary 3 requires at least one status with satisfies: true")
            for entry in self.decision_outcomes:
                if not isinstance(entry, OutcomeDefinition):
                    errors.append(
                        f"decision outcome '{entry}': vocabulary 3 requires an explicit kind "
                        f"(approving | conditional_approving | recording)"
                    )

        if errors:
            raise ValueError("; ".join(errors))
        return self


def validate_template_schema(data: dict) -> TemplateSchema:
    """Raises RuleValidationError with one message per problem, so a bad
    import can be explained field-by-field (REQ-012) rather than as a single
    opaque failure."""
    try:
        return TemplateSchema.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError, or the ValueError raised above
        messages = getattr(exc, "errors", None)
        if callable(messages):
            errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        else:
            errors = [str(exc)]
        raise RuleValidationError(errors) from exc


def _compare(left: Any, right: Any, op: str) -> bool:
    """`gte`/`lte` over whatever project state actually holds. Python 3
    raises TypeError on mismatched types ("x" >= 1), and a tenant-authored
    rule comparing a text fact against a numeric threshold is a realistic
    mistake -- so an incomparable pair fails closed, the same answer an
    unknown fact already gives, rather than propagating out of a readiness
    check and failing the request.

    Dates compare as text, deliberately: template JSON has no date type, so
    a rule's threshold is always a string, and this stays a plain
    comparison rather than growing date parsing DEC07 never asked for.
    That works because ISO-8601 in a single consistent format sorts
    lexicographically -- which is why callers must supply `as_at` as an ISO
    string, not a datetime object (a datetime compared against a string
    threshold would raise TypeError and fail closed every time, making
    date rules silently useless; app/routers/projects.py passes
    `.isoformat()` for exactly this reason).

    Known boundary behaviour, stated rather than left to be discovered: a
    full timestamp is lexicographically greater than the bare date it falls
    on ("2026-10-02T05:00:00+00:00" > "2026-10-02"), so `lte` against a
    bare date excludes that day. A rule meaning "on or before 2 October"
    should compare against the start of the next day, or against a full
    timestamp."""
    try:
        return left >= right if op == "gte" else left <= right
    except TypeError:
        return False


def _evaluate(condition: Condition, facts: dict[str, Any], deadline: float | None) -> bool:
    if deadline is not None and time.monotonic() > deadline:
        raise RuleEvaluationTimeout(
            f"rule evaluation exceeded its {EVALUATION_TIMEOUT_SECONDS}s budget "
            f"(depth<={MAX_CONDITION_DEPTH}, nodes<={MAX_CONDITION_NODES} should evaluate far inside it)"
        )

    if condition.op == "eq":
        if condition.fact not in facts:
            return False
        return facts[condition.fact] == condition.value
    if condition.op == "in":
        if condition.fact not in facts:
            return False
        return facts[condition.fact] in condition.value
    if condition.op in ("gte", "lte"):
        if condition.fact not in facts:
            return False
        return _compare(facts[condition.fact], condition.value, condition.op)
    if condition.op == "all":
        return all(_evaluate(c, facts, deadline) for c in condition.conditions)
    if condition.op == "any":
        return any(_evaluate(c, facts, deadline) for c in condition.conditions)
    if condition.op == "not":
        return not _evaluate(condition.conditions[0], facts, deadline)
    if condition.op == "count":
        # No short-circuit: the tally needs every sub-condition's answer.
        satisfied = sum(1 for c in condition.conditions if _evaluate(c, facts, deadline))
        if condition.compare == "eq":
            return satisfied == condition.value
        return _compare(satisfied, condition.value, condition.compare)
    raise AssertionError(f"unreachable: unknown operator {condition.op!r} slipped past validation")


def evaluate_condition(
    condition: Condition,
    facts: dict[str, Any],
    *,
    as_at: Any | None = None,
    timeout_seconds: float | None = EVALUATION_TIMEOUT_SECONDS,
) -> bool:
    """Evaluate order per Sec.5.5: unknown facts fail closed. This walks a
    fixed, small AST -- it never executes tenant-supplied code.

    DEC07: rules are "pure functions of project state plus a supplied 'as
    at' timestamp -- no external calls, no wall-clock reads inside the rule
    itself". So `as_at` is a parameter, never read from the clock here, and
    a rule reads it as the `as_at` fact like any other. Project state
    cannot shadow it: it is applied over `facts`, because project state is
    tenant-influenced and the evaluation timestamp is not. Omit it and a
    rule referencing `as_at` fails closed, like any other unknown fact.

    `time.monotonic` below is the timeout's own bookkeeping, not a fact a
    rule can read -- it cannot affect any rule's result, only whether
    evaluation is abandoned. Pass `timeout_seconds=None` to disable the
    deadline (no caller does; kept so the bound is explicit at the call
    site rather than implicit)."""
    if as_at is not None:
        facts = {**facts, AS_AT_FACT: as_at}
    deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
    return _evaluate(condition, facts, deadline)
