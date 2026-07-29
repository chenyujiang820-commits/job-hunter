"""智联爬虫单元测试 — 解析逻辑不依赖网络请求。"""

import unittest

from crawlers.zhilian import (
    _parse_salary,
    _job_id_from_url,
    _build_search_url,
    ZhilianCrawler,
)


class SalaryParsingTests(unittest.TestCase):
    """验证薪资文本解析逻辑。"""

    def test_parses_k_range_with_13_salary(self):
        result = _parse_salary("8-12K·13薪")
        self.assertEqual(result["min"], 8000)
        self.assertEqual(result["max"], 12000)
        self.assertEqual(result["unit"], "month")
        self.assertEqual(result["months_per_year"], 13)
        self.assertFalse(result["negotiable"])

    def test_parses_wan_range(self):
        result = _parse_salary("1.5-2万")
        self.assertEqual(result["min"], 15000)
        self.assertEqual(result["max"], 20000)
        self.assertEqual(result["unit"], "month")

    def test_parses_qian_range(self):
        result = _parse_salary("8千-1.2万")
        self.assertEqual(result["min"], 8000)
        self.assertEqual(result["max"], 12000)

    def test_parses_yearly_salary(self):
        result = _parse_salary("15-20万/年")
        self.assertEqual(result["min"], 150000)
        self.assertEqual(result["max"], 200000)
        self.assertEqual(result["unit"], "year")

    def test_parses_single_value(self):
        result = _parse_salary("8K")
        self.assertEqual(result["min"], 8000)
        self.assertEqual(result["max"], 8000)

    def test_parses_negotiable(self):
        result = _parse_salary("面议")
        self.assertEqual(result["min"], None)
        self.assertEqual(result["max"], None)
        self.assertTrue(result["negotiable"])

    def test_parses_negotiable_with_number(self):
        result = _parse_salary("面议·15K")
        self.assertTrue(result["negotiable"])

    def test_returns_none_for_empty_or_none(self):
        self.assertIsNone(_parse_salary(""))
        self.assertIsNone(_parse_salary("   "))
        self.assertIsNone(_parse_salary(None))

    def test_uses_chinese_dash_separator(self):
        result = _parse_salary("10–15K")
        self.assertEqual(result["min"], 10000)
        self.assertEqual(result["max"], 15000)

    def test_uses_tilde_separator(self):
        result = _parse_salary("5~8K")
        self.assertEqual(result["min"], 5000)
        self.assertEqual(result["max"], 8000)

    def test_handles_comma_in_number(self):
        result = _parse_salary("1,500-2,000万")
        self.assertEqual(result["min"], 15000000)
        self.assertEqual(result["max"], 20000000)

    def test_parses_with_chinese_units(self):
        result = _parse_salary("10至15万")
        self.assertEqual(result["min"], 100000)
        self.assertEqual(result["max"], 150000)

    def test_parses_lowercase_k(self):
        result = _parse_salary("8k-12k")
        self.assertEqual(result["min"], 8000)
        self.assertEqual(result["max"], 12000)


class JobIdExtractionTests(unittest.TestCase):
    """验证智联 URL 中职位 ID 的提取逻辑。"""

    def test_extracts_standard_zhaopin_id(self):
        url = "https://www.zhaopin.com/jobdetail/CC123456789J40000000000.htm"
        self.assertEqual(_job_id_from_url(url), "CC123456789J40000000000")

    def test_extracts_id_with_query_params(self):
        url = "https://www.zhaopin.com/jobdetail/CC00001111J20000000000.htm?ref=search"
        self.assertEqual(_job_id_from_url(url), "CC00001111J20000000000")

    def test_extracts_id_case_insensitive(self):
        url = "https://www.zhaopin.com/jobdetail/ccabcdefJ12345678901.htm"
        self.assertEqual(_job_id_from_url(url), "ccabcdefJ12345678901")

    def test_returns_none_for_non_zhaopin_url(self):
        url = "https://example.com/jobs/12345"
        self.assertIsNone(_job_id_from_url(url))

    def test_returns_none_for_empty_url(self):
        self.assertIsNone(_job_id_from_url(""))


class SearchUrlBuildingTests(unittest.TestCase):
    """验证智联搜索 URL 构建。"""

    def test_builds_url_with_known_city(self):
        url = _build_search_url("产品经理", "丽水")
        self.assertIn("kw=", url)
        self.assertIn("city=654", url)
        self.assertIn("p=1", url)

    def test_builds_url_with_custom_page(self):
        url = _build_search_url("产品经理", "杭州", page=3)
        self.assertIn("city=653", url)
        self.assertIn("p=3", url)

    def test_builds_url_with_unknown_city_falls_back(self):
        url = _build_search_url("测试", "火星")
        self.assertIn("city=653", url)  # default to 杭州


