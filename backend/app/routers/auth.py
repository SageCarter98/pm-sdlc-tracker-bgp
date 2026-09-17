from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import SESSION_COOKIE, get_current_user
from app.models import SecurityLogEvent, User
from app.security import create_session_token, hash_password, verify_password
from app.security_log import log_security_event

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    mfa_enabled: bool

    model_config = {"from_attributes": True}


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """REQ-001: register verified users. Email verification delivery is out
    of scope for this prototype (no mail infra yet) -- `verified` starts
    False and nothing here elevates it; that gap is tracked, not hidden."""
    if db.query(User).filter(User.email == payload.email).one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    log_security_event(db, "register", user_id=user.id, detail={"email": user.email})
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    """WP12/REQ-047: both outcomes are logged -- a failed attempt against a
    real email records that user_id (so the account holder can see
    someone tried), a failed attempt against an unknown email records
    user_id=None (there is no account to attribute it to, and this must
    never reveal whether the email exists via a different log shape)."""
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        log_security_event(db, "login_failure", user_id=user.id if user else None, detail={"email": payload.email})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_session_token(user.id)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    log_security_event(db, "login_success", user_id=user.id)
    db.commit()
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


class SecurityLogEventOut(BaseModel):
    event_type: str
    detail: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/security-log", response_model=list[SecurityLogEventOut])
def my_security_log(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SecurityLogEvent]:
    """REQ-031/047: own-data security history. Self-only in this pass --
    see SecurityLogEvent's docstring in app/models.py for why there is no
    tenant-administrator cross-user view here yet."""
    return (
        db.query(SecurityLogEvent)
        .filter(SecurityLogEvent.user_id == user.id)
        .order_by(SecurityLogEvent.created_at.desc())
        .limit(100)
        .all()
    )
