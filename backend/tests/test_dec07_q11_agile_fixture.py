"""DEC07 Q11/Q12: the third framework fixture, and what it proved.

Q11 asked for a third fixture *structurally different* from the two
gate-based ones already built -- "an agile Definition-of-Ready /
Definition-of-Done framework with no gates at all", recurring per-increment
checks, unnumbered -- on the explicit reasoning that "if the rule engine and
data model survive that without a special case, the model is genuinely
general." Q12 asked for full parity on the model: tracks, items, rules,
roles, statuses, decisions.

It did not fully survive, and this file is the record of exactly where.

The tests below come in two groups, and the distinction matters:

  * `test_works_*` -- real capability. These assert behaviour that should
    keep working; if one breaks, something regressed.

  * `test_gap_*` -- CHARACTERIZATION tests. They pin the CURRENT, WRONG
    behaviour so that fixing it shows up as a deliberate, visible change to
    this file instead of a silent diff elsewhere. They are NOT a claim that
    this behaviour is correct, and NOT a spec to preserve. Each is expected
    to be rewritten when the vocabulary-indirection work lands (see
    DEFECT_REGISTER.md, "DEC07-Q11 vocabulary indirection"). If you are
    here because one failed after you generalised the status/outcome
    vocabularies: good -- that is the point. Update the assertion; do not
    restore the old behaviour.

Q12 is therefore NOT satisfied by this fixture alone: it reaches parity on
tracks, items, rules and roles, but not on statuses or decisions.
"""

import json
from pathlib import Path

import pytest

from app.rule_engine import evaluate_condition, validate_template_schema
from tests.conftest import enable_mfa, register_and_login

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks" / "agile.json"

DOR = "definition-of-ready"
DOD = "definition-of-done"
REVIEW = "increment-review"


def _schema() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


class AgileProject:
    """This module's own small handle: a published agile template, one
    project seeded from it, and the helpers these tests need. Keeps the
    tenant/project/client plumbing out of every test body."""

    def __init__(self, client, tenant_id: str, created: dict):
        self.client = client
        self.tenant_id = tenant_id
        self.project_id = created["project"]["id"]
        self.occurrences = {o["gate_id"]: o for o in created["occurrences"]}
        self.items = {i["rule_id"]: i for i in created["evidence_items"]}

    def new_increment(self, gate_id: str) -> dict:
        resp = self.client.post(
            f"/orgs/{self.tenant_id}/projects/{self.project_id}/occurrences",
            json={"gate_id": gate_id, "trigger": "routine"},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def revise(self, rule_id: str, status: str, reference: str | None = None, base_revision: int = 1):
        payload: dict = {"base_revision": base_revision, "status": status}
        if reference is not None:
            payload["reference"] = reference
        return self.client.post(f"/orgs/{self.tenant_id}/evidence/{self.items[rule_id]['id']}/revisions", json=payload)

    def preview(self, gate_id: str, outcome: str | None = None) -> dict:
        resp = self.client.post(
            f"/orgs/{self.tenant_id}/projects/{self.project_id}/occurrences/{self.occurrences[gate_id]['id']}/preview",
            json={"outcome": outcome} if outcome else {},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def decide(self, gate_id: str, outcome: str, digest: str, key: str):
        return self.client.post(
            f"/orgs/{self.tenant_id}/projects/{self.project_id}/occurrences"
            f"/{self.occurrences[gate_id]['id']}/decisions",
            json={"outcome": outcome, "manifest_digest": digest},
            headers={"Idempotency-Key": key},
        )

    def hard_rules_of(self, gate_id: str) -> list[str]:
        return [
            rule_id
            for rule_id, item in self.items.items()
            if item["gate_id"] == gate_id and item["blocker_level"] == "hard"
        ]


@pytest.fixture()
def agile(client) -> AgileProject:
    register_and_login(client, "admin@squad.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Squad Co"}).json()["id"]

    imported = client.post(
        f"/orgs/{tenant_id}/templates/import",
        json={"name": "Agile DoR/DoD (validation fixture)", "schema_json": _schema()},
    ).json()
    published = client.post(f"/orgs/{tenant_id}/templates/{imported['template_id']}/versions/{imported['id']}/publish")
    assert published.status_code == 200, published.text

    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={"name": "Platform squad", "template_version_id": imported["id"], "class_id": "Team", "members": []},
    )
    assert created.status_code == 201, created.text
    return AgileProject(client, tenant_id, created.json())


