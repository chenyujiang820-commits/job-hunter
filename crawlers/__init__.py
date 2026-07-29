"""Crawler adapter abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class CrawlerAdapter(ABC):
    """招聘网站爬虫适配器基类。

    所有平台适配器需实现 platform、search、fetch_detail。
    search 和 fetch_detail 返回与 src.job_schema.JobSummary 兼容的 dict。
    """

    @property
    @abstractmethod
    def platform(self) -> str:
        """平台标识，如 zhaopin / boss / liepin。"""
        ...

    @abstractmethod
    def search(self, keyword: str, city: str = "", page: int = 1) -> list[Mapping[str, Any]]:
        """搜索职位列表，返回 JobSummary 兼容的 dict 列表。"""
        ...

    @abstractmethod
    def fetch_detail(self, url: str) -> str:
        """获取职位详情描述文本。"""
        ...
