"""
Custom exceptions for the SOC-IQ risk scoring engine.
"""

from __future__ import annotations


class RiskScoringError(Exception):
    """
    Base exception for all
    risk scoring errors.
    """


class InvalidIOCDataError(RiskScoringError):
    """
    Raised when IOC data provided to the
    scoring engine is invalid.
    """


class InvalidThreatIntelDataError(RiskScoringError):
    """
    Raised when threat intelligence data
    is invalid or malformed.
    """


class InvalidRiskScoreError(RiskScoringError):
    """
    Raised when a calculated risk score
    falls outside the supported range.
    """