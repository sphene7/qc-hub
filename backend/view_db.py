"""
Quick script to view database contents
"""
from app.db import init_database, get_db_session
from app.models import User, Project, ProjectMember, SheetData
from sqlalchemy import func

init_database()
db = get_db_session()

try:
    print("=" * 60)
    print("用户列表")
    print("=" * 60)
    users = db.query(User).all()
    for u in users:
        print(f"ID: {u.id}, 用户名: {u.username}, 角色: {u.role}, 邮箱: {u.email}")
    
    print("\n" + "=" * 60)
    print("项目列表")
    print("=" * 60)
    projects = db.query(Project).all()
    for p in projects:
        print(f"ID: {p.project_id}, 名称: {p.name}, 所有者ID: {p.owner_id}")
        print(f"  创建时间: {p.created_at}")
        
        # 统计数据行数
        row_count = db.query(func.count(SheetData.id)).filter(
            SheetData.project_id == p.id
        ).scalar()
        print(f"  数据行数: {row_count}")
        
        # 成员
        members = db.query(ProjectMember).filter(ProjectMember.project_id == p.id).all()
        if members:
            print(f"  成员数: {len(members)}")
        print()
    
    print("=" * 60)
    print("数据统计")
    print("=" * 60)
    
    # 按项目和sheet统计
    stats = db.query(
        SheetData.project_id,
        SheetData.sheet_name,
        func.count(SheetData.id).label('count')
    ).group_by(SheetData.project_id, SheetData.sheet_name).all()
    
    for stat in stats:
        project = db.query(Project).filter(Project.id == stat.project_id).first()
        print(f"项目: {project.name if project else 'Unknown'}, "
              f"工作表: {stat.sheet_name}, 行数: {stat.count}")

finally:
    db.close()

print("\n✓ 完成")
