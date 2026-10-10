"""DEC07 Q11/Q12: the third framework fixture, and what it proved.

Q11 asked for a third fixture *structurally different* from the two
gate-based ones already built -- "an agile Definition-of-Ready /
Definition-of-Done framework with no gates at all", recurring per-increment
checks, unnumbered -- on the explicit reasoning that "if the rule engine and
data model survive that without a special case, the model is genuinely
general." Q12 asked for full parity on the model: tracks, items, rules,
roles, statuses, decisions.

Structurally it survived; on statuses and decisions it did not, and that
history is the useful part. The gap was found by this fixture, recorded as
"DEC07-Q11 vocabulary indirection" in docs/DEFECT_REGISTER.md, pinned here
by characterization tests, and then fixed by the vocabulary-indirection
work. Q12 closes in this file, against the vocabulary-3 fixture
fixtures/synthetic/frameworks/agile.v3.json.

There are three groups of tests below, and the distinction still matters:

  * `test_works_*` -- real capability, asserted against the v1 fixture.
    Structural generality that held from the start; if one breaks,
    something regressed.

  * the positive counterparts -- six of the seven former `test_gap_*`
    tests, rewritten (not restored) against the v3 fixture exactly as their
    own docstrings instructed. Each names the gap test it replaces.

  * `test_required_fields_remains_declared_but_inert` -- the one
    characterization test that STAYS one, because the gap it pins is still
    open. `required_fields` is declared on every rule and consumed by
    nothing, and no part of this work gives it a consumer; the
    `required_fields` half of sub-finding 6 in DEFECT_REGISTER.md is
    deliberately left open to match. Do not convert it to a positive test
    until something actually enforces the named fields.

agile.json itself is unchanged: published and immutable under REQ-011, and
the artefact that demonstrated the gap. It keeps failing closed, which is
also G6's proof at the fixture level
(test_the_v1_fixture_is_retained_and_still_fails_closed).
"""

import json
from pathlib import Path

import pytest

from app.rule_engine import validate_template_schema
from tests.conftest import enable_mfa, login, register_and_login
from tests.test_projects import _invite_and_accept

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
        # All four mirrored fields are restated, not omitted: a revision is a
        # complete statement of them (CreateEvidenceRevisionRequest), and
        # explicit None here reproduces exactly what this helper's omission
        # used to mean implicitly. `reference` is overwritten just below when
        # a caller supplies one.
        payload: dict = {
            "base_revision": base_revision,
            "status": status,
            "owner_user_id": None,
            "due_date": None,
            "completed_date": None,
            "reference": None,
        }
        if reference is not None:
            payload["reference"] = reference
        return self.client.post(f"/orgs/{self.tenant_id}/evidence/{self.items[rule_id]['id']}/revisions", json=payload)

    def detail(self, rule_id: str) -> dict:
        """The item as STORED now, with its revisions -- `self.items` is the
        snapshot taken at project creation and never refreshed, so a test
        asserting about state after a revision has to re-read it."""
        resp = self.client.get(f"/orgs/{self.tenant_id}/evidence/{self.items[rule_id]['id']}")
        assert resp.status_code == 200, resp.text
        return resp.json()

    def current_status(self, rule_id: str) -> str:
        return self.detail(rule_id)["item"]["status"]

    def latest_revision_actor(self, rule_id: str) -> str:
        return self.detail(rule_id)["revisions"][-1]["actor_user_id"]

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

    def me(self) -> str:
        return self.client.get("/auth/me").json()["id"]

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
# These were CHARACTERIZATION tests pinning the vocabulary-indirection
# defect. The vocabulary-indirection work landed, so six of the seven are
# now their positive counterparts against the v3 fixture -- rewritten, not
# restored, exactly as the previous docstrings instructed. The seventh
# (required_fields) is still a gap test, because its gap is still open.
# --------------------------------------------------------------------------

FIXTURE_V3 = FIXTURE.parent / "agile.v3.json"


