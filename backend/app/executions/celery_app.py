"""Dedicated execution queues; database resources are created only after fork."""

import os

from celery import Celery  # type: ignore[import-untyped]

from app.executions.limits import VISIBILITY_SECONDS

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
    task_acks_late=False,
    task_reject_on_worker_lost=False,
    visibility_timeout=VISIBILITY_SECONDS,
    result_backend_transport_options={"visibility_timeout": VISIBILITY_SECONDS},
    task_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2,
    broker_transport_options={
        "visibility_timeout": VISIBILITY_SECONDS,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": False,
        "max_retries": 0,
    },
)


@app.task(name="owlculus.execute_plugin")
def execute_plugin(execution_id: int):
    from app.executions.supervisor import run

    run(execution_id, "plugin")


@app.task(name="owlculus.execute_hunt")
def execute_hunt(execution_id: int):
    from app.executions.supervisor import run

    run(execution_id, "hunt")
