"""Authenticated source-document endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import SourceDocument, User
from server.repositories.tenant import TenantRepository
from server.security.permissions import get_current_user
from server.services.documents import DocumentValidationError, upload_source_document


router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        document, file_object = upload_source_document(
            db,
            request.app.state.object_storage,
            user.id,
            file.filename or "upload",
            file.content_type or "application/octet-stream",
            file.file,
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "document_id": document.id,
        "file_id": file_object.id,
        "object_key": file_object.object_key,
        "filename": file_object.filename,
        "content_type": file_object.content_type,
        "size": file_object.size,
        "sha256": file_object.sha256,
    }


@router.get("")
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SourceDocument).where(SourceDocument.user_id == user.id)
    ).all()
    file_ids = [row.file_id for row in rows]
    files = {file.id: file for file in TenantRepository(db, user.id).list_files(file_ids)}
    return [
        {
            "document_id": row.id,
            "file_id": row.file_id,
            "filename": files[row.file_id].filename,
            "size": files[row.file_id].size,
        }
        for row in rows
        if row.file_id in files
    ]


@router.get("/{file_id}/download")
def download_document(
    file_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_object = TenantRepository(db, user.id).get_file(file_id)
    if file_object is None:
        raise HTTPException(status_code=404, detail="document not found")
    body = request.app.state.object_storage.open(file_object.object_key)
    headers = {"Content-Disposition": f'attachment; filename="{file_object.filename}"'}
    return StreamingResponse(body, media_type=file_object.content_type, headers=headers)
