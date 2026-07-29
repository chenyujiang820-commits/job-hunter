"""Administrator account operations without private-content browsing."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import SessionRecord, User
from server.security.passwords import hash_password
from server.security.permissions import require_admin
from server.security.sessions import SESSION_COOKIE
from server.models.entities import utc_now


router = APIRouter(prefix="/api/admin", tags=["admin"])


class PasswordResetPayload(BaseModel):
    password: str = Field(min_length=8, max_length=256)


@router.post("/users/{user_id}/password-reset", status_code=204)
def reset_password(
    user_id: str,
    payload: PasswordResetPayload,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    user.password_hash = hash_password(payload.password)
    db.execute(
        update(SessionRecord)
        .where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    db.commit()
