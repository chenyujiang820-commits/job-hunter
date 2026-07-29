"""猎聘爬虫 — Playwright CDP + URL 搜索 + 文本解析。

猎聘需要登录和 JS 渲染。通过 URL 参数搜索，等待前端渲染后提取卡片文本。
"""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Any, Mapping
from urllib.parse import quote

from crawlers import CrawlerAdapter
from crawlers.browser import get_page
from crawlers.salary import parse_salary

logger = logging.getLogger(__name__)

CITY_CODES: dict[str, str] = {
    "杭州": "hz", "丽水": "lishui", "金华": "jinhua",
    "宁波": "ningbo", "温州": "wenzhou", "绍兴": "shaoxing",
    "嘉兴": "jiaxing", "台州": "taizhou", "湖州": "huzhou",
    "衢州": "quzhou", "舟山": "zhoushan",
}


def _resolve_city(city: str) -> str:
    return CITY_CODES.get(city, city.lower())


def _extract_card_fields(text: str, fallback_city: str) -> dict[str, Any] | None:
    """从猎聘卡片文本中提取字段。"""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2:
        return None

    title = lines[0]

    # 过滤噪音卡片
    if any(w in title for w in ("新职位", "订阅", "广告", "微信", "扫一扫", "APP")):
        return None

    company = ""
    location = fallback_city
    salary_text = ""
    experience = ""
    education = ""

    for line in lines[1:]:
        # 薪资
        if re.search(r"[\d.]+\s*[-~至到]\s*[\d.]+|[薪面议Kk万月年]", line) and len(line) < 25:
            salary_text = line
        # 地点：杭州-滨江区、上海·浦东 等
        elif re.search(r"[\u4e00-\u9fa5]{2,}[-\u00b7·][\u4e00-\u9fa5]{2,}", line):
            location = line
        # 经验
        elif re.search(r"应届|在校|经验不限|^\d+[-\s~至到]?\d*\s*年", line):
            experience = line
        # 学历
        elif line in ("大专", "本科", "硕士", "博士", "学历不限", "中专/中技", "高中", "初中及以下"):
            education = line
        # 跳过高管名 (XX先生/女士, XX·HR等)
        elif re.search(r"[先生女士]$|·HR$|·猎头|·招聘", line):
            continue
        # 跳过行业/规模行 (如 "互联网港股上市2000-5000人")
        elif re.search(r"^\S+上市|^\S+融资|^.{2,4}/\S+", line) and len(line) < 30:
            continue
        # 公司名
        elif not company and 2 <= len(line) <= 30 and not re.search(r"^\d", line):
            company = line

    if not title or not company:
        return None

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary": parse_salary(salary_text),
        "experience": experience,
        "education": education,
        "tags": "",
    }


