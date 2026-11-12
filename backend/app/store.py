"""Workbook store with MySQL persistence."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session

from .entry import (
    attach_forms,
    drop_junk_rows,
    mark_imported,
    normalize_inspection_status_column,
    repair_legacy_month_values,
    repair_missing_row_ids,
    repair_overdue_days,
)
from .code_table import attach_code_table_lookups
from .spec_sync import sync_spec
from .models import Project, SheetData
from .logutil import log
from .sheet_util import resolve_sheet_name, sheet_row_stats
from .db import SessionLocal, release_db


def _serialize_value(val):
    """Convert pandas/numpy types to JSON-serializable Python types."""
    if pd.isna(val):
        return None
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.isoformat()
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='ignore')
    return val


def _row_to_dict(row):
    """Convert DataFrame row to JSON-serializable dict."""
    return {k: _serialize_value(v) for k, v in row.to_dict().items()}


def save(parsed: dict[str, Any], spec: dict[str, Any], 
         owner_id: int, project_name: str = None, db: Session = None) -> str:
    """
    Save workbook to database.
    
    Args:
        parsed: Parsed workbook data with sheets and DataFrames
        spec: Workbook specification
        owner_id: ID of the user creating this project
        project_name: Optional project name (defaults to workbook name)
        db: Database session
    
    Returns:
        Project ID (wid)
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()
    
    try:
        # Generate project ID
        wid = uuid.uuid4().hex[:12]
        
        # Prepare frames
        frames = {s["name"]: s["df"] for s in parsed["sheets"]}
        for name, df in list(frames.items()):
            if "抽检数据" in (name or "").strip() and "展开" not in name:
                frames[name] = normalize_inspection_status_column(df)
        mark_imported(frames)
        attach_forms(spec, frames)
        sync_spec(spec, frames)
        
        # Determine project name
        if not project_name:
            project_name = spec.get('name', f'Project {wid}')
        
        # Create project record
        project = Project(
            project_id=wid,
            name=project_name,
            description=f"Excel workbook: {spec.get('name', 'Unnamed')}",
            owner_id=owner_id,
            spec=spec
        )
        db.add(project)
        db.flush()  # Get the project.id
        
        # Save all sheet data
        for sheet_name, df in frames.items():
            if df is not None and not df.empty:
                # Convert DataFrame to records
                for _, row in df.iterrows():
                    row_dict = _row_to_dict(row)
                    # Determine source
                    source = row_dict.get('__source', 'imported')
                    if '__source' in row_dict:
                        del row_dict['__source']
                    
                    sheet_data = SheetData(
                        project_id=project.id,
                        sheet_name=sheet_name,
                        row_data=row_dict,
                        source=source,
                        created_by=None if source == 'imported' else owner_id
                    )
                    db.add(sheet_data)
        
        db.commit()
        return wid
    
    finally:
        if own_session:
            db.close()


def match_sheet_name(spec: dict[str, Any], raw: str | None) -> str | None:
    """按工作表名、主表、首页主表依次匹配 spec 里的真实表名。"""
    candidates: list[str] = []
    if raw:
        candidates.append(str(raw))
    else:
        primary = spec.get("primary_sheet")
        if primary:
            candidates.append(str(primary))
        design_sheet = ((spec.get("dashboard_design") or {}).get("main_table") or {}).get("sheet")
        if design_sheet:
            candidates.append(str(design_sheet))
    for candidate in candidates:
        target = candidate.strip()
        for sheet in spec.get("sheets") or []:
            name = sheet.get("name") or ""
            if name == candidate or name.strip() == target:
                return name
    return None


def related_sheet_names(spec: dict[str, Any], anchor: str) -> list[str]:
    """目标表 + 它的 VLOOKUP / join 对照表 + 代码表。不把无关大表一起读出来。"""
    names: list[str] = []

    def add(name: str | None) -> None:
        if not name:
            return
        target = str(name).strip()
        for sheet in spec.get("sheets") or []:
            sheet_name = sheet.get("name") or ""
            if sheet_name == name or sheet_name.strip() == target:
                if sheet_name not in names:
                    names.append(sheet_name)
                return
        if str(name) not in names:
            names.append(str(name))

    add(anchor)
    for sheet in spec.get("sheets") or []:
        if "代码" in (sheet.get("name") or ""):
            add(sheet.get("name"))
    anchor_sheet = next(
        (
            sheet for sheet in spec.get("sheets") or []
            if (sheet.get("name") or "") == anchor or (sheet.get("name") or "").strip() == anchor.strip()
        ),
        None,
    )
    if anchor_sheet:
        for column in (anchor_sheet.get("formula") or {}).get("columns") or []:
            for lookup in column.get("vlookups") or []:
                add(lookup.get("table_sheet"))
    return names


