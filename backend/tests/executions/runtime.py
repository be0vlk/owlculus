"""Worker-loadable deterministic providers, only imported by the test launcher."""

import asyncio
import os
from pathlib import Path

from app.plugins.base_plugin import BasePlugin
from app.plugins.plugin_types import IpAddressWrite
from app.services.api_key_vault import Provider


class AcceptancePlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.parameters = {
            "mode": {"type": "string", "default": "success"},
            "barrier": {"type": "string"},
            "query": {"type": "string"},
            "bytes": {"type": "integer", "default": 0},
            "count": {"type": "integer", "default": 1},
        }

    async def run(self, params, ctx):
        root = Path(os.environ["EXECUTION_TEST_DIR"])
        with (root / "provider-starts").open("a") as output:
            output.write(f"{params.get('barrier', 'none')}\n")
        if params.get("mode") == "sized":
            for _ in range(params["count"]):
                yield self.data({"value": "x" * (params["bytes"] - 35)})
            return
        if params.get("mode") == "pages":
            for index in range(205):
                yield self.data({"index": index})
            return
        if params.get("mode", "success") == "empty":
            return
        if params.get("mode", "success") == "vault":
            key = ctx.key(Provider.CUSTOM)
            if not key:
                yield ctx.missing_key(Provider.CUSTOM)
                return
            yield self.data({"configured": True, "redacted": key})
        yield self.data(
            {
                "query": params.get("query", "owl"),
                "case_id": ctx.case_id,
                "pid": os.getpid(),
            }
        )
        if params.get("mode") == "large-event":
            yield self.data({"value": "x" * 300})
        if params.get("mode") == "many-results":
            for index in range(10):
                yield self.data({"index": index, "value": "x" * 65})
        if params.get("mode") == "blocking":
            import time

            (root / "blocked").touch()
            time.sleep(600)
        if params.get("mode") == "subprocess":
            import subprocess
            import sys

            process = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(600)"]
            )
            (root / "subprocess-pid").write_text(str(process.pid))
            process.wait()
        if params.get("barrier"):
            for _ in range(600):
                if (root / params["barrier"]).exists():
                    break
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("Test barrier timed out")
        if params.get("mode", "success") == "error":
            yield self.error("Deterministic failure")
            yield self.complete()

    def entity_writes(self, payloads, params):
        if params.get("mode") == "sized":
            return []
        description = payloads[0].get("redacted", "Acceptance discovery")
        return [IpAddressWrite("192.0.2.10", description)]


def install():
    from app.plugins import plugin_registry

    from app.executions import supervisor
    import sys

    supervisor.CHILD_COMMAND = [
        sys.executable,
        "-m",
        "tests.executions.runtime",
        "child",
    ]

    original = plugin_registry.get_shipped_plugin_registry
    registry = original()
    # Keep shipped definitions for startup hunt validation.
    plugin_registry.get_shipped_plugin_registry = (
        lambda: plugin_registry.PluginRegistry.from_classes(
            [type(registry.create(name)) for name in registry.metadata()]
            + [AcceptancePlugin]
        )
    )


if __name__ == "__main__":
    import sys

    install()
    if sys.argv[1] == "child":
        from app.executions.child import main

        sys.argv.pop(1)
        main()
    elif sys.argv[1] == "api":
        import uvicorn

        uvicorn.run(
            "app.main:app", host="127.0.0.1", port=int(sys.argv[2]), log_level="warning"
        )
    elif sys.argv[1] in {"worker", "hunt-worker"}:
        from app.executions.celery_app import HUNT_QUEUE, QUEUE, app

        queue = HUNT_QUEUE if sys.argv[1] == "hunt-worker" else QUEUE

        app.worker_main(
            [
                "worker",
                "--pool=prefork",
                "--concurrency=2",
                "--prefetch-multiplier=1",
                f"--queues={queue}",
                "--loglevel=WARNING",
                f"--hostname={sys.argv[1]}@%h",
            ]
        )

    elif sys.argv[1] in {"dispatch-before", "dispatch-after"}:
        import time

        from app.executions import dispatcher

        original_send = dispatcher.app.send_task

        def interrupted_send(*args, **kwargs):
            if sys.argv[1] == "dispatch-after":
                original_send(*args, **kwargs)
            (Path(os.environ["EXECUTION_TEST_DIR"]) / "publication-window").touch()
            while True:
                time.sleep(1)

        dispatcher.app.send_task = interrupted_send
        dispatcher.dispatch_once()

    elif sys.argv[1] == "replay-effects":
        from contextlib import contextmanager

        from sqlalchemy import event
        from sqlmodel import Session, select

        from app.database.connection import engine
        from app.database.models import ExecutionControl, PluginExecution, User
        from app.executions.ownership import Ownership
        from app.executions.worker import WorkerVault, worker_adapter
        from app.plugins.plugin_types import EvidenceWrite

        execution_id = int(sys.argv[2])
        window = sys.argv[3]
        marker = Path(os.environ["EXECUTION_TEST_DIR"]) / f"effect-{window}"
        with Session(engine) as db:
            control = db.exec(
                select(ExecutionControl).where(
                    ExecutionControl.plugin_execution_id == execution_id
                )
            ).one()
            ownership = Ownership(control.id, control.generation, control.owner)
            execution = db.get(PluginExecution, execution_id)
            user = db.get(User, execution.created_by_id)
            case_id, save = execution.case_id, execution.save_to_case
            db.expunge(user)

        def pause():
            import time

            marker.touch()
            while True:
                time.sleep(1)

        @contextmanager
        def session_factory():
            with Session(engine, expire_on_commit=False) as db:
                if window in {"after-commit", "after-entity-commit"}:

                    def interrupted_commit(session):
                        if session.info.get("effect_kind") == (
                            "entity" if window == "after-entity-commit" else "evidence"
                        ):
                            pause()

                    event.listen(db, "after_commit", interrupted_commit)
                yield db

        if window == "after-file":
            from app.services import evidence_service

            original_save = evidence_service.save_upload_file

            async def interrupted_save(*args, **kwargs):
                result = await original_save(*args, **kwargs)
                pause()
                return result

            evidence_service.save_upload_file = interrupted_save

        async def replay():
            if window == "results":
                from app.executions.ownership import append_result

                with Session(engine) as db:
                    append_result(
                        db,
                        ownership,
                        {"type": "data", "data": {"replayed": True}},
                        operation_index=900,
                    )
                marker.touch()
                return
            with worker_adapter(session_factory, WorkerVault(engine), ownership).open(
                user=user, case_id=case_id, save_to_case=save
            ) as run:
                await run.evidence.write(
                    EvidenceWrite(
                        "AcceptancePlugin",
                        "Acceptance",
                        "Other",
                        case_id,
                        "Stable retained evidence",
                        "acceptance.txt",
                    ),
                    user,
                )
                await run.entities.write(
                    IpAddressWrite("192.0.2.10", "Exactly one enrichment"),
                    case_id,
                    user,
                )
            marker.touch()

        asyncio.run(replay())
