import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs/portal-research/zhaopin.md"
FIXTURES = ROOT / "docs/portal-research/zhaopin-fixtures/README.md"


class ZhaopinResearchRecordTests(unittest.TestCase):
    def _research_content(self):
        self.assertTrue(RESEARCH.is_file(), "zhaopin.md research record is missing")
        return RESEARCH.read_text(encoding="utf-8")

    def test_research_record_exists_and_declares_access_decision(self):
        content = self._research_content()

        for field in (
            "Research date",
            "Search entry",
            "Detail entry",
            "Search public status",
            "Detail public status",
            "robots.txt",
            "Service terms",
            "Access requirements",
            "Rate-limit observations",
            "Access decision",
        ):
            with self.subTest(field=field):
                self.assertIn(field, content)

        decisions = ("GO", "NO-GO", "MANUAL_URL_ONLY")
        self.assertTrue(any(f"Access decision: {decision}" in content for decision in decisions))

    def test_record_lists_normalized_search_and_detail_fields(self):
        content = self._research_content()
        required_fields = (
            "id",
            "title",
            "company",
            "location",
            "salary",
            "experience",
            "education",
            "date",
            "url",
            "source",
        )

        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", content)

    def test_record_does_not_depend_on_login_or_captcha_bypass(self):
        content = self._research_content().lower()
        forbidden_claims = (
            "captcha bypass",
            "绕过验证码",
            "cookie required",
            "logged-in session required",
            "登录态必需",
        )

        for claim in forbidden_claims:
            with self.subTest(claim=claim):
                self.assertNotIn(claim, content)

    def test_fixture_readme_requires_minimal_sanitized_search_and_detail_samples(self):
        self.assertTrue(FIXTURES.is_file())
        content = FIXTURES.read_text(encoding="utf-8").lower()

        for marker in (
            "search",
            "detail",
            "sensitive account data removed",
            "no cookies",
            "no tokens",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, content)


if __name__ == "__main__":
    unittest.main()
