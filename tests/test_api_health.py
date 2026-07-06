"""
Smoke tests for GET /health — no real DB required.
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    with patch("app.db.create_async_engine"):
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)


def _mock_session(ok: bool):
    sess = AsyncMock()
    if not ok:
        sess.execute = AsyncMock(side_effect=Exception("no db"))
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    return sess


def test_health_ok(client):
    with patch("app.main.AsyncSessionLocal", return_value=_mock_session(ok=True)):
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] is True


def test_health_degraded_when_db_down(client):
    with patch("app.main.AsyncSessionLocal", return_value=_mock_session(ok=False)):
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] is False
