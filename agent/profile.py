"""候选人画像管理。

基于用户真实简历，本地存储，不对外同步。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROFILE_DIR = Path(__file__).resolve().parents[1] / "profiles"


def get_profile() -> dict[str, Any]:
    """读取候选人画像。"""
    return {
        "name": "蒋辰宇",
        "title": "初级产品经理",
        "phone": "19818100936",
        "email": "19818100936@163.com",
        "location": "丽水",
        "party_member": True,
        "summary": (
            "通信工程专业本科（GPA 3.36/4.0，专业前5%），中共党员。"
            "1年政企客户经理经验，擅长通信与信息化解决方案，"
            "主导过273万和630万的5G+数字化车间集成项目。"
            "具备从技术视角理解客户需求、推动项目落地的能力。"
            "目标转向通信/硬件/物联网方向的产品经理岗位。"
        ),
        "skills": [
            "需求分析",
            "产品设计",
            "Axure",
            "通信原理",
            "物联网",
            "5G",
            "数据分析",
            "Linux基础",
            "Office",
            "项目管理",
            "客户沟通",
            "政企解决方案",
        ],
        "experience": [
            {
                "company": "中国电信股份有限公司义乌分公司",
                "title": "政企客户经理",
                "period": "2024.05 - 2025.03",
                "department": "政企中心",
                "location": "义乌",
                "summary": (
                    "为企业客户提供定制化通信与信息化服务，推动客户数字化转型。"
                    "负责战新业务拓展，涵盖企业网络安全、SD-WAN国际业务、"
                    "企业云业务、宽带网络、安防监控等。"
                ),
                "highlights": [
                    "主导浙江XX服饰5G+数字化车间项目，签约额273.9万，融合5G定制网+AI视觉+云网系统+智慧园区+数字孪生+网络安全",
                    "主导浙江XX拉链5G+数字化车间项目，签约额630万，金华地区首个集成5G+云网+ERP/MES/WMS的数字化车间项目",
                    "联合经信局推广网络安全产品（安全大脑），赋能走访企业70余家，成功签约50余户",
                ],
            }
        ],
        "education": [
            {
                "school": "中国计量大学现代科技学院",
                "degree": "本科",
                "major": "通信工程",
                "department": "信息工程学院",
                "period": "2020.10 - 2024.06",
                "gpa": "3.36/4.0（专业前5%）",
                "honors": [
                    "校级优秀毕业生",
                    "浙江省政府奖学金（2022、2023）",
                    "一等奖学金（2023）",
                    "大唐杯5G竞赛浙江省二等奖（2023）",
                    "浙江省高数竞赛三等奖（2023）",
                    "全国大学生数学建模优胜奖（2022）",
                ],
            }
        ],
        "projects": [
            {
                "name": "浙江XX服饰5G+数字化车间集成服务项目",
                "role": "项目成员",
                "summary": (
                    "签约额273.9万。融合5G定制网+AI视觉+云网系统+智慧园区平台"
                    "+数字孪生+网络安全服务。带动30余户高套发展和350间宿舍宽带。"
                ),
            },
            {
                "name": "浙江XX拉链5G+数字化车间集成服务项目",
                "role": "项目成员",
                "summary": (
                    "签约额630万，金华地区首个集成5G+云网系统"
                    "+ERP/MES/WMS软件系统的综合性数字化车间服务项目。"
                ),
            },
            {
                "name": "网络安全产品推广",
                "role": "项目成员",
                "summary": (
                    "联合经信局推广安全大脑等电信网安产品，"
                    "累计举办安全培训会3次，赋能走访企业70余家，签约50余户。"
                ),
            },
        ],
        "certificates": [
            "英语CET-4",
            "计算机二级",
            "驾驶证",
        ],
        "target": {
            "positions": ["初级产品经理", "产品助理", "政企解决方案"],
            "cities": ["丽水", "杭州", "金华"],
            "industries": ["通信", "硬件", "物联网", "政企解决方案", "5G"],
        },
    }


def format_profile_for_prompt() -> str:
    """将候选人画像格式化为 LLM prompt 可用的文本。"""
    p = get_profile()

    lines = [
        "## 候选人资料",
        f"姓名: {p['name']}",
        f"求职意向: {p['title']}",
        f"电话: {p.get('phone', '')}",
        f"邮箱: {p.get('email', '')}",
        f"所在地: {p.get('location', '')}",
        f"政治面貌: {'中共党员' if p.get('party_member') else ''}",
        "",
        f"简介: {p['summary']}",
        "",
    ]

    if p["skills"]:
        lines.append(f"技能: {', '.join(p['skills'])}")
        lines.append("")

    if p["experience"]:
        lines.append("## 工作经历")
        for exp in p["experience"]:
            lines.append(
                f"- {exp.get('company','')} | {exp.get('title','')} "
                f"({exp.get('period','')})"
            )
            if exp.get("summary"):
                lines.append(f"  职责: {exp['summary']}")
            for h in exp.get("highlights", []):
                lines.append(f"  亮点: {h}")
        lines.append("")

    if p["education"]:
        lines.append("## 教育经历")
        for edu in p["education"]:
            lines.append(
                f"- {edu.get('school','')} | {edu.get('major','')} | "
                f"{edu.get('degree','')} ({edu.get('period','')})"
            )
            if edu.get("gpa"):
                lines.append(f"  GPA: {edu['gpa']}")
            if edu.get("honors"):
                lines.append(f"  荣誉: {', '.join(edu['honors'])}")
        lines.append("")

    if p["projects"]:
        lines.append("## 项目经历")
        for proj in p["projects"]:
            lines.append(
                f"- {proj.get('name','')} ({proj.get('role','')}): "
                f"{proj.get('summary','')}"
            )
        lines.append("")

    lines.append("## 求职目标")
    t = p["target"]
    lines.append(f"- 目标岗位: {', '.join(t['positions'])}")
    lines.append(f"- 目标城市: {', '.join(t['cities'])}")
    lines.append(f"- 偏好行业: {', '.join(t['industries'])}")

    return "\n".join(lines)
