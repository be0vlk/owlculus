"""
FastAPI application entry point and configuration for Owlculus OSINT platform.

This module initializes the FastAPI application with middleware, CORS configuration,
logging setup, and API route inclusion. It serves as the main entry point for the
Owlculus backend application.

Key features include:
- FastAPI application initialization with OpenAPI documentation integration
- CORS middleware configuration for secure frontend-backend communication
- Request logging middleware with client IP and user agent tracking
- Application lifespan management with structured logging setup
- API router inclusion and centralized route management for OSINT endpoints
"""

from contextlib import asynccontextmanager

from app.api.router import api_router
from app.core.config import settings
from app.core.dependencies import get_client_ip, get_user_agent
from app.core.logging import client_ip_context, setup_logging, user_agent_context
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Owlculus backend starting up")
    yield
    logger.info("Owlculus backend shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
    proxy_headers=True,
)


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
    return response


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "Welcome to Owlculus API!"}
