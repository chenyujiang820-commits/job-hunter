import hashlib
import tempfile
import unittest
from io import BytesIO
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import CandidateProfile, Job, SearchTemplate, User
from server.services.evaluation import EvaluationService, SearchTemplateInput, SearchTemplateService
from server.services.material_batches import MaterialBatchService
from server.settings import Settings


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, owner_id, content, content_type, filename):
        data = content.read()
        key = f"users/{owner_id}/materials/{uuid4()}-{filename}"
        self.objects[key] = data
        return {"object_key": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class EndToEndPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/pilot.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.alice = User(id=str(uuid4()), username="alice", password_hash="hash", role="user")
        self.bob = User(id=str(uuid4()), username="bob", password_hash="hash", role="user")
        self.job = Job(
            id=str(uuid4()), source="boss", external_job_id="shared-job", title="物联网产品经理",
            company="共享科技", location="丽水", salary={"min": 8, "max": 12},
            description="物联网硬件产品规划",
        )
        self.db.add_all([
            self.alice,
            self.bob,
            self.job,
            CandidateProfile(user_id=self.alice.id, version=1, status="confirmed", data={"name": "Alice"}),
            CandidateProfile(user_id=self.bob.id, version=1, status="confirmed", data={"name": "Bob"}),
        ])
        self.db.commit()
        self.templates = SearchTemplateService(self.db)
        self.evaluations = EvaluationService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_two_user_offline_workflow_keeps_profile_scores_and_materials_private(self):
        alice_template = self.templates.create(
            self.alice.id,
            SearchTemplateInput(name="Alice template", keywords=["物联网"], cities=["丽水"]),
        )
        bob_template = self.templates.create(
            self.bob.id,
            SearchTemplateInput(name="Bob template", keywords=["销售"], cities=["杭州"], hard_exclusions=["物联网"]),
        )
        alice_eval = self.evaluations.evaluate_for_user(self.alice.id, [self.job.id], alice_template.id)[0]
        bob_eval = self.evaluations.evaluate_for_user(self.bob.id, [self.job.id], bob_template.id)[0]
        self.assertNotEqual(alice_eval.id, bob_eval.id)
        self.assertEqual(self.evaluations.list_for_user(self.alice.id), [alice_eval])
        self.assertEqual(self.evaluations.list_for_user(self.bob.id), [bob_eval])

        service = MaterialBatchService(
            self.db,
            FakeStorage(),
            workflow_fn=lambda job, profile: {
                "resume": f"# {profile['name']} / {job['title']}",
                "cover": "# 求职信",
                "fit": {},
                "review": {},
            },
        )
        batch = service.create(self.alice.id, [self.job.id], alice_template.id)
        service.run_draft(batch.id)
        draft = service.list_drafts(self.alice.id, batch.id)[0]

        self.assertIn("Alice", draft.resume_text)
        self.assertEqual(service.list_drafts(self.bob.id, batch.id), [])
        with self.assertRaises(ValueError):
            service.review(self.bob.id, draft.id, "approved")


if __name__ == "__main__":
    unittest.main()
