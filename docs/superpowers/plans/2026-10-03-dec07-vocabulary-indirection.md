# DEC07 Vocabulary Indirection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a framework template's declared status and decision-outcome vocabulary genuinely govern readiness, so the literal `"Complete"` and the Blueprint's five English outcome words stop being hardcoded in the engine.

**Architecture:** `statuses` and `decision_outcomes` accept structured entries carrying their own semantics (`satisfies`, `requires_exception`, `initial`, `kind`); plain strings still parse and normalise per `vocabulary_version`, which is how every already-published template keeps evaluating identically with no migration. A new `vocabulary_version: 3` gates the new semantics and additionally turns on evaluation of a rule's `conditions` tree against facts built from the occurrence's own evidence items.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, pytest, Jinja2, Ruff 0.9.6.

**Spec:** `docs/superpowers/specs/2026-10-03-dec07-vocabulary-indirection-design.md`

## Global Constraints

- **No migration and no table change.** `EvidenceItem.status` is already a free string; every existing row belongs to a project bound to a v1/v2 version. Spec §5.
- **Status ids are capped at 30 characters.** `EvidenceItem.status` and `EvidenceRevision.status` are `String(30)` (`app/models.py:327,356`). A longer id must be rejected at publish time, or it fails at revision time with a database error. Spec §5.
- **Published template versions are immutable (REQ-011).** Never edit a published `schema_json`. The agile fixture gets a *new version*, never an in-place change.
- **Vocabulary 1 and 2 behaviour must not change at all (G6).** Task 1 pins this with golden tests that must stay green through every later task.
- **`"Complete"` is a state concept, not a mandated literal** — owner ruling, 2026-10-03, recorded in spec §1 decision 7. This licenses removing the literal from readiness paths.
- **Rules stay pure (DEC07 Q10).** No clock read inside a rule, no external call. Facts derive from committed rows plus the supplied `as_at`.
- **`conditions` may only withhold satisfaction, never grant it.** Spec §4.4.
- **Fail closed everywhere.** An unknown status, an unknown fact, or an unresolvable reference means *not satisfied* — never satisfied-by-default.
- **Line length 120**, Ruff `check` + `format` must both pass (`backend/pyproject.toml`).
- **Run tests in chunks.** This machine has 3.46 GB RAM and cannot complete a single-process full suite; two attempts were OOM-killed. Use per-file runs during tasks and a chunked sweep at the end.
- **Never record a gate decision.** Evidence items and documentation only.

## Review Focus

These are input classes the spec implies but which no task's happy path exercises. Each has a test assigned to the task owning the code.

1. **Near-miss status ids** — `"met"`, `" Met"`, `"MET"` against a declared `"Met"`. Lookup must be exact, and a near-miss must be *rejected at the revision endpoint*, not silently stored as non-satisfying. (Task 4)
2. **The 30-character boundary** — an id of exactly 30 chars must publish; 31 must be rejected. Off-by-one here reaches the database as an error rather than a validation message. (Task 2)
3. **A stored status the bound template no longer declares** — reachable for legacy rows and anything that rebinds. Readiness must treat it as not satisfying and must not raise. (Task 3)
4. **`item:` facts for rules that were never seeded** — applicability can filter a rule out, so `item:<rule_id>` has no row. The fact is unknown and must fail closed, not error. (Task 6)
5. **A `requires_exception` status whose exception expired between preview and commit** — the locked readiness path must re-check validity, or an expired exception silently approves. (Task 3)

---

### Task 1: Pin vocabulary 1/2 behaviour before changing anything

This task writes no production code. It captures today's behaviour as golden tests so every later task has to prove it preserved it. G6 has no other real proof.

**Files:**
- Create: `backend/tests/test_dec07_vocabulary_backcompat.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `golden_readiness(client, tenant_id, project_id, occurrence_id) -> dict` — a normalised readiness snapshot used by this file only.

- [ ] **Step 1: Write the failing test**

```python
"""G6: vocabulary 1/2 templates must evaluate identically forever.

Written BEFORE the vocabulary-indirection change and must stay green
through every task of it. If one of these fails, back-compat broke --
that is the whole purpose of this file, so do not "update the
expectation" to match new behaviour.
"""

import json
from pathlib import Path

import pytest

from tests.conftest import enable_mfa, register_and_login

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks"
V1_V2_FIXTURES = ["standard", "regulated", "lightweight"]


def _schema(stem: str) -> dict:
    data = json.loads((FIXTURES_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


def _publish(client, tenant_id: str, stem: str) -> str:
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": stem, "schema_json": _schema(stem)}
    ).json()
    resp = client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    assert resp.status_code == 200, resp.text
    return created["id"]


@pytest.mark.parametrize("stem", V1_V2_FIXTURES)
def test_seeded_items_start_in_not_started(client, stem):
    """Today's seeding literal. A v1/v2 template must keep producing
    exactly 'Not started', because its stored rows already say so."""
    register_and_login(client, "admin@backcompat.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "BC Co"}).json()["id"]
    version_id = _publish(client, tenant_id, stem)
    schema = _schema(stem)

    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "BC project",
            "template_version_id": version_id,
            "class_id": schema["classes"][0],
            "members": [],
        },
    )
    assert created.status_code == 201, created.text
    items = created.json()["evidence_items"]
    assert items, f"{stem} seeded no evidence items for class {schema['classes'][0]}"
    assert {i["status"] for i in items} == {"Not started"}


@pytest.mark.parametrize("stem", V1_V2_FIXTURES)
def test_complete_still_clears_a_blocker_and_permits_the_declared_outcomes(client, stem):
    """The literal 'Complete' must keep working for v1/v2, and the
    permitted-outcome list must be unchanged."""
    register_and_login(client, "admin@backcompat.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "BC Co"}).json()["id"]
    version_id = _publish(client, tenant_id, stem)
    schema = _schema(stem)
    class_id = schema["classes"][0]

    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "BC project", "template_version_id": version_id, "class_id": class_id, "members": []},
    ).json()
    project_id = created["project"]["id"]
    occurrence_id = created["occurrences"][0]["id"]
    gate_id = created["occurrences"][0]["gate_id"]

    for item in created["evidence_items"]:
        if item["gate_id"] == gate_id and item["blocker_level"] in ("hard", "conditional"):
            resp = client.post(
                f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
                json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
            )
            assert resp.status_code == 201, resp.text

    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/preview", json={}
    ).json()
    assert preview["hard_blockers"] == []
    assert preview["conditional_blockers"] == []

    assert set(preview["permitted_outcomes"]) <= set(schema["decision_outcomes"])
    assert "Approve" in preview["permitted_outcomes"], (
        "Approve must stay permitted once blockers clear, for every v1/v2 fixture"
    )


@pytest.mark.parametrize("stem", V1_V2_FIXTURES)
def test_rule_conditions_are_still_not_evaluated_for_v1_v2(client, stem):
    """G6 specifically: turning conditions on for v3 must not turn it on
    for v1/v2. Completing a hard item clears its blocker even though no
    facts are ever supplied to satisfy its conditions tree."""
    register_and_login(client, "admin@backcompat.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "BC Co"}).json()["id"]
    version_id = _publish(client, tenant_id, stem)
    schema = _schema(stem)
    class_id = schema["classes"][0]

    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "BC project", "template_version_id": version_id, "class_id": class_id, "members": []},
    ).json()
    project_id = created["project"]["id"]
    occurrence = created["occurrences"][0]

    hard = [
        i
        for i in created["evidence_items"]
        if i["gate_id"] == occurrence["gate_id"] and i["blocker_level"] == "hard"
    ]
    if not hard:
        pytest.skip(f"{stem}'s first occurrence has no hard item to prove this with")

    for item in hard:
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
        )

    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence['id']}/preview", json={}
    ).json()
    assert preview["hard_blockers"] == []
