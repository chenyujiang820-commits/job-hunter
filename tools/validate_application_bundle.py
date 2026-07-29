"""Validate locally generated DOCX/PDF application materials."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

from docx import Document


@dataclass(frozen=True)
class ValidationReport:
    docx_readable: bool
    pdf_readable: bool
    required_terms_present: bool
    errors: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.docx_readable and self.pdf_readable and self.required_terms_present


def _docx_text(path: Path) -> str:
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise ValueError("DOCX is missing or not a valid ZIP package")
    document = Document(path)
    return "\n".join(p.text for p in document.paragraphs)


def _pdf_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError("PDF is missing")
    try:
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    except ImportError:
        executable = shutil.which("pdftotext")
        if not executable:
            raise RuntimeError("pypdf or pdftotext is required for PDF validation")
        result = subprocess.run(
            [executable, str(path), "-"], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "pdftotext failed")
        return result.stdout


def validate_application_bundle(
    docx: Path, pdf: Path | None, required_terms: list[str]
) -> ValidationReport:
    errors: list[str] = []
    docx_text = ""
    pdf_text = ""
    docx_readable = False
    pdf_readable = False

    try:
        docx_text = _docx_text(docx)
        docx_readable = True
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(f"DOCX: {exc}")

    if pdf is not None:
        try:
            pdf_text = _pdf_text(pdf)
            pdf_readable = True
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"PDF: {exc}")

    combined = docx_text + "\n" + pdf_text
    required_terms_present = docx_readable and all(term in combined for term in required_terms)
    if not required_terms_present and docx_readable:
        errors.append("required terms are missing")

    return ValidationReport(
        docx_readable=docx_readable,
        pdf_readable=pdf_readable,
        required_terms_present=required_terms_present,
        errors=tuple(errors),
    )
