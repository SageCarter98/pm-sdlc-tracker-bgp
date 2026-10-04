# Role Vocabulary Indirection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A framework template declares its own roles with semantics — which may supply evidence, and which may decide a gate — and the engine honours that instead of a hardcoded platform role set.

**Architecture:** Mirrors the DEC07 status/outcome work exactly. `roles` accepts structured entries beside plain strings, normalised by `vocabulary_version` through a new `role_lookup()` beside `status_lookup()`/`outcome_lookup()`. A new `vocabulary_version: 4` gates the semantics; v1–3 resolve through a legacy capability map that reproduces today's behaviour bit-for-bit. `DECISION_AUTHORITY_ROLES` is **split**: its two tenant-layer call sites stay platform-fixed, its two project-layer sites resolve declared capability — which is the spec's narrowing invariant expressed directly in code.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, Pydantic v2, pytest, Alembic (no migration in this plan), ruff.

**Spec:** `docs/superpowers/specs/2026-10-04-role-vocabulary-indirection-design.md`

## Global Constraints

- **No migration and no table change.** `ProjectMembership.role` is already `String(30)` with no database enum (`app/models.py:273`).
- **Role ids capped at 30 characters** — `ProjectMembership.role` is `String(30)`.
- **`VOCABULARY_VERSION` stays 2.** Spec §5.5 step 1: v4 ships accepted but unused. Do not change `app/rule_engine.py:62`.
- **Published template versions are immutable (REQ-011).** `agile.json` and `agile.v3.json` are never edited; `agile.v4.json` is a new file.
- **Vocabulary 1–3 behaviour must not change at all** (spec G5). `backend/tests/test_dec07_vocabulary_backcompat.py` and Task 1's new golden file pin this and must stay green through every task.
- **A declared role NARROWS authority, never widens it** (spec §4). Decision authority = tenant role permits AND declared role decides. Tenant-layer checks stay platform-fixed.
- **Tenant administrators keep decision authority unconditionally** at the project layer, matching the attest path's existing carve-out.
- **Fail closed everywhere.** An unresolvable role definition attests nothing and decides nothing.
- **Line length 120**; `ruff check` and `ruff format` must both pass (`backend/pyproject.toml`). Note E501 is not in ruff's configured selection, so the limit is discipline-enforced — do not rely on the linter to catch it.
- **Run tests in chunks.** This machine has 3.46 GB RAM and OOM-kills a single-process full run; 5-file and 3-file chunks have also been killed. Use **two test files per pytest process**, and run `test_dec08_performance_budgets.py` **alone**.
- **Never record a gate decision.** Do not run `tracker_cli.py`. Markdown evidence documents only.
- **No `Tracker-Evidence:` commit trailers.** An agent added two unprompted on 2026-10-04; they were unauthorised.

Python interpreter: `backend/.venv/Scripts/python.exe`.

## Review Focus

Five things the spec implies that no task's happy path exercises. Each has its test assigned to the task that owns the code.

1. **A v4 template whose declared decider role is held by someone whose tenant role cannot decide** must still be refused — the §4 invariant. If the endpoint guard were ever reordered after the project-role check, this is the only test that would notice. *(Task 3)*
2. **A v1/v2/v3 template must keep deciding exactly as today**, including that `approver`/`sponsor`/`tenant_administrator` decide and `contributor`/`assurance_reviewer` do not. *(Task 1, re-verified in Task 3)*
3. **A role id over 30 characters, or duplicated, arriving as a structured entry at vocabulary 1** must be rejected — the hole DEC07's I1 fix closed for statuses, which this task reopens in a new field if the checks are gated behind v4. *(Task 2)*
4. **A rule naming a role that declares `attests: false`** must be rejected at publish, not silently refuse every member the rule names at runtime. *(Task 2)*
5. **An undeclared member role at v4, and a template-declared role at v1–3**, must both be refused 422 — the assignment boundary works in both directions, and getting only one right leaves either custom roles unassignable or platform validation bypassed. *(Task 5)*

---

### Task 1: Pin vocabulary 1-3 role behaviour before changing anything

**Files:**
- Create: `backend/tests/test_role_vocabulary_backcompat.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: a golden file every later task must keep green. No code interface.

- [ ] **Step 1: Write the golden tests**

```python
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
```

- [ ] **Step 2: Run the tests to verify they pass against today's code**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_vocabulary_backcompat.py -q`
Expected: PASS. These describe current behaviour, so a failure here means the fixtures are not what this plan assumes — stop and report rather than editing a fixture.

- [ ] **Step 3: Commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/tests/test_role_vocabulary_backcompat.py
git commit -m "test: pin vocabulary 1-3 role behaviour before role indirection"
```

---

### Task 2: RoleDefinition, role_lookup and vocabulary 4 validation

**Files:**
- Modify: `backend/app/rule_engine.py` (constants ~:278-298, models ~:322, `TemplateSchema` ~:348-422, `_cross_references_resolve` ~:424-540)
- Test: `backend/tests/test_role_semantics.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `class RoleDefinition(BaseModel)` with `id: str`, `attests: bool = True`, `decides: bool = False`
  - `TemplateSchema.roles: list[str | RoleDefinition]`
  - `TemplateSchema.role_lookup() -> dict[str, RoleDefinition]`
  - `MAX_ROLE_ID_LENGTH = 30`
  - `_LEGACY_DECIDING_ROLES: set[str]`
  - `OPERATORS_BY_VOCABULARY_VERSION` gains key `4`
  Tasks 3, 4, 5 and 6 all consume `role_lookup()`.

- [ ] **Step 1: Write the failing tests**

