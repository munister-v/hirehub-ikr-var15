"""Менеджер WebSocket-з'єднань: статуси заявок розсилаються кандидатам у реальному часі."""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, max_per_candidate: int = 5):
        self.max_per_candidate = max_per_candidate
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    def count(self, candidate_id: int) -> int:
        return len(self._connections.get(candidate_id, ()))

    async def connect(self, candidate_id: int, websocket: WebSocket) -> bool:
        async with self._lock:
            if self.count(candidate_id) >= self.max_per_candidate:
                return False
            self._connections[candidate_id].add(websocket)
            return True

    async def disconnect(self, candidate_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.get(candidate_id, set()).discard(websocket)
            if not self._connections.get(candidate_id):
                self._connections.pop(candidate_id, None)

    async def publish(self, candidate_id: int, message: dict) -> int:
        """Надсилає повідомлення всім сокетам кандидата; повертає кількість доставлених."""
        delivered = 0
        for websocket in list(self._connections.get(candidate_id, ())):
            try:
                await websocket.send_json(message)
                delivered += 1
            except Exception:  # noqa: BLE001 — «мертвий» сокет прибираємо
                logger.info('Сокет кандидата %s закрито', candidate_id)
                await self.disconnect(candidate_id, websocket)
        return delivered
