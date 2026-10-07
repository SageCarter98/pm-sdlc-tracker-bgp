"""Vocabulary 4: a template declares its roles' semantics -- who may
supply evidence, and who may decide a gate."""

import pytest

from app.rule_engine import (
    MAX_ROLE_ID_LENGTH,
    OPERATORS_BY_VOCABULARY_VERSION,
    RoleDefinition,
    RuleValidationError,
    validate_template_schema,
)

BASE = {
    "schema_version": 1,
    "tracks": ["Delivery"],
    "classes": ["Team"],
    "statuses": [{"id": "Not started", "initial": True}, {"id": "Done", "satisfies": True}],
    "decision_outcomes": [{"id": "Accept", "kind": "approving"}, {"id": "Reject", "kind": "recording"}],
}


def _schema(roles, vocabulary_version=4, permitted=("product_owner",)):
    data = dict(BASE)
    data["vocabulary_version"] = vocabulary_version
    data["roles"] = roles
    data["gates"] = [
        {
            "gate_id": "G1",
            "name": "Done",
            "sequence": 1,
            "class_ids": ["Team"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "G1.R1",
                    "evidence_kind": "document",
                    "required": True,
                    "blocker_level": "hard",
                    "permitted_role_ids": list(permitted),
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                }
            ],
        }
    ]
    return data


def test_vocabulary_four_is_a_known_vocabulary():
    assert 4 in OPERATORS_BY_VOCABULARY_VERSION
    assert OPERATORS_BY_VOCABULARY_VERSION[4] == OPERATORS_BY_VOCABULARY_VERSION[3]


def test_structured_roles_resolve_their_declared_capabilities():
    schema = validate_template_schema(
        _schema([{"id": "product_owner", "attests": True, "decides": True}, {"id": "developer"}])
    )
    lookup = schema.role_lookup()
    assert lookup["product_owner"].decides is True
    assert lookup["product_owner"].attests is True
    # decides defaults False, attests defaults True: supplying evidence is
    # the common case, granting approval is the deliberate act.
    assert lookup["developer"].decides is False
    assert lookup["developer"].attests is True


def test_a_plain_string_role_at_v4_attests_but_does_not_decide():
    schema = validate_template_schema(_schema([{"id": "product_owner", "decides": True}, "developer"]))
    lookup = schema.role_lookup()
    assert lookup["developer"].attests is True
    assert lookup["developer"].decides is False


@pytest.mark.parametrize(
    "role,expect_decides",
    [("approver", True), ("sponsor", True), ("tenant_administrator", True), ("contributor", False)],
)
def test_legacy_roles_keep_todays_decision_authority(role, expect_decides):
    """G5: vocabulary 1-3 reproduces DECISION_AUTHORITY_ROLES exactly."""
    schema = validate_template_schema(_schema([role], vocabulary_version=2, permitted=(role,)))
    definition = schema.role_lookup()[role]
    assert definition.decides is expect_decides
    assert definition.attests is True


def test_v4_requires_at_least_one_deciding_role():
    with pytest.raises(RuleValidationError) as excinfo:
        validate_template_schema(_schema([{"id": "product_owner"}]))
    assert "at least one role with decides: true" in str(excinfo.value)


def test_a_rule_may_not_name_a_role_that_does_not_attest():
    """Review Focus 4: reject the self-contradiction at publish rather than
    silently refusing every member the rule names at runtime."""
    with pytest.raises(RuleValidationError) as excinfo:
        validate_template_schema(
            _schema(
                [{"id": "product_owner", "decides": True, "attests": False}],
                permitted=("product_owner",),
            )
        )
    assert "does not attest" in str(excinfo.value)


def test_structured_role_ids_are_length_capped_at_any_vocabulary_version():
    """Review Focus 3: a structured entry cannot exist in a template
    published before this work, so gating the cap behind v4 protects
    nothing -- exactly the hole DEC07's I1 fix closed for statuses."""
    long_id = "x" * (MAX_ROLE_ID_LENGTH + 1)
    with pytest.raises(RuleValidationError) as excinfo:
        validate_template_schema(
            _schema(
                [{"id": long_id, "decides": True}],
                vocabulary_version=1,
                permitted=(long_id,),
            )
        )
    assert f"exceeds the {MAX_ROLE_ID_LENGTH}-character limit" in str(excinfo.value)


def test_duplicate_structured_role_ids_are_rejected_at_any_vocabulary_version():
    with pytest.raises(RuleValidationError) as excinfo:
        validate_template_schema(
            _schema(
                [{"id": "dup", "decides": True}, {"id": "dup"}],
                vocabulary_version=1,
                permitted=("dup",),
            )
        )
    assert "duplicate role id declared" in str(excinfo.value)


def test_plain_string_roles_keep_v1_leniency():
    """G5: a published v1/v2 template carrying a duplicate or over-length
    PLAIN role string must keep validating exactly as it always did."""
    long_id = "y" * (MAX_ROLE_ID_LENGTH + 1)
    schema = validate_template_schema(
        _schema([long_id, long_id, "approver"], vocabulary_version=2, permitted=("approver",))
    )
    assert long_id in schema.role_lookup()


def test_role_definition_defaults():
    definition = RoleDefinition(id="x")
    assert definition.attests is True
    assert definition.decides is False