```python
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
    schema = validate_template_schema(
        _schema([{"id": "product_owner", "decides": True}, "developer"])
    )
    lookup = schema.role_lookup()
    assert lookup["developer"].attests is True
    assert lookup["developer"].decides is False


@pytest.mark.parametrize(
    "role,expect_decides",
    [("approver", True), ("sponsor", True), ("tenant_administrator", True), ("contributor", False)],
)
def test_legacy_roles_keep_todays_decision_authority(role, expect_decides):
    """G5: vocabulary 1-3 reproduces DECISION_AUTHORITY_ROLES exactly."""
    schema = validate_template_schema(
        _schema([role], vocabulary_version=2, permitted=(role,))
    )
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_semantics.py -q`
Expected: FAIL — `ImportError: cannot import name 'RoleDefinition'`.

- [ ] **Step 3: Add the constants and the model**

In `backend/app/rule_engine.py`, beside `MAX_OUTCOME_ID_LENGTH` (~:284):

```python
# ProjectMembership.role is String(30) (app/models.py), with the same
# consequence one step later as a status id: a longer declared role id
# validates, is offered for assignment, and then fails at project-creation
# time as a database error.
MAX_ROLE_ID_LENGTH = 30
```

Beside `_LEGACY_OUTCOME_KINDS` (~:297):

```python
# The third legacy map, same purpose as the two above: today's hardcoded
# decision_authority role names, expressed as data so a v1/v2/v3 template
# keeps deciding exactly as it always did (spec G5). Mirrors
# decisions.py's DECISION_AUTHORITY_ROLES at the time this was written.
_LEGACY_DECIDING_ROLES = {"approver", "sponsor", "tenant_administrator"}
```

After `OutcomeDefinition` (~:328):

```python
class RoleDefinition(BaseModel):
    """One framework role plus what it MAY DO, so authorization can ask the
    bound template instead of matching a platform role name.

    `attests` defaults True and `decides` defaults False: supplying evidence
    is the ordinary case for a declared role, and granting approval is the
    deliberate act. No max_length on `id` for the same reason
    StatusDefinition has none -- see its comment: the explicit loop in
    _cross_references_resolve is the single enforcement point, so REQ-012's
    one-error-per-problem aggregation survives.
    """

    id: str = Field(min_length=1)
    attests: bool = True
    decides: bool = False
```

- [ ] **Step 4: Add vocabulary 4 to the operator table**

In `OPERATORS_BY_VOCABULARY_VERSION` (~:67), add a key `4` whose value is the same set as key `3`. Role semantics add no operators; without this key, every v4 template is refused as "not a vocabulary this build knows".

- [ ] **Step 5: Widen the field and add the lookup**

Change `TemplateSchema.roles` (~:363) from `list[str] = Field(min_length=1)` to:

```python
    roles: list[str | RoleDefinition] = Field(min_length=1)
```

Add after `outcome_lookup()` (~:399):

```python
    def role_lookup(self) -> dict[str, RoleDefinition]:
        """Normalise mixed strings/objects into one lookup, like
        status_lookup(). A plain string resolves per vocabulary_version --
        at 1-3 through the legacy deciding-role map, which is what makes
        "old templates evaluate identically forever" true for roles too;
        at 4+ a bare string is an attesting, non-deciding role, so a
        template that wants a decider must say so explicitly (and §5.2's
        at-least-one-decider rule makes it)."""
        out: dict[str, RoleDefinition] = {}
        for entry in self.roles:
            if isinstance(entry, RoleDefinition):
                out[entry.id] = entry
                continue
            if self.vocabulary_version <= 3:
                out[entry] = RoleDefinition(id=entry, decides=(entry in _LEGACY_DECIDING_ROLES))
            else:
                out[entry] = RoleDefinition(id=entry)
        return out
```

- [ ] **Step 6: Resolve role cross-references through the lookup**

In `_cross_references_resolve`, change line ~426 so `role_set` comes from the lookup rather than the raw list (a structured entry is a `RoleDefinition`, not a string, so `set(self.roles)` would no longer contain its id):

```python
        role_lookup = self.role_lookup()
        class_set, role_set = set(self.classes), set(role_lookup)
```

- [ ] **Step 7: Add the attests cross-check**

Immediately after the existing `unknown_role_ids` block (~:452-454), inside the same `for rule in gate.rules:` loop:

```python
                non_attesting = sorted(
                    role_id
                    for role_id in rule.permitted_role_ids
                    if role_id in role_lookup and not role_lookup[role_id].attests
                )
                if non_attesting:
                    errors.append(
                        f"rule '{rule.rule_id}' names role(s) {non_attesting} that does not attest -- "
                        f"a rule cannot nominate a role the template says may not supply evidence"
                    )
```

- [ ] **Step 8: Add the role id and duplicate checks**

Beside the status/outcome blocks (~:501-522):

```python
        declared_role_ids = [entry.id if isinstance(entry, RoleDefinition) else entry for entry in self.roles]
        has_structured_role = any(isinstance(entry, RoleDefinition) for entry in self.roles)

        # Same reasoning as the status and outcome blocks above, and the same
        # correction DEC07's I1 fix applied: enforce as soon as the template
        # carries a structured role entry, at ANY vocabulary version, because
        # a structured entry cannot exist in a template published before this
        # work. Plain-string leniency stays version-gated (G5).
        if self.vocabulary_version >= 4 or has_structured_role:
            if len(declared_role_ids) != len(set(declared_role_ids)):
                errors.append("duplicate role id declared")
            for role_id in declared_role_ids:
                if len(role_id) > MAX_ROLE_ID_LENGTH:
                    errors.append(
                        f"role '{role_id}' exceeds the {MAX_ROLE_ID_LENGTH}-character limit "
                        f"imposed by ProjectMembership.role"
                    )
```

- [ ] **Step 9: Add the at-least-one-decider rule**

In the `if self.vocabulary_version >= 3:` block's v4 sibling — add a new block after it:

