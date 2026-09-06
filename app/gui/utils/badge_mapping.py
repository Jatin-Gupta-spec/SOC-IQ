"""
Shared badge-type mapping helpers for the SOC-IQ desktop application.

Several widgets need to turn a domain string (a severity label, a
risk-significance label, or a threat-intelligence enrichment state)
into the semantic ``BadgeType`` that ``StatusBadge`` uses to pick its
color. Before this module existed that mapping was re-declared per
widget (see e.g. the ``_SEVERITY_BADGE_MAP`` pattern in
``live_security_events_widget.py``), which risked the same semantic
state drifting to different colors in different places.

This module is presentation-only: it does not calculate severity or
significance, it only maps an existing label to a badge color.
"""

from __future__ import annotations

from app.services.ioc_detail_context import (
    TI_STATE_ENRICHED,
    TI_STATE_INCOMPLETE_CHECK,
    TI_STATE_NO_API_KEY,
    TI_STATE_NOT_ENRICHED,
    TI_STATE_PROVIDER_ERROR,
    TI_STATE_UNSUPPORTED_TYPE,
)
from app.services.models import BadgeType

__all__ = [
    "severity_to_badge_type",
    "ti_state_to_badge_type",
]

# Severity / risk-significance labels are used inconsistently in
# casing across the codebase ("HIGH" for investigation.severity,
# "High" for ioc_type_significance()), so this mapping is matched
# case-insensitively.
_SEVERITY_BADGE_MAP: dict[str, BadgeType] = {
    "critical": BadgeType.CRITICAL,
    "high": BadgeType.HIGH,
    "medium": BadgeType.MEDIUM,
    "low": BadgeType.LOW,
    "info": BadgeType.INFO,
}

_TI_STATE_BADGE_MAP: dict[str, BadgeType] = {
    TI_STATE_ENRICHED: BadgeType.SUCCESS,
    TI_STATE_NOT_ENRICHED: BadgeType.DEFAULT,
    TI_STATE_NO_API_KEY: BadgeType.WARNING,
    TI_STATE_PROVIDER_ERROR: BadgeType.ERROR,
    TI_STATE_INCOMPLETE_CHECK: BadgeType.WARNING,
    TI_STATE_UNSUPPORTED_TYPE: BadgeType.DEFAULT,
}


def severity_to_badge_type(text: str) -> BadgeType:
    """
    Map a severity or risk-significance label (e.g. "HIGH", "High",
    "Informational", "Waiting...") to a semantic ``BadgeType``.

    Unrecognized labels (placeholder text like "Waiting...",
    "Informational") fall back to ``BadgeType.DEFAULT`` rather than
    raising, since badges are frequently shown before a real value
    is known yet.
    """

    return _SEVERITY_BADGE_MAP.get(text.strip().lower(), BadgeType.DEFAULT)


def ti_state_to_badge_type(state: str) -> BadgeType:
    """
    Map one of the ``TI_STATE_*`` threat-intelligence enrichment
    state constants to a semantic ``BadgeType``.
    """

    return _TI_STATE_BADGE_MAP.get(state, BadgeType.DEFAULT)
