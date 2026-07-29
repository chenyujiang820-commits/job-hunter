"""投递状态跟踪单元测试。"""

import unittest
from pathlib import Path
from unittest.mock import patch

import src.outcome as oc


class OutcomeTrackerTests(unittest.TestCase):
    def setUp(self):
        # 用临时路径隔离测试
        self._tmp = Path("runtime/test_tracker.json")
        self._orig = oc.TRACKER_PATH
        oc.TRACKER_PATH = self._tmp

    def tearDown(self):
        oc.TRACKER_PATH = self._orig
        if self._tmp.exists():
            self._tmp.unlink()
        tmp = self._tmp.with_name(f".{self._tmp.name}.tmp")
        if tmp.exists():
            tmp.unlink()

    def _job(self, key="test-001"):
        return {
            "job_key": key,
            "title": "产品经理",
            "company": "测试公司",
            "location": "杭州",
            "url": "https://example.com/job/1",
        }

    def test_record_and_check_application(self):
        self.assertFalse(oc.has_applied("test-001"))
        oc.record_application(self._job("test-001"), status="收藏")
        self.assertTrue(oc.has_applied("test-001"))

    def test_duplicate_application_raises(self):
        oc.record_application(self._job("test-001"))
        with self.assertRaises(ValueError):
            oc.record_application(self._job("test-001"))

    def test_update_status_flow(self):
        job = self._job("test-002")
        oc.record_application(job, status="收藏")

        record = oc.update_status("test-002", "已投递", note="投递了官网")
        self.assertEqual(record.status, "已投递")
        self.assertIsNotNone(record.applied_date)

        record = oc.update_status("test-002", "一面", note="电话面试")
        self.assertEqual(record.status, "一面")
        self.assertIn("电话面试", str(record.note))

    def test_update_nonexistent_returns_none(self):
        self.assertIsNone(oc.update_status("no-such", "已投递"))

    def test_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            oc.record_application(self._job(), status="不存在的状态")

    def test_missing_job_key_raises(self):
        with self.assertRaises(ValueError):
            oc.record_application({"title": "无key"})

    def test_get_applications_and_summary(self):
        oc.record_application(self._job("a"), status="收藏")
        oc.record_application(self._job("b"), status="已投递")
        oc.record_application(self._job("c"), status="一面")

        apps = oc.get_applications()
        self.assertEqual(len(apps), 3)

        summary = oc.summary()
        self.assertEqual(summary["总计"], 3)
        self.assertEqual(summary.get("收藏", 0), 1)


if __name__ == "__main__":
    unittest.main()
