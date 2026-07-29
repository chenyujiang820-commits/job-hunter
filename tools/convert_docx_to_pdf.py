"""Convert DOCX materials to PDF.

Windows: uses docx2pdf (Word COM)
Linux/macOS: uses LibreOffice soffice --headless
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class MaterialToolUnavailable(RuntimeError):
    """Raised when a required local document tool is unavailable."""


def convert_docx_to_pdf(
    docx: Path,
    output_dir: Path,
    soffice: str = "soffice",
) -> Path:
    if not docx.is_file():
        raise FileNotFoundError(f"DOCX does not exist: {docx}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 路径 A: docx2pdf (Windows Word COM) — 最快，效果最好
    try:
        from docx2pdf import convert
        expected = output_dir / f"{docx.stem}.pdf"
        convert(str(docx), str(expected))
        if expected.is_file():
            return expected
    except Exception:
        pass

    # 路径 B: LibreOffice headless
    executable = soffice if Path(soffice).is_file() else shutil.which(soffice)
    if not executable:
        raise MaterialToolUnavailable(
            "需要 Word (Windows) 或 LibreOffice 来完成 DOCX→PDF 转换。"
            "Windows: pip install docx2pdf\n"
            "其他: apt install libreoffice"
        )

    completed = subprocess.run(
        [
            executable, "--headless", "--convert-to", "pdf",
            "--outdir", str(output_dir), str(docx),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    expected = output_dir / f"{docx.stem}.pdf"
    if completed.returncode != 0 or not expected.is_file():
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"DOCX to PDF conversion failed: {detail}")
    return expected