# --------------------------------------------------------------------------
# What genuinely works: the model IS general in structure.
# --------------------------------------------------------------------------


def test_works_fixture_is_a_valid_template_schema():
    """No special case: the agile shape passes the same validator a
    tenant's own imported JSON goes through."""
    schema = validate_template_schema(_schema())
    assert [g.gate_id for g in schema.gates] == [DOR, DOD, REVIEW]


def test_works_fixture_is_marked_a_validation_fixture_not_a_starter():
    """Q12: "Mark it a validation fixture, not a shipped starter template,
    until it has passed its own review." This flag is what stops
    seed_starter_frameworks.py publishing it to every tenant."""
    meta = json.loads(FIXTURE.read_text(encoding="utf-8"))["_meta"]
    assert meta["validation_fixture"] is True
    assert meta.get("note")


def test_works_check_ids_are_unnumbered():
    """Q11: "recurring per-increment checks, unnumbered". Nothing in the
    model forces a number into a gate_id or a rule_id."""
    schema = validate_template_schema(_schema())
    for gate in schema.gates:
        assert not any(ch.isdigit() for ch in gate.gate_id), gate.gate_id
        for rule in gate.rules:
            assert not any(ch.isdigit() for ch in rule.rule_id), rule.rule_id


def test_works_fixture_exercises_the_dec07_q10_vocabulary():
    """This fixture is the first consumer of the Q10 operator additions, so
    it is also the first thing that would catch a regression in them."""
    schema = validate_template_schema(_schema())
    assert schema.vocabulary_version == 2
    used: set[str] = set()
    for gate in schema.gates:
        for rule in gate.rules:
            used |= rule.operators_used()
    assert {"not", "count"} <= used, used


def test_works_recurring_checks_get_independent_evidence_each_increment(agile):
    """Q11's core structural claim. The same check set, evaluated again next
    sprint, with its own evidence -- expressed as occurrence 2 of the same
    definition, needing no new model concept and no special case."""
    assert all(o["sequence"] == 1 for o in agile.occurrences.values())
    sprint1 = {i["id"] for i in agile.items.values() if i["gate_id"] == DOD}
    assert sprint1

    second = agile.new_increment(DOD)
    assert second["occurrence"]["sequence"] == 2
    sprint2 = {i["id"] for i in second["evidence_items"]}

    assert sprint2, "a recurring check must seed its own evidence each increment"
    assert sprint1.isdisjoint(sprint2), (
        "REQ-016: no two occurrences may share evidence -- a sprint-2 check must never inherit sprint-1's answers"
    )


def test_works_triggered_checks_do_not_auto_seed(agile):
    """The increment-review set is deliberately all-`triggered`: it happens
    when someone calls the review, not automatically at project creation.
    REQ-016's existing rule covers this with no agile-specific code."""
    assert REVIEW not in agile.occurrences, "a check set with only triggered rules should get no automatic occurrence"


# --------------------------------------------------------------------------
# The gaps. CHARACTERIZATION ONLY -- see this module's docstring.
# Expected to be rewritten by the vocabulary-indirection fix, not preserved.
# --------------------------------------------------------------------------


