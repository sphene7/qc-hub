"""
Authentication and authorization utilities.
"""
import os
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy.orm import Session, defer
from app.models import User, Project, ProjectMember, Role
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return hash_password(plain_password) == hashed_password


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create JWT access token."""
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user by username and password."""
    user = db.query(User).filter(User.username == username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, username: str, password: str, email: str = None, 
                full_name: str = None, role: str = 'user') -> User:
    """Create a new user."""
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        full_name=full_name,
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# 权限位：
#   create/update/delete —— 通用增删改（巡检、客诉等模块共用）
#   submit   —— 送检登记（新增/修改送检单）
#   inspect  —— 抽检登记（新增/修改抽检记录）
#   handle   —— 异常登记（OA单号、责任、对策、结案）
#   dept     —— 非布尔：送检数据范围（空 = 全部；填了课室 = 只看本课室）
PROJECT_PERMISSION_KEYS = ("create", "read", "update", "delete", "submit", "inspect", "handle")

FULL_CRUD = {key: True for key in PROJECT_PERMISSION_KEYS}

DEFAULT_PERMISSIONS_BY_ROLE = {
    "read": {**{key: False for key in PROJECT_PERMISSION_KEYS}, "read": True},
    "entry": dict(FULL_CRUD),
    "admin": dict(FULL_CRUD),
}


def normalize_crud_permissions(
    permissions: dict[str, Any] | None,
    *,
    role: str = "read",
) -> dict[str, Any]:
    """Merge stored JSON permissions with role defaults."""
    base = dict(DEFAULT_PERMISSIONS_BY_ROLE.get(role, DEFAULT_PERMISSIONS_BY_ROLE["read"]))
    provided = permissions if isinstance(permissions, dict) else {}
    for key in PROJECT_PERMISSION_KEYS:
        if key in provided:
            base[key] = bool(provided[key])
    # 旧数据兼容：没有新权限位时，按「改」推断，保持原有行为
    if "submit" not in provided:
        base["submit"] = bool(base.get("create") or base.get("update"))
    if "inspect" not in provided:
        base["inspect"] = bool(base.get("update"))
    if "handle" not in provided:
        base["handle"] = bool(base.get("update"))
    if not base["read"]:
        for key in PROJECT_PERMISSION_KEYS:
            if key != "read":
                base[key] = False
    base["dept"] = str(provided.get("dept") or "").strip()
    return base


def permissions_from_role(role: str) -> dict[str, bool]:
    return dict(DEFAULT_PERMISSIONS_BY_ROLE.get(role, DEFAULT_PERMISSIONS_BY_ROLE["read"]))


def infer_role_from_permissions(permissions: dict[str, bool]) -> str:
    if permissions.get("create") or permissions.get("update") or permissions.get("delete"):
        return "entry"
    return "read"


