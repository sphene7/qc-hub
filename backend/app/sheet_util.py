"""Sheet name resolution and debug helpers."""

from __future__ import annotations

from typing import Any


def resolve_sheet_name(name: str | None, spec: dict[str, Any], frames: dict) -> str | None:
    """Match sheet name to frames key (handles trailing spaces)."""
    if not name:
        return None
    if name in frames:
        return name
    target = name.strip()
    for key in frames:
        if key.strip() == target:
            return key
    for sh in spec.get("sheets") or []:
        sn = sh.get("name") or ""
        if sn == name or sn.strip() == target:
            return sn if sn in frames else name
    return name


def sheet_row_stats(df) -> dict[str, Any]:
    if df is None:
        return {"rows": 0, "entered": 0, "columns": 0}
    entered = 0
    if hasattr(df, "columns") and "__source" in df.columns:
        entered = int((df["__source"] == "entered").sum())
    return {
        "rows": int(len(df)),
        "entered": entered,
        "columns": int(len(df.columns)) if hasattr(df, "columns") else 0,
    }
