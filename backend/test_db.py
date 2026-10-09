from app.db import init_database, get_db_session
from app.models import User

init_database()
db = get_db_session()
try:
    users = db.query(User).all()
    print(f'Found {len(users)} users:')
    for u in users:
        print(f'  - {u.username} ({u.role})')
finally:
    db.close()