```

- [ ] **Step 2: Run the tests and verify they PASS against current code**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_vocabulary_backcompat.py -q`
Expected: **PASS** (9 tests: 3 fixtures × 3 tests). These describe behaviour that already exists — unlike every other test in this plan, they must be green immediately. A failure here means the baseline was written wrong; fix the test, not the app.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_dec07_vocabulary_backcompat.py
git commit -m "test: pin vocabulary 1/2 readiness behaviour before changing it

G6's only real proof. Written against current behaviour and must stay
green through the whole vocabulary-indirection change."
```

---

### Task 2: Status and outcome definitions, normalisation, vocabulary 3

Schema layer only. Nothing is wired to readiness yet, so no behaviour changes.

**Files:**
- Modify: `backend/app/rule_engine.py:49-58` (version table), and the `TemplateSchema` class at `:242`
- Create: `backend/tests/test_dec07_status_semantics.py`

**Interfaces:**
- Produces:
  - `class StatusDefinition(BaseModel)` with `id: str`, `satisfies: bool`, `requires_exception: bool`, `initial: bool`
  - `class OutcomeDefinition(BaseModel)` with `id: str`, `kind: Literal["approving", "conditional_approving", "recording"]`
  - `TemplateSchema.status_lookup() -> dict[str, StatusDefinition]`
  - `TemplateSchema.outcome_lookup() -> dict[str, OutcomeDefinition]`
  - `TemplateSchema.initial_status() -> str`
  - `VOCABULARY_VERSION = 3`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_status_semantics.py -q`
Expected: FAIL — `ImportError`/`AttributeError` on `status_lookup`, and `KeyError: 3` on the operator table.

- [ ] **Step 3: Write the implementation**

In `backend/app/rule_engine.py`, change the version constants:

```python
VOCABULARY_VERSION = 3

OPERATORS_BY_VOCABULARY_VERSION: dict[int, set[str]] = {
    1: {"eq", "in", "all", "any"},
    2: {"eq", "in", "all", "any", "not", "gte", "lte", "count"},
    # Vocabulary 3 adds NO operators. The bump carries semantics instead:
    # structured status/outcome entries (StatusDefinition/OutcomeDefinition
    # below) and evaluation of a rule's `conditions` tree. Stated here
    # because "same set as 2" otherwise looks like a copy-paste slip.
    3: {"eq", "in", "all", "any", "not", "gte", "lte", "count"},
}
```

Add, above `TemplateSchema`:

```python
# EvidenceItem.status / EvidenceRevision.status are String(30)
# (app/models.py). A longer id validates happily and then fails at
# revision time as a database error, so it is rejected here instead.
MAX_STATUS_ID_LENGTH = 30

# v1/v2 templates declare bare strings. These two maps are what make
# "old templates evaluate identically forever" (DEC07 Q10) true with no
# migration: today's hardcoded literals, expressed as data.
_LEGACY_SATISFYING_STATUS = "Complete"
_LEGACY_INITIAL_STATUS = "Not started"
_LEGACY_OUTCOME_KINDS = {
    "Approve": "approving",
    "Approve with conditions": "conditional_approving",
    "Hold": "recording",
    "Redirect": "recording",
    "Terminate": "recording",
}


class StatusDefinition(BaseModel):
    """One evidence status plus what it MEANS, so readiness can ask the
    template instead of matching an English word."""

    id: str = Field(min_length=1, max_length=MAX_STATUS_ID_LENGTH)
    satisfies: bool = False
    # A satisfying status that must be justified by a valid ExceptionRecord
    # (REQ-020) rather than freely chosen. Without this, declaring an extra
    # satisfying status would be a route around a hard blocker.
    requires_exception: bool = False
    initial: bool = False


class OutcomeDefinition(BaseModel):
    """`kind` carries exactly the three behaviours _outcome_eligibility
    hardcodes today for the Blueprint's five words."""

    id: str = Field(min_length=1)
    kind: Literal["approving", "conditional_approving", "recording"]
```

In `TemplateSchema`, widen the two fields and add the lookups:

```python
    statuses: list[str | StatusDefinition] = Field(min_length=1)
    decision_outcomes: list[str | OutcomeDefinition] = Field(min_length=1)
```

```python
    def status_lookup(self) -> dict[str, StatusDefinition]:
        """Normalise mixed strings/objects into one lookup. Plain strings
        resolve per vocabulary_version -- that is the whole back-compat
        mechanism (G6)."""
        out: dict[str, StatusDefinition] = {}
        for entry in self.statuses:
            if isinstance(entry, StatusDefinition):
                out[entry.id] = entry
                continue
            if self.vocabulary_version <= 2:
                out[entry] = StatusDefinition(
                    id=entry,
                    satisfies=(entry == _LEGACY_SATISFYING_STATUS),
                    initial=(entry == _LEGACY_INITIAL_STATUS),
                )
            else:
                out[entry] = StatusDefinition(id=entry)
        return out

    def outcome_lookup(self) -> dict[str, OutcomeDefinition]:
        """An outcome with no resolvable kind is OMITTED, not defaulted --
        preserving today's honest refusal for a v1/v2 template declaring
        an outcome this prototype never handled."""
        out: dict[str, OutcomeDefinition] = {}
        for entry in self.decision_outcomes:
            if isinstance(entry, OutcomeDefinition):
                out[entry.id] = entry
                continue
            kind = _LEGACY_OUTCOME_KINDS.get(entry)
            if kind is not None:
                out[entry] = OutcomeDefinition(id=entry, kind=kind)
        return out

    def initial_status(self) -> str:
        """G7: the status a seeded item starts in comes from the template,
        never from a literal in the seeding code."""
        for definition in self.status_lookup().values():
            if definition.initial:
                return definition.id
        # Unreachable for v3 (validated) and for any v1/v2 template
        # declaring "Not started". A v1/v2 template that omits it falls
        # back to the first declared status, which is what the old literal
        # effectively meant for such a template.
        return next(iter(self.status_lookup()))
```

Extend `_cross_references_resolve` with the v3 rules. Add this before its `if errors:` return:

```python
        status_defs = list(self.status_lookup().values())
        declared_ids = [
            entry.id if isinstance(entry, StatusDefinition) else entry for entry in self.statuses
        ]
        if len(declared_ids) != len(set(declared_ids)):
            errors.append("duplicate status id declared")
        for definition in status_defs:
            if definition.requires_exception and not definition.satisfies:
                errors.append(
                    f"status '{definition.id}': requires_exception is meaningless without satisfies"
                )

        if self.vocabulary_version >= 3:
            if sum(1 for d in status_defs if d.initial) != 1:
                errors.append("vocabulary 3 requires exactly one status with initial: true")
            if not any(d.satisfies for d in status_defs):
                errors.append("vocabulary 3 requires at least one status with satisfies: true")
            for entry in self.decision_outcomes:
                if not isinstance(entry, OutcomeDefinition):
                    errors.append(
                        f"decision outcome '{entry}': vocabulary 3 requires an explicit kind "
                        f"(approving | conditional_approving | recording)"
                    )
```

Note on the length cap: `StatusDefinition.id` carries `max_length=30`, so a structured entry is caught by Pydantic. A **plain string** longer than 30 is not, so also add to the same block:

```python
        for status_id in declared_ids:
            if len(status_id) > MAX_STATUS_ID_LENGTH:
                errors.append(
                    f"status '{status_id}' exceeds the {MAX_STATUS_ID_LENGTH}-character limit "
                    f"imposed by EvidenceItem.status"
                )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_status_semantics.py -q`
Expected: PASS

- [ ] **Step 5: Verify back-compat and the existing suite are untouched**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_vocabulary_backcompat.py tests/test_rule_engine.py tests/test_dec07_rule_vocabulary.py tests/test_framework_fixtures.py tests/test_templates.py -q
```
Expected: PASS, no failures. If `test_framework_fixtures.py` or `test_templates.py` fails, the widened field types broke an existing assumption — fix the production code, not the test.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/rule_engine.py backend/tests/test_dec07_status_semantics.py
git commit -m "feat: structured status/outcome semantics and vocabulary 3

Schema layer only -- nothing is wired to readiness yet, so no behaviour
changes. Plain strings normalise per vocabulary_version, which is the
back-compat mechanism for every published template."
```

