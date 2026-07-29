"""Batch material drafts with per-draft review and finalization gates."""

from __future__ import annotations

import io
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.adapters.job_domain import job_to_summary
from server.models.entities import (
    CandidateProfile,
    FileObject,
    Job,
    MaterialBatch,
    MaterialDraft,
    SearchTemplate,
)


class MaterialBatchService:
    def __init__(
        self,
        db: Session,
        storage,
        workflow_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
        render_fn: Callable[[str, str, str | Path], Path] | None = None,
        convert_fn: Callable[[Path, Path], Path] | None = None,
    ):
        self.db = db
        self.storage = storage
        self.workflow_fn = workflow_fn or self._default_workflow
        self.render_fn = render_fn or self._default_render
        self.convert_fn = convert_fn or self._default_convert

    def create(self, user_id: str, job_ids: list[str], template_id: str) -> MaterialBatch:
        template = self.db.scalar(
            select(SearchTemplate).where(
                SearchTemplate.id == template_id,
                SearchTemplate.user_id == user_id,
            )
        )
        if template is None:
            raise ValueError("search template not found")
        if not job_ids:
            raise ValueError("at least one job is required")
        jobs = list(self.db.scalars(select(Job).where(Job.id.in_(job_ids))).all())
        if len(jobs) != len(set(job_ids)):
            raise ValueError("one or more jobs not found")

        batch = MaterialBatch(user_id=user_id, template_id=template_id, status="queued")
        self.db.add(batch)
        self.db.flush()
        for job in jobs:
            self.db.add(
                MaterialDraft(
                    user_id=user_id,
                    batch_id=batch.id,
                    job_id=job.id,
                    status="queued",
                )
            )
        self.db.commit()
        return batch

    def list_drafts(self, user_id: str, batch_id: str) -> list[MaterialDraft]:
        batch = self.db.scalar(
            select(MaterialBatch).where(MaterialBatch.id == batch_id, MaterialBatch.user_id == user_id)
        )
        if batch is None:
            return []
        return list(
            self.db.scalars(
                select(MaterialDraft)
                .where(MaterialDraft.batch_id == batch_id, MaterialDraft.user_id == user_id)
                .order_by(MaterialDraft.id)
            ).all()
        )

    def run_draft(self, batch_id: str) -> MaterialBatch:
        batch = self.db.get(MaterialBatch, batch_id)
        if batch is None:
            raise ValueError("material batch not found")
        batch.status = "running"
        self.db.commit()
        profile = self._profile_data(batch.user_id)
        drafts = list(
            self.db.scalars(select(MaterialDraft).where(MaterialDraft.batch_id == batch_id)).all()
        )
        for draft in drafts:
            if draft.status not in {"queued", "changes_requested"}:
                continue
            try:
                job = self.db.get(Job, draft.job_id)
                if job is None:
                    raise ValueError("job not found")
                result = self.workflow_fn(job_to_summary(job), profile)
                draft.resume_text = str(result.get("resume", ""))
                draft.cover_letter_text = str(result.get("cover", ""))
                draft.fit_data = result.get("fit", {}) or {}
                draft.review_data = result.get("review", {}) or {}
                draft.status = "draft_ready"
            except Exception as exc:
                draft.status = "failed"
                draft.review_data = {"error": str(exc)}
        batch.status = "completed_with_errors" if any(d.status == "failed" for d in drafts) else "completed"
        self.db.commit()
        return batch

    def review(self, user_id: str, draft_id: str, decision: str, notes: str = "") -> MaterialDraft:
        draft = self._get_draft(user_id, draft_id)
        if draft is None:
            raise ValueError("material draft not found")
        if draft.status not in {"draft_ready", "changes_requested"}:
            raise ValueError("draft is not ready for review")
        if decision not in {"approved", "changes_requested"}:
            raise ValueError("invalid review decision")
        draft.status = decision
        draft.review_notes = notes
        self.db.commit()
        return draft

    def finalize(self, user_id: str, draft_id: str) -> list[FileObject]:
        draft = self._get_draft(user_id, draft_id)
        if draft is None:
            raise ValueError("material draft not found")
        if draft.status != "approved":
            raise ValueError("draft must be approved before finalization")
        if draft.output_file_ids:
            return list(
                self.db.scalars(select(FileObject).where(FileObject.id.in_(draft.output_file_ids))).all()
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docx_path = self.render_fn(draft.resume_text, draft.cover_letter_text, root / f"{draft.id}.docx")
            pdf_path = self.convert_fn(Path(docx_path), root)
            files = [
                self._store_output(user_id, Path(docx_path), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                self._store_output(user_id, Path(pdf_path), "application/pdf"),
            ]
        draft.output_file_ids = [file_object.id for file_object in files]
        draft.status = "finalized"
        self.db.commit()
        return files

    def _get_draft(self, user_id: str, draft_id: str) -> MaterialDraft | None:
        return self.db.scalar(
            select(MaterialDraft).where(MaterialDraft.id == draft_id, MaterialDraft.user_id == user_id)
        )

    def _profile_data(self, user_id: str) -> dict[str, Any]:
        profile = self.db.scalars(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id, CandidateProfile.status == "confirmed")
            .order_by(CandidateProfile.version.desc())
        ).first()
        return profile.data if profile else {}

    def _store_output(self, user_id: str, path: Path, content_type: str) -> FileObject:
        stored = self.storage.put(user_id, io.BytesIO(path.read_bytes()), content_type, path.name)
        file_object = FileObject(
            user_id=user_id,
            object_key=str(stored["object_key"]),
            filename=path.name,
            content_type=content_type,
            size=int(stored["size"]),
            sha256=str(stored["sha256"]),
        )
        self.db.add(file_object)
        self.db.flush()
        return file_object

    @staticmethod
    def _default_workflow(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        from agent.generator import generate_cover_letter, generate_resume
        from agent.workflow import generate_application_materials

        resume_fn = lambda title, company, desc, fit_summary="", improvements=None: generate_resume(
            title, company, desc, fit_summary, improvements, profile_data=profile
        )
        cover_fn = lambda title, company, desc, fit_summary="", improvements=None: generate_cover_letter(
            title, company, desc, fit_summary, improvements, profile_data=profile
        )
        return generate_application_materials(job, resume_fn=resume_fn, cover_fn=cover_fn)

    @staticmethod
    def _default_render(resume: str, cover: str, output: str | Path) -> Path:
        from tools.render_docx import generate_docx

        return generate_docx(output, resume, cover)

    @staticmethod
    def _default_convert(docx: Path, output_dir: Path) -> Path:
        from tools.convert_docx_to_pdf import convert_docx_to_pdf

        return convert_docx_to_pdf(docx, output_dir)
