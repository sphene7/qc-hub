#!/bin/sh
set -e

echo "Waiting for MySQL at ${DB_HOST}:${DB_PORT}..."
until python - <<'PY'
import os, sys, time
import pymysql
host = os.environ.get("DB_HOST", "mysql")
port = int(os.environ.get("DB_PORT", "3306"))
user = os.environ.get("DB_USER", "root")
password = os.environ.get("DB_PASSWORD", "")
for i in range(60):
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=password)
        conn.close()
        sys.exit(0)
    except Exception:
        time.sleep(2)
sys.exit(1)
PY
do
  sleep 2
done

echo "Initializing database..."
python - <<'PY'
from app.db import init_database
init_database()
print("Database ready.")
PY

if [ -f /data/bundle.json ]; then
  echo "Checking bundle import..."
  python - <<'PY'
from pathlib import Path
from app.db import get_db_session
from app.models import Project

bundle = Path("/data/bundle.json")
db = get_db_session()
try:
    count = db.query(Project).count()
finally:
    db.close()

if count == 0 and bundle.is_file():
    print("Importing bundle.json ...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "scripts/import_bundle.py", str(bundle)])
else:
    print(f"Skip import (projects={count}, bundle={bundle.is_file()})")
PY
fi

python - <<'PY'
from app.db import get_db_session
from app.models import User
from app.auth import create_user

db = get_db_session()
try:
    if not db.query(User).filter(User.username == "admin").first():
        create_user(db, "admin", "admin123", email="admin@example.com", full_name="系统管理员", role="super_admin")
        print("Created default admin (admin / admin123) — change password after first login.")
finally:
    db.close()
PY

echo "Starting API server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
