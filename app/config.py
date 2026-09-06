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
from platformdirs import user_data_dir

# ==========================================================
# Application Information
#
# Moved ahead of the path sections below because
# APP_DATA_ROOT (Class 2 persistence root, see next section)
# needs APP_NAME/APP_AUTHOR to resolve the OS-conventional
# per-user data directory.
# ==========================================================

APP_NAME: str = "SOC-IQ"

APP_VERSION: str = "1.0.0"

APP_AUTHOR: str = "Himanshu Gupta"

APP_DESCRIPTION: str = (
    "Security Operations Center Intelligence & IOC Analysis Tool"
)

# ==========================================================
# Base Directory (BUNDLED RESOURCES ONLY)
#
# BASE_DIR is the source/bundle root. It is correct for
# read-only, bundled resources (samples, the .env lookup
# below) and MUST NOT be used for mutable, application-owned
# runtime data (database, logs, settings) -- see
# docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md.
# Under a frozen PyInstaller onefile build, Path(__file__)
# resolves inside the *ephemeral* per-launch extraction
# directory (sys._MEIPASS-style), which is exactly right for
# bundled resources (that's where they're unpacked to) but
# would be wrong -- and previously was wrong -- for anything
# that needs to survive a restart. See APP_DATA_ROOT below
# for the persistent equivalent.
# ==========================================================

BASE_DIR: Path = Path(__file__).resolve().parent.parent

# ==========================================================
# Load Environment Variables
# ==========================================================

load_dotenv(BASE_DIR / ".env")

# ==========================================================
# Bundled Resource Directories (Class 1 -- read-only,
# __file__-relative, correct in both dev and packaged mode)
# ==========================================================

SAMPLES_DIR: Path = BASE_DIR / "samples"
SAMPLE_REPORT: Path = SAMPLES_DIR / "malware_report.txt"

# ==========================================================
# Persistent Application Data Root (Class 2 -- mutable,
# application-owned runtime data: database, logs, settings)
#
# Resolved via platformdirs.user_data_dir(), which consults
# OS-native conventions/environment variables (%APPDATA% on
# Windows, ~/Library/Application Support on macOS,
# XDG_DATA_HOME on Linux) rather than sys.argv[0] or
# __file__. It therefore resolves to the same real,
# persistent-across-restarts location whether SOC-IQ is
# running from source, as `python -m app...`, or as a frozen
# PyInstaller onefile executable -- it never depends on the
# current working directory and never resolves inside
# sys._MEIPASS or any other temporary extraction directory,
# because it never looks at either of those in the first
# place.
# ==========================================================

APP_DATA_ROOT: Path = Path(
    user_data_dir(APP_NAME, APP_AUTHOR, roaming=True)
)

DATABASE_DIR: Path = APP_DATA_ROOT / "database"
LOGS_DIR: Path = APP_DATA_ROOT / "logs"
CONFIG_DIR: Path = APP_DATA_ROOT / "config"

#: Application-owned *default* export destination (advisory only --
#: pre-fills the Settings UI / save-dialog suggestion). Real exports
#: always go wherever the caller explicitly selects; see
#: ExportReportRequest.output_path / ExportHistoryCsvRequest.output_path,
#: which remain Class 3 (user-selected) and are untouched by this
#: constant.
EXPORTS_DIR: Path = APP_DATA_ROOT / "exports"

# ==========================================================
# Default Files
# ==========================================================

LOG_FILE: Path = LOGS_DIR / "soc_iq.log"

DATABASE_FILE: str = "soc_iq.db"
DATABASE_PATH: Path = DATABASE_DIR / DATABASE_FILE

SETTINGS_FILE: Path = CONFIG_DIR / "settings.json"

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
# Environment Configuration
# ==========================================================

APP_ENV: str = os.getenv("APP_ENV", "development")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ==========================================================
# VirusTotal Configuration
#
# Note: the VirusTotal API key itself is NOT read from the
# environment here. The live key is managed by the Settings
# subsystem (app.settings.service.SettingsService), persisted
# to config/settings.json, and editable from the GUI Settings
# page. Only the request timeout and base URL are environment-
# configurable.
# ==========================================================

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