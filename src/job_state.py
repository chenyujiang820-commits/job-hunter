"""Append-safe local state for normalized job summaries."""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from src.job_schema import JobSummary


@dataclass(frozen=True)
class MergeReport:
    new_count: int
    duplicate_count: int
    updated_count: int
    jobs: list[JobSummary]


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"\s+", "", text)


def _normalized_url(value: Any) -> str:
    parsed = urlsplit(str(value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.query,
            "",
        )
    )


def canonical_job_key(job: JobSummary) -> str:
    """Return a stable key, preferring the source's own ID."""
    source = _compact(job.get("source"))
    identifier = unicodedata.normalize("NFKC", str(job.get("id") or "")).strip()
    if source and identifier:
        return f"{source}:{identifier}"

    url = _normalized_url(job.get("url"))
    if url:
        return url

    company = _compact(job.get("company"))
    title = _compact(job.get("title"))
    if company or title:
        return f"text:{company}:{title}"
    raise ValueError("job must contain source/id, url, or company/title")


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "jobs": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid seen-jobs JSON: {path}") from exc

    if isinstance(state, list):
        state = {"version": 1, "jobs": state}
    if not isinstance(state, dict) or not isinstance(state.get("jobs", []), list):
        raise ValueError("seen-jobs state must contain a jobs list")
    return state


def _merge_values(old: Any, new: Any) -> Any:
    if isinstance(old, dict) and isinstance(new, dict):
        merged = copy.deepcopy(old)
        for key, value in new.items():
            if value is not None and value != "":
                merged[key] = copy.deepcopy(value)
        return merged
    if new is None or new == "":
        return copy.deepcopy(old)
    return copy.deepcopy(new)


def merge_seen_jobs(path: Path, jobs: list[JobSummary], today: str) -> MergeReport:
    """Merge jobs without deleting history or replacing known values with nulls."""
    state = _load_state(path)
    stored = state.get("jobs", [])
    index: dict[str, int] = {}
    normalized: list[JobSummary] = []

    for raw in stored:
        if not isinstance(raw, dict):
            raise ValueError("each seen job must be an object")
        item = copy.deepcopy(raw)
        key = item.get("job_key") or canonical_job_key(item)
        item["job_key"] = key
        index[key] = len(normalized)
        normalized.append(item)

    new_count = duplicate_count = updated_count = 0
    for raw in jobs:
        incoming = copy.deepcopy(dict(raw))
        key = canonical_job_key(incoming)
        incoming["job_key"] = key
        if key not in index:
            incoming.setdefault("first_seen", today)
            incoming.setdefault("last_seen", today)
            normalized.append(incoming)
            index[key] = len(normalized) - 1
            new_count += 1
            continue

        duplicate_count += 1
        position = index[key]
        previous = normalized[position]
        merged = copy.deepcopy(previous)
        for field, value in incoming.items():
            if field not in {"first_seen", "last_seen"}:
                merged[field] = _merge_values(merged.get(field), value)
        merged["first_seen"] = previous.get("first_seen", today)
        merged["last_seen"] = today
        comparable_previous = {k: v for k, v in previous.items() if k != "last_seen"}
        comparable_merged = {k: v for k, v in merged.items() if k != "last_seen"}
        if comparable_previous != comparable_merged:
            updated_count += 1
        normalized[position] = merged

    state["version"] = state.get("version", 1)
    state["updated_at"] = today
    state["jobs"] = normalized
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return MergeReport(new_count, duplicate_count, updated_count, normalized)
