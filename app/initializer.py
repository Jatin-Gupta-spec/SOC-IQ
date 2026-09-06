"""
Application initialization utilities.
"""

from __future__ import annotations

from app.config import (
    CONFIG_DIR,
    DATABASE_DIR,
    EXPORTS_DIR,
    LOGS_DIR,
    SAMPLES_DIR,
)
from app.logger import logger


def initialize_application() -> None:
    """
    Prepare the application environment.

    Creates every required persistent application-data directory
    (Class 2: database, logs, config, the app-owned default export
    location) before the application starts, plus SAMPLES_DIR, the
    one bundled resource directory SOC-IQ has historically verified
    here too. Must run before app.database.connection /
    app.logger / app.settings.repository perform their first write --
    see app/api/app.py's startup wiring for the production entrypoint,
    and docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md Part 15
    item 2 for why that wiring was previously missing.
    """

    directories = (
        LOGS_DIR,
        DATABASE_DIR,
        CONFIG_DIR,
        EXPORTS_DIR,
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