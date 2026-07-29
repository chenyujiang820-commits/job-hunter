"""Batch material creation and draft review endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import MaterialBatch, User
from server.security.permissions import get_current_user
from server.services.material_batches import MaterialBatchService


router = APIRouter(prefix="/api", tags=["materials"])


class MaterialBatchPayload(BaseModel):
    job_ids: list[str] = Field(min_length=1)
    template_id: str


class MaterialReviewPayload(BaseModel):
    decision: str
    notes: str = ""


def file_view(file_object) -> dict:
    return {
        "id": file_object.id,
        "filename": file_object.filename,
        "content_type": file_object.content_type,
        "size": file_object.size,
    }


def draft_view(draft) -> dict:
    return {
        "id": draft.id,
        "job_id": draft.job_id,
        "status": draft.status,
        "resume_text": draft.resume_text,
        "cover_letter_text": draft.cover_letter_text,
        "fit": draft.fit_data,
        "review": draft.review_data,
        "review_notes": draft.review_notes,
        "output_file_ids": draft.output_file_ids,
    }


def batch_view(batch, service: MaterialBatchService) -> dict:
    return {
        "id": batch.id,
        "status": batch.status,
        "template_id": batch.template_id,
        "drafts": [draft_view(draft) for draft in service.list_drafts(batch.user_id, batch.id)],
    }


def _run_batch(app, batch_id: str) -> None:
    db = app.state.session_factory()
    try:
        service = MaterialBatchService(db, app.state.object_storage)
        service.run_draft(batch_id)
    finally:
        db.close()


@router.post("/material-batches", status_code=202)
def create_batch(
    payload: MaterialBatchPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = MaterialBatchService(db, request.app.state.object_storage)
    try:
        batch = service.create(user.id, payload.job_ids, payload.template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(_run_batch, request.app, batch.id)
    return batch_view(batch, service)


@router.get("/material-batches/{batch_id}")
def get_batch(
    batch_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batch = db.scalar(select(MaterialBatch).where(MaterialBatch.id == batch_id, MaterialBatch.user_id == user.id))
    if batch is None:
        raise HTTPException(status_code=404, detail="material batch not found")
    return batch_view(batch, MaterialBatchService(db, None))


@router.patch("/material-drafts/{draft_id}/review")
def review_draft(
    draft_id: str,
    payload: MaterialReviewPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        draft = MaterialBatchService(db, None).review(user.id, draft_id, payload.decision, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return draft_view(draft)


@router.post("/material-drafts/{draft_id}/finalize")
def finalize_draft(
    draft_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        files = MaterialBatchService(db, request.app.state.object_storage).finalize(user.id, draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"files": [file_view(file_object) for file_object in files]}