---

### Task 3: Readiness asks the template, not the word "Complete"

**Files:**
- Modify: `backend/app/routers/decisions.py:95` (`_compute_readiness` signature), `:125` (the literal), and the three call sites at `:493`, `:604`, `:1096`
- Modify: `backend/app/routers/projects.py:532` (my-work progress)
- Create: `backend/tests/test_dec07_readiness_semantics.py`

**Interfaces:**
- Consumes: `TemplateSchema.status_lookup()` from Task 2.
- Produces: `_compute_readiness(db, project, occurrence, schema, *, lock=False) -> dict` — **`schema` is a new required positional parameter**; every caller must pass it.

- [ ] **Step 1: Write the failing test**

```python
"""DEC07: readiness resolves a status through the bound template's
declared semantics instead of matching the literal "Complete"."""

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import enable_mfa, register_and_login

V3 = {
    "vocabulary_version": 3,
    "tracks": ["Increment"],
    "classes": ["Team"],
    "roles": ["developer", "approver"],
    "statuses": [
        {"id": "Not met", "initial": True},
        {"id": "Met", "satisfies": True},
        {"id": "Waived", "satisfies": True, "requires_exception": True},
    ],
    "decision_outcomes": [
        {"id": "Increment accepted", "kind": "approving"},
        {"id": "Not accepted", "kind": "recording"},
    ],
    "gates": [
        {
            "gate_id": "dod",
            "name": "Definition of Done",
            "sequence": 1,
            "class_ids": ["Team"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "dod.checks",
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                    "evidence_kind": "link",
                    "permitted_role_ids": ["developer"],
                    "blocker_level": "hard",
                }
            ],
        }
    ],
}


@pytest.fixture()
def v3_project(client):
    register_and_login(client, "admin@v3.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    pub = client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    assert pub.status_code == 200, pub.text
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    )
    assert project.status_code == 201, project.text
    return tenant_id, project.json()


def _preview(client, tenant_id, created, outcome=None):
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{created['project']['id']}"
        f"/occurrences/{created['occurrences'][0]['id']}/preview",
        json={"outcome": outcome} if outcome else {},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_a_declared_satisfying_status_clears_a_hard_blocker(client, v3_project):
    """G1: the whole point. "Met" is this framework's completion word and
    the engine must honour it."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    assert _preview(client, tenant_id, created)["hard_blockers"] == [item["id"]]

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met", "reference": "https://ci/1"},
    )
    assert resp.status_code == 201, resp.text
    assert _preview(client, tenant_id, created)["hard_blockers"] == []


def test_the_literal_complete_is_not_special_for_a_v3_template(client, v3_project):
    """Owner ruling: Complete is a state concept, not a literal. A v3
    template that never declares it must reject it (Task 4 enforces the
    rejection; here we only require that it does not SATISFY)."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "x"},
    )
    if resp.status_code == 201:
        assert _preview(client, tenant_id, created)["hard_blockers"] == [item["id"]]
    else:
        assert resp.status_code == 422


def test_requires_exception_status_does_not_satisfy_without_a_valid_exception(client, v3_project):
    """Without this, declaring an extra satisfying status is a route around
    a hard blocker -- the exact failure mode this work closes."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Waived", "reference": "waiver-note"},
    )
    assert resp.status_code == 201, resp.text
    assert _preview(client, tenant_id, created)["hard_blockers"] == [item["id"]], (
        "a requires_exception status must not satisfy readiness on its own"
    )


def test_requires_exception_status_satisfies_with_a_valid_exception(client, v3_project):
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    admin_id = client.get("/auth/me").json()["id"]
    now = datetime.now(timezone.utc)

    client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Waived", "reference": "waiver-note"},
    )
    exc = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/exceptions",
        json={
            "reason": "accepted for this increment",
            "owner_user_id": admin_id,
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert exc.status_code == 201, exc.text
    assert _preview(client, tenant_id, created)["hard_blockers"] == []


def test_an_expired_exception_does_not_satisfy_on_the_locked_commit_path(client, v3_project):
    """REVIEW FOCUS 5. An exception valid at preview time but expired by
    commit time must not approve. The locked readiness path re-checks
    validity rather than trusting the earlier read."""
    from app.db import SessionLocal
    from app.models import ExceptionRecord

    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    admin_id = client.get("/auth/me").json()["id"]
    now = datetime.now(timezone.utc)

    client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Waived", "reference": "waiver-note"},
    )
    client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/exceptions",
        json={
            "reason": "accepted for this increment",
            "owner_user_id": admin_id,
            "starts_at": (now - timedelta(hours=2)).isoformat(),
            "expires_at": (now + timedelta(days=1)).isoformat(),
        },
    )
    body = _preview(client, tenant_id, created)
    assert body["hard_blockers"] == [], "precondition: the valid exception should satisfy at preview"
    digest = body["manifest_digest"]

    # Expire it behind the caller's back, exactly as elapsed time would.
    with SessionLocal() as db:
        record = db.query(ExceptionRecord).filter(ExceptionRecord.evidence_item_id == item["id"]).one()
        record.expires_at = now - timedelta(minutes=1)
        db.commit()

    refused = client.post(
        f"/orgs/{tenant_id}/projects/{created['project']['id']}"
        f"/occurrences/{created['occurrences'][0]['id']}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": digest},
        headers={"Idempotency-Key": "expired-exception-1"},
    )
    assert refused.status_code in (409, 422), (
        "an expired exception must not approve -- either the manifest is stale (409) or the "
        f"blocker is unresolved (422), got {refused.status_code}: {refused.text[:200]}"
    )


def test_an_undeclared_stored_status_fails_closed(client, v3_project):
    """REVIEW FOCUS 3. Reachable for legacy rows. Readiness must treat an
    unknown status as not satisfying and must not raise."""
    from app.db import SessionLocal
    from app.models import EvidenceItem

    tenant_id, created = v3_project
    item_id = created["evidence_items"][0]["id"]

    with SessionLocal() as db:
        row = db.query(EvidenceItem).filter(EvidenceItem.id == item_id).one()
        row.status = "Legacy word"
        db.commit()

    body = _preview(client, tenant_id, created)
    assert body["hard_blockers"] == [item_id]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_readiness_semantics.py -q`
Expected: FAIL — `test_a_declared_satisfying_status_clears_a_hard_blocker` fails because `"Met"` leaves the blocker in place.

- [ ] **Step 3: Write the implementation**

In `backend/app/routers/decisions.py`, change the signature:

```python
def _compute_readiness(
    db: Session,
    project: Project,
    occurrence: GateOccurrence,
    schema: TemplateSchema,
    *,
    lock: bool = False,
) -> dict:
```

Replace the literal at `:125`. Build the lookup once before the loop:

```python
    status_lookup = schema.status_lookup()

    hard_blockers, conditional_blockers, advisory_unsatisfied = [], [], []
    blocker_explanations = []
    for item in items:
        definition = status_lookup.get(item.status)
        # Fail closed on a status the bound template does not declare --
        # reachable for rows written before this template version, and the
        # same unknown-fact rule the condition evaluator already uses.
        satisfied = definition is not None and definition.satisfies
        if satisfied and definition.requires_exception:
            # REQ-020: a satisfying-but-waived status counts only when a
            # valid exception actually covers it. Otherwise declaring an
            # extra satisfying status would bypass a hard blocker.
            satisfied = _has_valid_exception(db, item, lock=lock)
        if satisfied:
            continue
```

Add the helper next to `_exception_is_currently_valid`:

```python
def _has_valid_exception(db: Session, item: EvidenceItem, *, lock: bool = False) -> bool:
    """REVIEW FOCUS 5: re-checked on the locked path too, so an exception
    that expired between preview and commit cannot silently approve."""
    query = db.query(ExceptionRecord).filter(ExceptionRecord.evidence_item_id == item.id).order_by(ExceptionRecord.id)
    if lock:
        query = query.with_for_update()
    return any(_exception_is_currently_valid(db, exc, lock=lock) for exc in query.all())
```

