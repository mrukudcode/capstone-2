"""
Database connection.

SQLite database is anchored to the backend directory so the same
claim_validator.db is used regardless of the directory from which
the application or scripts are launched.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

DEFAULT_DATABASE_PATH = os.path.join(
    BASE_DIR,
    "claim_validator.db"
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DATABASE_PATH.replace(os.sep, '/')}"
)

connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()