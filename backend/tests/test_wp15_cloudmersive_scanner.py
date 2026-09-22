"""WP15 Phase 2: real Cloudmersive Virus Scan API integration. Separate
from test_wp15_evidence_attachments.py (which forces the scanner to
"unavailable" for determinism) -- these tests make real network calls to
Cloudmersive and are skipped outright when BGP_CLOUDMERSIVE_API_KEY isn't
configured, same shape as the Postgres-availability skip every other live
test file in this project uses.

Uses the EICAR test string -- the industry-standard, universally-recognised
"this is not a real virus" payload every antivirus engine (Cloudmersive
included) is designed to flag, specifically so integrations like this one
can be tested without possessing or transmitting actual malware."""

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

pytestmark = [
    pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app not configured"),
    pytest.mark.skipif(not settings.cloudmersive_api_key, reason="BGP_CLOUDMERSIVE_API_KEY not configured"),
]

# Standard EICAR antivirus test string -- not malware, every AV engine is
# built to detect it as a positive test signal.
EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


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


def test_a_harmless_file_scans_clean_and_becomes_downloadable(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login(api_client, email)
    tenant_id = api_client.post("/orgs", json={"name": "WP15 scanner org 1"}).json()["id"]
    proj = _seed_project(api_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]

    upload = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("note.txt", io.BytesIO(b"a perfectly ordinary evidence note"), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["scan_status"] == "clean"
    assert body["status"] == "active"

    download = api_client.get(f"/orgs/{tenant_id}/attachments/{body['id']}/download")
    assert download.status_code == 200
    assert download.content == b"a perfectly ordinary evidence note"


def test_the_eicar_test_file_is_detected_and_quarantined(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _register_and_login(api_client, email)
    tenant_id = api_client.post("/orgs", json={"name": "WP15 scanner org 2"}).json()["id"]
    proj = _seed_project(api_client, tenant_id)
    item_id = proj["evidence_items"][0]["id"]

    upload = api_client.post(
        f"/orgs/{tenant_id}/evidence/{item_id}/attachments",
        files={"file": ("eicar.txt", io.BytesIO(EICAR.encode("ascii")), "text/plain")},
    )
    assert upload.status_code == 422, upload.text

    listing = api_client.get(f"/orgs/{tenant_id}/evidence/{item_id}/attachments").json()
    assert len(listing) == 1
    assert listing[0]["scan_status"] == "infected"
    assert listing[0]["status"] == "rejected"

    download = api_client.get(f"/orgs/{tenant_id}/attachments/{listing[0]['id']}/download")
    assert download.status_code == 423