```python
        if self.vocabulary_version >= 4:
            if not any(definition.decides for definition in role_lookup.values()):
                errors.append("vocabulary 4 requires at least one role with decides: true")
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_semantics.py tests/test_role_vocabulary_backcompat.py -q`
Expected: PASS, both files.

- [ ] **Step 11: Verify nothing regressed**

Run, two files per process:
```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_rule_engine.py tests/test_dec07_rule_vocabulary.py -q
.venv/Scripts/python.exe -m pytest tests/test_framework_fixtures.py tests/test_templates.py -q
.venv/Scripts/python.exe -m pytest tests/test_dec07_vocabulary_backcompat.py tests/test_dec07_status_semantics.py -q
```
Expected: PASS. `test_dec07_rule_vocabulary.py` asserts the unknown-version message using `max(OPERATORS_BY_VOCABULARY_VERSION) + 1`, so adding key 4 moves it to 5 automatically — if that test fails, it was hardcoded and needs the same `max(...)` treatment.

- [ ] **Step 12: Commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/rule_engine.py backend/tests/test_role_semantics.py
git commit -m "feat: declared role semantics and vocabulary 4

Roles may declare attests/decides; vocabulary 4 accepted but not the
default (VOCABULARY_VERSION stays 2, spec Sec.5.5 step 1)."
```

---

### Task 3: Split decision authority into its tenant and project layers

**Files:**
- Modify: `backend/app/routers/decisions.py` (`DECISION_AUTHORITY_ROLES` :33, call sites :98, :506, :516, :544)
- Test: `backend/tests/test_role_decision_authority.py` (create)

**Interfaces:**
- Consumes: `TemplateSchema.role_lookup()` from Task 2.
- Produces:
  - `TENANT_DECISION_AUTHORITY_ROLES: set[str]` (replaces `DECISION_AUTHORITY_ROLES`, same value, tenant layer only)
  - `_project_role_decides(schema: TemplateSchema, project_role: str, tenant_role: str) -> bool` — plain strings, not ORM objects, so the two call sites can pass `pm.role`/`membership.role` and `reviewer_pm.role`/`reviewer_membership.role` without the helper needing to know which layer fetched them

**Read this first:** the constant is consulted at two different layers. `:98` and `:506` check tenant `Membership.role`; `:516` and `:544` check project `ProjectMembership.role`. Only the project-layer pair becomes declared-capability. Converting the tenant pair would contradict spec §3.1 and break the §4 invariant. See the spec's §5.3 table.

- [ ] **Step 1: Write the failing tests**

```python
"""Decision authority resolves through the bound template at the PROJECT
layer, while the TENANT layer stays platform-fixed -- the two halves of
spec Sec.4's narrowing invariant."""

import json

import pytest

from app.routers.decisions import TENANT_DECISION_AUTHORITY_ROLES
from tests.conftest import enable_mfa, login, register_and_login
from tests.test_projects import FIXTURES_DIR

PASSWORD = "correct horse battery staple"
ADMIN = "admin@roledec.example"
DECIDER = "decider@roledec.example"
WORKER = "worker@roledec.example"

V4 = {
    "schema_version": 1,
    "vocabulary_version": 4,
    "tracks": ["Increment"],
    "classes": ["Team"],
    "roles": [
        {"id": "product_owner", "attests": True, "decides": True},
        {"id": "developer", "attests": True},
    ],
    "statuses": [{"id": "Not met", "initial": True}, {"id": "Met", "satisfies": True}],
    "decision_outcomes": [
        {"id": "Increment accepted", "kind": "approving"},
        {"id": "Not accepted", "kind": "recording"},
    ],
    "gates": [
        {
            "gate_id": "dod",
            "name": "Definition of done",
            "sequence": 1,
            "class_ids": ["Team"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "dod.checks",
                    "evidence_kind": "document",
                    "required": True,
                    "blocker_level": "hard",
                    "permitted_role_ids": ["developer", "product_owner"],
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                }
            ],
        }
    ],
}


def _invite(client, tenant_id, email, tenant_role):
    token = client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": tenant_role}).json()["token"]
    user_id = register_and_login(client, email).json()["id"]
    assert client.post("/invitations/accept", json={"token": token}).status_code == 200
    return user_id


@pytest.fixture()
def v4_project(client):
    """decider: tenant approver + project product_owner (declared decider).
    worker:  tenant approver + project developer (declared non-decider).
    The worker's TENANT role deliberately permits deciding, so a refusal
    can only come from the declared project role -- that is the point."""
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Role Dec Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": V4}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )

    decider_id = _invite(client, tenant_id, DECIDER, "approver")
    enable_mfa(client)
    login(client, ADMIN, PASSWORD)
    worker_id = _invite(client, tenant_id, WORKER, "approver")
    enable_mfa(client)

    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Squad",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [
                {"user_id": decider_id, "role": "product_owner"},
                {"user_id": worker_id, "role": "developer"},
            ],
        },
    ).json()
    return tenant_id, project, decider_id, worker_id


def _prepare_and_preview(client, tenant_id, project):
    """The worker supplies the evidence, so separation of duties is
    satisfied when someone else decides."""
    item = project["evidence_items"][0]
    login(client, WORKER, PASSWORD)
    assert (
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Met", "reference": "https://ci/1"},
        ).status_code
        == 201
    )
    occurrence_id = project["occurrences"][0]["id"]
    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/preview", json={}
    )
    assert preview.status_code == 200, preview.text
    return occurrence_id, preview.json()


