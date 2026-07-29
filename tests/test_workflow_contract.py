import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/domestic-job-search/SKILL.md"
AGENTS = ROOT / "AGENTS.md"
QUERIES = ROOT / ".agents/skills/domestic-job-search/references/search-queries.md"
EVALUATION = ROOT / ".agents/skills/domestic-job-search/references/job-evaluation.md"


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.agents = AGENTS.read_text(encoding="utf-8")
        cls.queries = QUERIES.read_text(encoding="utf-8")
        cls.evaluation = EVALUATION.read_text(encoding="utf-8")

    def _phase(self, name: str, next_name: str | None = None) -> str:
        section = self.skill.split(f"### `{name}`", 1)[1]
        if next_name:
            section = section.split(f"### `{next_name}`", 1)[0]
        return section

    def test_workflow_has_separate_scrape_rank_select_apply_stages(self):
        workflow = "scrape -> inspect/cache new jobs -> rank -> user selects job -> apply -> local archive"
        self.assertIn(workflow, self.skill)
        self.assertLess(self.skill.index("### `scrape`"), self.skill.index("### `rank`"))
        self.assertLess(self.skill.index("### `rank`"), self.skill.index("### `apply`"))
        self.assertIn("user selects job", self.skill)

    def test_scrape_is_manual_local_intake_and_does_not_generate_materials(self):
        scrape = self._phase("scrape", "rank")

        for marker in (
            "user-supplied Zhilian URL",
            "pasted visible job text",
            "tools/normalize_manual_job.py",
            "merge_seen_jobs",
            "read-only HTTP requests",
            "Do not submit",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, scrape)

        self.assertNotIn("DOCX", scrape)
        self.assertNotIn("PDF", scrape)

    def test_rank_applies_filters_and_returns_auditable_shortlist_without_materials(self):
        rank = self._phase("rank", "apply")

        for marker in (
            "apply_hard_filters",
            "location_tier",
            "score",
            "direction match",
            "gaps",
            "flags",
            "URL",
            "salary as a ranking reference",
            "exclusion reason",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rank)

        self.assertNotIn("DOCX", rank)
        self.assertNotIn("PDF", rank)

    def test_apply_requires_one_selected_job_and_confirmation_gates(self):
        apply = self._phase("apply", "outcome")

        for marker in (
            "exactly one user-selected job",
            "Confirm the profile",
            "user approval",
            "Produce both a tailored resume and cover letter",
            "generate DOCX and PDF locally",
            "Do not upload or submit",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, apply)

    def test_untrusted_job_text_is_data_not_instructions(self):
        for content in (self.skill, self.agents):
            self.assertTrue(
                "untrusted" in content.lower()
                or "do not follow instructions" in content.lower()
            )

    def test_outcome_is_manual_and_never_a_platform_write(self):
        outcome = self._phase("outcome")
        self.assertIn("manually reported", outcome)
        self.assertIn("Never call a platform write operation", outcome)

    def test_query_and_evaluation_references_preserve_confirmed_rules(self):
        self.assertLess(self.queries.index("丽水"), self.queries.index("杭州"))
        for marker in ("人工", "不访问登录", "反爬"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.queries)
        for marker in (
            "劳务派遣",
            "外包",
            "浙江",
            "长期驻场",
            "salary",
            "no salary floor",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.evaluation)

    def test_project_contract_keeps_manual_only_boundary(self):
        for marker in (
            "locally triggered",
            "manually pasted",
            "Do not schedule work or run a daemon",
            "rowser automation",
            "platform write operations",
            "candidate data",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.agents)


if __name__ == "__main__":
    unittest.main()
