from tests.conftest import register_and_login


def test_register_then_login(client):
    resp = client.post("/auth/register", json={"email": "a@tenant-a.example", "password": "correct horse battery staple"})
    assert resp.status_code == 201
    resp = client.post("/auth/login", json={"email": "a@tenant-a.example", "password": "correct horse battery staple"})
    assert resp.status_code == 200
    assert "bgp_session" in resp.cookies


def test_duplicate_registration_rejected(client):
    client.post("/auth/register", json={"email": "dup@tenant-a.example", "password": "correct horse battery staple"})
    resp = client.post("/auth/register", json={"email": "dup@tenant-a.example", "password": "another password"})
    assert resp.status_code == 409


def test_wrong_password_rejected(client):
    client.post("/auth/register", json={"email": "wp@tenant-a.example", "password": "correct horse battery staple"})
    resp = client.post("/auth/login", json={"email": "wp@tenant-a.example", "password": "wrong"})
    assert resp.status_code == 401


def test_creator_becomes_tenant_administrator(client):
    register_and_login(client, "founder@tenant-a.example")
    resp = client.post("/orgs", json={"name": "Aldergrove Community Trust"})
    assert resp.status_code == 201
    tenant_id = resp.json()["id"]

    membership = client.get(f"/orgs/{tenant_id}/me")
    assert membership.status_code == 200
    assert membership.json()["role"] == "tenant_administrator"


def test_unrelated_user_denied_membership_of_someone_elses_org(client):
    """TST-001/TST-003: a verified member reaches only their organisation;
    an unrelated account is denied."""
    register_and_login(client, "founder@tenant-a.example")
    tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]

    register_and_login(client, "outsider@tenant-b.example")
    resp = client.get(f"/orgs/{tenant_id}/me")
    assert resp.status_code == 403


def test_forged_tenant_id_in_url_cannot_grant_access(client):
    """TST-003: changing the tenant reference in the request cannot grant
    another tenant -- membership is re-verified server-side every time."""
    register_and_login(client, "founder@tenant-a.example")
    real_tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]

    register_and_login(client, "founder@tenant-b.example")
    other_tenant_id = client.post("/orgs", json={"name": "Birchwood"}).json()["id"]

    resp = client.get(f"/orgs/{real_tenant_id}/me")
    assert resp.status_code == 403
    resp = client.get(f"/orgs/{other_tenant_id}/me")
    assert resp.status_code == 200


def test_invitation_accept_creates_membership_with_invited_role(client):
    """TST-038: invited user reaches the intended project after sign-in."""
    register_and_login(client, "admin@tenant-a.example")
    tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]

    invite = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "contributor@tenant-a.example", "role": "contributor"}
    )
    assert invite.status_code == 201
    token = invite.json()["token"]

    register_and_login(client, "contributor@tenant-a.example")
    accept = client.post("/invitations/accept", json={"token": token})
    assert accept.status_code == 200
    assert accept.json() == {"tenant_id": tenant_id, "role": "contributor"}


def test_invitation_cannot_be_accepted_by_wrong_email(client):
    register_and_login(client, "admin@tenant-a.example")
    tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]
    token = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "contributor@tenant-a.example", "role": "contributor"}
    ).json()["token"]

    register_and_login(client, "someone-else@tenant-a.example")
    resp = client.post("/invitations/accept", json={"token": token})
    assert resp.status_code == 403


def test_non_admin_cannot_issue_invitations(client):
    register_and_login(client, "admin@tenant-a.example")
    tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]
    token = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "contributor@tenant-a.example", "role": "contributor"}
    ).json()["token"]

    register_and_login(client, "contributor@tenant-a.example")
    client.post("/invitations/accept", json={"token": token})

    resp = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "another@tenant-a.example", "role": "contributor"}
    )
    assert resp.status_code == 403


def test_approver_without_mfa_is_blocked(client):
    """TST-002: an approver without MFA cannot submit."""
    register_and_login(client, "admin@tenant-a.example")
    tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]
    token = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "approver@tenant-a.example", "role": "approver"}
    ).json()["token"]

    register_and_login(client, "approver@tenant-a.example")
    client.post("/invitations/accept", json={"token": token})

    resp = client.get(f"/orgs/{tenant_id}/approval-gate-check")
    assert resp.status_code == 403


def test_approver_with_verified_mfa_is_allowed(client):
    register_and_login(client, "admin@tenant-a.example")
    tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]
    token = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "approver@tenant-a.example", "role": "approver"}
    ).json()["token"]

    register_and_login(client, "approver@tenant-a.example")
    client.post("/invitations/accept", json={"token": token})

    enroll = client.post("/auth/mfa/enroll")
    import pyotp

    secret = pyotp.parse_uri(enroll.json()["provisioning_uri"]).secret
    code = pyotp.TOTP(secret).now()
    verify = client.post("/auth/mfa/verify", json={"code": code})
    assert verify.status_code == 200
    recovery_codes = verify.json()["recovery_codes"]
    assert len(recovery_codes) == 8

    resp = client.get(f"/orgs/{tenant_id}/approval-gate-check")
    assert resp.status_code == 200


def test_mfa_recovery_disables_mfa_and_requires_reenrolment(client):
    """TST-002: recovery restores access only after identity checks and
    forces MFA re-enrolment -- it must not silently keep approval rights."""
    register_and_login(client, "admin@tenant-a.example")
    tenant_id = client.post("/orgs", json={"name": "Aldergrove"}).json()["id"]
    token = client.post(
        f"/orgs/{tenant_id}/invitations", json={"email": "approver@tenant-a.example", "role": "approver"}
    ).json()["token"]

    register_and_login(client, "approver@tenant-a.example")
    client.post("/invitations/accept", json={"token": token})
    enroll = client.post("/auth/mfa/enroll")

    import pyotp

    secret = pyotp.parse_uri(enroll.json()["provisioning_uri"]).secret
    verify = client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()})
    recovery_code = verify.json()["recovery_codes"][0]

    recover = client.post("/auth/mfa/recover", json={"email": "approver@tenant-a.example", "recovery_code": recovery_code})
    assert recover.status_code == 200
    assert recover.json()["mfa_enabled"] is False

    resp = client.get(f"/orgs/{tenant_id}/approval-gate-check")
    assert resp.status_code == 403

    reuse = client.post("/auth/mfa/recover", json={"email": "approver@tenant-a.example", "recovery_code": recovery_code})
    assert reuse.status_code == 401
