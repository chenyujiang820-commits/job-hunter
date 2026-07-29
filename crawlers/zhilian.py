"""智联招聘爬虫 — curl_cffi 伪装 Chrome TLS 指纹 + BeautifulSoup HTML 解析。

使用 curl_cffi 发送 HTTP 请求（impersonate=self._impersonate），不依赖浏览器。
返回与 src.job_schema.JobSummary 兼容的 dict。
"""

from __future__ import annotations

import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import quote

from bs4 import BeautifulSoup
from curl_cffi import requests as curl

from crawlers import CrawlerAdapter
from crawlers.access_guard import ManualInterventionRequired, inspect_response

logger = logging.getLogger(__name__)

# 浙江省城市代码（智联搜索参数 city 值）
CITY_CODES: dict[str, str] = {
    "丽水": "654",
    "杭州": "653",
    "金华": "657",
    "宁波": "655",
    "温州": "658",
    "嘉兴": "660",
    "湖州": "661",
    "绍兴": "662",
    "衢州": "663",
    "舟山": "664",
    "台州": "665",
}

SEARCH_URL = "https://www.zhaopin.com/sou/"
DETAIL_BASE = "https://www.zhaopin.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 详情页 CSS 选择器优先级
DETAIL_SELECTORS = [
    ".job-detail-description",
    ".job-description",
    ".position-content",
    ".describe-content",
    "[class*=description]",
    "[class*=detail]",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_salary(text: str | None) -> dict[str, Any] | None:
    """解析薪资文本，返回 Salary 兼容的 dict。

    支持格式：8-12K·13薪、8千-1.2万、15-20万/年、面议。
    参考 job-research zhilian.py 的 _parse_salary 和 normalize_manual_job.py。
    """
    if not text or not text.strip():
        return None

    text = text.strip().replace(",", "").replace("，", "").replace("·", " ")
    negotiable = any(term in text for term in ("面议", "面谈", "可议"))
    months_per_year = 13 if re.search(r"13\s*薪", text) else None
    unit = "month"

    if negotiable and not re.search(r"\d", text):
        return {
            "raw": text,
            "min": None,
            "max": None,
            "unit": unit,
            "months_per_year": months_per_year,
            "negotiable": True,
        }

    # 范围: 8-12K, 8k-12k, 8千-1.2万, 15-20万/年
    range_match = re.search(
        r"(?P<min>[\d.]+)\s*(?P<min_unit>万|千|K|k)?\s*"
        r"[-–~至到]\s*"
        r"(?P<max>[\d.]+)\s*(?P<max_unit>万|千|K|k)?"
        r"(?:\s*/\s*(?:年|year))?",
        text,
    )
    if range_match:
        v_min = float(range_match.group("min"))
        v_max = float(range_match.group("max"))
        min_u = (range_match.group("min_unit") or "").lower()
        max_u = (range_match.group("max_unit") or "").lower()
        multiplier_map = {"k": 1000, "千": 1000, "万": 10000}
        # 优先用各自单位，缺失时用对侧单位，都没有则 ×1
        min_mult = multiplier_map.get(min_u) or multiplier_map.get(max_u, 1)
        max_mult = multiplier_map.get(max_u) or multiplier_map.get(min_u, 1)
        if "/年" in text or "/year" in text.lower():
            unit = "year"
        return {
            "raw": text,
            "min": int(v_min * min_mult),
            "max": int(v_max * max_mult),
            "unit": unit,
            "months_per_year": months_per_year,
            "negotiable": negotiable,
        }

    # 单值: 8K, 1.2万
    single_match = re.search(
        r"(?P<single>[\d.]+)\s*(?P<unit>万|千|K|k)", text
    )
    if single_match:
        v = float(single_match.group("single"))
        u = single_match.group("unit").lower()
        multiplier = {"k": 1000, "千": 1000, "万": 10000}.get(u, 1)
        return {
            "raw": text,
            "min": int(v * multiplier),
            "max": int(v * multiplier),
            "unit": "month",
            "months_per_year": months_per_year,
            "negotiable": negotiable,
        }

    return {
        "raw": text,
        "min": None,
        "max": None,
        "unit": "month",
        "months_per_year": months_per_year,
        "negotiable": negotiable,
    }


def _job_id_from_url(url: str) -> str | None:
    """从智联 URL 提取职位 ID（CC...J... 格式）。"""
    match = re.search(r"(CC[0-9A-Z]+J[0-9]+)", url, re.IGNORECASE)
    return match.group(1) if match else None


def _build_search_url(keyword: str, city: str, page: int = 1) -> str:
    city_code = CITY_CODES.get(city, "653")
    return f"{SEARCH_URL}?kw={quote(keyword)}&city={city_code}&p={page}"


class ZhilianCrawler(CrawlerAdapter):
    """智联招聘只读爬虫。

    使用 curl_cffi 发送 HTTP 请求，BeautifulSoup 解析 HTML。
    不依赖浏览器、不需要登录、不处理验证码。
    """

    def __init__(self) -> None:
        self.session = curl.Session()
        self.session.headers.update(HEADERS)
        self._impersonate = "chrome131"  # curl_cffi 0.15 实测支持的最高版本

    @property
    def platform(self) -> str:
        return "zhaopin"

    # ------------------------------------------------------------------
    # search (single page)
    # ------------------------------------------------------------------

    def search(
        self, keyword: str, city: str = "杭州", page: int = 1
    ) -> list[Mapping[str, Any]]:
        """搜索职位列表（单页）。"""
        return self._search_one(keyword, city, page)

    # ------------------------------------------------------------------
    # search_all (multi-page)
    # ------------------------------------------------------------------

    def search_all(
        self,
        keyword: str,
        city: str = "杭州",
        max_pages: int = 5,
    ) -> list[Mapping[str, Any]]:
        """搜索职位列表（多页），自动翻页去重。

        复用同一个 curl Session，按 URL 去重。
        无数据或连续空页时自动停止。
        """
        max_pages = min(max_pages, 10)
        all_results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        empty_streak = 0

        for pg in range(1, max_pages + 1):
            page_jobs = self._search_one(keyword, city, pg)
            if not page_jobs:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                continue
            empty_streak = 0

            new_count = 0
            for j in page_jobs:
                url = j.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(j)
                    new_count += 1

            logger.info(
                "智联 第%d页: %d条 (新增%d, 累计%d)",
                pg, len(page_jobs), new_count, len(all_results),
            )

            if pg < max_pages:
                time.sleep(random.uniform(1, 3))

        return all_results

    def _search_one(
        self, keyword: str, city: str, page: int
    ) -> list[Mapping[str, Any]]:
        """搜索单页，返回原始 JobSummary 兼容 dict。"""
        url = _build_search_url(keyword, city, page)
        logger.info("智联搜索: kw=%s city=%s page=%d", keyword, city, page)

        try:
            resp = self.session.get(
                url, impersonate=self._impersonate, timeout=15
            )
            time.sleep(0.5)
            inspect_response(resp.status_code, resp.text, platform=self.platform)
        except ManualInterventionRequired:
            raise
        except Exception as exc:
            logger.error("智联搜索请求失败: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".joblist-box__item")
        if not cards:
            logger.warning("智联未找到职位卡片 .joblist-box__item，页面结构可能已变")
            return []

        results: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        for card in cards[:25]:
            try:
                result = self._parse_card(card, city)
                if result is None:
                    continue
                title = result["title"] or ""
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                results.append(result)
            except Exception as exc:
                logger.warning("智联解析卡片异常: %s", exc)
                continue

        logger.info("智联返回 %d 条职位", len(results))
        return results

    def _parse_card(self, card, fallback_city: str) -> dict[str, Any] | None:
        """从单个职位卡片提取字段。"""
        name_el = card.select_one(".jobinfo__name")
        if not name_el:
            return None

        title = name_el.get_text(strip=True)
        if not title:
            return None

        href = name_el.get("href", "")
        if href and not href.startswith("http"):
            if href.startswith("//"):
                href = "https:" + href
            else:
                href = DETAIL_BASE + href

        company_el = card.select_one(".companyinfo__name")
        company = company_el.get_text(strip=True) if company_el else ""
        if not company:
            return None

        salary_el = card.select_one(".jobinfo__salary")
        salary_text = salary_el.get_text(strip=True) if salary_el else ""

        info_el = card.select_one(".jobinfo__other-info")
        location = fallback_city
        experience = ""
        education = ""
        if info_el:
            parts = info_el.get_text(strip=True, separator="\n").split("\n")
            # 3 parts: location / experience / education
            # 2 parts: experience / education (location missing)
            # 1 part: just one field
            if len(parts) >= 3:
                location = parts[0].strip() or fallback_city
                experience = parts[1]
                education = parts[2]
            elif len(parts) == 2:
                location = fallback_city
                experience = parts[0]
                education = parts[1]
            elif len(parts) == 1:
                location = parts[0].strip() or fallback_city

        tags_el = card.select_one(".jobinfo__tag")
        tags = tags_el.get_text(strip=True) if tags_el else ""

        job_id = _job_id_from_url(href) if href else None

        return {
            "id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "salary": _parse_salary(salary_text),
            "experience": experience,
            "education": education,
            "tags": tags,
            "date": None,
            "url": href,
            "source": "zhaopin",
            "description": None,
            "raw_text": None,
        }

    # ------------------------------------------------------------------
    # fetch_detail
    # ------------------------------------------------------------------

    def fetch_detail(self, url: str) -> str:
        """获取职位详情描述文本。

        优先尝试 HTTP 请求；遇到 JS 挑战时尝试 CDP 浏览器模式。
        """
        if not url:
            return ""

        # 路径 A：HTTP 请求
        try:
            resp = self.session.get(
                url, impersonate=self._impersonate, timeout=15
            )
            time.sleep(0.5)
            inspect_response(resp.status_code, resp.text, platform=self.platform)
            soup = BeautifulSoup(resp.text, "html.parser")
            for selector in DETAIL_SELECTORS:
                el = soup.select_one(selector)
                if el:
                    return el.get_text(strip=True, separator="\n")
            return soup.get_text(strip=True, separator="\n")[:3000]
        except ManualInterventionRequired:
            # JS 挑战或其他反爬 → 尝试 CDP fallback
            logger.info("智联 HTTP 详情被拦截，尝试 CDP fallback")
        except Exception as exc:
            logger.warning("智联 HTTP 详情请求异常: %s，尝试 CDP fallback", exc)

        # 路径 B：CDP fallback
        try:
            from crawlers.cdp_session import CDPSession, is_cdp_ready
            if not is_cdp_ready():
                logger.warning("CDP 不可用，无法获取智联详情")
                return ""
            cdp = CDPSession()
            tid, sid = cdp.create_page(background=True)
            cdp.navigate(url, sid)
            time.sleep(3)
            # 提取页面文本
            text = cdp.eval_js("document.body ? document.body.innerText : ''", sid) or ""
            cdp.close_target(tid)
            cdp.close()
            return str(text)[:5000]
        except Exception as exc:
            logger.error("智联 CDP 详情获取失败: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # fetch_details_batch
    # ------------------------------------------------------------------

    def fetch_details_batch(
        self,
        jobs: list[Mapping[str, Any]],
        max_details: int | None = None,
    ) -> list[Mapping[str, Any]]:
        """批量获取职位详情，原地更新 description 字段。

        HTTP 优先；遇 JS 挑战自动 CDP fallback。
        不设页间间隔（HTTP 请求轻量）。
        """
        if not jobs:
            return jobs

        targets = jobs[:max_details] if max_details else jobs
        logger.info("智联批量详情: %d 个职位", len(targets))

        for idx, job in enumerate(targets):
            url = job.get("url", "")
            if not url:
                continue

            title = job.get("title", "")[:30]
            logger.info("[%d/%d] %s", idx + 1, len(targets), title)

            desc = self.fetch_detail(url)
            if desc:
                job["description"] = desc
                logger.info("  JD: %d 字", len(desc))
            else:
                logger.info("  详情为空")

            if idx < len(targets) - 1:
                time.sleep(random.uniform(1, 2))

        return jobs
