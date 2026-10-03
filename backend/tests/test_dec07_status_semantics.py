"""DEC07 vocabulary indirection, schema layer: structured status and
outcome semantics, and their vocabulary-gated normalisation."""

import re

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


def _error_messages(exc_value: RuleValidationError) -> list[str]:
    """RuleValidationError.errors is, for a model-validator failure, a
    single pydantic-wrapped string: "<loc>: Value error, " followed by
    every "; "-joined message our own validator raised. Strip that
    pydantic prefix and split the rest back into individual messages, so
    a parametrized case can assert on the ONE message that actually
    proves its point, instead of a vague substring that a different
    firing rule could also satisfy (fix round 2/5, Important 4)."""
    out: list[str] = []
    for joined in exc_value.errors:
        joined = re.sub(r"^.*?Value error,\s*", "", joined, count=1)
        out.extend(part.strip() for part in joined.split("; "))
    return out


@pytest.mark.parametrize(
    "statuses, expected_message",
    [
        (
            [{"id": "A", "initial": True}, {"id": "B", "initial": True, "satisfies": True}],
            "vocabulary 3 requires exactly one status with initial: true",
        ),
        (
            # Same rule as above, the other side of it: zero initial
            # statuses is as invalid as two. There is no separate "exactly
            # one satisfies" rule -- satisfies only carries an "at least
            # one" requirement, covered by the next case.
            [{"id": "A", "satisfies": True}, {"id": "B", "satisfies": True}],
            "vocabulary 3 requires exactly one status with initial: true",
        ),
        (
            [{"id": "A", "initial": True}, {"id": "B"}],
            "vocabulary 3 requires at least one status with satisfies: true",
        ),
        (
            [{"id": "A", "initial": True}, {"id": "B", "requires_exception": True}],
            "status 'B': requires_exception is meaningless without satisfies",
        ),
        (
            [{"id": "A", "initial": True}, {"id": "A", "satisfies": True}],
            "duplicate status id declared",
        ),
    ],
)
def test_v3_status_validation_rules(statuses, expected_message):
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(
            _schema(
                vocabulary_version=3,
                statuses=statuses,
                decision_outcomes=[{"id": "Yes", "kind": "approving"}],
            )
        )
    assert expected_message in _error_messages(exc.value)


def test_status_id_length_boundary_is_thirty():
    """REVIEW FOCUS 2. EvidenceItem.status is String(30); an off-by-one
    here reaches the database as an error instead of a message. Uses a
    structured entry; test_v3_plain_string_status_over_length_is_rejected
    below covers the plain-string route specifically, since StatusDefinition
    no longer enforces the cap itself (fix round 2/5, Critical 2)."""
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
    expected = f"status '{'x' * 31}' exceeds the 30-character limit imposed by EvidenceItem.status"
    assert expected in _error_messages(exc.value)


def test_v3_plain_string_status_over_length_is_rejected_with_the_evidence_item_reason():
    """Critical 2 (fix round 2/5): StatusDefinition no longer enforces
    max_length, so a structured entry's cap is enforced purely by the
    explicit loop. A PLAIN STRING over 30 characters has no Pydantic field
    to catch it at all -- this is the only path that ever catches it, and
    it must surface OUR reason, not a generic one, since there is no
    generic one to fall back to."""
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(
            _schema(
                vocabulary_version=3,
                statuses=[{"id": "New", "initial": True}, {"id": "Done", "satisfies": True}, "x" * 31],
                decision_outcomes=[{"id": "Yes", "kind": "approving"}],
            )
        )
    messages = _error_messages(exc.value)
    assert any("imposed by EvidenceItem.status" in m for m in messages)
    assert any("30-character" in m for m in messages)


def test_v2_duplicate_and_overlength_statuses_still_validate():
    """G6 made explicit (fix round 2/5, controller-requested proof for
    Critical 1): gating the duplicate-id and length-cap checks behind
    vocabulary_version >= 3 must not newly reject a vocabulary-2 template
    that happens to declare a duplicate status id or an id longer than 30
    characters -- nothing ever checked either before this task, so a
    published, immutable (REQ-011) v1/v2 template carrying one must keep
    validating exactly as it always did on every re-read (routers/projects.py
    re-validates schema_json on every single project binding)."""
    dup = validate_template_schema(
        _schema(
            vocabulary_version=2,
            statuses=["Not started", "Complete", "Complete"],
            decision_outcomes=["Approve", "Hold"],
        )
    )
    assert dup is not None

    overlong = validate_template_schema(
        _schema(
            vocabulary_version=2,
            statuses=["Not started", "x" * 31],
            decision_outcomes=["Approve", "Hold"],
        )
    )
    assert overlong is not None


def test_vocabulary_three_has_the_same_operators_as_two():
    """The bump is about semantics, not operators."""
    from app.rule_engine import OPERATORS_BY_VOCABULARY_VERSION

    assert OPERATORS_BY_VOCABULARY_VERSION[3] == OPERATORS_BY_VOCABULARY_VERSION[2]
