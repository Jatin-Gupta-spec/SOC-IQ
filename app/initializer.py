"""
Application initialization utilities.
"""

from __future__ import annotations

from app.config import (
    DATABASE_DIR,
    LOGS_DIR,
    OUTPUT_DIR,
    SAMPLES_DIR,
)
from app.logger import logger


def initialize_application() -> None:
    """
    Prepare the application environment.

    Creates all required project directories
    before the application starts.
    """

    directories = (
        LOGS_DIR,
        OUTPUT_DIR,
        DATABASE_DIR,
        SAMPLES_DIR,
    )

    for directory in directories:

        try:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError as error:
            # Startup should still fail loudly (a missing writable
            # directory means logging, the database, and exports are
            # all unusable) -- but the caller needs to know *which*
            # directory and why, rather than an unlabeled OSError
            # surfacing from inside pathlib.
            logger.error(
                "Failed to create required directory %s: %s",
                directory,
                error,
            )
            raise

        logger.debug(
            "Verified directory: %s",
            directory,
        )