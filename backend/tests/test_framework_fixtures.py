"""TST-010: four distinct framework fixtures represent expected classes,
roles and gates without application code changes -- these are read and
validated exactly as a tenant's imported JSON would be (app.rule_engine),
with no framework-specific code anywhere in this test or the app."""

import json
from pathlib import Path

import pytest

from app.rule_engine import validate_template_schema

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks"
FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json"))


def test_fixture_files_exist():
    assert len(FIXTURE_FILES) == 4, f"expected 4 fixture frameworks, found {len(FIXTURE_FILES)}: {FIXTURE_FILES}"


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

    Counted against `len(FIXTURE_FILES)` rather than a hardcoded number on
    purpose. These assertions previously read `== 3`, which a fourth
    fixture could satisfy while *colliding* with an existing one (four
    fixtures with gate counts {2, 2, 4, 6} still give a set of size 3 and
    would have passed for entirely the wrong reason). Tied to the file
    count, a collision fails instead of hiding."""
    parsed = []
    for path in FIXTURE_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_meta", None)
        parsed.append(validate_template_schema(data))

    expected = len(FIXTURE_FILES)
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

    assert "agile" in validation_only, (
        "the agile DoR/DoD fixture must stay flagged as a validation fixture until DEC07 Q12's own review has passed"
    )
    assert sorted(starters) == ["lightweight", "regulated", "standard"], (
        f"unexpected set of shipped starter fixtures: {sorted(starters)}"
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
