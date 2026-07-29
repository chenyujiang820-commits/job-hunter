"""Invite registration and session endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import Invite, User, utc_now
from server.security.passwords import hash_password, verify_password
from server.security.sessions import (
    SESSION_COOKIE,
    SESSION_DAYS,
    issue_session,
    revoke_session,
    user_for_token,
)
from server.security.tokens import hash_token, is_expired


router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterPayload(BaseModel):
    invite: str = Field(min_length=8)
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=256)


class LoginPayload(BaseModel):
    username: str
    password: str


def user_view(user: User) -> dict[str, str]:
    return {"id": user.id, "username": user.username, "role": user.role, "status": user.status}


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload, response: Response, db: Session = Depends(get_db)):
    invite = db.scalars(
        select(Invite).where(Invite.token_hash == hash_token(payload.invite))
    ).first()
    if invite is None or invite.used_at is not None or is_expired(invite.expires_at):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invalid invite")
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username exists")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role="user",
        status="active",
    )
    invite.used_at = utc_now()
    db.add(user)
    try:
        db.flush()
        token = issue_session(db, user.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="registration conflict") from exc
    set_session_cookie(response, token)
    return user_view(user)


@router.post("/login")
def login(payload: LoginPayload, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user disabled")
    token = issue_session(db, user.id)
    db.commit()
    set_session_cookie(response, token)
    return user_view(user)


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    user = user_for_token(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
    return user_view(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    revoke_session(db, request.cookies.get(SESSION_COOKIE))
    db.commit()
    response.delete_cookie(SESSION_COOKIE)
