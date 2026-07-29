"""Per-user BOSS browser session endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import BrowserSession, User
from server.security.permissions import get_current_user
from server.services.browser_sessions import BrowserSessionService


router = APIRouter(prefix="/api/browser-sessions", tags=["browser-sessions"])


def session_view(session: BrowserSession | None) -> dict | None:
    if session is None:
        return None
    return {
        "id": session.id,
        "platform": session.platform,
        "status": session.status,
        "profile_path": session.profile_path,
        "last_used_at": session.last_used_at,
    }


def get_service(request: Request, db: Session) -> BrowserSessionService:
    return BrowserSessionService(db, request.app.state.settings, request.app.state.browser_connector)


@router.post("/start")
def start_session(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return session_view(get_service(request, db).start(user.id))


@router.get("")
def get_session(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return session_view(get_service(request, db).get(user.id))


@router.post("/stop")
def stop_session(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return session_view(get_service(request, db).stop(user.id))
