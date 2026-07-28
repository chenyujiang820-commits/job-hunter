"""Deterministic hard filters and location tiers for domestic job ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from src.job_schema import CandidateProfile, JobSummary


LocationTier = Literal["lishui", "hangzhou_jinhua", "other_zhejiang", "outside"]

_ZHEJIANG_CITIES = (
    "杭州",
    "宁波",
    "温州",
    "嘉兴",
    "湖州",
    "绍兴",
    "金华",
    "衢州",
    "舟山",
    "台州",
    "丽水",
)
_EXCLUSION_DEFAULTS = ("劳务派遣", "派遣制", "外包", "人力外包", "岗位外包")
_POSTGRADUATE_REQUIREMENTS = (
    "硕士及以上",
    "研究生及以上",
    "博士及以上",
    "博士后",
    "要求硕士",
    "要求研究生",
    "要求博士",
    "硕士学历",
    "研究生学历",
    "博士学历",
)
_LONG_TERM_ONSITE = ("长期驻场", "长期驻点", "长期出差驻场", "常驻现场", "长期现场办公")


@dataclass(frozen=True)
class FilterResult:
    passed: bool
    reasons: list[str]
    flags: list[str]
    location_tier: LocationTier


def _text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def location_tier(location: str) -> LocationTier:
    value = _text(location)
    if "省外" in value or "省外地区" in value:
        return "outside"
    if "丽水" in value:
        return "lishui"
    if "杭州" in value or "金华" in value:
        return "hangzhou_jinhua"
    if "浙江" in value or any(city in value for city in _ZHEJIANG_CITIES):
        return "other_zhejiang"
    return "outside"


def _job_text(job: Mapping[str, Any]) -> str:
    fields = ("title", "company", "location", "description", "raw_text")
    return " ".join(_text(job.get(field)) for field in fields)


def _education_text(job: Mapping[str, Any]) -> str:
    return _text(job.get("education")) + " " + _text(job.get("raw_text"))


def apply_hard_filters(job: JobSummary, profile: CandidateProfile) -> FilterResult:
    reasons: list[str] = []
    flags: list[str] = []
    tier = location_tier(str(job.get("location") or ""))
    full_text = _job_text(job)

    exclusions = tuple(profile.get("hard_exclusions", _EXCLUSION_DEFAULTS))
    if any(_text(term) in full_text for term in exclusions):
        reasons.append("dispatch_or_outsourcing")

    education = _education_text(job)
    if any(requirement in education for requirement in _POSTGRADUATE_REQUIREMENTS):
        reasons.append("education_above_bachelor")

    if tier == "outside":
        reasons.append("location_outside_zhejiang")

    if any(marker in full_text for marker in _LONG_TERM_ONSITE):
        flags.append("long_term_onsite")

    return FilterResult(
        passed=not reasons,
        reasons=reasons,
        flags=flags,
        location_tier=tier,
    )
