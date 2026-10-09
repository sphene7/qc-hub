"""Real-time inspection analytics computed from 问题清单 detail rows."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd

from .entry import drop_junk_rows, repair_legacy_month_values, repair_missing_row_ids

FIVE_M_COLUMNS = [
    ("人-张程亮", "人"),
    ("机-陈刚", "机"),
    ("料-王岩良", "料"),
    ("法（QCP/SOP）", "法"),
    ("环境-刘焕良", "环"),
]

DEFAULT_UNITS = ["组立", "技术", "品质", "运营", "自动化"]


def _month_sort_key(label: str) -> int:
    s = str(label or "").strip()
    m = re.match(r"^(\d{4})年(\d{1,2})月$", s)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    m = re.match(r"^(\d{1,2})月$", s)
    if m:
        return int(m.group(1))
    try:
        return int(s.replace("月", ""))
    except ValueError:
        return 99


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return num / den


def _is_closed(status: Any) -> bool:
    s = str(status or "").strip().lower()
    return s in {"close", "closed", "已结案"}


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


def _prepare_detail_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = drop_junk_rows(df.copy())
    out = repair_missing_row_ids(out)
    out, _ = repair_legacy_month_values(out)
    if "日期" in out.columns:
        out["__date"] = out["日期"].map(_parse_date)
    return out


def _filter_by_date(df: pd.DataFrame, target: date | None) -> pd.DataFrame:
    if target is None or df.empty or "__date" not in df.columns:
        return df
    return df[df["__date"] == target]


def _filter_by_date_range(
    df: pd.DataFrame,
    date_from: date | None,
    date_to: date | None,
) -> pd.DataFrame:
    if df.empty or (date_from is None and date_to is None):
        return df
    if "__date" not in df.columns:
        return df
    dates = df["__date"]
    mask = dates.notna()
    if date_from is not None:
        mask &= dates >= date_from
    if date_to is not None:
        mask &= dates <= date_to
    return df[mask]


def _slice_for_analytics(
    df: pd.DataFrame,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Filter raw detail rows by inclusive date range."""
    if df is None or df.empty or (date_from is None and date_to is None):
        return df
    prep = _prepare_detail_df(df)
    filtered = _filter_by_date_range(prep, date_from, date_to)
    if filtered.empty:
        return df.iloc[0:0].copy()
    return df.loc[filtered.index].copy()


def _default_focus_date(data: pd.DataFrame) -> date | None:
    """Pick the busiest inspection day (ties → latest date)."""
    if data.empty or "__date" not in data.columns:
        return None
    valid = data["__date"].map(lambda x: x if isinstance(x, date) else None).dropna()
    if valid.empty:
        return None
    counts = valid.value_counts()
    top_count = counts.iloc[0]
    candidates = counts[counts == top_count].index.tolist()
    return max(candidates)


def _count_closed(sub: pd.DataFrame) -> int:
    if sub.empty or "是否结案" not in sub.columns:
        return 0
    return int(sub["是否结案"].map(_is_closed).sum())


def _active_five_m_columns(df: pd.DataFrame) -> list[tuple[str, str]]:
    return [(col, label) for col, label in FIVE_M_COLUMNS if col in df.columns]


def _five_m_count(sub: pd.DataFrame, col: str) -> int:
    if sub.empty or col not in sub.columns:
        return 0
    series = pd.to_numeric(sub[col], errors="coerce").fillna(0)
    return int((series > 0).sum())


