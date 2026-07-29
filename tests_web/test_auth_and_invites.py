import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from server.app import create_app
from server.db import create_db_engine
from server.models.base import Base
from server.models.entities import Invite, User, utc_now
from server.security.passwords import hash_password
from server.security.tokens import hash_token
from server.settings import Settings


class AuthAndInviteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database = Path(self.temp.name) / "auth.db"
        settings = Settings(database_url=f"sqlite:///{database}")
        self.engine = create_db_engine(settings)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session = Session(self.engine)

        self.admin = User(
            id=str(uuid4()),
            username="admin",
            password_hash=hash_password("admin-pass"),
            role="admin",
            status="active",
        )
        self.raw_invite = "invite-for-alice"
        invite = Invite(
            id=str(uuid4()),
            token_hash=hash_token(self.raw_invite),
            expires_at=utc_now() + timedelta(hours=1),
            created_by=self.admin.id,
        )
        self.session.add_all([self.admin, invite])
        self.session.commit()

        self.app = create_app(settings)
        self.app.state.session_factory = self.factory
        self.client = TestClient(self.app)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.temp.cleanup()

    def _login(self, username: str, password: str):
        return self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )

    def test_invite_registration_is_one_time_and_session_is_private(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "invite": self.raw_invite,
                "username": "alice",
                "password": "alice-pass",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("session", response.cookies)
        self.assertTrue(response.cookies.get("session"))

        self.assertEqual(self.client.get("/api/auth/me").json()["username"], "alice")
        self.assertEqual(
            self.client.post(
                "/api/auth/register",
                json={
                    "invite": self.raw_invite,
                    "username": "alice-second",
                    "password": "another-pass",
                },
            ).status_code,
            409,
        )

    def test_logout_and_disabled_user_cannot_use_session(self):
        self.client.post(
            "/api/auth/register",
            json={
                "invite": self.raw_invite,
                "username": "alice",
                "password": "alice-pass",
            },
        )
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_regular_user_cannot_create_invites_or_reset_passwords(self):
        self.client.post(
            "/api/auth/register",
            json={
                "invite": self.raw_invite,
                "username": "alice",
                "password": "alice-pass",
            },
        )
        self.assertEqual(self.client.post("/api/admin/invites").status_code, 403)
        self.assertEqual(
            self.client.post(
                f"/api/admin/users/{self.admin.id}/password-reset",
                json={"password": "changed-pass"},
            ).status_code,
            403,
        )

    def test_disabled_user_cannot_login(self):
        user = User(
            id=str(uuid4()),
            username="disabled",
            password_hash=hash_password("disabled-pass"),
            role="user",
            status="disabled",
        )
        self.session.add(user)
        self.session.commit()

        response = self._login("disabled", "disabled-pass")

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