def test_a_declared_decider_may_record_a_decision(client, v4_project):
    tenant_id, project, _, _ = v4_project
    occurrence_id, preview = _prepare_and_preview(client, tenant_id, project)
    assert preview["hard_blockers"] == []

    login(client, DECIDER, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": preview["manifest_digest"]},
        headers={"Idempotency-Key": "v4-decider-1"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["outcome"] == "Increment accepted"


def test_a_declared_non_decider_is_refused_even_with_a_permitting_tenant_role(client, v4_project):
    """Review Focus 1 and spec Sec.4: the worker's tenant role is approver,
    which passes the endpoint guard, so the only thing that can refuse this
    is the bound template's declared role capability. If this test ever
    passes a 201, the project-layer check has been lost."""
    tenant_id, project, _, _ = v4_project
    occurrence_id, preview = _prepare_and_preview(client, tenant_id, project)

    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": preview["manifest_digest"]},
        headers={"Idempotency-Key": "v4-worker-1"},
    )
    assert resp.status_code == 403, resp.text
    assert "decision" in resp.text.lower() or "role" in resp.text.lower()


def test_a_declared_non_decider_cannot_record_a_compensating_review(client, v4_project):
    """Spec Sec.6's compensating-reviewer case, at the site that actually
    gates it. A compensating review is the reviewer's OWN authenticated
    action (`POST .../compensating-reviews`, body just `{"note": ...}` --
    `reviewer_user_id` is always the caller's own id, never typed by
    someone else), and that endpoint calls the same
    `_require_decision_authority` the decision endpoint does.

    So REQ-006's independence cannot be satisfied by someone the bound
    template says does not decide: the worker's tenant role is approver,
    which passes the endpoint guard, and the refusal can only come from
    the declared project role."""
    tenant_id, project, _, _ = v4_project
    occurrence_id = project["occurrences"][0]["id"]

    login(client, WORKER, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/compensating-reviews",
        json={"note": "I looked at it"},
    )

    assert resp.status_code == 403, resp.text


def test_a_declared_decider_can_record_a_compensating_review(client, v4_project):
    """The positive half, so the test above cannot pass for the wrong
    reason (e.g. the endpoint refusing everyone)."""
    tenant_id, project, _, _ = v4_project
    occurrence_id = project["occurrences"][0]["id"]

    login(client, DECIDER, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/compensating-reviews",
        json={"note": "I looked at it"},
    )

    assert resp.status_code == 201, resp.text


def test_the_tenant_layer_set_is_unchanged_and_still_platform_fixed():
    """Spec Sec.3.1: tenant roles gate MFA and endpoint access and predate
    any template binding, so this set must NOT become template-declared."""
    assert TENANT_DECISION_AUTHORITY_ROLES == {"approver", "sponsor", "tenant_administrator"}


def test_a_v1_v2_project_decides_exactly_as_before(client):
    """Review Focus 2 / G5, end to end rather than at the schema layer:
    the standard fixture is vocabulary 1 and its approver still decides."""
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Legacy Co"}).json()["id"]
    schema = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "Standard", "schema_json": schema}
    ).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    approver_id = _invite(client, tenant_id, DECIDER, "approver")
    enable_mfa(client)
    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Legacy",
            "template_version_id": created["id"],
            "class_id": "Standard-High",
            "members": [{"user_id": approver_id, "role": "approver"}],
        },
    ).json()
    item = next(e for e in project["evidence_items"] if e["gate_id"] == "S1")

    login(client, DECIDER, PASSWORD)
    assert (
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Complete", "reference": "doc-1"},
        ).status_code
        == 201
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_decision_authority.py -q`
Expected: FAIL — `ImportError: cannot import name 'TENANT_DECISION_AUTHORITY_ROLES'`.

- [ ] **Step 3: Rename the constant to name its layer**

In `backend/app/routers/decisions.py`, replace line 33:

```python
# TENANT-layer decision authority: which org-level Membership.role may
# decide at all. Platform-fixed on purpose (spec Sec.3.1) -- it gates MFA
# (models.ROLES_REQUIRING_MFA) and endpoint access via require_role, and a
# tenant exists before any template is bound, so there is nothing to
# resolve a declared role against here. The PROJECT layer is the half that
# became template-declared: see _project_role_decides below.
TENANT_DECISION_AUTHORITY_ROLES = {"approver", "sponsor", "tenant_administrator"}
```

Update the two tenant-layer call sites to the new name, leaving their logic alone:
- `:98` — `approver_membership.role in TENANT_DECISION_AUTHORITY_ROLES`
- `:506` — `reviewer_membership.role not in TENANT_DECISION_AUTHORITY_ROLES`

- [ ] **Step 4: Add the project-layer predicate**

Beside the other module-level helpers in `decisions.py`:

```python
def _project_role_decides(schema: TemplateSchema, project_role: str, tenant_role: str) -> bool:
    """PROJECT-layer decision authority, resolved through the bound
    template (spec Sec.5.3). Together with the tenant-layer check this is
    the intersection spec Sec.4 requires: the tenant role permits deciding
    AND the bound template says this project role decides.

    Tenant administrators always may, matching the attest path's existing
    carve-out in routers/projects.py -- otherwise a template could lock its
    own tenant's administrator out of its gates.

    Fails closed: a project role the bound template does not declare
    decides nothing, the same rule status_satisfies applies to an
    undeclared status."""
    if tenant_role == Role.TENANT_ADMINISTRATOR:
        return True
    definition = schema.role_lookup().get(project_role)
    return definition is not None and definition.decides
