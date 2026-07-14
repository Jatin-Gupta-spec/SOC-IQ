"""
Custom exceptions for the Threat Intelligence layer.

These exceptions provide a stable interface for the rest of the
application regardless of which HTTP library or provider is used.
"""


class ThreatIntelError(Exception):
    """
    Base exception for all Threat Intelligence errors.
    """


class VirusTotalError(ThreatIntelError):
    """
    Base exception for VirusTotal-related errors.
    """


class MissingAPIKeyError(VirusTotalError):
    """
    Raised when the VirusTotal API key is missing.
    """

class InvalidHashError(VirusTotalError):
    """
    Raised when an invalid SHA-256 hash is provided.
    """

class InvalidAPIKeyError(VirusTotalError):
    """
    Raised when the VirusTotal API key is invalid or unauthorized.
    """


class RateLimitExceededError(VirusTotalError):
    """
    Raised when the VirusTotal API rate limit is exceeded.
    """


class ThreatIntelConnectionError(VirusTotalError):
    """
    Raised when a network connection cannot be established.
    """


class ThreatIntelTimeoutError(VirusTotalError):
    """
    Raised when a request times out.
    """


class UnexpectedAPIResponseError(VirusTotalError):
    """
    Raised when the API returns an unexpected or malformed response.
    """