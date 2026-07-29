"""猎聘爬虫单元测试 — 解析逻辑不依赖浏览器。"""

import unittest

from crawlers.liepin import _resolve_city, LiepinCrawler


class LiepinCityResolutionTests(unittest.TestCase):
    def test_resolves_hangzhou(self):
        self.assertEqual(_resolve_city("杭州"), "hz")

    def test_resolves_lishui(self):
        self.assertEqual(_resolve_city("丽水"), "lishui")

    def test_falls_back_to_lowercase(self):
        self.assertEqual(_resolve_city("火星"), "火星")


class LiepinInterfaceTests(unittest.TestCase):
    def test_platform_property(self):
        self.assertEqual(LiepinCrawler().platform, "liepin")

    def test_has_search_method(self):
        self.assertTrue(callable(LiepinCrawler().search))

    def test_has_search_all_method(self):
        self.assertTrue(callable(LiepinCrawler().search_all))

    def test_has_fetch_detail(self):
        self.assertTrue(callable(LiepinCrawler().fetch_detail))

    def test_has_fetch_details_batch(self):
        self.assertTrue(callable(LiepinCrawler().fetch_details_batch))


if __name__ == "__main__":
    unittest.main()
