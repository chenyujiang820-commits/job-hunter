"""Boss 直聘爬虫 — Chrome CDP raw protocol + 页面内 API 调用。

通过 CDP 连接用户已登录的 Chrome，在浏览器上下文中
调用 Boss 官方 wapi（/wapi/zpgeek/search/joblist.json），
Cookie 自动携带，返回结构化 JSON（明文薪资）。

参考 boss-zhipin-scraper 的 boss_cdp_raw.py 实现。
"""

from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from crawlers import CrawlerAdapter
from crawlers.access_guard import ManualInterventionRequired, inspect_response
from crawlers.cdp_session import CDPSession, DEFAULT_CDP_PORT, is_cdp_ready
from crawlers.salary import parse_salary

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 常量
# ------------------------------------------------------------------

API_JOB_LIST_PATH = "/wapi/zpgeek/search/joblist.json"
CITY_CODES_PATH = Path(__file__).resolve().parent / "data" / "boss_city_codes.json"
MAX_PAGES_DEFAULT = 5

# 页面内 XHR 调 API 的 JS 模板
FETCH_API_JS = r"""
(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '__API_URL__', false);
    xhr.send();
    if (xhr.status !== 200) return JSON.stringify([{error: xhr.status}]);
    var data = JSON.parse(xhr.responseText);
    var jobs = (data.zpData || {}).jobList || [];
    var results = jobs.map(function(j) {
        return {
            encrypt_job_id: j.encryptJobId || '',
            title: j.jobName || '',
            salary: j.salaryDesc || '',
            location: (j.cityName || '') + '\u00b7' + (j.areaDistrict || ''),
            experience: j.jobExperience || '',
            education: j.jobDegree || '',
            tags: (j.skills || []).join(', '),
            boss_name: j.brandName || '',
            boss_title: j.bossTitle || '',
            boss_active: j.activeTimeDesc || (j.bossOnline ? '\u5728\u7ebf' : ''),
            company_scale: j.brandScaleName || '',
            company_stage: j.brandStageName || '',
            company_industry: j.brandIndustry || '',
            job_labels: (j.jobLabels || []).join(', '),
            welfare: (j.welfareList || []).join(', '),
            security_id: j.securityId || '',
            lid: j.lid || '',
            encrypt_brand_id: j.encryptBrandId || '',
            job_link: j.encryptJobId ? 'https://www.zhipin.com/job_detail/' + j.encryptJobId + '.html' : ''
        };
    });
    return JSON.stringify(results);
})()
"""

# 详情页提取 JS
EXTRACT_DETAIL_JS = r"""
(function(){
    var pageText = document.body ? document.body.innerText : '';
    var tags = [];
    var benefitWords = ['\u4e94\u9669','\u8865\u5145\u533b\u7597','\u5b9a\u671f\u4f53\u68c0','\u5e26\u85aa\u5e74\u5047','\u5e74\u7ec8\u5956','\u96f6\u98df','\u9910\u8865',
        '\u8282\u65e5\u798f\u5229','\u52a0\u73ed\u8865\u52a9','\u80a1\u7968\u671f\u6743','\u5458\u5de5\u65c5\u6e38','\u4ea4\u901a\u8865\u52a9','\u901a\u8baf\u8865\u8d34','\u56e2\u5efa',
        '\u751f\u65e5\u798f\u5229','\u514d\u8d39\u73ed\u8f66','\u5168\u52e4\u5956','\u5305\u5403','\u5f39\u6027\u5de5\u4f5c','\u4e0b\u5348\u8336','\u79df\u623f\u8865\u8d34',
        '\u4f53\u68c0','\u5065\u8eab','\u6587\u5316','\u5145\u7535\u5047','\u53f8\u9f84\u5047','\u7ea2\u5305','\u80fd\u91cf\u8865\u8d34','\u793e\u56e2','\u4e09\u85aa',
        '\u7ee9\u6548','\u5e95\u85aa','\u4fdd\u5e95','\u6d3b\u52a8\u57fa\u91d1','\u5b66\u4e60\u57fa\u91d1','\u8282\u65e5\u793c\u54c1','\u65e0\u969c\u7887'];
    function isBenefit(t) {
        if (t === '...' || t.length > 15 || t.length < 2) return true;
        for (var i = 0; i < benefitWords.length; i++) {
            if (t.indexOf(benefitWords[i]) !== -1) return true;
        }
        return false;
    }
    document.querySelectorAll('.job-tags .tag-all span, .job-keyword-list span').forEach(function(s){
        var t = s.innerText.trim();
        if(t && !isBenefit(t)) tags.push(t);
    });
    var jd = '';
    var sections = document.querySelectorAll('.job-detail-section, .job-sec');
    for (var i = 0; i < sections.length; i++) {
        var text = (sections[i].innerText || '').trim();
        if (text.indexOf('\u804c\u4f4d\u63cf\u8ff0') !== -1 && text.length > jd.length) {
            jd = text;
        }
    }
    return JSON.stringify({
        jd: jd,
        page_text: pageText.substring(0, 12000),
        tags: tags,
        url: location.href
    });
})()
"""


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_city_map() -> dict[str, str]:
    """加载 BOSS 城市代码表。"""
    if CITY_CODES_PATH.exists():
        with open(CITY_CODES_PATH, encoding="utf-8") as f:
            return json.load(f)
    # 硬编码回退：浙江主要城市
    return {
        "杭州": "101210100",
        "丽水": "101211100",
        "金华": "101210900",
        "宁波": "101210400",
        "温州": "101210300",
        "嘉兴": "101210500",
        "湖州": "101210600",
        "绍兴": "101210700",
        "衢州": "101211000",
        "舟山": "101211200",
        "台州": "101211300",
    }