Update the blocker explanation text in the same loop so it names the template's own word rather than "Complete":

```python
                    f"Gate {item.gate_id}: a {item.blocker_level} '{item.evidence_kind}' item "
                    f"(currently '{item.status}') is not in a status this framework treats as satisfied."
```

Update the three call sites:

- `:493` → `_compute_readiness(db, project, occurrence, schema)` (schema already loaded at `:492`)
- `:604` → `_compute_readiness(db, project, occurrence, schema, lock=True)` (already loaded at `:600`)
- `:1096` → load it first, since this one does not:

```python
    schema = _load_bound_schema(db, tenant_id, project.template_version_id)
    readiness = _compute_readiness(db, project, occurrence, schema)
```

Add `TemplateTemplateSchema` to the imports if absent — the correct name is `TemplateSchema`, already imported in `projects.py`; in `decisions.py` add it to the `app.rule_engine` import line.

In `backend/app/routers/projects.py`, the my-work loop at `:532` spans **multiple projects**, each possibly bound to a different template version, so build a per-project lookup rather than using one schema:

```python
    # my_work spans projects, so resolve each item's status against ITS OWN
    # bound template version. One schema would silently apply one
    # framework's vocabulary to another's items.
    status_lookup_by_project: dict[str, dict] = {}

    def _satisfies(item) -> bool:
        if item.project_id not in status_lookup_by_project:
            project_row = db.query(Project).filter(Project.id == item.project_id).one()
            schema = _load_bound_schema(db, tenant_id, project_row.template_version_id)
            status_lookup_by_project[item.project_id] = schema.status_lookup()
        definition = status_lookup_by_project[item.project_id].get(item.status)
        return definition is not None and definition.satisfies
```

then replace `if item.status == "Complete":` with `if _satisfies(item):` and the action text:

```python
        if _satisfies(item):
            direct_action = f"No action needed -- already '{item.status}'."
        else:
            direct_action = f"POST /orgs/{tenant_id}/evidence/{item.id}/revisions with a satisfying status and a reference"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_readiness_semantics.py -q`
Expected: PASS

- [ ] **Step 5: Verify nothing regressed**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_vocabulary_backcompat.py tests/test_decisions.py tests/test_projects.py tests/test_dec07_q11_agile_fixture.py -q
```
Expected: back-compat and `test_decisions.py`/`test_projects.py` PASS. **`test_dec07_q11_agile_fixture.py` will now have failures in its `test_gap_*` tests** — that is correct and intended; those are characterization tests pinned to the old behaviour, and Task 8 rewrites them. Note which fail; do not "fix" them here.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/routers/decisions.py backend/app/routers/projects.py backend/tests/test_dec07_readiness_semantics.py
git commit -m "feat: readiness resolves status through the template's semantics

Removes the literal \"Complete\" from both readiness paths. A
requires_exception status satisfies only via a valid ExceptionRecord, so
an extra satisfying status cannot become a route around a hard blocker."
```

---

### Task 4: REQ-018 on semantics, reject undeclared statuses, initial status from the template

**Files:**
- Modify: `backend/app/routers/projects.py:649` (REQ-018), `:204` and `:218` (seeding literal), and `create_evidence_revision` for validation
- Create: `backend/tests/test_dec07_revision_validation.py`

**Interfaces:**
- Consumes: `TemplateSchema.status_lookup()`, `TemplateSchema.initial_status()` from Task 2.
- Produces: no new public names.

- [ ] **Step 1: Write the failing test**

```python
"""DEC07: REQ-018 keyed on semantics, undeclared statuses rejected, and
the initial status taken from the template rather than a literal."""

import pytest

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3


@pytest.fixture()
def v3_project(client):
    register_and_login(client, "admin@v3rev.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Rev Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    )
    assert project.status_code == 201, project.text
    return tenant_id, project.json()


def test_seeded_item_starts_in_the_templates_declared_initial_status(client, v3_project):
    """G7: the platform must stop writing "Not started" into a framework
    that never declares it."""
    _, created = v3_project
    assert {i["status"] for i in created["evidence_items"]} == {"Not met"}


def test_req018_catches_a_satisfying_status_with_no_reference(client, v3_project):
    """G3: the control keys on `satisfies`, so "Met" is caught exactly as
    "Complete" is for a legacy template."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    assert item["required"] is True

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met"},
    )
    assert resp.status_code == 422
    assert "REQ-018" in resp.text


def test_a_non_satisfying_status_needs_no_reference(client, v3_project):
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Not met"},
    )
    assert resp.status_code == 201, resp.text


def test_an_undeclared_status_is_rejected(client, v3_project):
    """G4: `statuses` must constrain something."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Bananas", "reference": "x"},
    )
    assert resp.status_code == 422
    assert "Bananas" in resp.text


@pytest.mark.parametrize("near_miss", ["met", " Met", "MET", "Met "])
def test_near_miss_status_ids_are_rejected_not_silently_stored(client, v3_project, near_miss):
    """REVIEW FOCUS 1. Exact match only. A near-miss stored as a
    non-satisfying status would look accepted and never satisfy, which is
    the confusing failure this whole change exists to remove."""
    tenant_id, created = v3_project
    item = created["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": near_miss, "reference": "x"},
    )
    assert resp.status_code == 422, f"{near_miss!r} should be rejected, not stored"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_revision_validation.py -q`
Expected: FAIL — items seed as `"Not started"`, `"Met"` without a reference is accepted, `"Bananas"` is accepted.

- [ ] **Step 3: Write the implementation**

In `backend/app/routers/projects.py`, seeding. `_seed_evidence_for_occurrence` already receives `schema`, so replace both literals:

```python
            status=schema.initial_status(),
```

at `:204` and `:218`.

In `create_evidence_revision`, load the bound schema and validate before the REQ-018 check:

```python
    project_row = db.query(Project).filter(Project.id == item.project_id).one()
    schema = _load_bound_schema(db, tenant_id, project_row.template_version_id)
    status_lookup = schema.status_lookup()

    definition = status_lookup.get(payload.status)
    if definition is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"status '{payload.status}' is not declared by this project's template version "
            f"(declared: {sorted(status_lookup)})",
        )

    # REQ-018, keyed on what the status MEANS rather than on the literal
    # "Complete". Owner ruling 2026-10-03: Complete is a state concept.
    if definition.satisfies and item.required and not payload.reference:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Cannot mark a required item Complete without a reference (REQ-018)",
        )
```

and delete the old `if payload.status == "Complete" and item.required and not payload.reference:` block at `:649`.

Keep the REQ-018 message text byte-identical — `tests/test_projects.py` asserts on it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_revision_validation.py -q`
Expected: PASS

- [ ] **Step 5: Verify nothing regressed**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_vocabulary_backcompat.py tests/test_projects.py tests/test_decisions.py tests/test_wp13_webapp_new_pages.py tests/test_req035_decision_recovery.py -q
```
Expected: PASS. A failure in `test_wp13_webapp_new_pages.py` most likely means a webapp form posts a status the template does not declare — fix the caller, which is Task 7's area; if it blocks, note it and continue to Task 7 before re-running.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/routers/projects.py backend/tests/test_dec07_revision_validation.py
git commit -m "feat: REQ-018 on semantics, reject undeclared statuses, template initial status

Closes sub-findings 3, 4 and 7 of the vocabulary-indirection row."
```

---

### Task 5: Decision outcomes resolve by declared kind

**Files:**
- Modify: `backend/app/routers/decisions.py:257` (`_outcome_eligibility`) and `:289` (`_permitted_outcomes`)
- Create: `backend/tests/test_dec07_outcome_semantics.py`

**Interfaces:**
- Consumes: `TemplateSchema.outcome_lookup()` from Task 2.
- Produces: no signature changes — both functions already take `schema`.

- [ ] **Step 1: Write the failing test**

```python
"""DEC07: a template's declared decision outcomes become recordable,
resolved by declared kind rather than by matching English words."""

