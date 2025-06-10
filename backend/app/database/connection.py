from sqlmodel import create_engine, Session
from .models import SQLModel
from ..core.config import settings
from sqlalchemy_utils import database_exists, create_database

# Configure connection pooling for better performance and connection management
engine = create_engine(
    settings.get_database_url(),
    echo=False,
    pool_size=20,  # Number of connections to maintain in the pool
    max_overflow=10,  # Maximum overflow connections above pool_size
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,  # Recycle connections after 1 hour
)


def create_db_and_tables():
    if not database_exists(engine.url):
        create_database(engine.url)
    SQLModel.metadata.create_all(engine)


def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
