from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, SecretStr
import dotenv
import os

dotenv.load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Owlculus"
    DESCRIPTION: str = "An OSINT case management platform and toolkit"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"
    SECRET_KEY: SecretStr = SecretStr(os.environ.get("SECRET_KEY"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 4  # 4 hours, adjust if you want
    DB_USER: str = os.environ.get("POSTGRES_USER")
    DB_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD")
    DB_HOST: str = os.environ.get("POSTGRES_HOST")
    DB_PORT: str = os.environ.get("POSTGRES_PORT")
    DB_NAME: str = os.environ.get("POSTGRES_DB")
    DATABASE_URI: str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    BACKEND_CORS_ORIGINS: list[str | AnyHttpUrl] = [
        os.environ.get("FRONTEND_URL", "http://localhost:5173"),
        "http://localhost",
        "http://localhost:80",
    ]
    ALGORITHM: str = "HS256"

    def get_database_url(self) -> str:
        return self.DATABASE_URI

settings = Settings()