def sampling_support_sheets(spec: dict[str, Any]) -> list[str]:
    """抽检登记只用代码表和 OQC 公式对照表，不读 OQC 宽表本身。"""
    names: list[str] = []
    oqc_names = {
        sheet.get("name") or ""
        for sheet in spec.get("sheets") or []
        if "OQC" in (sheet.get("name") or "") or "抽检批次" in (sheet.get("name") or "")
    }

    def add(name: str | None) -> None:
        if not name or name in oqc_names or name in names:
            return
        names.append(name)

    for sheet in spec.get("sheets") or []:
        name = sheet.get("name") or ""
        if "代码" in name:
            add(name)
        if name not in oqc_names:
            continue
        for column in (sheet.get("formula") or {}).get("columns") or []:
            for lookup in column.get("vlookups") or []:
                add(lookup.get("table_sheet"))
    return names


def peek_spec(wid: str, db: Session) -> dict[str, Any] | None:
    row = db.query(Project.spec).filter(Project.project_id == wid).first()
    if row is None:
        release_db(db)
        return None
    spec = copy.deepcopy(row[0] or {})
    release_db(db)
    return spec


def load_for_sheet(wid: str, db: Session, sheet: str | None = None) -> Optional[dict[str, Any]]:
    """只加载一张业务表及其对照表，读完即还连接，不把整本工作簿扫进内存。"""
    spec = peek_spec(wid, db)
    if spec is None:
        return None
    name = match_sheet_name(spec, sheet)
    if not name:
        return get(wid, db, persist_repairs=False)
    return get(wid, db, sheets=related_sheet_names(spec, name), persist_repairs=False)


def load_sampling_frames(wid: str, db: Session) -> Optional[dict[str, Any]]:
    spec = peek_spec(wid, db)
    if spec is None:
        return None
    return get(wid, db, sheets=sampling_support_sheets(spec), persist_repairs=False)


