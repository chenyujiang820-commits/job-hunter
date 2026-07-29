"""Outcome CLI — 投递状态管理。

用法:
    python tools/outcome.py record <job_key>    # 记录投递
    python tools/outcome.py status <job_key> <状态>   # 更新状态
    python tools/outcome.py list               # 列出所有
    python tools/outcome.py summary            # 汇总
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python tools/outcome.py` to resolve project-root packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.outcome import (
    record_application,
    update_status,
    get_applications,
    summary,
    has_applied,
    STATUS_ORDER,
)

SEEN_JOBS_PATH = Path("runtime/seen_jobs.json")


def _find_job(job_key: str) -> dict | None:
    if not SEEN_JOBS_PATH.exists():
        return None
    data = json.loads(SEEN_JOBS_PATH.read_text(encoding="utf-8"))
    for j in data.get("jobs", []):
        if j.get("job_key") == job_key:
            return j
    return None


def cmd_record(args):
    job = _find_job(args.job_key)
    if not job:
        print(f"未找到职位: {args.job_key}")
        return 1

    if has_applied(args.job_key):
        print(f"该职位已记录投递")
        return 1

    rec = record_application(job, status=args.status or "收藏", note=args.note or "")
    print(f"✅ 已记录: {rec.title} @ {rec.company} → {rec.status}")


def cmd_status(args):
    rec = update_status(args.job_key, args.status, note=args.note or "")
    if rec:
        print(f"✅ {rec.title} → {rec.status}")
    else:
        print(f"未找到投递记录: {args.job_key}")
        return 1


def cmd_list(args):
    apps = get_applications(status_filter=args.status or None)
    if not apps:
        print("暂无投递记录")
        return

    print(f"{'状态':8s} {'岗位':28s} {'公司':16s} {'更新日期':12s}")
    print("-" * 70)
    for a in apps:
        date = a.last_updated[:10]
        print(f"{a.status:8s} {a.title[:28]:28s} {a.company[:16]:16s} {date}")


def cmd_summary(args):
    s = summary()
    print("投递状态汇总:")
    print("-" * 30)
    for status in STATUS_ORDER:
        cnt = s.get(status, 0)
        if cnt:
            bar = "█" * cnt
            print(f"  {status:8s} {cnt:3d} {bar}")
    print("-" * 30)
    print(f"  {'总计':8s} {s.get('总计', 0):3d}")


def main() -> int:
    parser = argparse.ArgumentParser(description="投递状态管理")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("record", help="记录投递")
    p.add_argument("job_key")
    p.add_argument("--status", default="收藏")
    p.add_argument("--note")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("status", help="更新状态")
    p.add_argument("job_key")
    p.add_argument("status")
    p.add_argument("--note")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("list", help="列出投递")
    p.add_argument("--status", help="按状态筛选")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("summary", help="汇总")
    p.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
