"""
Settings domain models for SOC-IQ.

Defines the application settings structure used throughout the
Settings subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ApplicationSettings:
    """
    Application configuration.

    Attributes
    ----------
    virustotal_api_key:
        VirusTotal API key used for threat intelligence.

    export_directory:
        Default directory for HTML/PDF exports.

    theme:
        Selected application theme.
    """

    virustotal_api_key: str = ""
    export_directory: str = str(Path("output").resolve())
    theme: str = "Dark Mode (SOC-IQ Standard)"