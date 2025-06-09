import sys
from pathlib import Path
from contextvars import ContextVar
from loguru import logger
from .config import logging_settings

# Context variables to store request info across async calls
client_ip_context: ContextVar[str] = ContextVar("client_ip", default=None)
user_agent_context: ContextVar[str] = ContextVar("user_agent", default=None)


def setup_logging():
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


def get_logger_with_context(**context):
    return logger.bind(**context)
