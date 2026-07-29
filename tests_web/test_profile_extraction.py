import io
import tempfile
import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import FileObject, SourceDocument, User
from server.services.profile_extraction import ConsentRequired, ProfileService
from server.settings import Settings


class MemoryStorage:
    def __init__(self, objects):
        self.objects = objects

    def open(self, object_key):
        return io.BytesIO(self.objects[object_key])


class FakeLLM:
    def __init__(self):
        self.calls = []

    def extract_profile(self, source_text, schema):
        self.calls.append((source_text, schema))
        return {
            "name": "Alice",
            "target": {"positions": ["产品经理"]},
            "source_refs": ["resume.txt"],
        }


class ProfileExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(
            Settings(database_url=f"sqlite:///{self.temp.name}/profile.db")
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            id=str(uuid4()), username="alice", password_hash="hash", role="user"
        )
        file_id = str(uuid4())
        object_key = f"users/{self.user.id}/source/resume.txt"
        self.db.add(self.user)
        self.db.add(
            FileObject(
                id=file_id,
                user_id=self.user.id,
                object_key=object_key,
                filename="resume.txt",
                content_type="text/plain",
                size=16,
                sha256="a" * 64,
            )
        )
        self.document = SourceDocument(
            id=str(uuid4()), user_id=self.user.id, file_id=file_id
        )
        self.db.add(self.document)
        self.db.commit()
        self.llm = FakeLLM()
        self.service = ProfileService(
            self.db,
            MemoryStorage({object_key: b"Name: Alice\nTarget: PM"}),
            self.llm,
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_requires_consent_and_confirmation_before_profile_write(self):
        with self.assertRaises(ConsentRequired):
            self.service.create_proposal(self.user.id, [self.document.id])

        self.service.set_ai_consent(self.user.id, True)
        proposal = self.service.create_proposal(self.user.id, [self.document.id])
        self.assertEqual(proposal.status, "pending")
        self.assertEqual(self.service.get_confirmed_profile(self.user.id), None)

        profile = self.service.confirm_proposal(
            self.user.id, proposal.id, accepted_fields=["name"]
        )

        self.assertEqual(profile.status, "confirmed")
        self.assertEqual(profile.data["name"], "Alice")
        self.assertNotIn("target", profile.data)
        self.assertEqual(proposal.status, "confirmed")
        self.assertEqual(len(self.llm.calls), 1)

    def test_revoked_consent_blocks_new_extraction(self):
        self.service.set_ai_consent(self.user.id, True)
        self.service.set_ai_consent(self.user.id, False)

        with self.assertRaises(ConsentRequired):
            self.service.create_proposal(self.user.id, [self.document.id])


if __name__ == "__main__":
    unittest.main()
