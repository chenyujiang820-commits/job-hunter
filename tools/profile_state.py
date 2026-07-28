"""Helpers for reading confirmed facts and gating profile changes."""

from dataclasses import dataclass
from pathlib import Path


CONFIRMATION_MARKER = "CONFIRMED"
CONFIRMED_FACTS_HEADING = "## Confirmed Facts"
SUPPORTED_SOURCE_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


@dataclass(frozen=True)
class CandidateProfile:
    facts: dict[str, str]


@dataclass(frozen=True)
class ProfileChange:
    field: str
    value: str
    source_path: Path
    confirmation_marker: str | None = None


@dataclass(frozen=True)
class ProfileProposal:
    title: str
    changes: list[ProfileChange]


def load_confirmed_profile(path: Path) -> CandidateProfile:
    """Read facts from the confirmed-facts section, excluding all proposal text."""
    _, facts, _ = _profile_sections(path.read_text(encoding="utf-8"))
    return CandidateProfile(facts)


def write_profile_proposal(path: Path, proposal: ProfileProposal) -> Path:
    """Write a reviewable proposal beneath ignored runtime state, never beside the profile."""
    _validate_change_sources(path, proposal.changes)
    proposal_directory = path.parent.parent / "runtime" / "profile-proposals"
    proposal_directory.mkdir(parents=True, exist_ok=True)
    proposal_path = proposal_directory / f"{path.stem}-proposal.md"
    lines = [f"# {proposal.title}", "", f"Confirmed profile: {path}", "", "## Proposed Changes", ""]
    for change in proposal.changes:
        marker = change.confirmation_marker or "PENDING"
        lines.extend(
            [
                f"- Field: {change.field}",
                f"  Value: {change.value}",
                f"  Source: {change.source_path.as_posix()}",
                f"  Confirmation: {marker}",
            ]
        )
    proposal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return proposal_path


def apply_confirmed_profile_changes(path: Path, changes: list[ProfileChange]) -> None:
    """Apply a batch only when every change has an explicit confirmation marker."""
    _validate_change_sources(path, changes)
    if any(change.confirmation_marker != CONFIRMATION_MARKER for change in changes):
        raise ValueError("Every profile change requires a CONFIRMED confirmation marker.")

    text = path.read_text(encoding="utf-8")
    prefix, facts, suffix = _profile_sections(text)
    for change in changes:
        facts[change.field] = change.value

    confirmed_lines = [f"- {field}: {value}" for field, value in facts.items()]
    separator = "" if not suffix or suffix.startswith("\n") else "\n"
    path.write_text(prefix + "\n".join(confirmed_lines) + separator + suffix, encoding="utf-8")


def _validate_change_sources(profile_path: Path, changes: list[ProfileChange]) -> None:
    project_root = profile_path.resolve().parent.parent
    documents_root = (project_root / "documents").resolve()
    for change in changes:
        source_path = change.source_path
        if ".." in source_path.parts:
            raise ValueError("Profile change source must not contain a '..' path component.")
        unresolved_source = source_path if source_path.is_absolute() else project_root / source_path
        if _contains_symlink(unresolved_source):
            raise ValueError("Profile change source must not be a symlink or have a symlink parent.")
        resolved_source = unresolved_source.resolve()
        if not resolved_source.is_relative_to(documents_root):
            raise ValueError("Profile change source must resolve under the project documents/ root.")
        if not resolved_source.is_file():
            raise ValueError("Profile change source must be an existing file.")
        if resolved_source.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
            raise ValueError("Profile change source must use a supported document extension.")


def _contains_symlink(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def _profile_sections(text: str) -> tuple[str, dict[str, str], str]:
    heading_start = text.find(CONFIRMED_FACTS_HEADING)
    if heading_start == -1:
        raise ValueError(f"Profile is missing {CONFIRMED_FACTS_HEADING!r}.")

    facts_start = text.find("\n", heading_start) + 1
    next_heading = text.find("\n## ", facts_start)
    facts_end = len(text) if next_heading == -1 else next_heading + 1
    facts = {}
    for line in text[facts_start:facts_end].splitlines():
        if line.startswith("- ") and ":" in line:
            field, value = line[2:].split(":", 1)
            facts[field.strip()] = value.strip()
    return text[:facts_start], facts, text[facts_end:]
