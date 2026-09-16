import os

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


database_url = URL.create(
    "postgresql+psycopg",
    username=os.getenv("POSTGRES_USER", "curriculum_review"),
    password=os.getenv("POSTGRES_PASSWORD", "local_dev_password"),
    host=os.getenv("POSTGRES_HOST", "db"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    database=os.getenv("POSTGRES_DB", "curriculum_review"),
)
engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
