"""投递状态跟踪 — 本地记录求职结果和状态流转。

只记录用户手动报告的结果，不调用平台写操作。
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# 状态机：按求职流程推进
STATUS_ORDER: tuple[str, ...] = (
    "收藏",
    "已投递",
    "简历筛选",
    "一面",
    "二面",
    "三面",
    "HR面",
    "已offer",
    "已拒绝",
    "已放弃",
)

# 活跃状态（仍在流程中）
ACTIVE_STATUSES = frozenset(
    {"收藏", "已投递", "简历筛选", "一面", "二面", "三面", "HR面"}
)

# 终态
FINAL_STATUSES = frozenset({"已offer", "已拒绝", "已放弃"})

StatusValue = Literal[
    "收藏", "已投递", "简历筛选",
    "一面", "二面", "三面", "HR面",
    "已offer", "已拒绝", "已放弃",
]

TRACKER_PATH = Path("runtime") / "application_tracker.json"


@dataclass
class ApplicationRecord:
    """单条投递记录。"""

    job_key: str
    title: str
    company: str
    location: str
    url: str
    status: str
    note: str
    applied_date: str | None
    first_seen: str
    last_updated: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_tracker() -> dict[str, Any]:
    """加载 tracking 状态。"""
    if not TRACKER_PATH.exists():
        return {"version": 1, "applications": []}

    data = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("applications"), list):
        raise ValueError("tracker 格式错误")
    return data


def _save_tracker(data: dict[str, Any]) -> None:
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRACKER_PATH.with_name(f".{TRACKER_PATH.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TRACKER_PATH)


def has_applied(job_key: str) -> bool:
    """检查是否已投递过该职位。"""
    data = _load_tracker()
    for app in data.get("applications", []):
        if app.get("job_key") == job_key:
            return True
    return False


def record_application(
    job: dict[str, Any],
    status: StatusValue = "收藏",
    note: str = "",
) -> ApplicationRecord:
    """记录一条投递申请。

    Args:
        job: 职位 dict（需含 job_key/title/company/location/url）
        status: 初始状态，默认"收藏"
        note: 备注

    Returns:
        创建的 ApplicationRecord

    Raises:
        ValueError: 状态不在允许列表中，或已投递过
    """
    if status not in STATUS_ORDER:
        raise ValueError(
            f"无效状态: {status}，允许: {', '.join(STATUS_ORDER)}"
        )

    job_key = job.get("job_key", "")
    if not job_key:
        raise ValueError("职位缺少 job_key")

    if has_applied(job_key):
        raise ValueError(f"该职位已记录投递: {job_key}")

    now = _now()
    today = _today()
    record = {
        "job_key": job_key,
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location", ""),
        "url": job.get("url", ""),
        "status": status,
        "note": note,
        "applied_date": today if status == "已投递" else None,
        "first_seen": today,
        "last_updated": now,
    }

    data = _load_tracker()
    data["applications"].append(record)
    data["updated_at"] = now
    _save_tracker(data)

    return ApplicationRecord(**record)


def update_status(
    job_key: str,
    new_status: StatusValue,
    note: str = "",
) -> ApplicationRecord | None:
    """更新投递状态。

    Args:
        job_key: 职位去重键
        new_status: 新状态
        note: 可选备注（追加到已有备注）

    Returns:
        更新后的记录，未找到返回 None
    """
    if new_status not in STATUS_ORDER:
        raise ValueError(
            f"无效状态: {new_status}，允许: {', '.join(STATUS_ORDER)}"
        )

    data = _load_tracker()
    for app in data.get("applications", []):
        if app.get("job_key") == job_key:
            now = _now()
            today = _today()

            old_status = app.get("status", "")
            app["status"] = new_status
            app["last_updated"] = now

            # 首次标记"已投递"时记录日期
            if new_status == "已投递" and not app.get("applied_date"):
                app["applied_date"] = today

            # 追加备注
            if note:
                existing = app.get("note", "")
                app["note"] = (
                    f"{existing}\n{now[:10]}: {note}"
                    if existing
                    else f"{now[:10]}: {note}"
                )

            data["updated_at"] = now
            _save_tracker(data)
            return ApplicationRecord(**app)

    return None


def get_applications(
    status_filter: str | None = None,
) -> list[ApplicationRecord]:
    """获取投递记录列表，可按状态筛选。

    Args:
        status_filter: 可选状态筛选

    Returns:
        ApplicationRecord 列表（按最近更新倒序）
    """
    data = _load_tracker()
    apps = data.get("applications", [])
    if status_filter:
        apps = [a for a in apps if a.get("status") == status_filter]
    records = [ApplicationRecord(**a) for a in apps]
    records.sort(key=lambda r: r.last_updated, reverse=True)
    return records


def summary() -> dict[str, int]:
    """投递状态汇总。"""
    data = _load_tracker()
    counts: dict[str, int] = {}
    for app in data.get("applications", []):
        status = app.get("status", "未知")
        counts[status] = counts.get(status, 0) + 1
    counts["总计"] = len(data.get("applications", []))
    return counts
