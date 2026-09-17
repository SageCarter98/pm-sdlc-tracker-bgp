import hashlib
import secrets

import pyotp
from cryptography.fernet import Fernet
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# WP12/REQ-045: loaded from settings.session_secret_key (env-overridable,
# random-per-process default), not a hardcoded literal -- see that
# field's docstring in app/core/config.py for why this changed 2026-09-17
# and what it does and doesn't fix. Rotation and DEC11 key custody remain
# not settled here.
_SESSION_SERIALIZER = URLSafeTimedSerializer(secret_key=settings.session_secret_key)
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12

# WP12/REQ-045: encrypts users.mfa_secret at rest. Fernet is authenticated
# (tampering is detected, not just confidentiality) and self-describes its
# own key version, which matters if/when key rotation is designed later
# (not done here -- rotating this key today would make every existing
# enrolled user's stored secret undecryptable, since there is exactly one
# active key and no re-encryption path; that's a real, named gap, not an
# oversight).
_mfa_fernet = Fernet(settings.mfa_encryption_key.encode("utf-8"))


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


def encrypt_mfa_secret(plaintext_secret: str) -> str:
    """WP12/REQ-045: called once, at enrolment (app/routers/mfa.py) --
    users.mfa_secret stores only this ciphertext, never the plaintext
    TOTP seed."""
    return _mfa_fernet.encrypt(plaintext_secret.encode("utf-8")).decode("utf-8")


def decrypt_mfa_secret(ciphertext: str) -> str:
    """Raises InvalidToken if the ciphertext doesn't match
    settings.mfa_encryption_key -- callers should let that propagate as a
    500, not silently treat a decryption failure as 'no MFA secret', since
    those are different failure modes (misconfiguration vs. never
    enrolled)."""
    return _mfa_fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


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