def _resolve_city(city: str) -> tuple[str, str]:
    """解析城市名 → (city_name, city_code)。"""
    city_map = _load_city_map()
    code = city_map.get(city, "")
    if code:
        return city, code
    # 模糊匹配
    for name, c in city_map.items():
        if city in name or name in city:
            return name, c
    return city, city  # 兜底：原样


# ------------------------------------------------------------------
# BossCdpCrawler
# ------------------------------------------------------------------

class BossCdpCrawler(CrawlerAdapter):
    """Boss 直聘 CDP 爬虫。

    通过 Chrome CDP 连接用户已登录的浏览器，
    在页面上下文中调用 Boss 官方 API 获取结构化职位数据。

    前置条件:
        - Chrome 已启动并开启调试端口 (--remote-debugging-port=9222)
        - 用户已在 Chrome 中登录 zhipin.com
    """

    def __init__(self, cdp_port: int = DEFAULT_CDP_PORT) -> None:
        self.cdp_port = cdp_port

    @property
    def platform(self) -> str:
        return "boss"

    # ------------------------------------------------------------------
    # search (single page)
    # ------------------------------------------------------------------

    def search(
        self, keyword: str, city: str = "杭州", page: int = 1
    ) -> list[Mapping[str, Any]]:
        """搜索 Boss 职位列表（单页）。"""
        return self._search_pages(keyword, city, start_page=page, max_pages=1)

    # ------------------------------------------------------------------
    # search_all (multi-page)
    # ------------------------------------------------------------------

    def search_all(
        self,
        keyword: str,
        city: str = "杭州",
        max_pages: int = 5,
    ) -> list[Mapping[str, Any]]:
        """搜索 Boss 职位列表（多页），自动翻页去重。

        复用同一个 CDP Session，避免每页重新连接。
        第 2 页起不再导航搜索页，直接调 API。
        """
        return self._search_pages(keyword, city, start_page=1, max_pages=max_pages)

    def _search_pages(
        self,
        keyword: str,
        city: str,
        start_page: int,
        max_pages: int,
    ) -> list[Mapping[str, Any]]:
        """搜索 Boss 职位列表，支持多页翻页。

        复用同一个 CDP Session；第 1 页导航建立 context，
        后续页直接调 API。
        """
        if not is_cdp_ready(self.cdp_port):
            logger.error(
                "Chrome CDP 不可用 (port %s)，请先启动 Chrome 调试模式",
                self.cdp_port,
            )
            return []

        city_name, city_code = _resolve_city(city)
        max_pages = min(max_pages, 10)  # 安全上限
        logger.info(
            "Boss 搜索: kw=%s city=%s(%s) pages=%d-%d",
            keyword, city_name, city_code, start_page, start_page + max_pages - 1,
        )

        try:
            cdp = CDPSession(self.cdp_port)
        except Exception as exc:
            logger.error("CDP 连接失败: %s", exc)
            return []

        all_results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        try:
            tid, sid = cdp.create_page(background=True)

            for pg in range(start_page, start_page + max_pages):
                if pg == start_page:
                    # 首页：导航到搜索页建立 session
                    search_url = (
                        f"https://www.zhipin.com/web/geek/job?"
                        f"query={keyword}&city={city_code}&page={pg}"
                    )
                    cdp.navigate(search_url, sid)
                    time.sleep(random.uniform(4, 8))

                api_params = (
                    f"scene=1&query={keyword}&city={city_code}"
                    f"&page={pg}&pageSize=30"
                )
                api_url = f"{API_JOB_LIST_PATH}?{api_params}"
                api_js = FETCH_API_JS.replace("__API_URL__", api_url)
                raw = cdp.eval_js(api_js, sid)
                _inspect_boss_api_response(raw)

                jobs = _parse_api_response(raw)
                if not jobs:
                    logger.info("Boss 第 %d 页无数据，停止翻页", pg)
                    break

                new_count = 0
                for j in jobs:
                    jid = j.get("encrypt_job_id", "")
                    if jid and jid not in seen_ids:
                        seen_ids.add(jid)
                        all_results.append(
                            _to_job_summary(j, keyword, city_name)
                        )
                        new_count += 1

                logger.info(
                    "Boss 第 %d 页: %d 条 (新增 %d, 累计 %d)",
                    pg, len(jobs), new_count, len(all_results),
                )

                # 页间等待
                if pg < start_page + max_pages - 1:
                    time.sleep(random.uniform(2, 5))

            cdp.close_target(tid)
            cdp.close()
            logger.info("Boss 搜索完成: 共 %d 条", len(all_results))
            return all_results

        except ManualInterventionRequired:
            try:
                cdp.close()
            except Exception:
                pass
            raise
        except Exception as exc:
            logger.error("Boss 搜索异常: %s", exc)
            try:
                cdp.close()
            except Exception:
                pass
            return all_results  # 返回已抓取的部分

    # ------------------------------------------------------------------
    # fetch_detail (single)
    # ------------------------------------------------------------------

    def fetch_detail(self, url: str) -> str:
        """获取单个职位详情 JD 文本。"""
        if not url or not is_cdp_ready(self.cdp_port):
            return ""

        try:
            cdp = CDPSession(self.cdp_port)
        except Exception as exc:
            logger.error("CDP 连接失败: %s", exc)
            return ""

        try:
            tid, sid = cdp.create_page(background=True)
            cdp.navigate(url, sid)
            time.sleep(random.uniform(3, 6))

            raw = cdp.eval_js(EXTRACT_DETAIL_JS, sid)
            try:
                data = json.loads(raw) if isinstance(raw, str) else {}
            except (json.JSONDecodeError, TypeError):
                data = {}

            page_text = data.get("page_text", "")
            inspect_response(200, page_text, platform=self.platform)
            jd = data.get("jd", "")

            cdp.close_target(tid)
            cdp.close()
            return jd

        except ManualInterventionRequired:
            try:
                cdp.close()
            except Exception:
                pass
            raise
        except Exception as exc:
            logger.error("Boss 详情获取失败: %s", exc)
            try:
                cdp.close()
            except Exception:
                pass
            return ""

    # ------------------------------------------------------------------
    # fetch_details_batch
    # ------------------------------------------------------------------

    def fetch_details_batch(
        self,
        jobs: list[Mapping[str, Any]],
        max_details: int | None = None,
        interval: tuple[float, float] = (12, 25),
    ) -> list[Mapping[str, Any]]:
        """批量获取职位详情，原地更新 description 字段。

        复用同一个 CDPSession，每个职位新开 target。
        参考 boss-zhipin-scraper 的 scrape_details 模式。

        Args:
            jobs: 职位列表（含 job_link）
            max_details: 最多抓取条数，None=全部
            interval: 详情页间等待秒数范围 (min, max)

        Returns:
            更新后的 jobs 列表
        """
        if not jobs or not is_cdp_ready(self.cdp_port):
            return jobs

        targets = jobs[:max_details] if max_details else jobs
        logger.info(
            "Boss 批量详情: %d 个职位", len(targets),
        )

        seen_urls: set[str] = set()

        for idx, job in enumerate(targets):
            url = job.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = job.get("title", "")[:30]
            company = job.get("company", "")[:15]
            t0 = time.time()
            logger.info(
                "[%d/%d] %s - %s", idx + 1, len(targets), company, title,
            )

            try:
                cdp = CDPSession(self.cdp_port)
            except Exception as exc:
                logger.warning("CDP 连接失败: %s", exc)
                continue

            try:
                tid, sid = cdp.create_page(background=True)
                cdp.navigate(url, sid)
                time.sleep(random.uniform(3, 6))

                # 模拟滚动（降低风控）
                for _ in range(random.randint(2, 4)):
                    delta = random.randint(200, 500)
                    cdp.eval_js(f"window.scrollBy(0,{delta})", sid)
                    time.sleep(random.uniform(0.5, 1.5))

                raw = cdp.eval_js(EXTRACT_DETAIL_JS, sid)
                try:
                    data = json.loads(raw) if isinstance(raw, str) else {}
                except (json.JSONDecodeError, TypeError):
                    data = {}

                page_text = data.get("page_text", "")
                inspect_response(200, page_text, platform=self.platform)

                jd = data.get("jd", "")
                tags = data.get("tags", [])

                if jd:
                    job["description"] = jd
                if tags:
                    existing = job.get("tags", "")
                    job["tags"] = (
                        existing + ", " + ", ".join(tags)
                        if existing
                        else ", ".join(tags)
                    )

                elapsed = time.time() - t0
                logger.info(
                    "  JD: %d 字 | 技能: %d | %.0fs",
                    len(jd), len(tags), elapsed,
                )

                cdp.close_target(tid)
                cdp.close()

            except ManualInterventionRequired:
                try:
                    cdp.close()
                except Exception:
                    pass
                raise
            except Exception as exc:
                logger.warning("详情获取失败: %s", exc)
                try:
                    cdp.close()
                except Exception:
                    pass
                continue

            # 详情页间隔
            if idx < len(targets) - 1:
                gap = random.uniform(*interval)
                time.sleep(gap)

        return jobs


