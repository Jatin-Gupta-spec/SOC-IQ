"""
Database migration runner for SOC-IQ.

Applies ordered, versioned SQL migration files to the SQLite database
and tracks the currently applied schema version in a dedicated,
single-row `schema_version` table.

Design (see docs/architecture/09-database-architecture.md and the
Part 15 audit that authorized this implementation):

- No ORM, no external migration dependency -- Python stdlib `sqlite3`
  plus plain `.sql` files is sufficient at this project's scale
  (ADR-005: SQLite is retained long-term; a single-user desktop
  application with one writer).
- Migrations are discovered from `app/database/migrations/`, named
  `NNNN_description.sql` (four-digit, zero-padded, strictly
  increasing version number), and always applied in numeric version
  order -- never filesystem/glob enumeration order.
- Each migration runs inside a single explicit transaction. A failed
  statement rolls back that entire migration; the recorded schema
  version does not advance past the last successfully applied
  migration.
- If the database's recorded version is *newer* than the newest
  migration this build knows about, the runner fails closed: it never
  downgrades, alters, or silently continues against a schema it does
  not understand.
- Bootstrap: a database created by a pre-migration-runner build
  already contains `investigations` but no `schema_version` table.
  That is treated identically to a version-0 database, and
  `0001_initial.sql` is written to be a no-op against an
  already-existing `investigations` table (see that file's header),
  so applying it neither loses nor alters existing data -- it only
  records that the database is now at version 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection
from sqlite3 import connect as sqlite_connect

from app.logger import logger

MIGRATIONS_DIR: Path = Path(__file__).resolve().parent / "migrations"

# Four digits, an underscore, a description, and the .sql extension.
# Deliberately strict: anything that doesn't match this shape is
# rejected rather than guessed at.
_MIGRATION_FILENAME_PATTERN = re.compile(r"^(\d{4})_[A-Za-z0-9_]+\.sql$")


class MigrationError(Exception):
    """
    Raised whenever the migration runner cannot safely proceed.

    Covers: malformed or duplicate migration files, a migration that
    fails partway through, and a database schema version newer than
    this build understands. In every case, the caller must treat this
    as fatal -- the application must not start normal database-backed
    operation while this exception is live.
    """


@dataclass(frozen=True, slots=True)
class Migration:
    """A single discovered migration file."""

    version: int
    name: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def _discover_migrations(
    migrations_dir: Path,
) -> list[Migration]:
    """
    Discover and validate every migration file in `migrations_dir`.

    Returns migrations sorted by version number. Raises
    MigrationError on a malformed filename or a duplicate version --
    both are treated as a fatal configuration error rather than
    something to guess around.
    """

    if not migrations_dir.is_dir():
        raise MigrationError(
            f"Migrations directory not found: {migrations_dir}"
        )

    migrations: list[Migration] = []
    seen_versions: dict[int, str] = {}

    for path in sorted(migrations_dir.iterdir()):

        if not path.is_file():
            continue

        if path.suffix != ".sql":
            continue

        match = _MIGRATION_FILENAME_PATTERN.match(path.name)

        if match is None:
            raise MigrationError(
                f"Malformed migration filename: {path.name!r}. "
                "Expected format: NNNN_description.sql "
                "(four digits, underscore, description)."
            )

        version = int(match.group(1))

        if version in seen_versions:
            raise MigrationError(
                f"Duplicate migration version {version}: "
                f"{seen_versions[version]!r} and {path.name!r} both "
                "claim it."
            )

        seen_versions[version] = path.name

        migrations.append(
            Migration(
                version=version,
                name=path.name,
                path=path,
            )
        )

    migrations.sort(key=lambda migration: migration.version)

    return migrations


def _split_statements(sql_script: str) -> list[str]:
    """
    Split a migration file's SQL text into individual statements.

    This is a deliberately simple split on ';'. Migration files in
    this project are expected to contain only straightforward DDL
    (CREATE TABLE, CREATE INDEX, and similar) -- never string
    literals or trigger bodies containing embedded semicolons. A
    migration needing either of those must not be introduced without
    first revisiting this function.
    """

    statements = [
        statement.strip()
        for statement in sql_script.split(";")
    ]

    return [
        statement
        for statement in statements
        if statement
    ]


def _table_exists(
    connection: Connection,
    table_name: str,
) -> bool:

    cursor = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name = ?;",
        (table_name,),
    )

    return cursor.fetchone() is not None


def _get_current_version(connection: Connection) -> int:
    """
    Determine the schema version currently recorded in the database.

    Absence of `schema_version` means version 0 -- covering both a
    genuinely brand-new database and the bootstrap case (a
    pre-migration-runner database that already has `investigations`
    but has never recorded a version).
    """

    if not _table_exists(connection, "schema_version"):
        return 0

    cursor = connection.execute(
        "SELECT version FROM schema_version;"
    )

    row = cursor.fetchone()

    if row is None:
        raise MigrationError(
            "schema_version table exists but contains no version "
            "row. Refusing to guess the current schema version."
        )

    return int(row[0])


def _set_version(
    connection: Connection,
    version: int,
) -> None:
    """
    Record `version` as the current schema version.

    Must be called only from within the same transaction as the
    migration whose success it is recording -- see `run_migrations`.
    Maintains the invariant of exactly one row in `schema_version`.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );
        """
    )

    cursor = connection.execute(
        "SELECT COUNT(*) FROM schema_version;"
    )

    row_count = cursor.fetchone()[0]

    if row_count == 0:

        connection.execute(
            "INSERT INTO schema_version (version) VALUES (?);",
            (version,),
        )

    else:

        connection.execute(
            "UPDATE schema_version SET version = ?;",
            (version,),
        )


def _fail_closed_on_newer_schema(
    current_version: int,
    latest_known_version: int,
) -> None:

    raise MigrationError(
        f"Database schema version ({current_version}) is newer "
        "than this application build understands (latest known "
        f"migration: {latest_known_version}). Refusing to start: "
        "downgrading, altering, or silently continuing against a "
        "newer schema is not supported. This database was likely "
        "created or migrated by a newer version of SOC-IQ."
    )


def _apply_migrations_on_connection(
    connection: Connection,
    migrations_dir: Path,
) -> int:
    """
    Apply any pending migrations to an already-open `connection`.

    `connection` must be in autocommit mode (isolation_level = None)
    so that this function has exclusive, explicit control over
    transaction boundaries -- see `run_migrations`.

    Concurrency (F-21B4E-01 fix): a second caller may commit one or
    more migrations at any point while this connection has not yet
    acquired SQLite's write lock. The pending-migration list can
    therefore never be computed once, up front, and then applied
    blindly -- doing so is exactly the TOCTOU that let a connection
    attempt to re-apply DDL another connection had already committed
    (e.g. a duplicate `ALTER TABLE ... ADD COLUMN`). The invariant
    this function now maintains instead: a migration is only ever
    applied if it is still pending *after* this connection holds the
    write lock -- so the schema version is re-read fresh, under
    `BEGIN IMMEDIATE`, on every single migration, one at a time.
    """

    migrations = _discover_migrations(migrations_dir)

    latest_known_version = (
        migrations[-1].version if migrations else 0
    )

    # Lock-free pre-check. This is purely a fast path -- it lets an
    # already-current database (by far the common case) return
    # without ever opening a transaction, exactly as before. It is
    # *not* relied on for correctness: it can be stale under
    # concurrency, but the only consequence of that staleness is
    # entering the loop below to discover, under the write lock, that
    # there is in fact nothing left to do. The authoritative version
    # read always happens inside the loop.
    precheck_version = _get_current_version(connection)

    if precheck_version > latest_known_version:
        _fail_closed_on_newer_schema(precheck_version, latest_known_version)

    if precheck_version == latest_known_version:

        logger.info(
            "Database schema is up to date (version %d). "
            "No migrations to apply.",
            precheck_version,
        )

        return precheck_version

    final_version = precheck_version

    while True:

        connection.execute("BEGIN IMMEDIATE;")

        # Re-read the schema version now that this connection holds
        # the write lock. Another connection may have committed one
        # or more migrations between the pre-check above (or the
        # previous loop iteration's COMMIT) and this BEGIN IMMEDIATE
        # actually acquiring the lock -- this is the fresh value that
        # decides what, if anything, is still pending.
        current_version = _get_current_version(connection)

        if current_version > latest_known_version:
            connection.execute("ROLLBACK;")
            _fail_closed_on_newer_schema(current_version, latest_known_version)

        next_migration = next(
            (
                migration
                for migration in migrations
                if migration.version > current_version
            ),
            None,
        )

        if next_migration is None:

            # Every migration this connection was ever going to
            # apply has already been committed -- by us, in an
            # earlier iteration, or by a concurrent caller that won
            # the race. Nothing left to do; release the lock.
            connection.execute("ROLLBACK;")
            final_version = current_version
            break

        logger.info(
            "Applying migration %04d (%s): %d -> %d",
            next_migration.version,
            next_migration.name,
            current_version,
            next_migration.version,
        )

        try:

            for statement in _split_statements(next_migration.sql):
                connection.execute(statement + ";")

            _set_version(connection, next_migration.version)

            connection.execute("COMMIT;")

        except Exception as exc:

            connection.execute("ROLLBACK;")

            logger.exception(
                "Migration %04d (%s) failed; rolled back. "
                "Database remains at version %d.",
                next_migration.version,
                next_migration.name,
                current_version,
            )

            raise MigrationError(
                f"Migration {next_migration.version:04d} "
                f"({next_migration.name}) failed and was rolled "
                f"back. Database remains at version "
                f"{current_version}. Underlying error: {exc}"
            ) from exc

        final_version = next_migration.version

    logger.info(
        "Database migrated successfully to version %d.",
        final_version,
    )

    return final_version


def run_migrations(
    database_path: Path,
    migrations_dir: Path = MIGRATIONS_DIR,
) -> int:
    """
    Bring the SQLite database at `database_path` up to the latest
    known schema version.

    Opens a short-lived, dedicated connection for the duration of the
    migration only -- this function does not accept or return a
    connection for reuse, so it cannot interfere with the
    connection-per-operation model the rest of the application uses
    (see app.database.connection.DatabaseConnection).

    Safe to call multiple times: a database already at the latest
    version is a no-op. Fails closed (raises MigrationError) rather
    than applying anything on: a malformed or duplicate migration
    file, a migration that fails partway, or a database whose
    recorded version is newer than this build understands.

    Returns the resulting schema version.
    """

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite_connect(database_path)

    # Autocommit mode: this function manages transaction boundaries
    # itself (BEGIN IMMEDIATE / COMMIT / ROLLBACK per migration)
    # rather than relying on the sqlite3 module's implicit-transaction
    # heuristics, which do not reliably wrap DDL statements.
    connection.isolation_level = None

    try:

        return _apply_migrations_on_connection(
            connection,
            migrations_dir,
        )

    finally:

        connection.close()
