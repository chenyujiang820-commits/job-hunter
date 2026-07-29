"""Apply 入口 — 选中职位 → 生成材料 → DOCX 输出。

用法:
    python tools/apply.py --job-id <id>     # 按缓存中的 job_key 选择
    python tools/apply.py --index <n>       # 按 rank 排序后的索引选择
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python tools/apply.py` to resolve project-root packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.workflow import generate_application_materials
from src.ranking_rules import rank_jobs
from tools.render_docx import generate_docx

SEEN_JOBS_PATH = Path("runtime/seen_jobs.json")
OUTPUT_DIR = Path("generated")


def load_jobs() -> list[dict]:
    """加载缓存中的所有职位。"""
    if not SEEN_JOBS_PATH.exists():
        print("未找到职位缓存，请先运行 scrape")
        return []
    data = json.loads(SEEN_JOBS_PATH.read_text(encoding="utf-8"))
    return rank_jobs(data.get("jobs", []))


def find_job(jobs: list[dict], job_id: str | None = None, index: int | None = None) -> dict | None:
    """按 job_key 或索引查找职位。"""
    if job_id:
        for j in jobs:
            if j.get("job_key", "") == job_id or j.get("id", "") == job_id:
                return j
        print(f"未找到 job_id={job_id}")
        return None

    if index is not None:
        if 0 <= index < len(jobs):
            return jobs[index]
        print(f"索引 {index} 超出范围 (0-{len(jobs)-1})")
        return None

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="生成职位申请材料")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job-id", help="按 job_key 或 id 选择")
    group.add_argument("--index", type=int, help="按缓存索引选择")
    parser.add_argument("--output", help="输出目录", default=str(OUTPUT_DIR))
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM，生成模板材料")
    args = parser.parse_args()

    jobs = load_jobs()
    if not jobs:
        return 1

    job = find_job(jobs, job_id=args.job_id, index=args.index)
    if not job:
        return 1

    title = job.get("title", "未知岗位")
    company = job.get("company", "未知公司")
    print(f"选中: {title} @ {company}")
    print(f"地点: {job.get('location','?')} | 薪资: {(job.get('salary',{}) or {}).get('raw','?')}")
    print()
    print(
        f"排序: 城市层级={job.get('_tier', '?')} | "
        f"方向分={job.get('_direction_score', '?')} | "
        f"风险标记={', '.join(job.get('_flags', [])) or '无'}"
    )
    print()

    if args.skip_llm:
        # 快速测试模式
        resume_md = f"# {title} - 简历\n\n## 个人简介\n\n通信工程专业本科，目标岗位为{title}。\n\n## 技能\n\n需求分析、产品设计、Axure\n\n## 教育\n\n本科 | 通信工程"
        cover_md = f"# 求职信\n\n尊敬的招聘负责人：\n\n我对贵司的{title}岗位非常感兴趣..."
        print("（跳过 LLM，使用模板材料）")
    else:
        print("正在分析匹配度...")
        result = generate_application_materials(job)

        fit = result["fit"]
        review = result["review"]
        print(f"匹配评分: {fit.get('total_score', 0)}/100")
        print(f"推荐: {fit.get('recommendation', '未知')}")
        print(f"评审: {'✅ 通过' if review.get('approved') else '⚠️ 需修订'}")
        print()

        resume_md = result["resume"]
        cover_md = result["cover"]

    # 生成 DOCX
    safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-（）()").strip()
    output_path = Path(args.output) / f"{safe_title}.docx"
    path = generate_docx(output_path, resume_md, cover_md, title=f"{title} - {company}")
    print(f"✅ 已生成: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