def test_gap_declared_statuses_are_not_honoured_by_readiness(agile):
    """PINS CURRENT WRONG BEHAVIOUR. The fixture declares its completion
    word as "Met". Readiness hardcodes the literal "Complete"
    (routers/decisions.py `item.status == "Complete"`), so marking every
    hard check "Met" leaves every one of them a hard blocker.

    It fails CLOSED -- no unready decision slips through, which is why this
    is a generality gap rather than a control bypass. But the framework's
    own vocabulary is not honoured, and `TemplateSchema.statuses` is read
    nowhere in any readiness path."""
    hard = agile.hard_rules_of(DOD)
    for rule_id in hard:
        assert agile.revise(rule_id, "Met", reference="https://ci.example/run/1").status_code == 201

    preview = agile.preview(DOD)
    assert len(preview["hard_blockers"]) == len(hard), (
        "if this now reports fewer blockers, the status vocabulary was generalised -- "
        "rewrite this test to assert the correct behaviour"
    )
    assert "has not been marked Complete" in preview["blocker_explanations"][0]["explanation"]


def test_gap_only_the_literal_word_complete_clears_a_blocker(agile):
    """PINS CURRENT WRONG BEHAVIOUR. The same item with the same reference
    clears its blocker only when the status string is exactly "Complete" --
    a word this framework never declares."""
    rule_id = agile.hard_rules_of(DOD)[0]
    item_id = agile.items[rule_id]["id"]

    assert agile.revise(rule_id, "Met", reference="https://ci.example/run/1").status_code == 201
    assert item_id in agile.preview(DOD)["hard_blockers"]

    assert agile.revise(rule_id, "Complete", reference="https://ci.example/run/1", base_revision=2).status_code == 201
    assert item_id not in agile.preview(DOD)["hard_blockers"]


def test_gap_an_undeclared_status_is_accepted(agile):
    """PINS CURRENT WRONG BEHAVIOUR. `statuses` constrains nothing: a status
    the template never declared is stored without complaint. The authoring
    UI offers the declared list (webapp/router.py passes `schema.statuses`
    into the evidence form), so that list looks authoritative while being
    advisory."""
    rule_id = agile.hard_rules_of(DOD)[0]
    assert "Bananas" not in _schema()["statuses"]
    assert agile.revise(rule_id, "Bananas", reference="x").status_code == 201


def test_gap_req018_reference_requirement_is_keyed_to_the_literal_word(agile):
    """PINS CURRENT WRONG BEHAVIOUR, and this is the sharpest edge of the
    five. REQ-018 ("do not allow a required item to be Complete without a
    reference") is enforced as `payload.status == "Complete"`
    (routers/projects.py). A framework whose completion word differs walks
    straight past it: a required hard check reaches a done-meaning status
    with no reference at all.

    Readiness still blocks the decision, so no unready gate gets approved --
    but the evidence record itself now carries exactly the unreferenced
    "done" this control exists to forbid."""
    rule_id = agile.hard_rules_of(DOD)[0]
    assert agile.items[rule_id]["required"] is True

    bypassed = agile.revise(rule_id, "Met")  # no reference whatsoever
    assert bypassed.status_code == 201, (
        "if this is now rejected, REQ-018 was generalised beyond the literal "
        "word -- rewrite this test to assert the correct behaviour"
    )

    enforced = agile.revise(rule_id, "Complete", base_revision=2)
    assert enforced.status_code == 422
    assert "REQ-018" in enforced.text


