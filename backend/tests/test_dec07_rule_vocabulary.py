"""DEC07 Q10 (docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md
lines 119-132): the approved vocabulary additions and tightenings.

Verbatim, so the tests below can be checked against it rather than a
paraphrase: "Approved as-is, plus three additions and two tightenings.
Add: `not` (without negation, authors write contorted rules to fake it);
`gte`/`lte` for dates and counts; `count(...)` with a comparison, because
'at least N of these complete' is a genuinely common governance rule.
Tighten: cap total condition nodes at 200 in addition to the depth-5
limit, and add a hard evaluation timeout. Rules must be pure functions of
project state plus a supplied 'as at' timestamp -- no external calls, no
wall-clock reads inside the rule itself. Stamp `vocabulary_version` on
every template version so old templates evaluate identically forever,
regardless of later vocabulary changes. Resist adding anything beyond
this."

That last sentence is a scope instruction, and these tests hold it: no
operator beyond not/gte/lte/count is added, and `count`'s comparison
reuses eq/gte/lte rather than introducing a fourth comparison form.

Pure in-process tests -- the rule engine touches no database, so no
Postgres skip marker here, unlike the RLS-dependent suites.
"""

import copy

import pytest

from app.rule_engine import (
    MAX_CONDITION_NODES,
    VOCABULARY_VERSION,
    Condition,
    RuleEvaluationTimeout,
    RuleValidationError,
    evaluate_condition,
    validate_template_schema,
)
from tests.test_rule_engine import MINIMAL_VALID_TEMPLATE


def _template_with_condition(condition: dict, *, vocabulary_version: int | None = VOCABULARY_VERSION) -> dict:
    data = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    if vocabulary_version is not None:
        data["vocabulary_version"] = vocabulary_version
    data["gates"][0]["rules"][0]["conditions"] = condition
    return data


# --- `not` -------------------------------------------------------------


def test_not_negates_its_single_nested_condition():
    cond = Condition(op="not", conditions=[Condition(op="eq", fact="a", value=1)])
    assert evaluate_condition(cond, {"a": 1}) is False
    assert evaluate_condition(cond, {"a": 2}) is True


def test_not_of_an_unknown_fact_is_true_because_the_inner_test_fails_closed():
    """Documents a real consequence of combining `not` with Sec.5.5's
    fail-closed unknown-fact rule, rather than leaving it to be discovered:
    an unknown fact makes the inner test False, so `not` reports True. A
    rule author writing `not(eq(fact, x))` against a fact the project state
    never supplies gets a passing condition, not a failing one."""
    cond = Condition(op="not", conditions=[Condition(op="eq", fact="missing", value=1)])
    assert evaluate_condition(cond, {}) is True


def test_not_requires_exactly_one_nested_condition():
    with pytest.raises(ValueError):
        Condition(op="not", conditions=[])
    with pytest.raises(ValueError):
        Condition(
            op="not",
            conditions=[Condition(op="eq", fact="a", value=1), Condition(op="eq", fact="b", value=2)],
        )


def test_not_does_not_take_a_bare_fact():
    with pytest.raises(ValueError):
        Condition(op="not", fact="a", value=1)


# --- `gte` / `lte` -----------------------------------------------------


@pytest.mark.parametrize(
    ("op", "fact_value", "threshold", "expected"),
    [
        ("gte", 5, 3, True),
        ("gte", 3, 3, True),
        ("gte", 2, 3, False),
        ("lte", 2, 3, True),
        ("lte", 3, 3, True),
        ("lte", 5, 3, False),
    ],
)
def test_gte_and_lte_over_counts(op, fact_value, threshold, expected):
    cond = Condition(op=op, fact="n", value=threshold)
    assert evaluate_condition(cond, {"n": fact_value}) is expected


def test_gte_and_lte_over_iso_dates():
    """DEC07 names these as "for dates and counts". ISO-8601 strings in a
    single consistent format compare correctly lexicographically, which is
    how project state already carries dates through template JSON."""
    cond = Condition(op="gte", fact="completed_date", value="2026-01-01")
    assert evaluate_condition(cond, {"completed_date": "2026-06-30"}) is True
    assert evaluate_condition(cond, {"completed_date": "2025-12-31"}) is False


def test_gte_and_lte_fail_closed_on_unknown_facts():
    assert evaluate_condition(Condition(op="gte", fact="missing", value=1), {}) is False
    assert evaluate_condition(Condition(op="lte", fact="missing", value=1), {}) is False