class CrawlerInterfaceTests(unittest.TestCase):
    """验证爬虫接口合规性。"""

    def test_platform_property_returns_zhaopin(self):
        crawler = ZhilianCrawler()
        self.assertEqual(crawler.platform, "zhaopin")

    def test_has_search_and_fetch_detail_methods(self):
        crawler = ZhilianCrawler()
        self.assertTrue(callable(crawler.search))
        self.assertTrue(callable(crawler.fetch_detail))

    def test_fetch_detail_returns_empty_for_empty_url(self):
        crawler = ZhilianCrawler()
        result = crawler.fetch_detail("")
        self.assertEqual(result, "")


class CardParsingTests(unittest.TestCase):
    """用模拟 HTML 验证卡片解析逻辑。"""

    def _mock_card_html(self, **overrides) -> str:
        """构造智联搜索卡片 HTML。"""
        title = overrides.get("title", "产品经理")
        company = overrides.get("company", "示例科技")
        salary = overrides.get("salary", "8-12K")
        location = overrides.get("location", "丽水")
        experience = overrides.get("experience", "1-3年")
        education = overrides.get("education", "本科")
        tags = overrides.get("tags", "需求分析、Axure")
        href = overrides.get(
            "href",
            "https://www.zhaopin.com/jobdetail/CC123456789J40000000000.htm",
        )

        return f"""<div class="joblist-box__item">
    <a class="jobinfo__name" href="{href}">{title}</a>
    <div class="companyinfo__name">{company}</div>
    <div class="jobinfo__salary">{salary}</div>
    <div class="jobinfo__other-info">{location}\n{experience}\n{education}</div>
    <div class="jobinfo__tag">{tags}</div>
</div>"""

    def test_parses_full_card(self):
        crawler = ZhilianCrawler()
        from bs4 import BeautifulSoup

        html = self._mock_card_html()
        soup = BeautifulSoup(html, "html.parser")
        card = soup.select_one(".joblist-box__item")

        result = crawler._parse_card(card, "杭州")
        self.assertEqual(result["title"], "产品经理")
        self.assertEqual(result["company"], "示例科技")
        self.assertEqual(result["location"], "丽水")
        self.assertEqual(result["salary"]["min"], 8000)
        self.assertEqual(result["salary"]["max"], 12000)
        self.assertEqual(result["experience"], "1-3年")
        self.assertEqual(result["education"], "本科")
        self.assertEqual(result["tags"], "需求分析、Axure")
        self.assertEqual(result["id"], "CC123456789J40000000000")
        self.assertEqual(result["source"], "zhaopin")

    def test_returns_none_when_name_element_missing(self):
        crawler = ZhilianCrawler()
        from bs4 import BeautifulSoup

        html = """<div class="joblist-box__item">
            <div class="companyinfo__name">示例公司</div>
        </div>"""
        soup = BeautifulSoup(html, "html.parser")
        card = soup.select_one(".joblist-box__item")

        self.assertIsNone(crawler._parse_card(card, "杭州"))

    def test_uses_fallback_city_when_location_empty(self):
        crawler = ZhilianCrawler()
        html = self._mock_card_html(location="")
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        card = soup.select_one(".joblist-box__item")

        result = crawler._parse_card(card, "杭州")
        self.assertEqual(result["location"], "杭州")

    def test_handles_relative_url(self):
        crawler = ZhilianCrawler()
        html = self._mock_card_html(
            href="//www.zhaopin.com/jobdetail/CC999999999J90000000000.htm",
        )
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        card = soup.select_one(".joblist-box__item")

        result = crawler._parse_card(card, "杭州")
        self.assertTrue(result["url"].startswith("https://"))


class ZhilianInterfaceTests(unittest.TestCase):
    """验证 ZhilianCrawler 新增接口。"""

    def test_has_search_all_method(self):
        from crawlers.zhilian import ZhilianCrawler
        self.assertTrue(callable(ZhilianCrawler.search_all))

    def test_has_fetch_details_batch_method(self):
        from crawlers.zhilian import ZhilianCrawler
        self.assertTrue(callable(ZhilianCrawler.fetch_details_batch))

    def test_search_all_respects_max_pages(self):
        from crawlers.zhilian import ZhilianCrawler
        import inspect
        sig = inspect.signature(ZhilianCrawler.search_all)
        self.assertIn("max_pages", sig.parameters)

    def test_fetch_details_batch_accepts_max_details(self):
        from crawlers.zhilian import ZhilianCrawler
        import inspect
        sig = inspect.signature(ZhilianCrawler.fetch_details_batch)
        self.assertIn("max_details", sig.parameters)


if __name__ == "__main__":
    unittest.main()
