import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.application_workflow import generate_application_bundle
from src.material_schema import ApplicationDraft


JOB = {"title": "产品经理", "company": "示例科技", "url": "https://example.test/job-1"}
DRAFT = ApplicationDraft(
    job=JOB,
    candidate_facts={"姓名": "候选人"},
    resume_sections={
        "summary": "通信工程背景",
        "experience": "需求分析",
        "education": "本科",
        "skills": "物联网",
    },
    cover_letter_text="申请技术型产品经理岗位。",
    required_keywords=["通信工程"],
)


class ApplicationWorkflowTests(unittest.TestCase):
    def test_rejected_material_generation_creates_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("src.application_workflow.require_user_confirmation", return_value=False):
                with self.assertRaises(PermissionError):
                    generate_application_bundle(JOB, DRAFT, Path("templates"), root)
            self.assertFalse((root / "resume.docx").exists())

    def test_selected_job_generates_both_formats_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resume_pdf = root / "pdf" / "resume.pdf"
            fake_cover_pdf = root / "pdf" / "cover_letter.pdf"

            def fake_convert(docx, output_dir, soffice="soffice"):
                output_dir.mkdir(parents=True, exist_ok=True)
                target = output_dir / f"{docx.stem}.pdf"
                target.write_bytes(b"pdf")
                return target

            class Report:
                passed = True
                errors = ()

            with patch("src.application_workflow.require_user_confirmation", return_value=True), patch(
                "src.application_workflow.convert_docx_to_pdf", side_effect=fake_convert
            ), patch(
                "src.application_workflow.validate_application_bundle", return_value=Report()
            ):
                bundle = generate_application_bundle(
                    JOB, DRAFT, Path("templates"), root
                )

            self.assertTrue(bundle.resume_docx.is_file())
            self.assertTrue(bundle.cover_letter_docx.is_file())
            self.assertEqual(bundle.resume_pdf, fake_resume_pdf)
            self.assertEqual(bundle.cover_letter_pdf, fake_cover_pdf)


if __name__ == "__main__":
    unittest.main()
