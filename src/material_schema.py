"""Data contracts for local application material generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ApplicationDraft:
    job: Mapping[str, Any]
    candidate_facts: Mapping[str, str]
    resume_sections: Mapping[str, str]
    cover_letter_text: str
    required_keywords: list[str] = field(default_factory=list)
    source_refs: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicationBundle:
    resume_docx: Path
    cover_letter_docx: Path
    resume_pdf: Path | None = None
    cover_letter_pdf: Path | None = None

