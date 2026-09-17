import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    """SQLite in-memory DB for the WP03 prototype test suite. The approved
    production target is PostgreSQL with RLS (REQ-007, WP04) -- this fixture
    only exercises application-level logic, not database-enforced isolation."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def enable_mfa(client) -> str:
    """Enrols and verifies TOTP MFA for the CURRENTLY authenticated session
    (BGP-F01: enrolling/replacing a factor requires either no existing
    factor yet, or a session that already passed one -- see
    app/routers/mfa.py's enroll). Returns the base32 secret and caches it on
    the client, keyed by email, so a later login() for the same user can
    complete the login-time second factor without the caller having to
    thread the secret through every call site."""
    enroll = client.post("/auth/mfa/enroll")
    assert enroll.status_code == 200, enroll.text
    secret = pyotp.parse_uri(enroll.json()["provisioning_uri"]).secret
    verify = client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()})
    assert verify.status_code == 200, verify.text
    email = client.get("/auth/me").json()["email"]
    client._mfa_secrets = getattr(client, "_mfa_secrets", {})
    client._mfa_secrets[email] = secret
    return secret


def login(client, email: str, password: str = "correct horse battery staple", mfa_secret: str | None = None):
    """BGP-F01: /auth/login alone no longer returns a full session for an
    MFA-enabled account -- this completes the second step
    (POST /auth/mfa/login-verify) when required, using an explicitly passed
    secret or the one enable_mfa() cached for this email on this client."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    if resp.json().get("mfa_required"):
        secret = mfa_secret or getattr(client, "_mfa_secrets", {}).get(email)
        assert secret is not None, f"{email} requires MFA but no secret is known for it in this test"
        resp = client.post("/auth/mfa/login-verify", json={"code": pyotp.TOTP(secret).now()})
        assert resp.status_code == 200, resp.text
    return resp


def register_and_login(client, email: str, password: str = "correct horse battery staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    return login(client, email, password)
