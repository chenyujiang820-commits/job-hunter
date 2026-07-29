"""Apply 工作流编排 — 分析 → 生成 → 评审 → 修订。

依赖注入设计，方便测试。
参考 job-research agent/workflow.py。
"""

from __future__ import annotations

from typing import Any, Callable


def generate_application_materials(
    posting: dict[str, Any],
    *,
    fit_fn: Callable[..., dict[str, Any]] | None = None,
    resume_fn: Callable[..., str] | None = None,
    cover_fn: Callable[..., str] | None = None,
    review_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """生成职位申请材料（简历 + 求职信），含评审→修订闭环。

    Args:
        posting: 职位 dict（含 title/company/description/location/salary/tags）
        fit_fn: 匹配分析函数
        resume_fn: 简历生成函数
        cover_fn: 求职信生成函数
        review_fn: 评审函数

    Returns:
        {
            "fit": dict,          # 匹配分析结果
            "resume": str,        # Markdown 简历
            "cover": str,         # 求职信
            "review": dict,       # 评审结果
        }
    """
    if fit_fn is None:
        from agent.matcher import analyze_fit
        fit_fn = analyze_fit
    if resume_fn is None:
        from agent.generator import generate_resume
        resume_fn = generate_resume
    if cover_fn is None:
        from agent.generator import generate_cover_letter
        cover_fn = generate_cover_letter
    if review_fn is None:
        from agent.reviewer import review_drafts
        review_fn = review_drafts

    # 提取字段
    job_title = posting.get("title", "")
    company = posting.get("company", "")
    job_desc = posting.get("description", "") or ""
    location = posting.get("location", "") or ""
    tags = posting.get("tags", "") or ""
    salary = posting.get("salary") or {}
    salary_text = salary.get("raw", "") if isinstance(salary, dict) else str(salary)

    # 1. 匹配分析
    fit = fit_fn(
        job_title=job_title,
        company=company,
        job_desc=job_desc,
        location=location,
        salary_text=salary_text,
        tags=tags,
    )
    fit_summary = fit.get("summary", "")

    # 2. 生成初稿
    resume = resume_fn(job_title, company, job_desc, fit_summary)
    cover = cover_fn(job_title, company, job_desc, fit_summary)

    # 3. 评审
    review = review_fn(job_title, company, job_desc, resume, cover)

    # 4. 若未通过，用改进建议修订一轮
    if not review.get("approved", True):
        improvements = review.get("improvements", []) or []
        if improvements:
            resume = resume_fn(
                job_title, company, job_desc, fit_summary,
                improvements=improvements,
            )
            cover = cover_fn(
                job_title, company, job_desc, fit_summary,
                improvements=improvements,
            )

    return {
        "fit": fit,
        "resume": resume,
        "cover": cover,
        "review": review,
    }
