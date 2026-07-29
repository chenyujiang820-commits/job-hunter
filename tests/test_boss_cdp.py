"""Boss CDP 爬虫单元测试 — 解析逻辑不依赖 CDP/浏览器。"""

import json
import unittest

from crawlers.boss_cdp import (
    _parse_api_response,
    _to_job_summary,
    _parse_boss_salary,
    _inspect_boss_api_response,
    _resolve_city,
    _load_city_map,
)


class BossCityResolutionTests(unittest.TestCase):
    """验证城市代码解析。"""

    def test_resolves_known_city(self):
        name, code = _resolve_city("杭州")
        self.assertEqual(name, "杭州")
        self.assertEqual(code, "101210100")

    def test_resolves_lishui(self):
        name, code = _resolve_city("丽水")
        self.assertEqual(name, "丽水")

    def test_returns_original_on_unknown(self):
        name, code = _resolve_city("火星")
        self.assertEqual(name, "火星")
        self.assertEqual(code, "火星")

    def test_city_map_loaded(self):
        city_map = _load_city_map()
        self.assertIn("杭州", city_map)
        self.assertIn("北京", city_map)
        self.assertGreater(len(city_map), 10)


class BossApiResponseParsingTests(unittest.TestCase):
    """验证 BOSS API 返回值的解析。"""

    def test_parses_valid_json_array(self):
        raw = json.dumps([
            {"encrypt_job_id": "abc123", "title": "产品经理",
             "salary": "15-25K", "boss_name": "XX科技",
             "location": "杭州·余杭区"},
        ])
        result = _parse_api_response(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "产品经理")

    def test_api_access_error_requires_manual_intervention(self):
        with self.assertRaisesRegex(RuntimeError, "暂停人工处理"):
            _inspect_boss_api_response(json.dumps([{"error": 401}]))

    def test_returns_empty_for_none(self):
        self.assertEqual(_parse_api_response(None), [])

    def test_returns_empty_for_non_json(self):
        self.assertEqual(_parse_api_response("not json"), [])

    def test_returns_empty_for_error_items(self):
        raw = json.dumps([
            {"error": 401},
            {"encrypt_job_id": "ok", "title": "OK"},
        ])
        result = _parse_api_response(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "OK")

    def test_returns_empty_for_non_list(self):
        raw = json.dumps({"code": 0, "data": []})
        self.assertEqual(_parse_api_response(raw), [])


class BossToJobSummaryTests(unittest.TestCase):
    """验证 API 条目 → JobSummary 转换。"""

    def test_converts_full_entry(self):
        api_job = {
            "encrypt_job_id": "abc123",
            "title": "产品经理",
            "salary": "15-25K·14薪",
            "boss_name": "XX科技",
            "location": "杭州·余杭区",
            "experience": "3-5年",
            "education": "本科",
            "tags": "需求分析, Axure",
            "job_link": "https://www.zhipin.com/job_detail/abc123.html",
        }
        result = _to_job_summary(api_job, "产品经理", "杭州")

        self.assertEqual(result["id"], "abc123")
        self.assertEqual(result["title"], "产品经理")
        self.assertEqual(result["company"], "XX科技")
        self.assertEqual(result["location"], "杭州·余杭区")
        self.assertEqual(result["salary"]["min"], 15000)
        self.assertEqual(result["salary"]["max"], 25000)
        self.assertEqual(result["experience"], "3-5年")
        self.assertEqual(result["education"], "本科")
        self.assertEqual(result["tags"], "需求分析, Axure")
        self.assertEqual(result["source"], "boss")
        self.assertEqual(result["url"], "https://www.zhipin.com/job_detail/abc123.html")

    def test_handles_missing_fields(self):
        api_job = {
            "encrypt_job_id": "",
            "title": "测试",
            "salary": "",
            "boss_name": "",
            "location": "",
            "tags": "",
            "job_link": "",
        }
        result = _to_job_summary(api_job, "kw", "city")
        self.assertEqual(result["id"], "")
        self.assertEqual(result["title"], "测试")
        self.assertIsNone(result["salary"])


class BossSalaryParsingTests(unittest.TestCase):
    """验证 BOSS 薪资文本解析（复用 zhilian 解析器）。"""

    def test_parses_k_salary(self):
        result = _parse_boss_salary("15-25K")
        self.assertEqual(result["min"], 15000)
        self.assertEqual(result["max"], 25000)

    def test_parses_wan_salary(self):
        result = _parse_boss_salary("1.5-2.5万")
        self.assertEqual(result["min"], 15000)
        self.assertEqual(result["max"], 25000)

    def test_parses_negotiable(self):
        result = _parse_boss_salary("面议")
        self.assertTrue(result["negotiable"])

    def test_returns_none_for_empty(self):
        self.assertIsNone(_parse_boss_salary(""))
        self.assertIsNone(_parse_boss_salary(None))


class BossCrawlerInterfaceTests(unittest.TestCase):
    """验证 BossCdpCrawler 接口完整性。"""

    def test_has_search_all_method(self):
        from crawlers.boss_cdp import BossCdpCrawler
        crawler = BossCdpCrawler(9222)
        self.assertTrue(callable(crawler.search_all))

    def test_has_fetch_details_batch_method(self):
        from crawlers.boss_cdp import BossCdpCrawler
        crawler = BossCdpCrawler(9222)
        self.assertTrue(callable(crawler.fetch_details_batch))

    def test_search_and_search_all_return_list(self):
        from crawlers.boss_cdp import BossCdpCrawler
        crawler = BossCdpCrawler(9222)
        # 无论 CDP 是否可用，都应返回 list
        r1 = crawler.search("test", city="杭州")
        r2 = crawler.search_all("test", city="杭州", max_pages=1)
        self.assertIsInstance(r1, list)
        self.assertIsInstance(r2, list)


class CoordinatorParamsTests(unittest.TestCase):
    """验证 coordinator 新参数。"""

    def test_search_and_store_accepts_new_params(self):
        from crawlers.coordinator import search_and_store
        # 验证函数签名接受新参数（不实际执行搜索）
        import inspect
        sig = inspect.signature(search_and_store)
        params = list(sig.parameters.keys())
        self.assertIn("max_pages", params)
        self.assertIn("fetch_details", params)
        self.assertIn("max_details", params)


if __name__ == "__main__":
    unittest.main()
