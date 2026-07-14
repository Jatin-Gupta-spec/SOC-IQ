"""
Application configuration.

This module loads environment variables from the project's
.env file and exposes typed configuration values for the
rest of the application.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


# Load environment variables from the project root.
load_dotenv()


def _get_int(name: str, default: int) -> int:
    """
    Read an integer environment variable.

    Args:
        name:
            Environment variable name.

        default:
            Default value if the variable is missing or invalid.

    Returns:
        Parsed integer value.
    """

    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)

    except ValueError:
        return default


# ==========================================================
# Application
# ==========================================================

APP_ENV: str = os.getenv(
    "APP_ENV",
    "development",
).strip()


# ==========================================================
# Logging
# ==========================================================

LOG_LEVEL: str = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()


# ==========================================================
# VirusTotal
# ==========================================================

VIRUSTOTAL_API_KEY: str = os.getenv(
    "VIRUSTOTAL_API_KEY",
    "",
).strip()


VIRUSTOTAL_TIMEOUT: int = _get_int(
    "VIRUSTOTAL_TIMEOUT",
    30,
)


VIRUSTOTAL_BASE_URL: str = os.getenv(
    "VIRUSTOTAL_BASE_URL",
    "https://www.virustotal.com/api/v3",
).strip()