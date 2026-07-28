"""Read-only metadata inventory for local candidate source documents."""

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


@dataclass(frozen=True)
class DocumentRecord:
    path: Path
    extension: str
    size_bytes: int
    relative_folder: str


def inventory_candidate_documents(root: Path) -> list[DocumentRecord]:
    """Return supported document metadata without opening or modifying source files."""
    records = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        relative_path = path.relative_to(root)
        relative_folder = relative_path.parent.as_posix()
        records.append(
            DocumentRecord(
                path=path,
                extension=path.suffix.lower(),
                size_bytes=path.stat().st_size,
                relative_folder=relative_folder if relative_folder != "." else ".",
            )
        )

    return sorted(records, key=lambda record: record.path.relative_to(root).as_posix().casefold())
