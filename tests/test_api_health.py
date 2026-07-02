"""
Smoke test for the FastAPI app — no DB required.
Uses TestClient (sync ASGI wrapper) to avoid asyncio complexity in CI.
"""
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


def _make_client():
    # Patch DB engine creation so we don't need a real Postgres
    with patch("app.db.create_async_engine"):
        from app.main import app
        return TestClient(app, raise_server_exceptions=True)


def test_health():
    client = _make_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
