from sqlalchemy_utils import create_database, database_exists
from sqlmodel import Session, create_engine

from ..core.config import settings
from .models import SQLModel

engine = create_engine(
    settings.get_database_url(),
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
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
