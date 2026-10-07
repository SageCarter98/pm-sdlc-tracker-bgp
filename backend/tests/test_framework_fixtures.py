"""TST-010: distinct framework fixtures represent expected classes, roles
and gates without application code changes -- these are read and validated
exactly as a tenant's imported JSON would be (app.rule_engine), with no
framework-specific code anywhere in this test or the app.

TST-010 as originally written asked only for distinct "classes, roles and
gates", and that omission is the root cause of the vocabulary-indirection
defect: REQ-010 also requires templates to version their status and
decision schemes, but nothing here ever asserted the fixtures differed in
those, so three fixtures that all declared "Complete" satisfied the
verification for six work packages. The omitted half is now asserted by
test_fixtures_differ_in_status_and_outcome_schemes_too below."""

import json
from pathlib import Path

import pytest

from app.rule_engine import validate_template_schema

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks"
FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json"))

# agile.v3.json and agile.v4.json are deliberately the SAME framework as
# agile.json re-expressed in a later vocabulary: identical gate_ids,
# rule_ids, required_fields and guidance by design, so that the diff
# between each pair is exactly the semantics (see their _meta notes).
# Neither can contribute a distinct class set, role set or gate count, and
# neither must be counted as if it could -- what they earn their place with
# is semantics no other fixture expresses: v3 the status/outcome
# distinctness asserted by test_fixtures_differ_in_status_and_outcome_schemes_too,
# v4 the declared role capabilities (product_owner decides; developer and
# facilitator attest) that REQ-010's role scheme requires.
RESTATED_AGILE_STEMS = {"agile.v3", "agile.v4"}
DISTINCT_FRAMEWORK_FILES = [p for p in FIXTURE_FILES if p.stem not in RESTATED_AGILE_STEMS]


def test_fixture_files_exist():
    assert len(FIXTURE_FILES) == 6, f"expected 6 fixture frameworks, found {len(FIXTURE_FILES)}: {FIXTURE_FILES}"
    assert len(DISTINCT_FRAMEWORK_FILES) == 4, (
        f"expected 4 structurally distinct frameworks, found {len(DISTINCT_FRAMEWORK_FILES)}"
    )


@pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_each_fixture_is_a_valid_template_schema(fixture_path):
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data.pop("_meta", None)
    schema = validate_template_schema(data)
    assert len(schema.gates) >= 1


def test_fixtures_have_distinct_classes_roles_and_gate_counts():
    """The whole point of REQ-010 is that these differences come from data,
    not from one code path per framework -- so assert the fixtures actually
    differ from each other, not just that each independently validates.

    Counted against `len(DISTINCT_FRAMEWORK_FILES)` rather than a
    hardcoded number on purpose. These assertions previously read `== 3`,
    which a fourth fixture could satisfy while *colliding* with an existing
    one (four fixtures with gate counts {2, 2, 4, 6} still give a set of
    size 3 and would have passed for entirely the wrong reason). Tied to
    the file count, a collision fails instead of hiding.

    agile.v3.json and agile.v4.json are excluded by construction, not waved
    through: each is agile.json's own framework restated in a later
    vocabulary and is required to keep every gate_id and rule_id identical,
    so counting them here would force a structural difference those
    fixtures are specifically forbidden to have. See
    DISTINCT_FRAMEWORK_FILES."""
    parsed = []
    for path in DISTINCT_FRAMEWORK_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_meta", None)
        parsed.append(validate_template_schema(data))

    expected = len(DISTINCT_FRAMEWORK_FILES)
    class_sets = [frozenset(s.classes) for s in parsed]
    role_sets = [frozenset(s.roles) for s in parsed]
    gate_counts = [len(s.gates) for s in parsed]

    assert len(set(class_sets)) == expected, "every fixture should declare a distinct class set"
    assert len(set(role_sets)) == expected, "every fixture should declare a distinct role set"
    assert len(set(gate_counts)) == expected, f"gate counts collide: {sorted(gate_counts)}"


def test_only_non_validation_fixtures_are_shipped_as_starters():
    """DEC07 Q12 requires the agile fixture stay "a validation fixture, not
    a shipped starter template, until it has passed its own review".
    scripts/seed_starter_frameworks.py enforces that by skipping any
    fixture flagged `_meta.validation_fixture` -- this asserts the flag the
    script keys on is actually present, so the two can't drift apart.

    Deliberately not a blanket "exactly one is a validation fixture": a
    second one is legitimate. What must hold is that every fixture is
    explicitly one or the other, never silently defaulted into shipping."""
    starters, validation_only = [], []
    for path in FIXTURE_FILES:
        meta = json.loads(path.read_text(encoding="utf-8")).get("_meta", {})
        (validation_only if meta.get("validation_fixture") else starters).append(path.stem)

    for stem in ("agile", "agile.v3", "agile.v4"):
        assert stem in validation_only, (
            f"the {stem} DoR/DoD fixture must stay flagged as a validation fixture "
            "until DEC07 Q12's own review has passed"
        )
    assert sorted(starters) == ["lightweight", "regulated", "standard"], (
        f"unexpected set of shipped starter fixtures: {sorted(starters)}"
    )


def test_fixtures_differ_in_status_and_outcome_schemes_too():
    """G8, and the root cause of the whole vocabulary-indirection defect.
    REQ-010 requires templates to version "status" and "decision" schemes,
    but TST-010 only ever asked for "classes, roles and gates" -- so three
    fixtures were built that all declared "Complete" and the Blueprint's
    outcome words, and nothing exercised the difference for six work
    packages. This asserts the part the original verification omitted.

    One pass over the fixtures rather than the three the plan's draft used:
    parsing five files three times is the same assertion at three times the
    cost, and memory on this machine is the binding constraint."""
    status_sets, outcome_sets, satisfying_words = set(), set(), set()
    for path in FIXTURE_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_meta", None)
        schema = validate_template_schema(data)
        status_sets.add(frozenset(schema.status_lookup()))
        outcome_sets.add(frozenset(schema.outcome_lookup()))
        satisfying_words |= {d.id for d in schema.status_lookup().values() if d.satisfies}

    assert len(status_sets) > 1, "no fixture exercises a non-default status scheme"
    assert len(outcome_sets) > 1, "no fixture exercises a non-default outcome scheme"
    assert satisfying_words - {"Complete"}, (
        "every fixture's completion word is still 'Complete' -- the exact blind spot that let "
        "the vocabulary-indirection defect survive"
    )


def test_regulated_fixture_uses_conditional_applicability():
    """The regulated fixture is the one that actually exercises 'all'/'in'
    nesting (Sec.5.5) -- confirm at least one rule does, so this fixture
    earns its place rather than just being 'more of the same but bigger'."""
    data = json.loads((FIXTURES_DIR / "regulated.json").read_text(encoding="utf-8"))
    data.pop("_meta", None)
    schema = validate_template_schema(data)
    ops_used = set()
    for gate in schema.gates:
        for rule in gate.rules:
            for cond in (rule.applicability, rule.conditions):
                if cond is not None:
                    ops_used.add(cond.op)
                    if cond.conditions:
                        ops_used.update(c.op for c in cond.conditions)
    assert {"eq", "in", "all"}.issubset(ops_used)
