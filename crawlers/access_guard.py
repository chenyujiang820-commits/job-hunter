"""Access-state checks shared by read-only platform crawlers."""

from __future__ import annotations

import re
from typing import Any


class ManualInterventionRequired(RuntimeError):
    """Raised when a platform requires a user to intervene in a browser."""

    status = "paused_manual_intervention"

    def __init__(
        self,
        reason: str,
        *,
        platform: str,
        status_code: int | None = None,
    ) -> None:
        self.reason = reason
        self.platform = platform
        self.status_code = status_code
        super().__init__(self.message)

    @property
    def message(self) -> str:
        return f"暂停人工处理（{self.platform}）：{self.reason}"


_BODY_MARKERS = (
    ("captcha", "检测到 CAPTCHA 页面"),
    ("验证码", "检测到验证码页面"),
    ("滑块", "检测到滑块验证页面"),
    ("安全验证", "检测到安全验证页面"),
    ("访问受限", "检测到访问受限页面"),
    ("操作频繁", "检测到访问频率限制"),
    ("请求过于频繁", "检测到访问频率限制"),
    ("反爬", "检测到平台访问控制页面"),
    ("too many requests", "检测到访问频率限制"),
    ("rate limit", "检测到访问频率限制"),
    ("access denied", "检测到访问拒绝页面"),
    ("请登录", "检测到登录页面"),
    ("登录后", "检测到登录要求"),
    ("<!doctype html><html><body><script>window._", "检测到 JS 挑战页面（反爬）"),
    ("<html><body><script>window._", "检测到 JS 挑战页面（反爬）"),
)


def inspect_response(
    status_code: int,
    body: Any,
    *,
    platform: str,
) -> None:
    """Raise an explicit pause signal for blocked or gated responses."""
    if status_code in {401, 403, 429}:
        raise ManualInterventionRequired(
            f"HTTP {status_code} 响应", platform=platform, status_code=status_code
        )
    if status_code >= 500:
        raise ManualInterventionRequired(
            f"HTTP {status_code} 异常响应", platform=platform, status_code=status_code
        )

    raw_text = str(body or "").lower()
    text = re.sub(r"\s+", "", raw_text)
    for marker, reason in _BODY_MARKERS:
        if marker in raw_text or marker.replace(" ", "") in text:
            raise ManualInterventionRequired(reason, platform=platform, status_code=status_code)
