import asyncio
import json
import logging
import uuid
from collections import defaultdict

from fastapi import WebSocket

from .config import get_settings


CHANNEL = "orbit:incident-events"
logger = logging.getLogger("orbit.realtime")


class IncidentSocketHub:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.instance_id = str(uuid.uuid4())
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._redis = None
        self._listener_task: asyncio.Task | None = None

    async def start(self) -> None:
        try:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(self.settings.redis_url, decode_responses=True, socket_connect_timeout=2)
            await self._redis.ping()
            self._listener_task = asyncio.create_task(self._listen())
        except Exception:
            self._redis = None
            if self.settings.redis_required:
                raise RuntimeError("Redis real-time transport is required but unavailable")
            logger.warning("Redis unavailable; WebSocket events are local to this API process")

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.aclose()

    async def _listen(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for raw in pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(raw["data"])
                    if envelope.get("origin") != self.instance_id:
                        await self._send_local(envelope["incident_id"], envelope["message"])
                except (KeyError, ValueError, TypeError):
                    logger.warning("Discarded malformed Redis real-time event")
        finally:
            await pubsub.aclose()

    async def connect(self, incident_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[incident_id].add(websocket)

    def disconnect(self, incident_id: str, websocket: WebSocket) -> None:
        self.connections[incident_id].discard(websocket)
        if not self.connections[incident_id]:
            self.connections.pop(incident_id, None)

    async def _send_local(self, incident_id: str, message: str) -> None:
        dead: list[WebSocket] = []
        for websocket in tuple(self.connections.get(incident_id, ())):
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(incident_id, websocket)

    async def publish(self, incident_id: str, event_type: str, payload: dict) -> None:
        message = json.dumps({"type": event_type, "payload": payload})
        await self._send_local(incident_id, message)
        if self._redis:
            try:
                await self._redis.publish(CHANNEL, json.dumps({"origin": self.instance_id, "incident_id": incident_id, "message": message}))
            except Exception:
                if self.settings.redis_required:
                    raise
                logger.exception("Redis publish failed; local clients were still notified")


hub = IncidentSocketHub()