def compute_unit_summary(df: pd.DataFrame, *, focus_date: date | None = None) -> dict[str, Any]:
    """Per 责任单位 summary with monthly columns, optional day snapshot, and TTL."""
    data = _prepare_detail_df(df)
    if data.empty or "责任单位" not in data.columns:
        return {"months": [], "focus_date": None, "rows": []}

    months = sorted(
        data["月份"].dropna().astype(str).str.strip().unique().tolist(),
        key=_month_sort_key,
    )
    units = [u for u in DEFAULT_UNITS if u in set(data["责任单位"].astype(str))]
    extra = sorted(
        {
            str(v).strip()
            for v in data["责任单位"].dropna().unique()
            if str(v).strip() and str(v).strip() not in units
        }
    )
    units.extend(extra)

    if focus_date is None:
        focus_date = _default_focus_date(data)

    rows: list[dict[str, Any]] = []
    for unit in units:
        unit_df = data[data["责任单位"].astype(str).str.strip() == unit]
        if unit_df.empty:
            continue

        month_metrics: dict[str, dict[str, Any]] = {}
        for month in months:
            sub = unit_df[unit_df["月份"].astype(str).str.strip() == month]
            total = int(len(sub))
            closed = _count_closed(sub)
            month_metrics[month] = {
                "total": total,
                "closed": closed,
                "close_rate": _safe_rate(closed, total),
            }

        day_metrics = {"total": 0, "closed": 0, "close_rate": None}
        if focus_date is not None:
            sub_day = unit_df[unit_df["__date"] == focus_date]
            total = int(len(sub_day))
            closed = _count_closed(sub_day)
            day_metrics = {
                "total": total,
                "closed": closed,
                "close_rate": _safe_rate(closed, total),
            }

        total_all = int(len(unit_df))
        closed_all = _count_closed(unit_df)
        rows.append(
            {
                "unit": unit,
                "months": month_metrics,
                "day": day_metrics,
                "ttl": {
                    "total": total_all,
                    "closed": closed_all,
                    "close_rate": _safe_rate(closed_all, total_all),
                },
            }
        )

    return {
        "months": months,
        "focus_date": focus_date.isoformat() if focus_date else None,
        "rows": rows,
    }


def compute_five_m_summary(df: pd.DataFrame, *, focus_date: date | None = None) -> dict[str, Any]:
    """5M distribution and drill-down issue descriptions for a given day (or all)."""
    data = _prepare_detail_df(df)
    cols = _active_five_m_columns(data)
    if data.empty or not cols:
        return {"focus_date": None, "items": [], "details": {}}

    if focus_date is None:
        focus_date = _default_focus_date(data)
    scoped = _filter_by_date(data, focus_date)

    total = int(len(scoped))
    items: list[dict[str, Any]] = []
    details: dict[str, list[dict[str, Any]]] = {}

    for col, label in cols:
        count = _five_m_count(scoped, col)
        rate = _safe_rate(count, total) if total else None
        items.append(
            {
                "key": col,
                "label": label,
                "full_label": col,
                "count": count,
                "share": rate,
            }
        )

        if "问题点描述" in scoped.columns:
            sub = scoped[pd.to_numeric(scoped[col], errors="coerce").fillna(0) > 0]
            if not sub.empty:
                grouped = (
                    sub["问题点描述"]
                    .astype(str)
                    .str.strip()
                    .replace({"nan": "", "None": ""})
                )
                grouped = grouped[grouped != ""]
                if not grouped.empty:
                    counts = grouped.value_counts().head(12)
                    details[col] = [
                        {"description": name, "count": int(n)} for name, n in counts.items()
                    ]

    items.sort(key=lambda x: (-x["count"], x["label"]))
    return {
        "focus_date": focus_date.isoformat() if focus_date else None,
        "total": total,
        "items": items,
        "details": details,
    }


