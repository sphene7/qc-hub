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
    if s == "NG" or s.startswith("[NG]"):
        return True
    # NG×N — same-batch multiple defect kinds
    return s.startswith("NG×") or s.startswith("NGX") or s.startswith("NG*")


def _normalize_verdict_bucket(val: Any) -> str:
    """判定归桶：OK / OK1(免检) / OK2(特采) / NG。"""
    s = str(val or "").strip().upper()
    if not s:
        return "OK"
    if s.startswith("NG") or s.startswith("[NG]"):
        return "NG"
    if s.startswith("OK1"):
        return "OK1"
    if s.startswith("OK2"):
        return "OK2"
    if s.startswith("OK"):
        return "OK"
    return "OK"


def _has_close_date(val: Any) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return True
    s = str(val).strip()
    return bool(s) and s.lower() not in {"nan", "none", "nat", "null", "-"}


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


def _sampling_unclosed_mask(data: pd.DataFrame, judge_col: str | None) -> pd.Series:
    """抽检未结案：优先「是否结案」；否则 NG 且无结案日期（对齐三级异常登记）。"""
    if data.empty:
        return pd.Series(dtype=bool)
    if "是否结案" in data.columns:
        return data["是否结案"].map(_is_open_close_status)
    if not judge_col:
        return pd.Series(False, index=data.index)
    ng = data[judge_col].map(_is_ng)
    if "结案日期" in data.columns:
        return ng & ~data["结案日期"].map(_has_close_date)
    return ng


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
        unclosed = int(_sampling_unclosed_mask(sub, judge_col).sum())
        closed_exc = max(0, ng - unclosed)
        rows.append(
            {
                "month": month,
                "abnormal": ng,
                "completed": ok,
                "total": total,
                "closed": closed_exc,
                # 抽检趋势线：用 OK 率（含 OK1/OK2）；另带回未结案 NG 供前端区分
                "close_rate": _safe_rate(ok, total),
                "unclosed_ng": unclosed,
                "metric": "ok_rate",
            }
        )
    return rows


def _sampling_open_items(df: pd.DataFrame, *, sort: str) -> list[dict[str, Any]]:
    data = _prepare_oqc_df(df)
    if data.empty:
        return []
    judge_col = _resolve_judge_col(data)
    mask = _sampling_unclosed_mask(data, judge_col)
    open_df = data.loc[mask].copy()
    if open_df.empty:
        return []

    items: list[dict[str, Any]] = []
    for idx, row in open_df.iterrows():
        judge = str(row.get(judge_col) or "—").strip() if judge_col else "—"
        model = str(row.get("机种") or row.get("部番") or row.get("系列") or "—").strip() or "—"
        phen = str(row.get("现象") or "").strip()
        title = f"{model} · {phen}" if phen else model
        unit = str(row.get("责任单位") or row.get("送检单位") or "—").strip() or "—"
        inspector = str(row.get("检验员") or "").strip()
        status = "异常未结案" if judge.upper().startswith("NG") else str(row.get("是否结案") or judge).strip()
        if inspector:
            status = f"{status} · {inspector}"
        sid = str(row.get("送检单号") or row.get("抽检单号") or "").strip()
        if not sid or sid.lower() in {"nan", "none", "nat", "null"}:
            sid = _row_id(row, idx)
        items.append(
            {
                "id": sid,
                "date": _fmt_date(row.get("日期")),
                "title": title,
                "status": status,
                "unit": unit,
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
    buckets = {"OK": 0, "OK1": 0, "OK2": 0, "NG": 0}
    if judge_col and not data.empty:
        for raw in data[judge_col].tolist():
            buckets[_normalize_verdict_bucket(raw)] += 1
    else:
        buckets["OK"] = total
    ng = buckets["NG"]
    ok_all = buckets["OK"] + buckets["OK1"] + buckets["OK2"]
    ng_rate = _safe_rate(ng, total)
    unclosed = int(_sampling_unclosed_mask(data, judge_col).sum()) if not data.empty else 0
    close_rate = _safe_rate(max(0, ng - unclosed), ng) if ng else None

    pie = [
        {"name": "正常 OK", "value": buckets["OK"]},
        {"name": "免检 OK1", "value": buckets["OK1"]},
        {"name": "特采 OK2", "value": buckets["OK2"]},
        {"name": "不良 NG", "value": ng},
    ]
    pie = [p for p in pie if p["value"] > 0] or [{"name": "暂无数据", "value": 0}]

    return {
        "total": total,
        "closed": ok_all,
        "open": unclosed if unclosed else ng,
        "close_rate": close_rate,
        "ng_rate": ng_rate,
        "pie": pie,
        "pie_metric": "ng_rate",
        "pie_center": f"{(ng_rate or 0) * 100:.1f}%" if total else "—",
        "list_label": "NG 未结案清单",
        "trend_labels": {"abnormal": "NG件数", "completed": "OK件数", "rate": "OK率"},
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
            "list_label": "NG 未结案清单" if module_key == "sampling" else "未结案清单",
            "trend_labels": (
                {"abnormal": "NG件数", "completed": "OK件数", "rate": "OK率"}
                if module_key == "sampling"
                else {"abnormal": "异常件数", "completed": "完成件数", "rate": "结案率"}
            ),
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
