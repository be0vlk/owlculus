"""One execution process owns its event loop, provider threads and subprocesses."""

import asyncio
import signal
import sys

from sqlmodel import create_engine

from app.core.config import settings
from app.executions.ownership import Ownership
from app.plugins.plugin_registry import get_shipped_plugin_registry


def main():
    kind, execution_id, control_id, generation, owner = sys.argv[1:]
    from app.executions.hunt_worker import execute as hunt
    from app.executions.worker import execute as plugin

    engine = create_engine(
        settings.get_database_url(), pool_pre_ping=True, hide_parameters=True
    )

    async def run():
        task = asyncio.current_task()
        assert task is not None
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
        await (hunt if kind == "hunt" else plugin)(
            engine,
            get_shipped_plugin_registry(),
            int(execution_id),
            ownership=Ownership(int(control_id), int(generation), owner),
        )

    try:
        asyncio.run(run())
    except asyncio.CancelledError:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
