import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)
        logger.info("WS client connected, total=%d", len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._active:
            self._active.remove(ws)
        logger.info("WS client disconnected, total=%d", len(self._active))

    async def broadcast(self, event_type: str, data: dict) -> None:
        if not self._active:
            return
        payload = json.dumps({"type": event_type, "data": data}, default=str)
        dead = []
        for ws in list(self._active):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._active.remove(ws)


manager = ConnectionManager()
