import os

import dotenv
from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings

dotenv.load_dotenv()


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
    SECRET_KEY: SecretStr = SecretStr(os.environ.get("SECRET_KEY"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 4  # 4 hours, adjust if you want
    DB_USER: str = os.environ.get("POSTGRES_USER")
    DB_PASSWORD: SecretStr = SecretStr(os.environ.get("POSTGRES_PASSWORD"))
    DB_HOST: str = os.environ.get("POSTGRES_HOST")
    DB_PORT: str = os.environ.get("POSTGRES_PORT")
    DB_NAME: str = os.environ.get("POSTGRES_DB")

    @property
    def DATABASE_URI(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD.get_secret_value()}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    BACKEND_CORS_ORIGINS: list[str | AnyHttpUrl] = [
        os.environ.get("FRONTEND_URL", "http://localhost:5173"),
        "http://localhost",
        "http://localhost:80",
    ]
    ALGORITHM: str = "HS256"

    def get_database_url(self) -> str:
        return self.DATABASE_URI


settings = Settings()
logging_settings = LoggingSettings()
