import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectContractTests(unittest.TestCase):
    def test_codex_contract_files_exist(self):
        expected = [
            "AGENTS.md",
            ".agents/skills/domestic-job-search/SKILL.md",
            ".agents/skills/domestic-job-search/references/candidate-profile.md",
            ".agents/skills/domestic-job-search/references/job-evaluation.md",
            ".agents/skills/domestic-job-search/references/search-queries.md",
            "documents/README.md",
        ]

        for relative_path in expected:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_skill_defines_codex_native_workflow(self):
        content = (ROOT / ".agents/skills/domestic-job-search/SKILL.md").read_text()

        for phase in ("scrape", "rank", "apply", "outcome"):
            with self.subTest(phase=phase):
                self.assertIn(phase, content)
        self.assertIn("scrape -> inspect/cache new jobs -> rank -> user selects job -> apply -> local archive", content)
        self.assertIn("does not depend on Claude Code slash-command execution", content)

    def test_manual_access_and_stop_conditions_are_protected(self):
        agents = (ROOT / "AGENTS.md").read_text()

        required_phrases = (
            "The MVP uses only manually triggered, public, read-only Zhilian search and detail access",
            "Stop immediately on login, CAPTCHA, SMS verification, or anti-bot pages",
            "Do not schedule work or run a daemon",
            "browser automation",
            "uploads",
            "submissions",
            "chat",
            "replies",
            "platform write operations",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, agents)

    def test_dependency_live_access_and_git_actions_require_authorization(self):
        agents = (ROOT / "AGENTS.md").read_text()

        self.assertIn(
            "Do not install or upgrade dependencies, access live portals, or commit/push/stash unless explicitly authorized",
            agents,
        )

    def test_apply_gates_and_material_requirements_are_protected(self):
        skill = (ROOT / ".agents/skills/domestic-job-search/SKILL.md").read_text()
        apply_section = skill.split("### `apply`", 1)[1].split("### `outcome`", 1)[0]

        required_phrases = (
            "Accept exactly one user-selected job",
            "Confirm the profile and user approval before drafting",
            "Produce both a tailored resume and cover letter for that selected job only",
            "Validate facts",
            "reviewer assessment",
            "user approval",
            "generate DOCX and PDF locally",
            "Do not upload or submit",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, apply_section)

    def test_local_only_and_future_sync_constraints_are_protected(self):
        agents = (ROOT / "AGENTS.md").read_text()
        readme = (ROOT / "documents/README.md").read_text()

        for phrase in (
            "candidate data",
            "generated materials",
            "tracker state",
            "scraper state",
            "email contents local",
            "Do not sync externally",
            "explicit, disabled adapter",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, agents)
        self.assertIn("mail/", readme)

    def test_candidate_constraints_are_recorded(self):
        profile = (ROOT / ".agents/skills/domestic-job-search/references/candidate-profile.md").read_text()
        evaluation = (ROOT / ".agents/skills/domestic-job-search/references/job-evaluation.md").read_text()

        for phrase in (
            "bachelor degree",
            "former graduate",
            "communications-engineering",
            "party-member",
            "Lishui",
            "Hangzhou",
            "Jinhua",
            "other Zhejiang",
            "dispatch",
            "outsourcing",
            "no salary floor",
            "on-site",
            "moderate travel",
            "long-term on-site assignment",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in profile or phrase in evaluation)

    def test_documents_guide_names_supported_sources_and_layout(self):
        content = (ROOT / "documents/README.md").read_text()

        for source_type in ("PDF", "DOCX", "Markdown", "plain text"):
            with self.subTest(source_type=source_type):
                self.assertIn(source_type, content)
        for directory in ("documents/", "documents/candidate/", "documents/templates/"):
            with self.subTest(directory=directory):
                self.assertIn(directory, content)

    def test_ignore_rules_keep_local_job_search_data(self):
        content = (ROOT / ".gitignore").read_text()

        for ignored_path in (
            "documents/**",
            "job_search_tracker.csv",
            "job_scraper/**",
            "generated/",
            "runtime/",
            "mail/**",
        ):
            with self.subTest(ignored_path=ignored_path):
                self.assertIn(ignored_path, content)
        self.assertIn("!documents/README.md", content)
        self.assertIn("!documents/templates/", content)


if __name__ == "__main__":
    unittest.main()
