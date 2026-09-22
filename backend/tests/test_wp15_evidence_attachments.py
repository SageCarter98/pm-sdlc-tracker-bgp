"""WP15: evidence attachments (FE-097/098, conditional capability). Live
Postgres only, same pattern as every other RLS-protected table's own test
file since WP04 -- SQLite has no RLS to break against.

This file specifically exercises the "no scanner configured" pathway --
still real, still the behaviour any deployment without
BGP_CLOUDMERSIVE_API_KEY sees -- so it force-monkeypatches the scanner to
"unavailable" regardless of whether a real key happens to be present in
this environment's own backend/.env. That keeps these tests deterministic
and independent of local config. See test_wp15_cloudmersive_scanner.py for
tests against the real Cloudmersive API (skipped when no key is configured).

Core property under test, not just "upload works": an attachment can never
be downloaded while scan_status != "clean" -- with no scanner available,
every upload stays permanently undownloadable, and that 423 is the correct
behaviour, not a bug to work around in the test."""

import io
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


@pytest.fixture(autouse=True)
def _force_no_scanner(monkeypatch):
    class _UnavailableScanner:
        def scan(self, filename, data):
            return "unavailable"

    monkeypatch.setattr("app.routers.attachments.scanner", _UnavailableScanner())


def _register_and_login(client, email, password="correct horse battery staple"):
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text


@pytest.fixture()
def api_client():
    from fastapi.testclient import TestClient

    from app.main import app

    assert app.dependency_overrides == {}, "this test needs the REAL Postgres get_db, not the SQLite fixture"
    return TestClient(app, follow_redirects=True)


_SCHEMA = {
    "schema_version": 1,
    "tracks": ["Delivery"],
    "classes": ["A"],
    "roles": ["tenant_administrator"],
    "statuses": ["Not started", "In progress", "Complete"],
    "decision_outcomes": ["Approve", "Hold"],
    "gates": [
        {
            "gate_id": "G1",
            "name": "Intake",
            "sequence": 1,
            "class_ids": ["A"],
            "rules": [
                {
                    "version": 1,
                    "rule_id": "R1",
                    "class_ids": ["A"],
                    "occurrence_type": "routine",
                    "evidence_kind": "document",
                    "permitted_role_ids": ["tenant_administrator"],
                    "blocker_level": "hard",
                }
            ],
        }
    ],
}


def _seed_project(client, tenant_id):
    tv = client.post(f"/orgs/{tenant_id}/templates/import", json={"name": "T", "schema_json": _SCHEMA}).json()
    client.post(f"/orgs/{tenant_id}/templates/{tv['template_id']}/versions/{tv['id']}/publish")
    return client.post(
        f"/orgs/{tenant_id}/projects", json={"name": "P", "template_version_id": tv["id"], "class_id": "A"}
    ).json()


def test_upload_then_download_is_blocked_pending_a_scanner(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login(api_client, email)
    tenant_id = api_client.post("/orgs", json={"name": "WP15 org 1"}).json()["id"]
    proj = _seed_project(api_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]

    upload = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("note.txt", io.BytesIO(b"hello evidence"), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["scan_status"] == "unavailable"
    assert body["status"] == "active"
    assert body["filename"] == "note.txt"
    assert body["size_bytes"] == len(b"hello evidence")

    download = api_client.get(f"/orgs/{tenant_id}/attachments/{body['id']}/download")
    assert download.status_code == 423, download.text


def test_a_second_upload_supersedes_the_first_not_overwrites_it(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login(api_client, email)
    tenant_id = api_client.post("/orgs", json={"name": "WP15 org 2"}).json()["id"]
    proj = _seed_project(api_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]

    first = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("v1.txt", io.BytesIO(b"version one"), "text/plain")},
    ).json()
    second = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("v2.txt", io.BytesIO(b"version two"), "text/plain")},
    ).json()

    listing = api_client.get(f"/orgs/{tenant_id}/evidence/{item_id}/attachments").json()
    assert len(listing) == 2
    by_id = {a["id"]: a for a in listing}
    assert by_id[first["id"]]["status"] == "superseded"
    assert by_id[second["id"]]["status"] == "active"


def test_upload_rejects_an_empty_file(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login(api_client, email)
    tenant_id = api_client.post("/orgs", json={"name": "WP15 org 3"}).json()["id"]
    proj = _seed_project(api_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]

    resp = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert resp.status_code == 422


def test_an_infected_upload_is_quarantined_and_does_not_supersede_the_active_version(api_client, monkeypatch):
    """Hermetic (fake scanner, no real network call) -- the logic under
    test is "infected never becomes active / never supersedes", not
    Cloudmersive's own detection accuracy (see
    test_wp15_cloudmersive_scanner.py for that, against the real API)."""
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login(api_client, email)
    tenant_id = api_client.post("/orgs", json={"name": "WP15 org 4"}).json()["id"]
    proj = _seed_project(api_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]

    class _CleanScanner:
        def scan(self, filename, data):
            return "clean"

    class _InfectedScanner:
        def scan(self, filename, data):
            return "infected"

    monkeypatch.setattr("app.routers.attachments.scanner", _CleanScanner())
    good = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("good.txt", io.BytesIO(b"legitimate evidence"), "text/plain")},
    ).json()
    assert good["scan_status"] == "clean"
    assert good["status"] == "active"

    monkeypatch.setattr("app.routers.attachments.scanner", _InfectedScanner())
    bad = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("bad.exe", io.BytesIO(b"pretend malware"), "application/octet-stream")},
    )
    assert bad.status_code == 422, bad.text

    listing = api_client.get(f"/orgs/{tenant_id}/evidence/{item_id}/attachments").json()
    by_id = {a["id"]: a for a in listing}
    # The good, clean version is still the active one -- the rejected
    # upload was recorded (quarantined, visible for audit) but never
    # touched it.
    assert by_id[good["id"]]["status"] == "active"
    rejected = [a for a in listing if a["id"] != good["id"]][0]
    assert rejected["scan_status"] == "infected"
    assert rejected["status"] == "rejected"

    download = api_client.get(f"/orgs/{tenant_id}/attachments/{rejected['id']}/download")
    assert download.status_code == 423


def test_attachment_is_isolated_to_its_own_tenant(api_client):
    """Same shape as every other RLS leak proof since WP04: a member of
    tenant A must not be able to list or download an attachment that
    belongs to tenant B, even by guessing/enumerating a real id."""
    email_a = f"{uuid.uuid4()}@example.com"
    _register_and_login(api_client, email_a)
    tenant_a = api_client.post("/orgs", json={"name": "WP15 tenant A"}).json()["id"]
    proj_a = _seed_project(api_client, tenant_a)
    item_a = proj_a["evidence_items"][0]["id"]
    attach_a = api_client.post(
        f"/orgs/{tenant_a}/evidence/{item_a}/attachments",
        files={"file": ("a.txt", io.BytesIO(b"tenant a data"), "text/plain")},
    ).json()

    from fastapi.testclient import TestClient

    from app.main import app

    client_b = TestClient(app, follow_redirects=True)
    email_b = f"{uuid.uuid4()}@example.com"
    _register_and_login(client_b, email_b)
    tenant_b = client_b.post("/orgs", json={"name": "WP15 tenant B"}).json()["id"]

    # Wrong tenant_id in the path -- RLS must hide the row even though the
    # attachment id itself is real and correctly guessed.
    resp = client_b.get(f"/orgs/{tenant_b}/attachments/{attach_a['id']}/download")
    assert resp.status_code == 404
