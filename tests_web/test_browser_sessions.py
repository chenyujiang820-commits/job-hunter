import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from server.adapters.browser_connector import BrowserSessionState
from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import User
from server.services.browser_sessions import BrowserSessionService
from server.settings import Settings


class FakeConnector:
    def __init__(self):
        self.started = []
        self.stopped = []

    def start(self, user_id, profile_path):
        self.started.append((user_id, profile_path))
        return BrowserSessionState(status="ready", reason="manual login may be required")

    def stop(self, user_id):
        self.stopped.append(user_id)


class BrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/browser.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user_a = User(id=str(uuid4()), username="alice", password_hash="hash", role="user")
        self.user_b = User(id=str(uuid4()), username="bob", password_hash="hash", role="user")
        self.db.add_all([self.user_a, self.user_b])
        self.db.commit()
        self.connector = FakeConnector()
        self.service = BrowserSessionService(
            self.db,
            Settings(database_url="sqlite:///:memory:", chromium_profile_root=self.temp.name),
            self.connector,
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_each_user_gets_an_independent_profile_and_start_is_idempotent(self):
        first = self.service.start(self.user_a.id)
        second = self.service.start(self.user_a.id)
        other = self.service.start(self.user_b.id)

        self.assertEqual(first.id, second.id)
        self.assertNotEqual(first.profile_path, other.profile_path)
        self.assertTrue(Path(first.profile_path).is_relative_to(Path(self.temp.name).resolve()))
        self.assertEqual(len(self.connector.started), 2)


if __name__ == "__main__":
    unittest.main()
