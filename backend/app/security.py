import hashlib
import secrets

import pyotp
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# WP01/WP03 prototype signing key. Not a production secret -- rotation and
# secure storage are DEC11/REQ-045, not settled here.
_SESSION_SERIALIZER = URLSafeTimedSerializer(secret_key="local-synthetic-prototype-key")
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_session_token(user_id: str) -> str:
    return _SESSION_SERIALIZER.dumps({"user_id": user_id})


def read_session_token(token: str) -> str | None:
    try:
        data = _SESSION_SERIALIZER.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("user_id")


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="Build Governance Platform")


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [secrets.token_hex(5) for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    # Recovery codes are single-use, high-entropy tokens, not passwords typed
    # repeatedly -- a fast salted hash is adequate and avoids bcrypt's 72-byte
    # input truncation surprises for this local prototype.
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
