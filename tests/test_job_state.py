import json
import tempfile
import unittest
from pathlib import Path


from src.job_state import canonical_job_key, merge_seen_jobs


class JobStateTests(unittest.TestCase):
    def test_canonical_key_prefers_source_and_id(self):
        job = {
            "source": "zhaopin_manual",
            "id": "CC123",
            "url": "https://example.com/one",
            "company": "公司 A",
            "title": "产品经理",
        }

        self.assertEqual(canonical_job_key(job), "zhaopin_manual:CC123")

    def test_canonical_key_falls_back_to_url_then_company_title(self):
        by_url = {"url": "HTTPS://Example.com/jobs/1/"}
        by_text = {"company": " 示例 公司 ", "title": " 产品 经理 "}

        self.assertEqual(canonical_job_key(by_url), "https://example.com/jobs/1")
        self.assertEqual(canonical_job_key(by_text), "text:示例公司:产品经理")

    def test_merge_seen_jobs_is_additive_and_updates_nonempty_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen_jobs.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "jobs": [
                            {
                                "job_key": "zhaopin:1",
                                "source": "zhaopin",
                                "id": "1",
                                "title": "产品经理",
                                "company": "旧公司名",
                                "location": None,
                                "first_seen": "2026-07-27",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = merge_seen_jobs(
                path,
                [
                    {
                        "source": "zhaopin",
                        "id": "1",
                        "title": "产品经理",
                        "company": "新公司名",
                        "location": "丽水",
                    },
                    {
                        "source": "zhaopin",
                        "id": "2",
                        "title": "产品助理",
                        "company": "另一家公司",
                    },
                ],
                today="2026-07-28",
            )

            state = json.loads(path.read_text(encoding="utf-8"))
            jobs = {job["job_key"]: job for job in state["jobs"]}

            self.assertEqual(report.new_count, 1)
            self.assertEqual(report.duplicate_count, 1)
            self.assertEqual(report.updated_count, 1)
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs["zhaopin:1"]["first_seen"], "2026-07-27")
            self.assertEqual(jobs["zhaopin:1"]["last_seen"], "2026-07-28")
            self.assertEqual(jobs["zhaopin:1"]["location"], "丽水")

    def test_merge_seen_jobs_preserves_existing_entries_when_batch_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen_jobs.json"
            report = merge_seen_jobs(path, [], today="2026-07-28")

            self.assertEqual(report.new_count, 0)
            self.assertEqual(report.duplicate_count, 0)
            self.assertEqual(report.updated_count, 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["jobs"], [])


if __name__ == "__main__":
    unittest.main()
