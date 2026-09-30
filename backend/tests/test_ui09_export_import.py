"""UI09 (docs/DEFECT_REGISTER.md IPA02, FE-067..072): the /ui counterpart to
test_export_import.py's JSON API. Before this, export/import stayed API-only
-- no /ui page existed at all. Same live-Postgres requirement as
test_wp13_webapp_new_pages.py/test_ipa02_membership_settings_ui.py -- these
routes go through the RLS-scoped get_db the SQLite `client` fixture doesn't
provide."""

import json
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


def _register_and_login_ui(client, email, password="correct horse battery staple"):
    resp = client.post(
        "/ui/register",
        data={"email": email, "password": password, "confirm_password": password},
    )
    assert resp.status_code in (200, 303), resp.text
    return resp


@pytest.fixture()
def ui_client():
    from fastapi.testclient import TestClient

    from app.main import app

    assert app.dependency_overrides == {}, "this test needs the REAL Postgres get_db, not the SQLite fixture"
    return TestClient(app, follow_redirects=True)


def _invite_and_accept_ui(admin_client, tenant_id, email, role="contributor"):
    from fastapi.testclient import TestClient

    from app.main import app

    invite = admin_client.post(f"/orgs/{tenant_id}/invitations", json={"email": email, "role": role}).json()
    member_client = TestClient(app, follow_redirects=True)
    _register_and_login_ui(member_client, email)
    accept = member_client.post("/invitations/accept", json={"token": invite["token"]})
    assert accept.status_code == 200, accept.text
    return member_client


def test_export_import_page_lists_a_created_export_and_offers_download(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI09 org 1"}).json()["id"]

    resp = ui_client.post(f"/ui/orgs/{tenant_id}/export-import/exports")
    assert resp.status_code == 200
    assert "Export created." in resp.text

    page = ui_client.get(f"/ui/orgs/{tenant_id}/export-import")
    assert page.status_code == 200
    assert f"/ui/orgs/{tenant_id}/export-import/exports/" in page.text
    assert "Download JSON" in page.text

    job_id = ui_client.get(f"/orgs/{tenant_id}/exports").json()[0]["id"]
    download = ui_client.get(f"/ui/orgs/{tenant_id}/export-import/exports/{job_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/json")
    assert f'filename="bgp-export-{tenant_id}-{job_id}.json"' in download.headers["content-disposition"]
    body = json.loads(download.text)
    assert body["manifest"]["source_tenant_id"] == tenant_id


def test_non_admin_member_sees_export_history_but_not_the_import_form(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI09 org 2"}).json()["id"]
    ui_client.post(f"/ui/orgs/{tenant_id}/export-import/exports")

    member_email = f"{uuid.uuid4()}@example.com"
    member_client = _invite_and_accept_ui(ui_client, tenant_id, member_email)

    page = member_client.get(f"/ui/orgs/{tenant_id}/export-import")
    assert page.status_code == 200
    # A non-admin member can still see and download their own tenant's export history (REQ-031).
    assert "Download JSON" in page.text
    # But the admin-only import journey is not shown to them at all.
    assert "Import an archive" not in page.text
    assert "archive_file" not in page.text


def test_admin_can_validate_and_commit_an_import_via_the_page(ui_client):
    from tests.test_projects import _create_org_as_admin, _create_project, _publish_standard_template

    tenant_a = _create_org_as_admin(ui_client, f"{uuid.uuid4()}@example.com")
    version_id, _ = _publish_standard_template(ui_client, tenant_a)
    _create_project(ui_client, tenant_a, version_id, "Standard-High")
    archive = ui_client.post(f"/orgs/{tenant_a}/exports").json()["archive"]

    tenant_b = ui_client.post("/orgs", json={"name": "UI09 org 3"}).json()["id"]

    validate_resp = ui_client.post(
        f"/ui/orgs/{tenant_b}/export-import/imports/validate",
        data={"archive_text": json.dumps(archive)},
    )
    assert validate_resp.status_code == 200
    assert "Archive validated" in validate_resp.text
    assert "Validation report" in validate_resp.text

    job_id = ui_client.get(f"/orgs/{tenant_b}/imports").json()[0]["id"]
    assert f"/ui/orgs/{tenant_b}/export-import/imports/{job_id}/commit" in validate_resp.text

    commit_resp = ui_client.post(f"/ui/orgs/{tenant_b}/export-import/imports/{job_id}/commit")
    assert commit_resp.status_code == 200
    assert "Import committed" in commit_resp.text
    assert "Commit / reconciliation report" in commit_resp.text

    imports = ui_client.get(f"/orgs/{tenant_b}/imports").json()
    assert imports[0]["status"] == "committed"
    assert imports[0]["commit_report"]["counts"]["projects"] == 1


def test_admin_can_validate_via_an_uploaded_file(ui_client):
    from tests.test_projects import _create_org_as_admin

    tenant_a = _create_org_as_admin(ui_client, f"{uuid.uuid4()}@example.com")
    archive = ui_client.post(f"/orgs/{tenant_a}/exports").json()["archive"]

    tenant_b = ui_client.post("/orgs", json={"name": "UI09 org 4"}).json()["id"]
    resp = ui_client.post(
        f"/ui/orgs/{tenant_b}/export-import/imports/validate",
        files={"archive_file": ("archive.json", json.dumps(archive).encode(), "application/json")},
        data={"archive_text": ""},
    )
    assert resp.status_code == 200
    assert "Archive validated" in resp.text


def test_malformed_json_paste_shows_an_honest_error(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI09 org 5"}).json()["id"]

    resp = ui_client.post(
        f"/ui/orgs/{tenant_id}/export-import/imports/validate",
        data={"archive_text": "{not valid json"},
    )
    assert resp.status_code == 200
    assert "Not valid JSON" in resp.text


def test_non_admin_cannot_validate_or_commit_an_import(ui_client):
    admin_email = f"{uuid.uuid4()}@example.com"
    _register_and_login_ui(ui_client, admin_email)
    tenant_id = ui_client.post("/orgs", json={"name": "UI09 org 6"}).json()["id"]
    archive = ui_client.post(f"/orgs/{tenant_id}/exports").json()["archive"]

    member_email = f"{uuid.uuid4()}@example.com"
    member_client = _invite_and_accept_ui(ui_client, tenant_id, member_email)

    resp = member_client.post(
        f"/ui/orgs/{tenant_id}/export-import/imports/validate",
        data={"archive_text": json.dumps(archive)},
    )
    assert resp.status_code == 200
    assert "Role does not permit this operation" in resp.text
    assert ui_client.get(f"/orgs/{tenant_id}/imports").json() == []

    resp = member_client.post(f"/ui/orgs/{tenant_id}/export-import/imports/does-not-exist/commit")
    assert resp.status_code == 200
    assert "Role does not permit this operation" in resp.text
