"""Atomic shared admission budgets for submitted login identities."""

from collections.abc import AsyncIterator, Awaitable
from hashlib import sha256
from secrets import token_hex
from typing import Any, cast

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from app.core.config import settings


class RedisLoginRateLimiter:
    """Admit attempts only when both sliding windows have available capacity."""

    _SCRIPT = """
local clock = redis.call('TIME')
local now = clock[1] * 1000 + math.floor(clock[2] / 1000)
local window = tonumber(ARGV[1])
local retry = 0
for i = 1, 2 do
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now - window)
    if redis.call('ZCARD', KEYS[i]) >= tonumber(ARGV[i + 1]) then
        local oldest = redis.call('ZRANGE', KEYS[i], 0, 0, 'WITHSCORES')
        retry = math.max(retry, tonumber(oldest[2]) + window - now)
    end
end
if retry > 0 then
    return math.ceil(retry / 1000)
end
for i = 1, 2 do
    redis.call('ZADD', KEYS[i], now, ARGV[4])
    redis.call('PEXPIRE', KEYS[i], window)
end
return 0
"""

    def __init__(self, redis_client: Redis) -> None:
        self.redis_client = redis_client

    async def check(self, client_address: str, username: str) -> None:
        """Charge an admitted attempt, or raise a temporary HTTP rejection."""
        # Login compares usernames exactly; do not trim or case-fold here.
        account_key = sha256(username.encode("utf-8")).hexdigest()
        try:
            retry_after = int(
                await cast(
                    Awaitable[Any],
                    self.redis_client.eval(
                        self._SCRIPT,
                        2,
                        f"owlculus:login-rate-limit:ip:{client_address}",
                        f"owlculus:login-rate-limit:account:{account_key}",
                        str(settings.LOGIN_LIMIT_WINDOW_SECONDS * 1000),
                        str(settings.LOGIN_IP_MAX_ATTEMPTS),
                        str(settings.LOGIN_ACCOUNT_MAX_ATTEMPTS),
                        token_hex(16),
                    ),
                )
            )
        except (OSError, RedisError):
            raise HTTPException(
                503,
                "Login is temporarily unavailable. Please retry shortly.",
                headers={"Retry-After": "5"},
            ) from None
        if retry_after:
            raise HTTPException(
                429,
                "Too many login attempts. Please retry later.",
                headers={"Retry-After": str(retry_after)},
            )


async def get_login_rate_limiter() -> AsyncIterator[RedisLoginRateLimiter]:
    """Bound Redis I/O and close request-owned connections on every exit path."""
    async with Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=1,
        socket_timeout=1,
        retry=Retry(NoBackoff(), 0),
    ) as redis:
        yield RedisLoginRateLimiter(redis)
