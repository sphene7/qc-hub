from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("Testing /api/auth/login endpoint...")
try:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