def test_gte_and_lte_fail_closed_on_incomparable_types_instead_of_raising():
    """A tenant-authored rule comparing a string fact against a numeric
    threshold would raise TypeError in Python 3. Failing closed keeps a
    bad rule from taking down project creation, consistent with how
    unknown facts already behave."""
    assert evaluate_condition(Condition(op="gte", fact="s", value=1), {"s": "not-a-number"}) is False
    assert evaluate_condition(Condition(op="lte", fact="s", value=1), {"s": None}) is False


def test_gte_requires_a_fact_and_rejects_nested_conditions():
    with pytest.raises(ValueError):
        Condition(op="gte", value=1)
    with pytest.raises(ValueError):
        Condition(op="gte", fact="a", value=1, conditions=[Condition(op="eq", fact="b", value=2)])


# --- `count(...)` with a comparison ------------------------------------


def _count_cond(compare: str, value: int) -> Condition:
    return Condition(
        op="count",
        compare=compare,
        value=value,
        conditions=[
            Condition(op="eq", fact="a", value="done"),
            Condition(op="eq", fact="b", value="done"),
            Condition(op="eq", fact="c", value="done"),
        ],
    )


def test_count_gte_is_the_at_least_n_of_these_rule_dec07_names():
    cond = _count_cond("gte", 2)
    assert evaluate_condition(cond, {"a": "done", "b": "done", "c": "no"}) is True
    assert evaluate_condition(cond, {"a": "done", "b": "no", "c": "no"}) is False


def test_count_eq_and_lte():
    assert evaluate_condition(_count_cond("eq", 3), {"a": "done", "b": "done", "c": "done"}) is True
    assert evaluate_condition(_count_cond("eq", 3), {"a": "done", "b": "done", "c": "no"}) is False
    assert evaluate_condition(_count_cond("lte", 1), {"a": "done", "b": "no", "c": "no"}) is True
    assert evaluate_condition(_count_cond("lte", 1), {"a": "done", "b": "done", "c": "no"}) is False


def test_count_counts_satisfied_subconditions_not_facts_present():
    cond = _count_cond("gte", 1)
    assert evaluate_condition(cond, {}) is False


def test_count_requires_a_comparison_and_an_integer_target():
    with pytest.raises(ValueError):
        Condition(op="count", conditions=[Condition(op="eq", fact="a", value=1)], value=1)  # no compare
    with pytest.raises(ValueError):
        Condition(op="count", compare="gte", conditions=[Condition(op="eq", fact="a", value=1)])  # no value
    with pytest.raises(ValueError):
        Condition(op="count", compare="gte", value="two", conditions=[Condition(op="eq", fact="a", value=1)])


def test_count_rejects_a_boolean_target_despite_bool_being_an_int_in_python():
    """`True` is an instance of `int` in Python, so a naive isinstance
    check would accept `count >= True`. Caught deliberately."""
    with pytest.raises(ValueError):
        Condition(op="count", compare="gte", value=True, conditions=[Condition(op="eq", fact="a", value=1)])


def test_count_rejects_a_comparison_outside_the_approved_vocabulary():
    with pytest.raises(ValueError):
        Condition(op="count", compare="gt", value=1, conditions=[Condition(op="eq", fact="a", value=1)])


# --- node cap (tightening 1) -------------------------------------------


def test_a_rule_within_the_node_cap_validates():
    flat = {"op": "all", "conditions": [{"op": "eq", "fact": f"f{i}", "value": i} for i in range(50)]}
    assert validate_template_schema(_template_with_condition(flat)) is not None


def test_total_condition_nodes_above_the_cap_are_rejected():
    oversized = {
        "op": "all",
        "conditions": [{"op": "eq", "fact": f"f{i}", "value": i} for i in range(MAX_CONDITION_NODES + 1)],
    }
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(_template_with_condition(oversized))
    assert "node" in str(exc.value).lower()


