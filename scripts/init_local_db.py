#!/usr/bin/env python3
"""Create local development database tables.

This is for local XR smoke tests where Docker/PostgreSQL is not available.
Use it with an explicit DATABASE_URL, typically SQLite:

    DATABASE_URL=sqlite:///./storage/local_api.sqlite uv run python scripts/init_local_db.py
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from app import models  # noqa: F401
from app.config import settings
from app.database import Base, engine


def ensure_local_sqlite_episode_lifecycle_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "episodes" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("episodes")}
    columns = {
        "finalize_reason": "ALTER TABLE episodes ADD COLUMN finalize_reason VARCHAR(128)",
        "failure_reason": "ALTER TABLE episodes ADD COLUMN failure_reason VARCHAR(128)",
        "failure_note": "ALTER TABLE episodes ADD COLUMN failure_note VARCHAR(2048)",
        "reset_count": "ALTER TABLE episodes ADD COLUMN reset_count INTEGER NOT NULL DEFAULT 0",
        "usable": "ALTER TABLE episodes ADD COLUMN usable BOOLEAN",
        "data_usability_score": "ALTER TABLE episodes ADD COLUMN data_usability_score FLOAT",
        "rejection_reasons": "ALTER TABLE episodes ADD COLUMN rejection_reasons JSON",
    }
    with engine.begin() as connection:
        for name, statement in columns.items():
            if name not in existing:
                connection.execute(text(statement))


def ensure_local_sqlite_quality_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    table_columns = {
        "evaluations": {
            "task_completion_score": "ALTER TABLE evaluations ADD COLUMN task_completion_score FLOAT NOT NULL DEFAULT 0",
            "interaction_quality_score": "ALTER TABLE evaluations ADD COLUMN interaction_quality_score FLOAT NOT NULL DEFAULT 0",
            "contact_sequence_score": "ALTER TABLE evaluations ADD COLUMN contact_sequence_score FLOAT NOT NULL DEFAULT 0",
            "physical_plausibility_score": "ALTER TABLE evaluations ADD COLUMN physical_plausibility_score FLOAT NOT NULL DEFAULT 0",
            "data_usability_score": "ALTER TABLE evaluations ADD COLUMN data_usability_score FLOAT",
            "evaluator_confidence": "ALTER TABLE evaluations ADD COLUMN evaluator_confidence FLOAT NOT NULL DEFAULT 0",
            "failure_mode": "ALTER TABLE evaluations ADD COLUMN failure_mode VARCHAR(128)",
        },
        "datasets": {
            "dataset_card_path": "ALTER TABLE datasets ADD COLUMN dataset_card_path VARCHAR(1024)",
            "lerobot_metadata_path": "ALTER TABLE datasets ADD COLUMN lerobot_metadata_path VARCHAR(1024)",
        },
    }
    with engine.begin() as connection:
        for table, columns in table_columns.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, statement in columns.items():
                if name not in existing:
                    connection.execute(text(statement))


def main() -> None:
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_local_sqlite_episode_lifecycle_columns()
    ensure_local_sqlite_quality_columns()
    print(f"initialized database: {settings.database_url}")
    print(f"storage root: {settings.storage_root}")


if __name__ == "__main__":
    main()
