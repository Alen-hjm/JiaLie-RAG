import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_minglie.db")
os.environ.setdefault("MODEL_MODE", "mock")
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings


def test_login_health_and_auth():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.post("/api/auth/login", json={"username": get_settings().admin_username, "password": get_settings().admin_password})
        assert response.status_code == 200
        assert client.get("/api/dashboard").status_code == 200

