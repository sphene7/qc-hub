"""
Authentication and authorization utilities.
"""
import os
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models import User, Project, ProjectMember
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


FULL_CRUD = {"create": True, "read": True, "update": True, "delete": True}

DEFAULT_PERMISSIONS_BY_ROLE = {
    "read": {"create": False, "read": True, "update": False, "delete": False},
    "entry": {"create": True, "read": True, "update": True, "delete": True},
    "admin": dict(FULL_CRUD),
}


def normalize_crud_permissions(
    permissions: dict[str, Any] | None,
    *,
    role: str = "read",
) -> dict[str, bool]:
    """Merge stored JSON permissions with role defaults."""
    base = dict(DEFAULT_PERMISSIONS_BY_ROLE.get(role, DEFAULT_PERMISSIONS_BY_ROLE["read"]))
    if permissions and isinstance(permissions, dict):
        for key in ("create", "read", "update", "delete"):
            if key in permissions:
                base[key] = bool(permissions[key])
    if not base["read"]:
        base["create"] = False
        base["update"] = False
        base["delete"] = False
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
    if required_role == "delete":
        return bool(perms.get("delete"))
    if required_role == "entry":
        return bool(perms.get("create") or perms.get("update") or perms.get("delete"))
    return False


def get_user_projects(db: Session, user_id: int) -> list:
    """Get all projects accessible to user."""
    user = get_user_by_id(db, user_id)
    if not user:
        return []
    
    # Super admins see all projects
    if user.role == 'super_admin':
        projects = db.query(Project).all()
    else:
        # Get owned projects
        owned = db.query(Project).filter(Project.owner_id == user_id).all()
        
        # Get projects where user is a member
        memberships = db.query(ProjectMember).filter(ProjectMember.user_id == user_id).all()
        member_project_ids = [m.project_id for m in memberships]
        member_projects = db.query(Project).filter(Project.id.in_(member_project_ids)).all() if member_project_ids else []
        
        # Combine and deduplicate
        projects = list({p.id: p for p in (owned + member_projects)}.values())
    
    return projects


def get_project_members(db: Session, project_id: str) -> list:
    """Get all members of a project with their roles."""
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        return []
    
    memberships = db.query(ProjectMember).filter(ProjectMember.project_id == project.id).all()
    
    members = []
    for m in memberships:
        user = get_user_by_id(db, m.user_id)
        if user:
            members.append({
                'user_id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': m.role,
                'permissions': normalize_crud_permissions(m.permissions, role=m.role),
                'joined_at': m.created_at.isoformat()
            })
    
    return members


def add_project_member(
    db: Session,
    project_id: str,
    user_id: int,
    role: str = "read",
    permissions: dict[str, Any] | None = None,
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
    else:
        member = ProjectMember(
            project_id=project.id,
            user_id=user_id,
            role=role,
            permissions=perms,
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

    perms = {
        "create": bool(permissions.get("create")),
        "read": bool(permissions.get("read")),
        "update": bool(permissions.get("update")),
        "delete": bool(permissions.get("delete")),
    }
    if not perms["read"]:
        perms = {"create": False, "read": False, "update": False, "delete": False}

    resolved_role = role or infer_role_from_permissions(perms)
    if resolved_role not in ("read", "entry", "admin"):
        resolved_role = infer_role_from_permissions(perms)

    return add_project_member(db, project_wid, user_id, resolved_role, perms)


def list_all_project_permissions(db: Session) -> list[dict[str, Any]]:
    """All explicit member grants (for admin UI)."""
    rows = (
        db.query(ProjectMember, Project, User)
        .join(Project, Project.id == ProjectMember.project_id)
        .join(User, User.id == ProjectMember.user_id)
        .order_by(User.username, Project.name)
        .all()
    )
    out = []
    for membership, project, user in rows:
        out.append(
            {
                "user_id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "project_id": project.project_id,
                "project_name": project.name,
                "owner_id": project.owner_id,
                "role": membership.role,
                "permissions": normalize_crud_permissions(membership.permissions, role=membership.role),
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