def get(wid: str, db: Session = None, *, sheets: list[str] | None = None, persist_repairs: bool = True) -> Optional[dict[str, Any]]:
    """
    Get workbook from database.
    
    Args:
        wid: Project ID
        db: Database session
    
    Returns:
        Dict with 'id', 'spec', 'frames' keys, or None if not found
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.project_id == wid).first()
        if not project:
            release_db(db)
            return None

        project_db_id = project.id
        spec = copy.deepcopy(project.spec or {})
        query = db.query(SheetData).filter(SheetData.project_id == project_db_id)
        if sheets is not None:
            query = query.filter(SheetData.sheet_name.in_(sheets)) if sheets else query.filter(SheetData.id < 0)
        sheet_rows = query.order_by(SheetData.id).all()

        sheet_data_map: dict[str, list] = {}
        for row in sheet_rows:
            row_dict = row.row_data.copy() if isinstance(row.row_data, dict) else dict(row.row_data or {})
            row_dict["__source"] = row.source
            row_dict["__db_id"] = row.id
            sheet_data_map.setdefault(row.sheet_name, []).append(row_dict)
        if sheets is not None:
            for name in sheets:
                sheet_data_map.setdefault(name, [])
        # 行已经拷成普通 dict。先还连接，再做 DataFrame 修复。
        release_db(db)

        frames: dict[str, pd.DataFrame] = {}
        sheet_repairs: dict[str, pd.DataFrame] = {}
        for sheet_name, rows in sheet_data_map.items():
            if rows:
                df = pd.DataFrame(rows)
                sheet_spec = next(
                    (s for s in (spec.get("sheets") or []) if s.get("name") == sheet_name),
                    None,
                )
                if sheet_spec and sheet_spec.get("columns"):
                    ordered = [c["key"] for c in sheet_spec["columns"] if c.get("key") in df.columns]
                    tail = [c for c in df.columns if c not in ordered and not str(c).startswith("__")]
                    meta = [c for c in df.columns if str(c).startswith("__")]
                    df = df[ordered + tail + meta]
                if "抽检数据" in (sheet_name or "").strip() and "展开" not in sheet_name:
                    df = normalize_inspection_status_column(df)
                df = drop_junk_rows(df)
                df = repair_missing_row_ids(df)
                df, month_fixed = repair_legacy_month_values(df)
                if month_fixed:
                    sheet_repairs[sheet_name] = df
                if sheet_spec:
                    df, overdue_fixed = repair_overdue_days(df, sheet_spec)
                    if overdue_fixed:
                        sheet_repairs[sheet_name] = df
                frames[sheet_name] = df
            else:
                frames[sheet_name] = pd.DataFrame()
        if persist_repairs:
            for sheet_name, df in sheet_repairs.items():
                update_sheet_data(wid, sheet_name, df, db=db)
        if sheets is None:
            sync_spec(spec, frames)
            attach_code_table_lookups(spec, frames)

        frame_summary = {k: sheet_row_stats(v) for k, v in frames.items()}
        log(f"[store.get] wid={wid} project_db_id={project_db_id} sheets={sheets if sheets is not None else 'all'} frames={frame_summary}")

        return {
            "id": wid,
            "spec": spec,
            "frames": frames,
        }
    finally:
        if own_session and db is not None:
            db.close()


def _db_id(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _canonical(value: Any) -> Any:
    """比较 JSON 行时把 1 和 1.0 看成同一个值。"""
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items() if not str(k).startswith("__")}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if np.isnan(value) or np.isinf(value):
            return None
        number = float(value)
        return int(number) if number.is_integer() else number
    return value


def _chunked(values: list[int], size: int = 400):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def update_sheet_data(wid: str, sheet_name: str, df: pd.DataFrame,
                     user_id: int = None, db: Session = None) -> bool:
    """按 __db_id 增量更新。未改动的行不删不插。"""
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.project_id == wid).first()
        if not project:
            log(f"[store.update_sheet_data] FAIL wid={wid} sheet={sheet_name!r} reason=project_not_found")
            return False

        save_name = sheet_name
        existing = {
            row_id: (payload, source)
            for row_id, payload, source in db.query(SheetData.id, SheetData.row_data, SheetData.source).filter(
                SheetData.project_id == project.id,
                SheetData.sheet_name == save_name,
            ).all()
        }
        seen: set[int] = set()
        inserted = 0
        updated = 0
        entered = 0
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                row_dict = _row_to_dict(row)
                source = row_dict.get("__source", "imported") or "imported"
                if source == "entered":
                    entered += 1
                row_dict.pop("__source", None)
                db_id = _db_id(row_dict.pop("__db_id", None))
                if db_id is not None and db_id in existing:
                    if db_id not in seen:
                        seen.add(db_id)
                        old_payload, old_source = existing[db_id]
                        if old_source != source or _canonical(old_payload) != _canonical(row_dict):
                            db.query(SheetData).filter(SheetData.id == db_id).update(
                                {SheetData.row_data: row_dict, SheetData.source: source},
                                synchronize_session=False,
                            )
                            updated += 1
                    continue
                db.add(SheetData(
                    project_id=project.id,
                    sheet_name=save_name,
                    row_data=row_dict,
                    source=source,
                    created_by=user_id if source == "entered" else None,
                ))
                inserted += 1

        stale = [row_id for row_id in existing if row_id not in seen]
        deleted = len(stale)
        for batch in _chunked(stale):
            db.query(SheetData).filter(SheetData.id.in_(batch)).delete(synchronize_session=False)

        db.commit()
        log(
            f"[store.update_sheet_data] OK wid={wid} sheet={save_name!r} "
            f"db_before={len(existing)} updated={updated} inserted={inserted} "
            f"deleted={deleted} entered={entered} stats={sheet_row_stats(df)}"
        )
        return True
    finally:
        if own_session and db is not None:
            db.close()
