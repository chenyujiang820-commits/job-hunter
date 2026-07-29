import tempfile
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from server.app import create_app
from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import User
from server.security.sessions import issue_session
from server.settings import Settings


class AiConsentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        settings = Settings(database_url=f"sqlite:///{self.temp.name}/consent.db")
        self.engine = create_db_engine(settings)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        db = Session(self.engine)
        user = User(
            id=str(uuid4()), username="alice", password_hash="hash", role="user"
        )
        db.add(user)
        self.user_id = user.id
        self.token = issue_session(db, user.id)
        db.commit()
        db.close()

        self.app = create_app(settings)
        self.app.state.session_factory = self.factory
        self.client = TestClient(self.app)
        self.client.cookies.set("session", self.token)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_user_can_grant_and_revoke_ai_consent(self):
        enabled = self.client.post("/api/settings/ai-consent", json={"enabled": True})
        disabled = self.client.post("/api/settings/ai-consent", json={"enabled": False})

        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.json()["enabled"])
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["enabled"])


if __name__ == "__main__":
    unittest.main()
