"""Administrator invitation endpoint."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import Invite, User, utc_now
from server.security.permissions import require_admin
from server.security.tokens import hash_token


router = APIRouter(prefix="/api/admin/invites", tags=["admin"])


@router.post("")
def create_invite(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    raw_token = secrets.token_urlsafe(24)
    db.add(
        Invite(
            token_hash=hash_token(raw_token),
            expires_at=utc_now() + timedelta(hours=24),
            created_by=admin.id,
        )
    )
    db.commit()
    return {"invite": raw_token, "expires_in_hours": 24}