import pytest

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3


@pytest.fixture()
def ready_v3(client):
    register_and_login(client, "admin@v3out.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Out Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()
    item = project["evidence_items"][0]
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met", "reference": "https://ci/1"},
    )
    assert resp.status_code == 201, resp.text
    return tenant_id, project


def _preview(client, tenant_id, project, outcome=None):
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}"
        f"/occurrences/{project['occurrences'][0]['id']}/preview",
        json={"outcome": outcome} if outcome else {},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_declared_outcomes_are_permitted_once_blockers_clear(client, ready_v3):
    """G2: `permitted_outcomes` was [] for any framework not using the
    Blueprint's five words."""
    tenant_id, project = ready_v3
    body = _preview(client, tenant_id, project)
    assert body["hard_blockers"] == []
    assert set(body["permitted_outcomes"]) == {"Increment accepted", "Not accepted"}


def test_an_approving_outcome_can_actually_be_recorded(client, ready_v3):
    tenant_id, project = ready_v3
    body = _preview(client, tenant_id, project, outcome="Increment accepted")
    assert body["outcome_allowed"] is True, body["outcome_denial_reason"]

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}"
        f"/occurrences/{project['occurrences'][0]['id']}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": body["manifest_digest"]},
        headers={"Idempotency-Key": "v3-accept-1"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["outcome"] == "Increment accepted"


def test_a_recording_outcome_needs_no_cleared_blockers(client):
    """`recording` is the Hold/Redirect/Terminate behaviour: recorded, not
    an approval, so it must work with blockers outstanding."""
    register_and_login(client, "admin@v3rec.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "V3 Rec Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()

    body = _preview(client, tenant_id, project)
    assert body["hard_blockers"], "this test needs an outstanding blocker to be meaningful"
    assert "Not accepted" in body["permitted_outcomes"]

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}"
        f"/occurrences/{project['occurrences'][0]['id']}/decisions",
        json={"outcome": "Not accepted", "manifest_digest": body["manifest_digest"]},
        headers={"Idempotency-Key": "v3-reject-1"},
    )
    assert resp.status_code == 201, resp.text


def test_an_outcome_the_template_never_declared_is_still_refused(client, ready_v3):
    tenant_id, project = ready_v3
    body = _preview(client, tenant_id, project)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}"
        f"/occurrences/{project['occurrences'][0]['id']}/decisions",
        json={"outcome": "Approve", "manifest_digest": body["manifest_digest"]},
        headers={"Idempotency-Key": "v3-bogus-1"},
    )
    assert resp.status_code == 422
    assert "not a decision outcome declared by this template version" in resp.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_outcome_semantics.py -q`
Expected: FAIL — `permitted_outcomes` comes back `[]` and recording 422s with "not handled by this prototype's decision logic".

- [ ] **Step 3: Write the implementation**

Replace the body of `_outcome_eligibility` in `backend/app/routers/decisions.py`:

```python
def _outcome_eligibility(
    schema: TemplateSchema, outcome: str, readiness: dict, conditions: ConditionsIn | None
) -> tuple[bool, str | None]:
    definition = schema.outcome_lookup().get(outcome)
    if definition is None:
        declared = [e if isinstance(e, str) else e.id for e in schema.decision_outcomes]
        if outcome in declared:
            # Declared but with no resolvable kind -- only reachable for a
            # v1/v2 template naming an outcome this prototype never
            # handled. Same honest refusal as before, deliberately kept.
            return False, (
                f"outcome '{outcome}' is declared by the template but not handled by this "
                f"prototype's decision logic"
            )
        return False, f"'{outcome}' is not a decision outcome declared by this template version"

    if definition.kind == "recording":
        # Blueprint Sec.2.2: recorded outcomes, not approvals -- no blocker
        # requirement.
        return True, None

    if readiness["hard_blockers"]:
        return False, "unresolved hard blocker(s) deny any approval outcome"

    if definition.kind == "approving":
        if readiness["conditional_blockers"]:
            return False, "unresolved conditional blocker(s) -- use 'Approve with conditions' or resolve them first"
        return True, None

    # conditional_approving
    if conditions is None:
        return False, "missing deadline or condition owner"
    if not conditions.conditions or not conditions.owner_user_id:
        return False, "missing deadline or condition owner"
    if _as_utc(conditions.deadline) <= _now():
        return False, "missing deadline or condition owner"
    return True, None
```

and `_permitted_outcomes`:

```python
def _permitted_outcomes(schema: TemplateSchema, readiness: dict) -> list[str]:
    """REQ-037's confirmation-summary list. Deliberately more lenient than
    _outcome_eligibility for conditional_approving: that outcome is
    structurally reachable whenever no hard blocker exists, even before the
    caller has supplied conditions -- the summary's job is to say which
    PATHS are open, not to pre-validate a payload nobody has written yet."""
    permitted = []
    for definition in schema.outcome_lookup().values():
        if definition.kind == "recording":
            permitted.append(definition.id)
        elif readiness["hard_blockers"]:
            continue
        elif definition.kind == "approving" and not readiness["conditional_blockers"]:
            permitted.append(definition.id)
        elif definition.kind == "conditional_approving":
            permitted.append(definition.id)
    return permitted
```

The denial message for an undeclared outcome changes wording, so grep for the old text and update any test that asserts it:

```bash
cd backend && grep -rn "is not a decision outcome declared" tests/ app/
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_outcome_semantics.py -q`
Expected: PASS

- [ ] **Step 5: Verify nothing regressed**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_vocabulary_backcompat.py tests/test_decisions.py tests/test_req035_decision_recovery.py tests/test_wp13_webapp_new_pages.py -q
```
Expected: PASS. Back-compat proves the Blueprint's five words still behave identically.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/routers/decisions.py backend/tests/test_dec07_outcome_semantics.py
git commit -m "feat: decision outcomes resolve by declared kind

Closes sub-finding 5. The Blueprint's five English words are now one
mapping for legacy templates rather than the engine's only vocabulary."
```

---

### Task 6: Evaluate `conditions` against the occurrence's evidence state

**Files:**
- Modify: `backend/app/routers/decisions.py` (`_compute_readiness`, add fact building)
- Create: `backend/tests/test_dec07_conditions_evaluation.py`

**Interfaces:**
- Consumes: `evaluate_condition` from `app.rule_engine`; `_compute_readiness` from Task 3.
- Produces: `_evidence_facts(items, status_lookup) -> dict[str, str]` — keys `item:<rule_id>`, values `"satisfied" | "unsatisfied"`.

- [ ] **Step 1: Write the failing test**

```python
"""DEC07 G5: a rule's `conditions` tree is evaluated for readiness
against facts built from the occurrence's own evidence items, making the
Q10 operators load-bearing. Narrow scope: no project-state facts."""

import copy

import pytest

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3

# A gate whose summary item requires at least 2 of the 3 checks satisfied.
V3_COUNT = copy.deepcopy(V3)
V3_COUNT["gates"][0]["rules"] = [
    {
        "version": 1,
        "rule_id": "dod.a",
        "class_ids": ["Team"],
        "occurrence_type": "routine",
        "evidence_kind": "note",
        "permitted_role_ids": ["developer"],
        "blocker_level": "advisory",
    },
    {
        "version": 1,
        "rule_id": "dod.b",
        "class_ids": ["Team"],
        "occurrence_type": "routine",
        "evidence_kind": "note",
        "permitted_role_ids": ["developer"],
        "blocker_level": "advisory",
    },
    {
        "version": 1,
        "rule_id": "dod.summary",
        "class_ids": ["Team"],
        "occurrence_type": "routine",
        "evidence_kind": "note",
        "permitted_role_ids": ["approver"],
        "blocker_level": "hard",
        "conditions": {
            "op": "count",
            "compare": "gte",
            "value": 2,
            "conditions": [
                {"op": "eq", "fact": "item:dod.a", "value": "satisfied"},
                {"op": "eq", "fact": "item:dod.b", "value": "satisfied"},
                {"op": "eq", "fact": "item:dod.missing", "value": "satisfied"},
            ],
        },
    },
]


