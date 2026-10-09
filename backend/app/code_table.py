"""CRUD for inspection code-table 分类/类别、模块/负责人 with linkage to 问题清单."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .entry import _next_id, build_form_spec, drop_junk_rows
from .logutil import log
from .spec_sync import sync_spec
from . import code_table_oqc


def _is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    s = str(v).strip()
    return not s or s.lower() in {"nan", "none", "nat"}


def _find_sheet_spec(spec: dict[str, Any], sheet_name: str) -> dict[str, Any] | None:
    target = (sheet_name or "").strip()
    for sheet in spec.get("sheets") or []:
        if (sheet.get("name") or "").strip() == target:
            return sheet
    return None


def _resolve_sheet_name(spec: dict[str, Any], frames: dict[str, pd.DataFrame], name: str | None) -> str | None:
    if not name:
        return None
    target = name.strip()
    for key in frames:
        if key == name or key.strip() == target:
            return key
    return _find_code_sheet(spec) if target == "代码" else None


def _find_code_sheet(spec: dict[str, Any]) -> str | None:
    for sheet in spec.get("sheets") or []:
        sn = (sheet.get("name") or "").strip()
        if sheet.get("kind") == "lookup" and ("代码" in sn or sn == "代码"):
            return sheet.get("name")
    for sheet in spec.get("sheets") or []:
        keys = {c.get("key") for c in sheet.get("columns") or []}
        if {"分类", "类别"}.issubset(keys):
            return sheet.get("name")
    return None


def _find_classification_linkage(spec: dict[str, Any]) -> tuple[str, str, str, str] | None:
    for join in spec.get("joins") or []:
        if join.get("via") != "VLOOKUP":
            continue
        cls_field = join.get("from_field")
        cat_field = join.get("result_field")
        main_sheet = join.get("from_sheet")
        code_sheet = join.get("to_sheet")
        if cls_field == "分类" and cat_field == "类别" and main_sheet and code_sheet:
            return main_sheet, cls_field, cat_field, code_sheet
    return None


def _find_module_linkage(spec: dict[str, Any]) -> tuple[str, str, str, str] | None:
    for join in spec.get("joins") or []:
        if join.get("via") != "VLOOKUP":
            continue
        mod_field = join.get("from_field")
        owner_field = join.get("result_field")
        main_sheet = join.get("from_sheet")
        code_sheet = join.get("to_sheet")
        if mod_field == "模块" and owner_field == "工段负责人" and main_sheet and code_sheet:
            return main_sheet, mod_field, owner_field, code_sheet
    return None


def _build_classification_lookup(code_df: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if code_df is None or code_df.empty:
        return lookup
    for _, row in code_df.iterrows():
        cls = str(row.get("分类") or "").strip()
        cat = str(row.get("类别") or "").strip()
        if cls and cat:
            lookup[cls] = cat
    return lookup


def _list_items(code_df: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if code_df is None or code_df.empty:
        return items
    for _, row in code_df.iterrows():
        cls = row.get("分类")
        cat = row.get("类别")
        if _is_blank(cls) or _is_blank(cat):
            continue
        classification = str(cls).strip()
        category = str(cat).strip()
        if classification in seen:
            continue
        seen.add(classification)
        items.append(
            {
                "no": row.get("序号"),
                "classification": classification,
                "category": category,
            }
        )
    items.sort(key=lambda x: (float(x["no"]) if x["no"] is not None else 9999, x["classification"]))
    return items


def _category_options(code_df: pd.DataFrame) -> list[str]:
    cats: set[str] = set()
    if code_df is None or code_df.empty:
        return []
    for _, row in code_df.iterrows():
        cat = row.get("类别")
        if not _is_blank(cat):
            cats.add(str(cat).strip())
    return sorted(cats, key=lambda x: x)


def _build_module_lookup(code_df: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if code_df is None or code_df.empty:
        return lookup
    for _, row in code_df.iterrows():
        mod = str(row.get("模块") or "").strip()
        owner = str(row.get("负责人") or "").strip()
        if mod and owner:
            lookup[mod] = owner
    return lookup


def _owner_to_modules(code_df: pd.DataFrame) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if code_df is None or code_df.empty:
        return out
    for _, row in code_df.iterrows():
        mod = str(row.get("模块") or "").strip()
        owner = str(row.get("负责人") or "").strip()
        if not mod or not owner:
            continue
        out.setdefault(owner, [])
        if mod not in out[owner]:
            out[owner].append(mod)
    for owner in out:
        out[owner].sort(key=lambda x: x)
    return out


def _list_modules(code_df: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if code_df is None or code_df.empty:
        return items
    for _, row in code_df.iterrows():
        mod = row.get("模块")
        owner = row.get("负责人")
        if _is_blank(mod) or _is_blank(owner):
            continue
        module = str(mod).strip()
        person = str(owner).strip()
        if module in seen:
            continue
        seen.add(module)
        items.append(
            {
                "no": row.get("序号"),
                "module": module,
                "owner": person,
            }
        )
    items.sort(key=lambda x: (float(x["no"]) if x["no"] is not None else 9999, x["module"]))
    return items


def _owner_options(code_df: pd.DataFrame) -> list[str]:
    owners: set[str] = set()
    if code_df is None or code_df.empty:
        return []
    for _, row in code_df.iterrows():
        owner = row.get("负责人")
        if not _is_blank(owner):
            owners.add(str(owner).strip())
    return sorted(owners, key=lambda x: x)


def _module_options(code_df: pd.DataFrame) -> list[str]:
    mods: set[str] = set()
    if code_df is None or code_df.empty:
        return []
    for _, row in code_df.iterrows():
        mod = row.get("模块")
        if not _is_blank(mod):
            mods.add(str(mod).strip())
    return sorted(mods, key=lambda x: x)


def _find_module_row_mask(code_df: pd.DataFrame, *, no: Any = None, module: str | None = None) -> pd.Series:
    if no is not None and "序号" in code_df.columns:
        series = code_df["序号"]
        try:
            match_val = float(no)
            mask = pd.to_numeric(series, errors="coerce") == match_val
            if mask.any():
                return mask
        except (TypeError, ValueError):
            pass
        mask = series.astype(str) == str(no)
        if mask.any():
            return mask
    if module:
        return code_df["模块"].astype(str).str.strip() == module.strip()
    raise ValueError("须指定序号或模块")


def _find_code_row_mask(code_df: pd.DataFrame, *, no: Any = None, classification: str | None = None) -> pd.Series:
    if no is not None and "序号" in code_df.columns:
        series = code_df["序号"]
        try:
            match_val = float(no)
            mask = pd.to_numeric(series, errors="coerce") == match_val
            if mask.any():
                return mask
        except (TypeError, ValueError):
            pass
        mask = series.astype(str) == str(no)
        if mask.any():
            return mask
    if classification:
        return code_df["分类"].astype(str).str.strip() == classification.strip()
    raise ValueError("须指定序号或分类")


def _refresh_main_sheet_options(
    spec: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    *,
    main_sheet: str,
    code_sheet: str,
    cls_field: str | None = None,
    cat_field: str | None = None,
    mod_field: str | None = None,
    owner_field: str | None = None,
) -> dict[str, Any] | None:
    main_spec = _find_sheet_spec(spec, main_sheet)
    if not main_spec:
        return None

    code_df = frames.get(code_sheet)
    cls_lookup = _build_classification_lookup(code_df)
    classifications = sorted(cls_lookup.keys())
    categories = _category_options(code_df)
    linked_categories = sorted(set(cls_lookup.values()))
    mod_lookup = _build_module_lookup(code_df)
    modules = sorted(mod_lookup.keys())
    owners = sorted(set(mod_lookup.values()))

    main_spec["form"] = build_form_spec(spec, main_spec, frames)
    for field in (main_spec.get("form") or {}).get("fields") or []:
        key = field.get("key")
        if cls_field and key == cls_field:
            field["options"] = classifications
        if cat_field and key == cat_field:
            field["options"] = linked_categories or categories
        if mod_field and key == mod_field:
            field["options"] = modules

    for flt in main_spec.get("filters") or []:
        fkey = flt.get("field")
        if cls_field and fkey == cls_field:
            flt["type"] = "enum"
            flt["options"] = classifications
        if cat_field and fkey == cat_field:
            flt["type"] = "enum"
            flt["options"] = categories
        if mod_field and fkey == mod_field:
            flt["type"] = "enum"
            flt["options"] = modules
        if owner_field and fkey == owner_field:
            flt["type"] = "enum"
            flt["options"] = owners

    design = spec.get("dashboard_design") or {}
    for flt in design.get("filters") or []:
        fkey = flt.get("field")
        if cls_field and fkey == cls_field:
            flt["options"] = classifications
        if cat_field and fkey == cat_field:
            flt["options"] = categories
        if mod_field and fkey == mod_field:
            flt["options"] = modules
        if owner_field and fkey == owner_field:
            flt["options"] = owners

    form = main_spec.get("form") or {}
    form["lookups"] = {
        "module_owners": mod_lookup,
        "owner_modules": _owner_to_modules(code_df),
        "classification_categories": cls_lookup,
        "category_options": categories,
    }
    main_spec["form"] = form

    sync_spec(spec, frames)
    return {
        "form": main_spec.get("form"),
        "filters": main_spec.get("filters"),
    }


def attach_code_table_lookups(spec: dict[str, Any], frames: dict[str, pd.DataFrame]) -> None:
    """Ensure entry form carries code-table linkage maps (inspection or OQC)."""
    code_name = _resolve_sheet_name(spec, frames, "代码") or _find_code_sheet(spec)
    code_df = frames.get(code_name) if code_name else None
    if code_table_oqc.is_oqc_code_df(code_df):
        code_table_oqc.attach_oqc_lookups(spec, frames)
        return

    cls_link = _find_classification_linkage(spec)
    mod_link = _find_module_linkage(spec)
    if not cls_link and not mod_link:
        return

    main_sheet = cls_link[0] if cls_link else mod_link[0]
    code_sheet = cls_link[3] if cls_link else mod_link[3]
    cls_field = cls_link[1] if cls_link else None
    cat_field = cls_link[2] if cls_link else None
    mod_field = mod_link[1] if mod_link else None
    owner_field = mod_link[2] if mod_link else None

    main_name = _resolve_sheet_name(spec, frames, main_sheet)
    code_name = _resolve_sheet_name(spec, frames, code_sheet)
    if not main_name or not code_name:
        return

    _refresh_main_sheet_options(
        spec,
        frames,
        main_sheet=main_name,
        code_sheet=code_name,
        cls_field=cls_field,
        cat_field=cat_field,
        mod_field=mod_field,
        owner_field=owner_field,
    )


def _ensure_code_columns(code_df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    out = code_df.copy() if code_df is not None else pd.DataFrame()
    for col in cols:
        if col not in out.columns:
            out[col] = None
    return out


def _code_table_payload(item: dict[str, Any], resolved: str) -> dict[str, Any]:
    raw_code_df = item["frames"].get(resolved)
    raw = raw_code_df if raw_code_df is not None else pd.DataFrame()
    id_key = "NO." if "NO." in raw.columns else "序号"
    code_df = drop_junk_rows(raw, id_key=id_key)
    if code_table_oqc.is_oqc_code_df(code_df):
        main_sheet = code_table_oqc._find_oqc_main_sheet(item["spec"])
        return code_table_oqc.oqc_payload(code_df, code_sheet=resolved, main_sheet=main_sheet)

    cls_link = _find_classification_linkage(item["spec"])
    mod_link = _find_module_linkage(item["spec"])
    mod_lookup = _build_module_lookup(code_df)
    return {
        "layout": "inspection",
        "code_sheet": resolved,
        "main_sheet": (cls_link[0] if cls_link else mod_link[0] if mod_link else None),
        "items": _list_items(code_df),
        "category_options": _category_options(code_df),
        "modules": _list_modules(code_df),
        "owner_options": _owner_options(code_df),
        "module_options": _module_options(code_df),
        "module_owners": mod_lookup,
        "owner_modules": _owner_to_modules(code_df),
        "classification_categories": _build_classification_lookup(code_df),
    }


def sync_issue_rows_from_code(item: dict[str, Any]) -> dict[str, Any]:
    cls_link = _find_classification_linkage(item["spec"])
    mod_link = _find_module_linkage(item["spec"])
    if not cls_link and not mod_link:
        return {"synced": False, "updated_issue_rows": 0, "updated_module_rows": 0}

    main_sheet = cls_link[0] if cls_link else mod_link[0]
    code_sheet = cls_link[3] if cls_link else mod_link[3]
    cls_field = cls_link[1] if cls_link else None
    cat_field = cls_link[2] if cls_link else None
    mod_field = mod_link[1] if mod_link else None
    owner_field = mod_link[2] if mod_link else None

    main_name = _resolve_sheet_name(item["spec"], item["frames"], main_sheet)
    code_name = _resolve_sheet_name(item["spec"], item["frames"], code_sheet)
    if not main_name or not code_name:
        return {"synced": False, "updated_issue_rows": 0, "updated_module_rows": 0}

    cls_lookup = _build_classification_lookup(item["frames"].get(code_name))
    mod_lookup = _build_module_lookup(item["frames"].get(code_name))
    main_df = item["frames"].get(main_name)
    updated_cat = 0
    updated_mod = 0

    if main_df is not None and not main_df.empty:
        out = main_df.copy()
        for idx in out.index:
            if cls_field and cls_field in out.columns:
                cls = str(out.at[idx, cls_field] or "").strip()
                if cls and cls in cls_lookup and cat_field and cat_field in out.columns:
                    new_cat = cls_lookup[cls]
                    if str(out.at[idx, cat_field] or "").strip() != new_cat:
                        out.at[idx, cat_field] = new_cat
                        updated_cat += 1
            if mod_field and mod_field in out.columns:
                mod = str(out.at[idx, mod_field] or "").strip()
                if mod and mod in mod_lookup and owner_field and owner_field in out.columns:
                    new_owner = mod_lookup[mod]
                    if str(out.at[idx, owner_field] or "").strip() != new_owner:
                        out.at[idx, owner_field] = new_owner
                        updated_mod += 1
        item["frames"][main_name] = out

    meta = _refresh_main_sheet_options(
        item["spec"],
        item["frames"],
        main_sheet=main_name,
        code_sheet=code_name,
        cls_field=cls_field,
        cat_field=cat_field,
        mod_field=mod_field,
        owner_field=owner_field,
    )
    log(
        f"[code_table.sync] main={main_name!r} updated_category_rows={updated_cat} "
        f"updated_module_rows={updated_mod}"
    )
    return {
        "synced": True,
        "main_sheet": main_name,
        "updated_issue_rows": updated_cat + updated_mod,
        "updated_category_rows": updated_cat,
        "updated_module_rows": updated_mod,
        "form": (meta or {}).get("form"),
        "filters": (meta or {}).get("filters"),
    }


def get_code_classifications(item: dict[str, Any], code_sheet: str | None = None) -> dict[str, Any]:
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")
    return _code_table_payload(item, resolved)


def create_code_classification(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    classification: str,
    category: str,
) -> dict[str, Any]:
    classification = (classification or "").strip()
    category = (category or "").strip()
    if not classification or not category:
        raise ValueError("分类和类别不能为空")

    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")

    code_df = item["frames"].get(resolved)
    if code_df is None:
        code_df = pd.DataFrame()
        item["frames"][resolved] = code_df

    existing = _build_classification_lookup(code_df)
    if classification in existing:
        raise ValueError(f"分类「{classification}」已存在")

    for idx in code_df.index:
        row_cat = str(code_df.at[idx, "类别"] or "").strip()
        row_cls = str(code_df.at[idx, "分类"] or "").strip()
        if row_cat == category and not row_cls:
            code_df.at[idx, "分类"] = classification
            code_df.at[idx, "__source"] = "entered"
            item["frames"][resolved] = code_df
            sheet_spec = _find_sheet_spec(spec, resolved)
            if sheet_spec:
                sheet_spec["row_count"] = int(len(code_df))
                sheet_spec["empty"] = False
            sync = sync_issue_rows_from_code(item)
            return {**_code_table_payload(item, resolved), "sync": sync}

    new_row: dict[str, Any] = {}
    for col in code_df.columns:
        if str(col).startswith("__"):
            continue
        new_row[col] = None
    new_row["序号"] = _next_id(code_df, "序号")
    new_row["分类"] = classification
    new_row["类别"] = category
    new_row["__source"] = "entered"

    item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([new_row])], ignore_index=True)
    sheet_spec = _find_sheet_spec(spec, resolved)
    if sheet_spec:
        sheet_spec["row_count"] = int(len(item["frames"][resolved]))
        sheet_spec["empty"] = False

    sync = sync_issue_rows_from_code(item)
    return {**_code_table_payload(item, resolved), "sync": sync}


def create_code_category(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    category: str,
) -> dict[str, Any]:
    """Create a category (大类) placeholder row without a classification yet."""
    category = (category or "").strip()
    if not category:
        raise ValueError("类别不能为空")

    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")

    code_df = item["frames"].get(resolved)
    if code_df is None:
        code_df = pd.DataFrame()
        item["frames"][resolved] = code_df

    if category in _category_options(code_df):
        raise ValueError(f"类别「{category}」已存在")

    new_row: dict[str, Any] = {}
    for col in code_df.columns:
        if str(col).startswith("__"):
            continue
        new_row[col] = None
    new_row["序号"] = _next_id(code_df, "序号")
    new_row["类别"] = category
    new_row["分类"] = None
    new_row["__source"] = "entered"

    item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([new_row])], ignore_index=True)
    sheet_spec = _find_sheet_spec(spec, resolved)
    if sheet_spec:
        sheet_spec["row_count"] = int(len(item["frames"][resolved]))
        sheet_spec["empty"] = False

    sync: dict[str, Any] | None = None
    cls_link = _find_classification_linkage(spec)
    if cls_link:
        main_sheet, cls_field, cat_field, code_sheet = cls_link
        main_name = _resolve_sheet_name(spec, item["frames"], main_sheet)
        code_name = _resolve_sheet_name(spec, item["frames"], code_sheet)
        if main_name and code_name:
            sync = _refresh_main_sheet_options(
                spec,
                item["frames"],
                main_sheet=main_name,
                code_sheet=code_name,
                cls_field=cls_field,
                cat_field=cat_field,
            )

    return {**_code_table_payload(item, resolved), "sync": sync or {}}


def update_code_classification(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    no: Any,
    classification: str,
    category: str,
    old_classification: str | None = None,
) -> dict[str, Any]:
    classification = (classification or "").strip()
    category = (category or "").strip()
    if not classification or not category:
        raise ValueError("分类和类别不能为空")

    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")

    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")

    old_name = (old_classification or "").strip()
    mask = _find_code_row_mask(code_df, no=no, classification=old_name or None)
    if not mask.any():
        raise ValueError("找不到该分类记录")

    idx = code_df.index[mask][0]
    prev_cls = str(code_df.at[idx, "分类"] or "").strip()

    dup_lookup = _build_classification_lookup(code_df)
    dup_lookup.pop(prev_cls, None)
    if classification in dup_lookup:
        raise ValueError(f"分类「{classification}」已存在")

    code_df = code_df.copy()
    code_df.at[idx, "分类"] = classification
    code_df.at[idx, "类别"] = category
    item["frames"][resolved] = code_df

    linkage = _find_classification_linkage(spec)
    if linkage:
        main_sheet, cls_field, cat_field, _ = linkage
        main_name = _resolve_sheet_name(spec, item["frames"], main_sheet)
        main_df = item["frames"].get(main_name) if main_name else None
        if main_df is not None and not main_df.empty and cls_field in main_df.columns:
            main_df = main_df.copy()
            if prev_cls != classification and cls_field in main_df.columns:
                cls_mask = main_df[cls_field].astype(str).str.strip() == prev_cls
                main_df.loc[cls_mask, cls_field] = classification
            if cat_field in main_df.columns:
                cls_mask = main_df[cls_field].astype(str).str.strip() == classification
                main_df.loc[cls_mask, cat_field] = category
            item["frames"][main_name] = main_df

    sync = sync_issue_rows_from_code(item)
    return {**_code_table_payload(item, resolved), "sync": sync}


def delete_code_classification(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    no: Any,
    classification: str | None = None,
) -> dict[str, Any]:
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")

    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")

    cls_name = (classification or "").strip()
    mask = _find_code_row_mask(code_df, no=no, classification=cls_name or None)
    if not mask.any():
        raise ValueError("找不到该分类记录")

    idx = code_df.index[mask][0]
    target_cls = str(code_df.at[idx, "分类"] or "").strip()

    linkage = _find_classification_linkage(spec)
    if linkage and target_cls:
        main_sheet, cls_field, _, _ = linkage
        main_name = _resolve_sheet_name(spec, item["frames"], main_sheet)
        main_df = item["frames"].get(main_name) if main_name else None
        if main_df is not None and cls_field in main_df.columns:
            used = int((main_df[cls_field].astype(str).str.strip() == target_cls).sum())
            if used > 0:
                raise ValueError(f"分类「{target_cls}」已被问题清单引用 {used} 次，无法删除")

    code_df = code_df.drop(index=idx).reset_index(drop=True)
    item["frames"][resolved] = code_df
    sheet_spec = _find_sheet_spec(spec, resolved)
    if sheet_spec:
        sheet_spec["row_count"] = int(len(code_df))

    sync = sync_issue_rows_from_code(item)
    return {**_code_table_payload(item, resolved), "sync": sync}


def create_code_module(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    module: str,
    owner: str,
) -> dict[str, Any]:
    module = (module or "").strip()
    owner = (owner or "").strip()
    if not module or not owner:
        raise ValueError("模块和负责人不能为空")

    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")

    code_df = item["frames"].get(resolved)
    if code_df is None:
        code_df = pd.DataFrame()
        item["frames"][resolved] = code_df
    code_df = _ensure_code_columns(code_df, "序号", "模块", "负责人")

    existing = _build_module_lookup(code_df)
    if module in existing:
        raise ValueError(f"模块「{module}」已存在")

    new_row: dict[str, Any] = {col: None for col in code_df.columns if not str(col).startswith("__")}
    new_row["序号"] = _next_id(code_df, "序号")
    new_row["模块"] = module
    new_row["负责人"] = owner
    new_row["__source"] = "entered"

    item["frames"][resolved] = pd.concat([code_df, pd.DataFrame([new_row])], ignore_index=True)
    sheet_spec = _find_sheet_spec(spec, resolved)
    if sheet_spec:
        sheet_spec["row_count"] = int(len(item["frames"][resolved]))
        sheet_spec["empty"] = False

    sync = sync_issue_rows_from_code(item)
    return {**_code_table_payload(item, resolved), "sync": sync}


def update_code_module(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    no: Any,
    module: str,
    owner: str,
    old_module: str | None = None,
) -> dict[str, Any]:
    module = (module or "").strip()
    owner = (owner or "").strip()
    if not module or not owner:
        raise ValueError("模块和负责人不能为空")

    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")

    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")
    code_df = _ensure_code_columns(code_df, "序号", "模块", "负责人")

    old_name = (old_module or "").strip()
    mask = _find_module_row_mask(code_df, no=no, module=old_name or None)
    if not mask.any():
        raise ValueError("找不到该模块记录")

    idx = code_df.index[mask][0]
    prev_mod = str(code_df.at[idx, "模块"] or "").strip()

    dup_lookup = _build_module_lookup(code_df)
    dup_lookup.pop(prev_mod, None)
    if module in dup_lookup:
        raise ValueError(f"模块「{module}」已存在")

    code_df = code_df.copy()
    code_df.at[idx, "模块"] = module
    code_df.at[idx, "负责人"] = owner
    item["frames"][resolved] = code_df

    mod_link = _find_module_linkage(spec)
    if mod_link:
        main_sheet, mod_field, owner_field, _ = mod_link
        main_name = _resolve_sheet_name(spec, item["frames"], main_sheet)
        main_df = item["frames"].get(main_name) if main_name else None
        if main_df is not None and not main_df.empty and mod_field in main_df.columns:
            main_df = main_df.copy()
            if prev_mod != module:
                mod_mask = main_df[mod_field].astype(str).str.strip() == prev_mod
                main_df.loc[mod_mask, mod_field] = module
            if owner_field in main_df.columns:
                mod_mask = main_df[mod_field].astype(str).str.strip() == module
                main_df.loc[mod_mask, owner_field] = owner
            item["frames"][main_name] = main_df

    sync = sync_issue_rows_from_code(item)
    return {**_code_table_payload(item, resolved), "sync": sync}


def delete_code_module(
    item: dict[str, Any],
    *,
    code_sheet: str | None,
    no: Any,
    module: str | None = None,
) -> dict[str, Any]:
    spec = item["spec"]
    resolved = _resolve_sheet_name(spec, item["frames"], code_sheet) or _find_code_sheet(spec)
    if not resolved:
        raise ValueError("找不到代码表")

    code_df = item["frames"].get(resolved)
    if code_df is None or code_df.empty:
        raise ValueError("代码表无数据")

    mod_name = (module or "").strip()
    mask = _find_module_row_mask(code_df, no=no, module=mod_name or None)
    if not mask.any():
        raise ValueError("找不到该模块记录")

    idx = code_df.index[mask][0]
    target_mod = str(code_df.at[idx, "模块"] or "").strip()

    mod_link = _find_module_linkage(spec)
    if mod_link and target_mod:
        main_sheet, mod_field, _, _ = mod_link
        main_name = _resolve_sheet_name(spec, item["frames"], main_sheet)
        main_df = item["frames"].get(main_name) if main_name else None
        if main_df is not None and mod_field in main_df.columns:
            used = int((main_df[mod_field].astype(str).str.strip() == target_mod).sum())
            if used > 0:
                raise ValueError(f"模块「{target_mod}」已被问题清单引用 {used} 次，无法删除")

    code_df = code_df.drop(index=idx).reset_index(drop=True)
    item["frames"][resolved] = code_df
    sheet_spec = _find_sheet_spec(spec, resolved)
    if sheet_spec:
        sheet_spec["row_count"] = int(len(code_df))

    sync = sync_issue_rows_from_code(item)
    return {**_code_table_payload(item, resolved), "sync": sync}