def test_the_node_cap_counts_applicability_and_conditions_together():
    """DEC07's words are "cap total condition nodes at 200". Read as the
    total a rule evaluates, not per tree -- so two trees of 150 nodes each
    is 300 and over the cap, even though neither tree alone exceeds it.
    The stricter reading, since bounding evaluation cost is the stated
    purpose; flagged in the engine's own comment as an interpretation."""
    half = MAX_CONDITION_NODES // 2 + 10
    data = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    data["vocabulary_version"] = VOCABULARY_VERSION
    rule = data["gates"][0]["rules"][0]
    rule["applicability"] = {
        "op": "all",
        "conditions": [{"op": "eq", "fact": f"a{i}", "value": i} for i in range(half)],
    }
    rule["conditions"] = {
        "op": "all",
        "conditions": [{"op": "eq", "fact": f"c{i}", "value": i} for i in range(half)],
    }
    with pytest.raises(RuleValidationError):
        validate_template_schema(data)


def test_the_depth_limit_still_applies_independently_of_the_node_cap():
    """A deeply nested but tiny tree breaches depth 5 while nowhere near
    200 nodes -- DEC07 adds the node cap "in addition to" the depth limit,
    so neither replaces the other."""
    cond: dict = {"op": "eq", "fact": "a", "value": 1}
    for _ in range(6):
        cond = {"op": "all", "conditions": [cond]}
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(_template_with_condition(cond))
    assert "depth" in str(exc.value).lower()


# --- hard evaluation timeout (tightening 2) ----------------------------


def test_evaluation_raises_when_it_exceeds_its_deadline():
    """The timeout is defence in depth, not the primary bound -- a tree
    already capped at depth 5 and 200 nodes evaluates in microseconds. A
    zero-length budget is the only honest way to prove the deadline is
    actually enforced rather than declared."""
    cond = Condition(
        op="all",
        conditions=[Condition(op="eq", fact=f"f{i}", value=i) for i in range(20)],
    )
    with pytest.raises(RuleEvaluationTimeout):
        evaluate_condition(cond, {f"f{i}": i for i in range(20)}, timeout_seconds=0.0)


def test_normal_evaluation_stays_well_inside_the_default_budget():
    cond = Condition(
        op="all",
        conditions=[Condition(op="eq", fact=f"f{i}", value=i) for i in range(MAX_CONDITION_NODES - 1)],
    )
    assert evaluate_condition(cond, {f"f{i}": i for i in range(MAX_CONDITION_NODES)}) is True


# --- purity: supplied "as at" timestamp --------------------------------


def test_as_at_is_supplied_by_the_caller_and_readable_as_a_fact():
    """DEC07: "pure functions of project state plus a supplied 'as at'
    timestamp -- no external calls, no wall-clock reads inside the rule
    itself." The engine never calls datetime.now(); a date-comparing rule
    reads the timestamp the caller supplied."""
    cond = Condition(op="lte", fact="as_at", value="2026-12-31")
    assert evaluate_condition(cond, {}, as_at="2026-06-01") is True
    assert evaluate_condition(cond, {}, as_at="2027-06-01") is False


def test_as_at_is_absent_unless_supplied_so_rules_relying_on_it_fail_closed():
    cond = Condition(op="lte", fact="as_at", value="2026-12-31")
    assert evaluate_condition(cond, {}) is False


def test_as_at_must_be_an_iso_string_not_a_datetime_or_date_rules_fail_closed_silently():
    """Pins the integration hazard this nearly shipped with. Template JSON
    has no date type, so a rule's threshold is always a string; a datetime
    compared against a string raises TypeError, which _compare turns into
    a fail-closed False. A date-based rule would then NEVER fire in
    production while passing every unit test that used strings on both
    sides. app/routers/projects.py passes `.isoformat()` because of this."""
    from datetime import datetime, timezone

    cond = Condition(op="lte", fact="as_at", value="2026-12-31")
    assert evaluate_condition(cond, {}, as_at=datetime(2026, 6, 1, tzinfo=timezone.utc)) is False
    assert evaluate_condition(cond, {}, as_at=datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat()) is True


def test_a_timestamp_is_lexicographically_after_the_bare_date_it_falls_on():
    """The documented boundary quirk of comparing dates as text, pinned so
    a future change to date handling has to confront it deliberately."""
    cond = Condition(op="lte", fact="as_at", value="2026-10-02")
    assert evaluate_condition(cond, {}, as_at="2026-10-02T05:00:00+00:00") is False
    assert evaluate_condition(cond, {}, as_at="2026-10-02") is True


