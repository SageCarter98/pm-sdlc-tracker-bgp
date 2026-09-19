from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import PREAUTH_SESSION_COOKIE, SESSION_COOKIE, get_current_user, get_session_mfa_verified
from app.models import MfaRecoveryCode, User
from app.security import (
    PENDING_MFA_MAX_AGE_SECONDS,
    create_session_token,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    generate_recovery_codes,
    hash_recovery_code,
    new_totp_secret,
    read_preauth_token,
    totp_provisioning_uri,
    verify_totp,
)
from app.security_log import log_security_event

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


class EnrollOut(BaseModel):
    provisioning_uri: str


class VerifyRequest(BaseModel):
    code: str


class VerifyOut(BaseModel):
    enabled: bool
    recovery_codes: list[str]


class RecoverRequest(BaseModel):
    email: str
    recovery_code: str


class LoginVerifyRequest(BaseModel):
    code: str


class LoginVerifyOut(BaseModel):
    id: str
    email: str
    mfa_enabled: bool


@router.post("/enroll", response_model=EnrollOut)
def enroll(
    user: User = Depends(get_current_user),
    mfa_verified: bool = Depends(get_session_mfa_verified),
    db: Session = Depends(get_db),
) -> EnrollOut:
    """REQ-002: accessible MFA setup. Generates a fresh secret each call
    (not yet enabled) so a user can retry scanning without side effects.
    REQ-045: only the encrypted form (app.security.encrypt_mfa_secret) is
    ever persisted -- the plaintext seed lives only in this function's
    local variable and the one-time provisioning URI response.

    BGP-F01 fix: if the account already has an enrolled factor, replacing it
    requires THIS session to have already passed a second-factor check
    (`mfa_verified`) -- a password-only session can no longer overwrite an
    existing enrolled factor. First-time enrolment (nothing to replace yet)
    still only needs an authenticated, password-verified session.

    BGP-F01 follow-up fix: the proposed secret is staged in
    `pending_mfa_secret`/`pending_mfa_created_at`, NOT written into
    `mfa_secret`/`mfa_enabled` -- so an already-enrolled account keeps its
    working factor (and stays `mfa_enabled=True`) for the entire replacement
    window. Calling this again before verifying just overwrites the pending
    secret (fine -- it hasn't taken effect yet); it can never touch the
    active factor. Only verify() promotes a pending secret to active."""
    if user.mfa_enabled and not mfa_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Re-verify your current second factor (or use account recovery) before replacing it",
        )
    plaintext_secret = new_totp_secret()
    user.pending_mfa_secret = encrypt_mfa_secret(plaintext_secret)
    user.pending_mfa_created_at = datetime.now(timezone.utc)
    db.commit()
    return EnrollOut(provisioning_uri=totp_provisioning_uri(plaintext_secret, user.email))


@router.post("/verify", response_model=VerifyOut)
def verify(
    payload: VerifyRequest, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> VerifyOut:
    """BGP-F01 fix: on success this both activates the new factor AND bumps
    `token_version`, invalidating every other previously-issued session for
    this user (a stale session from before a factor replacement must not
    keep being treated as MFA-satisfying). The CALLING session is kept
    usable by reissuing its cookie here with the new token_version and
    `mfa_verified=True` -- completing a second-factor check is exactly the
    action that should leave a session MFA-satisfying.

    BGP-F01 follow-up fix: verifies against `pending_mfa_secret` (the
    proposed replacement from enroll()), never the still-active
    `mfa_secret` -- so success is exactly what atomically promotes the
    pending secret to active. An expired pending secret (older than
    PENDING_MFA_MAX_AGE_SECONDS) is cleared and rejected here rather than
    silently accepted, so an abandoned replacement cannot be redeemed long
    after the fact; the active factor was never touched by enroll() in
    either case."""
    if user.pending_mfa_secret is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No MFA enrolment in progress -- call /auth/mfa/enroll first")
    pending_created_at = user.pending_mfa_created_at
    if pending_created_at is not None and pending_created_at.tzinfo is None:
        pending_created_at = pending_created_at.replace(tzinfo=timezone.utc)
    if pending_created_at is None or (datetime.now(timezone.utc) - pending_created_at).total_seconds() > PENDING_MFA_MAX_AGE_SECONDS:
        user.pending_mfa_secret = None
        user.pending_mfa_created_at = None
        log_security_event(db, "mfa_enrolment_expired", user_id=user.id)
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "MFA enrolment expired -- call /auth/mfa/enroll again")
    if not verify_totp(decrypt_mfa_secret(user.pending_mfa_secret), payload.code):
        log_security_event(db, "mfa_verify_failed", user_id=user.id)
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid MFA code")
    user.mfa_secret = user.pending_mfa_secret
    user.mfa_enabled = True
    user.pending_mfa_secret = None
    user.pending_mfa_created_at = None
    user.token_version += 1
    db.query(MfaRecoveryCode).filter(MfaRecoveryCode.user_id == user.id).delete()
    codes = generate_recovery_codes()
    for code in codes:
        db.add(MfaRecoveryCode(user_id=user.id, code_hash=hash_recovery_code(code)))
    log_security_event(db, "mfa_enabled", user_id=user.id)
    db.commit()
    db.refresh(user)
    token = create_session_token(user.id, user.token_version, mfa_verified=True)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return VerifyOut(enabled=True, recovery_codes=codes)