def test_gap_declared_decision_outcomes_cannot_be_recorded(agile):
    """PINS CURRENT WRONG BEHAVIOUR. With every hard blocker cleared the
    only way the engine accepts, this fixture's declared outcomes are still
    unusable: `_outcome_eligibility` matches the Blueprint's five English
    outcome words, so `permitted_outcomes` comes back empty and recording
    either declared outcome 422s.

    The engine is honest about it -- the message says the outcome is
    "declared by the template but not handled by this prototype's decision
    logic" -- so this is a known, deliberate limit rather than a surprise.
    This fixture is simply the first thing to reach it."""
    for rule_id in agile.hard_rules_of(DOD):
        agile.revise(rule_id, "Complete", reference="https://ci.example/run/1")

    preview = agile.preview(DOD)
    assert preview["hard_blockers"] == []
    assert preview["permitted_outcomes"] == [], (
        "if this is now non-empty, decision outcomes were generalised -- "
        "rewrite this test to assert the correct behaviour"
    )

    for outcome in _schema()["decision_outcomes"]:
        refused = agile.decide(DOD, outcome, preview["manifest_digest"], key=f"q11-{outcome}")
        assert refused.status_code == 422
        assert "not handled by this prototype's decision logic" in refused.text


def test_gap_rule_conditions_are_never_evaluated_at_runtime(agile):
    """PINS CURRENT WRONG BEHAVIOUR, and this is the widest of the findings.

    `evaluate_condition` has exactly one call site in the whole application
    (`routers/projects.py`, on `rule.applicability`). A rule's `conditions`
    tree -- the part that says what actually has to be true -- is validated
    for depth, the 200-node cap and the operator vocabulary, then never
    walked by any readiness path. Readiness is decided purely by the
    human-set `status` string.

    So all of DEC07 Q10's machinery (the new operators, the node cap, the
    evaluation timeout) currently governs a tree nothing evaluates for
    readiness. This test proves the consequence in three steps: the rule
    HAS a conditions tree; that tree is False against the only facts the
    application ever supplies; and the item's blocker clears anyway, on
    status alone."""
    schema = validate_template_schema(_schema())
    rule = next(
        r for g in schema.gates if g.gate_id == DOD for r in g.rules if r.rule_id == "definition-of-done.checks-pass"
    )

    assert rule.conditions is not None, "this test is meaningless if the rule has no conditions tree"

    # The predicate itself is sound and satisfiable -- this matters, because
    # it rules out the alternative reading that the condition is simply
    # malformed. Fed the fact it asks for, it is True.
    assert evaluate_condition(rule.conditions, {"automated_checks_passing": True}) is True

    # But the only facts any call site ever supplies are these (projects.py
    # seeds applicability with exactly `{"class_id": ...}`), so the fact is
    # unknown and the condition fails closed. No project state reaches it.
    assert evaluate_condition(rule.conditions, {"class_id": "Team"}) is False

    # ...and yet:
    assert agile.revise(rule.rule_id, "Complete", reference="https://ci.example/run/1").status_code == 201
    assert agile.items[rule.rule_id]["id"] not in agile.preview(DOD)["hard_blockers"], (
        "if this item is still blocked, rule.conditions is now actually "
        "evaluated -- rewrite this test to assert the correct behaviour"
    )


def test_gap_required_fields_is_declared_but_has_no_consumers(agile):
    """PINS CURRENT WRONG BEHAVIOUR. `required_fields` is declared on every
    rule in the approved Sec.5.5 schema and read by nothing: one line in
    `rule_engine.py` defines it, and there is no other reference anywhere in
    the application. There is no mechanism to supply the named fields at
    all, so a revision naming none of them satisfies the item."""
    rule_id = "definition-of-done.checks-pass"
    schema = validate_template_schema(_schema())
    rule = next(r for g in schema.gates if g.gate_id == DOD for r in g.rules if r.rule_id == rule_id)

    assert rule.required_fields == ["run_url"], "the fixture should declare a required field for this to mean anything"

    # Nothing supplies `run_url`; the revision carries only the platform's
    # own generic fields. Accepted regardless.
    accepted = agile.revise(rule_id, "Complete", reference="not-a-run-url")
    assert accepted.status_code == 201, (
        "if this is now rejected, required_fields gained an enforcer -- "
        "rewrite this test to assert the correct behaviour"
    )
    assert agile.items[rule_id]["id"] not in agile.preview(DOD)["hard_blockers"]