def get_project_access(
    db: Session,
    project_id: str,
    user_id: int,
) -> dict[str, Any] | None:
    """
    Resolve effective access for a user on a project.
    Returns None if no access; otherwise includes role, permissions, is_owner, can_manage_members.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        return None

    if user.role == "super_admin":
        return {
            "role": "admin",
            "permissions": dict(FULL_CRUD),
            "is_owner": False,
            "can_manage_members": True,
        }

    if project.owner_id == user_id:
        return {
            "role": "admin",
            "permissions": dict(FULL_CRUD),
            "is_owner": True,
            "can_manage_members": True,
        }

    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user_id,
    ).first()
    if not membership:
        return None

    perms = normalize_crud_permissions(membership.permissions, role=membership.role)
    if membership.role_id:
        role = db.query(Role).filter(Role.id == membership.role_id).first()
        if role:
            role_perms = {key: bool((role.permissions or {}).get(key)) for key in PROJECT_PERMISSION_KEYS}
            dept = str(perms.get("dept") or "")
            perms = normalize_crud_permissions(role_perms, role=membership.role)
            perms["dept"] = dept
    can_manage = membership.role == "admin"
    return {
        "role": membership.role,
        "permissions": perms,
        "is_owner": False,
        "can_manage_members": can_manage,
    }


def check_project_permission(
    db: Session,
    project_id: str,
    user_id: int,
    required_role: str = "read",
) -> bool:
    """
    Check project access.

    required_role: read | create | update | delete | entry | admin
    - CRUD flags gate data operations
    - entry: any of create/update/delete (legacy write endpoints)
    - admin: project member admin role or owner/super_admin
    """
    access = get_project_access(db, project_id, user_id)
    if not access:
        return False

    perms = access["permissions"]
    if required_role == "admin":
        return bool(access.get("can_manage_members"))
    if required_role == "read":
        return bool(perms.get("read"))
    if required_role == "create":
        return bool(perms.get("create"))
    if required_role == "update":
        return bool(perms.get("update"))
    if required_role == "submit":
        return bool(perms.get("submit"))
    if required_role == "inspect":
        return bool(perms.get("inspect"))
    if required_role == "handle":
        return bool(perms.get("handle"))
    if required_role == "delete":
        return bool(perms.get("delete"))
    if required_role == "entry":
        return bool(perms.get("create") or perms.get("update") or perms.get("delete"))
    return False


def _project_query(db: Session):
    """列表不读取整本工作簿 spec。"""
    return db.query(Project).options(defer(Project.spec), defer(Project.integration_config))


def get_user_projects(db: Session, user_id: int) -> list:
    """Get all projects accessible to user."""
    user = get_user_by_id(db, user_id)
    if not user:
        return []

    if user.role == 'super_admin':
        return _project_query(db).order_by(Project.id).all()

    owned = _project_query(db).filter(Project.owner_id == user_id).all()
    memberships = db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user_id).all()
    member_project_ids = [row[0] for row in memberships]
    member_projects = (
        _project_query(db).filter(Project.id.in_(member_project_ids)).all()
        if member_project_ids else []
    )
    return list({p.id: p for p in (owned + member_projects)}.values())


def project_list_access(db: Session, user: User, projects: list) -> dict[int, dict[str, Any] | None]:
    """一次查出当前用户在这些项目上的权限，避免逐个项目查库。"""
    if user.role == "super_admin":
        return {
            project.id: {
                "role": "admin",
                "permissions": dict(FULL_CRUD),
                "is_owner": False,
                "can_manage_members": True,
            }
            for project in projects
        }

    ids = [project.id for project in projects]
    memberships = []
    if ids:
        memberships = (
            db.query(ProjectMember)
            .filter(ProjectMember.user_id == user.id, ProjectMember.project_id.in_(ids))
            .all()
        )
    by_project = {item.project_id: item for item in memberships}
    role_ids = {item.role_id for item in memberships if item.role_id}
    roles = {}
    if role_ids:
        roles = {role.id: role for role in db.query(Role).filter(Role.id.in_(role_ids)).all()}

    out: dict[int, dict[str, Any] | None] = {}
    for project in projects:
        if project.owner_id == user.id:
            out[project.id] = {
                "role": "admin",
                "permissions": dict(FULL_CRUD),
                "is_owner": True,
                "can_manage_members": True,
            }
            continue
        membership = by_project.get(project.id)
        if membership is None:
            out[project.id] = None
            continue
        perms = normalize_crud_permissions(membership.permissions, role=membership.role)
        if membership.role_id:
            role = roles.get(membership.role_id)
            if role is not None:
                role_perms = {key: bool((role.permissions or {}).get(key)) for key in PROJECT_PERMISSION_KEYS}
                dept = str(perms.get("dept") or "")
                perms = normalize_crud_permissions(role_perms, role=membership.role)
                perms["dept"] = dept
        out[project.id] = {
            "role": membership.role,
            "permissions": perms,
            "is_owner": False,
            "can_manage_members": membership.role == "admin",
        }
    return out


def get_project_members(db: Session, project_id: str) -> list:
    """Get all members of a project with their roles."""
    project = db.query(Project.id).filter(Project.project_id == project_id).first()
    if not project:
        return []

    rows = (
        db.query(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .filter(ProjectMember.project_id == project[0])
        .all()
    )
    members = []
    for membership, user in rows:
        members.append({
            'user_id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'role': membership.role,
            'permissions': normalize_crud_permissions(membership.permissions, role=membership.role),
            'joined_at': membership.created_at.isoformat()
        })
    return members


def add_project_member(
    db: Session,
    project_id: str,
    user_id: int,
    role: str = "read",
    permissions: dict[str, Any] | None = None,
    role_id: int | None = None,
) -> bool:
    """Add or update a member on a project."""
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        return False

    perms = normalize_crud_permissions(permissions, role=role)

    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user_id,
    ).first()

    if existing:
        existing.role = role
        existing.permissions = perms
        existing.role_id = role_id
    else:
        member = ProjectMember(
            project_id=project.id,
            user_id=user_id,
            role=role,
            permissions=perms,
            role_id=role_id,
        )
        db.add(member)

    db.commit()
    return True


def set_user_project_permissions(
    db: Session,
    *,
    project_wid: str,
    user_id: int,
    permissions: dict[str, Any],
    role: str | None = None,
    role_id: int | None = None,
) -> bool:
    """Super-admin: grant or update CRUD permissions on a workbook/module."""
    project = db.query(Project).filter(Project.project_id == project_wid).first()
    if not project:
        return False
    if project.owner_id == user_id:
        return False

    user = get_user_by_id(db, user_id)
    if not user or user.role == "super_admin":
        return False

    raw = permissions or {}
    perms = {key: bool(raw.get(key)) for key in PROJECT_PERMISSION_KEYS}
    # 旧前端没传新权限位时，按「改」推断，保持兼容
    if raw.get("submit") is None:
        perms["submit"] = bool(perms["create"] or perms["update"])
    if raw.get("inspect") is None:
        perms["inspect"] = bool(perms["update"])
    if raw.get("handle") is None:
        perms["handle"] = bool(perms["update"])
    # 任一登记权限都视为可写（巡检/客诉仍走 create/update）
    if perms["submit"] or perms["inspect"] or perms["handle"]:
        perms["create"] = True
        perms["update"] = True
    if not perms["read"]:
        perms = {key: False for key in PROJECT_PERMISSION_KEYS}
    perms["dept"] = str(raw.get("dept") or "").strip()

    resolved_role = role or infer_role_from_permissions(perms)
    if resolved_role not in ("read", "entry", "admin"):
        resolved_role = infer_role_from_permissions(perms)

    return add_project_member(db, project_wid, user_id, resolved_role, perms, role_id=role_id)


def list_all_project_permissions(db: Session) -> list[dict[str, Any]]:
    """All explicit member grants (for admin UI)."""
    rows = (
        db.query(ProjectMember, Project, User)
        .join(Project, Project.id == ProjectMember.project_id)
        .join(User, User.id == ProjectMember.user_id)
        .order_by(User.username, Project.name)
        .all()
    )
    roles = {r.id: r for r in db.query(Role).all()}
    out = []
    for membership, project, user in rows:
        perms = normalize_crud_permissions(membership.permissions, role=membership.role)
        role = roles.get(membership.role_id) if membership.role_id else None
        if role is not None:
            dept = str(perms.get("dept") or "")
            role_perms = {key: bool((role.permissions or {}).get(key)) for key in PROJECT_PERMISSION_KEYS}
            perms = normalize_crud_permissions(role_perms, role=membership.role)
            perms["dept"] = dept
        out.append(
            {
                "user_id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "project_id": project.project_id,
                "project_name": project.name,
                "owner_id": project.owner_id,
                "role": membership.role,
                "role_id": membership.role_id,
                "role_name": role.name if role else None,
                "permissions": perms,
            }
        )
    return out


def remove_project_member(db: Session, project_id: str, user_id: int) -> bool:
    """Remove a member from a project."""
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        return False
    
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user_id
    ).first()
    
    if member:
        db.delete(member)
        db.commit()
        return True
    
    return False
