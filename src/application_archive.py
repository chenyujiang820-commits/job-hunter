"""Append-safe local archive for approved application materials."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from shutil import copy2
from typing import Any, Mapping

from src.job_state import canonical_job_key
from src.material_schema import ApplicationBundle


@dataclass(frozen=True)
class ArchiveRecord:
    job_key: str
    company: str
    role: str
    source_url: str
    archive_dir: Path
    resume_docx: Path
    cover_letter_docx: Path
    resume_pdf: Path | None
    cover_letter_pdf: Path | None
    confirmation_marker: str


def require_user_confirmation(action: str, payload_summary: str) -> bool:
    answer = input(f"Confirm {action}: {payload_summary} [y/N] ")
    return answer.strip().lower() in {"y", "yes", "确认", "是"}


def _safe_name(value: Any) -> str:
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", str(value or "unknown"))
    return text.strip(" .")[:80] or "unknown"


def _record_from_manifest(path: Path) -> ArchiveRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ArchiveRecord(
        job_key=data["job_key"],
        company=data["company"],
        role=data["role"],
        source_url=data["source_url"],
        archive_dir=path.parent,
        resume_docx=path.parent / data["resume_docx"],
        cover_letter_docx=path.parent / data["cover_letter_docx"],
        resume_pdf=path.parent / data["resume_pdf"] if data.get("resume_pdf") else None,
        cover_letter_pdf=path.parent / data["cover_letter_pdf"] if data.get("cover_letter_pdf") else None,
        confirmation_marker=data["confirmation_marker"],
    )


def _append_tracker(root: Path, record: ArchiveRecord) -> None:
    tracker = root.parent / "job_search_tracker.csv"
    fields = ["job_key", "company", "role", "source_url", "status", "archive_dir", "date"]
    exists = tracker.is_file()
    with tracker.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "job_key": record.job_key,
                "company": record.company,
                "role": record.role,
                "source_url": record.source_url,
                "status": "materials_generated",
                "archive_dir": record.archive_dir.relative_to(root.parent).as_posix(),
                "date": date.today().isoformat(),
            }
        )


def archive_application(
    job: Mapping[str, Any], bundle: ApplicationBundle, root: Path
) -> ArchiveRecord:
    """Archive approved materials locally without overwriting a submitted bundle."""
    company = str(job.get("company") or "unknown-company")
    role = str(job.get("title") or "unknown-role")
    summary = f"{company} / {role}"
    if not require_user_confirmation("archive application", summary):
        raise PermissionError("User confirmation is required before archiving materials")

    archive_dir = root / "applications" / f"{_safe_name(company)}_{_safe_name(role)}"
    manifest = archive_dir / "manifest.json"
    if manifest.is_file():
        return _record_from_manifest(manifest)

    for source in (
        bundle.resume_docx,
        bundle.cover_letter_docx,
        bundle.resume_pdf,
        bundle.cover_letter_pdf,
    ):
        if source is not None and not source.is_file():
            raise FileNotFoundError(f"Application material does not exist: {source}")

    archive_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str | None] = {}
    for field, source in (
        ("resume_docx", bundle.resume_docx),
        ("cover_letter_docx", bundle.cover_letter_docx),
        ("resume_pdf", bundle.resume_pdf),
        ("cover_letter_pdf", bundle.cover_letter_pdf),
    ):
        destination = archive_dir / source.name if source is not None else None
        if source is not None and destination is not None:
            copy2(source, destination)
        copied[field] = destination.name if destination is not None else None

    record = ArchiveRecord(
        job_key=canonical_job_key(dict(job)),
        company=company,
        role=role,
        source_url=str(job.get("url") or ""),
        archive_dir=archive_dir,
        resume_docx=archive_dir / copied["resume_docx"],
        cover_letter_docx=archive_dir / copied["cover_letter_docx"],
        resume_pdf=archive_dir / copied["resume_pdf"] if copied["resume_pdf"] else None,
        cover_letter_pdf=archive_dir / copied["cover_letter_pdf"] if copied["cover_letter_pdf"] else None,
        confirmation_marker="CONFIRMED",
    )
    manifest.write_text(
        json.dumps(
            {
                "job_key": record.job_key,
                "company": record.company,
                "role": record.role,
                "source_url": record.source_url,
                "resume_docx": copied["resume_docx"],
                "cover_letter_docx": copied["cover_letter_docx"],
                "resume_pdf": copied["resume_pdf"],
                "cover_letter_pdf": copied["cover_letter_pdf"],
                "confirmation_marker": record.confirmation_marker,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _append_tracker(root, record)
    return record
