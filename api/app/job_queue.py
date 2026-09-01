import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import get_settings


STREAM = "orbit:jobs"
DEAD_LETTER_STREAM = "orbit:jobs:dead-letter"
RETRY_SET = "orbit:jobs:retry"
GROUP = "orbit-workers"


@dataclass(frozen=True)
class QueuedJob:
    id: str
    kind: str


class JobQueue:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis = None

    async def redis(self):
        if self._redis is None:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(self.settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        return self._redis

    async def ensure_group(self) -> None:
        client = await self.redis()
        try:
            await client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, kind: str, payload: dict, requested_by: str) -> QueuedJob:
        client = await self.redis()
        job_id = str(uuid.uuid4())
        await client.xadd(STREAM, {"job_id": job_id, "kind": kind, "payload": json.dumps(payload), "attempt": "0", "requested_by": requested_by, "created_at": datetime.now(timezone.utc).isoformat()}, maxlen=self.settings.job_stream_max_length, approximate=True)
        return QueuedJob(job_id, kind)

    async def dead_letter(self, fields: dict, error: str) -> None:
        client = await self.redis()
        await client.xadd(DEAD_LETTER_STREAM, {**fields, "error": error[:2000], "failed_at": datetime.now(timezone.utc).isoformat()}, maxlen=self.settings.job_stream_max_length, approximate=True)

    async def schedule_retry(self, fields: dict, delay_seconds: int) -> None:
        client = await self.redis()
        await client.zadd(RETRY_SET, {json.dumps(fields, sort_keys=True): time.time() + delay_seconds})

    async def promote_due_retries(self) -> int:
        client = await self.redis()
        due = await client.zrangebyscore(RETRY_SET, min=0, max=time.time(), start=0, num=100)
        promoted = 0
        for encoded in due:
            if await client.zrem(RETRY_SET, encoded):
                fields = json.loads(encoded)
                await client.xadd(STREAM, fields, maxlen=self.settings.job_stream_max_length, approximate=True)
                promoted += 1
        return promoted

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()


job_queue = JobQueue()
