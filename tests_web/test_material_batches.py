import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import Job, SearchTemplate, User
from server.services.material_batches import MaterialBatchService
from server.settings import Settings


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, owner_id, content, content_type, filename):
        data = content.read()
        key = f"users/{owner_id}/materials/{filename}"
        self.objects[key] = data
        return {"object_key": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class MaterialBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/materials.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user_a = User(id=str(uuid4()), username="alice", password_hash="hash", role="user")
        self.user_b = User(id=str(uuid4()), username="bob", password_hash="hash", role="user")
        self.jobs = [
            Job(id=str(uuid4()), source="boss", external_job_id=f"job-{index}", title=f"产品经理 {index}", company="科技公司", location="丽水")
            for index in range(2)
        ]
        self.template = SearchTemplate(id=str(uuid4()), user_id=self.user_a.id, name="default", data={})
        self.db.add_all([self.user_a, self.user_b, *self.jobs, self.template])
        self.db.commit()

        def workflow(job, profile):
            return {
                "fit": {"total_score": 80},
                "resume": f"# {job['title']}\n\n## 个人简介\n{profile.get('name', '候选人')}",
                "cover": f"# 求职信\n\n申请 {job['title']}",
                "review": {"approved": True, "improvements": []},
            }

        def render(resume, cover, output):
            Path(output).write_bytes((resume + "\n" + cover).encode("utf-8"))
            return Path(output)

        def convert(docx, output_dir):
            output = Path(output_dir) / f"{Path(docx).stem}.pdf"
            output.write_bytes(b"pdf")
            return output

        self.storage = FakeStorage()
        self.service = MaterialBatchService(
            self.db,
            self.storage,
            workflow_fn=workflow,
            render_fn=render,
            convert_fn=convert,
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_batch_generates_multiple_drafts_and_requires_individual_approval(self):
        batch = self.service.create(self.user_a.id, [job.id for job in self.jobs], self.template.id)
        self.service.run_draft(batch.id)
        drafts = self.service.list_drafts(self.user_a.id, batch.id)

        self.assertEqual(len(drafts), 2)
        self.assertTrue(all(draft.status == "draft_ready" for draft in drafts))
        with self.assertRaises(ValueError):
            self.service.finalize(self.user_a.id, drafts[0].id)

        self.service.review(self.user_a.id, drafts[0].id, "approved", "已核对")
        files = self.service.finalize(self.user_a.id, drafts[0].id)
        self.assertEqual(len(files), 2)

    def test_failed_child_does_not_cancel_other_drafts_and_other_user_cannot_read(self):
        def failing_workflow(job, profile):
            if job["id"] == "job-0":
                raise RuntimeError("one draft failed")
            return {"resume": "resume", "cover": "cover", "fit": {}, "review": {"approved": True}}

        service = MaterialBatchService(self.db, self.storage, workflow_fn=failing_workflow)
        batch = service.create(self.user_a.id, [job.id for job in self.jobs], self.template.id)
        service.run_draft(batch.id)
        drafts = service.list_drafts(self.user_a.id, batch.id)

        self.assertEqual({draft.status for draft in drafts}, {"failed", "draft_ready"})
        self.assertEqual(service.list_drafts(self.user_b.id, batch.id), [])


if __name__ == "__main__":
    unittest.main()
