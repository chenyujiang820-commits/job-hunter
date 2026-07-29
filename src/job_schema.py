"""Typed shapes shared by manual intake, state, and ranking code."""

from typing import Any, Mapping, TypedDict


class Salary(TypedDict, total=False):
    raw: str
    min: int | None
    max: int | None
    unit: str
    months_per_year: int | None
    negotiable: bool


class JobSummary(TypedDict, total=False):
    id: str | None
    title: str | None
    company: str | None
    location: str | None
    salary: Salary | None
    experience: str | None
    education: str | None
    tags: str | None
    date: str | None
    url: str | None
    source: str | None
    description: str | None
    raw_text: str | None


CandidateProfile = Mapping[str, Any]
