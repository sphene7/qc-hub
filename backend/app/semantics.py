"""Turn parsed sheets into a dashboard spec: roles, KPIs, filters, charts, joins."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

from .parser import _excel_serial_to_date

DATE_SORT_FIELDS = frozenset({"日期", "抽检状况", "发生日期", "投诉日期", "反馈日期"})

# OQC 代码表 VLOOKUP：主表字段 → 代码表实际列名
OQC_CODE_JOIN_COLUMNS: dict[tuple[str, str], tuple[str, str]] = {
    ("系列", "送检单位"): ("机种", "课室"),
    ("系列", "确认者"): ("机种_2", "负责人"),
    ("送检单位", "课室负责人"): ("课室_2", "课室负责人"),
    ("不良代码", "现象"): ("代码", "不良描述"),
}
_CN_DATE_RE = re.compile(r"^(\d+)月(\d+)日$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

STATUS_HINTS = ("状态", "判定", "结案", "是否结案", "结果")
DIM_HINTS = (
    "月份", "月度", "机种", "系列", "部门", "课室", "单位", "类型",
    "产线", "模块", "工位", "类别", "分类", "客户", "生产地", "责任",
    "时间段", "送检类型", "不良属性", "问题归类",
)
SKIP_DIM = ("内容", "描述", "原因", "对策", "事项", "备注", "现象", "说明")
ID_HINTS = ("序号", "编号", "单号")
RATE_HINTS = ("率", "占比")
SUM_HINTS = ("数量", "件数", "天数", "抽检数", "不良数", "良品数", "送检")


def build_workbook_spec(parsed: dict[str, Any]) -> dict[str, Any]:
    sheets_out = []
    joins = []
    primary = _pick_primary(parsed["sheets"])
    for sheet in parsed["sheets"]:
        spec = _build_sheet_spec(sheet, is_primary=sheet["name"] == (primary or {}).get("name"))
        sheets_out.append(spec)
        joins.extend(spec.get("joins") or [])

    return {
        "filename": parsed["filename"],
        "title": parsed["title"],
        "primary_sheet": (primary or {}).get("name"),
        "sheets": sheets_out,
        "joins": _unique_joins(joins),
        "smart_view": _build_smart_view(sheets_out, _unique_joins(joins)),  # NEW
    }


def _pick_primary(sheets: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = []
    for s in sheets:
        score = 0
        if s.get("derived"):
            score += 8
        if s["kind"] == "fact":
            score += 20 + min(s["row_count"], 500) / 10
        elif s["kind"] == "table":
            score += 8
        elif s["kind"] == "dashboard":
            score += 3
        if s.get("empty"):
            score -= 15
        if s["kind"] in ("instruction", "hidden", "lookup"):
            score -= 20
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None


def _build_sheet_spec(sheet: dict[str, Any], is_primary: bool) -> dict[str, Any]:
    df: pd.DataFrame = sheet["df"]
    columns = [_with_role(c, df) for c in sheet["columns"]]
    formula_cols = {c["name"]: c for c in (sheet.get("formula") or {}).get("columns") or []}
    for col in columns:
        info = formula_cols.get(col["key"])
        if info:
            col["formula"] = {
                "kind": info["kind"],
                "expr": info.get("expr"),
                "sample": info.get("sample"),
                "depends_on": info.get("depends_on") or [],
                "functions": info.get("functions") or [],
            }
            if info["kind"] in ("calculated", "extract", "lookup") and col["role"] == "text":
                col["role"] = "dimension" if col["unique"] <= 40 else "text"

    joins = []
    for info in formula_cols.values():
        for v in info.get("vlookups") or []:
            joins.append(
                {
                    "from_sheet": sheet["name"],
                    "from_field": v.get("lookup_name") or info["name"],
                    "to_sheet": v.get("table_sheet"),
                    "to_field": f"第{v.get('table_key_col')}列",
                    "result_field": info["name"],
                    "via": "VLOOKUP",
                    "table": v.get("table"),
                }
            )

    kpis = _suggest_kpis(columns, df) if not sheet.get("empty") else []
    filters = _suggest_filters(columns, df) if not sheet.get("empty") else []
    charts = _suggest_charts(columns, df) if not sheet.get("empty") else []

    return {
        "name": sheet["name"],
        "kind": sheet["kind"],
        "row_count": sheet["row_count"],
        "col_count": sheet["col_count"],
        "header_row": sheet["header_row"],
        "empty": sheet["empty"],
        "note": sheet.get("note"),
        "derived": bool(sheet.get("derived")),
        "primary": is_primary,
        "columns": columns,
        "kpis": kpis,
        "filters": filters,
        "charts": charts,
        "joins": joins,
        "formula": {
            "count": (sheet.get("formula") or {}).get("count") or 0,
            "functions": (sheet.get("formula") or {}).get("functions") or [],
            "cross_sheets": (sheet.get("formula") or {}).get("cross_sheets") or [],
            "columns": (sheet.get("formula") or {}).get("columns") or [],
            "samples": (sheet.get("formula") or {}).get("samples") or [],
        },
        "preview": sheet.get("preview") or [],
    }


def _with_role(col: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    name = col["key"]
    n = len(df)
    uniq = col["unique"]
    fill = col["fill"]
    typ = col["type"]
    role = "text"
    if typ == "empty" or fill < 0.02:
        role = "empty"
    elif any(k in name for k in ID_HINTS) and uniq >= max(n * 0.8, 3):
        role = "id"
    elif typ == "date":
        role = "date"
    elif typ in ("number", "percent"):
        if any(k in name for k in ID_HINTS):
            role = "id"
        else:
            role = "measure"
    elif any(k in name for k in SKIP_DIM):
        role = "text"
    elif typ in ("string", "category") or "月份" in name:
        if 1 < uniq <= min(40, max(n * 0.6, 4)) or any(k in name for k in DIM_HINTS) or any(
            k in name for k in STATUS_HINTS
        ):
            role = "dimension"
        else:
            role = "text"
    out = dict(col)
    out["role"] = role
    if any(k in name for k in STATUS_HINTS):
        out["semantic"] = "status"
    elif any(k in name for k in RATE_HINTS):
        out["semantic"] = "rate"
    elif "月份" in name:
        out["semantic"] = "month"
    else:
        out["semantic"] = None
    return out


def _suggest_kpis(columns: list[dict[str, Any]], df: pd.DataFrame) -> list[dict[str, Any]]:
    kpis = [{"id": "rows", "label": "记录数", "agg": "count", "field": None, "format": "int"}]
    status_cols = [c for c in columns if c.get("semantic") == "status" and c["role"] == "dimension"]
    for c in status_cols[:1]:
        vc = df[c["key"]].dropna().astype(str)
        for val, cnt in vc.value_counts().head(4).items():
            kpis.append(
                {
                    "id": f"status_{c['key']}_{val}",
                    "label": f"{c['label']}·{val}",
                    "agg": "count_where",
                    "field": c["key"],
                    "value": str(val),
                    "format": "int",
                }
            )
        # close rate if Closed / Close / Y / OK present
        closed = [v for v in vc.unique() if str(v).lower() in {"closed", "close", "y", "ok", "是", "结案"}]
        if closed:
            kpis.append(
                {
                    "id": f"rate_{c['key']}",
                    "label": f"{c['label']}结案/合格率",
                    "agg": "ratio_where",
                    "field": c["key"],
                    "value": str(closed[0]),
                    "format": "percent",
                }
            )

    measures = [c for c in columns if c["role"] == "measure"]
    for c in measures:
        if c.get("semantic") == "rate" or c["type"] == "percent" or any(k in c["key"] for k in RATE_HINTS):
            kpis.append(
                {
                    "id": f"avg_{c['key']}",
                    "label": f"平均{c['label']}",
                    "agg": "mean",
                    "field": c["key"],
                    "format": "percent" if c["type"] == "percent" or "率" in c["key"] else "number",
                }
            )
        elif any(k in c["key"] for k in SUM_HINTS) or c["type"] == "number":
            # skip likely flags 0/1 with tiny unique
            if c["unique"] <= 3:
                continue
            kpis.append(
                {
                    "id": f"sum_{c['key']}",
                    "label": f"{c['label']}合计",
                    "agg": "sum",
                    "field": c["key"],
                    "format": "number",
                }
            )
        if len(kpis) >= 8:
            break
    return kpis[:8]


def _suggest_filters(columns: list[dict[str, Any]], df: pd.DataFrame) -> list[dict[str, Any]]:
    filters = []
    for c in columns:
        if c["role"] == "date":
            series = pd.to_datetime(df[c["key"]], errors="coerce").dropna()
            filters.append(
                {
                    "field": c["key"],
                    "label": c["label"],
                    "type": "date_range",
                    "min": series.min().date().isoformat() if len(series) else None,
                    "max": series.max().date().isoformat() if len(series) else None,
                }
            )
        elif c["role"] == "dimension" and 1 < c["unique"] <= 40:
            vals = (
                df[c["key"]].dropna().astype(str).value_counts().head(30).index.tolist()
            )
            filters.append(
                {
                    "field": c["key"],
                    "label": c["label"],
                    "type": "enum",
                    "options": vals,
                }
            )
        if len(filters) >= 6:
            break
    return filters


def _suggest_charts(columns: list[dict[str, Any]], df: pd.DataFrame) -> list[dict[str, Any]]:
    charts = []
    dims = [c for c in columns if c["role"] == "dimension"]
    dates = [c for c in columns if c["role"] == "date"]
    measures = [c for c in columns if c["role"] == "measure"]
    status = [c for c in dims if c.get("semantic") == "status"]

    rate_m = next((c for c in measures if c.get("semantic") == "rate" or "率" in c["key"]), None)
    sum_m = next((c for c in measures if any(k in c["key"] for k in SUM_HINTS) and c["unique"] > 3), None)

    if dates:
        d = dates[0]
        charts.append(
            {
                "id": "trend",
                "title": f"按{d['label']}趋势",
                "type": "line",
                "x": d["key"],
                "y": (rate_m or sum_m or {"key": None})["key"] if (rate_m or sum_m) else None,
                "agg": "mean" if rate_m and (not sum_m or rate_m is rate_m) else ("sum" if sum_m else "count"),
            }
        )
        if rate_m:
            charts[-1]["y"] = rate_m["key"]
            charts[-1]["agg"] = "mean"
            charts[-1]["title"] = f"{rate_m['label']}按{d['label']}"
        elif sum_m:
            charts[-1]["y"] = sum_m["key"]
            charts[-1]["agg"] = "sum"
        else:
            charts[-1]["y"] = None
            charts[-1]["agg"] = "count"
            charts[-1]["title"] = f"记录数按{d['label']}"

    if status:
        s = status[0]
        charts.append(
            {
                "id": "status_pie",
                "title": s["label"],
                "type": "pie",
                "x": s["key"],
                "y": None,
                "agg": "count",
            }
        )

    for dim in dims:
        if dim in status:
            continue
        if dim["unique"] > 16:
            continue
        ycol = sum_m or rate_m
        charts.append(
            {
                "id": f"bar_{dim['key']}",
                "title": f"按{dim['label']}" + (f"·{ycol['label']}" if ycol else "·件数"),
                "type": "bar",
                "x": dim["key"],
                "y": ycol["key"] if ycol else None,
                "agg": "mean" if ycol and (ycol.get("semantic") == "rate" or "率" in ycol["key"]) else (
                    "sum" if ycol else "count"
                ),
            }
        )
        if len(charts) >= 4:
            break

    if not charts and dims:
        dim = dims[0]
        charts.append(
            {
                "id": "bar_default",
                "title": f"按{dim['label']}计数",
                "type": "bar",
                "x": dim["key"],
                "y": None,
                "agg": "count",
            }
        )
    return charts[:4]


def _unique_joins(joins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for j in joins:
        key = (j.get("from_sheet"), j.get("from_field"), j.get("to_sheet"), j.get("via"), j.get("result_field"))
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


_FIVE_M_COL_RE = re.compile(r"^(人-|机-|料-|法|环境-|环-)")


def _is_five_m_column(name: str) -> bool:
    return bool(_FIVE_M_COL_RE.match((name or "").strip()))


def _resolve_df_columns(names: list[str], columns: pd.Index) -> list[str]:
    by_name = {str(c).strip(): c for c in columns}
    resolved: list[str] = []
    for name in names:
        key = (name or "").strip()
        if not key:
            continue
        col = by_name.get(key)
        if col is not None and col not in resolved:
            resolved.append(col)
    return resolved


def _five_m_is_active(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    return numeric >= 1


def apply_filters(df: pd.DataFrame, filters: dict[str, Any] | None) -> pd.DataFrame:
    if df is None or df.empty or not filters:
        return df
    out = df
    for field, spec in filters.items():
        if spec in (None, "", [], {}):
            continue
        if field == "__fiveM__" and isinstance(spec, dict) and spec.get("type") == "five_m":
            all_five_m = [c for c in out.columns if _is_five_m_column(str(c))]
            active = _resolve_df_columns(spec.get("active") or [], out.columns)
            if active:
                mask = pd.Series(True, index=out.index)
                for col in active:
                    mask &= _five_m_is_active(out[col])
                for col in all_five_m:
                    if col in active:
                        continue
                    mask &= ~_five_m_is_active(out[col])
                out = out[mask]
            continue
        if field not in out.columns:
            continue
        if isinstance(spec, dict) and spec.get("type") == "date_range":
            series = _series_to_filter_dates(out[field])
            start, end = spec.get("start"), spec.get("end")
            mask = pd.Series(True, index=out.index)
            if start:
                mask &= series >= pd.to_datetime(start)
            if end:
                mask &= series <= pd.to_datetime(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            out = out[mask]
        elif isinstance(spec, dict) and spec.get("type") in ("contains", "search"):
            needle = str(spec.get("value") or "").strip().lower()
            if needle:
                out = out[out[field].astype(str).str.lower().str.contains(needle, na=False, regex=False)]
        elif isinstance(spec, list):
            out = out[out[field].astype(str).isin([str(x) for x in spec])]
        else:
            out = out[out[field].astype(str) == str(spec)]
    return out


def _infer_year_from_series(series: pd.Series) -> int:
    for v in series:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        if isinstance(v, (datetime, pd.Timestamp)):
            ts = pd.Timestamp(v)
            if not pd.isna(ts):
                return int(ts.year)
        s = str(v).strip()
        m = _ISO_DATE_RE.match(s)
        if m:
            return int(m.group(1))
    return datetime.now().year


def _parse_sortable_date(v: Any, default_year: int) -> pd.Timestamp:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return pd.NaT
    if isinstance(v, (datetime, pd.Timestamp)):
        ts = pd.Timestamp(v)
        return ts if not pd.isna(ts) else pd.NaT
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        d = _excel_serial_to_date(float(v))
        if d:
            return pd.Timestamp(d.year, d.month, d.day)
    s = str(v).strip()
    if not s or s in ("－", "-", "/"):
        return pd.NaT
    m = _ISO_DATE_RE.match(s)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _CN_DATE_RE.match(s)
    if m:
        return pd.Timestamp(default_year, int(m.group(1)), int(m.group(2)))
    n = pd.to_numeric(s, errors="coerce")
    if pd.notna(n) and 20000 <= float(n) <= 80000:
        d = _excel_serial_to_date(float(n))
        if d:
            return pd.Timestamp(d.year, d.month, d.day)
    ts = pd.to_datetime(s, errors="coerce")
    return ts if not pd.isna(ts) else pd.NaT


def _series_to_filter_dates(series: pd.Series) -> pd.Series:
    """Parse heterogeneous date cells (Excel serial, ISO date, ISO datetime) for filtering."""
    default_year = _infer_year_from_series(series)
    return series.apply(lambda v: _parse_sortable_date(v, default_year))


def _build_sort_key(series: pd.Series, field: str) -> pd.Series:
    default_year = _infer_year_from_series(series)
    date_keys = series.apply(lambda v: _parse_sortable_date(v, default_year))
    date_rate = float(date_keys.notna().mean())

    numeric = pd.to_numeric(series, errors="coerce")
    num_rate = float(numeric.notna().mean())

    if field in DATE_SORT_FIELDS or date_rate >= max(0.25, num_rate):
        return date_keys
    if num_rate >= 0.5:
        return numeric
    text = series.astype(str).str.strip().str.lower()
    return text.replace({"": pd.NA, "nan": pd.NA, "－": pd.NA, "-": pd.NA})


def apply_sort(df: pd.DataFrame, sort: dict[str, Any] | None) -> pd.DataFrame:
    if df is None or df.empty or not sort:
        return df
    field = sort.get("field")
    direction = (sort.get("direction") or "asc").lower()
    if not field or field not in df.columns:
        return df
    ascending = direction != "desc"
    work = df.copy()
    work["_sort_key"] = _build_sort_key(work[field], field)
    return work.sort_values("_sort_key", ascending=ascending, na_position="last").drop(columns=["_sort_key"])


def build_column_filter_meta(
    df: pd.DataFrame,
    sheet_spec: dict[str, Any],
    frames: dict[str, pd.DataFrame] | None = None,
    *,
    all_sheets: list[dict[str, Any]] | None = None,
    enum_limit: int = 80,
) -> dict[str, Any]:
    """Build per-column filter widget metadata and VLOOKUP classification maps."""
    frames = frames or {}
    filters_by_field = {f["field"]: f for f in (sheet_spec.get("filters") or []) if f.get("field")}
    form_by_key = {f["key"]: f for f in ((sheet_spec.get("form") or {}).get("fields") or []) if f.get("key")}
    col_by_key = {c["key"]: c for c in (sheet_spec.get("columns") or []) if c.get("key")}

    columns: dict[str, dict[str, Any]] = {}
    display_keys = [c["key"] for c in (sheet_spec.get("columns") or []) if c.get("key") and not str(c["key"]).startswith("__")]

    for key in display_keys:
        col = col_by_key.get(key) or {}
        meta: dict[str, Any] = {"type": "text"}

        is_date = (
            col.get("role") == "date"
            or col.get("type") == "date"
            or "日期" in key
            or filters_by_field.get(key, {}).get("type") == "date_range"
        )
        if is_date:
            meta["type"] = "date"
            if df is not None and not df.empty and key in df.columns:
                dates = _series_to_filter_dates(df[key]).dropna()
                if not dates.empty:
                    meta["min"] = dates.min().date().isoformat()
                    meta["max"] = dates.max().date().isoformat()
            src = filters_by_field.get(key) or {}
            meta["min"] = meta.get("min") or src.get("min")
            meta["max"] = meta.get("max") or src.get("max")
            columns[key] = meta
            continue

        options: list[str] = []
        for src in (filters_by_field.get(key), form_by_key.get(key)):
            if src and src.get("options"):
                options = [str(o) for o in src["options"] if o is not None and str(o).strip()]
                break

        if not options and df is not None and not df.empty and key in df.columns:
            counts = df[key].dropna().astype(str)
            counts = counts[counts.str.lower().ne("nan")]
            uniq = counts.value_counts().head(enum_limit)
            if 0 < len(uniq.index) <= enum_limit:
                options = uniq.index.tolist()

        if not options and col.get("samples"):
            samples = [str(s) for s in col["samples"] if s is not None and str(s).strip()]
            if samples and (col.get("unique") or len(samples)) <= enum_limit:
                options = samples

        if options:
            meta["type"] = "enum"
            meta["options"] = options
        elif col.get("role") == "measure" or col.get("type") in {"number", "percent"}:
            meta["type"] = "number"
        elif any(h in key for h in ("描述", "内容", "对策", "原因", "备注", "事项")):
            meta["type"] = "text"
        elif col.get("unique") and col["unique"] <= enum_limit:
            meta["type"] = "enum"
            meta["options"] = options

        columns[key] = meta

    lookups: dict[str, dict[str, Any]] = {}
    for join in sheet_spec.get("joins") or []:
        if join.get("via") != "VLOOKUP":
            continue
        from_f = join.get("from_field")
        result_f = join.get("result_field")
        to_sheet = (join.get("to_sheet") or "").strip()
        if not from_f or not result_f or not to_sheet:
            continue

        ldf = None
        for name, frame in frames.items():
            if name.strip() == to_sheet:
                ldf = frame
                break
        code_left, code_right = OQC_CODE_JOIN_COLUMNS.get((from_f, result_f), (from_f, result_f))
        use_code_cols = (
            "代码" in to_sheet
            and (from_f, result_f) in OQC_CODE_JOIN_COLUMNS
            and ldf is not None
            and not ldf.empty
            and code_left in ldf.columns
            and code_right in ldf.columns
        )

        if not use_code_cols and (
            ldf is None or ldf.empty or from_f not in ldf.columns or result_f not in ldf.columns
        ):
            lookup_spec = next(
                (s for s in (all_sheets or []) if s.get("name", "").strip() == to_sheet),
                None,
            )
            preview = (lookup_spec or {}).get("preview") or []
            pairs: dict[str, str] = {}
            grouped: dict[str, list[str]] = {}
            for row in preview:
                k = str(row.get(from_f) or "").strip()
                v = str(row.get(result_f) or "").strip()
                if k:
                    pairs[k] = v
                    grouped.setdefault(v, []).append(k)
            if pairs:
                lookups[f"{from_f}__{result_f}"] = {"pairs": pairs, "grouped": grouped}
            continue

        pairs = {}
        grouped: dict[str, list[str]] = {}
        left_col = code_left if use_code_cols else from_f
        right_col = code_right if use_code_cols else result_f
        for _, row in ldf[[left_col, right_col]].dropna(how="all").drop_duplicates().iterrows():
            k = str(row[left_col]).strip()
            v = str(row[right_col]).strip()
            if not k or k.lower() in {"nan", "none"}:
                continue
            pairs[k] = v
            grouped.setdefault(v, []).append(k)
        if pairs:
            lookups[f"{from_f}__{result_f}"] = {"pairs": pairs, "grouped": grouped}
            if from_f in columns and columns[from_f].get("type") != "date":
                columns[from_f]["type"] = "enum"
                columns[from_f]["options"] = sorted(pairs.keys())
                columns[from_f]["lookup"] = f"{from_f}__{result_f}"
            if result_f in columns and columns[result_f].get("type") != "date":
                columns[result_f]["type"] = "enum"
                columns[result_f]["options"] = sorted({v for v in pairs.values()})

    return {"columns": columns, "lookups": lookups}


def compute_kpis(df: pd.DataFrame, kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    n = len(df)
    for k in kpis:
        agg = k.get("agg")
        field = k.get("field")
        val: Any = None
        if agg == "count":
            val = n
        elif df.empty:
            val = 0
        elif agg == "count_where" and field in df.columns:
            val = int((df[field].astype(str) == str(k.get("value"))).sum())
        elif agg == "ratio_where" and field in df.columns:
            val = float((df[field].astype(str) == str(k.get("value"))).mean()) if n else 0
        elif agg == "sum" and field in df.columns:
            val = float(pd.to_numeric(df[field], errors="coerce").sum())
        elif agg == "mean" and field in df.columns:
            val = float(pd.to_numeric(df[field], errors="coerce").mean())
        else:
            val = n
        if pd.isna(val):
            val = None
        result.append({**k, "computed": val})
    return result


def compute_chart(df: pd.DataFrame, chart: dict[str, Any], limit: int = 16) -> dict[str, Any]:
    x = chart.get("x")
    y = chart.get("y")
    agg = chart.get("agg") or "count"
    if df.empty or not x or x not in df.columns:
        return {**chart, "labels": [], "values": []}
    work = df.copy()
    if chart.get("type") == "line" and str(work[x].dtype).startswith("datetime"):
        work["_x"] = pd.to_datetime(work[x], errors="coerce").dt.strftime("%Y-%m-%d")
    else:
        work["_x"] = work[x].astype(str)
    work = work[work["_x"].notna() & (work["_x"] != "NaT") & (work["_x"] != "None")]
    if y and y in work.columns and agg in ("sum", "mean"):
        work["_y"] = pd.to_numeric(work[y], errors="coerce")
        grouped = work.groupby("_x", dropna=True)["_y"]
        series = grouped.mean() if agg == "mean" else grouped.sum()
    else:
        series = work.groupby("_x", dropna=True).size()
    series = series.sort_values(ascending=False) if chart.get("type") != "line" else series.sort_index()
    series = series.head(limit)
    values = [None if pd.isna(v) else (float(v) if not isinstance(v, (int,)) else int(v)) for v in series.tolist()]
    # ints for counts
    if agg == "count":
        values = [int(v or 0) for v in values]
    return {**chart, "labels": [str(i) for i in series.index.tolist()], "values": values}


def page_rows(df: pd.DataFrame, offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    total = int(len(df))
    chunk = df.iloc[offset : offset + limit]
    records = []
    for rec in chunk.to_dict(orient="records"):
        clean = {}
        for k, v in rec.items():
            if pd.isna(v):
                clean[k] = None
            elif hasattr(v, "isoformat"):
                try:
                    clean[k] = v.isoformat()[:10]
                except Exception:
                    clean[k] = str(v)
            elif isinstance(v, (float, int)) and not isinstance(v, bool):
                clean[k] = round(float(v), 6) if not float(v).is_integer() else int(v)
            else:
                try:
                    clean[k] = v.item()
                except Exception:
                    clean[k] = str(v)
        records.append(clean)
    return records, total


def _build_smart_view(sheets: list[dict[str, Any]], joins: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze sheets and their relationships to suggest smart integration.
    
    Returns a recommendation for how to integrate related sheets into
    unified views with CRUD functionality.
    """
    # 1. Identify main data sheets (fact tables with substantial data)
    main_sheets = []
    for s in sheets:
        if s['kind'] == 'fact' and s['row_count'] >= 20 and not s.get('empty'):
            main_sheets.append({
                'name': s['name'],
                'row_count': s['row_count'],
                'col_count': s['col_count'],
                'reason': '主要数据表',
            })
    
    # 2. Identify lookup/config sheets (referenced by others)
    lookup_sheets = []
    referenced_sheets = set()
    
    for j in joins:
        # If sheet A references sheet B via VLOOKUP, B is a lookup table
        referenced_sheets.add(j['to_sheet'])
    
    for s in sheets:
        if s['name'] in referenced_sheets or s['kind'] == 'lookup':
            if s['row_count'] < 200:  # Typical config tables are small
                lookup_sheets.append({
                    'name': s['name'],
                    'row_count': s['row_count'],
                    'referenced_by': [j['from_sheet'] for j in joins if j['to_sheet'] == s['name']],
                    'reason': '配置/对照表（被其他表引用）',
                })
    
    # 3. Identify dashboard/report sheets
    dashboard_sheets = []
    for s in sheets:
        if s['kind'] in ('dashboard', 'instruction'):
            dashboard_sheets.append({
                'name': s['name'],
                'kind': s['kind'],
                'reason': '仪表板/说明',
            })
    
    # 4. Generate integration recommendations
    recommendations = []
    
    for main in main_sheets:
        # Find which lookup tables this main sheet uses
        related_lookups = []
        field_mappings = []  # Detailed field-level mappings
        
        for j in joins:
            if j['from_sheet'] == main['name'] and j['to_sheet'] in [l['name'] for l in lookup_sheets]:
                lookup_sheet_name = j['to_sheet']
                
                # Find the actual lookup sheet to get column names
                lookup_sheet_obj = next((s for s in sheets if s['name'] == lookup_sheet_name), None)
                main_sheet_obj = next((s for s in sheets if s['name'] == main['name']), None)
                
                if lookup_sheet_obj and main_sheet_obj:
                    # Extract column index from "第X列"
                    to_field_str = j.get('to_field', '')
                    lookup_key_col_name = None
                    if '第' in to_field_str and '列' in to_field_str:
                        try:
                            col_idx = int(to_field_str.replace('第', '').replace('列', '')) - 1
                            if 0 <= col_idx < len(lookup_sheet_obj['columns']):
                                lookup_key_col_name = lookup_sheet_obj['columns'][col_idx]['key']
                        except:
                            pass
                    
                    # Get the main column that will display lookup results
                    result_col_name = j.get('result_field')
                    from_col_name = j.get('from_field')
                    
                    field_mappings.append({
                        'lookup_sheet': lookup_sheet_name,
                        'main_col': result_col_name,  # Column in main table to show dropdown
                        'main_key_col': from_col_name,  # Column in main table used for lookup
                        'lookup_key_col': lookup_key_col_name,  # Column in lookup table for matching
                        'via': j['via'],
                    })
                
                if lookup_sheet_name not in [l['lookup_name'] for l in related_lookups]:
                    related_lookups.append({
                        'lookup_name': lookup_sheet_name,
                        'field': j['from_field'],
                        'via': j['via'],
                    })
        
        if related_lookups:
            recommendations.append({
                'type': 'integrate',
                'main_sheet': main['name'],
                'lookup_sheets': [l['lookup_name'] for l in related_lookups],
                'field_mappings': field_mappings,  # NEW: Detailed field-level info
                'description': f"将 {main['name']} 与 {len(related_lookups)} 个配置表整合",
                'details': related_lookups,
                'benefit': '配置表作为下拉选项，无需单独页面',
            })
    
    # 5. Suggest hiding pure lookup sheets
    hide_suggestions = []
    for lookup in lookup_sheets:
        if lookup['referenced_by']:
            hide_suggestions.append({
                'sheet_name': lookup['name'],
                'reason': f"被 {', '.join(lookup['referenced_by'][:2])} 等引用，可作为内嵌选项",
            })
    
    return {
        'has_recommendations': len(recommendations) > 0,
        'main_sheets': main_sheets,
        'lookup_sheets': lookup_sheets,
        'dashboard_sheets': dashboard_sheets,
        'recommendations': recommendations,
        'hide_suggestions': hide_suggestions,
        'summary': _generate_summary(main_sheets, lookup_sheets, recommendations),
    }


def _generate_summary(main_sheets, lookup_sheets, recommendations):
    """Generate a human-readable summary of the integration suggestion."""
    parts = []
    
    if main_sheets:
        parts.append(f"检测到 {len(main_sheets)} 个主数据表")
    
    if lookup_sheets:
        parts.append(f"{len(lookup_sheets)} 个配置/对照表")
    
    if recommendations:
        parts.append(f"建议 {len(recommendations)} 个整合方案")
    else:
        parts.append("暂无整合建议")
    
    return "，".join(parts) + "。"
