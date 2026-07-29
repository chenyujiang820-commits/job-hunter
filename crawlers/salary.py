"""Shared Chinese job salary parsing."""

from __future__ import annotations

import re
from typing import Any


def parse_salary(text: str | None) -> dict[str, Any] | None:
    if not text or not text.strip():
        return None

    text = text.strip().replace(",", "").replace("，", "").replace("·", " ")
    negotiable = any(term in text for term in ("面议", "面谈", "可议"))
    months_per_year = 13 if re.search(r"13\s*薪", text) else None
    unit = "month"

    if negotiable and not re.search(r"\d", text):
        return {
            "raw": text,
            "min": None,
            "max": None,
            "unit": unit,
            "months_per_year": months_per_year,
            "negotiable": True,
        }

    range_match = re.search(
        r"(?P<min>[\d.]+)\s*(?P<min_unit>万|千|K|k)?\s*"
        r"[-–~至到]\s*"
        r"(?P<max>[\d.]+)\s*(?P<max_unit>万|千|K|k)?"
        r"(?:\s*/\s*(?:年|year))?",
        text,
    )
    if range_match:
        v_min = float(range_match.group("min"))
        v_max = float(range_match.group("max"))
        min_u = (range_match.group("min_unit") or "").lower()
        max_u = (range_match.group("max_unit") or "").lower()
        multiplier_map = {"k": 1000, "千": 1000, "万": 10000}
        min_mult = multiplier_map.get(min_u) or multiplier_map.get(max_u, 1)
        max_mult = multiplier_map.get(max_u) or multiplier_map.get(min_u, 1)
        if "/年" in text or "/year" in text.lower():
            unit = "year"
        return {
            "raw": text,
            "min": int(v_min * min_mult),
            "max": int(v_max * max_mult),
            "unit": unit,
            "months_per_year": months_per_year,
            "negotiable": negotiable,
        }

    single_match = re.search(
        r"(?P<single>[\d.]+)\s*(?P<unit>万|千|K|k)", text
    )
    if single_match:
        value = float(single_match.group("single"))
        unit_name = single_match.group("unit").lower()
        multiplier = {"k": 1000, "千": 1000, "万": 10000}.get(unit_name, 1)
        return {
            "raw": text,
            "min": int(value * multiplier),
            "max": int(value * multiplier),
            "unit": "month",
            "months_per_year": months_per_year,
            "negotiable": negotiable,
        }

    return {
        "raw": text,
        "min": None,
        "max": None,
        "unit": "month",
        "months_per_year": months_per_year,
        "negotiable": negotiable,
    }
