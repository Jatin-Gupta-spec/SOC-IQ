"""
SOC-IQ Configuration

Centralized application configuration.

Loads environment variables from .env and exposes
application-wide configuration values.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# ==========================================================
# Base Directories
# ==========================================================

BASE_DIR: Path = Path(__file__).resolve().parent.parent

# ==========================================================
# Load Environment Variables
# ==========================================================

load_dotenv(BASE_DIR / ".env")

# ==========================================================
# Project Directories
# ==========================================================

SAMPLES_DIR: Path = BASE_DIR / "samples"
OUTPUT_DIR: Path = BASE_DIR / "output"
LOGS_DIR: Path = BASE_DIR / "logs"
DATABASE_DIR: Path = BASE_DIR / "database"

# ==========================================================
# Default Files
# ==========================================================

SAMPLE_REPORT: Path = SAMPLES_DIR / "malware_report.txt"

JSON_EXPORT_FILE: Path = OUTPUT_DIR / "ioc_report.json"
CSV_EXPORT_FILE: Path = OUTPUT_DIR / "ioc_report.csv"

LOG_FILE: Path = LOGS_DIR / "soc_iq.log"

DATABASE_FILE: str = "soc_iq.db"
DATABASE_PATH: Path = DATABASE_DIR / DATABASE_FILE

# ==========================================================
# Supported IOC Types
# ==========================================================

IOC_TYPES: tuple[str, ...] = (
    "IPv4",
    "Domain",
    "URL",
    "Email",
    "MD5",
    "SHA1",
    "SHA256",
    "CVE",
    "Windows File Path",
    "Windows Registry Key",
)

# ==========================================================
# Application Information
# ==========================================================

APP_NAME: str = "SOC-IQ"

APP_VERSION: str = "1.0.0"

APP_AUTHOR: str = "Himanshu Gupta"

APP_DESCRIPTION: str = (
    "Security Operations Center Intelligence & IOC Analysis Tool"
)

# ==========================================================
# Environment Configuration
# ==========================================================

APP_ENV: str = os.getenv("APP_ENV", "development")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ==========================================================
# VirusTotal Configuration
# ==========================================================

VIRUSTOTAL_API_KEY: str = os.getenv(
    "VIRUSTOTAL_API_KEY",
    "",
)

_DEFAULT_VIRUSTOTAL_TIMEOUT = 30

_raw_vt_timeout = os.getenv("VIRUSTOTAL_TIMEOUT")

if _raw_vt_timeout is None:
    VIRUSTOTAL_TIMEOUT: int = _DEFAULT_VIRUSTOTAL_TIMEOUT
else:
    try:
        VIRUSTOTAL_TIMEOUT = int(_raw_vt_timeout)
    except ValueError:
        # This module is imported before app.logger can be (logger.py
        # imports from here), so a bad .env value can't crash the
        # whole application at import time over a malformed timeout --
        # fall back to the default and surface it with a warning
        # instead.
        warnings.warn(
            f"Invalid VIRUSTOTAL_TIMEOUT={_raw_vt_timeout!r}; "
            f"falling back to {_DEFAULT_VIRUSTOTAL_TIMEOUT}.",
            stacklevel=2,
        )
        VIRUSTOTAL_TIMEOUT = _DEFAULT_VIRUSTOTAL_TIMEOUT

VIRUSTOTAL_BASE_URL: str = os.getenv(
    "VIRUSTOTAL_BASE_URL",
    "https://www.virustotal.com/api/v3",
)