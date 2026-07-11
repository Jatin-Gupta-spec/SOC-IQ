"""
Custom exception hierarchy for the SOC-IQ application.

These exceptions represent application-specific failures
and provide clearer error reporting than generic Python
exceptions.
"""


class SOCIQError(Exception):
    """
    Base exception for all SOC-IQ application errors.
    """

    pass


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


class ExportError(SOCIQError):
    """
    Raised when exporting analysis results fails.
    """

    pass