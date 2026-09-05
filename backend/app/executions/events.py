"""Transactional publication intent and bounded, replayable Redis notifications.

Events are invalidations with durable revisions and result links, never result bodies.
PostgreSQL owns state; the dispatcher retries publication independently of workers.
"""

import os
from contextlib import nullcontext
from datetime import UTC, timedelta

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.core.utils import get_utc_now
from app.database.connection import engine
from app.database.db_utils import transaction
from app.database.models import (
    ExecutionControl,
    ExecutionEvent,
    HuntExecution,
    PluginExecution,
)

STREAM_LIMIT = max(1, int(os.environ.get("EXECUTION_STREAM_LIMIT", "10000")))
STREAM_TTL = max(1, int(os.environ.get("EXECUTION_STREAM_TTL_SECONDS", "86400")))


def event_redis_url() -> str:
    return os.environ.get("EXECUTION_EVENT_REDIS_URL") or os.environ.get(
        "REDIS_URL", "redis://localhost:6379/0"
    )


def redis_client():
    return Redis.from_url(
        event_redis_url(),
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )


def stream_key(kind, execution_id):
    return f"owlculus:events:{kind}:{execution_id}"


def record_event(db, control, *, advance=True):
    if advance:
        control.revision += 1
    db.add(ExecutionEvent(control_id=control.id, revision=control.revision))


# Redis 7-compatible, atomic exact trimming and expiration. A lost publication
# acknowledgment can safely retry the same revision without duplicating delivery.
PUBLISH = """
local last = redis.call('XREVRANGE', KEYS[1], '+', '-', 'COUNT', 1)
if #last == 0 or tonumber(string.match(last[1][1], '^(%d+)')) < tonumber(ARGV[1]) then
  redis.call('XADD', KEYS[1], 'MAXLEN', '=', ARGV[2], ARGV[1] .. '-0', 'revision', ARGV[1])
end
redis.call('EXPIRE', KEYS[1], ARGV[3])
return 1
"""


def publish_once(database_engine=engine, client=None) -> bool:
    """Publish one committed revision; leave intent intact on transport failure."""
    with Session(database_engine) as db, transaction(db):
        # Lock the execution first to serialize publishers for each stream. Writers
        # use this same lock, but only a bounded Redis call runs under it.
        control = db.exec(
            select(ExecutionControl)
            .where(col(ExecutionControl.id).in_(select(ExecutionEvent.control_id)))
            .where(
                or_(
                    col(ExecutionControl.event_publish_after).is_(None),
                    col(ExecutionControl.event_publish_after) <= get_utc_now(),
                )
            )
            .order_by(
                col(ExecutionControl.event_publish_after).asc().nullsfirst(),
                col(ExecutionControl.id),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if control is None:
            return False
        intent = db.exec(
            select(ExecutionEvent)
            .where(ExecutionEvent.control_id == control.id)
            .order_by(col(ExecutionEvent.revision))
            .limit(1)
        ).one()
        kind, execution_id = control.execution_reference()
        execution = db.get(
            HuntExecution if kind == "hunt" else PluginExecution, execution_id
        )
        assert isinstance(execution, (HuntExecution, PluginExecution))
        ttl = STREAM_TTL
        if execution.completed_at:
            ttl -= int(
                (
                    get_utc_now() - execution.completed_at.replace(tzinfo=UTC)
                ).total_seconds()
            )
        try:
            if ttl > 0:
                with (
                    redis_client() if client is None else nullcontext(client)
                ) as connection:
                    connection.eval(
                        PUBLISH,
                        1,
                        stream_key(kind, execution_id),
                        intent.revision,
                        STREAM_LIMIT,
                        ttl,
                    )
        except RedisError:
            # A damaged stream must not starve another execution's observers.
            control.event_publish_after = get_utc_now() + timedelta(seconds=2)
            return False
        control.event_publish_after = get_utc_now()
        db.delete(intent)
        return True


def refresh_active_streams(database_engine=engine):
    """Refresh quiet active streams without extending terminal retention."""
    with Session(database_engine) as db, redis_client() as client:
        for control in db.exec(
            select(ExecutionControl)
            .outerjoin(
                PluginExecution,
                col(PluginExecution.id) == ExecutionControl.plugin_execution_id,
            )
            .outerjoin(
                HuntExecution,
                col(HuntExecution.id) == ExecutionControl.hunt_execution_id,
            )
            .where(
                or_(
                    col(PluginExecution.status).in_(
                        ["queued", "running", "cancelling"]
                    ),
                    col(HuntExecution.status).in_(["pending", "running", "cancelling"]),
                )
            )
        ).yield_per(200):
            kind, execution_id = control.execution_reference()
            client.expire(stream_key(kind, execution_id), STREAM_TTL)
