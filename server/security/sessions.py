"""Opaque server-side session management."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models.entities import SessionRecord, User, utc_now
from server.security.tokens import hash_token, is_expired


SESSION_COOKIE = "session"
SESSION_DAYS = 7


def issue_session(db: Session, user_id: str) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        SessionRecord(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=utc_now() + timedelta(days=SESSION_DAYS),
        )
    )
    return raw_token


def user_for_token(db: Session, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    record = db.scalars(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(raw_token))
    ).first()
    if record is None or record.revoked_at is not None or is_expired(record.expires_at):
        return None
    user = db.get(User, record.user_id)
    if user is None or user.status != "active":
        return None
    return user


def revoke_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    record = db.scalars(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(raw_token))
    ).first()
    if record is not None:
        record.revoked_at = utc_now()
