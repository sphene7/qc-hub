"""Generate entry forms from parsed sheet specs and fill computed columns."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd

from .formulas import col_letters_to_index
from .logutil import log
from .semantics import ID_HINTS, SKIP_DIM, STATUS_HINTS, page_rows

CELL_RE = re.compile(r"(?<![A-Za-z0-9_])(\$?[A-Z]{1,3})(\$?\d+)\b", re.I)

MEASURE_NAME_HINTS = ("-张程亮", "-陈刚", "-王岩良", "QCP/SOP", "-刘焕良", "天数", "抽检数", "不良数", "良品数")
RICH_TEXT_IMAGE_FIELDS = frozenset({"内部未结案待跟进事项"})

# OQC 主表：Excel 有列但解析为 empty 的仍可录入字段
OQC_MANUAL_FIELDS: dict[str, str] = {
    "同批送检次数": "measure",
    "是否紧急出货": "dimension",
    "层别备注": "text",
    "单据类型": "dimension",
    "OA单号": "text",
    "结案日期": "date",
    "结案天数": "measure",
    "责任单位": "dimension",
    "责任课级负责人": "dimension",
    "品质工程师": "dimension",
    "判定_2": "dimension",
}

# OQC 录入表单不展示的列（表中可保留）
OQC_FORM_SKIP_FIELDS = frozenset({"是否结案"})


def _is_oqc_entry_sheet(sheet: dict[str, Any]) -> bool:
    name = (sheet.get("name") or "")
    return "OQC" in name or "抽检批次" in name


def is_rich_text_field(key: str) -> bool:
    name = (key or "").strip()
    return name in RICH_TEXT_IMAGE_FIELDS or name.startswith("结案后稽核事项")


def attach_forms(spec: dict[str, Any], frames: dict[str, pd.DataFrame]) -> None:
    for sheet in spec["sheets"]:
        sheet["form"] = build_form_spec(spec, sheet, frames)


def build_form_spec(spec: dict[str, Any], sheet: dict[str, Any], frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    if not _sheet_entry_enabled(sheet):
        return {"enabled": False, "fields": [], "computed": []}

    df = frames.get(sheet["name"])
    formula_by_name = {c["name"]: c for c in (sheet.get("formula") or {}).get("columns") or []}
    fields: list[dict[str, Any]] = []
    computed: list[dict[str, Any]] = []

    for col in sheet.get("columns") or []:
        key = col["key"]
        if key.startswith("__"):
            continue
        col = _entry_column(col, sheet, formula_by_name)
        finfo = formula_by_name.get(key)
        role = col.get("role")
        if role == "empty" and not finfo:
            manual_role = OQC_MANUAL_FIELDS.get(key) if _is_oqc_entry_sheet(sheet) else None
            if manual_role:
                col = {**col, "role": manual_role}
            elif not is_rich_text_field(key):
                continue
            else:
                col = {**col, "role": "text"}
        elif not role and not finfo and _is_oqc_entry_sheet(sheet) and key in OQC_MANUAL_FIELDS:
            col = {**col, "role": OQC_MANUAL_FIELDS[key]}
        oqc_manual = _is_oqc_entry_sheet(sheet) and key in OQC_MANUAL_FIELDS
        if not oqc_manual and (col.get("role") == "id" or any(h in key for h in ID_HINTS)):
            computed.append(_computed_field(col, finfo, "auto_id"))
            continue
        if finfo and finfo.get("kind") in {"lookup", "extract", "calculated"}:
            computed.append(_computed_field(col, finfo, finfo["kind"]))
            continue
        if finfo and finfo.get("kind") == "aggregate":
            continue
        if key == "判定" and _is_oqc_entry_sheet(sheet):
            computed.append(_computed_field(col, finfo, "calculated"))
            continue

        widget = _widget_for(col)
        options = _options_for(col, df, spec, frames, formula_by_name)
        allow_custom = widget == "select"
        if key == "是否紧急出货":
            widget = "select"
            options = ["是", "否"]
            allow_custom = False
        if key == "判定_2" and _is_oqc_entry_sheet(sheet):
            widget = "select"
            options = ["OK", "NG"]
            allow_custom = False
            required = True
        if _is_oqc_entry_sheet(sheet) and key in OQC_FORM_SKIP_FIELDS:
            continue
        if widget == "select" and not options:
            widget = "text"
            allow_custom = False
        required = bool(col.get("fill", 0) >= 0.7 and col.get("role") in {"date", "dimension", "measure"})
        if col.get("semantic") == "month" or "月份" in key:
            required = False
        fields.append(
            {
                "key": key,
                "label": col.get("label") or key,
                "widget": widget,
                "type": col.get("type"),
                "role": col.get("role"),
                "required": required,
                "options": options,
                "allow_custom": allow_custom,
                "help": _help_text(col, finfo),
            }
        )

    field_limit = _field_limit(sheet, len(fields))
    kept = fields[:field_limit]
    kept_keys = {f["key"] for f in kept}
    for field in fields[field_limit:]:
        if field.get("widget") == "rich_text" and field["key"] not in kept_keys:
            kept.append(field)
            kept_keys.add(field["key"])
    return {
        "enabled": bool(kept),
        "fields": kept,
        "computed": computed,
    }


def _sheet_entry_enabled(sheet: dict[str, Any]) -> bool:
    if sheet.get("derived"):
        return False
    if sheet.get("kind") in {"instruction", "hidden", "lookup", "dashboard"}:
        return False
    named_cols = [
        c["key"]
        for c in sheet.get("columns") or []
        if c.get("key") and not c["key"].startswith("__") and not str(c["key"]).startswith("列")
    ]
    return len(named_cols) >= 2


def _field_limit(sheet: dict[str, Any], field_count: int) -> int:
    if _is_oqc_entry_sheet(sheet):
        return field_count
    col_count = sheet.get("col_count") or field_count
    if col_count <= 40:
        return field_count
    return min(field_count, 22)


def _entry_column(col: dict[str, Any], sheet: dict[str, Any], formula_by_name: dict[str, Any]) -> dict[str, Any]:
    if col.get("role") != "empty" or formula_by_name.get(col["key"]):
        return col
    if not sheet.get("empty"):
        return col
    key = col.get("key") or ""
    if not key or str(key).startswith("列"):
        return col
    role = col.get("role") or "empty"
    if any(h in key for h in ID_HINTS):
        role = "id"
    elif key in {"日期", "投诉日期"} or "日期" in key:
        role = "date"
    elif any(h in key for h in MEASURE_NAME_HINTS) or key.endswith("数"):
        role = "measure"
    elif any(h in key for h in STATUS_HINTS) or "月份" in key:
        role = "dimension"
    elif any(h in key for h in SKIP_DIM):
        role = "text"
    else:
        role = "dimension"
    return {**col, "role": role}


def _computed_field(col: dict[str, Any], finfo: dict[str, Any] | None, kind: str) -> dict[str, Any]:
    return {
        "key": col["key"],
        "label": col.get("label") or col["key"],
        "kind": kind,
        "expr": (finfo or {}).get("expr") or (finfo or {}).get("sample") or "",
        "depends_on": (finfo or {}).get("depends_on") or [],
    }


def _is_five_m(col: dict[str, Any]) -> bool:
    key = col.get("key") or ""
    if col.get("role") != "measure":
        return False
    return any(h in key for h in ("人-", "机-", "料-", "法", "环境-"))


def _is_year_month_col(col: dict[str, Any]) -> bool:
    key = col.get("key") or ""
    if key == "月份" or col.get("semantic") == "month":
        return True
    return False


def _widget_for(col: dict[str, Any]) -> str:
    key = col.get("key") or ""
    if is_rich_text_field(key):
        return "rich_text"
    if _is_year_month_col(col):
        return "month"
    if col.get("type") == "date" or col.get("role") == "date":
        return "date"
    if _is_five_m(col):
        return "toggle"
    if col.get("type") in {"number", "percent"} or col.get("role") == "measure":
        return "number"
    if any(k in col["key"] for k in SKIP_DIM):
        return "textarea"
    uniq = col.get("unique") or 0
    if col.get("role") == "dimension" or col.get("semantic") == "status" or 1 < uniq <= 40:
        return "select"
    return "text"


def _options_for(
    col: dict[str, Any],
    df: pd.DataFrame | None,
    spec: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    formula_by_name: dict[str, Any],
) -> list[str]:
    if col.get("type") in {"number", "percent"} or col.get("role") == "measure":
        return []
    vals: list[str] = []
    seen: set[str] = set()

    def add(v: Any) -> None:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return
        s = str(v).strip()
        if not s or s.lower() in {"nan", "none", "nat"}:
            return
        if s not in seen:
            seen.add(s)
            vals.append(s)

    if df is not None and col["key"] in df.columns:
        for v in df[col["key"]].dropna().astype(str):
            add(v)
            if len(vals) >= 80:
                break

    # If this field is a VLOOKUP key, also pull keys from the code sheet.
    for other in spec.get("sheets") or []:
        for fcol in (other.get("formula") or {}).get("columns") or []:
            for v in fcol.get("vlookups") or []:
                if v.get("lookup_name") == col["key"]:
                    for k in _lookup_map(frames, spec, v).keys():
                        add(k)
                if fcol.get("name") == col["key"] and v.get("return_col"):
                    for k in _lookup_map(frames, spec, v).values():
                        add(k)

    return vals[:80]


def _help_text(col: dict[str, Any], finfo: dict[str, Any] | None) -> str:
    if finfo:
        return f"原表公式列，录入后自动计算：{(finfo.get('expr') or '')[:80]}"
    if col.get("semantic") == "status":
        return "使用原表已有分类"
    if col.get("role") == "dimension":
        return "下拉选项来自原表分类 / 对照表"
    return ""


def _sheet_column_key(spec: dict[str, Any], sheet_name: str, col_index: int) -> str | None:
    target = (sheet_name or "").strip()
    for sheet in spec.get("sheets") or []:
        sn = (sheet.get("name") or "").strip()
        if sn != target and sheet.get("name") != sheet_name:
            continue
        for col in sheet.get("columns") or []:
            if col.get("index") == col_index:
                return col.get("key")
    return None


def _lookup_map(frames: dict[str, pd.DataFrame], spec: dict[str, Any], vlookup: dict[str, Any]) -> dict[str, Any]:
    sheet_name = vlookup.get("table_sheet")
    key_name = vlookup.get("lookup_name")
    key_i = vlookup.get("table_key_col")
    ret_i = vlookup.get("return_col")
    if not sheet_name or not ret_i:
        return {}
    df = _frame_by_name(frames, sheet_name)
    if df is None or df.empty:
        return {}

    ret_name = _sheet_column_key(spec, sheet_name, int(ret_i))
    if not key_name and key_i:
        key_name = _sheet_column_key(spec, sheet_name, int(key_i))

    out: dict[str, Any] = {}
    if key_name and ret_name and key_name in df.columns and ret_name in df.columns:
        for _, row in df.iterrows():
            key = row.get(key_name)
            val = row.get(ret_name)
            if key is None or (isinstance(key, float) and pd.isna(key)):
                continue
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            k = str(key).strip()
            if k:
                out[k] = val
        return out

    if not key_i:
        return {}
    key_i, ret_i = int(key_i), int(ret_i)
    if key_i < 1 or ret_i < 1 or key_i > df.shape[1] or ret_i > df.shape[1]:
        return {}
    for key, val in zip(df.iloc[:, key_i - 1].tolist(), df.iloc[:, ret_i - 1].tolist()):
        if key is None or (isinstance(key, float) and pd.isna(key)):
            continue
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        out[str(key).strip()] = val
    return out


def _frame_by_name(frames: dict[str, pd.DataFrame], name: str) -> pd.DataFrame | None:
    if name in frames:
        return frames[name]
    name = (name or "").strip()
    for k, df in frames.items():
        if k.strip() == name:
            return df
    return None


CLOSED_STATUS_VALUES = frozenset({"close", "closed", "已结案"})
OPEN_STATUS_VALUES = frozenset({"open", "未结案"})


def _normalize_close_status(val: Any) -> str:
    s = str(val or "").strip()
    if s.lower() in CLOSED_STATUS_VALUES or s == "Close":
        return "Close"
    if s.lower() in OPEN_STATUS_VALUES or s == "Open":
        return "Open"
    return "待选择"


def _is_open_close_status(val: Any) -> bool:
    return _normalize_close_status(val) == "Open"


def _is_closed_close_status(val: Any) -> bool:
    return _normalize_close_status(val) == "Close"


def _sheet_overdue_meta(sheet: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    columns = sheet.get("columns") or []
    overdue_col = next((c["key"] for c in columns if "逾期" in c["key"]), None)
    date_col = next((c["key"] for c in columns if c.get("role") == "date"), None)
    if not date_col:
        date_col = next((c["key"] for c in columns if c["key"] in ("日期", "发生日期")), None)
    status_col = next((c["key"] for c in columns if c["key"] == "是否结案"), None)
    return overdue_col, date_col, status_col


def _parse_row_date(val: Any) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    dt = pd.to_datetime(val, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date()


def _compute_overdue_days(date_val: Any) -> int | None:
    d = _parse_row_date(date_val)
    if not d:
        return None
    return (date.today() - d).days


def _overdue_values_equal(a: Any, b: Any) -> bool:
    if _is_blank_cell(a) and _is_blank_cell(b):
        return True
    try:
        if a is not None and b is not None and float(a) == float(b):
            return True
    except (TypeError, ValueError):
        pass
    return a == b


def apply_overdue_days(row: dict[str, Any], sheet: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Only Open rows get 逾期天数 = today - 日期; others stay empty."""
    overdue_col, date_col, status_col = _sheet_overdue_meta(sheet)
    if not overdue_col:
        return row, False

    status = row.get(status_col) if status_col else None
    new_val: int | None = None
    if _is_open_close_status(status) and date_col and not _is_blank_cell(row.get(date_col)):
        new_val = _compute_overdue_days(row.get(date_col))

    old_val = row.get(overdue_col)
    if _overdue_values_equal(old_val, new_val):
        return row, False
    row[overdue_col] = new_val
    return row, True


