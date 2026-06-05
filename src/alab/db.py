from __future__ import annotations

import fcntl
import hashlib
import json
import re
import sqlite3
import time
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import AlabError
from .home import Home, ensure_layout

SCHEMA_VERSION = 3
MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATION_FILE_RE = re.compile(r"^(\d+)_([a-z0-9_]+)\.sql$")
DEFAULT_MIGRATION_LOCK_TIMEOUT_MS = 30000
MIGRATION_LOCK_POLL_SECONDS = 0.05
DEFAULT_SQLITE_BUSY_TIMEOUT_MS = 5000


@dataclass(frozen=True)
class MigrationFile:
    version: int
    name: str
    checksum: str
    sql: str


# Runtime schema SQL lives in src/alab/migrations/*.sql.


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_obj(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise AlabError("STORAGE_ERROR", "stored JSON value is not an object")
    return value


def contract_json_obj(
    text: str,
    *,
    label: str,
    allowed_keys: set[str],
    required_keys: set[str] | None = None,
    schema_version: int = 1,
) -> dict[str, Any]:
    value = json_obj(text)
    required = {"schema_version", *(required_keys or set())}
    unknown = sorted(set(value) - allowed_keys)
    missing = sorted(required - set(value))
    if missing:
        raise AlabError("STORAGE_ERROR", f"{label} missing JSON keys: {', '.join(missing)}")
    if unknown:
        raise AlabError("STORAGE_ERROR", f"{label} contains unknown JSON keys: {', '.join(unknown)}")
    if isinstance(value.get("schema_version"), bool) or value.get("schema_version") != schema_version:
        raise AlabError("STORAGE_ERROR", f"{label} schema_version must be {schema_version}")
    return value


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _load_migration_files() -> list[MigrationFile]:
    if not MIGRATIONS_DIR.exists():
        raise AlabError("STORAGE_ERROR", f"migration directory not found: {MIGRATIONS_DIR}")
    migrations: list[MigrationFile] = []
    seen: set[int] = set()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = MIGRATION_FILE_RE.match(path.name)
        if match is None:
            raise AlabError("STORAGE_ERROR", f"invalid migration filename: {path.name}")
        version = int(match.group(1))
        name = match.group(2)
        if version in seen:
            raise AlabError("STORAGE_ERROR", f"duplicate migration version: {version}")
        seen.add(version)
        data = path.read_bytes()
        sql = data.decode("utf-8")
        migrations.append(MigrationFile(version=version, name=name, checksum=_sha256(data), sql=sql))
    if not migrations:
        raise AlabError("STORAGE_ERROR", "no migration files found")
    migrations.sort(key=lambda migration: migration.version)
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, SCHEMA_VERSION + 1)):
        raise AlabError("STORAGE_ERROR", "migration files do not match the supported schema version")
    return migrations


def _schema_migrations_exist(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    return row is not None


def _database_has_user_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
    ).fetchone()
    return row is not None


def _applied_migrations(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    if not _schema_migrations_exist(conn):
        if _database_has_user_tables(conn):
            raise AlabError("STORAGE_ERROR", "database has schema but no migration history")
        return {}
    rows = conn.execute("SELECT version, name, checksum FROM schema_migrations").fetchall()
    return {int(row["version"]): (row["name"], row["checksum"]) for row in rows}


def _backup_database(home: Home, conn: sqlite3.Connection, from_version: int, to_version: int) -> Path | None:
    if from_version == 0:
        return None
    home.backups_path.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = home.backups_path / f"alab-{from_version}-to-{to_version}-{stamp}.db"
    try:
        with sqlite3.connect(backup_path) as backup_conn:
            conn.backup(backup_conn)
    except sqlite3.Error as exc:
        raise AlabError("STORAGE_ERROR", f"failed to create migration backup: {backup_path}") from exc
    return backup_path


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _apply_migration(conn: sqlite3.Connection, migration: MigrationFile) -> None:
    applied_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    script = "\n".join(
        [
            "BEGIN;",
            migration.sql,
            (
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES "
                f"({migration.version}, {_sql_literal(migration.name)}, {_sql_literal(migration.checksum)}, {_sql_literal(applied_at)});"
            ),
            "COMMIT;",
        ]
    )
    try:
        conn.executescript(script)
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise AlabError("STORAGE_ERROR", f"failed to apply migration {migration.version}") from exc


@contextmanager
def _migration_lock(home: Home) -> Iterator[None]:
    lock_path = home.path / ".migration.lock"
    timeout_ms = _migration_lock_timeout_ms(home)
    deadline = time.monotonic() + (timeout_ms / 1000)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AlabError(
                        "RESOURCE_BUSY",
                        "migration lock is busy",
                        "retry after the current migration completes",
                    ) from exc
                time.sleep(min(MIGRATION_LOCK_POLL_SECONDS, remaining))
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _migration_lock_timeout_ms(home: Home) -> int:
    return _global_config_positive_int(
        home,
        "locks",
        "acquire_timeout_ms",
        default=DEFAULT_MIGRATION_LOCK_TIMEOUT_MS,
    )


def _sqlite_busy_timeout_ms(home: Home) -> int:
    return _global_config_positive_int(
        home,
        "storage",
        "busy_timeout_ms",
        default=DEFAULT_SQLITE_BUSY_TIMEOUT_MS,
    )


def _global_config_positive_int(home: Home, section: str, key: str, *, default: int) -> int:
    try:
        data = tomllib.loads(home.config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return default
    section_data = data.get(section, {})
    if not isinstance(section_data, dict):
        return default
    value = section_data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return default
    return value


class Database:
    def __init__(self, home: Home):
        self.home = home

    def connect(self) -> sqlite3.Connection:
        ensure_layout(self.home)
        conn = sqlite3.connect(self.home.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(f"PRAGMA busy_timeout = {_sqlite_busy_timeout_ms(self.home)}")
        return conn

    def migrate(self) -> None:
        ensure_layout(self.home)
        migrations = _load_migration_files()
        migration_by_version = {migration.version: migration for migration in migrations}
        with _migration_lock(self.home):
            with self.connect() as conn:
                applied = _applied_migrations(conn)
                if applied and max(applied) > SCHEMA_VERSION:
                    raise AlabError("STORAGE_ERROR", "database schema is newer than this ALab version")
                for version, (name, checksum) in applied.items():
                    migration = migration_by_version.get(version)
                    if migration is None:
                        raise AlabError("STORAGE_ERROR", f"unknown applied migration version: {version}")
                    if migration.name != name or migration.checksum != checksum:
                        raise AlabError("STORAGE_ERROR", f"migration checksum mismatch for version {version}")
                current_version = max(applied, default=0)
                initial_version = current_version
                for migration in migrations:
                    if migration.version <= current_version:
                        continue
                    if initial_version > 0:
                        _backup_database(self.home, conn, current_version, migration.version)
                    _apply_migration(conn, migration)
                    current_version = migration.version

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def connect_initialized(home: Home) -> sqlite3.Connection:
    if not home.db_path.exists():
        raise AlabError("CONTEXT_NOT_FOUND", "ALab home is not initialized", "alab auth init")
    db = Database(home)
    db.migrate()
    return db.connect()


def one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def all_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params).fetchall())
