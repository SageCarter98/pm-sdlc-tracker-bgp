"""Golden pins for vocabulary 1-3 role DECLARATION SHAPE, written BEFORE
role indirection exists so later tasks cannot quietly change what a
published template means (spec G5).

This file pins declaration shape only: what each fixture's `roles` list
contains, and that every vocabulary 1-3 entry is a plain string. It does
NOT pin runtime role *behaviour* -- whether a role may actually attest an
item, or decide a gate, are different questions, and "may decide" does not
imply "may attest". Those are pinned separately, at vocabulary 1, in
tests/test_permitted_role_enforcement.py (its regulated.json/R2.R1-based
tests).

The three gate-based fixtures declare only platform roles, so their
declared shape must be bit-identical after this work. agile.json declares
none of them, which is the defect this work closes -- so what is pinned for
it here is today's declaration, deliberately, and Task 6 is where it
changes.
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


def test_the_platform_deciders_literal_matches_the_live_decision_authority_roles():
    """PLATFORM_DECIDERS above is deliberately a hand-copied literal, not an
    import of app.routers.decisions.DECISION_AUTHORITY_ROLES -- a golden
    file must encode its expectation independently, or editing the thing
    under test would make this file agree with it automatically, which is
    the opposite of a tripwire. This test is the ONLY place the two are
    linked. A later task in this plan is expected to rename
    DECISION_AUTHORITY_ROLES to TENANT_DECISION_AUTHORITY_ROLES; when it
    does, this one assertion will fail here, which is correct -- it forces
    that rename to confront this baseline as one deliberate edit, rather
    than the baseline silently drifting out of sync."""
    from app.routers.decisions import DECISION_AUTHORITY_ROLES

    assert PLATFORM_DECIDERS == DECISION_AUTHORITY_ROLES
