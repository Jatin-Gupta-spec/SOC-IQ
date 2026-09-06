"""
Error-code catalog, per docs/contracts/error-model.md.

Maps the SOC-IQ domain's *existing* exception classes onto stable,
frontend-facing error codes. Per docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md
S11, app/database/* and app/reporting/* were confirmed this phase to have
no per-module exception hierarchy of their own -- they raise the generic
app.exceptions.DatabaseError / ExportError, which is why those two map to a
single generic code each rather than a fine-grained catalog like
app/threat_intel/exceptions.py gets.
"""

from __future__ import annotations

from app.exceptions import DatabaseError, DuplicateInvestigationError, SOCIQError
from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidDomainError,
    InvalidHashError,
    InvalidIPError,
    InvalidURLError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
    ThreatIntelTimeoutError,
    UnexpectedAPIResponseError,
)

# Application-layer codes with no single existing exception class behind them.
INVESTIGATION_NOT_FOUND = "INVESTIGATION_NOT_FOUND"
INVALID_COMMAND_PAYLOAD = "INVALID_COMMAND_PAYLOAD"
REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
INTERNAL_ERROR = "INTERNAL_ERROR"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

# Exception-class -> error-code mapping. Order matters: more specific
# exception types are listed before their base classes so a lookup that
# walks the MRO (see `code_for_exception`) finds the most specific match.
_EXCEPTION_CODE_MAP: dict[type[Exception], str] = {
    # AnalyzeController.validate_report() raises a bare FileNotFoundError
    # (not a SOCIQError subclass) for a missing/invalid report path -- see
    # app/gui/controllers/analyze_controller.py.
    FileNotFoundError: REPORT_NOT_FOUND,
    DuplicateInvestigationError: "DUPLICATE_INVESTIGATION",
    DatabaseError: "DATABASE_ERROR",
    InvalidHashError: "TI_INVALID_IOC",
    InvalidIPError: "TI_INVALID_IOC",
    InvalidDomainError: "TI_INVALID_IOC",
    InvalidURLError: "TI_INVALID_IOC",
    InvalidAPIKeyError: "TI_INVALID_API_KEY",
    RateLimitExceededError: "TI_RATE_LIMITED",
    ThreatIntelConnectionError: "TI_PROVIDER_UNAVAILABLE",
    ThreatIntelTimeoutError: "TI_PROVIDER_UNAVAILABLE",
    UnexpectedAPIResponseError: "TI_PROVIDER_ERROR",
    SOCIQError: "APPLICATION_ERROR",
}


def code_for_exception(error: Exception) -> str:
    """
    Return the stable error code for a raised exception, walking the MRO
    so subclasses not explicitly listed still map onto their nearest
    listed ancestor rather than falling through to INTERNAL_ERROR.
    """

    for exc_type in type(error).__mro__:
        if exc_type in _EXCEPTION_CODE_MAP:
            return _EXCEPTION_CODE_MAP[exc_type]

    return INTERNAL_ERROR
