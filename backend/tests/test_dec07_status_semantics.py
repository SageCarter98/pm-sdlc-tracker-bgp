"""DEC07 vocabulary indirection, schema layer: structured status and
outcome semantics, and their vocabulary-gated normalisation."""

import pytest

from app.rule_engine import RuleValidationError, validate_template_schema

BASE = {
    "tracks": ["T"],
    "classes": ["C"],
    "roles": ["r"],
    "gates": [
        {
            "gate_id": "g",
            "name": "G",
            "sequence": 1,
            "class_ids": ["C"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "g.r",
                    "class_ids": ["C"],
                    "occurrence_type": "routine",
                    "evidence_kind": "note",
                    "permitted_role_ids": ["r"],
                    "blocker_level": "hard",
                }
            ],
        }
    ],
}


def _schema(**over):
    return {**BASE, **over}


def test_v2_plain_strings_normalise_to_todays_meaning():
    """G6 at the schema layer: 'Complete' satisfies and 'Not started' is
    initial, expressed as data rather than a literal in a branch."""
    s = validate_template_schema(
        _schema(
            vocabulary_version=2,
            statuses=["Not started", "In progress", "Complete"],
            decision_outcomes=["Approve", "Approve with conditions", "Hold"],
        )
    )
    lookup = s.status_lookup()
    assert lookup["Complete"].satisfies is True
    assert lookup["In progress"].satisfies is False
    assert lookup["Not started"].initial is True
    assert s.initial_status() == "Not started"

    outcomes = s.outcome_lookup()
    assert outcomes["Approve"].kind == "approving"
    assert outcomes["Approve with conditions"].kind == "conditional_approving"
    assert outcomes["Hold"].kind == "recording"


def test_v2_unmapped_plain_outcome_gets_no_kind():
    """Today's honest refusal is preserved: an outcome the prototype does
    not handle must not acquire an invented semantics."""
    s = validate_template_schema(
        _schema(
            vocabulary_version=2,
            statuses=["Not started", "Complete"],
            decision_outcomes=["Approve", "Increment accepted"],
        )
    )
    assert "Increment accepted" not in s.outcome_lookup()


def test_v3_structured_entries_carry_their_own_semantics():
    s = validate_template_schema(
        _schema(
            vocabulary_version=3,
            statuses=[
                {"id": "Not met", "initial": True},
                {"id": "Met", "satisfies": True},
                {"id": "Waived", "satisfies": True, "requires_exception": True},
            ],
            decision_outcomes=[
                {"id": "Increment accepted", "kind": "approving"},
                {"id": "Not accepted", "kind": "recording"},
            ],
        )
    )
    lookup = s.status_lookup()
    assert lookup["Met"].satisfies is True
    assert lookup["Waived"].requires_exception is True
    assert lookup["Not met"].satisfies is False
    assert s.initial_status() == "Not met"
    assert s.outcome_lookup()["Increment accepted"].kind == "approving"


def test_v3_plain_string_status_is_accepted_as_non_satisfying():
    """Asymmetry with outcomes, deliberate (spec 4.2): a non-satisfying
    status is an ordinary thing to declare, so the safe default is
    meaningful."""
    s = validate_template_schema(
        _schema(
            vocabulary_version=3,
            statuses=["Backlog", {"id": "Done", "satisfies": True, "initial": False}, {"id": "New", "initial": True}],
            decision_outcomes=[{"id": "Yes", "kind": "approving"}],
        )
    )
    assert s.status_lookup()["Backlog"].satisfies is False


def test_v3_plain_string_outcome_is_rejected():
    """An outcome with no kind can never be recorded, so accepting it only
    defers a 422 to gate day."""
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(
            _schema(
                vocabulary_version=3,
                statuses=[{"id": "New", "initial": True}, {"id": "Done", "satisfies": True}],
                decision_outcomes=["Approve"],
            )
        )
    assert "kind" in str(exc.value)


@pytest.mark.parametrize(
    "statuses, needle",
    [
        ([{"id": "A", "initial": True}, {"id": "B", "initial": True, "satisfies": True}], "exactly one"),
        ([{"id": "A", "satisfies": True}, {"id": "B", "satisfies": True}], "exactly one"),
        ([{"id": "A", "initial": True}, {"id": "B"}], "at least one"),
        ([{"id": "A", "initial": True}, {"id": "B", "requires_exception": True}], "requires_exception"),
        ([{"id": "A", "initial": True}, {"id": "A", "satisfies": True}], "duplicate"),
    ],
)
def test_v3_status_validation_rules(statuses, needle):
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(
            _schema(
                vocabulary_version=3,
                statuses=statuses,
                decision_outcomes=[{"id": "Yes", "kind": "approving"}],
            )
        )
    assert needle in str(exc.value).lower()


def test_status_id_length_boundary_is_thirty():
    """REVIEW FOCUS 2. EvidenceItem.status is String(30); an off-by-one
    here reaches the database as an error instead of a message."""
    ok = "x" * 30
    s = validate_template_schema(
        _schema(
            vocabulary_version=3,
            statuses=[{"id": "New", "initial": True}, {"id": ok, "satisfies": True}],
            decision_outcomes=[{"id": "Yes", "kind": "approving"}],
        )
    )
    assert ok in s.status_lookup()

    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(
            _schema(
                vocabulary_version=3,
                statuses=[{"id": "New", "initial": True}, {"id": "x" * 31, "satisfies": True}],
                decision_outcomes=[{"id": "Yes", "kind": "approving"}],
            )
        )
    assert "30" in str(exc.value)


def test_vocabulary_three_has_the_same_operators_as_two():
    """The bump is about semantics, not operators."""
    from app.rule_engine import OPERATORS_BY_VOCABULARY_VERSION

    assert OPERATORS_BY_VOCABULARY_VERSION[3] == OPERATORS_BY_VOCABULARY_VERSION[2]
