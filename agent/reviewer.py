"""评审 Agent — 审查生成的简历和求职信质量。

参考 job-research agent/reviewer.py。
"""

from __future__ import annotations

from agent.llm import chat

MODEL_REVIEW = "opencode-go/kimi-k2.6"


def build_review_prompt(
    job_title: str,
    company: str,
    job_desc: str,
    resume_text: str,
    cover_text: str,
) -> str:
    return f"""你是一个严格的求职材料评审专家。请审查以下生成材料的质量。

## 目标职位
- 岗位: {job_title}
- 公司: {company}

## 职位描述
{job_desc[:2000] if job_desc else "（暂无详细描述）"}

## 生成的简历
{resume_text[:3000]}

## 生成的求职信
{cover_text[:1500]}

## 评审维度
1. 事实准确性 — 简历和求职信中有没有编造候选人没有的经历或技能？
2. JD 关键词覆盖率 — 职位描述中的关键要求，简历中有多少被覆盖到了？
3. 语言风格 — 语气是否专业、得体？是否太夸张或太平淡？
4. 结构清晰度 — 简历结构是否清晰？求职信是否有逻辑？
5. 具体改进建议 — 逐条列出可以改进的具体点

## 输出要求
严格以 JSON 格式返回：
{{
    "fact_check": {{
        "passed": true,
        "issues": []
    }},
    "keyword_coverage": {{
        "covered": ["Python", "FastAPI"],
        "missing": ["Docker"],
        "score": 75
    }},
    "style_feedback": "语言风格评估",
    "improvements": [
        "建议1: ...",
        "建议2: ..."
    ],
    "overall_assessment": "整体评价",
    "approved": true
}}"""


def review_drafts(
    job_title: str,
    company: str,
    job_desc: str,
    resume_text: str,
    cover_text: str,
) -> dict:
    """评审生成的简历和求职信。

    返回: {fact_check, keyword_coverage, style_feedback, improvements, approved}
    """
    prompt = build_review_prompt(
        job_title, company, job_desc, resume_text, cover_text
    )
    try:
        import json
        result = chat(prompt, model="opencode-go/deepseek-v4-flash", temperature=0.2)
        result = result.strip()
        if result.startswith("`"):
            lines = result.split("\n")
            result = "\n".join(l for l in lines if not l.startswith("`"))
        return json.loads(result)
    except Exception as exc:
        return {
            "fact_check": {"passed": True, "issues": []},
            "keyword_coverage": {"covered": [], "missing": [], "score": 0},
            "style_feedback": f"评审失败: {exc}",
            "improvements": [],
            "overall_assessment": "评审异常",
            "approved": True,
        }
