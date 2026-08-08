"""
Database connection management for SOC-IQ.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from sqlite3 import Connection

from app.config import (
    DATABASE_DIR,
    DATABASE_PATH,
)
from app.logger import logger


class DatabaseConnection:
    """
    Manages the SQLite database connection for SOC-IQ.

    This class is responsible only for creating,
    providing, and safely closing database
    connections.
    """

    def __init__(
        self,
        database_path: Path = DATABASE_PATH,
    ) -> None:
        """
        Initialize the database connection manager.

        Args:
            database_path:
                Path to the SQLite database.
        """

        self._database_path = database_path
        self._connection: Connection | None = None

    def connect(self) -> Connection:
        """
        Create and return a SQLite connection.

        Returns:
            sqlite3.Connection
        """

        if self._connection is None:

            DATABASE_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            logger.info(
                "Opening SQLite database: %s",
                self._database_path,
            )

            connection = sqlite3.connect(
                self._database_path,
            )

            # `self._connection` must not be assigned until every
            # initialization step below has succeeded. Previously
            # the raw `sqlite3.connect()` result was assigned to
            # `self._connection` immediately, so a failure in one of
            # the subsequent `execute()` calls (e.g. the database
            # file is locked, corrupted, or on read-only storage)
            # left a half-configured connection in place: the
            # `is None` guard above would then be false on every
            # future call, so `connect()` would keep handing out
            # that broken connection forever instead of retrying,
            # and the native OS handle from the failed attempt was
            # never closed. Building the connection locally and only
            # publishing it to `self._connection` after everything
            # succeeds keeps every partial failure honest: it
            # propagates instead of being masked, and the instance
            # is left able to retry on the next call.
            try:

                connection.row_factory = sqlite3.Row

                connection.execute(
                    "PRAGMA foreign_keys = ON;"
                )

                # Report analysis (see app/analyzer.py) runs on a
                # background QThread and writes to this database
                # while GUI-thread pages (history, IOC viewer
                # refreshes) can read from it concurrently. Every
                # repository call opens a fresh connection to this
                # same on-disk file (see `close()`/`__exit__`), so
                # the default rollback-journal mode -- which locks
                # the whole database for the duration of a write and
                # blocks concurrent readers -- is a realistic
                # "database is locked" risk here. WAL lets readers
                # proceed without blocking on a concurrent writer.
                # This does not change any method's behavior or
                # signature, only the on-disk journaling strategy.
                connection.execute(
                    "PRAGMA journal_mode = WAL;"
                )

            except Exception:

                logger.exception(
                    "Failed to initialize SQLite connection: %s",
                    self._database_path,
                )

                connection.close()

                raise

            self._connection = connection

        return self._connection

    def close(self) -> None:
        """
        Close the active database connection.
        """

        if self._connection is not None:

            logger.info(
                "Closing SQLite database."
            )

            self._connection.close()

            self._connection = None

    def __enter__(
        self,
    ) -> Connection:
        """
        Context manager entry.
        """

        return self.connect()

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """
        Context manager exit.
        """

        self.close()