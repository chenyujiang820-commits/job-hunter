import tempfile
import unittest
from uuid import uuid4

from crawlers.access_guard import ManualInterventionRequired
from sqlalchemy.orm import Session

from server.adapters.browser_connector import BrowserSessionState, CollectionResult
from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import SearchTemplate, Task, User
from server.services.browser_sessions import BrowserSessionService
from server.services.job_collection import CollectionTaskService
from server.settings import Settings


class FakeConnector:
    def start(self, user_id, profile_path):
        return BrowserSessionState(status="ready")

    def stop(self, user_id):
        return None

    def collect(self, user_id, query):
        raise ManualInterventionRequired("CAPTCHA", platform="boss")


class CollectionTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/tasks.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(id=str(uuid4()), username="alice", password_hash="hash", role="user")
        self.template = SearchTemplate(
            id=str(uuid4()), user_id=self.user.id, name="boss", data={"keywords": ["产品经理"]}
        )
        self.db.add_all([self.user, self.template])
        self.db.commit()
        settings = Settings(database_url="sqlite:///:memory:", chromium_profile_root=self.temp.name)
        self.sessions = BrowserSessionService(self.db, settings, FakeConnector())
        self.service = CollectionTaskService(self.db, self.sessions, FakeConnector())

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_manual_intervention_is_persisted_as_paused_task(self):
        task = self.service.create(self.user.id, self.template.id)
        result = self.service.run(task.id)

        self.assertEqual(result.status, "paused")
        self.assertEqual(result.error_code, "manual_intervention")
        self.assertIn("暂停人工处理", result.error_message)
        self.assertEqual(self.db.get(Task, task.id).status, "paused")


if __name__ == "__main__":
    unittest.main()
