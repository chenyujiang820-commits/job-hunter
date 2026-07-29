"""FastAPI authorization dependencies."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from server.models.entities import User
from server.security.sessions import SESSION_COOKIE, user_for_token
from server.api.dependencies import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_for_token(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin required")
    return user