def repair_overdue_days(df: pd.DataFrame, sheet: dict[str, Any]) -> tuple[pd.DataFrame, int]:
    overdue_col, _, _ = _sheet_overdue_meta(sheet)
    if not overdue_col or df is None or df.empty or overdue_col not in df.columns:
        return df, 0

    out = df.copy()
    changed = 0
    for idx in out.index:
        row = out.loc[idx].to_dict()
        _, did = apply_overdue_days(row, sheet)
        if did:
            out.at[idx, overdue_col] = row[overdue_col]
            changed += 1
    if changed:
        log(f"[repair_overdue_days] updated {changed} row(s) in {overdue_col!r}")
    return out, changed


def fill_row(
    spec: dict[str, Any],
    sheet: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    values: dict[str, Any],
    *,
    assign_id: bool = False,
) -> dict[str, Any]:
    columns = sheet.get("columns") or []
    keys = [c["key"] for c in columns if not c["key"].startswith("__")]
    row = {k: _coerce(values.get(k), next((c for c in columns if c["key"] == k), {})) for k in keys}

    df = frames.get(sheet["name"])
    if assign_id:
        for col in columns:
            if col.get("role") == "id" or any(h in col["key"] for h in ID_HINTS):
                row[col["key"]] = _next_id(df, col["key"])

    date_col = next((c["key"] for c in columns if c.get("role") == "date"), None)
    month_col = next((c["key"] for c in columns if c.get("semantic") == "month" or "月份" in c["key"]), None)
    if date_col and month_col and row.get(date_col) and not row.get(month_col):
        dt = pd.to_datetime(row[date_col], errors="coerce")
        if not pd.isna(dt):
            row[month_col] = f"{int(dt.year)}年{int(dt.month)}月"

    overdue_col, _, _ = _sheet_overdue_meta(sheet)

    formula_cols = list((sheet.get("formula") or {}).get("columns") or [])
    headers = keys
    # Dependency order: extract → lookup → calculated
    order = {"extract": 0, "lookup": 1, "calculated": 2, "formula": 3, "index": -1}
    formula_cols.sort(key=lambda c: order.get(c.get("kind"), 9))

    id_keys = {c["key"] for c in columns if c.get("role") == "id" or any(h in c["key"] for h in ID_HINTS)}

    for finfo in formula_cols:
        name = finfo.get("name")
        if name not in row:
            continue
        kind = finfo.get("kind")
        # 序号等 ID 列：新增时上面已赋值，编辑时保留原值，勿用 ROW()-1 等公式重算
        if kind == "index" or name in id_keys:
            continue
        if name == month_col and row.get(month_col):
            continue
        if name == overdue_col:
            continue
        row[name] = _eval_formula_col(finfo, row, headers, spec, frames)

    for col in columns:
        key = col["key"]
        if key.startswith("__"):
            continue
        if col.get("role") == "measure" and row.get(key) is None:
            row[key] = 0
        if (col.get("semantic") == "status" or any(h in key for h in STATUS_HINTS)) and row.get(key) is None:
            row[key] = "待选择"

    apply_overdue_days(row, sheet)
    row["__source"] = "entered"
    return row


