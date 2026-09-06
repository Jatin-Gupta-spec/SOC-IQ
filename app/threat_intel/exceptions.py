"""
Custom exceptions for the Threat Intelligence layer.

These exceptions provide a stable interface for the rest of the
application regardless of which HTTP library or provider is used.

Phase 4C, Stage 1 adds a provider-neutral exception hierarchy
alongside the pre-existing VirusTotal-named one (see
`docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` SS10). Every
concrete VirusTotal exception now inherits from *both* its original
`VirusTotalError` base (so every existing `except VirusTotalError`
/ `except InvalidHashError` / etc. call site anywhere in the
codebase keeps matching exactly as before -- this is a strict
superset, not a rename) and the new provider-neutral base that
describes the same failure mode in adapter-agnostic terms (so new,
provider-neutral code -- e.g. a future second provider adapter, or
`ThreatIntelService` once it orchestrates multiple providers -- can
catch `ProviderRateLimitError` without needing to know it might
actually be a `RateLimitExceededError` under the hood). No existing
exception was renamed, removed, or had its base changed in a way
that would break an `isinstance` check that passes today.
"""


class ThreatIntelError(Exception):
    """
    Base exception for all Threat Intelligence errors.
    """


# ==========================================================
# Provider-neutral exception hierarchy (Phase 4C, Stage 1)
#
# These describe failure *categories* that any ThreatIntelProvider
# adapter can raise, independent of which concrete service (VirusTotal,
# and in future phases AbuseIPDB/OTX/etc.) produced them.
# ==========================================================


class ProviderConfigurationError(ThreatIntelError):
    """
    Raised when a provider is missing configuration it needs
    before it can attempt a lookup (e.g. no API key configured).
    """


class ProviderValidationError(ThreatIntelError):
    """
    Raised when an IOC value fails a provider's own input
    validation before any network call is attempted. This is a
    call-site problem (malformed IOC value), not a provider-side
    failure.
    """


class ProviderAuthError(ThreatIntelError):
    """
    Raised when a provider rejects the configured credentials
    (e.g. an invalid or unauthorized API key).
    """


class ProviderRateLimitError(ThreatIntelError):
    """
    Raised when a provider's rate limit has been exceeded.
    """


class ProviderConnectionError(ThreatIntelError):
    """
    Raised when a network connection to a provider cannot be
    established.
    """


class ProviderTimeoutError(ThreatIntelError):
    """
    Raised when a request to a provider times out.
    """


class ProviderResponseError(ThreatIntelError):
    """
    Raised when a provider returns an unexpected or malformed
    response.
    """


# ==========================================================
# VirusTotal-specific exceptions (pre-existing)
#
# Each now also inherits from the provider-neutral exception above
# that best describes the same failure category, per SS10 of the
# Phase 4C design doc. `VirusTotalError` remains every concrete
# exception's first base, so it remains the primary type for
# `isinstance` checks and is unaffected by this change.
# ==========================================================


class VirusTotalError(ThreatIntelError):
    """
    Base exception for VirusTotal-related errors.
    """


class MissingAPIKeyError(VirusTotalError, ProviderConfigurationError):
    """
    Raised when the VirusTotal API key is missing.
    """


class InvalidHashError(VirusTotalError, ProviderValidationError):
    """
    Raised when an invalid SHA-256 hash is provided.
    """


class InvalidIPError(VirusTotalError, ProviderValidationError):
    """
    Raised when an invalid IPv4 address is provided.
    """


class InvalidDomainError(VirusTotalError, ProviderValidationError):
    """
    Raised when an invalid domain name is provided.
    """


class InvalidURLError(VirusTotalError, ProviderValidationError):
    """
    Raised when an invalid URL is provided.
    """


class InvalidAPIKeyError(VirusTotalError, ProviderAuthError):
    """
    Raised when the VirusTotal API key is invalid or unauthorized.
    """


class RateLimitExceededError(VirusTotalError, ProviderRateLimitError):
    """
    Raised when the VirusTotal API rate limit is exceeded.
    """


class ThreatIntelConnectionError(VirusTotalError, ProviderConnectionError):
    """
    Raised when a network connection cannot be established.
    """


class ThreatIntelTimeoutError(VirusTotalError, ProviderTimeoutError):
    """
    Raised when a request times out.
    """


class UnexpectedAPIResponseError(VirusTotalError, ProviderResponseError):
    """
    Raised when the API returns an unexpected or malformed response.
    """