"""
SOC-IQ Configuration

Centralized application configuration.

Loads environment variables from .env and exposes
application-wide configuration values.
"""

from __future__ import annotations

import os
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

VIRUSTOTAL_TIMEOUT: int = int(
    os.getenv(
        "VIRUSTOTAL_TIMEOUT",
        "30",
    )
)

VIRUSTOTAL_BASE_URL: str = os.getenv(
    "VIRUSTOTAL_BASE_URL",
    "https://www.virustotal.com/api/v3",
)