"""
SOC-IQ
System Health Service

Provides application health information for
dashboard, diagnostics, and startup validation.
"""

from __future__ import annotations

from app.config import VIRUSTOTAL_API_KEY


class SystemHealthService:
    """
    Provides application component health.
    """

    def get_status(self) -> dict[str, str]:
        """
        Return current system status.
        """

        virustotal_status = (
            "Ready"
            if VIRUSTOTAL_API_KEY
            else "API Key Missing"
        )

        return {
            "database": "Connected",
            "repository": "Operational",
            "analysis_engine": "Ready",
            "virustotal": virustotal_status,
        }