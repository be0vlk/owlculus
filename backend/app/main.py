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
