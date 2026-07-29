import tempfile
import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import Job, SearchTemplate, User
from server.services.material_batches import MaterialBatchService
from server.settings import Settings


class MaterialPermissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/permissions.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user_a = User(id=str(uuid4()), username="alice", password_hash="hash", role="user")
        self.user_b = User(id=str(uuid4()), username="bob", password_hash="hash", role="user")
        self.job = Job(id=str(uuid4()), source="boss", external_job_id="job", title="产品经理", company="公司")
        self.template = SearchTemplate(id=str(uuid4()), user_id=self.user_a.id, name="default", data={})
        self.db.add_all([self.user_a, self.user_b, self.job, self.template])
        self.db.commit()
        self.service = MaterialBatchService(self.db, object())

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_user_cannot_create_batch_with_another_users_template(self):
        with self.assertRaises(ValueError):
            self.service.create(self.user_b.id, [self.job.id], self.template.id)


if __name__ == "__main__":
    unittest.main()
