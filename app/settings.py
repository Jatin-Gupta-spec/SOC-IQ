"""
Application settings.

This module loads configuration from environment variables
and exposes typed constants for the rest of the application.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load environment variables from the project's .env file.
load_dotenv()


def _get_int(name: str, default: int) -> int:
    """
    Read an integer environment variable.

    If the value is missing or invalid, return the provided default.
    """
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


APP_ENV: str = os.getenv("APP_ENV", "development")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

VIRUSTOTAL_API_KEY: str = os.getenv("VIRUSTOTAL_API_KEY", "").strip()

VIRUSTOTAL_TIMEOUT: int = _get_int(
    "VIRUSTOTAL_TIMEOUT",
    30,
)