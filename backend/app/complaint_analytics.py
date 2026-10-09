"""Real-time complaint analytics computed from 客诉跟进表 detail rows."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from typing import Any

import pandas as pd

from .entry import drop_junk_rows, repair_legacy_month_values, repair_missing_row_ids


def _month_sort_key(label: str) -> int:
    s = str(label or "").strip()
    m = re.match(r"^(\d{4})年(\d{1,2})月$", s)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    s = s.replace("月", "")
    try:
        return int(s)
    except ValueError:
        return 99


def _is_closed(status: Any) -> bool:
    return str(status or "").strip().lower() == "closed"


def _is_ongoing(status: Any) -> bool:
    s = str(status or "").strip().lower()
    return s in {"on-going", "ongoing"}


def _is_open(status: Any) -> bool:
    return str(status or "").strip().lower() == "open"


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return num / den


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


def _resolve_date_column(df: pd.DataFrame) -> str | None:
    for col in ("投诉日期", "日期", "发生日期", "反馈日期"):
        if col in df.columns:
            return col
    for col in df.columns:
        if "日期" in str(col):
            return col
    return None


def _prepare_detail_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = drop_junk_rows(df.copy())
    out = repair_missing_row_ids(out)
    out, _ = repair_legacy_month_values(out)
    date_col = _resolve_date_column(out)
    if date_col:
        out["__date"] = out[date_col].map(_parse_date)
    return out


def _month_bounds(label: str) -> tuple[date, date] | None:
    s = str(label or "").strip()
    m = re.match(r"^(\d{4})年(\d{1,2})月$", s)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _filter_by_date_range(
    df: pd.DataFrame,
    date_from: date | None,
    date_to: date | None,
) -> pd.DataFrame:
    if df.empty or (date_from is None and date_to is None):
        return df

    if "__date" in df.columns and df["__date"].notna().any():
        dates = df["__date"]
        mask = dates.notna()
        if date_from is not None:
            mask &= dates >= date_from
        if date_to is not None:
            mask &= dates <= date_to
        return df[mask]

    if "月份" not in df.columns:
        return df

    def month_in_range(label: Any) -> bool:
        bounds = _month_bounds(str(label))
        if bounds is None:
            return True
        start, end = bounds
        if date_from is not None and end < date_from:
            return False
        if date_to is not None and start > date_to:
            return False
        return True

    return df[df["月份"].map(month_in_range)]


def _slice_for_analytics(
    df: pd.DataFrame,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    if df is None or df.empty or (date_from is None and date_to is None):
        return df
    prep = _prepare_detail_df(df)
    filtered = _filter_by_date_range(prep, date_from, date_to)
    if filtered.empty:
        return df.iloc[0:0].copy()
    return df.loc[filtered.index].copy()


def compute_monthly_trend(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Monthly closed / on-going / open counts and closure metrics."""
    data = _prepare_detail_df(df)
    if data.empty or "月份" not in data.columns:
        return []

    status_col = "结案状态" if "结案状态" in data.columns else None
    days_col = "结案天数" if "结案天数" in data.columns else None
    months = sorted(data["月份"].dropna().astype(str).unique(), key=_month_sort_key)
    rows: list[dict[str, Any]] = []

    total_closed = total_ongoing = total_open = total_count = 0
    total_days_sum = 0.0
    closed_for_avg = 0

    for month in months:
        sub = data[data["月份"].astype(str) == month]
        closed = int(sub[status_col].map(_is_closed).sum()) if status_col else 0
        ongoing = int(sub[status_col].map(_is_ongoing).sum()) if status_col else 0
        open_count = int(sub[status_col].map(_is_open).sum()) if status_col else 0
        total = int(len(sub))
        rate = _safe_rate(closed, total)

        avg_days = None
        sum_days = None
        if days_col and days_col in sub.columns:
            closed_days = pd.to_numeric(sub.loc[sub[status_col].map(_is_closed), days_col], errors="coerce").dropna()
            if len(closed_days):
                avg_days = float(closed_days.mean())
                sum_days = float(closed_days.sum())
                total_days_sum += sum_days
                closed_for_avg += len(closed_days)

        rows.append(
            {
                "month": month,
                "closed": closed,
                "ongoing": ongoing,
                "open": open_count,
                "total": total,
                "close_rate": rate,
                "avg_close_days": avg_days,
                "sum_close_days": sum_days,
            }
        )
        total_closed += closed
        total_ongoing += ongoing
        total_open += open_count
        total_count += total

    rows.append(
        {
            "month": "合计",
            "closed": total_closed,
            "ongoing": total_ongoing,
            "open": total_open,
            "total": total_count,
            "close_rate": _safe_rate(total_closed, total_count),
            "avg_close_days": (total_days_sum / closed_for_avg) if closed_for_avg else None,
            "sum_close_days": total_days_sum if closed_for_avg else None,
            "is_total": True,
        }
    )
    return rows


