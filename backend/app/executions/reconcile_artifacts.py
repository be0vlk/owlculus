"""Reconcile interrupted execution-owned evidence files without touching uploads."""

from datetime import UTC
from typing import cast
from uuid import UUID

from sqlmodel import Session, select

from app.core.file_storage import UPLOAD_DIR
from app.core.utils import get_utc_now
from app.database.connection import engine
from app.database.models import (
    Evidence,
    ExecutionControl,
    HuntExecution,
    PluginExecution,
)


def reconcile(database_engine=engine, upload_dir=UPLOAD_DIR) -> int:
    removed = 0
    for path in upload_dir.glob("*/.execution-artifacts/*"):
        if (
            path.suffix not in {".txt", ".staging"}
            or not path.is_file()
            or path.is_symlink()
        ):
            continue
        control_id, _, identity = path.stem.partition("-")
        try:
            UUID(identity)
            case_id, control_id_number = int(path.parent.parent.name), int(control_id)
        except ValueError:
            continue
        with Session(database_engine) as db:
            control = db.exec(
                select(ExecutionControl)
                .where(ExecutionControl.id == control_id_number)
                .with_for_update()
            ).first()
            if control is None:
                continue
            model = HuntExecution if control.hunt_execution_id else PluginExecution
            execution = cast(
                HuntExecution | PluginExecution | None,
                db.get(model, control.hunt_execution_id or control.plugin_execution_id),
            )
            if execution is None or execution.case_id != case_id:
                continue
            if (
                execution.status in {"running", "cancelling"}
                and control.lease_until
                and control.lease_until.replace(tzinfo=UTC) > get_utc_now()
            ):
                continue
            relative_path = str(path.relative_to(upload_dir))
            if (
                db.exec(
                    select(Evidence.id).where(Evidence.content == relative_path)
                ).first()
                is not None
            ):
                continue
            # Holding the same control lock as the writer prevents a race with
            # publication. Only recognized files of non-live owners are removed.
            path.unlink(missing_ok=True)
            removed += 1
    return removed


if __name__ == "__main__":
    print(f"Reconciled {reconcile()} unreferenced execution artifacts")
