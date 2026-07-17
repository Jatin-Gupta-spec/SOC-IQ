"""
Base migration contract for SOC-IQ.

Every database migration must inherit from this class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from sqlite3 import Connection


class Migration(ABC):
    """
    Base class for every database migration.

    Each migration has:

    • a unique version number
    • a human-readable description
    • an upgrade() implementation
    """

    version: int

    description: str

    @abstractmethod
    def upgrade(
        self,
        connection: Connection,
    ) -> None:
        """
        Apply the database migration.

        Args:
            connection:
                Active SQLite connection.
        """
        raise NotImplementedError