from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import MfaRecoveryCode, User
from app.security import (
    generate_recovery_codes,
    hash_recovery_code,
    new_totp_secret,
    totp_provisioning_uri,
    verify_totp,
)

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


@router.post("/enroll", response_model=EnrollOut)
def enroll(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EnrollOut:
    """REQ-002: accessible MFA setup. Generates a fresh secret each call
    (not yet enabled) so a user can retry scanning without side effects."""
    user.mfa_secret = new_totp_secret()
    user.mfa_enabled = False
    db.commit()
    return EnrollOut(provisioning_uri=totp_provisioning_uri(user.mfa_secret, user.email))


@router.post("/verify", response_model=VerifyOut)
def verify(
    payload: VerifyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> VerifyOut:
    if not user.mfa_secret or not verify_totp(user.mfa_secret, payload.code):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid MFA code")
    user.mfa_enabled = True
    db.query(MfaRecoveryCode).filter(MfaRecoveryCode.user_id == user.id).delete()
    codes = generate_recovery_codes()
    for code in codes:
        db.add(MfaRecoveryCode(user_id=user.id, code_hash=hash_recovery_code(code)))
    db.commit()
    return VerifyOut(enabled=True, recovery_codes=codes)


@router.post("/recover")
def recover(payload: RecoverRequest, db: Session = Depends(get_db)) -> dict:
    """REQ-002: verified recovery without elevating rights -- a spent
    recovery code disables MFA and forces re-enrolment; it never grants
    approval authority by itself."""
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
    db.commit()
    return {"mfa_enabled": False, "message": "MFA reset. Re-enrolment is required before approving again."}