```

Add `Role` to the `app.models` import and `TemplateSchema` to the `app.rule_engine` import in that file if not already present.

- [ ] **Step 5: Convert the centralised helper**

**Read this before editing — the plan's earlier draft described `:544` as a standalone site and it is not.** `pm.role not in DECISION_AUTHORITY_ROLES` at `:544` lives inside
`_require_decision_authority(db, project_id, user, mfa_verified) -> ProjectMembership` (`:524`), which has **five callers**: `:921` (preview/decide path), `:1016`, `:1077` and `:1139` (exception endpoints), and `:1208` (compensating reviews). Converting it therefore makes exception authority and compensating-review authority template-governed as well as decisions. That is the right outcome — an exception is a decision about a blocker, and a compensating review is the reviewer's own authoritative act — but it is a wider blast radius than "the decision endpoint", so say so in your task report.

Load the schema **inside** the helper rather than threading a parameter through five callers. Everything needed is already in scope:

```python
    if pm is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this project")
    project = db.query(Project).filter(Project.id == project_id).one()
    schema = _load_bound_schema(db, project.tenant_id, project.template_version_id)
    if not _project_role_decides(schema, pm.role, membership.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role does not permit recording decisions")
```

`membership` here is the caller's tenant-level `Membership`, which the helper already resolves for its own MFA check — reuse that variable rather than re-querying. Add `Project` to the `app.models` import if absent.

At `:516` (the stored compensating review's reviewer still holding project authority at decision-commit time), the surrounding function already has the bound `schema` in scope for readiness:

```python
    if reviewer_pm is None or not _project_role_decides(schema, reviewer_pm.role, reviewer_membership.role):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The compensating reviewer no longer holds approval authority on this project"
        )
```

Leave `:98` and `:506` on `TENANT_DECISION_AUTHORITY_ROLES` — they read tenant `Membership.role`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_decision_authority.py -q`
Expected: PASS.

- [ ] **Step 7: Verify nothing regressed**

Run, two files per process:
```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_decisions.py tests/test_req035_decision_recovery.py -q
.venv/Scripts/python.exe -m pytest tests/test_dec07_outcome_semantics.py tests/test_dec07_q11_agile_fixture.py -q
.venv/Scripts/python.exe -m pytest tests/test_permitted_role_enforcement.py tests/test_role_vocabulary_backcompat.py -q
.venv/Scripts/python.exe -m pytest tests/test_dec07_readiness_semantics.py tests/test_integrity.py -q
```
Expected: PASS. `test_decisions.py` carries the REQ-006 separation-of-duties and compensating-review tests; a failure there means the tenant/project split was applied to the wrong site. The fourth line matters because `_require_decision_authority` also guards the **exception** endpoints (`:1077`, `:1139`) — exception-granting authority becomes template-governed by this change, and these files exercise it.

- [ ] **Step 8: Commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/routers/decisions.py backend/tests/test_role_decision_authority.py
git commit -m "feat: project-layer decision authority resolves through the template

Splits DECISION_AUTHORITY_ROLES: the two tenant-layer sites keep a
platform-fixed set, the two project-layer sites ask the bound template.
That split IS the spec's narrowing invariant in code."
```

---

### Task 4: The attest path resolves declared capability

**Files:**
- Modify: `backend/app/routers/projects.py` (`_require_permitted_to_attest`)
- Test: `backend/tests/test_permitted_role_enforcement.py` (extend)

**Interfaces:**
- Consumes: `role_lookup()` from Task 2.
- Produces: **a signature change** — `_require_permitted_to_attest(item, pm, membership, schema)` gains the bound schema, because resolving `attests` and scoping the fallback both need it. **Both** call sites must be updated: `create_evidence_revision` in `routers/projects.py` and `upload_attachment` in `routers/attachments.py`. Missing the second breaks attachment upload at import time, and `test_wp15_evidence_attachments.py` is what catches it.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_permitted_role_enforcement.py`:

```python
V4_ATTEST = {
    "schema_version": 1,
    "vocabulary_version": 4,
    "tracks": ["Delivery"],
    "classes": ["Team"],
    "roles": [
        {"id": "product_owner", "attests": True, "decides": True},
        {"id": "observer", "attests": False},
    ],
    "statuses": [{"id": "Not met", "initial": True}, {"id": "Met", "satisfies": True}],
    "decision_outcomes": [{"id": "Accept", "kind": "approving"}],
    "gates": [
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
                    "permitted_role_ids": ["product_owner"],
                    "class_ids": ["Team"],
                    "occurrence_type": "routine",
                }
            ],
        }
    ],
}


def test_a_v4_declared_role_may_attest_without_being_a_platform_role(client):
    """The payoff: 'product_owner' is not a platform Role, and at v4 it no
    longer has to be. This is the case the fallback used to swallow."""
    register_and_login(client, "admin@v4attest.example")
    tenant_id = client.post("/orgs", json={"name": "V4 Attest Co"}).json()["id"]
    created = client.post(
        f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": V4_ATTEST}
    ).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    member_id = _invite(client, tenant_id, "po@v4attest.example", "contributor")
    login(client, "admin@v4attest.example", PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "V4 Attest",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "product_owner"}],
        },
    ).json()
    item = project["evidence_items"][0]

    login(client, "po@v4attest.example", PASSWORD)
    resp = _submit(client, tenant_id, item["id"], status="Met")

    assert resp.status_code == 201, resp.text


def test_the_unassignable_fallback_does_not_apply_at_v4(client):
    """G6: below v4 the fallback is the only thing keeping custom-role
    frameworks usable; at v4 declared roles are assignable, so a role the
    rule does not name must be refused rather than waved through."""
    register_and_login(client, "admin@v4fb.example")
    tenant_id = client.post("/orgs", json={"name": "V4 FB Co"}).json()["id"]
    schema = dict(V4_ATTEST)
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": schema}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    # 'observer' declares attests: false and is not in permitted_role_ids.
    member_id = _invite(client, tenant_id, "obs@v4fb.example", "contributor")
    login(client, "admin@v4fb.example", PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "V4 FB",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "observer"}],
        },
    ).json()
    item = project["evidence_items"][0]

    login(client, "obs@v4fb.example", PASSWORD)
    resp = _submit(client, tenant_id, item["id"], status="Met")

    assert resp.status_code == 403, resp.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_permitted_role_enforcement.py -q`
