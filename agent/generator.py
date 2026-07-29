"""简历和求职信生成。

骨架由模板生成（保证结构完整），
自我评价和求职信正文由 LLM 润色（可选）。
"""

from __future__ import annotations

from agent.profile import get_profile
from agent.llm import chat


def generate_resume(
    job_title: str,
    company: str,
    job_desc: str,
    fit_summary: str = "",
    improvements: list[str] | None = None,
) -> str:
    """生成简历 Markdown。"""
    profile = get_profile()

    # 技能列表
    skills = profile.get("skills", [])
    skills_str = "、".join(skills) if skills else "需求分析、产品设计、Axure"

    # 教育背景
    edu = (profile.get("education") or [{}])[0]

    # LLM 生成自我评价
    summary_prompt = f"""写 2-3 句中文自我评价。候选人:通信工程本科，共产党员，技能:{skills_str}。目标:{job_title}@{company}。特点:技术背景+产品思维，适合通信/硬件/物联网方向产品岗。不要编造经历。直接输出文字。"""
    try:
        self_eval = chat(summary_prompt, temperature=0.3, max_tokens=300)
        # 清理可能的问候语前缀
        if "您好" in self_eval[:20]:
            self_eval = self_eval.split("\n", 1)[-1] if "\n" in self_eval else self_eval
    except Exception:
        self_eval = (
            f"通信工程专业本科，具备技术背景与产品思维。"
            f"熟悉需求分析、产品设计流程，对通信、硬件、物联网方向有浓厚兴趣。"
            f"期望在{job_title}岗位上发挥技术+产品复合优势。"
        )

    resume = f"""# [待补充] - 求职简历

## 求职意向
{job_title} | {company} | 全职

## 教育背景
{edu.get("school", "[待补充]")} | {edu.get("major", "通信工程")} | {edu.get("degree", "本科")} | {edu.get("period", "")}
中共党员

## 技能
{skills_str}

## 自我评价
{self_eval}
"""
    return resume


def generate_cover_letter(
    job_title: str,
    company: str,
    job_desc: str,
    fit_summary: str = "",
    improvements: list[str] | None = None,
) -> str:
    """生成求职信 Markdown。"""
    profile = get_profile()

    letter_prompt = f"""写一封 200-300 字中文求职信。
候选人:通信工程本科，共产党员，求职{job_title}@{company}。
风格:专业真诚，不编造经历，突出通信专业背景+产品潜力。
称呼:尊敬的招聘负责人。署名:[待补充]。
直接输出求职信正文，不要问候语。"""

    try:
        body = chat(letter_prompt, temperature=0.3, max_tokens=500)
        if "您好" in body[:20]:
            body = body.split("\n", 1)[-1] if "\n" in body else body
    except Exception:
        body = (
            f"我对贵司的{job_title}岗位非常感兴趣。"
            f"作为一名通信工程专业的毕业生，我具备扎实的技术基础和产品思维。"
            f"希望能有机会加入{company}，在通信/物联网产品方向发挥我的能力。"
        )

    cover = f"""# 求职信

尊敬的招聘负责人：

{body.strip()}

此致
敬礼

[待补充]
"""
    return cover