# ------------------------------------------------------------------
# 内部辅助
# ------------------------------------------------------------------

def _parse_api_response(raw: Any) -> list[dict[str, Any]]:
    """解析 FETCH_API_JS 返回的原始值。"""
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [
        item for item in parsed
        if isinstance(item, dict) and not item.get("error")
    ]


def _inspect_boss_api_response(raw: Any) -> None:
    """Convert BOSS API access errors into an explicit pause signal."""
    inspect_response(200, raw, platform="boss")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return
    if isinstance(parsed, list):
        statuses = {
            item.get("error")
            for item in parsed
            if isinstance(item, dict) and item.get("error")
        }
        if statuses & {401, 403, 429}:
            raise ManualInterventionRequired(
                f"API 返回访问状态 {sorted(statuses)}", platform="boss"
            )


def _to_job_summary(
    api_job: dict[str, Any], keyword: str, city: str
) -> dict[str, Any]:
    """将 BOSS API 返回的条目转为 JobSummary 兼容 dict。"""
    salary_text = api_job.get("salary", "")
    salary = _parse_boss_salary(salary_text)

    return {
        "id": api_job.get("encrypt_job_id"),
        "title": api_job.get("title"),
        "company": api_job.get("boss_name"),
        "location": api_job.get("location"),
        "salary": salary,
        "experience": api_job.get("experience"),
        "education": api_job.get("education"),
        "tags": api_job.get("tags"),
        "date": None,
        "url": api_job.get("job_link"),
        "source": "boss",
        "description": None,
        "raw_text": json.dumps(api_job, ensure_ascii=False),
    }


def _parse_boss_salary(text: str | None) -> dict[str, Any] | None:
    """解析 BOSS 薪资文本。"""
    return parse_salary(text)
