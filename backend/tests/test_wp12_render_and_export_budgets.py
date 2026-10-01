"""WP12 (Blueprint Sec.6, REQ-043) performance-budget remainder.

REQ-043's three numeric sub-parts (DEC08, docs/blueprint/
BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md, Q15/Q16):
  1. API p95/p99 latency -- already covered by test_dec08_performance_budgets.py.
  2. Render-timing (LCP/INP/CLS) and page-weight budgets -- need real browser
     tooling. Enforced by a separate Lighthouse-based Node harness
     (tools/perf-budgets/) and its own CI job, not testable from pytest --
     see that directory's README for how it is run and what it checks.
  3. Export streaming -- "asynchronous; must begin streaming within 2 s".
     This file covers that third sub-part, the one piece Python can test
     directly.

Before this change, GET .../export-import/exports/{id}/download fully
materialized the archive into one Python string via json.dumps(...) and
returned it as a single buffered fastapi.Response -- no bytes reached the
client until that whole string existed, regardless of archive size. Fixed
by streaming the same JSON content incrementally via
json.JSONEncoder.iterencode, through a real StreamingResponse, so bytes
start flowing as soon as the DB fetch completes, not after the entire body
is serialized. Archive content, FORMAT_VERSION and storage are unchanged --
only the delivery mechanism of the download endpoint differs.
"""

import json
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.routers.exports import _iter_archive_json

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


def test_iter_archive_json_yields_more_than_one_chunk_and_matches_dumps():
    """Proves the generator is genuinely incremental, not `yield full_string`
    once -- a single chunk would mean the whole archive was still buffered
    in memory before anything was emitted, defeating the point. No Postgres
    needed -- this is pure in-process behaviour of the helper itself."""
    archive = {
        "manifest": {"format_version": 1, "section_digests": {"templates": "abc123"}},
        "templates": [{"id": str(i), "name": f"Template {i}"} for i in range(200)],
        "projects": [],
    }
    chunks = list(_iter_archive_json(archive))
    assert len(chunks) > 1, "a single chunk means the whole archive was buffered before any byte was emitted"
    assert "".join(chunks) == json.dumps(archive, indent=2, default=str)


@pytest.fixture()
def ui_client():
    from fastapi.testclient import TestClient

    from app.main import app

    assert app.dependency_overrides == {}, "this test needs the REAL Postgres get_db, not the SQLite fixture"
    return TestClient(app, follow_redirects=True)


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app not configured")
def test_export_download_streams_without_buffering_the_whole_body_first(ui_client):
    from tests.test_projects import _create_project, _publish_standard_template
    from tests.test_ui09_export_import import _register_and_login_ui

    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "WP12 export-budget org"}).json()["id"]
    version_id, _ = _publish_standard_template(ui_client, tenant_id)
    _create_project(ui_client, tenant_id, version_id, "Standard-High")

    job_id = ui_client.post(f"/orgs/{tenant_id}/exports").json()["id"]

    start = time.monotonic()
    with ui_client.stream("GET", f"/ui/orgs/{tenant_id}/export-import/exports/{job_id}/download") as resp:
        assert resp.status_code == 200
        # DEC08 Q16's own words: "asynchronous; must begin streaming within
        # 2 s". A StreamingResponse never sends a precomputed
        # content-length -- the honest signal that the body was not fully
        # buffered in memory before the response started.
        assert "content-length" not in resp.headers
        body_iter = resp.iter_bytes()
        first_chunk = next(body_iter)
        time_to_first_byte = time.monotonic() - start
        body = first_chunk + b"".join(body_iter)

    assert time_to_first_byte < 2.0, f"time to first byte was {time_to_first_byte:.3f}s, budget is 2s"
    assert json.loads(body)["manifest"]["source_tenant_id"] == tenant_id
