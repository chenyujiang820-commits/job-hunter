"""User-owned search templates and job evaluations."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.adapters.job_domain import job_to_summary
from server.models.entities import Job, SearchTemplate, UserJobEvaluation
from server.repositories.tenant import TenantRepository
from src.ranking_rules import direction_score


DEFAULT_WEIGHTS = {"keyword": 25, "direction": 35, "location": 20, "salary": 20}


@dataclass(frozen=True)
class SearchTemplateInput:
    name: str
    keywords: list[str] = field(default_factory=list)
    cities: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    experience: str = ""
    education: str = ""
    salary_reference: int | None = None
    work_modes: list[str] = field(default_factory=list)
    hard_exclusions: list[str] = field(default_factory=list)
    weights: dict[str, int] = field(default_factory=dict)

    def to_data(self) -> dict[str, Any]:
        data = asdict(self)
        data["weights"] = _normalize_weights(self.weights)
        return data


class SearchTemplateService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: str, payload: SearchTemplateInput) -> SearchTemplate:
        template = SearchTemplate(user_id=user_id, name=payload.name, data=payload.to_data())
        self.db.add(template)
        self.db.commit()
        return template

    def list_for_user(self, user_id: str) -> list[SearchTemplate]:
        return list(
            self.db.scalars(
                select(SearchTemplate)
                .where(SearchTemplate.user_id == user_id)
                .order_by(SearchTemplate.created_at.desc())
            ).all()
        )

    def get(self, user_id: str, template_id: str) -> SearchTemplate | None:
        return self.db.scalar(
            select(SearchTemplate).where(
                SearchTemplate.id == template_id,
                SearchTemplate.user_id == user_id,
            )
        )


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db

    def evaluate_for_user(
        self,
        user_id: str,
        job_ids: list[str],
        template_id: str,
    ) -> list[UserJobEvaluation]:
        template = self.db.scalar(
            select(SearchTemplate).where(
                SearchTemplate.id == template_id,
                SearchTemplate.user_id == user_id,
            )
        )
        if template is None:
            raise ValueError("search template not found")
        jobs = list(self.db.scalars(select(Job).where(Job.id.in_(job_ids))).all())
        if len(jobs) != len(set(job_ids)):
            raise ValueError("one or more jobs not found")

        results = []
        for job in jobs:
            summary = job_to_summary(job)
            score, reasons, flags = _score_job(summary, template.data or {})
            evaluation = self.db.scalar(
                select(UserJobEvaluation).where(
                    UserJobEvaluation.user_id == user_id,
                    UserJobEvaluation.job_id == job.id,
                )
            )
            if evaluation is None:
                evaluation = UserJobEvaluation(user_id=user_id, job_id=job.id)
                self.db.add(evaluation)
            evaluation.score = score
            evaluation.reasons = reasons
            evaluation.decision = "excluded" if any(reason.startswith("hard:") for reason in reasons) else (
                "recommended" if score >= 60 else "review"
            )
            evaluation.flags = flags
            evaluation.notes = ""
            evaluation.rules_version = "web-1"
            results.append(evaluation)
        self.db.commit()
        return results

    def list_for_user(self, user_id: str) -> list[UserJobEvaluation]:
        return TenantRepository(self.db, user_id).list_evaluations()

    def update_for_user(
        self,
        user_id: str,
        job_id: str,
        decision: str | None = None,
        notes: str | None = None,
    ) -> UserJobEvaluation:
        evaluation = self.db.scalar(
            select(UserJobEvaluation).where(
                UserJobEvaluation.user_id == user_id,
                UserJobEvaluation.job_id == job_id,
            )
        )
        if evaluation is None:
            raise ValueError("evaluation not found")
        if decision is not None:
            evaluation.decision = decision
        if notes is not None:
            evaluation.notes = notes
        self.db.commit()
        return evaluation


def _score_job(job: dict[str, Any], data: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    keywords = _clean_terms(data.get("keywords", []))
    cities = _clean_terms(data.get("cities", []))
    exclusions = _clean_terms(data.get("hard_exclusions", []))
    weights = _normalize_weights(data.get("weights", {}))
    text = _job_text(job)
    reasons: list[str] = []
    flags: list[str] = []

    if exclusions and any(term in text for term in exclusions):
        reasons.append("hard:excluded_term")
    if cities and not any(city in _compact(job.get("location")) for city in cities):
        reasons.append("hard:location_not_in_template")

    if any(marker in text for marker in ("长期驻场", "长期驻点", "长期现场办公", "长期出差驻场")):
        flags.append("long_term_onsite")

    keyword_score = _match_score(text, keywords)
    location_score = _location_score(job.get("location", ""), cities)
    direction = direction_score(job)
    salary_score = _salary_score(job.get("salary") or {}, data.get("salary_reference"))
    components = {
        "keyword": keyword_score,
        "direction": direction,
        "location": location_score,
        "salary": salary_score,
    }
    total_weight = sum(weights.values()) or 1
    score = round(sum(components[name] * weights.get(name, 0) for name in components) / total_weight)
    if keywords and keyword_score:
        reasons.append("match:keyword")
    if cities and location_score:
        reasons.append("match:city")
    if not any(reason.startswith("hard:") for reason in reasons):
        reasons.append(f"score:{score}")
    return max(0, min(100, score)), reasons, flags


def _normalize_weights(weights: dict[str, Any]) -> dict[str, int]:
    normalized = dict(DEFAULT_WEIGHTS)
    for name in normalized:
        try:
            normalized[name] = max(0, int(weights.get(name, normalized[name])))
        except (TypeError, ValueError):
            continue
    return normalized


def _clean_terms(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip().lower() for value in values if str(value).strip()]


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _job_text(job: dict[str, Any]) -> str:
    return " ".join(_compact(job.get(field)) for field in ("title", "company", "location", "description"))


def _match_score(text: str, terms: list[str]) -> int:
    if not terms:
        return 50
    matched = sum(1 for term in terms if term in text)
    return round(matched / len(terms) * 100)


def _location_score(location: Any, cities: list[str]) -> int:
    value = _compact(location)
    if not cities:
        return 50
    for index, city in enumerate(cities):
        if city in value:
            return max(40, 100 - index * 15)
    return 0


def _salary_score(salary: dict[str, Any], reference: Any) -> int:
    if reference in (None, ""):
        return 50
    try:
        reference_value = float(reference)
        maximum = float(salary.get("max") or salary.get("min") or 0)
    except (TypeError, ValueError):
        return 50
    if maximum <= 0:
        return 50
    return max(0, min(100, round(maximum / reference_value * 100))) if reference_value > 0 else 50
