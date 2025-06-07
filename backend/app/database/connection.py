from sqlmodel import create_engine, Session
from .models import SQLModel
from ..core.config import settings
from sqlalchemy_utils import database_exists, create_database

engine = create_engine(settings.get_database_url(), echo=False)


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
