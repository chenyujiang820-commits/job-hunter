"""Tenant-scoped browser session lifecycle."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.adapters.browser_connector import BrowserConnector
from server.models.entities import BrowserSession
from server.settings import Settings


class BrowserSessionService:
    def __init__(self, db: Session, settings: Settings, connector: BrowserConnector):
        self.db = db
        self.settings = settings
        self.connector = connector
        self.profile_root = Path(settings.chromium_profile_root).resolve()

    def start(self, user_id: str) -> BrowserSession:
        session = self.db.scalar(
            select(BrowserSession).where(
                BrowserSession.user_id == user_id,
                BrowserSession.platform == "boss",
            )
        )
        profile_path = self.profile_root / user_id / "boss"
        if session is not None and session.status in {"ready", "running"}:
            return session
        state = self.connector.start(user_id, str(profile_path))
        if session is None:
            session = BrowserSession(
                user_id=user_id,
                platform="boss",
                profile_path=str(profile_path),
            )
            self.db.add(session)
        session.status = state.status
        self.db.commit()
        return session

    def stop(self, user_id: str) -> BrowserSession | None:
        session = self.db.scalar(
            select(BrowserSession).where(
                BrowserSession.user_id == user_id,
                BrowserSession.platform == "boss",
            )
        )
        self.connector.stop(user_id)
        if session is None:
            return None
        session.status = "stopped"
        self.db.commit()
        return session

    def get(self, user_id: str) -> BrowserSession | None:
        return self.db.scalar(
            select(BrowserSession).where(
                BrowserSession.user_id == user_id,
                BrowserSession.platform == "boss",
            )
        )
