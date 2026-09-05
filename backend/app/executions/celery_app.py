"""Dedicated plugin queue; the parent process never imports database resources."""

import asyncio
import os

from celery import Celery  # type: ignore[import-untyped]

app = Celery(
    "owlculus_executions",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)
HUNT_QUEUE = os.environ.get("HUNT_QUEUE", "owlculus.hunts")
QUEUE = os.environ.get("PLUGIN_QUEUE", "owlculus.plugins")
app.conf.update(
    task_default_queue=QUEUE,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
)


@app.task(name="owlculus.execute_plugin")
def execute_plugin(execution_id: int):
    from sqlmodel import create_engine

    from app.core.config import settings
    from app.executions.worker import execute
    from app.plugins.plugin_registry import get_shipped_plugin_registry

    engine = create_engine(
        settings.get_database_url(), pool_pre_ping=True, hide_parameters=True
    )
    try:
        asyncio.run(execute(engine, get_shipped_plugin_registry(), execution_id))
    finally:
        engine.dispose()


@app.task(name="owlculus.execute_hunt")
def execute_hunt(execution_id: int):
    from sqlmodel import create_engine

    from app.core.config import settings
    from app.executions.hunt_worker import execute
    from app.plugins.plugin_registry import get_shipped_plugin_registry

    engine = create_engine(
        settings.get_database_url(), pool_pre_ping=True, hide_parameters=True
    )
    try:
        asyncio.run(execute(engine, get_shipped_plugin_registry(), execution_id))
    finally:
        engine.dispose()
