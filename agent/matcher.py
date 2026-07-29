"""职位匹配评分 — 确定性规则引擎。

当 LLM 不可用时，使用基于规则的快速评分。
后续可切换到 LLM 5 维评分以获得更准确的结果。
"""

from __future__ import annotations

from typing import Any


def analyze_fit(
    job_title: str = "",
    company: str = "",
    job_desc: str = "",
    location: str = "",
    salary_text: str = "",
    tags: str = "",
) -> dict[str, Any]:
    """基于规则的职位匹配评分。

    评分维度（各 0-20 分）：
    - 技能匹配：关键词命中
    - 经验匹配：标题/描述中的经验要求
    - 地点匹配：丽水/浙江加分
    - 薪资匹配：薪资范围合理性
    - 职业发展：职位级别和方向匹配
    """
    scores: dict[str, int] = {}
    gaps: list[str] = []

    combined = f"{job_title} {job_desc} {tags}".lower()

    # 技能匹配
    skill_keywords = [
        "需求分析", "产品设计", "axure", "原型", "数据分析",
        "通信", "物联网", "硬件", "解决方案", "政企",
        "产品经理", "产品规划", "产品运营", "需求管理",
    ]
    skill_hits = sum(1 for kw in skill_keywords if kw in combined)
    scores["技能匹配"] = min(10 + skill_hits * 2, 20)

    # 经验匹配
    if "实习" in combined or "应届" in combined or "经验不限" in combined:
        scores["经验匹配"] = 16
    elif "1-3年" in combined or "1年" in combined:
        scores["经验匹配"] = 14
    elif "3-5年" in combined or "3年" in combined:
        scores["经验匹配"] = 10
    elif "5-10年" in combined or "5年" in combined:
        scores["经验匹配"] = 6
    else:
        scores["经验匹配"] = 12

    # 地点匹配
    location_lower = location.lower()
    if "丽水" in location_lower:
        scores["地点匹配"] = 20
    elif any(c in location_lower for c in ["杭州", "金华"]):
        scores["地点匹配"] = 18
    elif any(c in location_lower for c in ["浙江", "宁波", "温州", "绍兴", "嘉兴", "台州", "湖州", "衢州", "舟山"]):
        scores["地点匹配"] = 15
    else:
        scores["地点匹配"] = 5
        gaps.append("地点不在浙江")

    # 薪资匹配（不设硬底线）
    scores["薪资匹配"] = 14

    # 职业发展
    if any(kw in combined for kw in ["初级", "助理", "专员"]):
        scores["职业发展"] = 18
    elif any(kw in combined for kw in ["高级", "资深", "专家", "总监"]):
        scores["职业发展"] = 10
    elif any(kw in combined for kw in ["实习", "培训", "管培"]):
        scores["职业发展"] = 12
    else:
        scores["职业发展"] = 15

    # 排除项检测
    exclude_keywords = ["外包", "派遣", "劳务"]
    if any(kw in combined for kw in exclude_keywords):
        gaps.append("可能为外包/派遣岗位")

    total = sum(scores.values())
    if total >= 80:
        recommendation = "强烈推荐"
    elif total >= 65:
        recommendation = "推荐"
    elif total >= 50:
        recommendation = "可考虑"
    else:
        recommendation = "不推荐"

    return {
        "scores": scores,
        "total_score": total,
        "summary": _build_summary(scores, gaps, location, salary_text),
        "gaps": gaps,
        "recommendation": recommendation,
    }


def _build_summary(
    scores: dict[str, int],
    gaps: list[str],
    location: str,
    salary: str,
) -> str:
    parts = [f"综合评分{sum(scores.values())}/100"]
    top = max(scores, key=lambda k: scores[k])
    low = min(scores, key=lambda k: scores[k])
    parts.append(f"最强维度:{top}({scores[top]})")
    if scores[low] < 10:
        parts.append(f"最弱维度:{low}({scores[low]})")
    if "丽水" in location:
        parts.append("地点:丽水(最高优先级)")
    if salary:
        parts.append(f"薪资:{salary}")
    if gaps:
        parts.append(f"注意:{';'.join(gaps)}")
    return " | ".join(parts)
