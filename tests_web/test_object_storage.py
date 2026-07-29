import hashlib
import io
import tempfile
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from server.app import create_app
from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import FileObject, User
from server.security.sessions import issue_session
from server.settings import Settings


class MemoryObjectStorage:
    def __init__(self):
        self.objects = {}

    def put(self, owner_id, content, content_type, filename):
        data = content.read()
        key = f"users/{owner_id}/source/{filename}"
        self.objects[key] = {"body": data, "content_type": content_type}
        return {
            "object_key": key,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def open(self, object_key):
        return io.BytesIO(self.objects[object_key]["body"])

    def delete(self, object_key):
        self.objects.pop(object_key, None)


class ObjectStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        settings = Settings(database_url=f"sqlite:///{self.temp.name}/files.db")
        self.engine = create_db_engine(settings)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = Session(self.engine)
        self.user_a = User(
            id=str(uuid4()), username="alice", password_hash="hash", role="user"
        )
        self.user_b = User(
            id=str(uuid4()), username="bob", password_hash="hash", role="user"
        )
        self.db.add_all([self.user_a, self.user_b])
        self.db.commit()
        self.tokens = {
            self.user_a.id: issue_session(self.db, self.user_a.id),
            self.user_b.id: issue_session(self.db, self.user_b.id),
        }
        self.db.commit()

        self.storage = MemoryObjectStorage()
        self.app = create_app(settings)
        self.app.state.session_factory = self.factory
        self.app.state.object_storage = self.storage
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def _as_user(self, user_id):
        self.client.cookies.clear()
        self.client.cookies.set("session", self.tokens[user_id])

    def test_upload_stores_private_object_and_metadata(self):
        self._as_user(self.user_a.id)
        response = self.client.post(
            "/api/documents",
            files={"file": ("resume.txt", b"abc", "text/plain")},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["object_key"].startswith(f"users/{self.user_a.id}/"))
        self.assertEqual(payload["size"], 3)
        self.assertEqual(payload["sha256"], hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(self.db.query(FileObject).count(), 1)

    def test_other_user_cannot_download_private_object(self):
        self._as_user(self.user_a.id)
        uploaded = self.client.post(
            "/api/documents",
            files={"file": ("resume.txt", b"private", "text/plain")},
        ).json()

        self._as_user(self.user_b.id)
        response = self.client.get(f"/api/documents/{uploaded['file_id']}/download")

        self.assertEqual(response.status_code, 404)

    def test_upload_rejects_unsupported_extension_and_oversized_file(self):
        self._as_user(self.user_a.id)
        unsupported = self.client.post(
            "/api/documents",
            files={"file": ("resume.exe", b"abc", "application/octet-stream")},
        )
        oversized = self.client.post(
            "/api/documents",
            files={"file": ("resume.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
        )

        self.assertEqual(unsupported.status_code, 415)
        self.assertEqual(oversized.status_code, 413)


if __name__ == "__main__":
    unittest.main()