class LiepinCrawler(CrawlerAdapter):
    """猎聘爬虫 — Playwright + DOM 选择器。

    前置条件: Chrome 调试端口 + 已登录 liepin.com
    """

    @property
    def platform(self) -> str:
        return "liepin"

    def search(
        self, keyword: str, city: str = "杭州", page: int = 1
    ) -> list[Mapping[str, Any]]:
        """搜索猎聘职位（单页），CSS 选择器精确提取。"""
        try:
            page_obj = get_page()
        except Exception as exc:
            logger.error("Playwright 失败: %s", exc)
            return []

        city_code = _resolve_city(city)
        url = (
            f"https://www.liepin.com/zhaopin/"
            f"?key={quote(keyword)}&city={city_code}"
            f"&curPage={page - 1}"
        )

        logger.info("猎聘搜索: %s @ %s page=%d", keyword, city, page)

        try:
            page_obj.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(3)
        except Exception as exc:
            logger.error("猎聘页面加载失败: %s", exc)
            return []

        # 用 CSS 选择器提取卡片
        cards = page_obj.locator(".job-detail-box").all()
        if not cards:
            cards = page_obj.locator("[class*=job-detail-box]").all()

        results: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        for card in cards:
            try:
                job = self._parse_card_dom(card, city)
                if not job:
                    continue
                title = job["title"]
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                results.append(job)
            except Exception as exc:
                continue

        logger.info("猎聘返回 %d 条", len(results))
        return results

    def _parse_card_dom(self, card, fallback_city: str) -> dict[str, Any] | None:
        """从 DOM 元素精确提取职位字段。

        猎聘卡片结构（10 行固定模板）：
        [0] 标题  [1]【  [2] 地点  [3]】  [4] 急聘(可选)
        [5] 薪资  [6] 经验  [7] 学历  [8] 公司  [9] 行业/规模
        """
        lines = [l.strip() for l in card.inner_text().split("\n") if l.strip()]
        if len(lines) < 8:
            return None

        title = lines[0]
        # 过滤噪音
        if any(w in title for w in ("新职位", "订阅", "广告", "微信", "扫一扫", "APP")):
            return None

        # 地点: line[2] (在【】之间)
        location = lines[2] if len(lines) > 2 and lines[1] == "【" and lines[3] == "】" else fallback_city

        # 找到薪资行 — 包含 薪/K/万/数字范围
        salary_text = ""
        exp_idx = 5
        for i, line in enumerate(lines):
            if re.search(r"[\d.]+\s*[-~至到]\s*[\d.]+.*[Kk万月年薪]|薪资面议|面议", line):
                salary_text = line
                exp_idx = i + 1
                break

        # 经验: 薪资行的下一行
        experience = ""
        education = ""
        for i in range(exp_idx, min(exp_idx + 2, len(lines))):
            line = lines[i]
            if re.search(r"应届|在校|经验不限|\d+[-\s~至到]?\d*\s*年", line):
                experience = line
            elif line in ("大专", "本科", "硕士", "博士", "学历不限", "中专/中技", "高中", "初中及以下"):
                education = line

        # 公司: line[8]（倒数第二行），但如果 line[8] 是 HR 名则取 line[9]
        company = ""
        if len(lines) >= 9:
            candidate = lines[8]
            if re.search(r"[先生女士]$|·HR|·猎头|·招聘", candidate):
                # HR 名替代了公司名 → 公司名在 line[9]
                if len(lines) >= 10 and not re.search(r"上市|融资|/\S+", lines[9]) and len(lines[9]) <= 20:
                    company = lines[9]
            elif not re.search(r"上市|融资|/\S+", candidate) and len(candidate) <= 30:
                company = candidate

        if not company:
            # 兜底：倒序找第一个不像行业/规模/HR 的行
            for i in range(len(lines) - 1, max(len(lines) - 4, -1), -1):
                line = lines[i]
                if re.search(r"[先生女士]$|·HR$|·猎头|·招聘|^\d", line):
                    continue
                if re.search(r"上市|融资|/\S+", line) and len(line) < 30:
                    continue
                if 3 <= len(line) <= 30:
                    company = line
                    break

        if not title:
            return None

        # 链接
        link_el = card.locator("a[href*=job]").first
        href = ""
        if link_el.count():
            href = link_el.get_attribute("href") or ""

        return {
            "id": None,
            "title": title,
            "company": company or lines[-2] if len(lines) >= 2 else "未知",
            "location": location,
            "salary": parse_salary(salary_text),
            "experience": experience,
            "education": education,
            "tags": "",
            "date": None,
            "url": href if href.startswith("http") else f"https:{href}" if href else "",
            "source": "liepin",
            "description": None,
            "raw_text": card.inner_text()[:500],
        }

    def search_all(
        self, keyword: str, city: str = "杭州", max_pages: int = 5
    ) -> list[Mapping[str, Any]]:
        """多页搜索，去重。"""
        all_results: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        for pg in range(1, max_pages + 1):
            page_jobs = self.search(keyword, city, page=pg)
            if not page_jobs:
                break

            new_count = 0
            for j in page_jobs:
                t = j.get("title", "")
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    all_results.append(j)
                    new_count += 1

            if new_count == 0:
                break
            if pg < max_pages:
                time.sleep(random.uniform(2, 4))

        return all_results

    def fetch_detail(self, url: str) -> str:
        """获取详情。"""
        if not url:
            return ""
        try:
            page_obj = get_page()
            page_obj.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)
            text = page_obj.inner_text("body")
            return text[:5000] if text else ""
        except Exception as exc:
            logger.error("猎聘详情失败: %s", exc)
            return ""

    def fetch_details_batch(
        self, jobs: list[Mapping[str, Any]], max_details: int | None = None
    ) -> list[Mapping[str, Any]]:
        """批量详情。"""
        targets = jobs[:max_details] if max_details else jobs
        for idx, job in enumerate(targets):
            url = job.get("url", "")
            if not url:
                continue
            logger.info("[%d/%d] %s", idx + 1, len(targets), job.get("title", "")[:30])
            desc = self.fetch_detail(url)
            if desc:
                job["description"] = desc
            if idx < len(targets) - 1:
                time.sleep(random.uniform(2, 4))
        return jobs
