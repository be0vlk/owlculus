"""Bounded allocating probes, isolated from counters, queues, and event streams."""

from secrets import token_hex

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

# Each key expires even if a subsequent command fails. Never touch application keys.
PROBES = {
    "authentication": """
redis.call('ZADD', KEYS[1], 1, 'probe')
redis.call('EXPIRE', KEYS[1], 5)
local count = redis.call('ZCARD', KEYS[1])
redis.call('DEL', KEYS[1])
return count
""",
    "broker": """
redis.call('LPUSH', KEYS[1], 'probe')
redis.call('EXPIRE', KEYS[1], 5)
local value = redis.call('RPOP', KEYS[1])
return value == 'probe' and 1 or 0
""",
    "events": """
redis.call('XADD', KEYS[1], '*', 'revision', '1')
redis.call('EXPIRE', KEYS[1], 5)
local count = redis.call('XLEN', KEYS[1])
redis.call('DEL', KEYS[1])
redis.call('SET', KEYS[1], 'probe', 'EX', 5, 'NX')
local token = redis.call('GETDEL', KEYS[1])
return count == 1 and token == 'probe' and 1 or 0
""",
}


def storage_ready(client: Redis, role: str) -> bool:
    """Check the store's required data structure without leaking connection errors."""
    try:
        return client.eval(PROBES[role], 1, f"owlculus:health:{token_hex(16)}") == 1
    except (OSError, RedisError):
        return False


def execution_storage_status() -> dict[str, str]:
    """Report both configured execution endpoints independently of API readiness."""
    from app.executions.celery_app import app
    from app.executions.events import event_redis_url

    checks = {}
    for role, url in (("broker", app.conf.broker_url), ("events", event_redis_url())):
        with Redis.from_url(
            url,
            socket_connect_timeout=1,
            socket_timeout=1,
            retry=Retry(NoBackoff(), 0),
        ) as client:
            checks[role] = "ok" if storage_ready(client, role) else "unavailable"
    return checks
