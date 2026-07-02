import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy import text

from app.api.routers import admin, plahta, reports, reservations, rooms
from app.api.websocket import manager
from app.db import AsyncSessionLocal
from app.services.email_ingest import email_poll_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_poll_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _poll_task
    # In production the email-worker container handles polling.
    # RUN_EMAIL_WORKER=true enables the embedded loop (useful for dev/single-container setups).
    if os.getenv("RUN_EMAIL_WORKER", "false").lower() == "true":
        _poll_task = asyncio.create_task(email_poll_loop())
        logger.info("Embedded email poll loop started")
    yield
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Hotel Kotnik Backend", lifespan=lifespan)

app.include_router(reservations.router)
app.include_router(rooms.router)
app.include_router(plahta.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.websocket("/ws/events")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.get("/health")
async def health():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
