"""Keep dashboard display columns and entry forms aligned with sheet structure."""

from __future__ import annotations

from typing import Any

from .entry import build_form_spec, is_rich_text_field, _is_oqc_entry_sheet
from .module_blueprints import (
    MODULE_KEYS,
    SAMPLING_HIDDEN_DISPLAY_COLUMNS,
    apply_module_blueprint,
    attach_module_to_spec,
    curated_display_columns,
)


def _find_sheet(spec: dict[str, Any], sheet_name: str) -> dict[str, Any] | None:
    target = (sheet_name or "").strip()
    if not target:
        return None
    for sheet in spec.get("sheets") or []:
        if sheet.get("name", "").strip() == target:
            return sheet
    return None


def sheet_display_columns(sheet: dict[str, Any]) -> list[str]:
    cols: list[str] = []
    for col in sheet.get("columns") or []:
        key = col.get("key") or ""
        if not key or key.startswith("__"):
            continue
        if col.get("role") == "empty" and not str(key).startswith("列"):
            # header-only sheets may mark roles as empty; still show named columns
            pass
        elif col.get("role") == "empty":
            continue
        cols.append(key)
    return cols


def ensure_main_table_columns(design: dict[str, Any], spec: dict[str, Any]) -> None:
    """Keep display columns curated — do not expand to full Excel sheet width.

    Known homepage modules use blueprint column lists. Generic AI designs keep
    a reasonable curated list (or cap at ~20) instead of mirroring every column.
    """
    mt = design.get("main_table") or {}
    sheet_name = mt.get("sheet") or ""
    sheet = _find_sheet(spec, sheet_name)
    if not sheet:
        return

    all_cols = sheet_display_columns(sheet)
    if not all_cols:
        return

    present = set(all_cols)
    module_key = (
        design.get("module_key")
        or spec.get("module_key")
        or (design.get("business_understanding") or {}).get("module_key")
    )
    existing = [c for c in (mt.get("display_columns") or []) if c in present]

    hidden = (
        SAMPLING_HIDDEN_DISPLAY_COLUMNS
        if module_key == "sampling"
        else frozenset()
    )

    curated = curated_display_columns(sheet, module_key if module_key in MODULE_KEYS else None)
    if curated:
        extras = [c for c in existing if c not in curated and c not in hidden][:5]
        mt["display_columns"] = [c for c in (curated + extras) if c not in hidden]
        mt["columns_source"] = "module_blueprint"
    elif existing:
        # Preserve AI/user curated list; only drop missing columns
        # Cap runaway lists that look like full-sheet mirrors
        cleaned = [c for c in existing if c not in hidden]
        if len(cleaned) > 24 and len(cleaned) >= len(all_cols) * 0.85:
            mt["display_columns"] = cleaned[:18]
            mt["columns_source"] = "capped"
        else:
            mt["display_columns"] = cleaned
            mt.setdefault("columns_source", "curated")
    else:
        # No prior list: show a compact default, not every column
        preferred = [
            c for c in all_cols if not str(c).startswith("列") and c not in hidden
        ][:18]
        mt["display_columns"] = preferred or [c for c in all_cols[:18] if c not in hidden]
        mt["columns_source"] = "default_compact"

    design["main_table"] = mt


def ensure_dashboard_filters(design: dict[str, Any], spec: dict[str, Any]) -> None:
    mt = design.get("main_table") or {}
    sheet = _find_sheet(spec, mt.get("sheet") or "")
    if not sheet:
        return

    sheet_filters = sheet.get("filters") or []
    by_field = {f.get("field"): f for f in sheet_filters if f.get("field")}

    filters = list(design.get("filters") or [])
    if not filters and sheet_filters:
        design["filters"] = [dict(f) for f in sheet_filters]
        return

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for flt in filters:
        field = flt.get("field")
        if not field:
            continue
        seen.add(field)
        src = by_field.get(field) or {}
        item = dict(flt)
        if not item.get("label"):
            item["label"] = src.get("label") or field
        if not item.get("type"):
            item["type"] = src.get("type") or "enum"
        if not item.get("options") and src.get("options"):
            item["options"] = list(src["options"])
        if item.get("type") == "date_range":
            if not item.get("min") and src.get("min"):
                item["min"] = src["min"]
            if not item.get("max") and src.get("max"):
                item["max"] = src["max"]
        merged.append(item)

    # Append useful sheet filters missing from AI design (e.g. 是否结案, 月份)
    for field, src in by_field.items():
        if field in seen:
            continue
        merged.append(dict(src))

    design["filters"] = merged


DEFAULT_FILTER_EXCLUDED = frozenset({"序号", "月份", "问题点描述"})

