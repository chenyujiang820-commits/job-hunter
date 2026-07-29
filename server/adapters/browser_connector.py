"""Per-user, read-only BOSS browser connector boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

from crawlers.access_guard import ManualInterventionRequired, inspect_response
from crawlers.boss_cdp import (
    API_JOB_LIST_PATH,
    FETCH_API_JS,
    _inspect_boss_api_response,
    _parse_api_response,
    _resolve_city,
    _to_job_summary,
)


@dataclass(frozen=True)
class BrowserSessionState:
    status: str
    reason: str = ""


@dataclass(frozen=True)
class CollectionResult:
    status: str
    jobs: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


class BrowserConnector(Protocol):
    def start(self, user_id: str, profile_path: str) -> BrowserSessionState:
        ...

    def stop(self, user_id: str) -> None:
        ...

    def collect(self, user_id: str, query: dict[str, Any]) -> CollectionResult:
        ...


class ChromiumBrowserConnector:
    """Launch normal persistent Chromium contexts, one profile per user."""

    def __init__(self, profile_root: str):
        self.profile_root = Path(profile_root).resolve()
        self._contexts: dict[str, Any] = {}
        self._playwright = None

    def start(self, user_id: str, profile_path: str) -> BrowserSessionState:
        if user_id in self._contexts:
            return BrowserSessionState(status="ready")
        path = Path(profile_path).resolve()
        if not path.is_relative_to(self.profile_root):
            raise ValueError("browser profile path must stay under the configured profile root")
        path.mkdir(parents=True, exist_ok=True)
        from playwright.sync_api import sync_playwright

        if self._playwright is None:
            self._playwright = sync_playwright().start()
        context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(path),
            headless=False,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        self._contexts[user_id] = context
        if not context.pages:
            context.new_page()
        return BrowserSessionState(status="ready")

    def stop(self, user_id: str) -> None:
        context = self._contexts.pop(user_id, None)
        if context is not None:
            context.close()
        if not self._contexts and self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def collect(self, user_id: str, query: dict[str, Any]) -> CollectionResult:
        context = self._contexts.get(user_id)
        if context is None:
            raise ManualInterventionRequired("请先启动并登录 BOSS 浏览器", platform="boss")
        page = context.pages[0] if context.pages else context.new_page()
        keyword = str((query.get("keywords") or [""])[0])
        city = str((query.get("cities") or ["杭州"])[0])
        city_name, city_code = _resolve_city(city)
        search_url = (
            "https://www.zhipin.com/web/geek/job?"
            f"query={quote(keyword)}&city={quote(city_code)}&page=1"
        )
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        body = page.locator("body").inner_text(timeout=10000)
        inspect_response(200, body, platform="boss")
        api_url = (
            f"{API_JOB_LIST_PATH}?scene=1&query={quote(keyword)}"
            f"&city={quote(city_code)}&page=1&pageSize=30"
        )
        raw = page.evaluate(FETCH_API_JS.replace("__API_URL__", api_url))
        _inspect_boss_api_response(raw)
        jobs = [
            _to_job_summary(item, keyword, city_name)
            for item in _parse_api_response(raw)
        ]
        return CollectionResult(status="completed", jobs=jobs)