@pytest.fixture()
def count_project(client):
    register_and_login(client, "admin@cond.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Cond Co"}).json()["id"]
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "Cond", "schema_json": V3_COUNT}
    ).json()
    pub = client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    assert pub.status_code == 200, pub.text
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    )
    assert project.status_code == 201, project.text
    return tenant_id, project.json()


def _items(created):
    return {i["rule_id"]: i for i in created["evidence_items"]}


def _preview(client, tenant_id, created):
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{created['project']['id']}"
        f"/occurrences/{created['occurrences'][0]['id']}/preview",
        json={},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _meet(client, tenant_id, item):
    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
        json={"base_revision": 1, "status": "Met", "reference": "note-1"},
    )
    assert resp.status_code == 201, resp.text


def test_conditions_withhold_satisfaction_until_the_count_is_met(client, count_project):
    """G5 and spec 4.4: a satisfying status is necessary but not
    sufficient -- the conditions tree must also hold."""
    tenant_id, created = count_project
    items = _items(created)

    _meet(client, tenant_id, items["dod.summary"])
    assert items["dod.summary"]["id"] in _preview(client, tenant_id, created)["hard_blockers"], (
        "status alone must not satisfy an item whose conditions are false"
    )

    _meet(client, tenant_id, items["dod.a"])
    assert items["dod.summary"]["id"] in _preview(client, tenant_id, created)["hard_blockers"], (
        "one of three satisfied is below the count of 2"
    )

    _meet(client, tenant_id, items["dod.b"])
    assert items["dod.summary"]["id"] not in _preview(client, tenant_id, created)["hard_blockers"], (
        "two of three satisfied meets count gte 2, so the item is now satisfied"
    )


def test_conditions_can_only_withhold_never_grant(client, count_project):
    """Spec 4.4: with conditions true but the status not satisfying, the
    item stays unsatisfied. The human attestation remains the auditable
    act."""
    tenant_id, created = count_project
    items = _items(created)
    _meet(client, tenant_id, items["dod.a"])
    _meet(client, tenant_id, items["dod.b"])

    assert items["dod.summary"]["id"] in _preview(client, tenant_id, created)["hard_blockers"]


def test_a_fact_for_an_unseeded_rule_fails_closed(client, count_project):
    """REVIEW FOCUS 4. `item:dod.missing` names no seeded rule, so the
    fact is unknown. It must evaluate false without raising -- which the
    count test above already relies on, since 2 of 3 is only reachable if
    the third is false rather than an error."""
    tenant_id, created = count_project
    body = _preview(client, tenant_id, created)
    assert isinstance(body["hard_blockers"], list)


