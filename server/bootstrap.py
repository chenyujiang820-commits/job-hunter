"""Bootstrap local runtime dependencies before starting the API."""

from __future__ import annotations

import time

from server.adapters.object_storage import ObjectStorage, ensure_bucket
from server.db import create_session_factory
from server.models.entities import User
from server.security.passwords import hash_password
from server.settings import Settings


def initialize_object_storage(settings: Settings, attempts: int = 30, delay: float = 1.0) -> None:
    """Create the configured bucket, retrying while MinIO/S3 becomes ready."""
    storage = ObjectStorage.from_settings(settings)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            ensure_bucket(storage)
            return
        except Exception as exc:  # boto3 exposes different errors across S3 implementations
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay)
    raise RuntimeError("object storage did not become ready") from last_error


def initialize_admin(settings: Settings) -> None:
    """Create the first administrator when both bootstrap values are configured."""
    if not settings.initial_admin_username or not settings.initial_admin_password:
        return
    factory = create_session_factory(settings)
    db = factory()
    try:
        if db.query(User).filter(User.username == settings.initial_admin_username).first() is None:
            db.add(
                User(
                    username=settings.initial_admin_username,
                    password_hash=hash_password(settings.initial_admin_password),
                    role="admin",
                    status="active",
                )
            )
            db.commit()
    finally:
        db.close()


def main() -> None:
    settings = Settings()
    initialize_object_storage(settings)
    initialize_admin(settings)


if __name__ == "__main__":
    main()
