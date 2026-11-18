"""
Application configuration settings and environment variable management.

This module defines configuration classes for database connections, logging,
CORS settings, authentication parameters, and other application settings.
It uses Pydantic for settings validation and environment variable handling.
"""

import os
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL

from .deployment import validate_deployment

# Local Python tooling keeps its existing configuration; Compose sets this explicitly.
if os.environ.get("OWLCULUS_ENV") == "production":
    validate_deployment(os.environ, bootstrap="RUNTIME_POSTGRES_USER" in os.environ)


class LoggingSettings(BaseSettings):
    LOG_LEVEL: str = os.environ.get("OWLCULUS_LOG_LEVEL", "INFO")
    LOG_FILE: str = os.environ.get("OWLCULUS_LOG_FILE", "logs/owlculus.log")
    LOG_ROTATION: str = os.environ.get("OWLCULUS_LOG_ROTATION", "10 MB")
    LOG_RETENTION: str = os.environ.get("OWLCULUS_LOG_RETENTION", "30 days")


class Settings(BaseSettings):
    PROJECT_NAME: str = "Owlculus"
    DESCRIPTION: str = "An OSINT case management platform and toolkit"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    SECRET_KEY: SecretStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 4  # 4 hours in minutes
    DB_USER: str = Field(validation_alias="POSTGRES_USER")
    DB_PASSWORD: SecretStr = Field(validation_alias="POSTGRES_PASSWORD")
    DB_HOST: str = Field(validation_alias="POSTGRES_HOST")
    DB_PORT: str = Field(validation_alias="POSTGRES_PORT")
    DB_NAME: str = Field(validation_alias="POSTGRES_DB")

    @property
    def DATABASE_URI(self) -> str:
        return URL.create(
            "postgresql",
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value(),
            host=self.DB_HOST,
            port=int(self.DB_PORT),
            database=self.DB_NAME,
        ).render_as_string(hide_password=False)

    BACKEND_CORS_ORIGINS: list[str | AnyHttpUrl] = [
        os.environ.get("FRONTEND_URL", "http://localhost:5173"),
        os.environ.get("BACKEND_URL", "http://localhost:8000"),
        "http://localhost",
        "http://localhost:80",
        "http://localhost:8081",
    ]
    FORWARDED_ALLOW_IPS: str = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1,::1")
    AUTH_REDIS_URL: str = os.environ.get("AUTH_REDIS_URL", "redis://localhost:6380/0")
    STRIXY_PROVIDER: Literal["openai", "openai_compatible", "anthropic"] = "openai"
    STRIXY_MODEL: str | None = Field(default=None, min_length=1)
    STRIXY_BASE_URL: str | None = Field(default=None, min_length=1)
    STRIXY_SUPPORTS_VISION: bool = True
    API_DATABASE_CONCURRENCY: int = Field(default=8, ge=1, le=32)
    LOGIN_IP_MAX_ATTEMPTS: int = Field(default=30, ge=1, le=10000)
    LOGIN_ACCOUNT_MAX_ATTEMPTS: int = Field(default=10, ge=1, le=10000)
    LOGIN_LIMIT_WINDOW_SECONDS: int = Field(default=300, ge=1, le=86400)

    @field_validator("STRIXY_MODEL", "STRIXY_BASE_URL", mode="before")
    @classmethod
    def blank_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def openai_compatible_needs_endpoint(self) -> "Settings":
        if self.STRIXY_PROVIDER == "openai_compatible" and not (
            self.STRIXY_MODEL and self.STRIXY_BASE_URL
        ):
            raise ValueError(
                "STRIXY_PROVIDER=openai_compatible requires STRIXY_MODEL and STRIXY_BASE_URL"
            )
        return self

    def get_database_url(self) -> str:
        return self.DATABASE_URI


settings = Settings()
logging_settings = LoggingSettings()