def test_conditions_are_not_evaluated_for_a_v2_template(client):
    """G6 boundary: the same shaped rule at vocabulary 2 must behave as it
    does today -- conditions ignored, status alone decides."""
    v2 = copy.deepcopy(V3_COUNT)
    v2["vocabulary_version"] = 2
    v2["statuses"] = ["Not started", "In progress", "Complete"]
    v2["decision_outcomes"] = ["Approve", "Hold"]

    register_and_login(client, "admin@cond2.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Cond2 Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "Cond2", "schema_json": v2}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()
    items = _items(project)

    resp = client.post(
        f"/orgs/{tenant_id}/evidence/{items['dod.summary']['id']}/revisions",
        json={"base_revision": 1, "status": "Complete", "reference": "note-1"},
    )
    assert resp.status_code == 201, resp.text
    assert items["dod.summary"]["id"] not in _preview(client, tenant_id, project)["hard_blockers"], (
        "conditions must stay unevaluated at vocabulary 2"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_conditions_evaluation.py -q`
Expected: FAIL — `test_conditions_withhold_satisfaction_until_the_count_is_met` fails at its first assertion, because status alone currently satisfies.

- [ ] **Step 3: Write the implementation**

In `backend/app/routers/decisions.py`, add the fact builder above `_compute_readiness`:

```python
# DEC07 narrow-scope condition facts. The namespace is CLOSED: only
# `item:<rule_id>` exists, scoped to this occurrence. Cross-occurrence and
# project-state facts are deliberately absent -- a sprint-2 check must not
# depend on sprint-1's answers (REQ-016), and a general project-state fact
# pipeline is its own work package.
_ITEM_FACT_PREFIX = "item:"


def _evidence_facts(items: list[EvidenceItem], status_lookup: dict) -> dict[str, str]:
    """Facts are derived from STORED statuses only -- never from other
    items' freshly-derived condition results. That is what makes this a
    single pass with no fixpoint, no ordering dependence and no cycle: an
    item's conditions can read whether a sibling's status satisfies, but
    not whether that sibling's own conditions passed."""
    facts: dict[str, str] = {}
    for item in items:
        definition = status_lookup.get(item.status)
        satisfied = definition is not None and definition.satisfies
        facts[f"{_ITEM_FACT_PREFIX}{item.rule_id}"] = "satisfied" if satisfied else "unsatisfied"
    return facts
```

Inside `_compute_readiness`, after `status_lookup` is built and before the loop:

```python
    # Vocabulary 3 turns condition evaluation on. At 1/2 it stays off, so a
    # published template keeps evaluating identically (G6).
    conditions_enabled = schema.vocabulary_version >= 3
    facts = _evidence_facts(items, status_lookup) if conditions_enabled else {}
    rules_by_id = {rule.rule_id: rule for gate in schema.gates for rule in gate.rules}
```

and extend the satisfaction test in the loop, immediately after the exception check:

```python
        if satisfied and conditions_enabled:
            rule = rules_by_id.get(item.rule_id)
            if rule is not None and rule.conditions is not None:
                # Conditions may only WITHHOLD satisfaction, never grant it
                # (spec 4.4): we are already inside `if satisfied`.
                satisfied = evaluate_condition(rule.conditions, facts)
```

Add `evaluate_condition` to the `app.rule_engine` import in `decisions.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_conditions_evaluation.py -q`
Expected: PASS

- [ ] **Step 5: Verify nothing regressed**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_vocabulary_backcompat.py tests/test_dec07_readiness_semantics.py tests/test_dec07_rule_vocabulary.py tests/test_decisions.py -q
```
Expected: PASS

- [ ] **Step 6: Lint and commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/routers/decisions.py backend/tests/test_dec07_conditions_evaluation.py
git commit -m "feat: evaluate rule conditions against the occurrence's evidence state

Closes sub-finding 6's conditions half. Facts are a closed item: namespace
scoped to one occurrence, derived from stored statuses only, so there is no
fixpoint and no cycle. Conditions can withhold satisfaction, never grant it."
```

---

### Task 7: Render structured statuses in the UI without breaking the editor

Two concrete breakages: `template_editor.html:45,58` does `schema_json.statuses|join(', ')`, which renders dicts as Python reprs, and `evidence_form.html:25` iterates statuses as bare strings.

**Files:**
- Modify: `backend/app/templates/evidence_form.html:25`, `backend/app/templates/template_editor.html:44-45,58`
- Modify: `backend/app/webapp/router.py:443,527,574` (pass ids, not raw entries)
- Modify: `backend/app/routers/templates.py:65-68` (blank-draft starter schema)
- Create: `backend/tests/test_dec07_webapp_statuses.py`

**Interfaces:**
- Consumes: `TemplateSchema.status_lookup()`.
- Produces: webapp templates receive `statuses` as `list[str]` of ids.

- [ ] **Step 1: Write the failing test**

```python
"""DEC07: the authoring and evidence UIs must render a structured status
list as ids, not as Python dict reprs."""

from tests.conftest import enable_mfa, register_and_login
from tests.test_dec07_readiness_semantics import V3


def _setup(client):
    register_and_login(client, "admin@ui.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "UI Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V3", "schema_json": V3}).json()
    client.post(f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish")
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Squad", "template_version_id": created["id"], "class_id": "Team", "members": []},
    ).json()
    return tenant_id, created, project


def test_evidence_form_offers_declared_status_ids(client):
    tenant_id, _, project = _setup(client)
    item_id = project["evidence_items"][0]["id"]
    page = client.get(f"/ui/orgs/{tenant_id}/evidence/{item_id}")
    assert page.status_code == 200, page.text
    body = page.text

    for status_id in ("Not met", "Met", "Waived"):
        assert f'value="{status_id}"' in body, f"{status_id} missing from the status control"
    assert "StatusDefinition" not in body
    assert "{'id'" not in body and '{"id"' not in body, "a dict repr leaked into the page"


def test_template_editor_renders_status_ids_not_dict_reprs(client):
    tenant_id, created, _ = _setup(client)
    page = client.get(f"/ui/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}")
    assert page.status_code == 200, page.text
    assert "{'id'" not in page.text and '{"id"' not in page.text
    assert "Met" in page.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_webapp_statuses.py -q`
Expected: FAIL — dict reprs appear in the rendered pages. If the editor route 500s on the Jinja `join`, that is the same defect surfacing harder.

- [ ] **Step 3: Write the implementation**

In `backend/app/webapp/router.py`, at each of the three sites, pass ids:

```python
        statuses=list(schema.status_lookup()),
```

In `backend/app/templates/template_editor.html`, replace both `join` uses so a structured entry renders its id. Line 45:

```html
    <input type="text" id="statuses" name="statuses"
           value="{{ version.schema_json.statuses | map('bgp_status_id') | join(', ') }}" required>
```

and line 58:

```html
  <dt>Statuses</dt><dd>{{ version.schema_json.statuses | map('bgp_status_id') | join(', ') }}</dd>
```

Register the filter where the Jinja environment is configured (same module that builds `Jinja2Templates`):

```python
def _bgp_status_id(entry):
    """A status entry is either a bare string or an object with an id.
    Without this, Jinja's `join` renders a dict repr into the page."""
    return entry["id"] if isinstance(entry, dict) else entry


templates.env.filters["bgp_status_id"] = _bgp_status_id
```

`evidence_form.html:25` needs no change once the router passes ids, but confirm the loop body uses `s` directly:

```html
      {% for s in statuses %}
        <option value="{{ s }}" {% if draft and draft.status == s %}selected{% endif %}>{{ s }}</option>
      {% endfor %}
```

In `backend/app/routers/templates.py:65-68`, the blank-draft starter still declares `["Not started", "Complete"]` at the default vocabulary. Since `VOCABULARY_VERSION` is now 3 and v3 requires explicit semantics, make the starter valid:

```python
    "statuses": [
        {"id": "Not started", "initial": True},
        {"id": "Complete", "satisfies": True},
    ],
    "decision_outcomes": [
        {"id": "Approve", "kind": "approving"},
        {"id": "Hold", "kind": "recording"},
    ],
```

Confirm what version the starter stamps; if it stamps `VOCABULARY_VERSION`, this is required, and `tests/test_ui08_template_authoring.py` will prove it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_webapp_statuses.py -q`
Expected: PASS

- [ ] **Step 5: Verify the webapp suite is intact**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_ui08_template_authoring.py tests/test_wp13_webapp_new_pages.py tests/test_wp11_webapp_rls.py tests/test_wp14_requirement_guidance.py tests/test_templates.py tests/test_drafts.py -q
```
Expected: PASS

- [ ] **Step 6: Lint and commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/webapp/router.py backend/app/templates/ backend/app/routers/templates.py backend/tests/test_dec07_webapp_statuses.py
git commit -m "fix: render structured status entries as ids in the authoring and evidence UIs

The template editor joined the raw list, which renders dict reprs once a
status carries semantics."
```

---

### Task 8: Publish the v3 agile fixture, rewrite the characterization tests, close TST-010's gap

This is where Q12 closes. The v1 `agile.json` stays exactly as it is — immutable under REQ-011 and still the artefact the characterization tests described.

**Files:**
- Create: `fixtures/synthetic/frameworks/agile.v3.json`
- Modify: `backend/tests/test_dec07_q11_agile_fixture.py` (rewrite all seven `test_gap_*`)
- Modify: `backend/tests/test_framework_fixtures.py` (G8)
- Modify: `backend/scripts/seed_starter_frameworks.py` (skip-list already keys on `_meta.validation_fixture`; confirm the new file carries it)
- Modify: `docs/DEFECT_REGISTER.md`, `TRACKER.md`

**Interfaces:**
- Consumes: everything from Tasks 2-7.
- Produces: `fixtures/synthetic/frameworks/agile.v3.json`.

- [ ] **Step 1: Write the v3 fixture**

Copy `fixtures/synthetic/frameworks/agile.json` to `agile.v3.json` and change only the vocabulary block. Keep every `gate_id`, `rule_id` and guidance string identical, so the diff between the two files is exactly the semantics:

```json
  "_meta": {
    "name": "Cadence Agile DoR/DoD v3 (synthetic validation fixture)",
    "validation_fixture": true,
    "note": "Vocabulary-3 version of agile.json, written once the vocabulary-indirection work made declared statuses and outcomes real. agile.json itself is published and immutable (REQ-011) and is retained unchanged: it is the artefact that demonstrated the gap, and deleting it would delete the evidence.",
    "closes": "DEC07 Q12 -- full parity on the model including statuses and decisions."
  },
  "schema_version": 1,
  "vocabulary_version": 3,
  "tracks": ["Increment"],
  "classes": ["Team"],
  "roles": ["product_owner", "developer", "facilitator"],
  "statuses": [
    {"id": "Not met", "initial": true},
    {"id": "Met", "satisfies": true},
    {"id": "Waived", "satisfies": true, "requires_exception": true}
  ],
  "decision_outcomes": [
    {"id": "Increment accepted", "kind": "approving"},
    {"id": "Accepted with follow-ups", "kind": "conditional_approving"},
    {"id": "Not accepted", "kind": "recording"}
  ],
```

Note: the v1 file's `"Waived for this increment"` is shortened to `"Waived"` here. State that in `_meta` — it is 27 characters and would pass the 30-cap, but the shorter id is clearer and this is a new version, not an edit.

Add to `_meta`:

```json
    "status_id_note": "\"Waived\" replaces v1's \"Waived for this increment\" (27 chars, within the 30-character EvidenceItem.status limit) -- a deliberate choice in a NEW version, not an edit to the published one."
```

- [ ] **Step 2: Rewrite the seven characterization tests**

Each `test_gap_*` becomes its positive counterpart, run against the v3 fixture. Their docstrings already instruct this. Replace the gap block in `backend/tests/test_dec07_q11_agile_fixture.py` with:

```python
# --------------------------------------------------------------------------
# These were CHARACTERIZATION tests pinning the vocabulary-indirection
# defect. The vocabulary-indirection work landed, so each is now its
# positive counterpart against the v3 fixture -- rewritten, not restored,
# exactly as the previous docstrings instructed.
# --------------------------------------------------------------------------

FIXTURE_V3 = FIXTURE.parent / "agile.v3.json"


def _schema_v3() -> dict:
    data = json.loads(FIXTURE_V3.read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


@pytest.fixture()
def agile_v3(client) -> AgileProject:
    register_and_login(client, "admin@squadv3.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Squad V3 Co"}).json()["id"]
    imported = client.post(
        f"/orgs/{tenant_id}/templates/import",
        json={"name": "Agile DoR/DoD v3", "schema_json": _schema_v3()},
    ).json()
    pub = client.post(
        f"/orgs/{tenant_id}/templates/{imported['template_id']}/versions/{imported['id']}/publish"
    )
    assert pub.status_code == 200, pub.text
    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Platform squad", "template_version_id": imported["id"], "class_id": "Team", "members": []},
    )
    assert created.status_code == 201, created.text
    return AgileProject(client, tenant_id, created.json())


def test_declared_statuses_now_drive_readiness(agile_v3):
    """Was test_gap_declared_statuses_are_not_honoured_by_readiness."""
    for rule_id in agile_v3.hard_rules_of(DOD):
        assert agile_v3.revise(rule_id, "Met", reference="https://ci.example/run/1").status_code == 201
    assert agile_v3.preview(DOD)["hard_blockers"] == []


def test_items_start_in_the_declared_initial_status(agile_v3):
    """Was part of the same gap: the platform wrote "Not started" into a
    framework that never declared it."""
    assert {i["status"] for i in agile_v3.items.values()} == {"Not met"}


def test_an_undeclared_status_is_now_rejected(agile_v3):
    """Was test_gap_an_undeclared_status_is_accepted."""
    rule_id = agile_v3.hard_rules_of(DOD)[0]
    resp = agile_v3.revise(rule_id, "Bananas", reference="x")
    assert resp.status_code == 422
    assert "Bananas" in resp.text


def test_req018_now_catches_a_satisfying_status_without_a_reference(agile_v3):
    """Was test_gap_req018_reference_requirement_is_keyed_to_the_literal_word."""
    rule_id = agile_v3.hard_rules_of(DOD)[0]
    assert agile_v3.items[rule_id]["required"] is True
    resp = agile_v3.revise(rule_id, "Met")
    assert resp.status_code == 422
    assert "REQ-018" in resp.text


def test_declared_decision_outcomes_can_now_be_recorded(agile_v3):
    """Was test_gap_declared_decision_outcomes_cannot_be_recorded. This
    assertion closes DEC07 Q12."""
    for rule_id in agile_v3.hard_rules_of(DOD):
        agile_v3.revise(rule_id, "Met", reference="https://ci.example/run/1")
    preview = agile_v3.preview(DOD)
    assert preview["hard_blockers"] == []
    assert "Increment accepted" in preview["permitted_outcomes"]

    recorded = agile_v3.decide(DOD, "Increment accepted", preview["manifest_digest"], key="q12-closed")
    assert recorded.status_code == 201, recorded.text


def test_waived_requires_a_real_exception(agile_v3):
    """New, and the reason `requires_exception` exists: a second
    satisfying status must not become a way around a hard blocker."""
    rule_id = agile_v3.hard_rules_of(DOD)[0]
    assert agile_v3.revise(rule_id, "Waived", reference="waiver").status_code == 201
    assert agile_v3.items[rule_id]["id"] in agile_v3.preview(DOD)["hard_blockers"]


def test_the_v1_fixture_is_retained_and_still_fails_closed(agile):
    """Was test_gap_only_the_literal_word_complete_clears_a_blocker.
    agile.json is published and immutable (REQ-011); it must keep behaving
    exactly as it did, which is also G6's proof at the fixture level."""
    rule_id = agile.hard_rules_of(DOD)[0]
    assert agile.revise(rule_id, "Met", reference="https://ci.example/run/1").status_code in (201, 422)
    assert agile.items[rule_id]["id"] in agile.preview(DOD)["hard_blockers"]
```

Update the module docstring: replace the "It did not fully survive" framing and the `test_gap_*` paragraph with a note that the gap was found, recorded, fixed, and that Q12 closed here.

- [ ] **Step 3: Close TST-010's gap (G8)**

In `backend/tests/test_framework_fixtures.py`, change the count to 5 and add:

```python
def test_fixtures_differ_in_status_and_outcome_schemes_too():
    """G8, and the root cause of the whole vocabulary-indirection defect.
    REQ-010 requires templates to version "status" and "decision" schemes,
    but TST-010 only ever asked for "classes, roles and gates" -- so three
    fixtures were built that all declared "Complete" and the Blueprint's
    outcome words, and nothing exercised the difference for six work
    packages. This asserts the part the original verification omitted."""
    status_sets, outcome_sets = set(), set()
    for path in FIXTURE_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_meta", None)
        schema = validate_template_schema(data)
        status_sets.add(frozenset(schema.status_lookup()))
        outcome_sets.add(frozenset(schema.outcome_lookup()))

    assert len(status_sets) > 1, "no fixture exercises a non-default status scheme"
    assert len(outcome_sets) > 1, "no fixture exercises a non-default outcome scheme"

    satisfying_words = set()
    for path in FIXTURE_FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_meta", None)
        schema = validate_template_schema(data)
        satisfying_words |= {d.id for d in schema.status_lookup().values() if d.satisfies}
    assert satisfying_words - {"Complete"}, (
        "every fixture's completion word is still 'Complete' -- the exact blind spot that let "
        "the vocabulary-indirection defect survive"
    )
```

Also update `test_only_non_validation_fixtures_are_shipped_as_starters` so `agile.v3` joins `agile` in `validation_only`, and the starter list stays `["lightweight", "regulated", "standard"]`.

- [ ] **Step 4: Run the fixture and vocabulary tests**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_dec07_q11_agile_fixture.py tests/test_framework_fixtures.py tests/test_dec07_vocabulary_backcompat.py -q
```
Expected: PASS

- [ ] **Step 5: Chunked full sweep**

A single-process run cannot complete on this machine. Run in chunks of 5 files:

```bash
cd backend && FILES=$(ls tests/test_*.py) && N=0 && CHUNK=""
for f in $FILES; do CHUNK="$CHUNK $f"; N=$((N+1))
  if [ $N -eq 5 ]; then
    .venv/Scripts/python.exe -u -m pytest -q --tb=line -p no:cacheprovider $CHUNK
    CHUNK=""; N=0
  fi
done
[ -n "$CHUNK" ] && .venv/Scripts/python.exe -u -m pytest -q --tb=line -p no:cacheprovider $CHUNK
```

Expected: every chunk passes, 0 failures. Cross-check the total against `pytest --collect-only -q | tail -1`; a shortfall means a chunk silently skipped files.

- [ ] **Step 6: Update the register and tracker**

In `docs/DEFECT_REGISTER.md`, the `DEC07-Q11 vocabulary indirection` row: set the fix commits, move Status to `Closed`, set the closure date, and record in the test-evidence cell that the seven characterization tests were **rewritten into positive counterparts** and that back-compat for the three v1/v2 fixtures is proven by `test_dec07_vocabulary_backcompat.py`. Keep sub-finding 6's `required_fields` half **explicitly open** — this work does not fix it.

In `TRACKER.md`, add an entry recording: the six findings closed, Q12 closed with the v3 fixture as its evidence, the `required_fields` remainder still open, and the REQ-018 interpretation ruling that licensed G3. **No `tracker_cli.py gate` action.**

- [ ] **Step 7: Lint and commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format --check .
cd .. && git add fixtures/ backend/tests/ docs/DEFECT_REGISTER.md TRACKER.md backend/scripts/seed_starter_frameworks.py
git commit -m "feat: v3 agile fixture, rewritten characterization tests, TST-010 gap closed

Closes DEC07 Q12. The seven test_gap_* characterization tests became
their positive counterparts, as their own docstrings instructed. agile.json
is retained unchanged -- published and immutable under REQ-011, and it is
the artefact that demonstrated the gap.

Also closes the verification gap that allowed the defect: TST-010 asked
only for distinct classes, roles and gates, so three fixtures all
declaring \"Complete\" satisfied it. Fixture distinctness now covers status
and outcome schemes too.

required_fields stays inert and its register entry stays open."
```

---

## Notes for the executor

- **Task 1 is the only task whose tests pass before implementation.** Everywhere else, watch the test fail first; a test that passes immediately is testing nothing.
- **Task 3 Step 5 deliberately leaves `test_dec07_q11_agile_fixture.py` failing.** Those are characterization tests pinned to the defect. Task 8 rewrites them. Do not patch them earlier to get a green run.
- **If `test_dec07_vocabulary_backcompat.py` ever fails, stop.** That is G6 breaking, which is the one outcome this design must not produce. Fix the production code; never adjust those expectations.
- **The REQ-018 message string must stay byte-identical** — existing tests assert on it.
- Memory on this machine is tight; run per-file during tasks, chunked at the end.
