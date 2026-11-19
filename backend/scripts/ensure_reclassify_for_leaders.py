"""核对并补齐「跨类移动」权限（reclassify）。

方案 2：内置角色「项目主管」默认带跨类；洪沛生账号 hps_all 挂该角色。

用法（在 backend 目录或仓库根目录）:
  # 仅核对：补齐项目主管角色的 reclassify，并列出谁有跨类
  python -m scripts.ensure_reclassify_for_leaders
  python scripts/ensure_reclassify_for_leaders.py

  # 额外把指定用户在变焦/抽检项目上设为项目主管并开跨类（默认 hps_all）
  python -m scripts.ensure_reclassify_for_leaders --grant
  python -m scripts.ensure_reclassify_for_leaders --grant --user hps_all

不绑死人名：可用 --user 换账号。不会改 hps_smp 等抽送检账号。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import PROJECT_PERMISSION_KEYS, set_user_project_permissions  # noqa: E402
from app.db import get_db_session, init_database  # noqa: E402
from app.main import DEFAULT_ROLES, _ensure_roles_seeded  # noqa: E402
from app.models import Project, ProjectMember, Role, User  # noqa: E402

LEADER_ROLE_NAME = "项目主管"
DEFAULT_GRANT_USER = "hps_all"


def _oqc_projects(db) -> list[Project]:
    projects = db.query(Project).order_by(Project.id).all()
    picked = []
    for p in projects:
        name = (p.name or "").lower()
        if "变焦" in (p.name or "") or "抽检" in (p.name or "") or "oqc" in name:
            picked.append(p)
    return picked or projects


def _patch_leader_role(db) -> Role | None:
    """确保「项目主管」存在且 reclassify=True，并给所有角色补齐缺失权限 key。"""
    _ensure_roles_seeded(db)
    defaults_by_name = {item["name"]: item["permissions"] for item in DEFAULT_ROLES}
    changed = False
    for role in db.query(Role).all():
        perms = dict(role.permissions or {})
        default_perms = defaults_by_name.get(role.name) or {}
        dirty = False
        for key in PROJECT_PERMISSION_KEYS:
            if key not in perms:
                perms[key] = bool(default_perms.get(key, False))
                dirty = True
        if role.name == LEADER_ROLE_NAME and not perms.get("reclassify"):
            perms["reclassify"] = True
            dirty = True
        if dirty:
            role.permissions = perms
            changed = True
    if changed:
        db.commit()
        print("✓ 已补齐角色权限位（含项目主管.reclassify=True）")
    else:
        print("· 角色权限位已齐全，无需修补")

    leader = db.query(Role).filter(Role.name == LEADER_ROLE_NAME).first()
    if not leader:
        print(f"⚠ 找不到角色「{LEADER_ROLE_NAME}」，请先跑角色种子或在角色管理里创建")
        return None
    flag = bool((leader.permissions or {}).get("reclassify"))
    print(f"· 「{LEADER_ROLE_NAME}」reclassify = {flag}")
    return leader


def _effective_reclassify(membership: ProjectMember, roles: dict[int, Role], is_owner: bool) -> bool:
    if is_owner:
        return True
    if membership.role_id and membership.role_id in roles:
        role = roles[membership.role_id]
        return bool((role.permissions or {}).get("reclassify"))
    return bool((membership.permissions or {}).get("reclassify"))


def _list_reclassify_holders(db, projects: list[Project]) -> None:
    roles = {r.id: r for r in db.query(Role).all()}
    users = {u.id: u for u in db.query(User).all()}
    print("\n=== 各项目跨类权限持有者 ===")
    for project in projects:
        print(f"\n[{project.name}] ({project.project_id})")
        holders: list[str] = []
        if project.owner_id and project.owner_id in users:
            owner = users[project.owner_id]
            holders.append(f"  · {owner.username}（{owner.full_name or '-'}）— 项目所有者")
        members = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project.id)
            .all()
        )
        for m in members:
            if not _effective_reclassify(m, roles, is_owner=False):
                continue
            user = users.get(m.user_id)
            if not user:
                continue
            if project.owner_id == user.id:
                continue
            role_name = roles[m.role_id].name if m.role_id and m.role_id in roles else (m.role or "-")
            holders.append(f"  · {user.username}（{user.full_name or '-'}）— 角色 {role_name}")
        if holders:
            print("\n".join(holders))
        else:
            print("  （无成员持有跨类；仅超管可兜底）")


def _grant_user_as_leader(db, *, username: str, leader: Role, projects: list[Project]) -> None:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        print(f"\n⚠ 用户「{username}」不存在。可先跑：python -m scripts.seed_hongpeisheng")
        return
    if user.role == "super_admin":
        print(f"\n· {username} 已是超管，天然具备跨类，跳过赋权")
        return

    perms = {key: bool((leader.permissions or {}).get(key)) for key in PROJECT_PERMISSION_KEYS}
    perms["dept"] = ""
    # 双保险：成员 JSON 也显式开跨类（即便未挂角色也能用）
    perms["reclassify"] = True

    print(f"\n=== 赋权 {username} → 「{LEADER_ROLE_NAME}」+ reclassify ===")
    for project in projects:
        if project.owner_id == user.id:
            print(f"  · 跳过自有项目 {project.name}")
            continue
        ok = set_user_project_permissions(
            db,
            project_wid=project.project_id,
            user_id=user.id,
            permissions=perms,
            role_id=leader.id,
        )
        if ok:
            print(f"  ✓ {project.name}（{project.project_id}）")
        else:
            print(f"  · 未能授权 {project.name}（可能已是 owner / 无此用户）")


def main() -> None:
    parser = argparse.ArgumentParser(description="核对/补齐跨类移动（reclassify）权限")
    parser.add_argument(
        "--grant",
        action="store_true",
        help=f"把指定用户设为项目主管并开跨类（默认用户 {DEFAULT_GRANT_USER}）",
    )
    parser.add_argument(
        "--user",
        default=DEFAULT_GRANT_USER,
        help=f"配合 --grant 使用的用户名（默认 {DEFAULT_GRANT_USER}）",
    )
    args = parser.parse_args()

    init_database()
    db = get_db_session()
    try:
        leader = _patch_leader_role(db)
        projects = _oqc_projects(db)
        if not projects:
            print("⚠ 未找到任何项目")
        else:
            print(f"· 核对项目：{', '.join(p.name for p in projects)}")

        if args.grant:
            if not leader:
                print("无法赋权：缺少项目主管角色")
            else:
                _grant_user_as_leader(db, username=args.user, leader=leader, projects=projects)

        if projects:
            _list_reclassify_holders(db, projects)

        print("\n完成。")
        print("提示：其他人不要挂「项目主管」；普通送检/检验/品质默认无跨类。")
        print("超管与项目所有者始终可跨类（运维兜底）。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