Expected: FAIL — the v4 attest test 422s at project creation, because Task 5 has not yet taught the member role field about declared roles. **This is expected ordering**: implement Step 3 now, leave these two tests failing, and they go green in Task 5 Step 6. Record that in the task report rather than "fixing" it here.

- [ ] **Step 3: Resolve attests and scope the fallback**

In `_require_permitted_to_attest` (`backend/app/routers/projects.py`), the body becomes:

```python
    if item.owner_user_id is not None and item.owner_user_id == membership.user_id:
        return
    if membership.role == Role.TENANT_ADMINISTRATOR:
        return

    declared = item.permitted_role_ids or []
    role_lookup = schema.role_lookup()
    definition = role_lookup.get(pm.role)
    if definition is not None and definition.attests and pm.role in declared:
        return

    # Below vocabulary 4 the platform Role enum is still the only source of
    # assignable project roles, so a framework naming its own roles has
    # permitted_role_ids no member can match -- enforcing strictly there
    # would make every item in such a framework attestable only by a tenant
    # administrator or the assigned owner. At 4+ declared roles ARE
    # assignable, so the fallback is neither needed nor wanted.
    if schema.vocabulary_version < 4 and not (set(declared) & {role.value for role in Role}):
        return

    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"your project role '{pm.role}' is not permitted to submit evidence for this item "
        f"(permitted roles: {sorted(declared)})",
    )
```

This needs the bound `schema`, which the function does not currently receive. Add it as a parameter — `_require_permitted_to_attest(item, pm, membership, schema)` — and update both call sites: `create_evidence_revision` in this file and `upload_attachment` in `backend/app/routers/attachments.py`. Both already load or can load the bound schema via `_load_bound_schema(db, tenant_id, project.template_version_id)`; in `attachments.py` fetch the project with the existing `_get_owned_project_or_404` helper first.

- [ ] **Step 4: Run the attest tests that do not need Task 5**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_permitted_role_enforcement.py -q -k "not v4"`
Expected: PASS — all seven pre-existing tests, including both exemptions and the below-v4 fallback.

- [ ] **Step 5: Verify nothing regressed**

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_wp15_evidence_attachments.py tests/test_wp15_cloudmersive_scanner.py -q
.venv/Scripts/python.exe -m pytest tests/test_projects.py tests/test_dec07_revision_validation.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/routers/projects.py backend/app/routers/attachments.py backend/tests/test_permitted_role_enforcement.py
git commit -m "feat: attest path resolves declared role capability

Two v4 tests are deliberately left red until Task 5 teaches project
creation about declared member roles."
```

---

### Task 5: Project membership accepts declared roles

**Files:**
- Modify: `backend/app/routers/projects.py` (`ProjectMemberIn` :35-37, project creation ~:256-300)
- Test: `backend/tests/test_role_assignment.py` (create)

**Interfaces:**
- Consumes: `role_lookup()` from Task 2.
- Produces: `ProjectMemberIn.role` becomes `str` (was `Role`). Callers that passed a platform role string are unaffected; `member.role.value` at ~:298 becomes `member.role`.

- [ ] **Step 1: Write the failing tests**

```python
"""Review Focus 5: the assignment boundary must work in BOTH directions --
a declared role assignable at v4, and only platform roles below it."""

import json

import pytest

from tests.conftest import login, register_and_login
from tests.test_projects import FIXTURES_DIR
from tests.test_role_decision_authority import V4, _invite

PASSWORD = "correct horse battery staple"
ADMIN = "admin@roleassign.example"


def _publish(client, tenant_id, name, schema):
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": name, "schema_json": schema}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )
    return created["id"]


@pytest.fixture()
def tenant(client):
    register_and_login(client, ADMIN)
    return client.post("/orgs", json={"name": "Role Assign Co"}).json()["id"]


def test_a_v4_declared_role_is_assignable(client, tenant):
    version_id = _publish(client, tenant, "V4", V4)
    member_id = _invite(client, tenant, "dev@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "developer"}],
        },
    )

    assert resp.status_code == 201, resp.text


def test_an_undeclared_role_is_refused_at_v4(client, tenant):
    version_id = _publish(client, tenant, "V4", V4)
    member_id = _invite(client, tenant, "ghost@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Team",
            "members": [{"user_id": member_id, "role": "approver"}],
        },
    )

    assert resp.status_code == 422, resp.text
    assert "developer" in resp.text and "product_owner" in resp.text


def test_below_v4_only_platform_roles_are_accepted(client, tenant):
    """The other direction: a v1 template must not start accepting
    arbitrary strings just because the field stopped being enum-typed."""
    schema = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    version_id = _publish(client, tenant, "Standard", schema)
    member_id = _invite(client, tenant, "legacy@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Standard-High",
            "members": [{"user_id": member_id, "role": "product_owner"}],
        },
    )

    assert resp.status_code == 422, resp.text


def test_below_v4_a_platform_role_still_works(client, tenant):
    schema = json.loads((FIXTURES_DIR / "standard.json").read_text(encoding="utf-8"))
    schema.pop("_meta", None)
    version_id = _publish(client, tenant, "Standard", schema)
    member_id = _invite(client, tenant, "ok@roleassign.example", "contributor")
    login(client, ADMIN, PASSWORD)

    resp = client.post(
        f"/orgs/{tenant}/projects",
        json={
            "name": "P",
            "template_version_id": version_id,
            "class_id": "Standard-High",
            "members": [{"user_id": member_id, "role": "approver"}],
        },
    )

    assert resp.status_code == 201, resp.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_assignment.py -q`
Expected: FAIL — `test_a_v4_declared_role_is_assignable` gets 422 from the `Role` enum.

- [ ] **Step 3: Loosen the field's type**

In `backend/app/routers/projects.py`, change `ProjectMemberIn` (:35-37):

