"""Golden pins for vocabulary 1-3 ROLE behaviour, written BEFORE role
indirection exists so later tasks cannot quietly change what a published
template means (spec G5).

The three gate-based fixtures declare only platform roles, so their
behaviour must be bit-identical after this work. agile.json declares none
of them, which is the defect this work closes -- so what is pinned for it
here is today's behaviour, deliberately, and Task 6 is where it changes.
"""

import json
from pathlib import Path

import pytest

from app.rule_engine import validate_template_schema

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks"

PLATFORM_DECIDERS = {"approver", "sponsor", "tenant_administrator"}


def _schema(name: str):
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return validate_template_schema(data)


@pytest.mark.parametrize("name", ["standard.json", "regulated.json", "lightweight.json"])
def test_the_gate_based_fixtures_declare_only_platform_roles(name):
    """If this ever fails, a fixture gained a custom role and the
    back-compat claims below stop covering what they say they cover."""
    schema = _schema(name)
    assert set(schema.roles) <= PLATFORM_DECIDERS | {"contributor", "assurance_reviewer"}


@pytest.mark.parametrize("name", ["standard.json", "regulated.json", "lightweight.json", "agile.json"])
def test_declared_roles_are_plain_strings_today(name):
    """Vocabulary 1-3 templates declare bare strings. Task 2 must keep
    parsing them; this is what proves it did not change their shape."""
    schema = _schema(name)
    assert all(isinstance(entry, str) for entry in schema.roles), schema.roles


def test_agile_declares_no_platform_assignable_role():
    """The defect this work closes, pinned as today's fact so Task 6's
    change is visible as a deliberate change rather than a silent diff."""
    schema = _schema("agile.json")
    assert set(schema.roles) == {"product_owner", "developer", "facilitator"}
    assert not (set(schema.roles) & (PLATFORM_DECIDERS | {"contributor", "assurance_reviewer"}))
