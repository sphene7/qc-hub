from app.db import init_database, get_db_session
from app.auth import authenticate_user, create_access_token

init_database()
db = get_db_session()
try:
    print("Testing authentication...")
    user = authenticate_user(db, 'admin', 'admin123')
    if user:
        print(f"✓ User authenticated: {user.username}")
        token = create_access_token(user.id, user.username, user.role)
        print(f"✓ Token created: {token[:50]}...")
    else:
        print("✗ Authentication failed")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
