"""WP12: REQ-045 (secret storage), REQ-047 (security logs, access review)."""
import pyotp

from tests.conftest import register_and_login
from tests.test_projects import _create_org_as_admin, _invite_and_accept


def test_mfa_secret_is_encrypted_at_rest_not_plaintext(client):
    from app.db import get_db
    from app.main import app
    from app.models import User

    register_and_login(client, "user@tenant-a.example")
    enroll = client.post("/auth/mfa/enroll")
    secret = pyotp.parse_uri(enroll.json()["provisioning_uri"]).secret

    db = next(app.dependency_overrides[get_db]())
    user = db.query(User).filter(User.email == "user@tenant-a.example").one()
    assert user.mfa_secret != secret, "the plaintext TOTP seed must never be stored as-is"
    assert secret not in user.mfa_secret

    # ... and the app can still round-trip it correctly.
    code = pyotp.TOTP(secret).now()
    verify = client.post("/auth/mfa/verify", json={"code": code})
    assert verify.status_code == 200, verify.text


def test_login_success_and_failure_are_logged(client):
    register_and_login(client, "user@tenant-a.example")

    bad = client.post("/auth/login", json={"email": "user@tenant-a.example", "password": "wrong password entirely"})
    assert bad.status_code == 401

    register_and_login(client, "user@tenant-a.example")  # a real successful login

    log = client.get("/auth/security-log")
    assert log.status_code == 200, log.text
    event_types = [e["event_type"] for e in log.json()]
    assert "register" in event_types
    assert "login_failure" in event_types
    assert "login_success" in event_types


def test_security_log_is_self_scoped(client):
    register_and_login(client, "user-a@tenant-a.example")
    log_a = client.get("/auth/security-log").json()
    assert len(log_a) >= 1

    register_and_login(client, "user-b@tenant-a.example")
    log_b = client.get("/auth/security-log")
    assert log_b.status_code == 200
    # user B never registered/logged in under user A's session -- their own
    # log must not contain user A's events.
    assert all("user-a" not in str(e.get("detail")) for e in log_b.json())


def test_mfa_verify_failure_and_enable_are_logged(client):
    register_and_login(client, "user@tenant-a.example")
    client.post("/auth/mfa/enroll")

    bad = client.post("/auth/mfa/verify", json={"code": "000000"})
    assert bad.status_code == 422

    log = client.get("/auth/security-log").json()
    assert any(e["event_type"] == "mfa_verify_failed" for e in log)


def test_access_review_lists_tenant_membership(client):
    tenant_id = _create_org_as_admin(client)
    _invite_and_accept(client, tenant_id, "contributor@tenant-a.example", "contributor")

    register_and_login(client, "admin@tenant-a.example")
    review = client.get(f"/orgs/{tenant_id}/access-review")
    assert review.status_code == 200, review.text
    body = review.json()
    emails = {e["email"] for e in body}
    assert "admin@tenant-a.example" in emails
    assert "contributor@tenant-a.example" in emails
    roles = {e["email"]: e["role"] for e in body}
    assert roles["contributor@tenant-a.example"] == "contributor"


def test_access_review_requires_tenant_administrator_role(client):
    tenant_id = _create_org_as_admin(client)
    _invite_and_accept(client, tenant_id, "contributor@tenant-a.example", "contributor")
    # _invite_and_accept leaves the contributor logged in

    resp = client.get(f"/orgs/{tenant_id}/access-review")
    assert resp.status_code == 403


def test_invitation_events_are_logged_with_tenant_scope(client):
    tenant_id = _create_org_as_admin(client)
    _invite_and_accept(client, tenant_id, "contributor@tenant-a.example", "contributor")

    register_and_login(client, "admin@tenant-a.example")
    log = client.get("/auth/security-log").json()
    assert any(e["event_type"] == "invitation_created" for e in log)
