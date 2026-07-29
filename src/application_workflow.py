"""User-confirmed local application material workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.material_schema import ApplicationBundle, ApplicationDraft
from tools.convert_docx_to_pdf import convert_docx_to_pdf
from tools.render_docx import render_docx
from tools.validate_application_bundle import validate_application_bundle
from src.application_archive import require_user_confirmation


def generate_application_bundle(
    job: Mapping[str, Any],
    draft: ApplicationDraft,
    templates_root: Path,
    output_root: Path,
    *,
    soffice: str = "soffice",
) -> ApplicationBundle:
    """Generate and validate materials for exactly one confirmed selected job."""
    if not job or not str(job.get("url") or "").strip():
        raise ValueError("one selected job with a URL is required")
    if not require_user_confirmation(
        "generate application materials",
        f"{job.get('company', '')} / {job.get('title', '')}",
    ):
        raise PermissionError("User confirmation is required before material generation")

    resume_docx = render_docx(
        templates_root / "resume" / "resume_template.docx",
        draft,
        output_root / "resume.docx",
    )
    cover_docx = render_docx(
        templates_root / "cover_letters" / "cover_letter_template.docx",
        draft,
        output_root / "cover_letter.docx",
    )
    pdf_root = output_root / "pdf"
    resume_pdf = convert_docx_to_pdf(resume_docx, pdf_root, soffice=soffice)
    cover_pdf = convert_docx_to_pdf(cover_docx, pdf_root, soffice=soffice)

    required_terms = draft.required_keywords
    resume_report = validate_application_bundle(resume_docx, resume_pdf, required_terms)
    cover_report = validate_application_bundle(cover_docx, cover_pdf, required_terms)
    if not resume_report.passed or not cover_report.passed:
        raise ValueError(
            "application material validation failed: "
            f"resume={resume_report.errors}; cover={cover_report.errors}"
        )

    return ApplicationBundle(
        resume_docx=resume_docx,
        cover_letter_docx=cover_docx,
        resume_pdf=resume_pdf,
        cover_letter_pdf=cover_pdf,
    )
