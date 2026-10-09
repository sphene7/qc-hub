"""Cross-module abnormal / unclosed monitoring dashboard."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from .complaint_analytics import (
    _is_closed as _complaint_closed,
    _is_ongoing,
    _is_open as _complaint_open,
    _month_sort_key,
    _parse_date,
    _prepare_detail_df as _prepare_complaint_df,
    compute_monthly_trend as _complaint_monthly_trend,
)
from .entry import _is_closed_close_status, _is_open_close_status
from .inspection_analytics import (
    _count_closed,
    _is_closed as _inspection_closed,
    _prepare_detail_df as _prepare_inspection_df,
)
from .oqc_analytics import _prepare_oqc_df

MODULE_LABELS = {
    "inspection": "KK",
    "complaint": "客诉",
    "sampling": "抽检",
}

PIE_METRIC_LABELS = {
    "inspection": "结案率",
    "complaint": "结案率",
    "sampling": "NG率",
}


def _resolve_main_df(item: dict[str, Any], sheet_name: str | None = None) -> tuple[str, pd.DataFrame | None]:
    spec = item["spec"]
    raw = sheet_name or (spec.get("dashboard_design") or {}).get("main_table", {}).get("sheet")
    target = (raw or "").strip()
    for name, frame in item["frames"].items():
        if name == raw or name.strip() == target:
            return name, frame
    return target, None


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return num / den


def _fmt_date(val: Any) -> str | None:
    d = _parse_date(val)
    return d.isoformat() if d else None


def _row_id(row: pd.Series, fallback: int) -> str:
    for key in ("序号", "NO.", "编号"):
        if key in row.index:
            v = row.get(key)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                return str(v).strip()
    return str(fallback)


def _is_ng(val: Any) -> bool:
    s = str(val or "").strip().upper()
    return s == "NG" or s.startswith("[NG]")


def _resolve_judge_col(df: pd.DataFrame) -> str | None:
    """NG 判定优先读「判定」列，其次「判定_2」。"""
    if "判定" in df.columns:
        return "判定"
    if "判定_2" in df.columns:
        return "判定_2"
    return None


def _inspection_monthly_trend(df: pd.DataFrame) -> list[dict[str, Any]]:
    data = _prepare_inspection_df(df)
    if data.empty or "月份" not in data.columns:
        return []
    months = sorted(data["月份"].dropna().astype(str).str.strip().unique().tolist(), key=_month_sort_key)
    rows: list[dict[str, Any]] = []
    for month in months:
        sub = data[data["月份"].astype(str).str.strip() == month]
        total = int(len(sub))
        closed = _count_closed(sub)
        open_count = total - closed
        rows.append(
            {
                "month": month,
                "abnormal": open_count,
                "completed": closed,
                "total": total,
                "closed": closed,
                "close_rate": _safe_rate(closed, total),
            }
        )
    return rows


def _inspection_open_items(df: pd.DataFrame, *, sort: str) -> list[dict[str, Any]]:
    data = _prepare_inspection_df(df)
    if data.empty or "是否结案" not in data.columns:
        return []
    mask = ~data["是否结案"].map(_inspection_closed)
    open_df = data.loc[mask].copy()
    if open_df.empty:
        return []

    items: list[dict[str, Any]] = []
    for idx, row in open_df.iterrows():
        items.append(
            {
                "id": _row_id(row, idx),
                "date": _fmt_date(row.get("日期")),
                "title": str(row.get("问题点描述") or row.get("类别") or "—").strip() or "—",
                "status": str(row.get("是否结案") or "未结案").strip(),
                "unit": str(row.get("责任单位") or "—").strip(),
                "extra": str(row.get("模块") or "—").strip(),
            }
        )
    reverse = sort != "asc"
    items.sort(key=lambda x: (x["date"] or "", x["id"]), reverse=reverse)
    return items


def _inspection_summary(df: pd.DataFrame) -> dict[str, Any]:
    data = _prepare_inspection_df(df)
    total = int(len(data))
    closed = _count_closed(data) if not data.empty else 0
    open_count = total - closed
    close_rate = _safe_rate(closed, total)
    return {
        "total": total,
        "closed": closed,
        "open": open_count,
        "close_rate": close_rate,
        "ng_rate": None,
        "pie": [
            {"name": "已结案", "value": closed},
            {"name": "未结案", "value": open_count},
        ],
        "pie_metric": "close_rate",
        "pie_center": f"{(close_rate or 0) * 100:.1f}%" if total else "—",
    }


def _complaint_open_items(df: pd.DataFrame, *, sort: str) -> list[dict[str, Any]]:
    data = _prepare_complaint_df(df)
    status_col = "结案状态" if "结案状态" in data.columns else None
    if data.empty or not status_col:
        return []
    mask = ~data[status_col].map(_complaint_closed)
    open_df = data.loc[mask].copy()
    if open_df.empty:
        return []

    date_col = next((c for c in ("投诉日期", "日期", "发生日期") if c in open_df.columns), None)
    items: list[dict[str, Any]] = []
    for idx, row in open_df.iterrows():
        status = str(row.get(status_col) or "—").strip()
        items.append(
            {
                "id": _row_id(row, idx),
                "date": _fmt_date(row.get(date_col)) if date_col else None,
                "title": str(row.get("投诉内容") or row.get("系列") or "—").strip() or "—",
                "status": status,
                "unit": str(row.get("责任跟踪者") or row.get("客户担当") or "—").strip(),
                "extra": str(row.get("系列") or "—").strip(),
            }
        )
    reverse = sort != "asc"
    items.sort(key=lambda x: (x["date"] or "", x["id"]), reverse=reverse)
    return items


def _complaint_summary(df: pd.DataFrame) -> dict[str, Any]:
    trend = _complaint_monthly_trend(df)
    total_row = next((r for r in trend if r.get("is_total")), None)
    if total_row:
        total = int(total_row["total"])
        closed = int(total_row["closed"])
        ongoing = int(total_row.get("ongoing") or 0)
        open_count = int(total_row.get("open") or 0)
    else:
        data = _prepare_complaint_df(df)
        status_col = "结案状态" if "结案状态" in data.columns else None
        total = int(len(data))
        closed = int(data[status_col].map(_complaint_closed).sum()) if status_col else 0
        ongoing = int(data[status_col].map(_is_ongoing).sum()) if status_col else 0
        open_count = int(data[status_col].map(_complaint_open).sum()) if status_col else 0
    unclosed = ongoing + open_count
    close_rate = _safe_rate(closed, total)
    return {
        "total": total,
        "closed": closed,
        "open": unclosed,
        "close_rate": close_rate,
        "ng_rate": None,
        "pie": [
            {"name": "已结案", "value": closed},
            {"name": "跟进中", "value": ongoing},
            {"name": "未结案", "value": open_count},
        ],
        "pie_metric": "close_rate",
        "pie_center": f"{(close_rate or 0) * 100:.1f}%" if total else "—",
    }


def _complaint_monthly(df: pd.DataFrame) -> list[dict[str, Any]]:
    trend = _complaint_monthly_trend(df)
    rows: list[dict[str, Any]] = []
    for item in trend:
        if item.get("is_total"):
            continue
        abnormal = int(item.get("ongoing") or 0) + int(item.get("open") or 0)
        rows.append(
            {
                "month": item["month"],
                "abnormal": abnormal,
                "completed": item["closed"],
                "total": item["total"],
                "closed": item["closed"],
                "close_rate": item.get("close_rate"),
            }
        )
    return rows


def _sampling_monthly_trend(df: pd.DataFrame) -> list[dict[str, Any]]:
    data = _prepare_oqc_df(df)
    if data.empty:
        return []
    judge_col = _resolve_judge_col(data)
    month_col = "月份" if "月份" in data.columns else None
    if not month_col:
        return []

    months = sorted(data[month_col].dropna().astype(str).str.strip().unique().tolist(), key=_month_sort_key)
    rows: list[dict[str, Any]] = []
    for month in months:
        sub = data[data[month_col].astype(str).str.strip() == month]
        total = int(len(sub))
        ng = int(sub[judge_col].map(_is_ng).sum()) if judge_col else 0
        ok = total - ng
        closed = 0
        if "是否结案" in sub.columns:
            closed = int(sub["是否结案"].map(_is_closed_close_status).sum())
        rows.append(
            {
                "month": month,
                "abnormal": ng,
                "completed": ok,
                "total": total,
                "closed": closed,
                "close_rate": _safe_rate(closed, total) if "是否结案" in sub.columns else _safe_rate(ok, total),
            }
        )
    return rows


def _sampling_open_items(df: pd.DataFrame, *, sort: str) -> list[dict[str, Any]]:
    data = _prepare_oqc_df(df)
    if data.empty:
        return []
    judge_col = _resolve_judge_col(data)
    if "是否结案" in data.columns:
        mask = data["是否结案"].map(_is_open_close_status)
    elif judge_col:
        mask = data[judge_col].map(_is_ng)
    else:
        return []

    open_df = data.loc[mask].copy()
    if open_df.empty:
        return []

    items: list[dict[str, Any]] = []
    for idx, row in open_df.iterrows():
        judge = str(row.get(judge_col) or "—").strip() if judge_col else "—"
        items.append(
            {
                "id": _row_id(row, idx),
                "date": _fmt_date(row.get("日期")),
                "title": str(row.get("系列") or row.get("机种") or "—").strip() or "—",
                "status": str(row.get("是否结案") or judge).strip(),
                "unit": str(row.get("送检单位") or "—").strip(),
                "extra": judge,
            }
        )
    reverse = sort != "asc"
    items.sort(key=lambda x: (x["date"] or "", x["id"]), reverse=reverse)
    return items


def _sampling_summary(df: pd.DataFrame) -> dict[str, Any]:
    data = _prepare_oqc_df(df)
    total = int(len(data))
    judge_col = _resolve_judge_col(data)
    ng = int(data[judge_col].map(_is_ng).sum()) if judge_col and not data.empty else 0
    ok = total - ng
    ng_rate = _safe_rate(ng, total)
    open_count = 0
    close_rate = None
    if "是否结案" in data.columns and not data.empty:
        open_count = int(data["是否结案"].map(_is_open_close_status).sum())
        closed = int(data["是否结案"].map(_is_closed_close_status).sum())
        close_rate = _safe_rate(closed, total)

    return {
        "total": total,
        "closed": ok,
        "open": ng,
        "close_rate": close_rate,
        "ng_rate": ng_rate,
        "pie": [
            {"name": "OK", "value": ok},
            {"name": "NG", "value": ng},
        ],
        "pie_metric": "ng_rate",
        "pie_center": f"{(ng_rate or 0) * 100:.1f}%" if total else "—",
    }


def build_module_monitor(
    module_key: str,
    item: dict[str, Any],
    *,
    sheet_name: str | None = None,
    sort: str = "desc",
) -> dict[str, Any]:
    label = MODULE_LABELS.get(module_key, module_key)
    metric_label = PIE_METRIC_LABELS.get(module_key, "结案率")
    resolved, df = _resolve_main_df(item, sheet_name)
    empty = {
        "module": module_key,
        "label": label,
        "metric_label": metric_label,
        "sheet": resolved,
        "summary": {
            "total": 0,
            "closed": 0,
            "open": 0,
            "close_rate": None,
            "ng_rate": None,
            "pie": [],
            "pie_metric": "close_rate",
            "pie_center": "—",
        },
        "monthly_trend": [],
        "open_items": [],
    }
    if df is None or df.empty:
        return empty

    if module_key == "inspection":
        summary = _inspection_summary(df)
        monthly = _inspection_monthly_trend(df)
        open_items = _inspection_open_items(df, sort=sort)
    elif module_key == "complaint":
        summary = _complaint_summary(df)
        monthly = _complaint_monthly(df)
        open_items = _complaint_open_items(df, sort=sort)
    elif module_key == "sampling":
        summary = _sampling_summary(df)
        monthly = _sampling_monthly_trend(df)
        open_items = _sampling_open_items(df, sort=sort)
    else:
        return empty

    return {
        "module": module_key,
        "label": label,
        "metric_label": metric_label,
        "sheet": resolved,
        "summary": summary,
        "monthly_trend": monthly,
        "open_items": open_items,
    }