def _next_id(df: pd.DataFrame | None, key: str) -> int:
    if df is None or df.empty or key not in df.columns:
        return 1
    series = pd.to_numeric(df[key], errors="coerce")
    mx = series.max()
    if pd.isna(mx):
        return len(df) + 1
    return int(mx) + 1


def _coerce(value: Any, col: dict[str, Any]) -> Any:
    if value is None or value == "":
        return None
    typ = col.get("type")
    if typ in {"number", "percent"} or col.get("role") == "measure":
        try:
            n = float(value)
            return int(n) if n.is_integer() else n
        except (TypeError, ValueError):
            return None
    if typ == "date" or col.get("role") == "date":
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date().isoformat()
    return value


def _eval_formula_col(
    finfo: dict[str, Any],
    row: dict[str, Any],
    headers: list[str],
    spec: dict[str, Any],
    frames: dict[str, pd.DataFrame],
) -> Any:
    kind = finfo.get("kind")
    sample = finfo.get("sample") or finfo.get("expr") or ""
    deps = finfo.get("depends_on") or []
    name = finfo.get("name")

    if kind == "extract" or ("LEFT" in sample.upper() and "FIND" in sample.upper()):
        src = deps[0] if deps else None
        raw = str(row.get(src) or "").strip()
        if not raw:
            return None
        if "-" in raw:
            return raw.split("-", 1)[0]
        return raw

    if kind == "lookup" or finfo.get("vlookups"):
        vlookups = finfo.get("vlookups") or []
        if vlookups:
            v = vlookups[0]
            key = row.get(v.get("lookup_name") or (deps[0] if deps else None))
            if key is None or str(key).strip() == "":
                return None
            mp = _lookup_map(frames, spec, v)
            found = mp.get(str(key).strip())
            if found is None:
                # try without spaces / case
                for k, val in mp.items():
                    if str(k).strip().lower() == str(key).strip().lower():
                        return val
                return None
            return found

    if sample:
        return _eval_sample(sample, row, headers)
    if len(deps) == 2 and name and "率" in name:
        a, b = row.get(deps[0]), row.get(deps[1])
        try:
            return float(a) / float(b) if b not in (None, 0, 0.0) else None
        except (TypeError, ValueError, ZeroDivisionError):
            return row.get(name)
    return row.get(name)


