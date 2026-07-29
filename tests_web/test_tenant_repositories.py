import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import (
    CandidateProfile,
    FileObject,
    Job,
    User,
    UserJobEvaluation,
)
from server.repositories.tenant import JobRepository, TenantRepository
from server.settings import Settings


class TenantRepositoryTests(unittest.TestCase):
    def setUp(self):
        settings = Settings(database_url="sqlite+pysqlite:///:memory:")
        self.engine = create_db_engine(settings)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.user_a = User(
            id=str(uuid4()), username="alice", password_hash="hash-a", role="user"
        )
        self.user_b = User(
            id=str(uuid4()), username="bob", password_hash="hash-b", role="user"
        )
        self.session.add_all([self.user_a, self.user_b])
        self.session.flush()

        self.job = Job(
            id=str(uuid4()),
            source="boss",
            external_job_id="boss-100",
            title="产品经理",
            company="示例科技",
            location="丽水",
            url="https://example.test/jobs/boss-100",
        )
        self.session.add(self.job)
        self.session.add_all(
            [
                CandidateProfile(
                    id=str(uuid4()),
                    user_id=self.user_a.id,
                    version=1,
                    status="confirmed",
                    data={"title": "产品经理"},
                ),
                FileObject(
                    id=str(uuid4()),
                    user_id=self.user_a.id,
                    object_key=f"users/{self.user_a.id}/source/a.txt",
                    filename="a.txt",
                    content_type="text/plain",
                    size=3,
                    sha256="a" * 64,
                ),
                UserJobEvaluation(
                    id=str(uuid4()),
                    user_id=self.user_a.id,
                    job_id=self.job.id,
                    score=92,
                    decision="recommended",
                ),
            ]
        )
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_private_rows_are_scoped_to_authenticated_user(self):
        repo_a = TenantRepository(self.session, self.user_a.id)
        repo_b = TenantRepository(self.session, self.user_b.id)

        self.assertIsNotNone(repo_a.get_profile())
        self.assertIsNone(repo_b.get_profile())
        self.assertEqual(len(repo_a.list_evaluations()), 1)
        self.assertEqual(repo_b.list_evaluations(), [])

        file_id = self.session.query(FileObject).one().id
        self.assertIsNotNone(repo_a.get_file(file_id))
        self.assertIsNone(repo_b.get_file(file_id))

    def test_public_job_is_visible_to_both_users(self):
        jobs_a = JobRepository(self.session).get_by_id(self.job.id)
        jobs_b = JobRepository(self.session).get_by_id(self.job.id)

        self.assertEqual(jobs_a.id, jobs_b.id)
        self.assertEqual(jobs_a.external_job_id, "boss-100")


if __name__ == "__main__":
    unittest.main()
