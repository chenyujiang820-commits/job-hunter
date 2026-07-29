import tempfile
import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import SearchTemplate, User
from server.services.evaluation import SearchTemplateInput, SearchTemplateService
from server.settings import Settings


class SearchTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/templates.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(id=str(uuid4()), username="alice", password_hash="hash", role="user")
        self.db.add(self.user)
        self.db.commit()
        self.service = SearchTemplateService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_template_is_user_owned_and_keeps_custom_filters(self):
        template = self.service.create(
            self.user.id,
            SearchTemplateInput(
                name="产品经理试点",
                keywords=["物联网", "硬件"],
                cities=["丽水"],
                hard_exclusions=["外包"],
                weights={"keyword": 70, "location": 30},
            ),
        )

        self.assertIsInstance(template, SearchTemplate)
        self.assertEqual(template.data["cities"], ["丽水"])
        self.assertEqual(template.data["weights"]["keyword"], 70)
        self.assertEqual(self.service.get(self.user.id, template.id).user_id, self.user.id)


if __name__ == "__main__":
    unittest.main()
