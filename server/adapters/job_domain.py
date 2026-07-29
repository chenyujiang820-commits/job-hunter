"""Conversion between web ORM jobs and the existing ranking domain shape."""

from __future__ import annotations

from typing import Any

from server.models.entities import Job


def job_to_summary(job: Job) -> dict[str, Any]:
    return {
        "id": job.external_job_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "salary": job.salary or {},
        "url": job.url,
        "source": job.source,
        "description": job.description,
    }
