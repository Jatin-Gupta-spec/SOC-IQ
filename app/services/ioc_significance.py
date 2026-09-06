"""
IOC significance presentation helper for the SOC-IQ desktop application.

Maps an IOC category to a human-readable risk-significance label
(e.g. "High", "Medium") for display in the IOC detail experience.

This is presentation logic only. It reads
`RiskScoringEngine.IOC_WEIGHTS` as the single source of truth for
"how much does this IOC category matter" and does not duplicate,
override, or recalculate anything the scoring engine already
owns -- see PHASE2_PART2A scope: "Do NOT redesign or replace the
existing scoring algorithm."
"""

from __future__ import annotations

from app.scoring.engine import RiskScoringEngine

# Display titles for each IOC category key, shared by every
# workspace widget that needs to show a category as a human
# label rather than its raw dictionary key.
IOC_TYPE_TITLES: dict[str, str] = {
    "ipv4": "IPv4 Address",
    "domains": "Domain",
    "urls": "URL",
    "emails": "Email Address",
    "md5": "MD5 Hash",
    "sha1": "SHA1 Hash",
    "sha256": "SHA256 Hash",
    "cves": "CVE",
    "windows_file_paths": "Windows File Path",
    "windows_registry_keys": "Windows Registry Key",
}


def ioc_type_title(ioc_type: str) -> str:
    """
    Return the display title for an IOC category key, falling
    back to the raw key for any category this workspace doesn't
    otherwise know how to label.
    """

    return IOC_TYPE_TITLES.get(ioc_type, ioc_type)


def ioc_type_weight(ioc_type: str) -> int:
    """
    Return the scoring engine's weight for an IOC category.
    """

    return RiskScoringEngine.IOC_WEIGHTS.get(ioc_type, 0)


def ioc_type_significance(ioc_type: str) -> str:
    """
    Translate an IOC category's scoring weight into a coarse
    significance label for the analyst.

    Thresholds are presentation-only banding over the existing
    weight table (max weight in `IOC_WEIGHTS` is 8, for CVEs) and
    do not feed back into any score calculation.
    """

    weight = ioc_type_weight(ioc_type)

    if weight >= 6:
        return "High"

    if weight >= 3:
        return "Medium"

    if weight >= 1:
        return "Low"

    return "Informational"
