"""OQC 变焦抽检：按送检单位 × 日的批次合格率推移（对齐 Excel 首页推移图）。"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from typing import Any

import pandas as pd

from .entry import drop_junk_rows, repair_legacy_month_values

SECTION_ORDER = ["变焦一课", "变焦二课", "变焦三课", "试做课", "试验课", "红外", "消费三课"]

SENT_FIELD = "抽检批"
PASS_FIELD = "合格批"
UNIT_FIELD = "送检单位"
DATE_FIELD = "日期"
MONTH_FIELD = "月份"


def _parse_date(val: Any) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, pd.Timestamp):
        return val.date()
    s = str(val).strip()
    if not s:
        return None
    try:
        return pd.to_datetime(s).date()
    except (ValueError, TypeError):
        return None


def _parse_month_label(val: Any) -> tuple[int, int] | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})年(\d{1,2})月$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(\d{1,2})月$", s)
    if m:
        return 2026, int(m.group(1))
    return None


def _num(val: Any) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        s = str(val).strip()
        if not s or s in {"-", "—"}:
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return num / den


def _resolve_sheet(item: dict[str, Any], sheet_name: str | None) -> tuple[str, pd.DataFrame | None]:
    spec = item["spec"]
    raw = sheet_name or (spec.get("dashboard_design") or {}).get("main_table", {}).get("sheet")
    target = (raw or "").strip()
    for name, frame in item["frames"].items():
        if name == raw or name.strip() == target:
            return name, frame
    return target, None


def _prepare_oqc_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = drop_junk_rows(df.copy(), id_key="序号")
    if out.empty:
        out = drop_junk_rows(df.copy(), id_key="NO.")
    out, _ = repair_legacy_month_values(out)
    if DATE_FIELD in out.columns:
        out["__date"] = out[DATE_FIELD].map(_parse_date)
    if MONTH_FIELD in out.columns:
        out["__ym"] = out[MONTH_FIELD].map(_parse_month_label)
    return out


def _infer_default_month(df: pd.DataFrame, title: str = "") -> tuple[int, int]:
    m = re.search(r"(\d{4})年(\d{1,2})月", title or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    if not df.empty and "__date" in df.columns:
        dates = [d for d in df["__date"] if d is not None]
        if dates:
            latest = max(dates)
            return latest.year, latest.month
    if not df.empty and "__ym" in df.columns:
        pairs = [p for p in df["__ym"] if p]
        if pairs:
            y, mo = max(pairs)
            return y, mo
    today = date.today()
    return today.year, today.month


def _filter_month(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    if df.empty:
        return df
    mask = pd.Series([False] * len(df), index=df.index)
    if "__date" in df.columns:
        mask = mask | df["__date"].map(
            lambda d: d is not None and d.year == year and d.month == month
        )
    if "__ym" in df.columns:
        mask = mask | df["__ym"].map(lambda p: p == (year, month))
    if not mask.any() and "__date" in df.columns:
        mask = df["__date"].notna()
    out = df.loc[mask].copy()
    if "送检类型" in out.columns:
        types = out["送检类型"].astype(str).str.strip()
        normal = types == "正常送检"
        if normal.any():
            out = out.loc[normal].copy()
    return out


def _section_sort_key(name: str) -> tuple[int, str]:
    n = (name or "").strip()
    if n in SECTION_ORDER:
        return SECTION_ORDER.index(n), n
    return len(SECTION_ORDER) + 1, n


def _day_bucket(day: int) -> dict[str, Any]:
    return {"day": day, "sent": 0.0, "passed": 0.0, "rate": None}


def _build_section_rows(
    df: pd.DataFrame, *, year: int, month: int, days_in_month: int
) -> list[dict[str, Any]]:
    if df.empty or UNIT_FIELD not in df.columns:
        return []

    units = sorted(
        {str(u).strip() for u in df[UNIT_FIELD].dropna() if str(u).strip()},
        key=_section_sort_key,
    )
    sections: list[dict[str, Any]] = []

    for unit in units:
        sub = df[df[UNIT_FIELD].astype(str).str.strip() == unit]
        days = [_day_bucket(d) for d in range(1, days_in_month + 1)]
        for _, row in sub.iterrows():
            d = row.get("__date")
            if d is None or d.year != year or d.month != month:
                continue
            day = d.day
            if day < 1 or day > days_in_month:
                continue
            bucket = days[day - 1]
            bucket["sent"] += _num(row.get(SENT_FIELD))
            bucket["passed"] += _num(row.get(PASS_FIELD))

        ttl_sent = 0.0
        ttl_passed = 0.0
        for bucket in days:
            bucket["sent"] = round(bucket["sent"], 4)
            bucket["passed"] = round(bucket["passed"], 4)
            bucket["rate"] = _safe_rate(bucket["passed"], bucket["sent"])
            ttl_sent += bucket["sent"]
            ttl_passed += bucket["passed"]

        sections.append(
            {
                "name": unit,
                "days": days,
                "ttl": {
                    "sent": round(ttl_sent, 4),
                    "passed": round(ttl_passed, 4),
                    "rate": _safe_rate(ttl_passed, ttl_sent),
                },
            }
        )
    return sections


def _build_summary(sections: list[dict[str, Any]], days_in_month: int) -> dict[str, Any]:
    days = [_day_bucket(d) for d in range(1, days_in_month + 1)]
    ttl_sent = 0.0
    ttl_passed = 0.0
    for sec in sections:
        for i, bucket in enumerate(sec["days"]):
            days[i]["sent"] += bucket["sent"]
            days[i]["passed"] += bucket["passed"]
        ttl_sent += sec["ttl"]["sent"]
        ttl_passed += sec["ttl"]["passed"]

    for bucket in days:
        bucket["sent"] = round(bucket["sent"], 4)
        bucket["passed"] = round(bucket["passed"], 4)
        bucket["rate"] = _safe_rate(bucket["passed"], bucket["sent"])

    return {
        "name": "汇总",
        "days": days,
        "ttl": {
            "sent": round(ttl_sent, 4),
            "passed": round(ttl_passed, 4),
            "rate": _safe_rate(ttl_passed, ttl_sent),
        },
    }


def build_oqc_analytics(
    item: dict[str, Any],
    sheet_name: str | None = None,
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    resolved, df = _resolve_sheet(item, sheet_name)
    title_base = item.get("spec", {}).get("title") or item.get("spec", {}).get("filename") or ""
    empty = {
        "sheet": resolved,
        "year": year,
        "month": month,
        "title": "",
        "days_in_month": 31,
        "sections": [],
        "summary": {"name": "汇总", "days": [], "ttl": {"sent": 0, "passed": 0, "rate": None}},
    }
    if df is None:
        return empty

    prepared = _prepare_oqc_df(df)
    if year is None or month is None:
        year, month = _infer_default_month(prepared, title_base)

    scoped = _filter_month(prepared, year, month)
    days_in_month = calendar.monthrange(year, month)[1]
    sections = _build_section_rows(scoped, year=year, month=month, days_in_month=days_in_month)
    summary = _build_summary(sections, days_in_month)

    chart_title = f"{month}月变焦产品批次合格率推移图"
    chart_subtitle = "正常送检"
    return {
        "sheet": resolved,
        "year": year,
        "month": month,
        "title": chart_title,
        "subtitle": chart_subtitle,
        "days_in_month": days_in_month,
        "sections": sections,
        "summary": summary,
    }
