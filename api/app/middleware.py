import hashlib
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings


class ProductionGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.local_counts: dict[tuple[str, int], int] = defaultdict(int)
        self._redis = None

    def identity(self, request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        raw = authorization if authorization else (request.client.host if request.client else "unknown")
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    async def limited(self, request: Request) -> bool:
        if request.url.path in {"/health", "/ready"} or request.url.path.startswith("/metrics"):
            return False
        minute = int(time.time() // 60)
        identity = self.identity(request)
        key = f"orbit:rate:{identity}:{minute}"
        try:
            if self._redis is None:
                from redis.asyncio import Redis
                self._redis = Redis.from_url(self.settings.redis_url, decode_responses=True, socket_connect_timeout=1)
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 90)
            return count > self.settings.rate_limit_requests_per_minute
        except Exception:
            if self.settings.redis_required:
                return True
            local_key = (identity, minute)
            self.local_counts[local_key] += 1
            if len(self.local_counts) > 10_000:
                self.local_counts = defaultdict(int, {item: value for item, value in self.local_counts.items() if item[1] >= minute - 1})
            return self.local_counts[local_key] > self.settings.rate_limit_requests_per_minute

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.settings.max_request_body_bytes:
                    return JSONResponse({"detail": "Request body is too large"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length header"}, status_code=400)
        if await self.limited(request):
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=()"
        if self.settings.environment != "development":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
