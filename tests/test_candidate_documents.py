import os
import tempfile
import unittest
from pathlib import Path

from tools.inventory_candidate_documents import inventory_candidate_documents
from tools.profile_state import (
    ProfileChange,
    ProfileProposal,
    apply_confirmed_profile_changes,
    load_confirmed_profile,
    write_profile_proposal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CandidateDocumentTests(unittest.TestCase):
    def test_inventory_returns_supported_files_in_deterministic_order(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "documents"
            (root / "candidate").mkdir(parents=True)
            (root / "zeta.txt").write_text("synthetic")
            (root / "candidate" / "alpha.PDF").write_bytes(b"pdf")
            (root / "candidate" / "beta.docx").write_bytes(b"docx")
            (root / "notes.md").write_text("synthetic")
            (root / "ignored.csv").write_text("synthetic")

            records = inventory_candidate_documents(root)

            self.assertEqual(
                [record.path.relative_to(root).as_posix() for record in records],
                ["candidate/alpha.PDF", "candidate/beta.docx", "notes.md", "zeta.txt"],
            )
            self.assertEqual([record.extension for record in records], [".pdf", ".docx", ".md", ".txt"])
            self.assertEqual([record.size_bytes for record in records], [3, 4, 9, 9])
            self.assertEqual([record.relative_folder for record in records], ["candidate", "candidate", ".", "."])

    def test_inventory_returns_no_records_for_an_empty_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.assertEqual(inventory_candidate_documents(Path(temporary_directory)), [])

    def test_proposal_does_not_mutate_confirmed_profile_and_records_sources(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            profile_path = root / "profiles" / "candidate-profile.md"
            profile_path.parent.mkdir()
            (root / "documents").mkdir()
            (root / "documents" / "synthetic.txt").write_text("synthetic")
            profile_path.write_text("# Candidate Profile\n\n## Confirmed Facts\n\n- Name: Synthetic Candidate\n")
            before = profile_path.read_text()
            proposal = ProfileProposal(
                title="Review synthetic update",
                changes=[ProfileChange("Location", "Lishui", Path("documents/synthetic.txt"))],
            )

            proposal_path = write_profile_proposal(profile_path, proposal)

            self.assertNotEqual(proposal_path, profile_path)
            self.assertEqual(profile_path.read_text(), before)
            self.assertTrue(proposal_path.is_file())
            self.assertIn("documents/synthetic.txt", proposal_path.read_text())
            self.assertIn("Confirmation: PENDING", proposal_path.read_text())

    def test_proposal_and_application_reject_invalid_source_paths_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            profile_path = self._write_synthetic_profile(root)
            outside_source = root / "outside.txt"
            outside_source.write_text("synthetic")
            unsupported_source = root / "documents" / "unsupported.csv"
            unsupported_source.write_text("synthetic")
            invalid_sources = [
                outside_source,
                root / "documents" / "missing.txt",
                unsupported_source,
            ]
            before = profile_path.read_text()

            for source_path in invalid_sources:
                with self.subTest(source_path=source_path):
                    change = ProfileChange("Location", "Lishui", source_path, "CONFIRMED")
                    with self.assertRaisesRegex(ValueError, "source"):
                        write_profile_proposal(profile_path, ProfileProposal("Invalid source", [change]))
                    with self.assertRaisesRegex(ValueError, "source"):
                        apply_confirmed_profile_changes(profile_path, [change])
                    self.assertEqual(profile_path.read_text(), before)
                    self.assertFalse((root / "runtime" / "profile-proposals").exists())

    def test_proposal_and_application_reject_traversal_source_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            profile_path = self._write_synthetic_profile(root)
            traversal_source = Path("documents/../documents/synthetic.txt")

            self._assert_source_rejected_without_writes(profile_path, traversal_source)

    def test_proposal_and_application_reject_symlink_source_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            profile_path = self._write_synthetic_profile(root)
            symlink_path = root / "documents" / "linked.txt"
            try:
                os.symlink(self._source_path(profile_path), symlink_path)
            except OSError as error:
                self.skipTest(f"Windows symlink creation prerequisite unavailable: {error}")

            self.assertTrue(symlink_path.is_symlink())
            self._assert_source_rejected_without_writes(profile_path, symlink_path)

    def test_proposal_path_is_under_the_ignored_runtime_rule(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            profile_path = self._write_synthetic_profile(root)
            change = ProfileChange("Location", "Lishui", self._source_path(profile_path))

            proposal_path = write_profile_proposal(profile_path, ProfileProposal("Runtime proposal", [change]))

            self.assertIn("runtime/", (PROJECT_ROOT / ".gitignore").read_text())
            self.assertTrue(proposal_path.is_relative_to(root / "runtime" / "profile-proposals"))

    def test_apply_rejects_changes_without_an_explicit_confirmation_marker(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = self._write_synthetic_profile(Path(temporary_directory))

            with self.assertRaisesRegex(ValueError, "CONFIRMED"):
                apply_confirmed_profile_changes(
                    profile_path,
                    [ProfileChange("Location", "Lishui", self._source_path(profile_path))],
                )

            self.assertEqual(load_confirmed_profile(profile_path).facts["Location"], "Hangzhou")

    def test_apply_updates_only_explicitly_confirmed_changes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = self._write_synthetic_profile(Path(temporary_directory))

            apply_confirmed_profile_changes(
                profile_path,
                [
                    ProfileChange(
                        "Location",
                        "Lishui",
                        self._source_path(profile_path),
                        confirmation_marker="CONFIRMED",
                    )
                ],
            )

            profile = load_confirmed_profile(profile_path)
            self.assertEqual(profile.facts, {"Name": "Synthetic Candidate", "Location": "Lishui"})

    def test_confirmed_profile_excludes_field_lines_in_proposal_history(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = self._write_synthetic_profile(Path(temporary_directory))

            profile = load_confirmed_profile(profile_path)

            self.assertNotIn("Field", profile.facts)
            self.assertEqual(profile.facts["Location"], "Hangzhou")

    def test_mixed_confirmation_batch_leaves_profile_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = self._write_synthetic_profile(Path(temporary_directory))
            before = profile_path.read_text()
            source_path = self._source_path(profile_path)

            with self.assertRaisesRegex(ValueError, "CONFIRMED"):
                apply_confirmed_profile_changes(
                    profile_path,
                    [
                        ProfileChange("Location", "Lishui", source_path, "CONFIRMED"),
                        ProfileChange("Name", "Changed Candidate", source_path),
                    ],
                )

            self.assertEqual(profile_path.read_text(), before)

    @staticmethod
    def _write_synthetic_profile(root: Path) -> Path:
        profile_path = root / "profiles" / "candidate-profile.md"
        profile_path.parent.mkdir()
        documents_path = root / "documents"
        documents_path.mkdir()
        (documents_path / "synthetic.txt").write_text("synthetic")
        profile_path.write_text(
            "# Candidate Profile\n\n## Confirmed Facts\n\n"
            "- Name: Synthetic Candidate\n"
            "- Location: Hangzhou\n\n"
            "## Proposal History\n\n"
            "- Field: Proposal-only value\n"
        )
        return profile_path

    @staticmethod
    def _source_path(profile_path: Path) -> Path:
        return profile_path.parent.parent / "documents" / "synthetic.txt"

    def _assert_source_rejected_without_writes(self, profile_path: Path, source_path: Path) -> None:
        before = profile_path.read_text()
        change = ProfileChange("Location", "Lishui", source_path, "CONFIRMED")
        with self.assertRaisesRegex(ValueError, "source"):
            write_profile_proposal(profile_path, ProfileProposal("Invalid source", [change]))
        with self.assertRaisesRegex(ValueError, "source"):
            apply_confirmed_profile_changes(profile_path, [change])
        self.assertEqual(profile_path.read_text(), before)
        self.assertFalse((profile_path.parent.parent / "runtime" / "profile-proposals").exists())


if __name__ == "__main__":
    unittest.main()
