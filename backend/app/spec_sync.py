"""Keep dashboard display columns and entry forms aligned with sheet structure."""

from __future__ import annotations

from typing import Any

from .entry import build_form_spec, is_rich_text_field, _is_oqc_entry_sheet


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
    mt = design.get("main_table") or {}
    sheet_name = mt.get("sheet") or ""
    sheet = _find_sheet(spec, sheet_name)
    if not sheet:
        return

    all_cols = sheet_display_columns(sheet)
    if not all_cols:
        return

    existing = list(mt.get("display_columns") or [])
    if existing and len(existing) >= len(all_cols):
        merged = existing[:]
        for col in all_cols:
            if col not in merged:
                merged.append(col)
        mt["display_columns"] = merged
    else:
        mt["display_columns"] = all_cols
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
    "OA单号",
    "结案天数",
    "不良率",
})


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


def ensure_oqc_entry_forms(spec: dict[str, Any], frames: dict[str, Any]) -> None:
    """OQC 主表录入项随 entry 规则刷新（判定自动、判定_2 手选等）。"""
    for sheet in spec.get("sheets") or []:
        if not _is_oqc_entry_sheet(sheet):
            continue
        rebuilt = build_form_spec(spec, sheet, frames)
        if rebuilt.get("enabled"):
            sheet["form"] = rebuilt


def sync_spec(spec: dict[str, Any], frames: dict[str, Any] | None = None) -> dict[str, Any]:
    design = spec.get("dashboard_design")
    if design:
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
