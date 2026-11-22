from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from app.config import Settings


SCHEMA_VERSION = 2


class RecipeRevisionConflict(Exception):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def connect(settings: Settings) -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        settings.database_path,
        timeout=10,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


@contextmanager
def open_db(settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except Exception:
        connection.execute("ROLLBACK")
        raise
    else:
        connection.execute("COMMIT")


def init_db(settings: Settings) -> None:
    settings.ensure_directories()
    with open_db(settings) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assets (
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
                thumbnail_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (thumbnail_status IN ('pending', 'ready', 'failed')),
                thumbnail_relative_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                recipe_id TEXT,
                recipe_revision INTEGER,
                recipe_snapshot TEXT,
                status TEXT NOT NULL
                    CHECK (status IN ('queued', 'running', 'completed', 'failed')),
                error_code TEXT,
                output_path TEXT,
                output_format TEXT,
                output_quality INTEGER,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS recipes (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                revision INTEGER NOT NULL,
                document_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                ON jobs(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_jobs_asset_id
                ON jobs(asset_id);
            CREATE INDEX IF NOT EXISTS idx_recipes_asset_updated
                ON recipes(asset_id, updated_at DESC);
            """
        )
        with transaction(connection):
            existing = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, utc_now()),
                )
            elif int(existing["version"]) == 1:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN recipe_id TEXT"
                )
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN recipe_revision INTEGER"
                )
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN recipe_snapshot TEXT"
                )
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN output_path TEXT"
                )
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN output_format TEXT"
                )
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN output_quality INTEGER"
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, utc_now()),
                )
            elif int(existing["version"]) != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported database schema version: {existing['version']}"
                )


def insert_asset_with_thumbnail_job(
    settings: Settings,
    *,
    asset_id: str,
    job_id: str,
    display_name: str,
    relative_path: str,
    sha256: str,
    size_bytes: int,
    width: int,
    height: int,
    orientation: int,
    has_icc_profile: bool,
) -> None:
    now = utc_now()
    with open_db(settings) as connection, transaction(connection):
        connection.execute(
            """
            INSERT INTO assets(
                id, display_name, relative_path, sha256, mime_type, size_bytes,
                width, height, orientation, has_icc_profile, thumbnail_status,
                created_at
            ) VALUES (?, ?, ?, ?, 'image/jpeg', ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                asset_id,
                display_name,
                relative_path,
                sha256,
                size_bytes,
                width,
                height,
                orientation,
                int(has_icc_profile),
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO jobs(id, kind, asset_id, status, created_at)
            VALUES (?, 'thumbnail', ?, 'queued', ?)
            """,
            (job_id, asset_id, now),
        )


def list_assets(settings: Settings, *, limit: int, offset: int) -> tuple[list[dict], int]:
    with open_db(settings) as connection:
        total = int(connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0])
        rows = connection.execute(
            """
            SELECT * FROM assets
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows], total


def get_asset(settings: Settings, asset_id: str) -> dict | None:
    with open_db(settings) as connection:
        row = connection.execute(
            "SELECT * FROM assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_asset(settings: Settings, asset_id: str) -> dict | None:
    with open_db(settings) as connection, transaction(connection):
        row = connection.execute(
            "SELECT * FROM assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            return None
        job_outputs = [
            item["output_path"]
            for item in connection.execute(
                "SELECT output_path FROM jobs WHERE asset_id = ? AND output_path IS NOT NULL",
                (asset_id,),
            ).fetchall()
        ]
        connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    deleted = dict(row)
    deleted["job_outputs"] = job_outputs
    return deleted


def create_recipe(settings: Settings, document: dict) -> dict:
    now = utc_now()
    with open_db(settings) as connection, transaction(connection):
        connection.execute(
            """
            INSERT INTO recipes(
                id, asset_id, name, schema_version, revision,
                document_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["recipe_id"],
                document["source_asset_id"],
                document["name"],
                document["schema_version"],
                document["revision"],
                json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                now,
                now,
            ),
        )
    recipe = get_recipe(settings, document["recipe_id"])
    if recipe is None:
        raise RuntimeError("Recipe was not persisted")
    return recipe


def list_recipes(settings: Settings, asset_id: str) -> list[dict]:
    with open_db(settings) as connection:
        rows = connection.execute(
            """
            SELECT document_json FROM recipes
            WHERE asset_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (asset_id,),
        ).fetchall()
    return [json.loads(row["document_json"]) for row in rows]


def get_recipe(settings: Settings, recipe_id: str) -> dict | None:
    with open_db(settings) as connection:
        row = connection.execute(
            "SELECT document_json FROM recipes WHERE id = ?",
            (recipe_id,),
        ).fetchone()
    return json.loads(row["document_json"]) if row else None


def update_recipe(
    settings: Settings,
    recipe_id: str,
    document: dict,
    expected_revision: int,
) -> dict | None:
    with open_db(settings) as connection, transaction(connection):
        row = connection.execute(
            "SELECT revision, document_json FROM recipes WHERE id = ?",
            (recipe_id,),
        ).fetchone()
        if row is None:
            return None
        current_revision = int(row["revision"])
        if current_revision != expected_revision:
            raise RecipeRevisionConflict
        updated = dict(document)
        updated["revision"] = current_revision + 1
        connection.execute(
            """
            UPDATE recipes
            SET name = ?, schema_version = ?, revision = ?,
                document_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["schema_version"],
                updated["revision"],
                json.dumps(updated, ensure_ascii=False, separators=(",", ":")),
                utc_now(),
                recipe_id,
            ),
        )
    return updated


def delete_recipe(settings: Settings, recipe_id: str) -> bool:
    with open_db(settings) as connection, transaction(connection):
        cursor = connection.execute(
            "DELETE FROM recipes WHERE id = ?",
            (recipe_id,),
        )
    return cursor.rowcount > 0


def create_job(
    settings: Settings,
    *,
    job_id: str,
    kind: str,
    asset_id: str,
    recipe_id: str | None = None,
    recipe_revision: int | None = None,
    recipe_snapshot: dict | None = None,
    output_format: str | None = None,
    output_quality: int | None = None,
) -> None:
    with open_db(settings) as connection, transaction(connection):
        connection.execute(
            """
            INSERT INTO jobs(
                id, kind, asset_id, recipe_id, recipe_revision, recipe_snapshot,
                status, output_format, output_quality, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)
            """,
            (
                job_id,
                kind,
                asset_id,
                recipe_id,
                recipe_revision,
                (
                    json.dumps(
                        recipe_snapshot,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    if recipe_snapshot is not None
                    else None
                ),
                output_format,
                output_quality,
                utc_now(),
            ),
        )


def discard_queued_previews(settings: Settings, asset_id: str) -> int:
    with open_db(settings) as connection, transaction(connection):
        cursor = connection.execute(
            """
            DELETE FROM jobs
            WHERE kind = 'preview' AND asset_id = ? AND status = 'queued'
            """,
            (asset_id,),
        )
    return cursor.rowcount


def recover_interrupted_jobs(settings: Settings) -> int:
    with open_db(settings) as connection, transaction(connection):
        cursor = connection.execute(
            """
            UPDATE jobs
            SET status = 'queued', started_at = NULL, finished_at = NULL
            WHERE status = 'running'
            """
        )
    return cursor.rowcount


def claim_next_job(settings: Settings) -> dict | None:
    with open_db(settings) as connection, transaction(connection):
        row = connection.execute(
            """
            SELECT * FROM jobs
            WHERE status = 'queued'
            ORDER BY created_at, id
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        started_at = utc_now()
        connection.execute(
            """
            UPDATE jobs
            SET status = 'running', started_at = ?, error_code = NULL
            WHERE id = ? AND status = 'queued'
            """,
            (started_at, row["id"]),
        )
        claimed = dict(row)
        claimed["status"] = "running"
        claimed["started_at"] = started_at
    return claimed


def complete_thumbnail_job(
    settings: Settings,
    *,
    job_id: str,
    asset_id: str,
    thumbnail_relative_path: str,
) -> bool:
    with open_db(settings) as connection, transaction(connection):
        asset = connection.execute(
            "SELECT id FROM assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        if asset is None:
            return False
        connection.execute(
            """
            UPDATE assets
            SET thumbnail_status = 'ready', thumbnail_relative_path = ?
            WHERE id = ?
            """,
            (thumbnail_relative_path, asset_id),
        )
        connection.execute(
            """
            UPDATE jobs
            SET status = 'completed', finished_at = ?
            WHERE id = ? AND status = 'running'
            """,
            (utc_now(), job_id),
        )
    return True


def complete_job(
    settings: Settings,
    *,
    job_id: str,
    output_relative_path: str,
) -> bool:
    with open_db(settings) as connection, transaction(connection):
        cursor = connection.execute(
            """
            UPDATE jobs
            SET status = 'completed', output_path = ?, finished_at = ?
            WHERE id = ? AND status = 'running'
            """,
            (output_relative_path, utc_now(), job_id),
        )
    return cursor.rowcount > 0


def fail_job(
    settings: Settings,
    *,
    job_id: str,
    asset_id: str,
    error_code: str,
) -> None:
    now = utc_now()
    with open_db(settings) as connection, transaction(connection):
        job = connection.execute(
            "SELECT kind FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        connection.execute(
            """
            UPDATE jobs
            SET status = 'failed', error_code = ?, finished_at = ?
            WHERE id = ? AND status = 'running'
            """,
            (error_code, now, job_id),
        )
        if job and job["kind"] == "thumbnail":
            connection.execute(
                """
                UPDATE assets
                SET thumbnail_status = 'failed'
                WHERE id = ?
                """,
                (asset_id,),
            )


def get_job(settings: Settings, job_id: str) -> dict | None:
    with open_db(settings) as connection:
        row = connection.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def remove_asset_files(settings: Settings, asset: dict) -> None:
    paths = [settings.project_root / asset["relative_path"]]
    if asset.get("thumbnail_relative_path"):
        paths.append(settings.project_root / asset["thumbnail_relative_path"])
    paths.extend(
        settings.project_root / output_path
        for output_path in asset.get("job_outputs", [])
    )
    for path in paths:
        if path.is_file():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    original_dir = (settings.project_root / asset["relative_path"]).parent
    if original_dir.is_dir():
        try:
            original_dir.rmdir()
        except OSError:
            pass


def project_path(settings: Settings, relative_path: str) -> Path:
    path = (settings.project_root / relative_path).resolve()
    root = settings.project_root.resolve()
    if root not in path.parents:
        raise ValueError("Unsafe storage path")
    return path
