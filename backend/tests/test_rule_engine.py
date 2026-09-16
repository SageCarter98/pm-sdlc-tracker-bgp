import copy

import pytest

from app.rule_engine import (
    Condition,
    RuleValidationError,
    evaluate_condition,
    validate_template_schema,
)

MINIMAL_VALID_TEMPLATE = {
    "tracks": ["Delivery"],
    "classes": ["A", "B"],
    "roles": ["contributor", "approver"],
    "statuses": ["Not started", "Complete"],
    "decision_outcomes": ["Approve", "Hold"],
    "gates": [
        {
            "gate_id": "G1",
            "name": "Intake",
            "sequence": 1,
            "class_ids": ["A", "B"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "G1.R1",
                    "class_ids": ["A"],
                    "occurrence_type": "routine",
                    "evidence_kind": "document",
                    "permitted_role_ids": ["approver"],
                    "blocker_level": "hard",
                }
            ],
        }
    ],
}


def test_minimal_valid_template_passes():
    schema = validate_template_schema(MINIMAL_VALID_TEMPLATE)
    assert schema.gates[0].gate_id == "G1"


def test_rejects_unknown_operator():
    bad = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    bad["gates"][0]["rules"][0]["applicability"] = {"op": "regex", "fact": "x", "value": ".*"}
    with pytest.raises(RuleValidationError):
        validate_template_schema(bad)


def test_rejects_prohibited_fact():
    bad = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    bad["gates"][0]["rules"][0]["applicability"] = {"op": "eq", "fact": "disable_audit", "value": True}
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(bad)
    assert "platform invariant" in str(exc.value)


def test_rejects_unknown_class_reference():
    bad = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    bad["gates"][0]["class_ids"] = ["Z"]
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(bad)
    assert "undeclared class" in str(exc.value)


def test_rejects_unknown_role_reference():
    bad = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    bad["gates"][0]["rules"][0]["permitted_role_ids"] = ["nonexistent_role"]
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(bad)
    assert "undeclared role" in str(exc.value)


def test_rejects_duplicate_rule_id():
    bad = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    bad["gates"][0]["rules"].append(dict(bad["gates"][0]["rules"][0]))
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(bad)
    assert "duplicate rule_id" in str(exc.value)


def test_rejects_excessive_nesting():
    nested = {"op": "eq", "fact": "x", "value": 1}
    for _ in range(6):
        nested = {"op": "all", "conditions": [nested]}
    bad = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    bad["gates"][0]["rules"][0]["conditions"] = nested
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(bad)
    assert "nesting exceeds max depth" in str(exc.value)


def test_all_and_any_require_conditions_not_fact():
    bad = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    bad["gates"][0]["rules"][0]["applicability"] = {"op": "all", "fact": "x"}
    with pytest.raises(RuleValidationError):
        validate_template_schema(bad)


def test_evaluate_condition_eq():
    cond = Condition(op="eq", fact="class_id", value="A")
    assert evaluate_condition(cond, {"class_id": "A"}) is True
    assert evaluate_condition(cond, {"class_id": "B"}) is False


def test_evaluate_condition_unknown_fact_fails_closed():
    cond = Condition(op="eq", fact="never_supplied", value="A")
    assert evaluate_condition(cond, {}) is False


def test_evaluate_condition_all_any():
    all_cond = Condition(
        op="all",
        conditions=[Condition(op="eq", fact="a", value=1), Condition(op="eq", fact="b", value=2)],
    )
    assert evaluate_condition(all_cond, {"a": 1, "b": 2}) is True
    assert evaluate_condition(all_cond, {"a": 1, "b": 99}) is False

    any_cond = Condition(
        op="any",
        conditions=[Condition(op="eq", fact="a", value=1), Condition(op="eq", fact="b", value=2)],
    )
    assert evaluate_condition(any_cond, {"a": 99, "b": 2}) is True


def test_evaluate_condition_in():
    cond = Condition(op="in", fact="role", value=["approver", "sponsor"])
    assert evaluate_condition(cond, {"role": "approver"}) is True
    assert evaluate_condition(cond, {"role": "contributor"}) is False
