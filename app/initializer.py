"""
Application startup and environment initialization.
"""

from app.config import LOGS_DIR, OUTPUT_DIR
from app.logger import logger


def initialize_application():
    """
    Prepare the application environment before execution.

    Creates required directories if they do not already exist.
    """

    required_directories = (
        LOGS_DIR,
        OUTPUT_DIR,
    )

    for directory in required_directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    logger.info(
        "Application environment initialized successfully."
    )