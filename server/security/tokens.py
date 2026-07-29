"""Hashing and expiry helpers for one-time and session tokens."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= datetime.now(timezone.utc)
