import asyncio
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager

from .config import get_settings


class CoordinationBusy(RuntimeError):
    pass


class CoordinationUnavailable(RuntimeError):
    pass


class Coordination:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis = None
        self._local_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def redis(self):
        if self._redis is None:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(self.settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        return self._redis

    async def ping(self) -> bool:
        try:
            return bool(await (await self.redis()).ping())
        except Exception:
            return False

    @asynccontextmanager
    async def lock(self, key: str, ttl_seconds: int = 120):
        token = str(uuid.uuid4())
        redis_key = f"orbit:lock:{key}"
        client = None
        acquired = False
        try:
            client = await self.redis()
            acquired = await client.set(redis_key, token, nx=True, ex=ttl_seconds)
            if not acquired:
                raise CoordinationBusy("Operation is already running for this incident")
        except CoordinationBusy:
            raise
        except Exception:
            if self.settings.redis_required:
                raise CoordinationUnavailable("Redis coordination is unavailable")
        if acquired and client is not None:
            try:
                yield
            finally:
                await client.eval("if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end", 1, redis_key, token)
            return
        local = self._local_locks[key]
        if local.locked():
            raise CoordinationBusy("Operation is already running for this incident")
        async with local:
            yield

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()


coordination = Coordination()
