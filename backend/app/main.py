from __future__ import annotations

import os
import tempfile
import traceback
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import store
from .complaint_analytics import build_complaint_analytics
from .inspection_analytics import build_inspection_analytics
from .oqc_analytics import build_oqc_analytics
from .code_table import (
    create_code_category,
    create_code_classification,
    create_code_module,
    delete_code_classification,
    delete_code_module,
    get_code_classifications,
    update_code_classification,
    update_code_module,
)
from . import code_table_oqc
from .entry import (
    append_row,
    delete_row,
    delete_rows,
    drop_junk_rows,
    export_sheet_xlsx,
    export_workbook_xlsx,
    merged_export_sheet_names,
    preview_row,
    update_row_field,
    update_row_values,
)
from .parser import parse_workbook
from .semantics import (
    apply_filters,
    apply_sort,
    build_column_filter_meta,
    build_workbook_spec,
    compute_chart,
    compute_kpis,
    page_rows,
)
from .db import init_database, get_db
from .auth import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    check_project_permission,
    get_user_projects,
    get_user_by_id,
    create_user,
    get_project_members,
    add_project_member,
    remove_project_member,
    verify_password,
    hash_password,
    get_project_access,
    list_all_project_permissions,
    set_user_project_permissions,
)
from .models import User, Project, ProjectMember
from .logutil import log, LOG_FILE
from .sheet_util import resolve_sheet_name, sheet_row_stats
from .abnormal_monitor import build_module_monitor
from .config import (
    IS_PRODUCT,
    ALLOW_UPLOAD,
    ALLOW_REGISTER,
    ENABLE_AI,
    get_modules,
    get_system_info,
    get_ui_settings,
    save_ui_settings,
)

ROOT = Path(__file__).resolve().parents[2]
TESTDATA = ROOT / "testdata"
DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="ExcelToWeb", version="0.1.0")

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_database()
    info = get_system_info()
    log(f"Excel-to-Web started — mode={info['mode']} name={info['system_name']}")
    log(f"日志文件: {LOG_FILE}")