```python
class ProjectMemberIn(BaseModel):
    user_id: str
    # Not `Role`: at vocabulary 4 a member's project role is any role the
    # bound template version declares, which the handler validates against
    # that binding (REQ-010's role scheme). Below v4 the handler restricts
    # this to exactly the platform Role enum, so existing callers are
    # unaffected. Enum-typing it here would make the v4 case unreachable
    # before any template could be consulted.
    role: str
```

At ~:298, `role=member.role.value` becomes `role=member.role`.

- [ ] **Step 4: Validate against the binding**

In the project-creation handler, after the bound schema is loaded (`schema = _load_bound_schema(...)`, ~:256) and before members are added:

```python
    if schema.vocabulary_version >= 4:
        permitted_member_roles = set(schema.role_lookup())
        source = "declared by this template version"
    else:
        permitted_member_roles = {role.value for role in Role}
        source = "a platform role"
    unknown_member_roles = sorted({m.role for m in payload.members} - permitted_member_roles)
    if unknown_member_roles:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"member role(s) {unknown_member_roles} are not {source} "
            f"(permitted: {sorted(permitted_member_roles)})",
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_assignment.py -q`
Expected: PASS, all four.

- [ ] **Step 6: Confirm Task 4's deferred tests now pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_permitted_role_enforcement.py -q`
Expected: PASS, all nine — including the two v4 tests Task 4 left red.

- [ ] **Step 7: Verify nothing regressed**

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_projects.py tests/test_role_decision_authority.py -q
.venv/Scripts/python.exe -m pytest tests/test_dec05_durability_mechanism.py tests/test_export_import.py -q
.venv/Scripts/python.exe -m pytest tests/test_wp13_webapp_new_pages.py tests/test_ui09_export_import.py -q
```
Expected: PASS. Export/import matters here because `exports.py` writes `ProjectMembership` rows on import; if it type-checked against `Role`, it needs the same loosening.

- [ ] **Step 8: Commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/routers/projects.py backend/tests/test_role_assignment.py
git commit -m "feat: project members may hold any role the bound template declares"
```

---

### Task 6: The v4 agile fixture, and the invariant proved end to end

**Files:**
- Create: `fixtures/synthetic/frameworks/agile.v4.json`
- Modify: `backend/tests/test_framework_fixtures.py`, `backend/scripts/seed_starter_frameworks.py`
- Test: `backend/tests/test_role_invariant.py` (create)

**Interfaces:**
- Consumes: everything from Tasks 2-5.
- Produces: the fixture other tests may bind to.

- [ ] **Step 1: Write the v4 fixture**

Copy `fixtures/synthetic/frameworks/agile.v3.json` to `agile.v4.json` and change only the vocabulary block and `_meta`. Keep every `gate_id`, `rule_id`, guidance string, status, outcome and condition tree byte-identical, so the diff between v3 and v4 is exactly the role semantics:

```json
  "vocabulary_version": 4,
  "roles": [
    {"id": "product_owner", "attests": true, "decides": true},
    {"id": "developer", "attests": true},
    {"id": "facilitator", "attests": true}
  ],
```

`_meta` gains:

```json
    "roles_note": "Vocabulary-4 version of agile.v3.json. The role block is the only semantic change: product_owner decides, developer and facilitator attest. agile.json and agile.v3.json are published and immutable (REQ-011) and are retained unchanged -- v3 is what demonstrated that declared roles were ignored, and deleting it would delete the evidence.",
    "closes": "The 'declared role vocabulary is not honoured' register row -- REQ-010's role scheme, the last field of that requirement's own list."
```

- [ ] **Step 2: Keep it out of the starter set**

The mechanism is the `_meta.validation_fixture: true` flag, which `agile.v3.json` already carries and the copy inherits — so confirm it is present rather than adding a name to a list. Then:

