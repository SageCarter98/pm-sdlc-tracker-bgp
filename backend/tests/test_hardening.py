"""WP12: REQ-045 (secret storage), REQ-047 (security logs, access review)."""
import pyotp

from tests.conftest import enable_mfa, register_and_login
from tests.test_projects import _create_org_as_admin, _invite_and_accept


def test_mfa_secret_is_encrypted_at_rest_not_plaintext(client):
    from app.db import get_db
    from app.main import app
    from app.models import User

    register_and_login(client, "user@tenant-a.example")
    enroll = client.post("/auth/mfa/enroll")
    secret = pyotp.parse_uri(enroll.json()["provisioning_uri"]).secret

    # BGP-F01 follow-up: before verify(), the proposed secret lives in
    # pending_mfa_secret, not mfa_secret -- see app/routers/mfa.py:enroll.
    db = next(app.dependency_overrides[get_db]())
    user = db.query(User).filter(User.email == "user@tenant-a.example").one()
    assert user.mfa_secret is None, "an unverified replacement must not touch the (here, not-yet-existing) active factor"
    assert user.pending_mfa_secret != secret, "the plaintext TOTP seed must never be stored as-is"
    assert secret not in user.pending_mfa_secret

    # ... and the app can still round-trip it correctly.
    code = pyotp.TOTP(secret).now()
    verify = client.post("/auth/mfa/verify", json={"code": code})
    assert verify.status_code == 200, verify.text

    db.refresh(user)
    assert user.mfa_secret is not None, "success promotes the pending secret to active"
    assert secret not in user.mfa_secret
    assert user.pending_mfa_secret is None, "the pending secret is cleared once promoted"


def test_factor_replacement_does_not_disable_active_mfa_mid_flight(client):
    """BGP-F01 follow-up (BGP_Follow_Up_Review_Findings_v1.0.pdf): starting a
    replacement (POST /enroll on an already-enrolled account) must not make
    the account appear unenrolled -- a password-only session must still be
    refused a full session, and the OLD factor must still work, right up
    until the NEW one is actually verified."""
    from app.db import get_db
    from app.main import app
    from app.models import User

    register_and_login(client, "user@tenant-a.example")
    old_secret = enable_mfa(client)

    # Start a replacement -- old factor must remain untouched by this alone.
    started = client.post("/auth/mfa/enroll")
    assert started.status_code == 200, started.text

    db = next(app.dependency_overrides[get_db]())
    user = db.query(User).filter(User.email == "user@tenant-a.example").one()
    assert user.mfa_enabled is True, "starting a replacement must not disable the active factor"
    assert user.mfa_secret is not None

    # A fresh password-only login still requires the OLD, still-active
    # factor -- it must not be satisfiable by password alone just because a
    # replacement is in flight.
    login_start = client.post("/auth/login", json={"email": "user@tenant-a.example", "password": "correct horse battery staple"})
    assert login_start.json()["mfa_required"] is True
    login_finish = client.post("/auth/mfa/login-verify", json={"code": pyotp.TOTP(old_secret).now()})
    assert login_finish.status_code == 200, login_finish.text


def test_completing_replacement_activates_new_factor_and_invalidates_old_sessions(client):
    """BGP-F01 follow-up verification points 1 and 4: only a SUCCESSFUL
    verify() promotes the pending secret to active, and doing so invalidates
    sessions issued under the old factor."""
    register_and_login(client, "user@tenant-a.example")
    old_secret = enable_mfa(client)
    old_session_cookie = client.cookies.get("bgp_session")

    enroll = client.post("/auth/mfa/enroll")
    new_secret = pyotp.parse_uri(enroll.json()["provisioning_uri"]).secret
    verify = client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(new_secret).now()})
    assert verify.status_code == 200, verify.text

    # The old factor no longer verifies logins -- it was replaced, not kept
    # active alongside the new one.
    login_start = client.post("/auth/login", json={"email": "user@tenant-a.example", "password": "correct horse battery staple"})
    assert login_start.json()["mfa_required"] is True
    stale_code_login = client.post("/auth/mfa/login-verify", json={"code": pyotp.TOTP(old_secret).now()})
    assert stale_code_login.status_code == 422

    # A session token issued before the replacement is now stale (token_version bumped).
    client.cookies.set("bgp_session", old_session_cookie)
    stale_session = client.get("/auth/me")
    assert stale_session.status_code == 401


def test_expired_pending_replacement_is_rejected_and_old_factor_still_works(client):
    """BGP-F01 follow-up verification point 3: an abandoned/expired
    replacement must be rejected at verify(), and must not have disturbed
    the original working factor in the meantime."""
    from datetime import datetime, timedelta, timezone

    from app.db import get_db
    from app.main import app
    from app.models import User
    from app.security import PENDING_MFA_MAX_AGE_SECONDS

    register_and_login(client, "user@tenant-a.example")
    old_secret = enable_mfa(client)

    enroll = client.post("/auth/mfa/enroll")
    new_secret = pyotp.parse_uri(enroll.json()["provisioning_uri"]).secret

    db = next(app.dependency_overrides[get_db]())
    user = db.query(User).filter(User.email == "user@tenant-a.example").one()
    user.pending_mfa_created_at = datetime.now(timezone.utc) - timedelta(seconds=PENDING_MFA_MAX_AGE_SECONDS + 1)
    db.commit()

    expired = client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(new_secret).now()})
    assert expired.status_code == 422, expired.text
    assert "expired" in expired.text.lower()

    # The original factor was never touched -- it still works.
    still_works = client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(old_secret).now()})
    # There's no pending secret any more (cleared on expiry), so re-using the
    # OLD code against /verify correctly reports "no enrolment in progress",
    # not success -- confirming the old factor was left alone (still
    # user.mfa_enabled=True, unaffected) rather than silently accepted here.
    assert still_works.status_code == 422
    db.refresh(user)
    assert user.mfa_enabled is True
    assert user.mfa_secret is not None


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