COMPLAINT_FILTER_EXCLUDED = frozenset({
    "投诉内容",
    "不良率",
    "暂定对策",
    "结案日期",
    "结案天数",
    "不良原因",
    "改善对策(恒久对策）",
    "内部未结案待跟进事项",
    "延期天数",
})

OQC_FILTER_EXCLUDED = frozenset({
    "送检数量",
    "机能抽检数量",
    "外观抽检数量",
    "不良数量",
    "数量",
    "同批送检次数",
    "间断送检次数",
    "层别备注",
    "是否紧急出货",
    "不良代码",
    "单据类型",
    "判定_2",
    "不良率",
    # 长文本闭环列不适合做筛选项（仍在列表展示）
    "临时对策",
    "根因分析",
    "永久对策",
    "改善后确认",
})

# 抽检主表补齐业务字段（旧项目同步时注入）
OQC_ENSURE_COLUMNS: tuple[dict[str, Any], ...] = (
    {
        "key": "不良属性",
        "label": "不良属性",
        "role": "dimension",
        "type": "string",
        "insert_before": "不良位置",
    },
    {
        "key": "检验员",
        "label": "检验员",
        "role": "dimension",
        "type": "string",
        "insert_before": "同批送检次数",
    },
    {
        "key": "OA单号",
        "label": "OA单号",
        "role": "text",
        "type": "string",
        "insert_before": "责任单位",
    },
    {
        "key": "指定质控公司",
        "label": "指定质控公司",
        "role": "dimension",
        "type": "string",
        "insert_before": "责任单位",
    },
    {
        "key": "临时对策",
        "label": "临时对策",
        "role": "text",
        "type": "string",
        "insert_before": "责任单位",
    },
    {
        "key": "根因分析",
        "label": "根因分析",
        "role": "text",
        "type": "string",
        "insert_before": "责任单位",
    },
    {
        "key": "永久对策",
        "label": "永久对策",
        "role": "text",
        "type": "string",
        "insert_before": "责任单位",
    },
    {
        "key": "改善后确认",
        "label": "改善后确认",
        "role": "text",
        "type": "string",
        "insert_before": "责任单位",
    },
    {
        "key": "责任人",
        "label": "责任人",
        "role": "dimension",
        "type": "string",
        "insert_before": "责任课级负责人",
    },
    {
        "key": "结案日期",
        "label": "结案日期",
        "role": "date",
        "type": "date",
        "insert_before": "结案天数",
    },
    {
        "key": "结案天数",
        "label": "结案天数",
        "role": "measure",
        "type": "number",
    },
)


def _is_complaint_sheet(sheet: dict[str, Any] | None, design: dict[str, Any]) -> bool:
    name = (sheet.get("name") if sheet else "") or ""
    entity = ((design.get("business_understanding") or {}).get("main_entity") or "")
    return "客诉" in name or "客诉" in entity


def _is_oqc_sheet(sheet: dict[str, Any] | None, design: dict[str, Any]) -> bool:
    name = (sheet.get("name") if sheet else "") or ""
    entity = ((design.get("business_understanding") or {}).get("main_entity") or "")
    return "OQC" in name or "抽检批次" in name or "OQC" in entity or "抽检批次" in entity


def ensure_filter_exclusions(design: dict[str, Any], spec: dict[str, Any]) -> None:
    mt = design.get("main_table") or {}
    sheet = _find_sheet(spec, mt.get("sheet") or "")
    if not sheet:
        return

    excluded = set(DEFAULT_FILTER_EXCLUDED)
    if _is_complaint_sheet(sheet, design):
        excluded |= COMPLAINT_FILTER_EXCLUDED
    if _is_oqc_sheet(sheet, design):
        excluded |= OQC_FILTER_EXCLUDED

    for col in mt.get("display_columns") or []:
        if (col or "").startswith("结案后稽核事项"):
            excluded.add(col)

    mt["filter_excluded_columns"] = sorted(excluded)
    design["main_table"] = mt


def _is_year_month_field(field: dict[str, Any]) -> bool:
    key = field.get("key") or ""
    return key == "月份" or field.get("semantic") == "month"


def ensure_month_form_fields(spec: dict[str, Any]) -> None:
    for sheet in spec.get("sheets") or []:
        form = sheet.get("form") or {}
        if not form.get("enabled"):
            continue
        for field in form.get("fields") or []:
            if _is_year_month_field(field):
                field["widget"] = "month"
                field["allow_custom"] = True
            if field.get("key") == "是否紧急出货":
                field["widget"] = "select"
                field["options"] = ["是", "否"]
                field["allow_custom"] = False


