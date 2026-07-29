"""Private source-document validation and metadata persistence."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from server.models.entities import FileObject, SourceDocument


MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".txt"}


class DocumentValidationError(ValueError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _read_content(content: BinaryIO) -> bytes:
    data = content.read()
    if not isinstance(data, bytes):
        data = data.encode("utf-8")
    return data


def upload_source_document(
    db: Session,
    storage,
    user_id: str,
    filename: str,
    content_type: str,
    content: BinaryIO,
) -> tuple[SourceDocument, FileObject]:
    safe_name = Path(filename).name
    if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError("unsupported document extension", 415)
    data = _read_content(content)
    if len(data) > MAX_DOCUMENT_SIZE:
        raise DocumentValidationError("document exceeds 10 MiB", 413)

    stored = storage.put(user_id, BytesIO(data), content_type, safe_name)
    file_object = FileObject(
        user_id=user_id,
        object_key=str(stored["object_key"]),
        filename=safe_name,
        content_type=content_type,
        size=int(stored["size"]),
        sha256=str(stored["sha256"]),
    )
    db.add(file_object)
    try:
        db.flush()
        document = SourceDocument(user_id=user_id, file_id=file_object.id)
        db.add(document)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(str(stored["object_key"]))
        raise
    return document, file_object
