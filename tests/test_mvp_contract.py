import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MvpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    def test_readme_describes_local_mvp_flow(self):
        for marker in ("scrape", "rank", "apply", "outcome", "DOCX", "PDF"):
            self.assertIn(marker, self.readme)

    def test_readme_keeps_platform_writes_out_of_scope(self):
        for marker in ("不自动上传", "不自动", "本地保存", "paused_manual_intervention"):
            self.assertIn(marker, self.readme)

    def test_project_contract_keeps_candidate_data_local(self):
        self.assertIn("Keep candidate data", self.agents)
        self.assertIn("platform write operations", self.agents)


if __name__ == "__main__":
    unittest.main()
