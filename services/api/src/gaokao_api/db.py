from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings

Base = declarative_base()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def ensure_schema_compatibility() -> None:
    inspector = inspect(engine)
    if "session_states" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        _add_column_if_missing(
            connection,
            table_name="session_states",
            column_name="pending_recommendation_confirmation",
            statement="ALTER TABLE session_states ADD COLUMN pending_recommendation_confirmation BOOLEAN DEFAULT 0",
        )
        _add_column_if_missing(
            connection,
            table_name="session_states",
            column_name="field_provenance",
            statement="ALTER TABLE session_states ADD COLUMN field_provenance JSON DEFAULT '{}'",
        )


def _add_column_if_missing(connection, *, table_name: str, column_name: str, statement: str) -> None:
    current_columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
    if column_name in current_columns:
        return
    try:
        connection.execute(text(statement))
    except OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


@contextmanager
def session_scope() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
