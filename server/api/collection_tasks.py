"""BOSS collection task endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import Task, User
from server.security.permissions import get_current_user
from server.services.browser_sessions import BrowserSessionService
from server.services.job_collection import CollectionTaskService


router = APIRouter(prefix="/api", tags=["collection-tasks"])


class CollectionTaskPayload(BaseModel):
    template_id: str


def task_view(task: Task) -> dict:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
    }


def _run_task(app, task_id: str) -> None:
    db = app.state.session_factory()
    try:
        service = CollectionTaskService(
            db,
            BrowserSessionService(db, app.state.settings, app.state.browser_connector),
            app.state.browser_connector,
        )
        service.run(task_id)
    finally:
        db.close()


@router.post("/collection-tasks", status_code=202)
def create_collection_task(
    payload: CollectionTaskPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollectionTaskService(
        db,
        BrowserSessionService(db, request.app.state.settings, request.app.state.browser_connector),
        request.app.state.browser_connector,
    )
    try:
        task = service.create(user.id, payload.template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(_run_task, request.app, task.id)
    return task_view(task)


@router.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task_view(task)
