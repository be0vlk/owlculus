"""Shared sliding-window admission budgets for security-sensitive public endpoints."""

from collections.abc import AsyncIterator, Awaitable
from hashlib import sha256
from secrets import token_hex
from typing import Any, cast

from redis import Redis as SyncRedis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import RateLimitException, ServiceUnavailableException
from app.core.redis_health import bounded_redis, storage_ready

_readiness_redis = bounded_redis(settings.AUTH_REDIS_URL, SyncRedis)


def is_rate_limit_storage_ready() -> bool:
    """Check allocating writes without changing real admission budgets."""
    return storage_ready(_readiness_redis, "authentication")


class SlidingWindowLimiter:
    """Charge one attempt to every key only when all their windows have capacity."""

    # Redis 7 flagged scripts reject OOM before any counter mutation.
    _SCRIPT = """#!lua
local clock = redis.call('TIME')
local now = clock[1] * 1000 + math.floor(clock[2] / 1000)
local window = tonumber(ARGV[1])
local retry = 0
for i = 1, #KEYS do
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now - window)
    if redis.call('ZCARD', KEYS[i]) >= tonumber(ARGV[i + 1]) then
        local oldest = redis.call('ZRANGE', KEYS[i], 0, 0, 'WITHSCORES')
        retry = math.max(retry, tonumber(oldest[2]) + window - now)
    end
end
if retry > 0 then
    return math.ceil(retry / 1000)
end
for i = 1, #KEYS do
    redis.call('ZADD', KEYS[i], now, ARGV[#KEYS + 2])
    redis.call('PEXPIRE', KEYS[i], window)
end
return 0
"""
    _UNAVAILABLE: str

    def __init__(self, redis_client: Redis) -> None:
        self.redis_client = redis_client

    async def _retry_after(self, window_seconds: int, limits: dict[str, int]) -> int:
        """Seconds until every key has capacity, or 0 once the attempt is charged."""
        try:
            return int(
                await cast(
                    Awaitable[Any],
                    self.redis_client.eval(
                        self._SCRIPT,
                        len(limits),
                        *limits,
                        str(window_seconds * 1000),
                        *map(str, limits.values()),
                        token_hex(16),
                    ),
                )
            )
        except (OSError, RedisError):
            raise ServiceUnavailableException(
                self._UNAVAILABLE, retry_after=5
            ) from None


class RedisClientRateLimiter(SlidingWindowLimiter):
    """Bootstrap attempts per client, shared across API processes and restarts."""

    _UNAVAILABLE = "Setup is temporarily unavailable. Please retry shortly."

    def __init__(
        self, redis_client: Redis, *, max_attempts: int = 3, window_seconds: int = 3600
    ) -> None:
        super().__init__(redis_client)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    async def allow(self, client_address: str) -> bool:
        key = f"owlculus:bootstrap-rate-limit:{client_address}"
        return not await self._retry_after(
            self.window_seconds, {key: self.max_attempts}
        )


class RedisLoginRateLimiter(SlidingWindowLimiter):
    """Admit login attempts only when both the IP and account windows have room."""

    _UNAVAILABLE = "Login is temporarily unavailable. Please retry shortly."

    async def check(self, client_address: str, username: str) -> None:
        """Charge an admitted attempt, or raise a temporary HTTP rejection."""
        # Login compares usernames exactly; do not trim or case-fold here.
        account_key = sha256(username.encode("utf-8")).hexdigest()
        retry_after = await self._retry_after(
            settings.LOGIN_LIMIT_WINDOW_SECONDS,
            {
                f"owlculus:login-rate-limit:ip:{client_address}": settings.LOGIN_IP_MAX_ATTEMPTS,
                f"owlculus:login-rate-limit:account:{account_key}": settings.LOGIN_ACCOUNT_MAX_ATTEMPTS,
            },
        )
        if retry_after:
            raise RateLimitException(
                "Too many login attempts. Please retry later.",
                retry_after=retry_after,
            )


async def get_login_rate_limiter() -> AsyncIterator[RedisLoginRateLimiter]:
    """Bound Redis I/O and close request-owned connections on every exit path."""
    async with bounded_redis(settings.AUTH_REDIS_URL, Redis) as redis:
        yield RedisLoginRateLimiter(redis)
