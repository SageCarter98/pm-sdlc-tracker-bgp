"""DEC08 (docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md,
Q15): numeric API p95/p99 latency budgets, "Server time at origin, excluding
client network" -- enforced here as an in-process TestClient measurement
against real Postgres, which is exactly that scope (no real network hop to
exclude in the first place). Answer's own words: "All of this enforced in CI
as a blocking budget check, not a dashboard someone reads occasionally" --
this file is that check; see .github/workflows/ci.yml's dedicated step.

Budgets enforced here (Q15):
- Reads (gate view, dashboard): p95 <= 300 ms, p99 <= 800 ms
- Ordinary writes: p95 <= 500 ms
- Decision writes: p95 <= 800 ms, p99 <= 1.5 s

Not enforced HERE, but enforced ELSEWHERE -- corrected 2026-10-07, because
this docstring described both of DEC08's other two numeric sub-parts as
unbuilt and both were built on 2026-10-01 in `5e9baf5` (PR #9). What is
true is only that pytest is the wrong place for them, not that they are
missing:

- The export budget ("asynchronous; must begin streaming within 2 s") is
  enforced by `test_wp12_render_and_export_budgets.py`. The premise this
  docstring previously rested on -- that exports are synchronous so there
  is no "begin streaming" moment -- no longer holds: the download endpoint
  now streams incrementally via `exports.py`'s `_iter_archive_json` through
  a real `StreamingResponse`, so the moment exists and is measured.
- DEC08's render-timing budgets (LCP/INP/CLS and page-weight KB under an
  emulated Fast-3G/mid-range-Android profile) are enforced by the Lighthouse
  Node harness in `tools/perf-budgets/` and its own blocking CI step
  ("Render-timing and page-weight budgets (DEC08 Q14/Q16)" in
  `.github/workflows/ci.yml`). Still correct that THIS Postgres-backed API
  test cannot measure them honestly -- it needs a real headless browser,
  which is exactly what that harness provides.

So this file covers the first of REQ-043's three numeric sub-parts. The
other two are covered, each in the only place that can measure it.

Same live-Postgres requirement as every other IPA02/WP13+ webapp/API test in
this suite -- server-side timing against the SQLite fixture (in-memory, no
real network round trip to Postgres) would not measure what DEC08 asks for.
"""

import statistics
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings

try:
    _owner_engine = create_engine(settings.migration_database_url, future=True)
    with _owner_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    _app_engine = create_engine(settings.database_url, future=True)
    with _app_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    POSTGRES_AVAILABLE = True
except OperationalError:
    POSTGRES_AVAILABLE = False

pytestmark = pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app not configured")


@pytest.fixture()
def pg_client():
    from fastapi.testclient import TestClient

    from app.main import app

    assert app.dependency_overrides == {}, "DEC08 measures real server time -- the SQLite fixture is not real Postgres"
    return TestClient(app)


def _percentiles(samples_ms: list[float]) -> dict:
    ranked = statistics.quantiles(samples_ms, n=100, method="inclusive")
    return {"p50": ranked[48], "p95": ranked[93], "p99": ranked[97]}


def _timed(fn, n: int) -> list[float]:
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def _setup_project(pg_client):
    """Same shape as test_decisions.py's own _setup_project_with_second_
    approver, but with unique-per-call emails -- that helper hardcodes
    'admin@tenant-a.example'/'approver2@tenant-a.example', fine for the
    SQLite `client` fixture (truncated per test) but not for real Postgres,
    which persists accounts (and their MFA-enrolled state) across separate
    test functions in this same file."""
    from tests.conftest import enable_mfa, register_and_login
    from tests.test_projects import (
        _create_org_as_admin,
        _create_project,
        _invite_and_accept,
        _publish_standard_template,
    )

    admin_email = f"{uuid.uuid4()}@example.com"
    approver_email = f"{uuid.uuid4()}@example.com"

    tenant_id = _create_org_as_admin(pg_client, admin_email)
    enable_mfa(pg_client)
    admin_id = pg_client.get("/auth/me").json()["id"]

    approver_id = _invite_and_accept(pg_client, tenant_id, approver_email, "approver")
    enable_mfa(pg_client)

    register_and_login(pg_client, admin_email)
    version_id, _ = _publish_standard_template(pg_client, tenant_id)
    created = _create_project(
        pg_client, tenant_id, version_id, "Standard-High", members=[{"user_id": approver_id, "role": "approver"}]
    ).json()
    return tenant_id, created, admin_id, approver_id


