"""
Seed script to create initial test users.
Run this once to set up the system with test accounts.
"""
from app.db import init_database, get_db_session
from app.auth import create_user
from app.models import User

def seed_users():
    """Create test users."""
    # Initialize database
    init_database()
    
    db = get_db_session()
    try:
        # Check if super admin already exists
        existing = db.query(User).filter(User.username == 'admin').first()
        if existing:
            print("Super admin 'admin' already exists.")
        else:
            # Create super admin
            admin = create_user(
                db,
                username='admin',
                password='admin123',
                email='admin@example.com',
                full_name='系统管理员',
                role='super_admin'
            )
            print(f"✓ Created super admin: {admin.username} (password: admin123)")
        
        # Check if test user exists
        existing = db.query(User).filter(User.username == 'user1').first()
        if existing:
            print("Test user 'user1' already exists.")
        else:
            # Create regular test user
            user = create_user(
                db,
                username='user1',
                password='user123',
                email='user1@example.com',
                full_name='测试用户1',
                role='user'
            )
            print(f"✓ Created test user: {user.username} (password: user123)")
        
        # Check if test user 2 exists
        existing = db.query(User).filter(User.username == 'user2').first()
        if existing:
            print("Test user 'user2' already exists.")
        else:
            # Create another test user
            user2 = create_user(
                db,
                username='user2',
                password='user123',
                email='user2@example.com',
                full_name='测试用户2',
                role='user'
            )
            print(f"✓ Created test user: {user2.username} (password: user123)")
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()
    
    print("\n✓ Database seeded successfully!")
    print("\nTest Accounts:")
    print("  Super Admin: admin / admin123")
    print("  User 1: user1 / user123")
    print("  User 2: user2 / user123")

if __name__ == '__main__':
    seed_users()
