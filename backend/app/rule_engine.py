"""Declarative rule vocabulary, Blueprint Sec.5.5. REQ-013: restrict
configurable rules to a versioned declarative vocabulary; prohibit
executable code and invariant overrides. Nothing in this module ever
evaluates a string as code -- conditions are structured data, walked by
_evaluate_condition, not passed to eval/exec or a template engine.

DEC07 (exact vocabulary and limits, third framework choice) is still open --
this is a working prototype of the schema shape Sec.5.5 already approved,
not a claim that DEC07 is resolved.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_CONDITION_DEPTH = 5

# Sec.5.5: "Permitted operators are equality, membership and bounded all/any
# over declared facts. No arbitrary scripts, network lookups or unbounded
# recursion."
ALLOWED_OPERATORS = {"eq", "in", "all", "any"}

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


class Condition(BaseModel):
    """A single leaf test, or a bounded all/any over nested conditions.
    There is no "expression" field anywhere in this model -- there is
    nothing here capable of representing arbitrary code."""

    op: Literal["eq", "in", "all", "any"]
    fact: str | None = None
    value: Any | None = None
    conditions: list["Condition"] | None = None

    @field_validator("fact")
    @classmethod
    def _fact_not_prohibited(cls, v: str | None) -> str | None:
        if v is not None and v in PROHIBITED_FACTS:
            raise ValueError(f"fact '{v}' is a platform invariant and cannot be referenced by a rule")
        return v

    @model_validator(mode="after")
    def _shape_matches_operator(self) -> "Condition":
        if self.op in ("eq", "in"):
            if self.fact is None:
                raise ValueError(f"operator '{self.op}' requires 'fact'")
            if self.conditions is not None:
                raise ValueError(f"operator '{self.op}' does not take nested 'conditions'")
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


Condition.model_rebuild()


class Rule(BaseModel):
    """Sec.5.5 approved rule schema fields, exactly."""

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

    @model_validator(mode="after")
    def _bounded_depth(self) -> "Rule":
        for cond in (self.applicability, self.conditions):
            if cond is not None and cond.depth() > MAX_CONDITION_DEPTH:
                raise ValueError(f"rule '{self.rule_id}': condition nesting exceeds max depth {MAX_CONDITION_DEPTH}")
        return self


class GateDefinition(BaseModel):
    gate_id: str
    name: str
    sequence: int
    class_ids: list[str] = Field(min_length=1)
    rules: list[Rule] = Field(default_factory=list)


class TemplateSchema(BaseModel):
    """REQ-010: version framework templates containing tracks, gates,
    classification, role, status, decision and applicability schemes."""

    schema_version: int = 1
    tracks: list[str] = Field(min_length=1)
    classes: list[str] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    statuses: list[str] = Field(min_length=1)
    decision_outcomes: list[str] = Field(min_length=1)
    gates: list[GateDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def _cross_references_resolve(self) -> "TemplateSchema":
        errors: list[str] = []
        class_set, role_set = set(self.classes), set(self.roles)
        seen_gate_ids: set[str] = set()
        seen_rule_ids: set[str] = set()

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
                    errors.append(f"rule '{rule.rule_id}' references undeclared class(es) {sorted(unknown_rule_classes)}")

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


def evaluate_condition(condition: Condition, facts: dict[str, Any]) -> bool:
    """Evaluate order per Sec.5.5: unknown facts fail closed. This walks a
    fixed, small AST -- it never executes tenant-supplied code."""
    if condition.op == "eq":
        if condition.fact not in facts:
            return False
        return facts[condition.fact] == condition.value
    if condition.op == "in":
        if condition.fact not in facts:
            return False
        return facts[condition.fact] in condition.value
    if condition.op == "all":
        return all(evaluate_condition(c, facts) for c in condition.conditions)
    if condition.op == "any":
        return any(evaluate_condition(c, facts) for c in condition.conditions)
    raise AssertionError(f"unreachable: unknown operator {condition.op!r} slipped past validation")
