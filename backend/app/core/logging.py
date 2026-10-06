"""
Application logging configuration and structured logging utilities.

This module sets up structured logging using Loguru with context information,
configurable log levels, file rotation, and security-focused logging features.
It includes context variables for tracking client IP and user agent across requests.
"""

import inspect
import logging
import re
import sys
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any

from loguru import logger

from .config import logging_settings
from .exceptions import DomainException

# Context variables to store request info across async calls
client_ip_context: ContextVar[str | None] = ContextVar("client_ip", default=None)
user_agent_context: ContextVar[str | None] = ContextVar("user_agent", default=None)
OBSERVATION_TOKEN = re.compile(r"([?&]token=)[^&\s\"]+")


class ObservationTokenFilter(logging.Filter):
    """Uvicorn logs handshake URLs; remove ephemeral capabilities before output."""

    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(
                (
                    OBSERVATION_TOKEN.sub(r"\1[redacted]", arg)
                    if isinstance(arg, str)
                    else arg
                )
                for arg in record.args
            )
        record.msg = OBSERVATION_TOKEN.sub(r"\1[redacted]", str(record.msg))
        return True


def setup_logging():
    for name in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addFilter(ObservationTokenFilter())
    logger.remove()

    log_dir = Path(logging_settings.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    console_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {extra} | {message}"

    logger.add(
        sys.stderr,
        format=console_format,
        level="DEBUG" if logging_settings.LOG_LEVEL == "DEBUG" else "INFO",
        colorize=True,
        enqueue=True,
    )

    logger.add(
        logging_settings.LOG_FILE,
        format=file_format,
        level=logging_settings.LOG_LEVEL,
        rotation=logging_settings.LOG_ROTATION,
        retention=logging_settings.LOG_RETENTION,
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    logger.info("Logging system initialized")
    logger.debug(f"Log level: {logging_settings.LOG_LEVEL}")
    logger.debug(f"Log file: {logging_settings.LOG_FILE}")


def get_security_logger(**context):
    # Automatically include client IP and user agent from context if available
    client_ip = client_ip_context.get()
    if client_ip:
        context["client_ip"] = client_ip

    user_agent = user_agent_context.get()
    if user_agent:
        context["user_agent"] = user_agent

    return logger.bind(log_type="security", **context)


def audit_operation[**P, R](
    action: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Record one structured attempt/failed/error/success outcome per call.

    The actor is the operation's bound ``current_user`` argument; integer
    ``*_id`` arguments and the result's ``id`` identify what was touched.
    """

    def decorate(operation: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        signature = inspect.signature(operation)

        @wraps(operation)
        async def audited(*args: P.args, **kwargs: P.kwargs) -> R:
            arguments = signature.bind(*args, **kwargs).arguments
            context: dict[str, Any] = {
                "action": action,
                "actor_user_id": getattr(arguments.get("current_user"), "id", None),
            }
            context.update(
                (name, value)
                for name, value in arguments.items()
                if name.endswith("_id") and isinstance(value, int)
            )
            audit_logger = get_security_logger(
                **context, event_type=f"{action}_attempt"
            )
            try:
                result = await operation(*args, **kwargs)
            except DomainException as error:
                audit_logger.bind(
                    event_type=f"{action}_failed",
                    failure_reason=type(error).__name__,
                ).warning(f"{action} failed")
                raise
            except Exception as error:
                audit_logger.bind(
                    event_type=f"{action}_error", error_type=type(error).__name__
                ).error(f"{action} failed unexpectedly")
                raise
            success: dict[str, Any] = {"event_type": f"{action}_success"}
            if isinstance(result_id := getattr(result, "id", None), int):
                success["result_id"] = result_id
            audit_logger.bind(**success).info(f"{action} succeeded")
            return result

        return audited

    return decorate
