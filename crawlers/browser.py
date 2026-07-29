"""浏览器管理 — CDP 模式连接用户已有 Chrome。

通过 Chrome DevTools Protocol 连接用户已登录的浏览器，
无需额外安装浏览器驱动。用于提取 Cookie 和只读页面检查。

参考 job-research crawlers/browser.py。
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from config import DATA_DIR  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

CDP_PORT = 9222
CDP_PROFILE_DIR = DATA_DIR / "cdp_profile"

_page: Any = None
_context: Any = None
_pw: Any = None
_is_cdp: bool = False


def _is_chrome_with_debug() -> bool:
    """检查是否有 Chrome 在调试模式下运行。"""
    try:
        import httpx
        r = httpx.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _launch_chrome_cdp() -> bool:
    """自动启动带 CDP 端口的 Chrome（使用已有 profile 保持登录态）。"""
    candidates = [
        os.path.expanduser(
            "~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"
        ),
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ]
    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    for p in candidates:
        if Path(p).exists():
            try:
                subprocess.Popen(
                    [
                        p,
                        f"--remote-debugging-port={CDP_PORT}",
                        f"--user-data-dir={CDP_PROFILE_DIR}",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"已启动 Chrome（调试端口 {CDP_PORT}），等待 5 秒...")
                time.sleep(5)
                return _is_chrome_with_debug()
            except Exception:
                continue
    return False


def get_page():
    """获取浏览器页面对象。

    优先连接已有的 Chrome CDP，失败则自动启动。
    返回 playwright Page 对象。
    """
    global _page, _context, _pw, _is_cdp

    # 复用前先关闭旧页面，避免标签页泄漏
    if _page is not None:
        try:
            _page.close()
        except Exception:
            pass
        _page = None

    ws_url = None

    # 尝试 CDP 连接
    if _is_cdp or _is_chrome_with_debug():
        try:
            import httpx
            r = httpx.get(
                f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3
            )
            ws_url = r.json().get("webSocketDebuggerUrl")
        except Exception:
            pass

        if ws_url:
            try:
                from playwright.sync_api import sync_playwright
                _pw = sync_playwright().start()
                browser = _pw.chromium.connect_over_cdp(ws_url)
                ctx = (
                    browser.contexts[0]
                    if browser.contexts
                    else browser.new_context()
                )
                _page = ctx.new_page()
                _page.set_default_timeout(30000)
                _is_cdp = True
                logger.info("CDP 模式：连接已有 Chrome")
                return _page
            except Exception as e:
                logger.warning("CDP 连接失败: %s", e)

    # 自动启动 Chrome
    print("未检测到 Chrome 调试端口，尝试自动启动...")
    if _launch_chrome_cdp():
        try:
            import httpx
            r = httpx.get(
                f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3
            )
            ws_url = r.json().get("webSocketDebuggerUrl")
            from playwright.sync_api import sync_playwright
            _pw = sync_playwright().start()
            browser = _pw.chromium.connect_over_cdp(ws_url)
            ctx = (
                browser.contexts[0]
                if browser.contexts
                else browser.new_context()
            )
            _page = ctx.new_page()
            _page.set_default_timeout(30000)
            _is_cdp = True
            logger.info("CDP 模式：自动启动 Chrome 成功")
            return _page
        except Exception as e:
            logger.warning("自动启动 CDP 失败: %s", e)

    # 保底：Playwright 自启浏览器
    from playwright.sync_api import sync_playwright
    BROWSER_DATA_DIR = DATA_DIR / "browser_profile"
    BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _pw = sync_playwright().start()
    _context = _pw.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_DATA_DIR),
        headless=False,
        slow_mo=200,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--window-size=1280,800",
        ],
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    _context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        window.chrome = { runtime: {} };
    """)
    _page = _context.new_page()
    _page.set_default_timeout(30000)
    logger.info("Playwright 自启模式")
    return _page


def close_browser() -> None:
    """关闭浏览器连接。"""
    global _page, _context, _pw
    if _page:
        try:
            _page.close()
        except Exception:
            pass
        _page = None
    if _context:
        try:
            _context.close()
        except Exception:
            pass
        _context = None
    if _pw:
        try:
            _pw.stop()
        except Exception:
            pass
        _pw = None


def ensure_login(
    page, url: str, check_selector: str, login_hint: str = "请手动登录"
) -> bool:
    """导航到页面，等待用户手动登录。

    如果检测到验证码页面，提示用户处理。
    登录成功后返回 True，超时返回 False。
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        logger.warning("导航失败: %s", e)
        return False

    time.sleep(3)

    for _ in range(10):
        try:
            body = page.inner_text("body")[:200]
            if "验证" in body or "captcha" in body.lower():
                print("验证码页面，请手动处理...")
                time.sleep(5)
                continue
        except Exception:
            pass
        try:
            if page.locator(check_selector).first.is_visible():
                return True
        except Exception:
            pass
        time.sleep(1)

    print(f"\n{login_hint}")
    print("请在打开的浏览器中完成登录（扫码/账号密码）")
    print("登录成功后等待 120 秒...\n")
    for _ in range(120):
        time.sleep(1)
        try:
            if page.locator(check_selector).first.is_visible():
                print("登录成功！")
                return True
        except Exception:
            pass
    logger.warning("登录超时")
    return False
