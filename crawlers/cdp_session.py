"""Chrome CDP raw protocol 会话封装。

通过 WebSocket 直接与 Chrome DevTools Protocol 通信，
不依赖 Playwright/Selenium 等重型框架。

参考 boss-zhipin-scraper 的 CDPSession 实现。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CDP_PORT = 9222

# 后台页面 visibility override，避免 document.hidden=true 触发反爬
BACKGROUND_VISIBILITY_SCRIPT = (
    "Object.defineProperty(document, 'hidden', {get: () => false});"
    "Object.defineProperty(document, 'visibilityState', {get: () => 'visible'});"
    "Object.defineProperty(document, 'webkitHidden', {get: () => false});"
    "Object.defineProperty(document, 'webkitVisibilityState', {get: () => 'visible'});"
)


class CDPSession:
    """Chrome CDP WebSocket 会话。

    前置条件: Chrome 需以调试模式启动:
        chrome --remote-debugging-port=9222 --remote-allow-origins=*

    Chrome 150+ 默认拒绝非 localhost 来源的 WebSocket 连接，
    必须添加 --remote-allow-origins=* 参数。

    使用方式:
        session = CDPSession(9222)
        tid, sid = session.create_page()
        session.navigate("https://example.com", sid)
        result = session.eval_js("document.title", sid)
        session.close()
    """

    def __init__(self, cdp_port: int = DEFAULT_CDP_PORT) -> None:
        import requests as _requests
        import websocket as _websocket  # type: ignore[import-untyped]

        self.cdp_port = cdp_port
        resp = _requests.get(
            f"http://127.0.0.1:{cdp_port}/json/version", timeout=10
        )
        ws_url = resp.json()["webSocketDebuggerUrl"]
        self.ws = _websocket.create_connection(ws_url, timeout=60)
        self.mid = 0

    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        sid: str | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        """发送 CDP 命令并等待响应。

        Args:
            method: CDP 方法名 (e.g. "Page.navigate")
            params: 参数字典
            sid: 目标 session ID
            timeout: 超时秒数

        Returns:
            CDP 响应字典
        """
        import websocket as _websocket  # type: ignore[import-untyped]

        self.mid += 1
        msg: dict[str, Any] = {
            "id": self.mid,
            "method": method,
            "params": params or {},
        }
        if sid:
            msg["sessionId"] = sid
        self.ws.send(json.dumps(msg))

        start = time.time()
        for _ in range(1000):
            if time.time() - start > timeout:
                raise TimeoutError(
                    f"CDP send({method}) 超时 ({timeout}s)"
                )
            try:
                raw = self.ws.recv()
            except _websocket.WebSocketTimeoutException:
                raise TimeoutError(
                    f"CDP WebSocket recv 超时, method={method}"
                )
            try:
                r = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                logger.debug("跳过非 JSON 消息: %s", raw[:100])
                continue
            if r.get("id") == self.mid:
                return r

        raise TimeoutError(
            f"CDP send({method}) 在 1000 条消息内未找到匹配响应"
        )

    def eval_js(self, js: str, sid: str) -> Any:
        """在页面中执行 JavaScript 并返回结果。"""
        r = self.send(
            "Runtime.evaluate",
            {"expression": js, "returnByValue": True},
            sid,
        )
        return r.get("result", {}).get("result", {}).get("value", None)

    def create_page(
        self, background: bool = True
    ) -> tuple[str, str]:
        """创建新标签页并返回 (target_id, session_id)。

        background=True 时注入 visibility override 脚本。
        """
        target = self.send(
            "Target.createTarget",
            {"url": "about:blank", "background": background},
        )
        target_id = target["result"]["targetId"]
        attached = self.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        session_id = attached["result"]["sessionId"]
        if background:
            self.send(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": BACKGROUND_VISIBILITY_SCRIPT},
                session_id,
            )
        return target_id, session_id

    def navigate(self, url: str, sid: str) -> None:
        """导航到指定 URL。"""
        self.send("Page.navigate", {"url": url}, sid)

    def close_target(self, target_id: str) -> None:
        """关闭标签页。"""
        self.send("Target.closeTarget", {"targetId": target_id})

    def close(self) -> None:
        """关闭 WebSocket 连接。"""
        self.ws.close()


def is_cdp_ready(cdp_port: int = DEFAULT_CDP_PORT) -> bool:
    """检查 Chrome CDP 是否可用。"""
    try:
        import requests as _requests
        r = _requests.get(
            f"http://127.0.0.1:{cdp_port}/json/version", timeout=3
        )
        return r.status_code == 200
    except Exception:
        return False