def _eval_sample(sample: str, row: dict[str, Any], headers: list[str]) -> Any:
    text = sample[1:] if sample.startswith("=") else sample
    text = text.lstrip("+")

    def repl(m: re.Match) -> str:
        col_i = col_letters_to_index(m.group(1))
        if 1 <= col_i <= len(headers):
            val = row.get(headers[col_i - 1])
            return _literal(val)
        return "None"

    expr = CELL_RE.sub(repl, text)

    def brace_repl(m: re.Match) -> str:
        field = m.group(1)
        return _literal(row.get(field))

    expr = re.sub(r"\{([^}]+)\}", brace_repl, expr)
    expr = re.sub(r"IFERROR\s*\(", "iferror(", expr, flags=re.I)
    expr = re.sub(r"\bIF\s*\(", "iff(", expr, flags=re.I)
    expr = expr.replace("<>", "!=")
    expr = re.sub(r"(?<![<>=!])=(?!=)", "==", expr)
    try:
        return _safe_eval(expr)
    except ZeroDivisionError:
        return None
    except Exception:
        return None


def _literal(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "None"
    if isinstance(val, bool):
        return "True" if val else "False"
    if isinstance(val, (int, float)):
        return repr(val)
    return repr(str(val))


def iff(cond, a, b):
    return a if cond else b


def iferror(val, fallback):
    if val is None:
        return fallback
    return val


def _safe_eval(expr: str) -> Any:
    allowed = {
        "iff": iff,
        "iferror": iferror,
        "None": None,
        "True": True,
        "False": False,
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "int": int,
        "float": float,
        "str": str,
    }
    # reject names
    if re.search(r"__", expr) or re.search(r"import|lambda|open|exec|eval", expr, re.I):
        raise ValueError("blocked")
    return eval(expr, {"__builtins__": {}}, allowed)  # noqa: S307  restricted env


def append_row(item: dict[str, Any], sheet_name: str, values: dict[str, Any]) -> dict[str, Any]:
    log(f"[entry.append_row] sheet={sheet_name!r} value_keys={list(values.keys())}")
    spec = item["spec"]
    sheet = next((s for s in spec["sheets"] if s["name"] == sheet_name), None)
    if not sheet:
        sheet = next((s for s in spec["sheets"] if (s.get("name") or "").strip() == (sheet_name or "").strip()), None)
        if sheet:
            log(f"[entry.append_row] resolved sheet name {sheet_name!r} -> {sheet['name']!r}")
            sheet_name = sheet["name"]
    form_enabled = (sheet.get("form") or {}).get("enabled") if sheet else False
    if not sheet or (not form_enabled and sheet.get("kind") not in ("fact", "table")):
        log(f"[entry.append_row] FAIL sheet not enabled sheet={sheet_name!r}")
        raise ValueError("该工作表不支持录入")
    row = fill_row(spec, sheet, item["frames"], values, assign_id=True)
    df = item["frames"].get(sheet_name)
    if df is None:
        log(f"[entry.append_row] FAIL no dataframe sheet={sheet_name!r} frame_keys={list(item['frames'].keys())}")
        raise ValueError("找不到数据表")
    if "__source" not in df.columns:
        df = df.copy()
        df["__source"] = "imported"
        item["frames"][sheet_name] = df
    new_df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    item["frames"][sheet_name] = new_df
    sheet["row_count"] = int(len(new_df))
    sheet["empty"] = False
    _refresh_options(spec, sheet, new_df, item["frames"])
    clean, _ = page_rows(pd.DataFrame([row]), 0, 1)
    saved = clean[0] if clean else row
    log(
        f"[entry.append_row] OK sheet={sheet_name!r} rows={len(new_df)} "
        f"new_id={saved.get('序号')} 是否结案={saved.get('是否结案')} source=entered"
    )
    return saved


def preview_row(item: dict[str, Any], sheet_name: str, values: dict[str, Any]) -> dict[str, Any]:
    spec = item["spec"]
    sheet = next((s for s in spec["sheets"] if s["name"] == sheet_name), None)
    if not sheet:
        raise ValueError("找不到工作表")
    row = fill_row(spec, sheet, item["frames"], values, assign_id=False)
    clean, _ = page_rows(pd.DataFrame([row]), 0, 1)
    return clean[0] if clean else row


def update_row_field(
    item: dict[str, Any],
    sheet_name: str,
    row_id_key: str,
    row_id_value: Any,
    field: str,
    value: Any,
) -> dict[str, Any]:
    spec = item["spec"]
    sheet = next((s for s in spec["sheets"] if s["name"] == sheet_name), None)
    if not sheet:
        raise ValueError("找不到工作表")
    df = item["frames"].get(sheet_name)
    if df is None or df.empty:
        raise ValueError("该表无数据")
    if row_id_key not in df.columns:
        raise ValueError(f"找不到行标识列 {row_id_key}")
    if field not in df.columns:
        raise ValueError(f"找不到字段 {field}")

    col = next((c for c in sheet.get("columns") or [] if c["key"] == field), {})
    coerced = _coerce(value, col)

    series = df[row_id_key]
    if pd.api.types.is_numeric_dtype(series):
        try:
            match_val = float(row_id_value)
            mask = pd.to_numeric(series, errors="coerce") == match_val
        except (TypeError, ValueError):
            mask = series.astype(str) == str(row_id_value)
    else:
        mask = series.astype(str) == str(row_id_value)

    if not mask.any():
        raise ValueError("找不到该行")

    idx = df.index[mask][0]
    df = df.copy()
    df.at[idx, field] = coerced

    overdue_col, _, _ = _sheet_overdue_meta(sheet)
    if overdue_col and field in {overdue_col, "是否结案", "日期"}:
        row_dict = df.loc[idx].to_dict()
        apply_overdue_days(row_dict, sheet)
        if overdue_col in df.columns:
            df.at[idx, overdue_col] = row_dict.get(overdue_col)

    item["frames"][sheet_name] = df
    _refresh_options(spec, sheet, df, item["frames"])
    clean, _ = page_rows(df.loc[[idx]], 0, 1)
    return clean[0] if clean else df.loc[idx].to_dict()


def _is_blank_cell(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    s = str(v).strip()
    return s in ("", "-", "－", "None", "nan", "NaN")


def is_junk_row(row: dict[str, Any], id_key: str = "序号") -> bool:
    """无序号且所有业务字段均为空的行（Excel 导入残留）。"""
    id_val = row.get(id_key)
    if not _is_blank_cell(id_val):
        return False
    for k, v in row.items():
        if str(k).startswith("__"):
            continue
        if not _is_blank_cell(v):
            return False
    return True


def drop_junk_rows(df: pd.DataFrame, id_key: str = "序号") -> pd.DataFrame:
    if df is None or df.empty:
        return df
    keep = [not is_junk_row(r.to_dict(), id_key) for _, r in df.iterrows()]
    if all(keep):
        return df
    return df.loc[keep].reset_index(drop=True)


LEGACY_MONTH_DEFAULT_YEAR = 2026


def _normalize_month_cell(value: Any, default_year: int = LEGACY_MONTH_DEFAULT_YEAR) -> tuple[Any, bool]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value, False
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "nat"}:
        return value, False
    if re.match(r"^\d{4}年\d{1,2}月$", s):
        return s, False
    m = re.match(r"^(\d{1,2})月$", s)
    if m:
        return f"{default_year}年{int(m.group(1))}月", True
    return value, False


def repair_legacy_month_values(
    df: pd.DataFrame,
    *,
    col: str = "月份",
    default_year: int = LEGACY_MONTH_DEFAULT_YEAR,
) -> tuple[pd.DataFrame, int]:
    """Convert legacy month labels like '8月' to '2026年8月'."""
    if df is None or df.empty or col not in df.columns:
        return df, 0
    out = df.copy()
    changed = 0
    for idx in out.index:
        new_val, did = _normalize_month_cell(out.at[idx, col], default_year)
        if did:
            out.at[idx, col] = new_val
            changed += 1
    if changed:
        log(f"[repair_legacy_month_values] normalized {changed} row(s) in {col!r}")
    return out, changed


def repair_missing_row_ids(df: pd.DataFrame, id_key: str = "序号") -> pd.DataFrame:
    """Restore 序号 lost when ROW()-1 was re-evaluated during row edits."""
    if df is None or df.empty or id_key not in df.columns:
        return df
    out = df.copy()
    repaired = 0
    for pos, idx in enumerate(out.index):
        if not _is_blank_cell(out.at[idx, id_key]):
            continue
        if is_junk_row(out.loc[idx].to_dict(), id_key):
            continue
        prev_id = next_id = None
        for j in range(pos - 1, -1, -1):
            v = out.iloc[j][id_key]
            if not _is_blank_cell(v):
                prev_id = float(v)
                break
        for j in range(pos + 1, len(out)):
            v = out.iloc[j][id_key]
            if not _is_blank_cell(v):
                next_id = float(v)
                break
        if prev_id is not None and next_id is not None and next_id - prev_id > 1:
            out.at[idx, id_key] = int(prev_id + 1)
            repaired += 1
        elif prev_id is not None:
            out.at[idx, id_key] = int(prev_id + 1)
            repaired += 1
        elif next_id is not None:
            out.at[idx, id_key] = max(1, int(next_id - 1))
            repaired += 1
    if repaired:
        log(f"[repair_missing_row_ids] restored {repaired} row id(s) in {id_key!r}")
    return out


def _row_mask(df: pd.DataFrame, row_id_key: str, row_id_value: Any) -> pd.Series:
    if row_id_key not in df.columns:
        raise ValueError(f"找不到行标识列 {row_id_key}")
    series = df[row_id_key]
    if pd.api.types.is_numeric_dtype(series):
        try:
            match_val = float(row_id_value)
            return pd.to_numeric(series, errors="coerce") == match_val
        except (TypeError, ValueError):
            return series.astype(str) == str(row_id_value)
    return series.astype(str) == str(row_id_value)


def update_row_values(
    item: dict[str, Any],
    sheet_name: str,
    row_id_key: str,
    row_id_value: Any,
    values: dict[str, Any],
) -> dict[str, Any]:
    spec = item["spec"]
    sheet = next((s for s in spec["sheets"] if s["name"] == sheet_name), None)
    if not sheet:
        sheet = next(
            (s for s in spec["sheets"] if (s.get("name") or "").strip() == (sheet_name or "").strip()),
            None,
        )
        if sheet:
            sheet_name = sheet["name"]
    if not sheet:
        raise ValueError("找不到工作表")
    df = item["frames"].get(sheet_name)
    if df is None or df.empty:
        raise ValueError("该表无数据")

    mask = _row_mask(df, row_id_key, row_id_value)
    if not mask.any():
        raise ValueError("找不到该行")

    idx = df.index[mask][0]
    existing = df.loc[idx].to_dict()
    merged = {**existing, **values}
    merged.pop("__source", None)
    row = fill_row(spec, sheet, item["frames"], merged, assign_id=False)
    row["__source"] = existing.get("__source") or "entered"

    df = df.copy()
    for key, val in row.items():
        if key in df.columns:
            df.at[idx, key] = val
    item["frames"][sheet_name] = df
    _refresh_options(spec, sheet, df, item["frames"])
    clean, _ = page_rows(df.loc[[idx]], 0, 1)
    return clean[0] if clean else row


def delete_row(
    item: dict[str, Any],
    sheet_name: str,
    row_id_key: str,
    row_id_value: Any | None = None,
    *,
    db_id: int | None = None,
) -> int:
    spec = item["spec"]
    sheet = next((s for s in spec["sheets"] if s["name"] == sheet_name), None)
    if not sheet:
        sheet = next(
            (s for s in spec["sheets"] if (s.get("name") or "").strip() == (sheet_name or "").strip()),
            None,
        )
        if sheet:
            sheet_name = sheet["name"]
    if not sheet:
        raise ValueError("找不到工作表")
    df = item["frames"].get(sheet_name)
    if df is None or df.empty:
        raise ValueError("该表无数据")

    if db_id is not None:
        if "__db_id" not in df.columns:
            raise ValueError("找不到该行")
        mask = pd.to_numeric(df["__db_id"], errors="coerce") == int(db_id)
    elif row_id_value is not None:
        mask = _row_mask(df, row_id_key, row_id_value)
    else:
        raise ValueError("无法识别要删除的行")

    if not mask.any():
        raise ValueError("找不到该行")

    new_df = df.loc[~mask].reset_index(drop=True)
    new_df = drop_junk_rows(new_df, row_id_key)
    item["frames"][sheet_name] = new_df
    sheet["row_count"] = int(len(new_df))
    sheet["empty"] = len(new_df) == 0
    _refresh_options(spec, sheet, new_df, item["frames"])
    return int(len(new_df))


def delete_rows(
    item: dict[str, Any],
    sheet_name: str,
    row_id_key: str,
    targets: list[dict[str, Any]],
) -> int:
    """Delete multiple rows in one pass."""
    if not targets:
        raise ValueError("未指定要删除的行")
    spec = item["spec"]
    sheet = next((s for s in spec["sheets"] if s["name"] == sheet_name), None)
    if not sheet:
        sheet = next(
            (s for s in spec["sheets"] if (s.get("name") or "").strip() == (sheet_name or "").strip()),
            None,
        )
        if sheet:
            sheet_name = sheet["name"]
    if not sheet:
        raise ValueError("找不到工作表")
    df = item["frames"].get(sheet_name)
    if df is None or df.empty:
        raise ValueError("该表无数据")

    combined = pd.Series(False, index=df.index)
    for target in targets:
        db_id = target.get("db_id")
        row_id_value = target.get("row_id")
        if db_id is not None:
            if "__db_id" not in df.columns:
                continue
            combined |= pd.to_numeric(df["__db_id"], errors="coerce") == int(db_id)
        elif row_id_value is not None:
            combined |= _row_mask(df, row_id_key, row_id_value)
    if not combined.any():
        raise ValueError("找不到要删除的行")

    new_df = df.loc[~combined].reset_index(drop=True)
    new_df = drop_junk_rows(new_df, row_id_key)
    item["frames"][sheet_name] = new_df
    sheet["row_count"] = int(len(new_df))
    sheet["empty"] = len(new_df) == 0
    _refresh_options(spec, sheet, new_df, item["frames"])
    return int(len(new_df))


def _refresh_options(spec: dict[str, Any], sheet: dict[str, Any], df: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> None:
    form = sheet.get("form") or {}
    formula_by_name = {c["name"]: c for c in (sheet.get("formula") or {}).get("columns") or []}
    for field in form.get("fields") or []:
        col = next((c for c in sheet["columns"] if c["key"] == field["key"]), None)
        if not col:
            continue
        field["options"] = _options_for(col, df, spec, frames, formula_by_name)
    for flt in sheet.get("filters") or []:
        if flt.get("type") == "enum" and flt.get("field") in df.columns:
            flt["options"] = (
                df[flt["field"]].dropna().astype(str).value_counts().head(30).index.tolist()
            )


def mark_imported(frames: dict[str, pd.DataFrame]) -> None:
    for name, df in list(frames.items()):
        if df is None:
            continue
        if "__source" not in df.columns:
            copy = df.copy()
            copy["__source"] = "imported"
            frames[name] = copy


def _safe_sheet_title(name: str, used: set[str]) -> str:
    # Excel sheet 名最长 31 字符；保留可读性，仅去掉首尾空白
    base = (name.strip() or "明细")[:31]
    title = base
    n = 1
    while title in used:
        suffix = f"_{n}"
        title = f"{base[: 31 - len(suffix)]}{suffix}"
        n += 1
    used.add(title)
    return title


def merged_export_sheet_names(spec: dict, frames: dict) -> list[str]:
    """「导出合并表」：主表 + 抽检宽表 + 趋势 + 代码表（与 Excel 原稿结构一致）。"""
    from .sheet_util import resolve_sheet_name

    names: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if not name:
            return
        resolved = resolve_sheet_name(name, spec, frames)
        if not resolved or resolved in seen or resolved not in frames:
            return
        df = frames[resolved]
        if df is None or len(df) == 0:
            return
        names.append(resolved)
        seen.add(resolved)

    design = spec.get("dashboard_design") or {}
    add((design.get("main_table") or {}).get("sheet"))

    for sh in spec.get("sheets") or []:
        sn = sh.get("name") or ""
        if not sn:
            continue
        if sh.get("state") == "hidden":
            continue
        if sn.strip().startswith("Sheet") and sn.strip()[5:].isdigit():
            continue
        kind = sh.get("kind") or ""
        # 跳过展开长表（导出宽表「抽检数据」即可）
        if "展开" in sn:
            continue
        if kind == "lookup" or "抽检" in sn or kind == "dashboard" or "趋势" in sn:
            add(sn)

    if not names:
        for sn, df in frames.items():
            if df is not None and len(df) > 0 and "展开" not in sn:
                add(sn)
    return names


def _sheet_spec_for(spec: dict | None, sheet_name: str) -> dict | None:
    if not spec:
        return None
    for sh in spec.get("sheets") or []:
        if sh.get("name") == sheet_name:
            return sh
        if (sh.get("name") or "").strip() == (sheet_name or "").strip():
            return sh
    return None


def _format_export_cell(v: Any) -> Any:
    if v is None:
        return "－"
    if isinstance(v, float) and pd.isna(v):
        return "－"
    if isinstance(v, str):
        s = v.strip()
        if s in ("", "-", "－", "/"):
            return "－"
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        fv = float(v)
        if fv == int(fv):
            return int(fv)
        return v
    return v


def _format_inspection_status(v: Any) -> Any:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "－"
    if isinstance(v, str):
        s = v.strip()
        if s in ("", "-", "－"):
            return "－"
        # ISO date → 7月18日
        if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
            try:
                dt = pd.to_datetime(s, errors="coerce")
                if not pd.isna(dt):
                    return f"{int(dt.month)}月{int(dt.day)}日"
            except Exception:
                pass
        return s
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        from .parser import _excel_serial_to_date

        d = _excel_serial_to_date(float(v))
        if d:
            return f"{d.month}月{d.day}日"
    return _format_export_cell(v)


def normalize_inspection_status_column(df: pd.DataFrame) -> pd.DataFrame:
    """抽检数据首列「抽检状况」存的是 Excel 日期序列号，统一转为 7月18日 显示格式。"""
    col = "抽检状况"
    if col not in df.columns or df.empty:
        return df
    out = df.copy()
    out[col] = out[col].apply(_format_inspection_status)
    return out


def prepare_sheet_for_export(df: pd.DataFrame, sheet_spec: dict | None) -> tuple[pd.DataFrame, list[tuple[int, int]]]:
    out = df.drop(columns=[c for c in df.columns if str(c).startswith("__")], errors="ignore").copy()
    merge_ranges: list[tuple[int, int]] = []

    if sheet_spec and sheet_spec.get("columns"):
        ordered = [c["key"] for c in sheet_spec["columns"] if c.get("key") in out.columns]
        tail = [c for c in out.columns if c not in ordered]
        out = out[ordered + tail]

    is_lookup = bool(sheet_spec and sheet_spec.get("kind") == "lookup")
    first_col = out.columns[0] if len(out.columns) else None

    if is_lookup and first_col is not None:
        out, merge_ranges = _prepare_lookup_category_export(out)

    for col in out.columns:
        if is_lookup and col == first_col:
            continue
        if col == "抽检状况":
            out[col] = out[col].apply(_format_inspection_status)
        else:
            out[col] = out[col].apply(_format_export_cell)

    return out, merge_ranges


def _cell_is_blank(v: Any) -> bool:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return True
    return str(v).strip() in ("", "-", "－", "/")


def _prepare_lookup_category_export(out: pd.DataFrame) -> tuple[pd.DataFrame, list[tuple[int, int]]]:
    """对照表（如类别定义）：同类别首列合并，与 Excel 原稿一致。"""
    if out.empty:
        return out, []
    cat_col = out.columns[0]
    work = out.copy()
    col_name = str(cat_col).strip()
    # 解析器偶发把第一组「类别」名误写入列名（如 状态标识类），下方行首列为空
    seed = (
        col_name
        if col_name
        and col_name not in ("类别", "类 别", "类   别", "分 类", "分类")
        and not col_name.startswith("列")
        else None
    )
    effective: list[str | None] = []
    current: str | None = seed
    for v in work[cat_col]:
        if not _cell_is_blank(v):
            current = str(v).strip()
        effective.append(current)

    merge_ranges: list[tuple[int, int]] = []
    group_start = 0
    for i in range(1, len(effective) + 1):
        if i == len(effective) or effective[i] != effective[group_start]:
            if i - 1 > group_start and effective[group_start]:
                merge_ranges.append((group_start + 2, i - 1 + 2))
            group_start = i

    new_vals: list[Any] = []
    prev: str | None = None
    for eff in effective:
        if eff != prev:
            new_vals.append(eff if eff else None)
            prev = eff
        else:
            new_vals.append(None)
    work[cat_col] = new_vals
    return work, merge_ranges


def export_sheet_xlsx(df: pd.DataFrame, sheet_name: str, path, spec: dict | None = None) -> None:
    export_workbook_xlsx({sheet_name: df}, [sheet_name], path, spec)


def export_workbook_xlsx(
    frames: dict[str, pd.DataFrame],
    sheet_names: list[str],
    path,
    spec: dict | None = None,
) -> None:
    used: set[str] = set()
    written = 0
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name in sheet_names:
            df = frames.get(name)
            if df is None or len(df) == 0:
                continue
            sheet_spec = _sheet_spec_for(spec, name)
            out, merge_ranges = prepare_sheet_for_export(df, sheet_spec)
            title = _safe_sheet_title(name, used)
            out.to_excel(writer, sheet_name=title, index=False)
            if merge_ranges:
                ws = writer.sheets[title]
                for start_row, end_row in merge_ranges:
                    if end_row > start_row:
                        ws.merge_cells(
                            start_row=start_row,
                            start_column=1,
                            end_row=end_row,
                            end_column=1,
                        )
            written += 1
    if written == 0:
        raise ValueError("没有可导出的数据")