@router.post("/login-verify", response_model=LoginVerifyOut)
def login_verify(
    payload: LoginVerifyRequest,
    response: Response,
    db: Session = Depends(get_db),
    bgp_preauth: str | None = Cookie(default=None),
) -> LoginVerifyOut:
    """BGP-F01 fix: the other half of the corrected login flow -- POST
    /auth/login never issues a full `bgp_session` cookie for an MFA-enabled
    account by itself any more; this endpoint is the only place that does,
    and only after checking the second factor against the pre-auth cookie
    /auth/login set. A password-only caller who never passes a valid code
    here never gets a session that satisfies require_mfa."""
    if bgp_preauth is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No MFA login in progress -- log in with your password first")
    preauth = read_preauth_token(bgp_preauth)
    if preauth is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA login expired or invalid -- log in again")
    user = db.get(User, preauth.get("user_id"))
    if user is None or user.token_version != preauth.get("tv") or not user.mfa_enabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA login expired or invalid -- log in again")
    if not user.mfa_secret or not verify_totp(decrypt_mfa_secret(user.mfa_secret), payload.code):
        log_security_event(db, "mfa_verify_failed", user_id=user.id)
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid MFA code")

    response.delete_cookie(PREAUTH_SESSION_COOKIE)
    token = create_session_token(user.id, user.token_version, mfa_verified=True)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    log_security_event(db, "login_success", user_id=user.id, detail={"mfa": True})
    db.commit()
    return LoginVerifyOut(id=user.id, email=user.email, mfa_enabled=user.mfa_enabled)


@router.post("/recover")
def recover(payload: RecoverRequest, db: Session = Depends(get_db)) -> dict:
    """REQ-002: verified recovery without elevating rights -- a spent
    recovery code disables MFA and forces re-enrolment; it never grants
    approval authority by itself.

    BGP-F01 fix: also bumps `token_version`, so any session token issued
    before this recovery (on any device) stops being accepted the moment it
    is next presented -- 'invalidate affected sessions after... recovery'."""
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid recovery attempt")
    code_hash = hash_recovery_code(payload.recovery_code)
    record = (
        db.query(MfaRecoveryCode)
        .filter(MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.code_hash == code_hash, MfaRecoveryCode.used_at.is_(None))
        .one_or_none()
    )
    if record is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid recovery attempt")
    record.used_at = datetime.now(timezone.utc)
    user.mfa_enabled = False
    user.mfa_secret = None
    # BGP-F01 follow-up: a recovery clears any in-flight replacement too --
    # a pending secret from before this recovery must not remain redeemable
    # against an account that just had its factor reset out from under it.
    user.pending_mfa_secret = None
    user.pending_mfa_created_at = None
    user.token_version += 1
    log_security_event(db, "mfa_recovery_used", user_id=user.id)
    db.commit()
    return {"mfa_enabled": False, "message": "MFA reset. Re-enrolment is required before approving again."}
