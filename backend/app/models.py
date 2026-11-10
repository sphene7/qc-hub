"""
Database models for Excel-to-Web system with authentication and project management.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey, Index, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """User accounts with roles."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), default='user', nullable=False)  # 'super_admin', 'user'
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owned_projects = relationship('Project', back_populates='owner', foreign_keys='Project.owner_id')
    memberships = relationship('ProjectMember', back_populates='user', cascade='all, delete-orphan')


class Project(Base):
    """Projects (Excel workbooks) with metadata."""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), unique=True, nullable=False, index=True)  # Short unique ID (e.g., wid)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    spec = Column(JSON, nullable=False)  # Full workbook spec as JSON
    integration_config = Column(JSON, nullable=True)  # Integration preferences
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship('User', back_populates='owned_projects', foreign_keys=[owner_id])
    members = relationship('ProjectMember', back_populates='project', cascade='all, delete-orphan')
    sheet_data = relationship('SheetData', back_populates='project', cascade='all, delete-orphan')


class ProjectMember(Base):
    """User membership and permissions within a project."""
    __tablename__ = 'project_members'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role = Column(String(20), default='read', nullable=False)  # 'admin', 'entry', 'read'
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=True, index=True)
    permissions = Column(JSON, nullable=True)  # {create, read, update, delete, submit, inspect, handle, dept}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship('Project', back_populates='members')
    user = relationship('User', back_populates='memberships')
    
    # Unique constraint: one role per user per project
    __table_args__ = (
        Index('idx_project_user', 'project_id', 'user_id', unique=True),
    )


class SheetData(Base):
    """Data rows for project sheets."""
    __tablename__ = 'sheet_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    sheet_name = Column(String(100), nullable=False)
    row_data = Column(JSON, nullable=False)  # Full row as JSON (dict)
    source = Column(String(20), default='imported', nullable=False)  # 'imported', 'entered'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # NULL for imported
    
    # Relationships
    project = relationship('Project', back_populates='sheet_data')
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_project_sheet', 'project_id', 'sheet_name'),
    )


class Department(Base):
    """组织部门 / 课室。送检范围的归属单位。"""
    __tablename__ = 'departments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey('departments.id'), nullable=True, index=True)
    leader = Column(String(100), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ==================== 抽检业务表（强类型，替代 sheet_data JSON） ====================

class SamplingSubmission(Base):
    """送检单：一批送检一张单。"""
    __tablename__ = 'sampling_submissions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    code = Column(String(40), unique=True, nullable=False, index=True)
    submit_date = Column(DateTime, nullable=False, index=True)  # 送检日期（精确到分）
    month_label = Column(String(20), nullable=True)
    part_no = Column(String(100), nullable=True, index=True)  # 部番（完整，含 -）
    model = Column(String(100), nullable=True)                # 机种（部番 - 前）
    series = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True, index=True)
    business_unit = Column(String(50), nullable=True, index=True)  # 事业部（部番对照）
    submit_type = Column(String(50), nullable=True)  # 送检类型：正常送检 / 返工送检 …
    qty = Column(Integer, nullable=True)
    batch_seq = Column(Integer, nullable=True)
    urgent = Column(String(10), nullable=True)
    remark = Column(Text, nullable=True)
    confirmer = Column(String(50), nullable=True)
    room_owner = Column(String(50), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    inspections = relationship('SamplingInspection', back_populates='submission', cascade='all, delete-orphan')


class SamplingInspection(Base):
    """抽检记录：一条 = 一名检验员对一张送检单的抽检。"""
    __tablename__ = 'sampling_inspections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('sampling_submissions.id'), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    inspector = Column(String(50), nullable=True, index=True)
    appearance_qty = Column(Integer, nullable=True)
    function_qty = Column(Integer, nullable=True)
    defect_qty = Column(Integer, nullable=True)
    defect_rate = Column(String(20), nullable=True)
    batch_sent = Column(Integer, nullable=True)
    batch_pass = Column(Integer, nullable=True)
    batch_rate = Column(String(20), nullable=True)
    verdict = Column(String(20), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    submission = relationship('SamplingSubmission', back_populates='inspections')
    defects = relationship('SamplingDefect', back_populates='inspection', cascade='all, delete-orphan')
    exception = relationship('SamplingException', back_populates='inspection', uselist=False,
                             cascade='all, delete-orphan')


class SamplingDefect(Base):
    """不良明细：一条 = 一种不良。"""
    __tablename__ = 'sampling_defects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey('sampling_inspections.id'), nullable=False, index=True)
    attr = Column(String(20), nullable=True)
    location = Column(String(100), nullable=True)
    phenomenon = Column(String(100), nullable=True)
    qty = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    inspection = relationship('SamplingInspection', back_populates='defects')


class SamplingException(Base):
    """异常处理：一条抽检最多一条。"""
    __tablename__ = 'sampling_exceptions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey('sampling_inspections.id'), nullable=False, unique=True, index=True)
    oa_no = Column(String(50), nullable=True)
    qc_company = Column(String(100), nullable=True)
    owner_dept = Column(String(100), nullable=True)
    owner = Column(String(50), nullable=True)
    temp_action = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    perm_action = Column(Text, nullable=True)
    verify = Column(Text, nullable=True)
    close_date = Column(Date, nullable=True)
    close_days = Column(Integer, nullable=True)
    confirmer = Column(String(50), nullable=True)          # 确认者
    room_owner = Column(String(50), nullable=True)         # 课室负责人
    dept_head = Column(String(50), nullable=True)          # 责任课级负责人
    quality_engineer = Column(String(50), nullable=True)   # 品质工程师
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    inspection = relationship('SamplingInspection', back_populates='exception')


class AuditLog(Base):
    """审计日志：谁在什么时候改了什么。"""
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    entity = Column(String(40), nullable=False, index=True)
    entity_id = Column(String(50), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    changes = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Role(Base):
    """角色：一套权限点，用户按项目套用。"""
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(200), nullable=True)
    permissions = Column(JSON, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class ModelBusinessUnit(Base):
    """部番 → 事业部 对照表（来源：OQC 表格对应表）。"""
    __tablename__ = 'model_bu_map'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), unique=True, nullable=False, index=True)  # 部番
    base_model = Column(String(50), nullable=True, index=True)            # "-" 前的基型
    business_unit = Column(String(50), nullable=False, index=True)        # 事业部
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
