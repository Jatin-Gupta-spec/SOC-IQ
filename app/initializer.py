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

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.debug(
            "Verified directory: %s",
            directory,
        )