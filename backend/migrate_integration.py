"""
Migration script to add integration_config column to projects table
"""
from app.db import init_database, get_db_session
from sqlalchemy import text

init_database()
db = get_db_session()

try:
    print("Adding integration_config column to projects table...")
    
    # Check if column already exists
    result = db.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = 'excel_to_web' 
        AND TABLE_NAME = 'projects' 
        AND COLUMN_NAME = 'integration_config'
    """))
    
    exists = result.scalar() > 0
    
    if exists:
        print("Column already exists, skipping.")
    else:
        # Add the column
        db.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN integration_config JSON NULL
        """))
        db.commit()
        print("✓ Column added successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()

print("\n✓ Migration complete!")
