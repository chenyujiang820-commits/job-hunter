import tempfile
import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import User
from server.repositories.tenant import JobRepository
from server.settings import Settings


class SharedJobRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(Settings(database_url=f"sqlite:///{self.temp.name}/jobs.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id=str(uuid4()), username="alice", password_hash="hash", role="user"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_upsert_uses_source_and_external_id_as_public_identity(self):
        repository = JobRepository(self.db)
        first = repository.upsert_public_job({
            "source": "boss", "id": "same", "title": "产品经理", "location": "丽水"
        })
        second = repository.upsert_public_job({
            "source": "boss", "id": "same", "title": "高级产品经理", "location": "丽水"
        })
        self.db.commit()

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.title, "高级产品经理")


if __name__ == "__main__":
    unittest.main()
