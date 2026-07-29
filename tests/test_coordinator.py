import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crawlers.access_guard import ManualInterventionRequired
from crawlers.coordinator import search_and_store


class FakeCrawler:
    def __init__(self, jobs=None, error=None):
        self.jobs = jobs or []
        self.error = error

    def search(self, keyword, city):
        if self.error:
            raise self.error
        return list(self.jobs)

    def fetch_detail(self, url):
        return "职位详情"


class CoordinatorTests(unittest.TestCase):
    def test_manual_intervention_is_returned_as_paused_status(self):
        crawler = FakeCrawler(
            error=ManualInterventionRequired("验证码", platform="zhaopin")
        )
        with patch("crawlers.coordinator.CRAWLERS", {"zhaopin": crawler}):
            result = search_and_store("产品经理", city="丽水")

        self.assertEqual(result["status"], "paused_manual_intervention")
        self.assertIn("暂停人工处理", result["message"])

    def test_total_new_counts_merged_jobs(self):
        crawler = FakeCrawler(
            jobs=[
                {
                    "id": "job-1",
                    "title": "产品经理",
                    "company": "示例公司",
                    "location": "丽水",
                    "url": "https://example.test/job-1",
                    "source": "zhaopin",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "seen_jobs.json"
            with patch("crawlers.coordinator.CRAWLERS", {"zhaopin": crawler}), patch(
                "crawlers.coordinator.SEEN_JOBS_PATH", state_path
            ):
                result = search_and_store("产品经理", city="丽水")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["total_fetched"], 1)
        self.assertEqual(result["total_new"], 1)


if __name__ == "__main__":
    unittest.main()
