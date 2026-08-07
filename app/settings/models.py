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

    export_directory: str = str(
        Path("output").resolve()
    )

    theme: str = "Dark Mode (SOC-IQ Standard)"

    def __repr__(self) -> str:
        """
        Redact the VirusTotal API key from the default repr.

        `@dataclass` generates a repr that includes every field
        verbatim. Without this override, `virustotal_api_key` would
        be printed in full anywhere this object ends up in a log
        line, a debugger, or an exception message/traceback --
        exactly the kind of accidental secret exposure this field
        exists to avoid.
        """

        redacted_key = "<redacted>" if self.virustotal_api_key else ""

        return (
            f"{self.__class__.__name__}("
            f"virustotal_api_key={redacted_key!r}, "
            f"export_directory={self.export_directory!r}, "
            f"theme={self.theme!r})"
        )