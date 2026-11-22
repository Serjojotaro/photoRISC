from __future__ import annotations

import sqlite3

from app import db
from app.config import Settings


def test_stage_one_schema_is_migrated_to_stage_two(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True)
    with sqlite3.connect(settings.database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations(version, applied_at)
            VALUES (1, '2026-11-22T00:00:00Z');

            CREATE TABLE assets (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                relative_path TEXT NOT NULL UNIQUE,
                sha256 TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                orientation INTEGER NOT NULL DEFAULT 1,
                has_icc_profile INTEGER NOT NULL DEFAULT 0,
                thumbnail_status TEXT NOT NULL DEFAULT 'pending',
                thumbnail_relative_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                error_code TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            );
            """
        )

    db.init_db(settings)

    with sqlite3.connect(settings.database_path) as connection:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert version == 2
    assert {
        "recipe_id",
        "recipe_revision",
        "recipe_snapshot",
        "output_path",
        "output_format",
        "output_quality",
    }.issubset(columns)
    assert "recipes" in tables
