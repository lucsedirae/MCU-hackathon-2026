"""Database-backed sessions and administrator-provisioned accounts."""

import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from threading import Lock
from time import monotonic
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.database import engine
from app.models import User, LoginSession, now

router = APIRouter(prefix="/api/auth", tags=["Accounts"])


def db():
    with Session(engine) as session:
        yield session


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=16384, r=8, p=1
    ).hex()
    return salt + ":" + digest


def verify(password, encoded):
    salt, expected = encoded.split(":")
    result = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=16384, r=8, p=1
    ).hex()
    return hmac.compare_digest(result, expected)


def public(user):
    return {
        k: getattr(user, k)
        for k in ("id", "email", "name", "admin", "must_change", "active")
    }


def identity(request: Request, session: Session = Depends(db)):
    token = request.cookies.get("cr_session", "")
    login = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not login or login.expires <= now():
        raise HTTPException(401, "Sign in to continue.")
    user = session.get(User, login.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account unavailable.")
    return user


def current(user: User = Depends(identity)):
    if user.must_change:
        raise HTTPException(403, "Change your temporary password first.")
    return user


def administrator(user: User = Depends(current)):
    if not user.admin:
        raise HTTPException(403, "Administrator access required.")
    return user


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class NewUser(Credentials):
    name: str = Field(min_length=1, max_length=120)
    admin: bool = False


class PasswordChange(BaseModel):
    old_password: str = Field(max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


def validate_password(value):
    if len(value) < 8:
        raise HTTPException(422, "Use at least 8 characters for passwords.")


def create_account(payload, session, must_change=True):
    validate_password(payload.password)
    email = payload.email.strip().lower()
    if "@" not in email or not payload.name.strip():
        raise HTTPException(422, "Enter a name and email address.")
    if session.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "That email already has an account.")
    user = User(
        email=email,
        name=payload.name.strip(),
        password=hash_password(payload.password),
        admin=payload.admin,
        must_change=must_change,
    )
    session.add(user)
    session.flush()
    return user


@router.get("/setup")
def setup_status(session: Session = Depends(db)):
    return {"required": session.scalar(select(User.id).limit(1)) is None}


@router.post("/setup")
def setup(payload: NewUser, session: Session = Depends(db)):
    # A database lock makes first-admin creation safe across simultaneous requests.
    session.execute(text("SELECT pg_advisory_xact_lock(73492211)"))
    if session.scalar(select(User.id).limit(1)):
        raise HTTPException(409, "Initial setup has already completed.")
    payload.admin = True
    user = create_account(payload, session, must_change=False)
    session.commit()
    return public(user)


_attempts = {}
_attempt_lock = Lock()


@router.post("/login")
def login(
    payload: Credentials,
    request: Request,
    response: Response,
    session: Session = Depends(db),
):
    address = request.client.host if request.client else "unknown"
    with _attempt_lock:
        cutoff = monotonic() - 300
        for key in list(_attempts):
            _attempts[key] = [t for t in _attempts[key] if t > cutoff]
            if not _attempts[key]:
                del _attempts[key]
        attempts = _attempts.setdefault(address, [])
        if len(attempts) >= 20:
            raise HTTPException(429, "Too many attempts. Try again in five minutes.")
        attempts.append(monotonic())
    user = session.scalar(
        select(User).where(User.email == payload.email.strip().lower())
    )
    if not user or not user.active or not verify(payload.password, user.password):
        raise HTTPException(401, "Incorrect email or password.")
    token = secrets.token_urlsafe(32)
    session.add(
        LoginSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires=now() + timedelta(hours=12),
        )
    )
    session.commit()
    response.set_cookie(
        "cr_session",
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("COOKIE_SECURE") == "true",
        max_age=43200,
        path="/",
    )
    return public(user)


@router.get("/me")
def me(user: User = Depends(identity)):
    return public(user)


@router.post("/password")
def password(
    payload: PasswordChange,
    user: User = Depends(identity),
    session: Session = Depends(db),
):
    if not verify(payload.old_password, user.password):
        raise HTTPException(400, "Current password is incorrect.")
    if payload.old_password == payload.new_password:
        raise HTTPException(400, "Choose a different password.")
    user.password = hash_password(payload.new_password)
    user.must_change = False
    session.query(LoginSession).filter(LoginSession.user_id == user.id).delete()
    session.commit()
    return {"message": "Password changed. Sign in again."}


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(db)):
    digest = hashlib.sha256(request.cookies.get("cr_session", "").encode()).hexdigest()
    session.query(LoginSession).filter(LoginSession.token_hash == digest).delete()
    session.commit()
    response.delete_cookie("cr_session", path="/")
    return {"message": "Signed out."}


@router.get("/users")
def users(user: User = Depends(administrator), session: Session = Depends(db)):
    return [public(u) for u in session.scalars(select(User).order_by(User.name))]


@router.post("/users")
def add_user(
    payload: NewUser,
    user: User = Depends(administrator),
    session: Session = Depends(db),
):
    created = create_account(payload, session)
    session.commit()
    return public(created)


class ResetPassword(BaseModel):
    password: str = Field(min_length=8, max_length=256)


@router.post("/users/{user_id}/reset")
def reset_password(
    user_id: str,
    payload: ResetPassword,
    admin: User = Depends(administrator),
    session: Session = Depends(db),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user.password = hash_password(payload.password)
    user.must_change = True
    session.query(LoginSession).filter(LoginSession.user_id == user.id).delete()
    session.commit()
    return {"message": "Temporary password set; existing sessions revoked."}
