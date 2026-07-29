"""Private evaluation endpoints over shared public jobs."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.dependencies import get_db
from server.models.entities import Job, User, UserJobEvaluation
from server.security.permissions import get_current_user
from server.services.evaluation import EvaluationService


router = APIRouter(prefix="/api", tags=["evaluations"])


class EvaluationBatchPayload(BaseModel):
    job_ids: list[str] = Field(min_length=1)
    template_id: str


class EvaluationUpdatePayload(BaseModel):
    decision: str | None = None
    notes: str | None = None


def evaluation_view(evaluation: UserJobEvaluation) -> dict:
    return {
        "id": evaluation.id,
        "job_id": evaluation.job_id,
        "score": evaluation.score,
        "decision": evaluation.decision,
        "reasons": evaluation.reasons,
        "flags": evaluation.flags,
        "notes": evaluation.notes,
        "rules_version": evaluation.rules_version,
    }


@router.get("/jobs")
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    jobs = list(db.scalars(select(Job).order_by(Job.fetched_at.desc()).offset(offset).limit(min(limit, 200))).all())
    evaluations = {
        evaluation.job_id: evaluation
        for evaluation in EvaluationService(db).list_for_user(user.id)
    }
    return [
        {
            "id": job.id,
            "source": job.source,
            "external_job_id": job.external_job_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary,
            "description": job.description,
            "url": job.url,
            "evaluation": evaluation_view(evaluations[job.id]) if job.id in evaluations else None,
        }
        for job in jobs
    ]


@router.post("/evaluations/batch")
def evaluate_batch(
    payload: EvaluationBatchPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        evaluations = EvaluationService(db).evaluate_for_user(user.id, payload.job_ids, payload.template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"evaluations": [evaluation_view(evaluation) for evaluation in evaluations]}


@router.patch("/evaluations/{job_id}")
def update_evaluation(
    job_id: str,
    payload: EvaluationUpdatePayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        evaluation = EvaluationService(db).update_for_user(
            user.id, job_id, payload.decision, payload.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return evaluation_view(evaluation)
