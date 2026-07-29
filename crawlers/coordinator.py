"""爬虫协调器 — 多平台搜索 + 结果入库。

将爬虫返回的职位数据转换为 JobSummary 兼容的 dict，
通过 merge_seen_jobs 合并到本地缓存。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from crawlers.access_guard import ManualInterventionRequired
from src.job_state import merge_seen_jobs

logger = logging.getLogger(__name__)

def _init_crawlers() -> dict[str, Any]:
    crawlers: dict[str, Any] = {}
    try:
        from crawlers.zhilian import ZhilianCrawler
        crawlers["zhaopin"] = ZhilianCrawler()
    except ImportError:
        pass
    try:
        from crawlers.boss_cdp import BossCdpCrawler  # noqa: F811
        crawlers["boss"] = BossCdpCrawler()
    except ImportError:
        pass
    try:
        from crawlers.liepin import LiepinCrawler  # noqa: F811
        crawlers["liepin"] = LiepinCrawler()
    except ImportError:
        pass
    return crawlers

CRAWLERS: dict[str, Any] = _init_crawlers()

SEEN_JOBS_PATH = Path("runtime/seen_jobs.json")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def search_and_store(
    keyword: str,
    city: str = "杭州",
    platforms: list[str] | None = None,
    max_pages: int = 1,
    fetch_details: bool = False,
    max_details: int | None = None,
) -> dict[str, Any]:
    """搜索多平台职位，去重后合并到本地缓存。

    Args:
        keyword: 搜索关键词
        city: 城市
        platforms: 平台列表，默认 ["zhaopin"]
        max_pages: 每个平台最多翻页数
        fetch_details: 是否抓取详情（Boss 走 CDP 批量模式）
        max_details: 最多抓取详情条数

    返回:
        {
            "status": "completed" | "completed_with_errors" | "paused_manual_intervention",
            "message": str,
            "total_fetched": int,
            "total_new": int,
            "errors": list[str],
        }
    """
    if platforms is None:
        platforms = ["zhaopin"]

    total_fetched = 0
    total_new = 0
    errors: list[str] = []

    for plat in platforms:
        crawler = CRAWLERS.get(plat)
        if not crawler:
            errors.append(f"未知平台: {plat}")
            continue

        logger.info("[%s] 搜索: %s @ %s (max_pages=%d)", plat, keyword, city, max_pages)
        try:
            if max_pages > 1 and hasattr(crawler, 'search_all'):
                items = crawler.search_all(keyword, city, max_pages=max_pages)
            else:
                items = crawler.search(keyword, city)
        except ManualInterventionRequired as exc:
            errors.append(str(exc))
            return {
                "status": exc.status,
                "message": str(exc),
                "total_fetched": total_fetched,
                "total_new": total_new,
                "errors": errors,
            }
        except Exception as exc:
            logger.error("[%s] 搜索异常: %s", plat, exc)
            errors.append(f"{plat}: {exc}")
            continue

        total_fetched += len(items)
        if not items:
            continue

        # 获取详情
        if fetch_details and items:
            logger.info("[%s] 抓取详情: %d 个职位", plat, min(len(items), max_details or len(items)))
            if hasattr(crawler, 'fetch_details_batch'):
                try:
                    items = crawler.fetch_details_batch(
                        items, max_details=max_details
                    )
                except ManualInterventionRequired as exc:
                    errors.append(str(exc))
                    return {
                        "status": exc.status,
                        "message": str(exc),
                        "total_fetched": total_fetched,
                        "total_new": total_new,
                        "errors": errors,
                    }
            else:
                for item in items:
                    url = item.get("url", "")
                    if url:
                        try:
                            desc = crawler.fetch_detail(url)
                            if desc:
                                item["description"] = desc
                        except ManualInterventionRequired as exc:
                            errors.append(str(exc))
                            return {
                                "status": exc.status,
                                "message": str(exc),
                                "total_fetched": total_fetched,
                                "total_new": total_new,
                                "errors": errors,
                            }
                        except Exception as exc:
                            logger.warning("[%s] 详情获取失败: %s", plat, exc)

        # 合并到本地缓存
        report = merge_seen_jobs(SEEN_JOBS_PATH, items, _today())
        total_new += report.new_count
        logger.info(
            "[%s] 新增 %d / 重复 %d / 更新 %d",
            plat,
            report.new_count,
            report.duplicate_count,
            report.updated_count,
        )

    return {
        "status": "completed_with_errors" if errors else "completed",
        "message": "职位采集完成" if not errors else "职位采集完成，但存在部分错误",
        "total_fetched": total_fetched,
        "total_new": total_new,
        "errors": errors,
    }
