"""
Custom exception hierarchy for the SOC-IQ application.

These exceptions represent application-specific failures
and provide clearer error reporting than generic Python
exceptions.
"""

from __future__ import annotations


class SOCIQError(Exception):
    """
    Base exception for all SOC-IQ application errors.
    """

    pass


# ==========================================================
# Report Processing
# ==========================================================


class ReportReadError(SOCIQError):
    """
    Raised when a malware report cannot be read.
    """

    pass


class IOCExtractionError(SOCIQError):
    """
    Raised when IOC extraction fails.
    """

    pass


class DuplicateInvestigationError(SOCIQError):
    """
    Raised when an investigation already exists
    for the selected report.
    """

    def __init__(
        self,
        report_name: str,
    ) -> None:
        super().__init__(
            (
                f"An investigation for '{report_name}' "
                "already exists."
            )
        )

        self.report_name = report_name


# ==========================================================
# Export
# ==========================================================


class ExportError(SOCIQError):
    """
    Raised when exporting analysis results fails.
    """

    pass


# ==========================================================
# Database
# ==========================================================


class DatabaseError(SOCIQError):
    """
    Raised for database-related failures.
    """

    pass


# ==========================================================
# Risk Scoring
# ==========================================================


class RiskScoringError(SOCIQError):
    """
    Raised when risk score calculation fails.
    """

    pass


# ==========================================================
# Validation
# ==========================================================


class ValidationError(SOCIQError):
    """
    Raised when application validation fails.
    """

    pass