"""
FastAPI application entry point and configuration for Owlculus OSINT platform.

This module initializes the FastAPI application with middleware, CORS configuration,
logging setup, and API route inclusion. It serves as the main entry point for the
Owlculus backend application.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel

from app.api.router import api_router
from app.core.config import settings
from app.core.dependencies import get_client_ip, get_user_agent
from app.core.exception_handler import handle_domain_exception
from app.core.exceptions import BaseException as DomainException
from app.core.logging import client_ip_context, setup_logging, user_agent_context
from app.core.rate_limiting import is_rate_limit_storage_ready
from app.core.setup import check_and_generate_setup_token
from app.database.connection import engine
from app.hunts.hunt_definition_check import HuntDefinitionCheck
from app.hunts.hunt_registry import shipped_hunt_registry
from app.services.plugin_service import PluginService


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


def _check_hunt_definitions() -> None:
    """Fail startup if a shipped hunt cannot be executed by the plugin catalogue."""
    with Session(engine) as session:
        definition_check = HuntDefinitionCheck(
            PluginService(session).parameter_catalogue()
        )
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Owlculus backend starting up")
    app.state.setup_token_check_complete = False
    app.state.hunt_sync_complete = False
    _check_hunt_definitions()
    _complete_setup_token_check(app)
    _complete_hunt_sync(app)
    yield
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
    return await call_next(request)


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


@app.get("/health/ready")
@app.get("/health")
async def readiness_check() -> JSONResponse:
    """Report whether Owlculus can accept application traffic."""
    ready, checks = _readiness_status()
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/")
async def root():
    return {"message": "Welcome to Owlculus API!"}