def ensure_rich_text_form(spec: dict[str, Any], frames: dict[str, Any] | None = None) -> None:
    if not frames:
        return

    for sheet in spec.get("sheets") or []:
        form = sheet.get("form") or {}
        if not form.get("enabled"):
            continue

        field_keys = {f.get("key") for f in form.get("fields") or []}
        missing_rich = [
            col.get("key")
            for col in sheet.get("columns") or []
            if is_rich_text_field(col.get("key") or "") and col.get("key") not in field_keys
        ]
        if missing_rich:
            rebuilt = build_form_spec(spec, sheet, frames)
            if rebuilt.get("enabled"):
                sheet["form"] = rebuilt
            continue

        for field in form.get("fields") or []:
            if is_rich_text_field(field.get("key") or ""):
                field["widget"] = "rich_text"


def ensure_form_fields(spec: dict[str, Any], frames: dict[str, Any] | None = None) -> None:
    """Rebuild entry forms when fields are missing compared to sheet columns."""
    if not frames:
        return

    for sheet in spec.get("sheets") or []:
        if sheet.get("derived"):
            continue
        cols = [
            c["key"]
            for c in sheet.get("columns") or []
            if c.get("key") and not c["key"].startswith("__")
        ]
        if len(cols) < 2:
            continue

        form = sheet.get("form") or {}
        covered = {f["key"] for f in form.get("fields") or []} | {f["key"] for f in form.get("computed") or []}
        missing = [k for k in cols if k not in covered and not str(k).startswith("列")]
        if not missing:
            continue

        rebuilt = build_form_spec(spec, sheet, frames)
        if rebuilt.get("enabled") and len(rebuilt.get("fields") or []) >= len(form.get("fields") or []):
            sheet["form"] = rebuilt


def _insert_column_meta(sheet: dict[str, Any], col_meta: dict[str, Any]) -> bool:
    """Insert a column definition if missing. Returns True when newly added."""
    key = col_meta["key"]
    columns = list(sheet.get("columns") or [])
    if any((c.get("key") or "") == key for c in columns):
        # Keep role usable for forms even if Excel marked it empty
        for c in columns:
            if (c.get("key") or "") == key and c.get("role") in {None, "", "empty"}:
                c["role"] = col_meta.get("role") or "dimension"
                c.setdefault("type", col_meta.get("type") or "string")
                c.setdefault("label", col_meta.get("label") or key)
                sheet["columns"] = columns
                return True
        return False

    item = {
        "key": key,
        "label": col_meta.get("label") or key,
        "role": col_meta.get("role") or "dimension",
        "type": col_meta.get("type") or "string",
    }
    before = col_meta.get("insert_before")
    idx = next((i for i, c in enumerate(columns) if (c.get("key") or "") == before), -1)
    if idx >= 0:
        columns.insert(idx, item)
    else:
        columns.append(item)
    sheet["columns"] = columns
    return True


def ensure_oqc_schema(spec: dict[str, Any], frames: dict[str, Any] | None = None) -> None:
    """Inject 不良属性等抽检字段，并保证 dataframe 有对应列。"""
    for sheet in spec.get("sheets") or []:
        if not _is_oqc_entry_sheet(sheet):
            continue
        for meta in OQC_ENSURE_COLUMNS:
            _insert_column_meta(sheet, meta)

        if not frames:
            continue
        name = sheet.get("name") or ""
        df = frames.get(name)
        if df is None:
            continue
        changed = False
        for meta in OQC_ENSURE_COLUMNS:
            key = meta["key"]
            if key not in df.columns:
                df = df.copy()
                df[key] = None
                changed = True
        if changed:
            frames[name] = df


def ensure_oqc_entry_forms(spec: dict[str, Any], frames: dict[str, Any]) -> None:
    """OQC 主表录入项随 entry 规则刷新（判定自动、判定_2 手选等）。"""
    for sheet in spec.get("sheets") or []:
        if not _is_oqc_entry_sheet(sheet):
            continue
        rebuilt = build_form_spec(spec, sheet, frames)
        if rebuilt.get("enabled"):
            sheet["form"] = rebuilt


def sync_spec(spec: dict[str, Any], frames: dict[str, Any] | None = None) -> dict[str, Any]:
    # Backfill module alignment for older projects that lack module_key
    if not spec.get("module_key"):
        attach_module_to_spec(spec, filename=spec.get("filename"))

    ensure_oqc_schema(spec, frames)

    design = spec.get("dashboard_design")
    if design:
        module_key = design.get("module_key") or spec.get("module_key")
        design = apply_module_blueprint(design, spec, module_key)
        spec["dashboard_design"] = design
        ensure_main_table_columns(design, spec)
        ensure_dashboard_filters(design, spec)
        ensure_filter_exclusions(design, spec)
    ensure_month_form_fields(spec)
    if frames:
        ensure_form_fields(spec, frames)
        ensure_rich_text_form(spec, frames)
        ensure_oqc_entry_forms(spec, frames)
        ensure_month_form_fields(spec)
    return spec
