#!/usr/bin/env python3
"""
Import a bundle JSON into a (usually empty) database.

Usage (from backend/):
  python scripts/import_bundle.py ../deploy/data/bundle.json
  python scripts/import_bundle.py bundle.json --reset
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db import init_database, get_db_session  # noqa: E402
from app.models import Base, Project, ProjectMember, SheetData, User  # noqa: E402
from app.db import engine  # noqa: E402


def _parse_dt(value: str | None):
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def import_bundle(path: Path, reset: bool = False) -> None:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    if bundle.get("version") != 1:
        raise SystemExit("不支持的 bundle 版本")

    init_database()

    if reset:
        print("⚠ 清空现有数据...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    db = get_db_session()
    try:
        existing_users = {u.username: u for u in db.query(User).all()}
        user_id_map: dict[int, int] = {}

        for u in bundle.get("users", []):
            old_id = u["id"]
            if u["username"] in existing_users:
                user_id_map[old_id] = existing_users[u["username"]].id
                continue
            row = User(
                username=u["username"],
                password_hash=u["password_hash"],
                email=u.get("email"),
                full_name=u.get("full_name"),
                role=u.get("role", "user"),
                created_at=_parse_dt(u.get("created_at")),
                updated_at=_parse_dt(u.get("updated_at")),
            )
            db.add(row)
            db.flush()
            user_id_map[old_id] = row.id
            existing_users[u["username"]] = row

        project_id_map: dict[int, int] = {}
        for p in bundle.get("projects", []):
            old_internal = p["id"]
            existing = db.query(Project).filter(Project.project_id == p["project_id"]).first()
            if existing:
                project_id_map[old_internal] = existing.id
                print(f"  跳过已存在项目: {p['name']} ({p['project_id']})")
                continue

            owner_id = user_id_map.get(p["owner_id"], p["owner_id"])
            row = Project(
                project_id=p["project_id"],
                name=p["name"],
                description=p.get("description"),
                owner_id=owner_id,
                spec=p["spec"],
                integration_config=p.get("integration_config"),
                created_at=_parse_dt(p.get("created_at")),
                updated_at=_parse_dt(p.get("updated_at")),
            )
            db.add(row)
            db.flush()
            project_id_map[old_internal] = row.id

        for m in bundle.get("project_members", []):
            new_project_id = project_id_map.get(m["project_id"])
            new_user_id = user_id_map.get(m["user_id"])
            if not new_project_id or not new_user_id:
                continue
            exists = (
                db.query(ProjectMember)
                .filter(
                    ProjectMember.project_id == new_project_id,
                    ProjectMember.user_id == new_user_id,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                ProjectMember(
                    project_id=new_project_id,
                    user_id=new_user_id,
                    role=m.get("role", "read"),
                    created_at=_parse_dt(m.get("created_at")),
                )
            )

        imported_rows = 0
        for s in bundle.get("sheet_data", []):
            new_project_id = project_id_map.get(s["project_id"])
            if not new_project_id:
                continue
            db.add(
                SheetData(
                    project_id=new_project_id,
                    sheet_name=s["sheet_name"],
                    row_data=s["row_data"],
                    source=s.get("source", "imported"),
                    created_at=_parse_dt(s.get("created_at")),
                    created_by=user_id_map.get(s["created_by"]) if s.get("created_by") else None,
                )
            )
            imported_rows += 1

        db.commit()
        print(f"✓ 导入完成: {len(project_id_map)} 个项目, {imported_rows} 行数据")
        for p in bundle.get("projects", []):
            print(f"  - {p['name']}  wid={p['project_id']}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Import ExcelToWeb bundle JSON")
    parser.add_argument("bundle", help="Path to bundle JSON")
    parser.add_argument("--reset", action="store_true", help="Drop all tables before import")
    args = parser.parse_args()

    path = Path(args.bundle)
    if not path.is_file():
        raise SystemExit(f"文件不存在: {path}")

    import_bundle(path, reset=args.reset)


if __name__ == "__main__":
    main()
