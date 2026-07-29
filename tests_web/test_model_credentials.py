import tempfile
import unittest
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from server.app import create_app
from server.bootstrap import initialize_admin
from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import ModelCredential, User
from server.security.passwords import verify_password
from server.security.sessions import issue_session
from server.settings import Settings


class ModelCredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.key = Fernet.generate_key().decode("ascii")
        self.settings = Settings(
            database_url=f"sqlite:///{self.temp.name}/credentials.db",
            model_credential_key=self.key,
        )
        self.engine = create_db_engine(self.settings)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = Session(self.engine)
        self.user = User(id=str(uuid4()), username="alice", password_hash="hash")
        self.db.add(self.user)
        self.db.commit()
        token = issue_session(self.db, self.user.id)
        self.db.commit()
        self.app = create_app(self.settings)
        self.app.state.session_factory = self.factory
        self.client = TestClient(self.app)
        self.client.cookies.set("session", token)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_model_key_is_encrypted_and_never_returned(self):
        response = self.client.put(
            "/api/settings/model-key",
            json={"provider": "openai-compatible", "api_key": "sk-private-value"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sk-private-value", response.text)
        credential = self.db.scalar(select(ModelCredential).where(ModelCredential.user_id == self.user.id))
        self.assertIsNotNone(credential)
        self.assertNotEqual(credential.encrypted_key, "sk-private-value")
        self.assertEqual(self.app.state.credential_cipher.decrypt(credential.encrypted_key), "sk-private-value")

    def test_initial_admin_is_created_only_when_configured(self):
        settings = Settings(
            database_url=f"sqlite:///{self.temp.name}/admin.db",
            initial_admin_username="root-admin",
            initial_admin_password="strong-password",
        )
        engine = create_db_engine(settings)
        Base.metadata.create_all(engine)
        initialize_admin(settings)
        with Session(engine) as db:
            admin = db.scalar(select(User).where(User.username == "root-admin"))
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, "admin")
            self.assertTrue(verify_password("strong-password", admin.password_hash))
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