1. Run `grep -rn "agile.v3" backend/ fixtures/ --include=*.py --include=*.json` and add `agile.v4` beside every hit that is an explicit name list rather than flag-driven. At the time of writing that is `backend/scripts/seed_starter_frameworks.py`; verify rather than assume.
2. In `backend/tests/test_framework_fixtures.py`, bump the fixture-count assertion from 5 to 6 and confirm `test_only_non_validation_fixtures_are_shipped_as_starters` still expects exactly `["lightweight", "regulated", "standard"]`.
3. `test_fixtures_differ_in_status_and_outcome_schemes_too` (added by DEC07's Task 8) iterates every fixture — confirm it still passes with a sixth file rather than assuming it is count-independent.

- [ ] **Step 3: Write the invariant test**

```python
"""Spec Sec.4, end to end: a declared `decides` role NARROWS authority
within the Blueprint's model and never grants authority the holder's
tenant role lacks.

This is the test that would catch the endpoint guard being reordered
after the project-role check. It is deliberately in its own file so it
is hard to delete by accident along with a fixture refactor.
"""

from tests.conftest import enable_mfa, login, register_and_login
from tests.test_role_decision_authority import V4, _invite

PASSWORD = "correct horse battery staple"
ADMIN = "admin@invariant.example"
WEAK = "weak@invariant.example"


def test_a_declared_decider_whose_tenant_role_cannot_decide_is_still_refused(client):
    register_and_login(client, ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Invariant Co"}).json()["id"]
    created = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "V4", "schema_json": V4}).json()
    assert (
        client.post(
            f"/orgs/{tenant_id}/templates/{created['template_id']}/versions/{created['id']}/publish"
        ).status_code
        == 200
    )

    # Tenant role 'contributor' -- cannot decide at the tenant layer.
    # Project role 'product_owner' -- the template says it DOES decide.
    weak_id = _invite(client, tenant_id, WEAK, "contributor")
    login(client, ADMIN, PASSWORD)
    project = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Squad",
            "template_version_id": created["id"],
            "class_id": "Team",
            "members": [{"user_id": weak_id, "role": "product_owner"}],
        },
    ).json()
    item = project["evidence_items"][0]
    occurrence_id = project["occurrences"][0]["id"]

    login(client, ADMIN, PASSWORD)
    assert (
        client.post(
            f"/orgs/{tenant_id}/evidence/{item['id']}/revisions",
            json={"base_revision": 1, "status": "Met", "reference": "https://ci/1"},
        ).status_code
        == 201
    )
    preview = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/preview", json={}
    ).json()

    login(client, WEAK, PASSWORD)
    resp = client.post(
        f"/orgs/{tenant_id}/projects/{project['project']['id']}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Increment accepted", "manifest_digest": preview["manifest_digest"]},
        headers={"Idempotency-Key": "invariant-1"},
    )

    assert resp.status_code == 403, (
        "a template-declared decider must not reach a decision when the holder's "
        f"TENANT role does not permit deciding -- got {resp.status_code}"
    )
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_invariant.py tests/test_framework_fixtures.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add fixtures/synthetic/frameworks/agile.v4.json backend/tests/test_role_invariant.py backend/tests/test_framework_fixtures.py backend/app/routers/templates.py backend/scripts/seed_starter_frameworks.py
git commit -m "feat: v4 agile fixture and the narrowing invariant proved end to end"
```

---

### Task 7: Tidy the version-wording wart, sweep, and record

**Files:**
- Modify: `backend/app/rule_engine.py` (the `>= 3` message wording)
- Modify: `docs/DEFECT_REGISTER.md`, `TRACKER.md`
- Test: `backend/tests/test_role_semantics.py` (extend)

**Interfaces:**
- Consumes: everything. Produces nothing for later tasks — this is the last task.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_role_semantics.py`:

```python
def test_a_v4_template_does_not_get_v3_phrasing():
    """Spec Sec.7's recorded wart: the `>= 3` blocks apply v3's content
    rules with v3's wording to every higher version, so a v4 template that
    omits an initial status is told about 'vocabulary 3'."""
    data = _schema([{"id": "po", "decides": True}])
    data["statuses"] = [{"id": "Met", "satisfies": True}]  # no initial
    with pytest.raises(RuleValidationError) as excinfo:
        validate_template_schema(data)
    message = str(excinfo.value)
    assert "exactly one status with initial: true" in message
    assert "vocabulary 3" not in message, message
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_semantics.py::test_a_v4_template_does_not_get_v3_phrasing -q`
Expected: FAIL — the message says "vocabulary 3 requires exactly one status with initial: true".

- [ ] **Step 3: Make the wording name the declared version**

In `_cross_references_resolve`'s `if self.vocabulary_version >= 3:` block, replace the three hardcoded "vocabulary 3" strings with the declared version, e.g.:

```python
            if sum(1 for d in status_defs if d.initial) != 1:
                errors.append(
                    f"vocabulary {self.vocabulary_version} requires exactly one status with initial: true"
                )
```

Do the same for the satisfies rule and the explicit-kind rule. Leave the version *gates* (`>= 3`, `>= 4`) alone — only the wording changes.

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_role_semantics.py tests/test_dec07_status_semantics.py -q`
Expected: PASS. `test_dec07_status_semantics.py` asserts some of these messages; update its expected strings to the same `vocabulary {n}` form where it does.

- [ ] **Step 5: Chunked full sweep**

Run the whole suite two files per pytest process, and `test_dec08_performance_budgets.py` alone:

```bash
cd backend
ls tests/test_*.py | sort > /tmp/allt.txt
for i in $(seq 1 2 $(wc -l < /tmp/allt.txt)); do \
  F=$(sed -n "${i},$((i+1))p" /tmp/allt.txt | tr '\n' ' '); \
  echo "--- $F"; .venv/Scripts/python.exe -m pytest $F -q --no-header -p no:cacheprovider 2>&1 | tail -2; \
done
.venv/Scripts/python.exe -m pytest tests/test_dec08_performance_budgets.py -q
```

Report every red with its file name and your conclusion with evidence. A perf-budget red while sharing a process is usually memory — re-run that file alone before concluding anything. Any other red is real until proven otherwise.

- [ ] **Step 6: Update the register and tracker**

In `docs/DEFECT_REGISTER.md`:
- Move the row "Declared role vocabulary is not honoured (the DEC07 gap, in `roles`)" to **Closed**, citing the fix commits, `agile.v4.json`, and the four new test files by name.
- Add a new row for the verification gap the spec identified: **WP05 is nominally delivered while REQ-010's role scheme was never implemented** — the same requirement-versus-verification mismatch TST-010 had for statuses and decisions. Record that nobody has checked whether other REQ/TST pairs share the shape. Status: Open.
- Record that **AC08/AC09 remain unverified** because Directive v1.2 is not in this repository (spec §2.1), so this work is not claimed to satisfy WP05's acceptance criteria.

In `TRACKER.md`, add an entry recording what shipped, the vocabulary-4 staging (accepted but unused, `VOCABULARY_VERSION` still 2), the sweep result, and the two items above. **No `tracker_cli.py` invocation of any kind.**

Evidence standard: no claim without a specific locatable reference. Never fabricate a commit SHA — use `git rev-parse --short HEAD`, adding it in a follow-up commit if needed.

- [ ] **Step 7: Commit**

```bash
cd backend && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .
cd .. && git add backend/app/rule_engine.py backend/tests/test_role_semantics.py backend/tests/test_dec07_status_semantics.py docs/DEFECT_REGISTER.md TRACKER.md
git commit -m "feat: version-accurate validation wording; close the role-vocabulary row

Records WP05's unimplemented REQ-010 element as its own open row, and
AC08/AC09 as unverified (Directive v1.2 absent from this repository)."
```
