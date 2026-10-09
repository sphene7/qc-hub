"""Workbook store with MySQL persistence."""

from __future__ import annotations

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
from .db import get_db


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
    should_close_db = False
    if db is None:
        db = next(get_db())
        should_close_db = True
    
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
        if should_close_db:
            db.close()


def get(wid: str, db: Session = None) -> Optional[dict[str, Any]]:
    """
    Get workbook from database.
    
    Args:
        wid: Project ID
        db: Database session
    
    Returns:
        Dict with 'id', 'spec', 'frames' keys, or None if not found
    """
    should_close_db = False
    if db is None:
        db = next(get_db())
        should_close_db = True
    
    try:
        # Get project
        project = db.query(Project).filter(Project.project_id == wid).first()
        if not project:
            return None
        
        # Get all sheet data
        sheet_rows = (
            db.query(SheetData)
            .filter(SheetData.project_id == project.id)
            .order_by(SheetData.id)
            .all()
        )
        
        # Reconstruct DataFrames
        frames = {}
        sheet_data_map = {}
        
        for row in sheet_rows:
            sheet_name = row.sheet_name
            if sheet_name not in sheet_data_map:
                sheet_data_map[sheet_name] = []
            
            # Add __source back
            row_dict = row.row_data.copy()
            row_dict['__source'] = row.source
            row_dict['__db_id'] = row.id
            sheet_data_map[sheet_name].append(row_dict)
        
        # Create DataFrames
        spec = project.spec or {}
        sheet_repairs: dict[str, pd.DataFrame] = {}
        for sheet_name, rows in sheet_data_map.items():
            if rows:
                df = pd.DataFrame(rows)
                # 按 spec 列顺序排列（JSON 载入后列会变成字母序）
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
        for sheet_name, df in sheet_repairs.items():
            update_sheet_data(wid, sheet_name, df, db=db)
        sync_spec(spec, frames)
        attach_code_table_lookups(spec, frames)

        frame_summary = {k: sheet_row_stats(v) for k, v in frames.items()}
        log(f"[store.get] wid={wid} project_db_id={project.id} frames={frame_summary}")

        return {
            "id": wid,
            "spec": spec,
            "frames": frames
        }
    
    finally:
        if should_close_db:
            db.close()


def update_sheet_data(wid: str, sheet_name: str, df: pd.DataFrame, 
                     user_id: int = None, db: Session = None) -> bool:
    """
    Update sheet data in database.
    
    Args:
        wid: Project ID
        sheet_name: Sheet name
        df: Updated DataFrame
        user_id: User making the change
        db: Database session
    
    Returns:
        True if successful, False otherwise
    """
    should_close_db = False
    if db is None:
        db = next(get_db())
        should_close_db = True
    
    try:
        # Get project
        project = db.query(Project).filter(Project.project_id == wid).first()
        if not project:
            log(f"[store.update_sheet_data] FAIL wid={wid} sheet={sheet_name!r} reason=project_not_found")
            return False

        save_name = sheet_name
        before = db.query(SheetData).filter(
            SheetData.project_id == project.id,
            SheetData.sheet_name == save_name,
        ).count()
        
        # Delete existing rows for this sheet
        db.query(SheetData).filter(
            SheetData.project_id == project.id,
            SheetData.sheet_name == save_name
        ).delete()
        
        inserted = 0
        entered = 0
        # Insert new rows
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                row_dict = _row_to_dict(row)
                source = row_dict.get('__source', 'imported')
                if source == 'entered':
                    entered += 1
                if '__source' in row_dict:
                    del row_dict['__source']
                row_dict.pop('__db_id', None)
                
                sheet_data = SheetData(
                    project_id=project.id,
                    sheet_name=save_name,
                    row_data=row_dict,
                    source=source,
                    created_by=user_id if source == 'entered' else None
                )
                db.add(sheet_data)
                inserted += 1
        
        db.commit()
        log(
            f"[store.update_sheet_data] OK wid={wid} sheet={save_name!r} "
            f"db_before={before} inserted={inserted} entered={entered} stats={sheet_row_stats(df)}"
        )
        return True
    
    finally:
        if should_close_db:
            db.close()
