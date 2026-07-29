"""Deterministic hard filters and location tiers for domestic job ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from src.job_schema import CandidateProfile, JobSummary


LocationTier = Literal["lishui", "hangzhou_jinhua", "other_zhejiang", "outside"]

_ZHEJIANG_CITIES = (
    "杭州",
    "宁波",
    "温州",
    "嘉兴",
    "湖州",
    "绍兴",
    "金华",
    "衢州",
    "舟山",
    "台州",
    "丽水",
)
_EXCLUSION_DEFAULTS = ("劳务派遣", "派遣制", "外包", "人力外包", "岗位外包")
_POSTGRADUATE_REQUIREMENTS = (
    "硕士及以上",
    "研究生及以上",
    "博士及以上",
    "博士后",
    "要求硕士",
    "要求研究生",
    "要求博士",
    "硕士学历",
    "研究生学历",
    "博士学历",
)
_LONG_TERM_ONSITE = ("长期驻场", "长期驻点", "长期出差驻场", "常驻现场", "长期现场办公")


@dataclass(frozen=True)
class FilterResult:
    passed: bool
    reasons: list[str]
    flags: list[str]
    location_tier: LocationTier


def _text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def location_tier(location: str) -> LocationTier:
    value = _text(location)
    if "省外" in value or "省外地区" in value:
        return "outside"
    if "丽水" in value:
        return "lishui"
    if "杭州" in value or "金华" in value:
        return "hangzhou_jinhua"
    if "浙江" in value or any(city in value for city in _ZHEJIANG_CITIES):
        return "other_zhejiang"
    return "outside"


def _job_text(job: Mapping[str, Any]) -> str:
    fields = ("title", "company", "location", "description", "raw_text")
    return " ".join(_text(job.get(field)) for field in fields)


def _education_text(job: Mapping[str, Any]) -> str:
    return _text(job.get("education")) + " " + _text(job.get("raw_text"))


def apply_hard_filters(job: JobSummary, profile: CandidateProfile) -> FilterResult:
    reasons: list[str] = []
    flags: list[str] = []
    tier = location_tier(str(job.get("location") or ""))
    full_text = _job_text(job)

    exclusions = tuple(profile.get("hard_exclusions", _EXCLUSION_DEFAULTS))
    if any(_text(term) in full_text for term in exclusions):
        reasons.append("dispatch_or_outsourcing")

    education = _education_text(job)
    if any(requirement in education for requirement in _POSTGRADUATE_REQUIREMENTS):
        reasons.append("education_above_bachelor")

    if tier == "outside":
        reasons.append("location_outside_zhejiang")

    if any(marker in full_text for marker in _LONG_TERM_ONSITE):
        flags.append("long_term_onsite")

    return FilterResult(
        passed=not reasons,
        reasons=reasons,
        flags=flags,
        location_tier=tier,
    )


# ---------------------------------------------------------------------------
# 方向匹配评分
# ---------------------------------------------------------------------------

# 目标方向关键词 — 候选人偏好的技术型产品方向
_TARGET_DIRECTIONS = (
    "通信", "通讯", "5g", "4g", "物联网", "iot",
    "硬件", "嵌入式", "芯片", "半导体",
    "政企", "政府", "解决方案", "toG", "tog", "toB", "tob",
    "数据产品", "数据分析", "数据平台",
    "ai产品", "人工智能", "大模型", "智能",
    "网络", "云计算", "云平台", "saas",
    "新能源", "电力", "能源管理",
    "产品规划", "需求分析", "产品设计", "产品经理",
)

# 不相关方向 — 命中大幅降分
_IRRELEVANT_DIRECTIONS = (
    "宠物", "猫", "狗", "动物",
    "团餐", "餐饮", "食品", "生鲜", "厨师",
    "建筑", "施工", "工程经理", "土木", "装修",
    "金融产品", "银行", "证券", "保险", "信贷", "风控", "理财",
    "医疗", "医药", "医院", "临床", "肿瘤", "护士", "药品",
    "教育产品", "教培", "培训",
    "地产", "房产", "物业",
    "服装", "纺织", "鞋",
    "游戏", "电竞",
    "直播", "短视频",
    "数字货币", "web3", "nft",
    "招聘", "hr", "人力资源",
    "法务", "合规",
    "质量主管", "质检",
    "特斯拉", "汽车销售",
    "运营", "新媒体", "内容运营", "电商运营",
    "bdm", "城市主管", "销售",
)


def direction_score(job: JobSummary, profile: CandidateProfile | None = None) -> int:
    """计算职位方向与候选人偏好的匹配度（0-100）。

    目标方向（通信/硬件/物联网/政企/数据/AI）加分，
    不相关方向（宠物/餐饮/建筑/金融）减分。
    """
    full_text = _job_text(job)
    title = _text(job.get("title"))
    tags = _text(job.get("tags"))
    combined = f"{full_text} {title} {tags}"

    score = 50  # 基准分

    # 目标方向命中加分
    target_hits = 0
    for kw in _TARGET_DIRECTIONS:
        if kw in combined:
            target_hits += 1
    # 前 3 个命中各 +10，之后各 +5
    score += min(target_hits, 3) * 10 + max(0, target_hits - 3) * 5
    score = min(score, 90)  # 硬上限 90（除非地点满分）

    # 不相关方向命中的惩罚
    for kw in _IRRELEVANT_DIRECTIONS:
        if kw in combined:
            score -= 35
            break  # 命中一个即大幅降分

    # 如果岗位名称看起来就是产品方向，加点分
    if "产品" in title:
        score += 5

    return max(0, min(score, 100))


def rank_jobs(
    jobs: list[JobSummary],
    profile: CandidateProfile | None = None,
) -> list[dict[str, Any]]:
    """对通过硬过滤的岗位进行综合排序。

    排序权重: 城市层级 > 方向匹配 > 薪资水平。
    返回带排序元数据的 dict 列表。
    """
    tier_priority = {
        "lishui": 0,
        "hangzhou_jinhua": 1,
        "other_zhejiang": 2,
        "outside": 3,
    }

    ranked = []
    for job in jobs:
        filter_result = apply_hard_filters(job, profile or {})
        if not filter_result.passed:
            continue

        dir_score = direction_score(job, profile)
        tier = filter_result.location_tier
        s = job.get("salary", {}) or {}
        sal_mid = (s.get("min", 0) or 0) + (s.get("max", 0) or 0)

        ranked.append({
            **job,
            "_tier": tier,
            "_direction_score": dir_score,
            "_flags": filter_result.flags,
            "_sort_key": (
                tier_priority.get(tier, 3),  # 城市优先
                -dir_score,                    # 方向降序
                -sal_mid,                      # 薪资降序
            ),
        })

    ranked.sort(key=lambda j: j["_sort_key"])
    return ranked
