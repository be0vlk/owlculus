"""Application rate limits for security-sensitive public endpoints."""

from collections import deque
from secrets import token_hex
from threading import Lock
from time import monotonic
from typing import Protocol

from app.core.config import settings
from fastapi import Request
from redis import Redis as SyncRedis
from redis.asyncio import Redis
from redis.exceptions import RedisError


class ClientRateLimiter(Protocol):
    """Rate-limit storage boundary used by the bootstrap route."""

    async def allow(self, client_address: str) -> bool:
        """Return whether this attempt is within the configured limit."""


class InMemoryClientRateLimiter:
    """Track a bounded number of attempts per client in a sliding time window."""

    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts_by_client: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._last_cleanup = monotonic()

    async def allow(self, client_address: str) -> bool:
        """Record an allowed attempt, or reject when the client's window is full."""
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            attempt_timestamps = self._attempts_by_client.setdefault(
                client_address, deque()
            )
            while attempt_timestamps and attempt_timestamps[0] <= cutoff:
                attempt_timestamps.popleft()

            if len(attempt_timestamps) >= self.max_attempts:
                return False

            attempt_timestamps.append(now)
            self._cleanup_expired_clients(cutoff, now)
            return True

    def _cleanup_expired_clients(self, cutoff: float, now: float) -> None:
        if now - self._last_cleanup < self.window_seconds:
            return

        self._attempts_by_client = {
            client: attempts
            for client, attempts in self._attempts_by_client.items()
            if attempts and attempts[-1] > cutoff
        }
        self._last_cleanup = now


class RedisClientRateLimiter:
    """Share sliding-window attempt counters across API processes and restarts."""

    _ALLOW_ATTEMPT_SCRIPT = """
local redis_time = redis.call('TIME')
local now = redis_time[1] * 1000 + math.floor(redis_time[2] / 1000)
local cutoff = now - tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then
    return 0
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], ARGV[1])
return 1
"""

    def __init__(
        self, redis_client: Redis, *, max_attempts: int, window_seconds: int
    ) -> None:
        self.redis_client = redis_client
        self.max_attempts = max_attempts
        self.window_milliseconds = window_seconds * 1000

    async def allow(self, client_address: str) -> bool:
        """Atomically record one attempt in a Redis-backed sliding window."""
        result = await self.redis_client.eval(
            self._ALLOW_ATTEMPT_SCRIPT,
            1,
            f"owlculus:bootstrap-rate-limit:{client_address}",
            self.window_milliseconds,
            self.max_attempts,
            token_hex(16),
        )
        return bool(result)


_limiter_creation_lock = Lock()
_readiness_redis = SyncRedis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def is_rate_limit_storage_ready() -> bool:
    """Return whether the shared rate-limit store accepts commands."""
    try:
        return bool(_readiness_redis.ping())
    except (OSError, RedisError):
        return False


def get_bootstrap_rate_limiter(request: Request) -> ClientRateLimiter:
    """Return the limiter scoped to the current ASGI application instance."""
    limiter = getattr(request.app.state, "bootstrap_rate_limiter", None)
    if limiter is not None:
        return limiter

    with _limiter_creation_lock:
        limiter = getattr(request.app.state, "bootstrap_rate_limiter", None)
        if limiter is None:
            limiter = RedisClientRateLimiter(
                Redis.from_url(settings.REDIS_URL),
                max_attempts=3,
                window_seconds=60 * 60,
            )
            request.app.state.bootstrap_rate_limiter = limiter
        return limiter
