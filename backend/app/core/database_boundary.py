"""Run a complete HTTP unit of work away from the ASGI transport loop.

Dependencies, authorization, endpoint work, serialization, and session finalizers
run in one worker context. Only a materialized Response crosses back. WebSockets
keep their existing short, independently owned snapshot sessions.
"""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context
from threading import BoundedSemaphore
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute

from app.core.config import settings

_transport_loop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar(
    "database_transport_loop", default=None
)
_request_slots = BoundedSemaphore(settings.API_DATABASE_CONCURRENCY)
_request_executor: ThreadPoolExecutor | None = None


def _executor() -> ThreadPoolExecutor:
    global _request_executor
    if _request_executor is None:
        _request_executor = ThreadPoolExecutor(
            max_workers=settings.API_DATABASE_CONCURRENCY,
            thread_name_prefix="api-database",
        )
    return _request_executor


async def shutdown_database_workers() -> None:
    """Drain owned work before application lifespan state can be reused."""
    global _request_executor
    if _request_executor is not None:
        await asyncio.to_thread(_request_executor.shutdown, wait=True)
        _request_executor = None


async def on_transport_loop[Result](
    operation: Callable[[], Awaitable[Result]],
) -> Result:
    """Keep shared asynchronous admission/CPU limiters on their owning loop."""
    loop = _transport_loop.get()
    if loop is None or loop is asyncio.get_running_loop():
        return await operation()

    async def run() -> Result:
        return await operation()

    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(run(), loop))


class DatabaseRoute(APIRoute):
    """Bound complete HTTP database requests without queuing unbounded work."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            if not _request_slots.acquire(blocking=False):
                raise HTTPException(
                    503,
                    "API database capacity is busy; retry shortly",
                    headers={"Retry-After": "1"},
                )
            loop = asyncio.get_running_loop()

            async def receive():
                return await on_transport_loop(request.receive)

            def run() -> Response:
                token = _transport_loop.set(loop)
                try:
                    return asyncio.run(handler(Request(request.scope, receive)))
                finally:
                    _transport_loop.reset(token)
                    _request_slots.release()

            # A disconnected/cancelled transport must not release capacity or
            # finalize a session while its database call is still running.
            work = asyncio.wrap_future(_executor().submit(copy_context().run, run))
            try:
                return await asyncio.shield(work)
            except asyncio.CancelledError:
                while not work.done():
                    try:
                        await asyncio.shield(work)
                    except asyncio.CancelledError:
                        continue
                # Retrieve a worker exception even when the client has gone.
                if not work.cancelled():
                    work.exception()
                raise

        return handle
