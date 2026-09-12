"""Redis dispatch from durable assistant intent and conservative lost-worker recovery."""

from datetime import UTC, timedelta

from sqlmodel import Session, col, select

from app.core.strixy_config import StrixyConfig
from app.core.utils import get_utc_now
from app.database.connection import engine
from app.database.db_utils import transaction
from app.database.models import StrixyRun
from app.executions.celery_app import QUEUE, app
from app.executions.strixy_worker import finish, lock_run


def dispatch_once(database_engine=engine) -> bool:
    now = get_utc_now()
    with Session(database_engine) as db:
        ids = db.exec(
            select(StrixyRun.id)
            .where(
                col(StrixyRun.status).in_(["pending", "running"]),
                StrixyRun.dispatch_at <= now,
            )
            .order_by(col(StrixyRun.dispatch_at))
            .limit(50)
        ).all()
    busy = False
    for run_id in ids:
        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None:
                continue
            _, run = selected
            if (
                run.status not in {"pending", "running"}
                or run.dispatch_at.replace(tzinfo=UTC) > now
            ):
                continue
            config = StrixyConfig.model_validate(run.configuration)
            if run.status == "running":
                if run.deadline and now >= run.deadline.replace(tzinfo=UTC) + timedelta(
                    seconds=10
                ):
                    finish(run, "failed", "completion_uncertain")
                    run.limit_code = "runtime_limit"
                    db.add(run)
                continue
            if now >= run.created_at.replace(tzinfo=UTC) + timedelta(
                seconds=config.queue_seconds
            ):
                finish(run, "failed", "worker_unavailable")
            else:
                try:
                    app.send_task(
                        "owlculus.execute_strixy",
                        args=[run.id],
                        task_id=f"strixy-{run.id}",
                        queue=QUEUE,
                        retry=False,
                        time_limit=config.runtime_seconds + 5,
                    )
                    run.dispatch_at = now + timedelta(seconds=30)
                    run.dispatch_attempts = 0
                except Exception:  # noqa: BLE001 - sanitized broker failures
                    run.dispatch_attempts += 1
                    run.dispatch_at = now + timedelta(
                        seconds=min(60, 2**run.dispatch_attempts)
                    )
                    if run.dispatch_attempts >= 5:
                        finish(run, "failed", "dispatch_failed")
            db.add(run)
            busy = True
    return busy