def compute_category_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per 类别 issue count, share, closed count, close rate."""
    data = _prepare_detail_df(df)
    if data.empty or "类别" not in data.columns:
        return []

    labels = (
        data["类别"]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": ""})
    )
    valid = data[labels != ""].copy()
    if valid.empty:
        return []

    grand_total = int(len(valid))
    grouped = valid.groupby(valid["类别"].astype(str).str.strip(), dropna=False)
    rows: list[dict[str, Any]] = []
    grand_closed = 0

    for name, sub in grouped:
        label = str(name or "").strip()
        if not label:
            continue
        total = int(len(sub))
        closed = _count_closed(sub)
        rows.append(
            {
                "category": label,
                "total": total,
                "share": _safe_rate(total, grand_total),
                "closed": closed,
                "close_rate": _safe_rate(closed, total),
            }
        )
        grand_closed += closed

    rows.sort(key=lambda r: (-r["total"], r["category"]))
    rows.append(
        {
            "category": "Total",
            "total": grand_total,
            "share": 1.0 if grand_total else None,
            "closed": grand_closed,
            "close_rate": _safe_rate(grand_closed, grand_total),
            "is_total": True,
        }
    )
    return rows


def compute_module_owner_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per 模块 + 工段负责人 closure summary."""
    data = _prepare_detail_df(df)
    if data.empty or "模块" not in data.columns:
        return []

    owner_col = "工段负责人" if "工段负责人" in data.columns else None
    rows_map: dict[str, dict[str, Any]] = {}

    for _, row in data.iterrows():
        module = str(row.get("模块") or "").strip()
        if not module or module.lower() in {"nan", "none"}:
            continue
        owner = str(row.get(owner_col) or "").strip() if owner_col else ""
        key = f"{module}::{owner}" if owner else module
        if key not in rows_map:
            rows_map[key] = {
                "module": module,
                "owner": owner or "—",
                "total": 0,
                "closed": 0,
            }
        rows_map[key]["total"] += 1
        if _is_closed(row.get("是否结案")):
            rows_map[key]["closed"] += 1

    rows = []
    grand_total = grand_closed = 0
    for item in rows_map.values():
        total = item["total"]
        closed = item["closed"]
        rows.append(
            {
                "module": item["module"],
                "owner": item["owner"],
                "label": f"{item['module']} / {item['owner']}" if item["owner"] != "—" else item["module"],
                "total": total,
                "closed": closed,
                "close_rate": _safe_rate(closed, total),
            }
        )
        grand_total += total
        grand_closed += closed

    rows.sort(key=lambda r: (-r["total"], r["module"], r["owner"]))
    rows.append(
        {
            "module": "Total",
            "owner": "",
            "label": "Total",
            "total": grand_total,
            "closed": grand_closed,
            "close_rate": _safe_rate(grand_closed, grand_total),
            "is_total": True,
        }
    )
    return rows


def build_inspection_analytics(
    item: dict[str, Any],
    sheet_name: str | None = None,
    *,
    focus_date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    spec = item["spec"]
    raw = sheet_name or (spec.get("dashboard_design") or {}).get("main_table", {}).get("sheet")
    target = (raw or "").strip()
    df = None
    resolved = target
    for name, frame in item["frames"].items():
        if name == raw or name.strip() == target:
            df = frame
            resolved = name
            break

    parsed_date: date | None = _parse_date(focus_date) if focus_date else None
    parsed_from: date | None = _parse_date(date_from) if date_from else None
    parsed_to: date | None = _parse_date(date_to) if date_to else None
    if parsed_from and parsed_to and parsed_from > parsed_to:
        parsed_from, parsed_to = parsed_to, parsed_from

    empty = {
        "sheet": target,
        "date_from": parsed_from.isoformat() if parsed_from else None,
        "date_to": parsed_to.isoformat() if parsed_to else None,
        "unit_summary": {"months": [], "focus_date": None, "rows": []},
        "five_m_summary": {"focus_date": None, "items": [], "details": {}, "total": 0},
        "category_summary": [],
        "module_owner_summary": [],
    }
    if df is None:
        return empty

    scoped = _slice_for_analytics(df, date_from=parsed_from, date_to=parsed_to)

    unit_summary = compute_unit_summary(scoped, focus_date=parsed_date)
    five_m_summary = compute_five_m_summary(scoped, focus_date=parsed_date)

    return {
        "sheet": resolved,
        "date_from": parsed_from.isoformat() if parsed_from else None,
        "date_to": parsed_to.isoformat() if parsed_to else None,
        "unit_summary": unit_summary,
        "five_m_summary": five_m_summary,
        "category_summary": compute_category_summary(scoped),
        "module_owner_summary": compute_module_owner_summary(scoped),
    }