def test_a_supplied_fact_cannot_shadow_the_platform_as_at_value():
    """Project state is tenant-influenced; the evaluation timestamp is
    not. If both carry `as_at`, the caller-supplied timestamp wins."""
    cond = Condition(op="lte", fact="as_at", value="2026-12-31")
    assert evaluate_condition(cond, {"as_at": "2020-01-01"}, as_at="2027-06-01") is False


# --- vocabulary_version ------------------------------------------------


def test_a_template_omitting_vocabulary_version_defaults_to_1():
    """Every already-published version predates this field, and published
    versions are immutable (REQ-011) -- so the default is what gives them
    "evaluate identically forever" without a migration or a backfill."""
    data = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    assert "vocabulary_version" not in data
    assert validate_template_schema(data).vocabulary_version == 1


def test_a_version_1_template_cannot_use_the_operators_dec07_added():
    """The whole point of stamping the version: a template authored against
    vocabulary 1 keeps evaluating under vocabulary 1, so introducing new
    operators cannot change how it behaves."""
    for condition in (
        {"op": "not", "conditions": [{"op": "eq", "fact": "a", "value": 1}]},
        {"op": "gte", "fact": "n", "value": 1},
        {"op": "lte", "fact": "n", "value": 1},
        {"op": "count", "compare": "gte", "value": 1, "conditions": [{"op": "eq", "fact": "a", "value": 1}]},
    ):
        with pytest.raises(RuleValidationError) as exc:
            validate_template_schema(_template_with_condition(condition, vocabulary_version=1))
        assert "vocabulary" in str(exc.value).lower()


def test_a_current_vocabulary_template_may_use_them():
    for condition in (
        {"op": "not", "conditions": [{"op": "eq", "fact": "a", "value": 1}]},
        {"op": "gte", "fact": "n", "value": 1},
        {"op": "count", "compare": "gte", "value": 1, "conditions": [{"op": "eq", "fact": "a", "value": 1}]},
    ):
        assert validate_template_schema(_template_with_condition(condition)) is not None


def test_version_1_still_accepts_the_original_four_operators():
    for condition in (
        {"op": "eq", "fact": "a", "value": 1},
        {"op": "in", "fact": "a", "value": [1, 2]},
        {"op": "all", "conditions": [{"op": "eq", "fact": "a", "value": 1}]},
        {"op": "any", "conditions": [{"op": "eq", "fact": "a", "value": 1}]},
    ):
        assert validate_template_schema(_template_with_condition(condition, vocabulary_version=1)) is not None


def test_an_unknown_future_vocabulary_version_is_rejected():
    with pytest.raises(RuleValidationError):
        validate_template_schema(
            _template_with_condition({"op": "eq", "fact": "a", "value": 1}, vocabulary_version=VOCABULARY_VERSION + 1)
        )


def test_the_authoring_ui_describes_the_new_operators_in_plain_language():
    """UI08's read-back renderer fell through to "Unrecognised condition
    shape" for anything outside eq/in/all/any, so adding operators to the
    engine alone would have made a valid rule look broken in the authoring
    view. Creating them from the guided form is still out of scope (that is
    DEC07's own anticipated UI pass); reading them back is not."""
    from app.webapp.router import _describe_condition

    assert _describe_condition({"op": "not", "conditions": [{"op": "eq", "fact": "waived", "value": True}]}) == (
        "NOT waived = True"
    )
    assert _describe_condition({"op": "gte", "fact": "score", "value": 3}) == "score is at least 3"
    assert _describe_condition({"op": "lte", "fact": "score", "value": 3}) == "score is at most 3"
    assert (
        _describe_condition(
            {
                "op": "count",
                "compare": "gte",
                "value": 2,
                "conditions": [{"op": "eq", "fact": "a", "value": "Complete"}],
            }
        )
        == "at least 2 of [a = 'Complete']"
    )
    assert "Unrecognised" not in _describe_condition(
        {"op": "all", "conditions": [{"op": "not", "conditions": [{"op": "eq", "fact": "a", "value": 1}]}]}
    )


def test_the_applicability_tree_is_vocabulary_gated_too_not_just_conditions():
    data = copy.deepcopy(MINIMAL_VALID_TEMPLATE)
    data["vocabulary_version"] = 1
    data["gates"][0]["rules"][0]["applicability"] = {"op": "gte", "fact": "n", "value": 1}
    with pytest.raises(RuleValidationError) as exc:
        validate_template_schema(data)
    assert "vocabulary" in str(exc.value).lower()