def compute_staff_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per 责任跟踪者 (客户担当) complaint closure summary."""
    data = _prepare_detail_df(df)
    staff_col = next((c for c in ("责任跟踪者", "客户担当") if c in data.columns), None)
    status_col = "结案状态" if "结案状态" in data.columns else None
    if data.empty or not staff_col or not status_col:
        return []

    grouped = data.groupby(data[staff_col].astype(str).str.strip(), dropna=False)
    rows: list[dict[str, Any]] = []
    grand_total = grand_closed = 0

    for name, sub in grouped:
        label = str(name or "").strip()
        if not label or label.lower() in {"nan", "none"}:
            continue
        total = int(len(sub))
        closed = int(sub[status_col].map(_is_closed).sum())
        rate = _safe_rate(closed, total)
        rows.append({"staff": label, "total": total, "closed": closed, "close_rate": rate})
        grand_total += total
        grand_closed += closed

    rows.sort(key=lambda r: (-r["total"], r["staff"]))
    rows.append(
        {
            "staff": "合计",
            "total": grand_total,
            "closed": grand_closed,
            "close_rate": _safe_rate(grand_closed, grand_total),
            "is_total": True,
        }
    )
    return rows


def compute_monthly_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Monthly 客诉总件数 / 结案件数 / 累计结案率 (for bottom summary table)."""
    trend = compute_monthly_trend(df)
    rows = []
    for item in trend:
        rows.append(
            {
                "month": item["month"],
                "total": item["total"],
                "closed": item["closed"],
                "close_rate": item["close_rate"],
                "is_total": item.get("is_total", False),
            }
        )
    return rows


def compute_series_counts(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Count complaints per 系列."""
    data = _prepare_detail_df(df)
    if data.empty or "系列" not in data.columns:
        return []

    counts = (
        data["系列"]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": ""})
    )
    counts = counts[counts != ""]
    if counts.empty:
        return []

    grouped = counts.value_counts()
    rows = [{"series": name, "count": int(n)} for name, n in grouped.items()]
    rows.sort(key=lambda r: (-r["count"], r["series"]))
    return rows


def build_complaint_analytics(
    item: dict[str, Any],
    sheet_name: str | None = None,
    *,
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
    parsed_from = _parse_date(date_from) if date_from else None
    parsed_to = _parse_date(date_to) if date_to else None
    if parsed_from and parsed_to and parsed_from > parsed_to:
        parsed_from, parsed_to = parsed_to, parsed_from

    meta = {
        "date_from": parsed_from.isoformat() if parsed_from else None,
        "date_to": parsed_to.isoformat() if parsed_to else None,
    }

    if df is None:
        return {
            "sheet": target,
            "monthly_trend": [],
            "staff_summary": [],
            "monthly_summary": [],
            "series_counts": [],
            **meta,
        }

    scoped = _slice_for_analytics(df, date_from=parsed_from, date_to=parsed_to)

    return {
        "sheet": resolved,
        "monthly_trend": compute_monthly_trend(scoped),
        "staff_summary": compute_staff_summary(scoped),
        "monthly_summary": compute_monthly_summary(scoped),
        "series_counts": compute_series_counts(scoped),
        **meta,
    }