def _schema_v3() -> dict:
    data = json.loads(FIXTURE_V3.read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


def _publish_v3_project(client, tenant_id: str, members: list[dict]) -> AgileProject:
    imported = client.post(
        f"/orgs/{tenant_id}/templates/import",
        json={"name": "Agile DoR/DoD v3", "schema_json": _schema_v3()},
    ).json()
    pub = client.post(f"/orgs/{tenant_id}/templates/{imported['template_id']}/versions/{imported['id']}/publish")
    assert pub.status_code == 200, pub.text
    created = client.post(
        f"/orgs/{tenant_id}/projects",
        json={
            "name": "Platform squad",
            "template_version_id": imported["id"],
            "class_id": "Team",
            "members": members,
        },
    )
    assert created.status_code == 201, created.text
    return AgileProject(client, tenant_id, created.json())


@pytest.fixture()
def agile_v3(client) -> AgileProject:
    register_and_login(client, "admin@squadv3.example")
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Squad V3 Co"}).json()["id"]
    return _publish_v3_project(client, tenant_id, [])


V3_SOD_ADMIN = "admin@squadv3sod.example"
V3_SOD_SECOND = "developer2@squadv3sod.example"


@pytest.fixture()
def agile_v3_two_person(client) -> AgileProject:
    """The same v3 project, but with a SECOND project member, so a decision
    can be reached without tripping REQ-006. Every seeded evidence item's
    revision 1 is attributed to whoever created the project, so in the
    single-user `agile_v3` fixture the admin is the only preparer of every
    required item -- which is self-only approval by definition."""
    register_and_login(client, V3_SOD_ADMIN)
    enable_mfa(client)
    tenant_id = client.post("/orgs", json={"name": "Squad V3 SoD Co"}).json()["id"]
    second_id = _invite_and_accept(client, tenant_id, V3_SOD_SECOND, "approver")
    enable_mfa(client)
    login(client, V3_SOD_ADMIN)
    # "approver" is a platform Role, and project membership roles must be one
    # of those -- agile.v3.json's own declared roles (product_owner,
    # developer, facilitator) are NOT assignable, which is exactly the
    # "declared role vocabulary is not honoured" gap recorded in
    # docs/DEFECT_REGISTER.md. So this member's project role cannot match any
    # of this template's permitted_role_ids, and submission falls back to
    # membership-only (see _require_permitted_to_attest). That fallback is
    # what keeps this test working; it is not an endorsement of it.
    return _publish_v3_project(client, tenant_id, [{"user_id": second_id, "role": "approver"}])


def test_the_v3_fixture_declares_vocabulary_3_and_its_own_semantics():
    """The fixture is what makes vocabulary 3 reachable at all:
    VOCABULARY_VERSION (the stamp on new guided-authoring drafts) stays 2
    per spec Sec.7 rollout step 1, so a template only evaluates as v3 when
    its own JSON says so."""
    schema = validate_template_schema(_schema_v3())
    assert schema.vocabulary_version == 3
    statuses = schema.status_lookup()
    assert schema.initial_status() == "Not met"
    assert statuses["Met"].satisfies is True
    assert statuses["Waived"].satisfies is True
    assert statuses["Waived"].requires_exception is True
    assert {o.id: o.kind for o in schema.outcome_lookup().values()} == {
        "Increment accepted": "approving",
        "Accepted with follow-ups": "conditional_approving",
        "Not accepted": "recording",
    }
    # Every status id has to fit EvidenceItem.status (String(30)), so the
    # cap is worth asserting. It is NOT why v1's "Waived for this
    # increment" became "Waived": that string is 25 characters and was
    # already within the limit. The rename is an editorial choice available
    # in a new template version -- a shorter id that reads the same in a
    # status control -- and nothing forced it.
    assert all(len(status_id) <= 30 for status_id in statuses)
    assert len("Waived for this increment") <= 30, "the v1 id fitted; the cap did not drive the rename"


def test_declared_statuses_now_drive_readiness(agile_v3):
    """Was test_gap_declared_statuses_are_not_honoured_by_readiness."""
    hard = agile_v3.hard_rules_of(DOD)
    assert hard, "this test is meaningless if the gate has no hard items"
    for rule_id in hard:
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


def test_declared_decision_outcomes_can_now_be_recorded(agile_v3_two_person):
    """Was test_gap_declared_decision_outcomes_cannot_be_recorded. This
    assertion closes DEC07 Q12.

    It reaches the decision THROUGH REQ-006, not around it: the second
    project member prepares one of the two hard items, so the deciding
    admin is not the only preparer and separation of duties is satisfied
    without an override. The self-only case is the next test, and it is
    refused."""
    agile_v3 = agile_v3_two_person
    hard = agile_v3.hard_rules_of(DOD)
    assert len(hard) >= 2, "this test needs two hard items so the two members can prepare one each"

    login(agile_v3.client, V3_SOD_SECOND)
    assert agile_v3.revise(hard[0], "Met", reference="https://ci.example/run/1").status_code == 201
    login(agile_v3.client, V3_SOD_ADMIN)
    for rule_id in hard[1:]:
        assert agile_v3.revise(rule_id, "Met", reference="https://ci.example/run/1").status_code == 201

    preview = agile_v3.preview(DOD)
    assert preview["hard_blockers"] == []
    assert "Increment accepted" in preview["permitted_outcomes"]
    assert agile_v3.latest_revision_actor(hard[0]) != agile_v3.me(), (
        "separation of duties has to be genuinely satisfied here, not skipped"
    )

    recorded = agile_v3.decide(DOD, "Increment accepted", preview["manifest_digest"], key="q12-closed")
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["outcome"] == "Increment accepted"


def test_a_declared_approving_outcome_is_refused_for_a_self_only_approver(agile_v3):
    """REQ-006 keyed on the outcome's declared `kind` rather than on the
    Blueprint's literal words.

    This assertion used to be the other way round. `_record_decision` gated
    `_check_separation_of_duties` on `payload.outcome in ("Approve",
    "Approve with conditions")` while `_outcome_eligibility` above it
    already resolved outcomes by `kind`, so a template-declared `approving`
    outcome committed an approval with no self-approval check at all -- the
    identical evidence state under the word "Approve" being refused 403 by
    test_decisions.py::test_full_approval_flow_with_separation_of_duties_override.
    The register row "DEC07 SoD outcome literal" carries the history. This
    test now pins the control instead of the bypass."""
    hard = agile_v3.hard_rules_of(DOD)
    for rule_id in hard:
        assert agile_v3.revise(rule_id, "Met", reference="https://ci.example/run/1").status_code == 201
    preview = agile_v3.preview(DOD)
    assert preview["hard_blockers"] == [], "the refusal below must be about REQ-006, not about a blocker"

    # The precondition, asserted rather than assumed: one user authored
    # every required item's current revision and is now the decider.
    assert {agile_v3.latest_revision_actor(r) for r in hard} == {agile_v3.me()}

    denied = agile_v3.decide(DOD, "Increment accepted", preview["manifest_digest"], key="sod-v3-approving")
    assert denied.status_code == 403, denied.text
    assert "compensating review" in denied.text, denied.text


def test_waived_requires_a_real_exception(agile_v3):
    """New, and the reason `requires_exception` exists: a second
    satisfying status must not become a way around a hard blocker."""
    rule_id = agile_v3.hard_rules_of(DOD)[0]
    assert agile_v3.revise(rule_id, "Waived", reference="waiver").status_code == 201
    assert agile_v3.items[rule_id]["id"] in agile_v3.preview(DOD)["hard_blockers"]


def test_rule_conditions_are_now_evaluated_for_readiness(agile_v3):
    """Was test_gap_rule_conditions_are_never_evaluated_at_runtime, the
    widest of the findings: `conditions` used to be validated and then
    never walked by any readiness path.

    The v3 fixture's `definition-of-ready.acceptance-criteria` carries the
    one condition tree that survived retranslation into DEC07's closed
    `item:<rule_id>` fact namespace -- at least two of its two sibling DoR
    checks satisfied. The second half of this test is the assertion that
    matters: regress one sibling and the summary item blocks AGAIN while
    its own status still says "Met". Without that half, the test would
    pass whether or not conditions are evaluated at all."""
    summary = f"{DOR}.acceptance-criteria"
    sibling = f"{DOR}.no-blocking-unknowns"
    other = f"{DOR}.sized"
    summary_item_id = agile_v3.items[summary]["id"]

    for rule_id in (sibling, other, summary):
        assert agile_v3.revise(rule_id, "Met", reference="ready-1").status_code == 201
    assert summary_item_id not in agile_v3.preview(DOR)["hard_blockers"]

    # One sibling regresses. The summary item's OWN status is untouched and
    # still satisfying, so only condition evaluation can block it.
    assert agile_v3.revise(sibling, "Not met", base_revision=2).status_code == 201
    assert agile_v3.current_status(summary) == "Met", "the summary item's own status must be untouched here"
    assert summary_item_id in agile_v3.preview(DOR)["hard_blockers"], (
        "the summary item must block again once a sibling regresses, despite its own satisfying status -- "
        "if it does not, rule.conditions is no longer being evaluated"
    )


def test_required_fields_remains_declared_but_inert(agile_v3):
    """STILL A CHARACTERIZATION TEST -- the one of the seven that did not
    become a positive counterpart, because its gap is still open.

    `required_fields` is declared on every rule in the approved Sec.5.5
    schema and read by nothing: one line in `rule_engine.py` defines the
    field, and there is no other reference anywhere in the application.
    There is no mechanism to supply the named fields at all, so a revision
    naming none of them satisfies the item. The vocabulary-indirection work
    did not change that and did not claim to -- see the `required_fields`
    half of sub-finding 6 in docs/DEFECT_REGISTER.md, which stays open.

    Run against the v3 fixture only because the v1 fixture no longer
    accepts the literal "Complete" (a status it never declared); the gap
    being pinned is unchanged."""
    rule_id = f"{DOD}.checks-pass"
    rule = next(r for g in validate_template_schema(_schema_v3()).gates for r in g.rules if r.rule_id == rule_id)
    assert rule.required_fields == ["run_url"], "the fixture should declare a required field for this to mean anything"

    # Nothing supplies `run_url`; the revision carries only the platform's
    # own generic fields, and `reference` is not even URL-shaped. Accepted
    # regardless, and the item's blocker clears.
    accepted = agile_v3.revise(rule_id, "Met", reference="not-a-run-url")
    assert accepted.status_code == 201, (
        "if this is now rejected, required_fields gained an enforcer -- "
        "rewrite this test as its positive counterpart and close the register row"
    )
    assert agile_v3.items[rule_id]["id"] not in agile_v3.preview(DOD)["hard_blockers"]


def test_the_v1_fixture_seeds_its_own_first_declared_status(agile):
    """An ACCEPTED vocabulary-1/2 behaviour change, pinned so it cannot be
    silent (docs/DEFECT_REGISTER.md, the DEC07-Q11 row's G6 exceptions).

    Seeding used to write the literal "Not started" into every new evidence
    item; it now calls `TemplateSchema.initial_status()`. agile.json is
    vocabulary 2 and declares ['Not met', 'Met', 'Waived for this
    increment'] -- it never declared "Not started" -- so its projects now
    seed 'Not met'. That is arguably more correct than before (the platform
    was writing a status this framework does not recognise), but it IS a
    change for any v1/v2 template that omits "Not started", and the three
    gate-based fixtures keep seeding "Not started" only because they all
    declare it (test_dec07_vocabulary_backcompat.py pins that side)."""
    assert {i["status"] for i in agile.items.values()} == {"Not met"}
    schema = validate_template_schema(_schema())
    assert "Not started" not in schema.status_lookup(), (
        "this test only means something while agile.json omits the old seeding literal"
    )


def test_the_v1_fixture_is_retained_and_still_fails_closed(agile):
    """Was test_gap_only_the_literal_word_complete_clears_a_blocker.
    agile.json is published and immutable (REQ-011); it must keep behaving
    exactly as it did, which is also G6's proof at the fixture level.

    At vocabulary 2 a plain-string status only satisfies if it is the
    literal "Complete", so this fixture's own "Met" is stored happily and
    still blocks -- failing closed, the behaviour the finding described."""
    rule_id = agile.hard_rules_of(DOD)[0]
    assert agile.revise(rule_id, "Met", reference="https://ci.example/run/1").status_code == 201
    assert agile.items[rule_id]["id"] in agile.preview(DOD)["hard_blockers"]
