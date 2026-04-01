from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings

Base = declarative_base()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def ensure_schema_compatibility() -> None:
    inspector = inspect(engine)
    if "session_states" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("session_states")}
    statements: list[str] = []

    if "pending_recommendation_confirmation" not in columns:
        statements.append("ALTER TABLE session_states ADD COLUMN pending_recommendation_confirmation BOOLEAN DEFAULT 0")
    if "field_provenance" not in columns:
        statements.append("ALTER TABLE session_states ADD COLUMN field_provenance JSON DEFAULT '{}'")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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
