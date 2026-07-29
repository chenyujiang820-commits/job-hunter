"""Repository methods that enforce public/private data boundaries."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models.entities import (
    CandidateProfile,
    FileObject,
    Job,
    UserJobEvaluation,
)


class TenantRepository:
    def __init__(self, session: Session, user_id: str):
        self.session = session
        self.user_id = user_id

    def get_profile(self) -> CandidateProfile | None:
        statement = (
            select(CandidateProfile)
            .where(
                CandidateProfile.user_id == self.user_id,
                CandidateProfile.status == "confirmed",
            )
            .order_by(CandidateProfile.version.desc())
        )
        return self.session.scalars(statement).first()

    def list_evaluations(self) -> list[UserJobEvaluation]:
        statement = select(UserJobEvaluation).where(
            UserJobEvaluation.user_id == self.user_id
        )
        return list(self.session.scalars(statement).all())

    def get_file(self, file_id: str) -> FileObject | None:
        statement = select(FileObject).where(
            FileObject.id == file_id,
            FileObject.user_id == self.user_id,
        )
        return self.session.scalars(statement).first()

    def list_files(self, file_ids: list[str]) -> list[FileObject]:
        if not file_ids:
            return []
        statement = select(FileObject).where(
            FileObject.user_id == self.user_id,
            FileObject.id.in_(file_ids),
        )
        return list(self.session.scalars(statement).all())


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, job_id: str) -> Job | None:
        return self.session.get(Job, job_id)

    def upsert_public_job(self, job: dict[str, Any]) -> Job:
        statement = select(Job).where(
            Job.source == job.get("source", ""),
            Job.external_job_id == job.get("id", ""),
        )
        existing = self.session.scalars(statement).first()
        values = {
            "source": job.get("source", ""),
            "external_job_id": job.get("id", ""),
            "title": job.get("title") or "",
            "company": job.get("company") or "",
            "location": job.get("location") or "",
            "salary": job.get("salary") or {},
            "description": job.get("description") or "",
            "url": job.get("url") or "",
        }
        if existing is None:
            existing = Job(**values)
            self.session.add(existing)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
        self.session.flush()
        return existing
