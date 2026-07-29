import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.apply import find_job, load_jobs


class ApplySelectionTests(unittest.TestCase):
    def test_load_jobs_returns_ranked_and_filtered_shortlist(self):
        jobs = [
            {
                "id": "outside-1",
                "title": "产品经理",
                "company": "外省公司",
                "location": "北京市",
                "salary": {"min": 12000, "max": 18000},
            },
            {
                "id": "other-zhejiang-1",
                "title": "产品经理",
                "company": "杭州公司",
                "location": "杭州市",
                "salary": {"min": 9000, "max": 14000},
            },
            {
                "id": "lishui-1",
                "title": "物联网产品经理",
                "company": "丽水公司",
                "location": "丽水市",
                "salary": {"min": 7000, "max": 10000},
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "seen_jobs.json"
            cache.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False), encoding="utf-8")

            with patch("tools.apply.SEEN_JOBS_PATH", cache):
                ranked = load_jobs()

        self.assertEqual([job["id"] for job in ranked], ["lishui-1", "other-zhejiang-1"])
        self.assertEqual(ranked[0]["_tier"], "lishui")
        self.assertIn("_direction_score", ranked[0])
        self.assertIn("_flags", ranked[0])

    def test_find_job_cannot_select_filtered_job_by_id(self):
        ranked_jobs = [
            {
                "id": "lishui-1",
                "job_key": "zhaopin:lishui-1",
                "title": "产品经理",
            }
        ]

        self.assertIsNone(find_job(ranked_jobs, job_id="outside-1"))
        self.assertEqual(find_job(ranked_jobs, job_id="zhaopin:lishui-1"), ranked_jobs[0])


if __name__ == "__main__":
    unittest.main()
