"""OQC / 变焦抽检 代码表：不良代码、机种关联、课室负责人，联动主表 VLOOKUP 列。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .entry import build_form_spec
from .logutil import log
from .spec_sync import sync_spec


def _is_blank(v: Any) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return not s or s.lower() in {"nan", "none", "nat"}


def _row_no(row: pd.Series) -> int | None:
    """Extract row id from NO./序号, never return NaN."""
    for key in ("NO.", "序号"):
        if key not in row.index:
            continue
        val = row.get(key)
        if _is_blank(val):
            continue
        try:
            n = float(val)
            if pd.isna(n):
                continue
            return int(n) if n == int(n) else int(n)
        except (TypeError, ValueError):
            continue
    return None


def _no_sort_key(no: int | None) -> float:
    return float(no) if no is not None else 9999.0


def _sanitize_json(value: Any) -> Any:
    """Replace NaN/Inf with null so FastAPI can serialize OQC payloads."""
    if isinstance(value, dict):
        return {k: _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(v) for v in value]
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (float,)):
        if pd.isna(value) or value in {float("inf"), float("-inf")}:
            return None
        return value
    try:
        import numpy as np

        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            f = float(value)
            if pd.isna(f) or f in {float("inf"), float("-inf")}:
                return None
            return f
    except ImportError:
        pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def is_oqc_code_df(code_df: pd.DataFrame | None) -> bool:
    if code_df is None or code_df.empty:
        return False
    keys = set(code_df.columns)
    return "代码" in keys and "不良描述" in keys and "大类" in keys


def _pair_lookup(code_df: pd.DataFrame, left: str, right: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if code_df is None or code_df.empty:
        return out
    for _, row in code_df.iterrows():
        a = str(row.get(left) or "").strip()
        b = str(row.get(right) or "").strip()
        if a and b:
            out[a] = b
    return out


def list_defects(code_df: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if code_df is None or code_df.empty:
        return items
    for _, row in code_df.iterrows():
        code = row.get("代码")
        if _is_blank(code):
            continue
        key = str(code).strip()
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "no": _row_no(row),
                "code": key,
                "desc": str(row.get("不良描述") or "").strip(),
                "category": str(row.get("大类") or "").strip(),
            }
        )
    items.sort(key=lambda x: (_no_sort_key(x["no"]), x["code"]))
    return items


def list_model_sections(code_df: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if code_df is None or code_df.empty:
        return items
    for _, row in code_df.iterrows():
        model = row.get("机种")
        section = row.get("课室")
        if _is_blank(model) or _is_blank(section):
            continue
        key = str(model).strip()
        if key in seen:
            continue
        seen.add(key)
        items.append({"model": key, "section": str(section).strip(), "no": _row_no(row)})
    items.sort(key=lambda x: x["model"])
    return items


def list_model_owners(code_df: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if code_df is None or code_df.empty:
        return items
    for _, row in code_df.iterrows():
        model = row.get("机种_2") or row.get("机种")
        owner = row.get("负责人")
        if _is_blank(model) or _is_blank(owner):
            continue
        key = str(model).strip()
        if key in seen:
            continue
        seen.add(key)
        items.append({"model": key, "owner": str(owner).strip(), "no": _row_no(row)})
    items.sort(key=lambda x: x["model"])
    return items


def list_section_heads(code_df: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if code_df is None or code_df.empty:
        return items
    for _, row in code_df.iterrows():
        head = row.get("课室负责人")
        if _is_blank(head):
            continue
        section = row.get("课室_2")
        if _is_blank(section):
            section = row.get("课室")
            if not _is_blank(row.get("机种")):
                continue
        if _is_blank(section):
            continue
        key = str(section).strip()
        if key in seen:
            continue
        seen.add(key)
        items.append({"section": key, "head": str(head).strip(), "no": _row_no(row)})
    items.sort(key=lambda x: x["section"])
    return items


def defect_category_options(code_df: pd.DataFrame) -> list[str]:
    cats: set[str] = set()
    if code_df is not None and not code_df.empty and "大类" in code_df.columns:
        for val in code_df["大类"]:
            if not _is_blank(val):
                cats.add(str(val).strip())
    return sorted(cats, key=lambda x: x)


def build_oqc_lookups(code_df: pd.DataFrame) -> dict[str, Any]:
    return {
        "series_sections": _pair_lookup(code_df, "机种", "课室"),
        "series_confirmers": _pair_lookup(code_df, "机种_2", "负责人"),
        "section_heads": {h["section"]: h["head"] for h in list_section_heads(code_df)},
        "defect_phenomena": _pair_lookup(code_df, "代码", "不良描述"),
        "defect_category_by_code": {
            d["code"]: d["category"] for d in list_defects(code_df) if d.get("category")
        },
    }


def oqc_payload(code_df: pd.DataFrame, *, code_sheet: str, main_sheet: str | None) -> dict[str, Any]:
    lookups = build_oqc_lookups(code_df)
    return _sanitize_json(
        {
            "layout": "oqc",
            "code_sheet": code_sheet,
            "main_sheet": main_sheet,
            "defects": list_defects(code_df),
            "defect_categories": defect_category_options(code_df),
            "model_sections": list_model_sections(code_df),
            "model_owners": list_model_owners(code_df),
            "section_heads": list_section_heads(code_df),
            "series_sections": lookups["series_sections"],
            "series_confirmers": lookups["series_confirmers"],
            "defect_phenomena": lookups["defect_phenomena"],
            "defect_category_by_code": lookups["defect_category_by_code"],
            "lookups": lookups,
        }
    )


def _find_oqc_main_sheet(spec: dict[str, Any]) -> str | None:
    for join in spec.get("joins") or []:
        if join.get("via") == "VLOOKUP" and join.get("to_sheet") and "代码" in str(join.get("to_sheet", "")):
            return join.get("from_sheet")
    dd = spec.get("dashboard_design") or {}
    return (dd.get("main_table") or {}).get("sheet")


def _resolve_sheet_name(spec: dict[str, Any], frames: dict[str, pd.DataFrame], name: str | None) -> str | None:
    if not name:
        return None
    target = name.strip()
    for key in frames:
        if key == name or key.strip() == target:
            return key
    for sheet in spec.get("sheets") or []:
        if (sheet.get("name") or "").strip() == target:
            return sheet.get("name")
    return None


def _find_sheet_spec(spec: dict[str, Any], sheet_name: str) -> dict[str, Any] | None:
    target = (sheet_name or "").strip()
    for sheet in spec.get("sheets") or []:
        if (sheet.get("name") or "").strip() == target:
            return sheet
    return None


def _oqc_join_rules(spec: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """(main_from, main_result, code_left, code_right)"""
    rules: list[tuple[str, str, str, str]] = []
    mapping = {
        ("系列", "送检单位"): ("机种", "课室"),
        ("系列", "确认者"): ("机种_2", "负责人"),
        ("送检单位", "课室负责人"): ("课室_2", "课室负责人"),
        ("不良代码", "现象"): ("代码", "不良描述"),
    }
    for join in spec.get("joins") or []:
        if join.get("via") != "VLOOKUP":
            continue
        pair = (join.get("from_field"), join.get("result_field"))
        if pair in mapping:
            left, right = mapping[pair]
            rules.append((pair[0], pair[1], left, right))
    return rules


def sync_oqc_rows_from_code(item: dict[str, Any]) -> dict[str, Any]:
    spec = item["spec"]
    main_sheet = _find_oqc_main_sheet(spec)
    if not main_sheet:
        return {"synced": False, "updated_rows": 0}

    main_name = _resolve_sheet_name(spec, item["frames"], main_sheet)
    code_name = _resolve_sheet_name(spec, item["frames"], "代码")
    if not main_name or not code_name:
        return {"synced": False, "updated_rows": 0}

    code_df = item["frames"].get(code_name)
    main_df = item["frames"].get(main_name)
    if main_df is None or main_df.empty:
        meta = refresh_oqc_main_options(spec, item["frames"], main_name, code_name)
        return {"synced": True, "main_sheet": main_name, "updated_rows": 0, "form": (meta or {}).get("form")}

    lookups: dict[str, dict[str, str]] = {}
    for _, result_field, left, right in _oqc_join_rules(spec):
        lookups[result_field] = _pair_lookup(code_df, left, right)

    out = main_df.copy()
    updated = 0
    for idx in out.index:
        for from_field, result_field, _, _ in _oqc_join_rules(spec):
            if from_field not in out.columns or result_field not in out.columns:
                continue
            src = str(out.at[idx, from_field] or "").strip()
            if not src:
                continue
            mp = lookups.get(result_field) or {}
            new_val = mp.get(src)
            if new_val is None:
                continue
            if str(out.at[idx, result_field] or "").strip() != new_val:
                out.at[idx, result_field] = new_val
                updated += 1

    item["frames"][main_name] = out
    meta = refresh_oqc_main_options(spec, item["frames"], main_name, code_name)
    log(f"[code_table_oqc.sync] main={main_name!r} updated_rows={updated}")
    return {
        "synced": True,
        "main_sheet": main_name,
        "updated_rows": updated,
        "form": (meta or {}).get("form"),
        "filters": (meta or {}).get("filters"),
    }


def refresh_oqc_main_options(
    spec: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    main_sheet: str,
    code_sheet: str,
) -> dict[str, Any] | None:
    main_spec = _find_sheet_spec(spec, main_sheet)
    if not main_spec:
        return None

    code_df = frames.get(code_sheet)
    lookups = build_oqc_lookups(code_df)
    series_list = sorted(lookups["series_sections"].keys())
    sections = sorted(set(lookups["series_sections"].values()))
    defect_codes = sorted(lookups["defect_phenomena"].keys())

    main_spec["form"] = build_form_spec(spec, main_spec, frames)
    for field in (main_spec.get("form") or {}).get("fields") or []:
        key = field.get("key")
        if key in ("系列", "机种"):
            field["options"] = series_list
        elif key == "送检单位":
            field["options"] = sections
        elif key == "不良代码":
            field["options"] = defect_codes

    for flt in main_spec.get("filters") or []:
        fkey = flt.get("field")
        if fkey in ("系列", "机种"):
            flt["type"] = "enum"
            flt["options"] = series_list
        elif fkey == "送检单位":
            flt["type"] = "enum"
            flt["options"] = sections
        elif fkey == "不良代码":
            flt["type"] = "enum"
            flt["options"] = defect_codes

    design = spec.get("dashboard_design") or {}
    for flt in design.get("filters") or []:
        fkey = flt.get("field")
        if fkey == "系列":
            flt["options"] = series_list
        if fkey == "送检单位":
            flt["options"] = sections

    form = main_spec.get("form") or {}
    form["lookups"] = lookups
    main_spec["form"] = form
    sync_spec(spec, frames)
    return {"form": main_spec.get("form"), "filters": main_spec.get("filters")}


def attach_oqc_lookups(spec: dict[str, Any], frames: dict[str, pd.DataFrame]) -> None:
    code_name = _resolve_sheet_name(spec, frames, "代码")
    main_sheet = _find_oqc_main_sheet(spec)
    if not code_name or not main_sheet:
        return
    main_name = _resolve_sheet_name(spec, frames, main_sheet)
    if not main_name:
        return
    code_df = frames.get(code_name)
    if not is_oqc_code_df(code_df):
        return
    refresh_oqc_main_options(spec, frames, main_name, code_name)


def _get_code_df(item: dict[str, Any], resolved: str) -> pd.DataFrame:
    df = item["frames"].get(resolved)
    if df is None:
        return pd.DataFrame()
    return df


def _ensure_columns(code_df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    out = code_df.copy() if code_df is not None else pd.DataFrame()
    for col in cols:
        if col not in out.columns:
            out[col] = None
    return out


def _next_no(code_df: pd.DataFrame) -> float:
    col = "NO." if "NO." in code_df.columns else "序号"
    if col not in code_df.columns:
        return 1.0
    series = pd.to_numeric(code_df[col], errors="coerce")
    mx = series.max()
    if pd.isna(mx):
        return float(len(code_df) + 1)
    return float(mx) + 1


def _blank_row(code_df: pd.DataFrame) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for col in code_df.columns:
        if str(col).startswith("__"):
            continue
        row[col] = None
    row["__source"] = "entered"
    return row


def _find_defect_mask(code_df: pd.DataFrame, *, code: str) -> pd.Series:
    return code_df["代码"].astype(str).str.strip() == code.strip()


def _update_all_model_field(code_df: pd.DataFrame, model: str, field: str, value: str) -> pd.DataFrame:
    out = code_df.copy()
    for col in ("机种", "机种_2"):
        if col in out.columns:
            mask = out[col].astype(str).str.strip() == model.strip()
            out.loc[mask, field] = value
    return out


def create_oqc_defect(
    item: dict[str, Any], *, code_sheet: str | None, code: str | None, desc: str | None, category: str
) -> dict[str, Any]:
    code = (code or "").strip()
    desc = (desc or "").strip()
    category = (category or "").strip()
    if not category:
        raise ValueError("大类不能为空")

    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    if not resolved:
        raise ValueError("找不到代码表")
    code_df = _ensure_columns(_get_code_df(item, resolved), "NO.", "代码", "不良描述", "大类")
    code_df = code_df.copy()

    if not code and not desc:
        for idx in code_df.index:
            cat_val = code_df.at[idx, "大类"]
            if _is_blank(cat_val) or str(cat_val).strip() != category:
                continue
            sync = sync_oqc_rows_from_code(item)
            return {
                **oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)),
                "sync": sync,
            }
        row = _blank_row(code_df)
        row["NO."] = _next_no(code_df)
        row["大类"] = category
        item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
        sync = sync_oqc_rows_from_code(item)
        return {**oqc_payload(item["frames"][resolved], code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}

    if not code or not desc:
        raise ValueError("代码和不良描述不能为空")

    if code in _pair_lookup(code_df, "代码", "不良描述"):
        raise ValueError(f"不良代码「{code}」已存在")

    slot_mask = code_df["大类"].astype(str).str.strip().eq(category) & code_df["代码"].map(_is_blank)
    if slot_mask.any():
        idx = code_df.index[slot_mask][0]
        code_df.at[idx, "代码"] = code
        code_df.at[idx, "不良描述"] = desc
        item["frames"][resolved] = code_df
    else:
        row = _blank_row(code_df)
        row["NO."] = _next_no(code_df)
        row["代码"] = code
        row["不良描述"] = desc
        row["大类"] = category
        item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(item["frames"][resolved], code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def update_oqc_defect(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    old_code: str,
    code: str,
    desc: str,
    category: str,
) -> dict[str, Any]:
    old_code = (old_code or "").strip()
    code = (code or "").strip()
    desc = (desc or "").strip()
    category = (category or "").strip()
    if not old_code or not code:
        raise ValueError("代码不能为空")

    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")

    mask = _find_defect_mask(code_df, code=old_code)
    if not mask.any():
        raise ValueError("找不到该不良代码")

    if old_code != code and code in _pair_lookup(code_df, "代码", "不良描述"):
        raise ValueError(f"不良代码「{code}」已存在")

    code_df = code_df.copy()
    idx = code_df.index[mask][0]
    code_df.at[idx, "代码"] = code
    code_df.at[idx, "不良描述"] = desc
    code_df.at[idx, "大类"] = category
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def rename_oqc_defect_category(
    item: dict[str, Any], *, code_sheet: str | None, old_category: str, category: str
) -> dict[str, Any]:
    old_category = (old_category or "").strip()
    category = (category or "").strip()
    if not old_category or not category:
        raise ValueError("大类名称不能为空")
    if old_category == category:
        raise ValueError("新大类名称与原名称相同")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _get_code_df(item, resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    mask = code_df["大类"].astype(str).str.strip() == old_category
    if not mask.any():
        raise ValueError(f"找不到大类「{old_category}」")
    code_df = code_df.copy()
    code_df.loc[mask, "大类"] = category
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def delete_oqc_defect_category(item: dict[str, Any], *, code_sheet: str | None, category: str) -> dict[str, Any]:
    category = (category or "").strip()
    if not category:
        raise ValueError("大类不能为空")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _get_code_df(item, resolved)
    main_name = _resolve_sheet_name(spec, item["frames"], _find_oqc_main_sheet(spec) or "")
    main_df = item["frames"].get(main_name) if main_name else None
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    mask = code_df["大类"].astype(str).str.strip() == category
    if not mask.any():
        raise ValueError(f"找不到大类「{category}」")
    if main_df is not None and "不良代码" in main_df.columns:
        codes = (
            code_df.loc[mask, "代码"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )
        for code in codes:
            if not code or code.lower() in {"nan", "none"}:
                continue
            used = int((main_df["不良代码"].astype(str).str.strip() == code).sum())
            if used > 0:
                raise ValueError(f"大类下代码「{code}」已被抽检明细引用 {used} 次，无法删除该大类")
    code_df = code_df.loc[~mask].reset_index(drop=True)
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def delete_oqc_defect(item: dict[str, Any], *, code_sheet: str | None, code: str) -> dict[str, Any]:
    code = (code or "").strip()
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    main_name = _resolve_sheet_name(spec, item["frames"], _find_oqc_main_sheet(spec) or "")
    main_df = item["frames"].get(main_name) if main_name else None
    if main_df is not None and "不良代码" in main_df.columns:
        used = int((main_df["不良代码"].astype(str).str.strip() == code).sum())
        if used > 0:
            raise ValueError(f"不良代码「{code}」已被抽检明细引用 {used} 次，无法删除")
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    mask = _find_defect_mask(code_df, code=code)
    if not mask.any():
        raise ValueError("找不到该不良代码")
    code_df = code_df.drop(index=code_df.index[mask][0]).reset_index(drop=True)
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def create_oqc_model_section(item: dict[str, Any], *, code_sheet: str | None, model: str | None, section: str) -> dict[str, Any]:
    model = (model or "").strip()
    section = (section or "").strip()
    if not section:
        raise ValueError("课室不能为空")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _ensure_columns(_get_code_df(item, resolved), "NO.", "机种", "课室")
    code_df = code_df.copy()

    if not model:
        for idx in code_df.index:
            sec_val = code_df.at[idx, "课室"]
            if _is_blank(sec_val):
                continue
            if str(sec_val).strip() == section:
                sync = sync_oqc_rows_from_code(item)
                return {
                    **oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)),
                    "sync": sync,
                }
        row = _blank_row(code_df)
        row["NO."] = _next_no(code_df)
        row["课室"] = section
        item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
        sync = sync_oqc_rows_from_code(item)
        return {**oqc_payload(item["frames"][resolved], code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}

    if model in _pair_lookup(code_df, "机种", "课室"):
        raise ValueError(f"机种「{model}」已存在")

    slot_mask = code_df["课室"].astype(str).str.strip().eq(section) & code_df["机种"].map(_is_blank)
    if slot_mask.any():
        idx = code_df.index[slot_mask][0]
        code_df.at[idx, "机种"] = model
        item["frames"][resolved] = code_df
    else:
        row = _blank_row(code_df)
        row["NO."] = _next_no(code_df)
        row["机种"] = model
        row["课室"] = section
        item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(item["frames"][resolved], code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def update_oqc_model_section(
    item: dict[str, Any], *, code_sheet: str | None, old_model: str, model: str, section: str
) -> dict[str, Any]:
    old_model = (old_model or "").strip()
    model = (model or "").strip()
    section = (section or "").strip()
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    lookup = _pair_lookup(code_df, "机种", "课室")
    if old_model not in lookup:
        raise ValueError("找不到该机种")
    if model != old_model and model in lookup:
        raise ValueError(f"机种「{model}」已存在")
    code_df = code_df.copy()
    mask = code_df["机种"].astype(str).str.strip() == old_model
    code_df.loc[mask, "机种"] = model
    code_df.loc[mask, "课室"] = section
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def rename_oqc_classroom_group(
    item: dict[str, Any], *, code_sheet: str | None, old_section: str, section: str
) -> dict[str, Any]:
    old_section = (old_section or "").strip()
    section = (section or "").strip()
    if not old_section or not section:
        raise ValueError("课室名称不能为空")
    if old_section == section:
        raise ValueError("新课室名称与原名称相同")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _get_code_df(item, resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    mask = code_df["课室"].astype(str).str.strip() == old_section
    if not mask.any():
        raise ValueError(f"找不到课室「{old_section}」")
    code_df = code_df.copy()
    code_df.loc[mask, "课室"] = section
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def delete_oqc_classroom_group(item: dict[str, Any], *, code_sheet: str | None, section: str) -> dict[str, Any]:
    section = (section or "").strip()
    if not section:
        raise ValueError("课室不能为空")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _get_code_df(item, resolved)
    main_name = _resolve_sheet_name(spec, item["frames"], _find_oqc_main_sheet(spec) or "")
    main_df = item["frames"].get(main_name) if main_name else None
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    mask = code_df["课室"].astype(str).str.strip() == section
    if not mask.any():
        raise ValueError(f"找不到课室「{section}」")
    if main_df is not None and "系列" in main_df.columns:
        models = (
            code_df.loc[mask, "机种"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )
        for model in models:
            if not model or model.lower() in {"nan", "none"}:
                continue
            used = int((main_df["系列"].astype(str).str.strip() == model).sum())
            if used > 0:
                raise ValueError(f"课室下机种「{model}」已被主表引用 {used} 次，无法删除该课室")
    code_df = code_df.loc[~mask].reset_index(drop=True)
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def delete_oqc_model_section(item: dict[str, Any], *, code_sheet: str | None, model: str) -> dict[str, Any]:
    model = (model or "").strip()
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    main_name = _resolve_sheet_name(spec, item["frames"], _find_oqc_main_sheet(spec) or "")
    main_df = item["frames"].get(main_name) if main_name else None
    if main_df is not None and "系列" in main_df.columns:
        used = int((main_df["系列"].astype(str).str.strip() == model).sum())
        if used > 0:
            raise ValueError(f"机种「{model}」已被主表引用 {used} 次，无法删除")
    if code_df is None:
        raise ValueError("代码表无数据")
    mask = code_df["机种"].astype(str).str.strip() == model
    if not mask.any():
        raise ValueError("找不到该机种")
    code_df = code_df.loc[~mask].reset_index(drop=True)
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def _model_owner_mask(code_df: pd.DataFrame, model: str) -> pd.Series:
    model = (model or "").strip()
    if "机种_2" in code_df.columns:
        m2 = code_df["机种_2"].astype(str).str.strip() == model
        if m2.any():
            return m2
    if "机种" in code_df.columns:
        return code_df["机种"].astype(str).str.strip() == model
    return pd.Series([False] * len(code_df), index=code_df.index)


def _model_owner_lookup(code_df: pd.DataFrame) -> dict[str, str]:
    out = _pair_lookup(code_df, "机种_2", "负责人")
    for item in list_model_owners(code_df):
        out.setdefault(item["model"], item["owner"])
    return out


def create_oqc_model_owner(item: dict[str, Any], *, code_sheet: str | None, model: str | None, owner: str) -> dict[str, Any]:
    model = (model or "").strip()
    owner = (owner or "").strip()
    if not owner:
        raise ValueError("负责人不能为空")
    if not model:
        spec = item["spec"]
        resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
        code_df = _ensure_columns(_get_code_df(item, resolved), "NO.", "机种_2", "负责人")
        code_df = code_df.copy()
        for idx in code_df.index:
            owner_val = code_df.at[idx, "负责人"]
            if _is_blank(owner_val) or str(owner_val).strip() != owner:
                continue
            if _is_blank(code_df.at[idx, "机种_2"]) and _is_blank(code_df.at[idx, "机种"]):
                sync = sync_oqc_rows_from_code(item)
                return {
                    **oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)),
                    "sync": sync,
                }
        row = _blank_row(code_df)
        row["NO."] = _next_no(code_df)
        row["负责人"] = owner
        item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
        sync = sync_oqc_rows_from_code(item)
        return {**oqc_payload(item["frames"][resolved], code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _ensure_columns(_get_code_df(item, resolved), "NO.", "机种", "机种_2", "负责人")
    if model in _model_owner_lookup(code_df):
        raise ValueError(f"机种「{model}」已存在")
    code_df = code_df.copy()
    slot_mask = code_df["负责人"].astype(str).str.strip().eq(owner) & code_df["机种_2"].map(_is_blank) & code_df["机种"].map(_is_blank)
    if slot_mask.any():
        idx = code_df.index[slot_mask][0]
        code_df.at[idx, "机种_2"] = model
        code_df.at[idx, "机种"] = model
    else:
        mask = _model_owner_mask(code_df, model)
        if mask.any():
            idx = code_df.index[mask][0]
            code_df.at[idx, "机种_2"] = model
            code_df.at[idx, "负责人"] = owner
        else:
            row = _blank_row(code_df)
            row["NO."] = _next_no(code_df)
            row["机种_2"] = model
            row["负责人"] = owner
            code_df = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def update_oqc_model_owner(
    item: dict[str, Any], *, code_sheet: str | None, old_model: str, model: str, owner: str
) -> dict[str, Any]:
    old_model = (old_model or "").strip()
    model = (model or "").strip()
    owner = (owner or "").strip()
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    lookup = _model_owner_lookup(code_df)
    if old_model not in lookup:
        raise ValueError("找不到该机种")
    if model != old_model and model in lookup:
        raise ValueError(f"机种「{model}」已存在")
    code_df = code_df.copy()
    mask = _model_owner_mask(code_df, old_model)
    if not mask.any():
        raise ValueError("找不到该机种")
    code_df.loc[mask, "机种_2"] = model
    code_df.loc[mask, "负责人"] = owner
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def _rename_oqc_person_in_code_df(code_df: pd.DataFrame, old_owner: str, new_owner: str) -> dict[str, int]:
    """第三页「负责人」与第四页「课室负责人」同人名时一并替换（就地修改 code_df）。"""
    for col in ("NO.", "机种", "机种_2", "负责人", "课室_2", "课室负责人"):
        if col not in code_df.columns:
            code_df[col] = None
    model_mask = code_df["负责人"].astype(str).str.strip() == old_owner
    head_mask = code_df["课室负责人"].astype(str).str.strip() == old_owner
    model_n = int(model_mask.sum())
    head_n = int(head_mask.sum())
    if model_n:
        code_df.loc[model_mask, "负责人"] = new_owner
    if head_n:
        code_df.loc[head_mask, "课室负责人"] = new_owner
    return {"model_owner_rows": model_n, "section_head_rows": head_n}


def bulk_rename_oqc_model_owners(
    item: dict[str, Any], *, code_sheet: str | None, old_owner: str, new_owner: str
) -> dict[str, Any]:
    old_owner = (old_owner or "").strip()
    new_owner = (new_owner or "").strip()
    if not old_owner or not new_owner:
        raise ValueError("原负责人和新负责人不能为空")
    if old_owner == new_owner:
        raise ValueError("新负责人与原负责人相同，无需更换")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _get_code_df(item, resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    code_df = code_df.copy()
    counts = _rename_oqc_person_in_code_df(code_df, old_owner, new_owner)
    if counts["model_owner_rows"] + counts["section_head_rows"] <= 0:
        raise ValueError(f"未找到负责人/课室负责人为「{old_owner}」的记录")
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    payload = oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec))
    payload["bulk_rename"] = {
        "old_owner": old_owner,
        "new_owner": new_owner,
        "updated_rows": counts["model_owner_rows"],
        "updated_section_heads": counts["section_head_rows"],
    }
    return {**payload, "sync": sync}


def delete_oqc_model_owner(item: dict[str, Any], *, code_sheet: str | None, model: str) -> dict[str, Any]:
    model = (model or "").strip()
    if not model:
        raise ValueError("机种不能为空")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    if model not in _model_owner_lookup(code_df):
        raise ValueError("找不到该机种")
    code_df = code_df.copy()
    mask = _model_owner_mask(code_df, model)
    if not mask.any():
        raise ValueError("找不到该机种")
    code_df.loc[mask, "负责人"] = None
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def create_oqc_section_head(
    item: dict[str, Any], *, code_sheet: str | None, section: str | None, head: str
) -> dict[str, Any]:
    section = (section or "").strip()
    head = (head or "").strip()
    if not head:
        raise ValueError("课室负责人不能为空")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _ensure_columns(_get_code_df(item, resolved), "NO.", "课室_2", "课室负责人")
    if not section:
        code_df = code_df.copy()
        for idx in code_df.index:
            head_val = code_df.at[idx, "课室负责人"]
            if _is_blank(head_val) or str(head_val).strip() != head:
                continue
            if _is_blank(code_df.at[idx, "课室_2"]):
                sync = sync_oqc_rows_from_code(item)
                return {
                    **oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)),
                    "sync": sync,
                }
        row = _blank_row(code_df)
        row["NO."] = _next_no(code_df)
        row["课室负责人"] = head
        item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
        sync = sync_oqc_rows_from_code(item)
        return {**oqc_payload(item["frames"][resolved], code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}

    if section in _pair_lookup(code_df, "课室_2", "课室负责人"):
        raise ValueError(f"课室「{section}」已存在")
    code_df = code_df.copy()
    slot_mask = code_df["课室负责人"].astype(str).str.strip().eq(head) & code_df["课室_2"].map(_is_blank)
    if slot_mask.any():
        idx = code_df.index[slot_mask][0]
        code_df.at[idx, "课室_2"] = section
    else:
        row = _blank_row(code_df)
        row["NO."] = _next_no(code_df)
        row["课室_2"] = section
        row["课室负责人"] = head
        code_df = pd.concat([code_df, pd.DataFrame([row])], ignore_index=True)
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def update_oqc_section_head(
    item: dict[str, Any], *, code_sheet: str | None, old_section: str, section: str, head: str
) -> dict[str, Any]:
    old_section = (old_section or "").strip()
    section = (section or "").strip()
    head = (head or "").strip()
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    lookup = _pair_lookup(code_df, "课室_2", "课室负责人")
    if old_section not in lookup:
        raise ValueError("找不到该课室")
    if section != old_section and section in lookup:
        raise ValueError(f"课室「{section}」已存在")
    code_df = code_df.copy()
    mask = code_df["课室_2"].astype(str).str.strip() == old_section
    code_df.loc[mask, "课室_2"] = section
    code_df.loc[mask, "课室负责人"] = head
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def rename_oqc_section_head_group(
    item: dict[str, Any], *, code_sheet: str | None, old_head: str, head: str
) -> dict[str, Any]:
    old_head = (old_head or "").strip()
    head = (head or "").strip()
    if not old_head or not head:
        raise ValueError("课室负责人不能为空")
    if old_head == head:
        raise ValueError("新负责人名称与原名称相同")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _get_code_df(item, resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    mask = code_df["课室负责人"].astype(str).str.strip() == old_head
    if not mask.any():
        raise ValueError(f"找不到课室负责人「{old_head}」")
    code_df = code_df.copy()
    code_df.loc[mask, "课室负责人"] = head
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def delete_oqc_section_head_group(item: dict[str, Any], *, code_sheet: str | None, head: str) -> dict[str, Any]:
    head = (head or "").strip()
    if not head:
        raise ValueError("课室负责人不能为空")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = _get_code_df(item, resolved)
    main_name = _resolve_sheet_name(spec, item["frames"], _find_oqc_main_sheet(spec) or "")
    main_df = item["frames"].get(main_name) if main_name else None
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    mask = code_df["课室负责人"].astype(str).str.strip() == head
    if not mask.any():
        raise ValueError(f"找不到课室负责人「{head}」")
    if main_df is not None and "送检单位" in main_df.columns:
        sections = (
            code_df.loc[mask, "课室_2"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )
        for sec in sections:
            if not sec or sec.lower() in {"nan", "none"}:
                continue
            used = int((main_df["送检单位"].astype(str).str.strip() == sec).sum())
            if used > 0:
                raise ValueError(f"负责人下课室「{sec}」已被抽检明细引用 {used} 次，无法删除该负责人")
    code_df = code_df.loc[~mask].reset_index(drop=True)
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}


def delete_oqc_section_head(item: dict[str, Any], *, code_sheet: str | None, section: str) -> dict[str, Any]:
    section = (section or "").strip()
    if not section:
        raise ValueError("课室不能为空")
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet or "代码")
    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    main_name = _resolve_sheet_name(spec, item["frames"], _find_oqc_main_sheet(spec) or "")
    main_df = item["frames"].get(main_name) if main_name else None
    if main_df is not None and "送检单位" in main_df.columns:
        used = int((main_df["送检单位"].astype(str).str.strip() == section).sum())
        if used > 0:
            raise ValueError(f"课室「{section}」已被抽检明细引用 {used} 次，无法删除")
    lookup = {h["section"]: h["head"] for h in list_section_heads(code_df)}
    if section not in lookup:
        raise ValueError("找不到该课室")
    code_df = code_df.copy()
    mask = code_df["课室_2"].astype(str).str.strip() == section
    if not mask.any():
        raise ValueError("找不到该课室")
    code_df.loc[mask, "课室负责人"] = None
    item["frames"][resolved] = code_df
    sync = sync_oqc_rows_from_code(item)
    return {**oqc_payload(code_df, code_sheet=resolved, main_sheet=_find_oqc_main_sheet(spec)), "sync": sync}
