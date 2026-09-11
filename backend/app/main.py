"""
FastAPI application entry point and configuration for Owlculus OSINT platform.

This module initializes the FastAPI application with middleware, CORS configuration,
logging setup, and API route inclusion. It serves as the main entry point for the
Owlculus backend application.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel

from app.api.router import api_router
from app.core.config import settings
from app.core.database_boundary import shutdown_database_workers
from app.core.dependencies import get_client_ip, get_user_agent
from app.core.exception_handler import handle_domain_exception
from app.core.exceptions import BaseException as DomainException
from app.core.logging import client_ip_context, setup_logging, user_agent_context
from app.core.rate_limiting import is_rate_limit_storage_ready
from app.core.setup import check_and_generate_setup_token
from app.database.connection import readiness_engine as engine
from app.hunts.hunt_definition_check import HuntDefinitionCheck
from app.hunts.hunt_registry import shipped_hunt_registry
from app.plugins.plugin_registry import PluginRegistry, get_shipped_plugin_registry

HUNT_SYNC_RETRY_SECONDS = 1.0
READINESS_TIMEOUT_SECONDS = 1.0
_health_executor: ThreadPoolExecutor | None = None


def _complete_setup_token_check(application: FastAPI) -> bool:
    """Attempt setup-token initialization without preventing process startup."""
    if application.state.setup_token_check_complete:
        return True

    try:
        with Session(engine) as session:
            check_and_generate_setup_token(session)
    except (OSError, RuntimeError, SQLAlchemyError):
        logger.warning(
            "Initial setup-token check is incomplete; readiness remains unavailable"
        )
        return False

    application.state.setup_token_check_complete = True
    return True


def _check_hunt_definitions(plugin_registry: PluginRegistry) -> None:
    """Fail startup if a shipped hunt cannot be executed by the plugin catalogue."""
    definition_check = HuntDefinitionCheck(plugin_registry.parameter_catalogue())
    shipped_hunt_registry.check(definition_check)


def _complete_hunt_sync(application: FastAPI) -> bool:
    """Synchronize checked hunts once the database schema is available."""
    if application.state.hunt_sync_complete:
        return True

    try:
        with Session(engine) as session:
            shipped_hunt_registry.sync(session)
    except SQLAlchemyError:
        logger.warning(
            "Hunt definition sync is incomplete; readiness remains unavailable"
        )
        return False

    application.state.hunt_sync_complete = True
    return True


async def _retry_hunt_sync_during_startup(application: FastAPI) -> None:
    """Keep degraded startup ownership of the sync until the schema appears."""
    while not application.state.hunt_sync_complete:
        await asyncio.sleep(HUNT_SYNC_RETRY_SECONDS)
        await _bounded_readiness()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _health_executor
    setup_logging()
    logger.info("Owlculus backend starting up")
    app.state.setup_token_check_complete = False
    app.state.hunt_sync_complete = False
    app.state.plugin_registry = get_shipped_plugin_registry()
    _check_hunt_definitions(app.state.plugin_registry)
    await _bounded_readiness()
    hunt_sync_task = None
    if not app.state.hunt_sync_complete:
        hunt_sync_task = asyncio.create_task(_retry_hunt_sync_during_startup(app))
    try:
        yield
    finally:
        if hunt_sync_task is not None:
            hunt_sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await hunt_sync_task
        await shutdown_database_workers()
        if _health_executor is not None:
            await asyncio.to_thread(_health_executor.shutdown, wait=True)
            _health_executor = None
        app.state.readiness_work = None
        logger.info("Owlculus backend shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
)
app.state.setup_token_check_complete = False
app.state.hunt_sync_complete = False
app.add_exception_handler(DomainException, handle_domain_exception)


# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Middleware to capture client IP and user agent for logging
@app.middleware("http")
async def request_info_middleware(request: Request, call_next):
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    client_ip_context.set(client_ip)
    user_agent_context.set(user_agent)
    response = await call_next(request)
    path = request.url.path
    if path.startswith(
        ("/api/plugins/executions/", "/api/hunts/executions/", "/api/evidence/")
    ) or (path.startswith("/api/cases/") and path.endswith("/export")):
        # FileResponse otherwise advertises validators for immutable report bytes;
        # authorization can change independently of those bytes or revisions.
        response.headers["Cache-Control"] = "private, no-store"
    return response


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Report process liveness without checking external dependencies."""
    return {"status": "healthy"}


def _readiness_status() -> tuple[bool, dict[str, str]]:
    """Check the database, schema, setup token, and rate-limit storage."""
    checks: dict[str, str] = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            checks["database"] = "ok"
            try:
                present_tables = set(inspect(connection).get_table_names())
                required_tables = set(SQLModel.metadata.tables)
                checks["schema"] = (
                    "ok" if required_tables <= present_tables else "missing"
                )
            except SQLAlchemyError:
                checks["schema"] = "unavailable"
    except SQLAlchemyError:
        checks["database"] = "unavailable"
        checks["schema"] = "unavailable"

    if checks["database"] == "ok" and checks["schema"] == "ok":
        _complete_setup_token_check(app)
        _complete_hunt_sync(app)

    checks["setup_token"] = (
        "ok" if app.state.setup_token_check_complete else "incomplete"
    )
    checks["hunt_registry"] = "ok" if app.state.hunt_sync_complete else "incomplete"
    checks["rate_limit_storage"] = (
        "ok" if is_rate_limit_storage_ready() else "unavailable"
    )
    return all(check == "ok" for check in checks.values()), checks


async def _bounded_readiness() -> tuple[bool, dict[str, str]]:
    """Coalesce probes; a delayed check retains its one reserved worker slot."""
    global _health_executor
    if _health_executor is None:
        _health_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="readiness"
        )
    work = getattr(app.state, "readiness_work", None)
    if work is None or work.done():
        work = _health_executor.submit(_readiness_status)
        app.state.readiness_work = work
    try:
        return await asyncio.wait_for(
            asyncio.shield(asyncio.wrap_future(work)), READINESS_TIMEOUT_SECONDS
        )
    except TimeoutError:
        return False, {"database": "delayed"}


@app.get("/health/execution")
def execution_health_check() -> JSONResponse:
    """Execution storage health does not gate authentication traffic."""
    from app.core.redis_health import execution_storage_status

    checks = execution_storage_status()
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/health/ready")
@app.get("/health")
async def readiness_check() -> JSONResponse:
    """Report whether Owlculus can accept application traffic."""
    ready, checks = await _bounded_readiness()
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/")
async def root():
    return {"message": "Welcome to Owlculus API!"}
