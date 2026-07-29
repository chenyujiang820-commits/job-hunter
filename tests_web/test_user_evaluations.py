import tempfile
import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import Job, User
from server.services.evaluation import SearchTemplateInput, SearchTemplateService, EvaluationService
from server.settings import Settings


class UserEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/evaluation.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user_a = User(id=str(uuid4()), username="alice", password_hash="hash", role="user")
        self.user_b = User(id=str(uuid4()), username="bob", password_hash="hash", role="user")
        self.job = Job(
            id=str(uuid4()), source="boss", external_job_id="job-1", title="物联网产品经理",
            company="示例科技", location="丽水", salary={"min": 8, "max": 12},
            description="负责物联网硬件产品规划，接受长期驻场风险评估",
        )
        self.db.add_all([self.user_a, self.user_b, self.job])
        self.db.commit()
        self.templates = SearchTemplateService(self.db)
        self.evaluations = EvaluationService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_two_users_get_private_scores_from_one_shared_job(self):
        template_a = self.templates.create(
            self.user_a.id,
            SearchTemplateInput(name="technical", keywords=["物联网"], cities=["丽水"], weights={"keyword": 100}),
        )
        template_b = self.templates.create(
            self.user_b.id,
            SearchTemplateInput(name="excluded", keywords=["销售"], cities=["杭州"], hard_exclusions=["物联网"]),
        )

        result_a = self.evaluations.evaluate_for_user(self.user_a.id, [self.job.id], template_a.id)
        result_b = self.evaluations.evaluate_for_user(self.user_b.id, [self.job.id], template_b.id)

        self.assertEqual(len(result_a), 1)
        self.assertGreater(result_a[0].score, 0)
        self.assertEqual(result_b[0].decision, "excluded")
        self.assertEqual(result_a[0].flags, ["long_term_onsite"])
        self.assertNotEqual(result_a[0].user_id, result_b[0].user_id)


if __name__ == "__main__":
    unittest.main()
