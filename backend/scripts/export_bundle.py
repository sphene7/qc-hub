#!/usr/bin/env python3
"""
Export one or more projects (by wid) into a portable bundle JSON.

Usage (from backend/):
  python scripts/export_bundle.py --wids abc123,def456,ghi789 -o ../deploy/data/bundle.json
  python scripts/export_bundle.py --all -o bundle.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db import init_database, get_db_session  # noqa: E402
from app.models import Project, ProjectMember, SheetData, User  # noqa: E402


def _iso(dt):
    if dt is None:
        return None
    return dt.isoformat()


def export_bundle(wids: list[str] | None, include_all: bool) -> dict:
    init_database()
    db = get_db_session()
    try:
        if include_all:
            projects = db.query(Project).order_by(Project.id).all()
        else:
            projects = (
                db.query(Project)
                .filter(Project.project_id.in_(wids))
                .order_by(Project.id)
                .all()
            )
        if not projects:
            raise SystemExit("未找到要导出的项目，请检查 wid 是否正确")

        found_wids = {p.project_id for p in projects}
        if wids and not include_all:
            missing = [w for w in wids if w not in found_wids]
            if missing:
                print(f"警告: 以下 wid 不存在，已跳过: {', '.join(missing)}")

        project_ids = [p.id for p in projects]
        members = db.query(ProjectMember).filter(ProjectMember.project_id.in_(project_ids)).all()
        user_ids = {p.owner_id for p in projects} | {m.user_id for m in members}
        users = db.query(User).filter(User.id.in_(user_ids)).all()

        sheet_rows = db.query(SheetData).filter(SheetData.project_id.in_(project_ids)).all()

        return {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "password_hash": u.password_hash,
                    "email": u.email,
                    "full_name": u.full_name,
                    "role": u.role,
                    "created_at": _iso(u.created_at),
                    "updated_at": _iso(u.updated_at),
                }
                for u in users
            ],
            "projects": [
                {
                    "id": p.id,
                    "project_id": p.project_id,
                    "name": p.name,
                    "description": p.description,
                    "owner_id": p.owner_id,
                    "spec": p.spec,
                    "integration_config": p.integration_config,
                    "created_at": _iso(p.created_at),
                    "updated_at": _iso(p.updated_at),
                }
                for p in projects
            ],
            "project_members": [
                {
                    "project_id": m.project_id,
                    "user_id": m.user_id,
                    "role": m.role,
                    "created_at": _iso(m.created_at),
                }
                for m in members
            ],
            "sheet_data": [
                {
                    "project_id": s.project_id,
                    "sheet_name": s.sheet_name,
                    "row_data": s.row_data,
                    "source": s.source,
                    "created_at": _iso(s.created_at),
                    "created_by": s.created_by,
                }
                for s in sheet_rows
            ],
        }
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Export ExcelToWeb projects to bundle JSON")
    parser.add_argument("--wids", help="Comma-separated project_id (wid) list")
    parser.add_argument("--all", action="store_true", help="Export all projects in database")
    parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    if not args.all and not args.wids:
        parser.error("请指定 --wids 或 --all")

    wids = [w.strip() for w in (args.wids or "").split(",") if w.strip()]
    bundle = export_bundle(wids if not args.all else None, args.all)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ 已导出 {len(bundle['projects'])} 个项目")
    for p in bundle["projects"]:
        print(f"  - {p['name']}  wid={p['project_id']}")
    print(f"✓ 用户: {len(bundle['users'])}  数据行: {len(bundle['sheet_data'])}")
    print(f"✓ 文件: {out.resolve()}")


if __name__ == "__main__":
    main()
