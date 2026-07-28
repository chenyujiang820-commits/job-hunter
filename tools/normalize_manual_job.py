"""Normalize a user-supplied Zhilian URL and pasted job text locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


LABELS = {
    "title": ("职位名称", "岗位名称", "职位", "岗位"),
    "company": ("公司名称", "公司", "招聘企业", "企业"),
    "location": ("工作地点", "地点", "工作城市", "城市"),
    "salary": ("薪资范围", "薪资", "薪酬", "工资"),
    "experience": ("工作经验", "经验要求", "经验"),
    "education": ("学历要求", "学历", "教育程度"),
    "date": ("发布日期", "发布时间", "更新时间", "更新日期"),
    "description": ("职位描述", "岗位职责", "工作内容", "职位详情"),
}

_LABEL_PATTERN = re.compile(
    r"^\s*(?P<label>职位名称|岗位名称|职位|岗位|公司名称|公司|招聘企业|企业|"
    r"工作地点|地点|工作城市|城市|薪资范围|薪资|薪酬|工资|工作经验|经验要求|经验|"
    r"学历要求|学历|教育程度|发布日期|发布时间|更新时间|更新日期|职位描述|岗位职责|"
    r"工作内容|职位详情)\s*[:：]\s*(?P<value>.*)\s*$"
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _label_key(label: str) -> str | None:
    for key, aliases in LABELS.items():
        if label in aliases:
            return key
    return None


def _parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        match = _LABEL_PATTERN.match(line)
        if match:
            current = _label_key(match.group("label"))
            if current is not None:
                sections.setdefault(current, [])
                value = _clean(match.group("value"))
                if value:
                    sections[current].append(value)
            continue

        if current == "description" and _clean(line):
            sections[current].append(_clean(line) or "")

    return {key: "\n".join(values).strip() for key, values in sections.items() if values}


def _parse_salary(value: str | None) -> dict[str, Any] | None:
    value = _clean(value)
    if not value:
        return None

    negotiable = any(term in value for term in ("面议", "面谈", "可议"))
    months_per_year = 13 if re.search(r"(?:·|\s)?13\s*薪", value) else None
    if negotiable and not re.search(r"\d", value):
        return {
            "raw": value,
            "min": None,
            "max": None,
            "unit": "month",
            "months_per_year": months_per_year,
            "negotiable": True,
        }

    range_match = re.search(
        r"(?P<min>\d+(?:\.\d+)?)\s*(?:[-~至到])\s*"
        r"(?P<max>\d+(?:\.\d+)?)\s*(?P<unit>K|k|千|万)?",
        value,
    )
    single_match = re.search(r"(?P<single>\d+(?:\.\d+)?)\s*(?P<unit>K|k|千|万)", value)
    match = range_match or single_match
    if not match:
        return {
            "raw": value,
            "min": None,
            "max": None,
            "unit": "month",
            "months_per_year": months_per_year,
            "negotiable": negotiable,
        }

    unit = (match.groupdict().get("unit") or "").lower()
    multiplier = {"k": 1000, "千": 1000, "万": 10000}.get(unit, 1)
    minimum = float(match.groupdict().get("min") or match.group("single")) * multiplier
    maximum = float(match.groupdict().get("max") or minimum / multiplier) * multiplier
    return {
        "raw": value,
        "min": int(minimum),
        "max": int(maximum),
        "unit": "month",
        "months_per_year": months_per_year,
        "negotiable": negotiable,
    }


def _extract_title(text: str, sections: dict[str, str]) -> str | None:
    if sections.get("title"):
        return sections["title"]
    for line in text.splitlines():
        candidate = _clean(line)
        if candidate and not _LABEL_PATTERN.match(line):
            return candidate
    return None


def _job_id(url: str, text: str) -> str:
    match = re.search(r"(CC[0-9A-Z]+J[0-9]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)
    digest = hashlib.sha256(f"{url}\n{text}".encode("utf-8")).hexdigest()[:16]
    return f"manual-{digest}"


def normalize_manual_job(url: str, text: str) -> dict[str, Any]:
    """Return a deterministic JobSummary from local, user-supplied data only."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute http(s) URL")

    text = text.strip()
    sections = _parse_sections(text)
    return {
        "id": _job_id(url.strip(), text),
        "title": _extract_title(text, sections),
        "company": sections.get("company"),
        "location": sections.get("location"),
        "salary": _parse_salary(sections.get("salary")),
        "experience": sections.get("experience"),
        "education": sections.get("education"),
        "date": sections.get("date"),
        "url": url.strip(),
        "source": "zhaopin_manual",
        "description": sections.get("description"),
        "raw_text": text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize pasted job text locally")
    parser.add_argument("--url", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--text-file", type=Path)
    args = parser.parse_args()

    text = args.text if args.text is not None else args.text_file.read_text(encoding="utf-8")
    result = normalize_manual_job(args.url, text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
