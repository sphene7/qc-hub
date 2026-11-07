"""为洪沛生开通两个账号：全权限 + 仅抽送检。

用法（在 backend 目录或仓库根目录）:
  python -m scripts.seed_hongpeisheng
  python scripts/seed_hongpeisheng.py

默认密码均为 Hps@2026（首次登录后请改密）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import FULL_CRUD, create_user, set_user_project_permissions  # noqa: E402
from app.db import get_db_session, init_database  # noqa: E402
from app.main import DEFAULT_ROLES, _ensure_roles_seeded  # noqa: E402
from app.models import Project, Role, User  # noqa: E402

DEFAULT_PASSWORD = "Hps@2026"

ACCOUNTS = [
    {
        "username": "hps_all",
        "full_name": "洪沛生",
        "email": "hps_all@local",
        "role_name": "项目主管",
        "permissions": {
            "create": True,
            "read": True,
            "update": True,
            "delete": True,
            "submit": True,
            "inspect": True,
            "handle": True,
            "dept": "",
        },
        "note": "全部权限",
    },
    {
        "username": "hps_smp",
        "full_name": "洪沛生（抽送检）",
        "email": "hps_smp@local",
        "role_name": None,
        "permissions": {
            "create": True,
            "read": True,
            "update": True,
            "delete": False,
            "submit": True,
            "inspect": True,
            "handle": False,
            "dept": "",
        },
        "note": "仅抽送检（送检+抽检）",
    },
]


def _ensure_user(db, *, username: str, full_name: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user:
        print(f"  · 已存在用户 {username}（id={user.id}）")
        if full_name and user.full_name != full_name:
            user.full_name = full_name
            db.commit()
        return user
    user = create_user(
        db,
        username=username,
        password=DEFAULT_PASSWORD,
        email=email,
        full_name=full_name,
        role="user",
    )
    print(f"  ✓ 创建用户 {username} / {DEFAULT_PASSWORD}（{full_name}）")
    return user


def _role_id(db, name: str | None) -> int | None:
    if not name:
        return None
    role = db.query(Role).filter(Role.name == name).first()
    return role.id if role else None


def _oqc_projects(db) -> list[Project]:
    projects = db.query(Project).order_by(Project.id).all()
    picked = []
    for p in projects:
        name = (p.name or "").lower()
        if "变焦" in (p.name or "") or "抽检" in (p.name or "") or "oqc" in name:
            picked.append(p)
    return picked or projects


def main() -> None:
    init_database()
    db = get_db_session()
    try:
        _ensure_roles_seeded(db)
        # 保证 DEFAULT_ROLES 有「送检+抽检」组合可用时，项目主管等已在库
        for item in DEFAULT_ROLES:
            if not db.query(Role).filter(Role.name == item["name"]).first():
                pass

        projects = _oqc_projects(db)
        if not projects:
            print("⚠ 未找到任何项目，仅创建账号，请稍后在「权限管理」里授权。")
        else:
            print(f"将授权项目：{', '.join(p.name for p in projects)}")

        for acc in ACCOUNTS:
            print(f"\n[{acc['note']}]")
            user = _ensure_user(
                db,
                username=acc["username"],
                full_name=acc["full_name"],
                email=acc["email"],
            )
            role_id = _role_id(db, acc["role_name"])
            for project in projects:
                if project.owner_id == user.id:
                    print(f"  · 跳过自有项目 {project.name}")
                    continue
                ok = set_user_project_permissions(
                    db,
                    project_wid=project.project_id,
                    user_id=user.id,
                    permissions=acc["permissions"],
                    role_id=role_id,
                )
                if ok:
                    print(f"  ✓ 授权 {project.name}（{project.project_id}）")
                else:
                    print(f"  · 未能授权 {project.name}（可能已是 owner / 无此用户）")

        print("\n完成。登录账号：")
        for acc in ACCOUNTS:
            print(f"  {acc['username']} / {DEFAULT_PASSWORD}  — {acc['note']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
