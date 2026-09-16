"""TST-010: three distinct framework fixtures represent expected classes,
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
    assert len(FIXTURE_FILES) == 3, f"expected 3 fixture frameworks, found {len(FIXTURE_FILES)}: {FIXTURE_FILES}"


@pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_each_fixture_is_a_valid_template_schema(fixture_path):
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data.pop("_meta", None)
    schema = validate_template_schema(data)
    assert len(schema.gates) >= 1


def test_fixtures_have_distinct_classes_roles_and_gate_counts():
    """The whole point of REQ-010 is that these differences come from data,
    not from three different code paths -- so assert the fixtures actually
    differ from each other, not just that each independently validates."""
    parsed = []
    for path in FIXTURE_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_meta", None)
        parsed.append(validate_template_schema(data))

    class_sets = [frozenset(s.classes) for s in parsed]
    role_sets = [frozenset(s.roles) for s in parsed]
    gate_counts = [len(s.gates) for s in parsed]

    assert len(set(class_sets)) == 3, "fixtures should not all declare the same classes"
    assert len(set(role_sets)) == 3, "fixtures should not all declare the same roles"
    assert len(set(gate_counts)) == 3, "fixtures should not all have the same number of gates"


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
