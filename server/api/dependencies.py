"""Request-scoped database dependencies."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    db = factory()
    try:
        yield db
    finally:
        db.close()