def _require_upload_allowed(current_user: User) -> None:
    if ALLOW_UPLOAD:
        return
    if current_user.role == "super_admin":
        return
    raise HTTPException(403, "当前系统已禁用上传新项目")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    log(f">>> {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        log(f"<<< {request.method} {request.url.path} -> {response.status_code}")
        return response
    except Exception as exc:
        log(f"!!! {request.method} {request.url.path} ERROR: {exc}")
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SortBody(BaseModel):
    field: str
    direction: str = "asc"


class QueryBody(BaseModel):
    sheet: str | None = None
    filters: dict = Field(default_factory=dict)
    sort: SortBody | None = None
    offset: int = 0
    limit: int = 50


class RowBody(BaseModel):
    sheet: str | None = None
    values: dict = Field(default_factory=dict)


class UpdateRowBody(BaseModel):
    sheet: str | None = None
    row_key: str = "序号"
    row_id: str | int | float
    field: str
    value: str | int | float | None = None


class PutRowBody(BaseModel):
    sheet: str | None = None
    row_key: str = "序号"
    row_id: str | int | float
    values: dict = Field(default_factory=dict)


class DeleteRowTarget(BaseModel):
    row_id: str | int | float | None = None
    db_id: int | None = None


class DeleteRowBody(BaseModel):
    sheet: str | None = None
    row_key: str = "序号"
    row_id: str | int | float | None = None
    db_id: int | None = None
    rows: list[DeleteRowTarget] | None = None


class ExportBody(BaseModel):
    mode: str = "merged"  # merged | all | sheet | filtered
    sheet: str | None = None
    filters: dict = Field(default_factory=dict)
    sort: SortBody | None = None


class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class AdminCreateUserBody(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class CrudPermissionsBody(BaseModel):
    create: bool = False
    read: bool = True
    update: bool = False
    delete: bool = False


class AdminPermissionGrantBody(BaseModel):
    user_id: int
    project_id: str
    permissions: CrudPermissionsBody
    role: Optional[str] = None


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileBody(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None


class AdminUpdateUserBody(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None


class UiSettingsBody(BaseModel):
    show_raw_sheets: bool | None = None
    show_export_merged: bool | None = None
    project_nav_orders: dict[str, list[str]] | None = None


class CodeCategoryBody(BaseModel):
    code_sheet: str | None = None
    category: str


class CodeClassificationBody(BaseModel):
    code_sheet: str | None = None
    classification: str
    category: str


class CodeClassificationUpdateBody(BaseModel):
    code_sheet: str | None = None
    classification: str
    category: str
    old_classification: str | None = None


class CodeModuleBody(BaseModel):
    code_sheet: str | None = None
    module: str
    owner: str


class CodeModuleUpdateBody(BaseModel):
    code_sheet: str | None = None
    module: str
    owner: str
    old_module: str | None = None


class OqcDefectBody(BaseModel):
    code_sheet: str | None = None
    code: str | None = None
    desc: str | None = None
    category: str


class OqcDefectUpdateBody(BaseModel):
    code_sheet: str | None = None
    code: str
    desc: str
    category: str
    old_code: str | None = None


class OqcDefectCategoryBody(BaseModel):
    code_sheet: str | None = None
    old_category: str
    category: str


class OqcClassroomGroupBody(BaseModel):
    code_sheet: str | None = None
    old_section: str
    section: str


class OqcSectionHeadGroupBody(BaseModel):
    code_sheet: str | None = None
    old_head: str
    head: str


class OqcModelSectionBody(BaseModel):
    code_sheet: str | None = None
    model: str | None = None
    section: str


class OqcModelSectionUpdateBody(BaseModel):
    code_sheet: str | None = None
    model: str
    section: str
    old_model: str | None = None


class OqcModelOwnerBody(BaseModel):
    code_sheet: str | None = None
    model: str | None = None
    owner: str


class OqcModelOwnerUpdateBody(BaseModel):
    code_sheet: str | None = None
    model: str
    owner: str
    old_model: str | None = None


class OqcModelOwnerBulkRenameBody(BaseModel):
    code_sheet: str | None = None
    old_owner: str
    new_owner: str


class OqcSectionHeadBody(BaseModel):
    code_sheet: str | None = None
    section: str | None = None
    head: str


class OqcSectionHeadUpdateBody(BaseModel):
    code_sheet: str | None = None
    section: str
    head: str
    old_section: str | None = None


class MemberBody(BaseModel):
    username: str
    role: str = "read"  # 'admin', 'entry', 'read'
    permissions: CrudPermissionsBody | None = None


# Dependency: Get current user from JWT token
def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    """Extract and validate JWT token, return current user."""
    if not authorization:
        raise HTTPException(401, "未登录")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(401, "无效的认证头")
    
    token = parts[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "登录已过期或无效")
    
    user = get_user_by_id(db, payload['user_id'])
    if not user:
        raise HTTPException(401, "用户不存在")
    
    return user


# Dependency: Optional authentication (for public endpoints)
def get_current_user_optional(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Optional[User]:
    """Optional authentication - returns None if not authenticated."""
    if not authorization:
        return None
    
    try:
        return get_current_user(authorization, db)
    except HTTPException:
        return None


def _public_spec(spec: dict) -> dict:
    sheets = []
    for s in spec["sheets"]:
        sheets.append({k: v for k, v in s.items() if k != "df"})
    return {**spec, "sheets": sheets}


def _ingest_path(path: Path, filename: str, owner_id: int, db: Session, *, enable_ai: bool | None = None) -> dict:
    use_ai = ENABLE_AI if enable_ai is None else enable_ai

    log(f"\n📥 开始导入项目: {filename}")
    parsed = parse_workbook(path, filename)
    log(f"   ✅ 解析完成")
    
    spec = build_workbook_spec(parsed)
    log(f"   ✅ 规格生成完成")
    
    if use_ai:
        from app.deepseek import analyze_excel_structure
        log(f"\n🤖 开始AI分析（项目创建）...")
        try:
            dashboard_design = analyze_excel_structure(parsed, spec)
            spec['dashboard_design'] = dashboard_design
            log(f"   ✅ AI设计方案已生成")
        except Exception as e:
            log(f"   ❌ AI分析失败: {e}")
            traceback.print_exc()
            spec['dashboard_design'] = None
    else:
        log("   ℹ AI 分析已禁用，跳过 DeepSeek")
        spec['dashboard_design'] = None
    
    log(f"\n💾 保存项目到数据库...")
    wid = store.save(parsed, spec, owner_id, project_name=filename, db=db)
    log(f"   ✅ 项目已保存，ID: {wid}\n")
    
    return {"id": wid, "spec": _public_spec(spec)}


# ==================== System Info ====================

@app.get("/api/system/info")
def system_info():
    """Public runtime configuration for frontend (platform vs product mode)."""
    return get_system_info()


# ==================== Authentication Endpoints ====================

@app.post("/api/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    """User login."""
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    
    token = create_access_token(user.id, user.username, user.role)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        }
    }


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }


@app.post("/api/auth/change-password")
def change_password(
    body: ChangePasswordBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password for the current user."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    if len(body.new_password.strip()) < 6:
        raise HTTPException(400, "新密码至少 6 位")

    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "密码已更新"}


@app.put("/api/auth/profile")
def update_profile(
    body: UpdateProfileBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's display profile."""
    full_name = body.full_name.strip() if body.full_name is not None else None
    email = body.email.strip() if body.email is not None else None
    if email == "":
        email = None
    if email:
        existing = db.query(User).filter(User.email == email, User.id != current_user.id).first()
        if existing:
            raise HTTPException(400, "邮箱已被其他用户使用")
    current_user.full_name = full_name or None
    current_user.email = email
    db.commit()
    db.refresh(current_user)
    return {"message": "个人资料已更新", "user": {"id": current_user.id, "username": current_user.username, "email": current_user.email, "full_name": current_user.full_name, "role": current_user.role}}


@app.post("/api/auth/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    """User registration."""
    if not ALLOW_REGISTER:
        raise HTTPException(403, "当前系统已关闭自助注册")

    username = body.username.strip()
    if not username or len(username) > 50:
        raise HTTPException(400, "用户名不能为空且不能超过 50 个字符")
    if len(body.password.strip()) < 6:
        raise HTTPException(400, "密码至少 6 位")
    # Check if username exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(400, "用户名已存在")

    email = body.email.strip() if body.email else None
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "邮箱已被其他用户使用")
    
    # Create user
    user = create_user(db, username, body.password, body.email, body.full_name)
    
    token = create_access_token(user.id, user.username, user.role)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        }
    }


# ==================== Admin Endpoints ====================

@app.get("/api/admin/users")
def list_all_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all users (super admin only)."""
    if current_user.role != 'super_admin':
        raise HTTPException(403, "需要超级管理员权限")
    
    users = db.query(User).all()
    return {
        "users": [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "created_at": u.created_at.isoformat(),
        } for u in users]
    }


@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a user (super admin only)."""
    if current_user.role != 'super_admin':
        raise HTTPException(403, "需要超级管理员权限")
    
    # Cannot delete yourself
    if user_id == current_user.id:
        raise HTTPException(400, "不能删除自己")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    
    # Cannot delete super admins
    if user.role == 'super_admin':
        raise HTTPException(400, "不能删除超级管理员")

    owned_count = db.query(Project).filter(Project.owner_id == user_id).count()
    if owned_count:
        raise HTTPException(400, f"该用户仍拥有 {owned_count} 个项目，请先移交或删除项目")
    
    db.delete(user)
    db.commit()
    
    return {"message": "用户已删除"}


@app.put("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    body: AdminUpdateUserBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a user's account fields (super admin only)."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if body.username is not None:
        username = body.username.strip()
        if not username:
            raise HTTPException(400, "用户名不能为空")
        if db.query(User).filter(User.username == username, User.id != user_id).first():
            raise HTTPException(400, "用户名已存在")
        user.username = username
    if body.email is not None:
        email = body.email.strip() or None
        if email and db.query(User).filter(User.email == email, User.id != user_id).first():
            raise HTTPException(400, "邮箱已被其他用户使用")
        user.email = email
    if body.full_name is not None:
        user.full_name = body.full_name.strip() or None
    db.commit()
    db.refresh(user)
    return {"message": "用户信息已更新", "user": {"id": user.id, "username": user.username, "email": user.email, "full_name": user.full_name, "role": user.role, "created_at": user.created_at.isoformat()}}


@app.post("/api/admin/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset a user's password without requiring the old password."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.password_hash = hash_password("123456")
    db.commit()
    return {"message": "密码已重置为 123456"}


@app.post("/api/admin/users")
def admin_create_user(
    body: AdminCreateUserBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create user (super admin only)."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")

    username = body.username.strip()
    if not username or len(username) > 50:
        raise HTTPException(400, "用户名不能为空且不能超过 50 个字符")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(400, "用户名已存在")

    email = body.email.strip() if body.email else None
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "邮箱已被其他用户使用")

    user = create_user(
        db,
        username,
        "123456",
        email,
        body.full_name,
        role="user",
    )
    return {
        "message": "用户已创建，初始密码为 123456",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at.isoformat(),
        },
    }


@app.get("/api/admin/permissions")
def admin_list_permissions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List users, workbooks, and CRUD grants (super admin only)."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")

    users = db.query(User).order_by(User.username).all()
    projects = db.query(Project).order_by(Project.name).all()
    grants = list_all_project_permissions(db)

    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
            }
            for u in users
            if u.role != "super_admin"
        ],
        "projects": [
            {
                "id": p.project_id,
                "name": p.name,
                "owner_id": p.owner_id,
            }
            for p in projects
        ],
        "grants": grants,
    }


@app.put("/api/admin/permissions")
def admin_upsert_permission(
    body: AdminPermissionGrantBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant or update a user's CRUD permissions on a workbook/module."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")

    perms = body.permissions.model_dump()
    if not any(perms.values()):
        raise HTTPException(400, "至少需要勾选「查」或其它一项权限")

    ok = set_user_project_permissions(
        db,
        project_wid=body.project_id.strip(),
        user_id=body.user_id,
        permissions=perms,
        role=body.role,
    )
    if not ok:
        raise HTTPException(400, "无法设置权限（用户/模块不存在，或该用户为模块所有者）")

    return {"message": "权限已保存"}


@app.delete("/api/admin/permissions")
def admin_revoke_permission(
    user_id: int,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a user's access to a workbook/module."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")

    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(404, "模块不存在")
    if project.owner_id == user_id:
        raise HTTPException(400, "不能移除模块所有者的权限")

    if not remove_project_member(db, project_id, user_id):
        raise HTTPException(404, "该用户未分配此模块权限")

    return {"message": "权限已移除"}


@app.get("/api/admin/settings")
def get_admin_settings(current_user: User = Depends(get_current_user)):
    """Get UI settings (super admin only)."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")
    return get_ui_settings()


@app.put("/api/admin/settings")
def update_admin_settings(
    body: UiSettingsBody,
    current_user: User = Depends(get_current_user),
):
    """Update UI settings (super admin only)."""
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "未提供可更新的设置项")
    saved = save_ui_settings(updates)
    return {"settings": saved, "message": "界面设置已保存"}


# ==================== Project Management Endpoints ====================

@app.get("/api/projects")
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all projects accessible to current user."""
    projects = get_user_projects(db, current_user.id)
    
    result = []
    for p in projects:
        access = get_project_access(db, p.project_id, current_user.id)
        user_role = access["role"] if access else None
        permissions = access["permissions"] if access else None
        can_manage = bool(access and access.get("can_manage_members"))

        result.append({
            "id": p.project_id,
            "name": p.name,
            "description": p.description,
            "owner_id": p.owner_id,
            "is_owner": p.owner_id == current_user.id,
            "user_role": user_role,
            "permissions": permissions,
            "can_manage_members": can_manage,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        })
    
    return {"projects": result}


@app.delete("/api/projects/{wid}")
def delete_project(wid: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a project (requires owner or super_admin)."""
    if IS_PRODUCT and current_user.role != "super_admin":
        raise HTTPException(403, "产品模式下仅超级管理员可删除模块数据")

    project = db.query(Project).filter(Project.project_id == wid).first()
    if not project:
        raise HTTPException(404, "项目不存在")
    
    # Only owner or super_admin can delete
    if project.owner_id != current_user.id and current_user.role != 'super_admin':
        raise HTTPException(403, "只有项目所有者或超级管理员可以删除项目")
    
    db.delete(project)
    db.commit()
    
    return {"message": "项目已删除"}


@app.get("/api/projects/{wid}/members")
def list_members(wid: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List project members (requires admin permission)."""
    if not check_project_permission(db, wid, current_user.id, 'admin'):
        raise HTTPException(403, "无权限")
    
    members = get_project_members(db, wid)
    return {"members": members}


@app.post("/api/projects/{wid}/members")
def add_member(wid: str, body: MemberBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add member to project (requires admin permission)."""
    if not check_project_permission(db, wid, current_user.id, 'admin'):
        raise HTTPException(403, "无权限")
    
    # Find user by username
    user = db.query(User).filter(User.username == body.username).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    
    perms = body.permissions.model_dump() if body.permissions else None
    success = add_project_member(db, wid, user.id, body.role, perms)
    if not success:
        raise HTTPException(500, "添加成员失败")
    
    return {"message": "成员已添加"}


@app.delete("/api/projects/{wid}/members/{user_id}")
def remove_member(wid: str, user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove member from project (requires admin permission)."""
    if not check_project_permission(db, wid, current_user.id, 'admin'):
        raise HTTPException(403, "无权限")
    
    # Cannot remove owner
    project = db.query(Project).filter(Project.project_id == wid).first()
    if project and project.owner_id == user_id:
        raise HTTPException(400, "不能移除项目所有者")
    
    success = remove_project_member(db, wid, user_id)
    if not success:
        raise HTTPException(404, "成员不存在")
    
    return {"message": "成员已移除"}


# ==================== Workbook/Data Endpoints ====================


@app.post("/api/upload/preview")
async def upload_preview(
    file: UploadFile = File(...), 
    enable_ai: bool = True,  # Enable AI analysis by default
    current_user: User = Depends(get_current_user)
):
    """Upload Excel file and preview (does NOT save to database)."""
    _require_upload_allowed(current_user)

    from app.deepseek import analyze_excel_structure
    
    suffix = Path(file.filename or "book.xlsx").suffix.lower()
    if suffix not in {".xlsx", ".xlsm", ".xls"}:
        raise HTTPException(400, "请上传 Excel 文件（.xlsx / .xlsm）")
    data = await file.read()
    if len(data) > 80 * 1024 * 1024:
        raise HTTPException(400, "文件过大")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        # Parse Excel
        log(f"\n📂 开始解析Excel文件: {file.filename}")
        parsed = parse_workbook(tmp_path, file.filename or tmp_path.name)
        log(f"   ✅ Excel解析完成，共 {len(parsed.get('sheets', []))} 个工作表")
        
        spec = build_workbook_spec(parsed)
        log(f"   ✅ 工作簿规格生成完成")
        
        # AI Analysis (DeepSeek)
        if enable_ai and ENABLE_AI:
            log(f"\n🤖 AI分析已启用，准备调用 DeepSeek...")
            try:
                dashboard_design = analyze_excel_structure(parsed, spec)
                spec['dashboard_design'] = dashboard_design
                log(f"   ✅ AI分析结果已添加到规格中")
            except Exception as e:
                log(f"   ❌ AI分析异常: {e}")
                import traceback
                traceback.print_exc()
                spec['dashboard_design'] = None
        else:
            log(f"\n⏭️  AI分析已禁用")
        
        return {"spec": _public_spec(spec), "filename": file.filename}
    except Exception as exc:
        raise HTTPException(500, f"解析失败：{exc}") from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


@app.post("/api/projects/create")
async def create_project(
    file: UploadFile = File(...), 
    integration_config: str = None,  # JSON string of integration config
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Create project from uploaded Excel file with optional integration config."""
    import json

    _require_upload_allowed(current_user)
    
    suffix = Path(file.filename or "book.xlsx").suffix.lower()
    if suffix not in {".xlsx", ".xlsm", ".xls"}:
        raise HTTPException(400, "请上传 Excel 文件（.xlsx / .xlsm）")
    data = await file.read()
    if len(data) > 80 * 1024 * 1024:
        raise HTTPException(400, "文件过大")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        result = _ingest_path(tmp_path, file.filename or tmp_path.name, current_user.id, db)
        
        # Save integration config if provided
        if integration_config:
            try:
                config = json.loads(integration_config)
                project = db.query(Project).filter(Project.project_id == result['id']).first()
                if project:
                    project.integration_config = config
                    db.commit()
            except:
                pass  # Ignore if config is invalid
        
        return result
    except Exception as exc:
        raise HTTPException(500, f"解析失败：{exc}") from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Legacy: Upload Excel file and create project directly."""
    return await create_project(file, current_user, db)


@app.get("/api/samples")
def samples():
    if not TESTDATA.exists():
        return {"items": []}
    items = []
    for p in sorted(TESTDATA.glob("*.xlsx")):
        items.append({"name": p.name, "size": p.stat().st_size})
    return {"items": items}


@app.post("/api/samples/{name:path}")
def load_sample(name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    path = TESTDATA / name
    if not path.exists() or path.suffix.lower() != ".xlsx":
        raise HTTPException(404, "样表不存在")
    try:
        return _ingest_path(path, name, current_user.id, db)
    except Exception as exc:
        raise HTTPException(500, f"解析失败：{exc}") from exc


@app.get("/api/workbooks/{wid}")
def get_workbook(wid: str,
                current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Get workbook spec (requires read permission)."""
    if not check_project_permission(db, wid, current_user.id, 'read'):
        raise HTTPException(403, "无权限")
    
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    return {"id": wid, "spec": _public_spec(item["spec"])}


@app.post("/api/workbooks/{wid}/query")
def query_workbook(wid: str, body: QueryBody,
                  current_user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Query workbook data (requires read permission)."""
    if not check_project_permission(db, wid, current_user.id, 'read'):
        raise HTTPException(403, "无权限")
    
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    spec = item["spec"]
    raw_sheet = body.sheet or spec.get("primary_sheet")
    sheet_name = resolve_sheet_name(raw_sheet, spec, item["frames"]) or raw_sheet
    sheet_spec = next((s for s in spec["sheets"] if s["name"] == sheet_name), None)
    if not sheet_spec:
        sheet_spec = next(
            (s for s in spec["sheets"] if (s.get("name") or "").strip() == (sheet_name or "").strip()),
            None,
        )
    if not sheet_spec:
        log(f"[query] FAIL wid={wid} sheet={raw_sheet!r} resolved={sheet_name!r} frame_keys={list(item['frames'].keys())}")
        raise HTTPException(404, "找不到该工作表")
    sheet_name = sheet_spec["name"]
    df = item["frames"].get(sheet_name)
    if df is None:
        log(f"[query] FAIL wid={wid} no dataframe sheet={sheet_name!r}")
        raise HTTPException(404, "该表无数据")
    df = drop_junk_rows(df)
    filtered = apply_filters(df, body.filters)
    sorted_df = apply_sort(filtered, body.sort.model_dump() if body.sort else None)
    kpis = compute_kpis(sorted_df, sheet_spec.get("kpis") or [])
    charts = [compute_chart(sorted_df, c) for c in (sheet_spec.get("charts") or [])]
    rows, total = page_rows(sorted_df, body.offset, min(body.limit, 500))
    entered = int((df.get("__source") == "entered").sum()) if "__source" in df.columns else 0
    log(
        f"[query] wid={wid} sheet={sheet_name!r} raw={len(df)} filtered={len(filtered)} "
        f"total={total} offset={body.offset} limit={body.limit} entered={entered} "
        f"filters={body.filters} sort={body.sort.model_dump() if body.sort else None}"
    )
    if rows:
        sample_ids = [r.get("序号") for r in rows[:3]]
        log(f"[query] sample 序号 (first page): {sample_ids}")
    return {
        "sheet": sheet_name,
        "total": total,
        "entered": entered,
        "kpis": kpis,
        "charts": charts,
        "rows": rows,
        "offset": body.offset,
        "limit": body.limit,
    }


@app.get("/api/workbooks/{wid}/complaint-analytics")
def complaint_analytics(
    wid: str,
    sheet: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real-time complaint trend analytics from detail sheet rows."""
    if not check_project_permission(db, wid, current_user.id, "read"):
        raise HTTPException(403, "无权限")

    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    return build_complaint_analytics(item, sheet, date_from=date_from, date_to=date_to)


@app.get("/api/workbooks/{wid}/inspection-analytics")
def inspection_analytics(
    wid: str,
    sheet: str | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real-time inspection dashboard analytics from 问题清单 rows."""
    if not check_project_permission(db, wid, current_user.id, "read"):
        raise HTTPException(403, "无权限")

    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    return build_inspection_analytics(
        item,
        sheet,
        focus_date=date,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/api/workbooks/{wid}/oqc-analytics")
def oqc_analytics(
    wid: str,
    sheet: str | None = None,
    year: int | None = None,
    month: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """OQC 批次合格率按送检单位、按日推移（对齐 Excel 首页图表）。"""
    if not check_project_permission(db, wid, current_user.id, "read"):
        raise HTTPException(403, "无权限")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    return build_oqc_analytics(item, sheet, year=year, month=month)


@app.get("/api/abnormal-monitor")
def abnormal_monitor(
    sort: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """KK / 客诉 / 抽检 异常结案与未结案监控大屏数据。"""
    sort_dir = "asc" if str(sort).lower() == "asc" else "desc"
    modules = get_modules()
    panels: list[dict] = []
    for mod in modules:
        key = str(mod.get("key") or "").strip()
        wid = str(mod.get("project_id") or "").strip()
        if not key or not wid:
            continue
        if not check_project_permission(db, wid, current_user.id, "read"):
            continue
        item = store.get(wid, db)
        if not item:
            continue
        panels.append(build_module_monitor(key, item, sort=sort_dir))

    return {"modules": panels, "sort": sort_dir}


@app.get("/api/workbooks/{wid}/code-classifications")
def list_code_classifications(
    wid: str,
    code_sheet: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "read"):
        raise HTTPException(403, "无权限")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        return get_code_classifications(item, code_sheet)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/workbooks/{wid}/code-classifications")
def add_code_classification(
    wid: str,
    body: CodeClassificationBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = create_code_classification(
            item,
            code_sheet=body.code_sheet,
            classification=body.classification,
            category=body.category,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    code_sheet = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet, item["frames"][code_sheet], current_user.id, db)
    sync = result.get("sync") or {}
    main_sheet = sync.get("main_sheet")
    if main_sheet and main_sheet in item["frames"]:
        store.update_sheet_data(wid, main_sheet, item["frames"][main_sheet], current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return result


@app.post("/api/workbooks/{wid}/code-categories")
def add_code_category(
    wid: str,
    body: CodeCategoryBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = create_code_category(
            item,
            code_sheet=body.code_sheet,
            category=body.category,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    code_sheet = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet, item["frames"][code_sheet], current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return result


@app.put("/api/workbooks/{wid}/code-classifications/{no}")
def put_code_classification(
    wid: str,
    no: str,
    body: CodeClassificationUpdateBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        row_no: str | int | float = no
        try:
            row_no = float(no) if "." in no else int(no)
        except ValueError:
            row_no = no
        result = update_code_classification(
            item,
            code_sheet=body.code_sheet,
            no=row_no,
            classification=body.classification,
            category=body.category,
            old_classification=body.old_classification,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    code_sheet = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet, item["frames"][code_sheet], current_user.id, db)
    sync = result.get("sync") or {}
    main_sheet = sync.get("main_sheet")
    if main_sheet and main_sheet in item["frames"]:
        store.update_sheet_data(wid, main_sheet, item["frames"][main_sheet], current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return result


@app.delete("/api/workbooks/{wid}/code-classifications/{no}")
def remove_code_classification(
    wid: str,
    no: str,
    code_sheet: str | None = None,
    classification: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        row_no: str | int | float = no
        try:
            row_no = float(no) if "." in no else int(no)
        except ValueError:
            row_no = no
        result = delete_code_classification(
            item,
            code_sheet=code_sheet,
            no=row_no,
            classification=classification,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    code_sheet_name = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet_name, item["frames"][code_sheet_name], current_user.id, db)
    sync = result.get("sync") or {}
    main_sheet = sync.get("main_sheet")
    if main_sheet and main_sheet in item["frames"]:
        store.update_sheet_data(wid, main_sheet, item["frames"][main_sheet], current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return result


@app.post("/api/workbooks/{wid}/code-modules")
def add_code_module(
    wid: str,
    body: CodeModuleBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = create_code_module(
            item,
            code_sheet=body.code_sheet,
            module=body.module,
            owner=body.owner,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    code_sheet = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet, item["frames"][code_sheet], current_user.id, db)
    sync = result.get("sync") or {}
    main_sheet = sync.get("main_sheet")
    if main_sheet and main_sheet in item["frames"]:
        store.update_sheet_data(wid, main_sheet, item["frames"][main_sheet], current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return result


@app.put("/api/workbooks/{wid}/code-modules/{no}")
def put_code_module(
    wid: str,
    no: str,
    body: CodeModuleUpdateBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        row_no: str | int | float = no
        try:
            row_no = float(no) if "." in no else int(no)
        except ValueError:
            row_no = no
        result = update_code_module(
            item,
            code_sheet=body.code_sheet,
            no=row_no,
            module=body.module,
            owner=body.owner,
            old_module=body.old_module,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    code_sheet = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet, item["frames"][code_sheet], current_user.id, db)
    sync = result.get("sync") or {}
    main_sheet = sync.get("main_sheet")
    if main_sheet and main_sheet in item["frames"]:
        store.update_sheet_data(wid, main_sheet, item["frames"][main_sheet], current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return result


@app.delete("/api/workbooks/{wid}/code-modules/{no}")
def remove_code_module(
    wid: str,
    no: str,
    code_sheet: str | None = None,
    module: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        row_no: str | int | float = no
        try:
            row_no = float(no) if "." in no else int(no)
        except ValueError:
            row_no = no
        result = delete_code_module(
            item,
            code_sheet=code_sheet,
            no=row_no,
            module=module,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    code_sheet_name = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet_name, item["frames"][code_sheet_name], current_user.id, db)
    sync = result.get("sync") or {}
    main_sheet = sync.get("main_sheet")
    if main_sheet and main_sheet in item["frames"]:
        store.update_sheet_data(wid, main_sheet, item["frames"][main_sheet], current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return result


def _commit_code_table_result(
    wid: str,
    item: dict,
    result: dict,
    current_user: User,
    db: Session,
) -> None:
    code_sheet_name = result["code_sheet"]
    store.update_sheet_data(wid, code_sheet_name, item["frames"][code_sheet_name], current_user.id, db)
    sync = result.get("sync") or {}
    main_sheet = sync.get("main_sheet")
    if main_sheet and main_sheet in item["frames"]:
        store.update_sheet_data(wid, main_sheet, item["frames"][main_sheet], current_user.id, db)
    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()


@app.post("/api/workbooks/{wid}/oqc-defects")
def add_oqc_defect(wid: str, body: OqcDefectBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.create_oqc_defect(
            item, code_sheet=body.code_sheet, code=body.code, desc=body.desc, category=body.category
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.put("/api/workbooks/{wid}/oqc-defects/{code}")
def put_oqc_defect(
    wid: str, code: str, body: OqcDefectUpdateBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.update_oqc_defect(
            item,
            code_sheet=body.code_sheet,
            old_code=body.old_code or code,
            code=body.code,
            desc=body.desc,
            category=body.category,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.delete("/api/workbooks/{wid}/oqc-defects/{code}")
def remove_oqc_defect(
    wid: str, code: str, code_sheet: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.delete_oqc_defect(item, code_sheet=code_sheet, code=code)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.put("/api/workbooks/{wid}/oqc-defect-categories")
def rename_oqc_defect_category(
    wid: str, body: OqcDefectCategoryBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.rename_oqc_defect_category(
            item, code_sheet=body.code_sheet, old_category=body.old_category, category=body.category
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.delete("/api/workbooks/{wid}/oqc-defect-categories")
def remove_oqc_defect_category(
    wid: str, category: str, code_sheet: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.delete_oqc_defect_category(item, code_sheet=code_sheet, category=category)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.post("/api/workbooks/{wid}/oqc-model-sections")
def add_oqc_model_section(
    wid: str, body: OqcModelSectionBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.create_oqc_model_section(
            item, code_sheet=body.code_sheet, model=body.model, section=body.section
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.put("/api/workbooks/{wid}/oqc-model-sections/{model}")
def put_oqc_model_section(
    wid: str, model: str, body: OqcModelSectionUpdateBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.update_oqc_model_section(
            item, code_sheet=body.code_sheet, old_model=body.old_model or model, model=body.model, section=body.section
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.delete("/api/workbooks/{wid}/oqc-model-sections/{model}")
def remove_oqc_model_section(
    wid: str, model: str, code_sheet: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.delete_oqc_model_section(item, code_sheet=code_sheet, model=model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.put("/api/workbooks/{wid}/oqc-classroom-groups")
def rename_oqc_classroom_group(
    wid: str, body: OqcClassroomGroupBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.rename_oqc_classroom_group(
            item, code_sheet=body.code_sheet, old_section=body.old_section, section=body.section
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.delete("/api/workbooks/{wid}/oqc-classroom-groups")
def remove_oqc_classroom_group(
    wid: str, section: str, code_sheet: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.delete_oqc_classroom_group(item, code_sheet=code_sheet, section=section)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.post("/api/workbooks/{wid}/oqc-model-owners/bulk-rename")
def bulk_rename_oqc_model_owners(
    wid: str, body: OqcModelOwnerBulkRenameBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.bulk_rename_oqc_model_owners(
            item, code_sheet=body.code_sheet, old_owner=body.old_owner, new_owner=body.new_owner
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.post("/api/workbooks/{wid}/oqc-model-owners")
def add_oqc_model_owner(
    wid: str, body: OqcModelOwnerBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.create_oqc_model_owner(
            item, code_sheet=body.code_sheet, model=body.model, owner=body.owner
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.put("/api/workbooks/{wid}/oqc-model-owners/{model}")
def put_oqc_model_owner(
    wid: str, model: str, body: OqcModelOwnerUpdateBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.update_oqc_model_owner(
            item, code_sheet=body.code_sheet, old_model=body.old_model or model, model=body.model, owner=body.owner
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.delete("/api/workbooks/{wid}/oqc-model-owners/{model}")
def remove_oqc_model_owner(
    wid: str, model: str, code_sheet: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.delete_oqc_model_owner(item, code_sheet=code_sheet, model=model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.post("/api/workbooks/{wid}/oqc-section-heads")
def add_oqc_section_head(
    wid: str, body: OqcSectionHeadBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "create"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.create_oqc_section_head(
            item, code_sheet=body.code_sheet, section=body.section, head=body.head
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.put("/api/workbooks/{wid}/oqc-section-heads/{section}")
def put_oqc_section_head(
    wid: str, section: str, body: OqcSectionHeadUpdateBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.update_oqc_section_head(
            item, code_sheet=body.code_sheet, old_section=body.old_section or section, section=body.section, head=body.head
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.delete("/api/workbooks/{wid}/oqc-section-heads/{section}")
def remove_oqc_section_head(
    wid: str, section: str, code_sheet: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.delete_oqc_section_head(item, code_sheet=code_sheet, section=section)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.put("/api/workbooks/{wid}/oqc-section-head-groups")
def rename_oqc_section_head_group(
    wid: str, body: OqcSectionHeadGroupBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.rename_oqc_section_head_group(
            item, code_sheet=body.code_sheet, old_head=body.old_head, head=body.head
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.delete("/api/workbooks/{wid}/oqc-section-head-groups")
def remove_oqc_section_head_group(
    wid: str, head: str, code_sheet: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限修改代码表")
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    try:
        result = code_table_oqc.delete_oqc_section_head_group(item, code_sheet=code_sheet, head=head)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _commit_code_table_result(wid, item, result, current_user, db)
    return result


@app.get("/api/workbooks/{wid}/column-meta")
def workbook_column_meta(
    wid: str,
    sheet: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Column filter metadata (enum options, date ranges, lookup maps)."""
    if not check_project_permission(db, wid, current_user.id, "read"):
        raise HTTPException(403, "无权限")

    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")

    spec = item["spec"]
    sheet_spec = next((s for s in spec["sheets"] if s["name"] == sheet), None)
    if not sheet_spec:
        raise HTTPException(404, "找不到该工作表")

    df = item["frames"].get(sheet_name := sheet)
    if df is None:
        raise HTTPException(404, "该表无数据")

    meta = build_column_filter_meta(df, sheet_spec, item["frames"], all_sheets=spec.get("sheets"))
    return {"sheet": sheet_name, **meta}


@app.post("/api/workbooks/{wid}/preview-row")
def preview_entry(wid: str, body: RowBody,
                 current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Preview a row entry (requires entry permission)."""
    if not check_project_permission(db, wid, current_user.id, 'create'):
        raise HTTPException(403, "无权限")
    
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    sheet_name = body.sheet or item["spec"].get("primary_sheet")
    try:
        row = preview_row(item, sheet_name, body.values)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"row": row}


@app.post("/api/workbooks/{wid}/rows")
def add_row(wid: str, body: RowBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add new row to sheet (requires entry permission)."""
    if not check_project_permission(db, wid, current_user.id, 'create'):
        raise HTTPException(403, "无权限录入数据")
    
    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    raw_sheet = body.sheet or item["spec"].get("primary_sheet")
    sheet_name = resolve_sheet_name(raw_sheet, item["spec"], item["frames"]) or raw_sheet
    log(f"[add_row] wid={wid} user={current_user.id} raw_sheet={raw_sheet!r} sheet={sheet_name!r} values={body.values}")
    try:
        row = append_row(item, sheet_name, body.values)
    except ValueError as exc:
        log(f"[add_row] FAIL wid={wid} error={exc}")
        raise HTTPException(400, str(exc)) from exc
    
    # Save updated data back to database
    df = item["frames"].get(sheet_name)
    if df is None:
        for k in item["frames"]:
            if k.strip() == (sheet_name or "").strip():
                df = item["frames"][k]
                sheet_name = k
                break
    if df is None:
        log(f"[add_row] FAIL wid={wid} dataframe missing after append keys={list(item['frames'].keys())}")
        raise HTTPException(500, "写入内存成功但找不到数据表")
    ok = store.update_sheet_data(wid, sheet_name, df, current_user.id, db)
    if not ok:
        log(f"[add_row] FAIL wid={wid} update_sheet_data returned False")
        raise HTTPException(500, "保存到数据库失败")

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()
        log(f"[add_row] spec persisted row_count updated")
    
    sheet_spec = next((s for s in item["spec"]["sheets"] if s["name"] == sheet_name), None)
    log(f"[add_row] OK wid={wid} row_count={sheet_spec['row_count'] if sheet_spec else '?'} new 序号={row.get('序号')}")
    return {
        "row": row,
        "row_count": sheet_spec["row_count"],
        "form": sheet_spec.get("form"),
        "filters": sheet_spec.get("filters"),
    }


@app.patch("/api/workbooks/{wid}/rows")
def patch_row(
    wid: str,
    body: UpdateRowBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a single field on an existing row."""
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改数据")

    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    sheet_name = body.sheet or item["spec"].get("primary_sheet")
    try:
        row = update_row_field(
            item,
            sheet_name,
            body.row_key,
            body.row_id,
            body.field,
            body.value,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    df = item["frames"].get(sheet_name)
    store.update_sheet_data(wid, sheet_name, df, current_user.id, db)
    return {"row": row}


@app.put("/api/workbooks/{wid}/rows")
def put_row(
    wid: str,
    body: PutRowBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update multiple fields on an existing row."""
    if not check_project_permission(db, wid, current_user.id, "update"):
        raise HTTPException(403, "无权限修改数据")

    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    sheet_name = body.sheet or item["spec"].get("primary_sheet")
    try:
        row = update_row_values(
            item,
            sheet_name,
            body.row_key,
            body.row_id,
            body.values,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    df = item["frames"].get(sheet_name)
    if df is None:
        for k in item["frames"]:
            if k.strip() == (sheet_name or "").strip():
                df = item["frames"][k]
                sheet_name = k
                break
    store.update_sheet_data(wid, sheet_name, df, current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    sheet_spec = next((s for s in item["spec"]["sheets"] if s["name"] == sheet_name), None)
    return {
        "row": row,
        "row_count": sheet_spec["row_count"] if sheet_spec else len(df),
    }


@app.delete("/api/workbooks/{wid}/rows")
def remove_row(
    wid: str,
    body: DeleteRowBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a row from a sheet."""
    if not check_project_permission(db, wid, current_user.id, "delete"):
        raise HTTPException(403, "无权限删除数据")

    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")
    sheet_name = body.sheet or item["spec"].get("primary_sheet")
    try:
        if body.rows:
            row_count = delete_rows(
                item,
                sheet_name,
                body.row_key,
                [r.model_dump() for r in body.rows],
            )
        else:
            if body.db_id is None and body.row_id is None:
                raise HTTPException(400, "须指定 row_id 或 db_id")
            row_count = delete_row(
                item,
                sheet_name,
                body.row_key,
                body.row_id,
                db_id=body.db_id,
            )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    df = item["frames"].get(sheet_name)
    if df is None:
        for k in item["frames"]:
            if k.strip() == (sheet_name or "").strip():
                df = item["frames"][k]
                sheet_name = k
                break
    store.update_sheet_data(wid, sheet_name, df, current_user.id, db)

    project = db.query(Project).filter(Project.project_id == wid).first()
    if project:
        project.spec = item["spec"]
        db.commit()

    return {"row_count": row_count}


@app.get("/api/workbooks/{wid}/export")
def export_workbook_get(
    wid: str,
    background_tasks: BackgroundTasks,
    sheet: str | None = None,
    mode: str = "merged",
    all_sheets: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export workbook to Excel (requires read permission)."""
    if all_sheets:
        mode = "all"
    return _export_workbook(wid, ExportBody(mode=mode, sheet=sheet), background_tasks, current_user, db)


@app.post("/api/workbooks/{wid}/export")
def export_workbook_post(
    wid: str,
    body: ExportBody,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export with filters (e.g. current table view)."""
    return _export_workbook(wid, body, background_tasks, current_user, db)


def _remove_export_file(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _export_workbook(
    wid: str,
    body: ExportBody,
    background_tasks: BackgroundTasks | None,
    current_user: User,
    db: Session,
):
    if not check_project_permission(db, wid, current_user.id, 'read'):
        raise HTTPException(403, "无权限访问此项目")

    item = store.get(wid, db)
    if not item:
        raise HTTPException(404, "工作簿不存在或已过期")

    spec = item["spec"]
    frames = item["frames"]
    mode = body.mode or "merged"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()

    try:
        if mode == "filtered":
            if not body.sheet:
                raise HTTPException(400, "filtered 模式须指定 sheet")
            sheet_name = resolve_sheet_name(body.sheet, spec, frames)
            df = frames.get(sheet_name)
            if df is None:
                raise HTTPException(404, "该表无数据")
            filtered = apply_filters(df, body.filters)
            filtered = apply_sort(filtered, body.sort.model_dump() if body.sort else None)
            export_workbook_xlsx({sheet_name: filtered}, [sheet_name], tmp.name, spec)
        elif mode == "all":
            sheet_names = [s.get("name") for s in spec.get("sheets") or [] if s.get("name") in frames]
            if not sheet_names:
                sheet_names = list(frames.keys())
            export_workbook_xlsx(frames, sheet_names, tmp.name, spec)
        elif mode == "sheet":
            sheet_name = resolve_sheet_name(body.sheet or spec.get("primary_sheet"), spec, frames)
            df = frames.get(sheet_name) if sheet_name else None
            if df is None:
                raise HTTPException(404, "该表无数据")
            export_sheet_xlsx(df, sheet_name, tmp.name, spec)
        else:
            sheet_names = merged_export_sheet_names(spec, frames)
            export_workbook_xlsx(frames, sheet_names, tmp.name, spec)
    except ValueError as exc:
        _remove_export_file(tmp.name)
        raise HTTPException(400, str(exc)) from exc

    filename = f"{spec.get('title') or 'merged'}-合并.xlsx"
    if background_tasks is not None:
        background_tasks.add_task(_remove_export_file, tmp.name)
    return FileResponse(
        tmp.name,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        return FileResponse(DIST / "index.html")