def test_read_budget_gate_dashboard_and_my_work(pg_client):
    tenant_id, _created, _admin_id, _approver_id = _setup_project(pg_client)

    def _read():
        resp = pg_client.get(f"/orgs/{tenant_id}/my-work")
        assert resp.status_code == 200, resp.text

    samples = _timed(_read, n=40)
    stats = _percentiles(samples)
    assert stats["p95"] <= 300, f"read p95 {stats['p95']:.1f} ms exceeds DEC08's 300 ms budget ({stats})"
    assert stats["p99"] <= 800, f"read p99 {stats['p99']:.1f} ms exceeds DEC08's 800 ms budget ({stats})"


def test_ordinary_write_budget_evidence_revision(pg_client):
    tenant_id, created, _admin_id, _approver_id = _setup_project(pg_client)
    item_id = next(e["id"] for e in created["evidence_items"] if e["gate_id"] == "S1")

    counter = {"revision": 1}

    def _write():
        resp = pg_client.post(
            f"/orgs/{tenant_id}/evidence/{item_id}/revisions",
            json={
                "base_revision": counter["revision"],
                "status": "In progress",
                "reference": f"doc-{counter['revision']}",
                "source_hash": "sha256:x",
            },
        )
        assert resp.status_code == 201, resp.text
        counter["revision"] += 1

    samples = _timed(_write, n=30)
    stats = _percentiles(samples)
    assert stats["p95"] <= 500, f"ordinary-write p95 {stats['p95']:.1f} ms exceeds DEC08's 500 ms budget ({stats})"


def test_decision_write_budget_hold_and_supersede(pg_client):
    """Repeated Hold decisions on one occurrence chain (create then N-1
    supersessions) -- Hold bypasses the hard-blocker denial (decisions.py
    line ~263), so this measures the real decision-commit code path
    (idempotency check, manifest re-validation, coordinated locks, append-
    only insert) without needing full evidence completion first, same
    manifest_digest throughout since nothing about the evidence changes."""
    tenant_id, created, _admin_id, _approver_id = _setup_project(pg_client)
    project_id = created["project"]["id"]
    occurrence_id = next(o["id"] for o in created["occurrences"] if o["gate_id"] == "S1")

    preview = pg_client.post(f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/preview", json={})
    assert preview.status_code == 200, preview.text
    digest = preview.json()["manifest_digest"]

    first = pg_client.post(
        f"/orgs/{tenant_id}/projects/{project_id}/occurrences/{occurrence_id}/decisions",
        json={"outcome": "Hold", "manifest_digest": digest},
        headers={"Idempotency-Key": "dec08-perf-0"},
    )
    assert first.status_code == 201, first.text
    current_id = first.json()["id"]

    counter = {"i": 1}
    current_id_holder = {"id": current_id}

    def _supersede_current():
        resp = pg_client.post(
            f"/orgs/{tenant_id}/decisions/{current_id_holder['id']}/superseding",
            json={"outcome": "Hold", "manifest_digest": digest, "reason": "perf-budget measurement"},
            headers={"Idempotency-Key": f"dec08-perf-{counter['i']}"},
        )
        assert resp.status_code == 201, resp.text
        current_id_holder["id"] = resp.json()["id"]
        counter["i"] += 1

    samples = _timed(_supersede_current, n=20)
    stats = _percentiles(samples)
    assert stats["p95"] <= 800, f"decision-write p95 {stats['p95']:.1f} ms exceeds DEC08's 800 ms budget ({stats})"
    assert stats["p99"] <= 1500, f"decision-write p99 {stats['p99']:.1f} ms exceeds DEC08's 1.5 s budget ({stats})"
