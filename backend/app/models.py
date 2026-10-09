"""
Database models for Excel-to-Web system with authentication and project management.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, JSON
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
    permissions = Column(JSON, nullable=True)  # {create, read, update, delete}
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
