import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.application_archive import archive_application
from src.material_schema import ApplicationBundle


JOB = {
    "id": "job-1",
    "title": "产品经理",
    "company": "示例科技",
    "url": "https://example.test/job-1",
    "source": "zhaopin",
}


def _bundle(root: Path, suffix: str = "") -> ApplicationBundle:
    resume = root / f"resume{suffix}.docx"
    cover = root / f"cover{suffix}.docx"
    resume.write_bytes(b"resume")
    cover.write_bytes(b"cover")
    return ApplicationBundle(resume_docx=resume, cover_letter_docx=cover)


class ApplicationArchiveTests(unittest.TestCase):
    def test_rejected_confirmation_creates_no_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "documents"
            with patch("builtins.input", return_value="n"):
                with self.assertRaises(PermissionError):
                    archive_application(JOB, _bundle(root.parent), root)
            self.assertFalse((root / "applications").exists())

    def test_archive_copies_materials_and_appends_tracker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "documents"
            with patch("builtins.input", return_value="y"):
                record = archive_application(JOB, _bundle(root.parent), root)

            self.assertTrue(record.resume_docx.is_file())
            self.assertTrue(record.cover_letter_docx.is_file())
            self.assertTrue((record.archive_dir / "manifest.json").is_file())
            tracker = root.parent / "job_search_tracker.csv"
            self.assertEqual(len(tracker.read_text(encoding="utf-8").splitlines()), 2)
            self.assertTrue(record.archive_dir.is_relative_to(root))

    def test_repeated_archive_preserves_first_bundle_and_tracker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "documents"
            with patch("builtins.input", return_value="y"):
                first = archive_application(JOB, _bundle(root.parent), root)
                first_bytes = first.resume_docx.read_bytes()
                second = archive_application(JOB, _bundle(root.parent, "-new"), root)

            self.assertEqual(first.archive_dir, second.archive_dir)
            self.assertEqual(first_bytes, first.resume_docx.read_bytes())
            tracker = root.parent / "job_search_tracker.csv"
            self.assertEqual(len(tracker.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
