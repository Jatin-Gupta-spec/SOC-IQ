"""
Evidence correlation service for SOC-IQ.

Phase 3B: helps an analyst understand relationships between
evidence already present inside an investigation. This module is
deliberately plain Python (no Qt dependency) so it can be unit
tested directly and reused outside the GUI layer -- matching the
existing pattern in app/services/ioc_detail_context.py.

Scope (see PHASE3_PART3B):
    - Correlation is deterministic: the same investigation data
      always produces the same `CorrelationReport`, in the same
      order. No randomness, no network calls, no LLM calls, no
      hidden heuristics, no time-dependent behavior.
    - Correlation is derived entirely from data already present on
      `Investigation` (extracted IOCs + existing threat-intelligence
      enrichment). No new provider, no new database, no external
      lookups.
    - Only relationships the existing data can actually justify are
      produced -- see each `_correlate_*` method's docstring for the
      specific justification.

Explicitly out of scope for this module: graph databases, machine
learning / LLM-based correlation, attack-path prediction, and any
form of autonomous reasoning. This service performs correlation and
presentation support only.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.database.models import Investigation
from app.services.correlation_models import (
    RELATIONSHIP_DOMAIN_URL_HOST,
    RELATIONSHIP_DUPLICATE_IOC,
    RELATIONSHIP_THREAT_INTEL_LINK,
    CorrelatedEvidence,
    CorrelationReport,
    CorrelationResult,
    CorrelationSummary,
)

# ==========================================================
# Normalization
# ==========================================================


def _normalize_default(value: str) -> str:
    """
    Fallback normalization: trim surrounding whitespace and
    lowercase. Used for any IOC category without a more specific
    rule below.
    """

    return value.strip().lower()


def _normalize_domain(value: str) -> str:
    """
    Normalize a domain for comparison: lowercase, trimmed, and
    without a trailing dot (a trailing "." denotes the DNS root and
    is representationally equivalent to the same domain without it).
    """

    normalized = value.strip().lower()

    if normalized.endswith("."):
        normalized = normalized[:-1]

    return normalized


def _normalize_url(value: str) -> str:
    """
    Normalize a URL for comparison: lowercase scheme and host only.
    The path, query, and fragment are left exactly as extracted --
    they are frequently case-sensitive in practice (e.g. a
    case-sensitive web server path), so lowercasing them could
    create a false match between two genuinely different URLs.
    """

    stripped = value.strip()

    parsed = urlparse(stripped)

    if not parsed.scheme or not parsed.netloc:
        # Not a parseable absolute URL -- fall back to a
        # whitespace/lowercase-only normalization rather than
        # raising, so a malformed extracted value can still be
        # compared (and simply fail to match anything) instead of
        # breaking correlation for the whole investigation.
        return stripped.lower()

    rest = stripped[len(parsed.scheme) + len("://") + len(parsed.netloc) :]

    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{rest}"


def _url_host(value: str) -> str | None:
    """
    Extract the lowercased host portion of a URL, or `None` if the
    value is not a parseable absolute URL.
    """

    parsed = urlparse(value.strip())

    if not parsed.netloc:
        return None

    # Strip a userinfo/port component if present so
    # "user@host:8080" compares as "host".
    host = parsed.netloc.split("@")[-1].split(":")[0]

    return host.lower() or None


# Comparison-only normalizers, keyed by the same IOC category keys
# used throughout the codebase (see app/extractor.py IOC_PATTERNS
# and app/services/ioc_significance.py IOC_TYPE_TITLES). Hashes
# (md5/sha1/sha256) and Windows paths/registry keys are
# case-insensitive by construction, so the default lowercasing rule
# already normalizes them correctly.
_NORMALIZERS: dict[str, Any] = {
    "domains": _normalize_domain,
    "urls": _normalize_url,
}


def normalize_ioc_value(ioc_type: str, value: str) -> str:
    """
    Return the comparison-only normalized form of an IOC value.

    This is used exclusively for correlation matching. It never
    replaces or mutates the original stored IOC value (see
    PHASE3_PART3B section 9: "Do NOT modify the original stored
    IOC").
    """

    normalizer = _NORMALIZERS.get(ioc_type, _normalize_default)

    return normalizer(value)


# ==========================================================
# Correlation Service
# ==========================================================


class CorrelationService:
    """
    Derives deterministic relationships between evidence already
    present in a single investigation.

    The GUI must consume this service rather than calculating
    correlations itself (see PHASE3_PART3B section 6/7).
    """

    def correlate(self, investigation: Investigation) -> CorrelationReport:
        """
        Build the full correlation report for one investigation.

        Args:
            investigation:
                The investigation to correlate. Its `iocs` and
                `threat_intelligence` fields are read as-is; nothing
                is fetched or mutated.

        Returns:
            A `CorrelationReport` with deterministically ordered
            results, safe to display even when empty.
        """

        iocs = investigation.iocs or {}

        results: list[CorrelationResult] = []

        results.extend(self._correlate_duplicates(iocs))
        results.extend(self._correlate_domain_url_hosts(iocs))
        results.extend(
            self._correlate_threat_intel_links(
                iocs,
                investigation.threat_intelligence or {},
            )
        )

        # Deterministic ordering: relationship priority first (see
        # RELATIONSHIP_PRIORITY), then a stable tie-break on the
        # evidence values themselves so re-running correlation on
        # identical input always yields an identical result list
        # (PHASE3_PART3B section 23: "Determinism" / "Ordering").
        results.sort(
            key=lambda result: (
                result.priority,
                result.primary.ioc_type,
                result.primary.value,
                result.related.ioc_type,
                result.related.value,
            )
        )

        total_evidence_count = sum(
            len(values) for values in iocs.values()
        )

        # Only count evidence that is actually one of the
        # investigation's extracted IOCs against
        # `correlated_evidence_count`. A threat-intelligence link's
        # "related" side (see `_correlate_threat_intel_links`) is a
        # synthetic reference to the existing enrichment record, not
        # a second piece of extracted evidence -- counting it here
        # would let `correlated_evidence_count` exceed
        # `total_evidence_count`, which is derived from `iocs` alone.
        correlated_values: set[tuple[str, str]] = set()

        for result in results:
            for evidence in (result.primary, result.related):
                if evidence.value in iocs.get(evidence.ioc_type, []):
                    correlated_values.add((evidence.ioc_type, evidence.value))

        summary = CorrelationSummary(
            total_evidence_count=total_evidence_count,
            correlated_evidence_count=len(correlated_values),
            relationship_count=len(results),
            shared_investigation_evidence_count=total_evidence_count,
        )

        return CorrelationReport(results=results, summary=summary)

    # ------------------------------------------------------------
    # Priority 1: exact normalized IOC identity
    # ------------------------------------------------------------

    def _correlate_duplicates(
        self,
        iocs: dict[str, list[str]],
    ) -> list[CorrelationResult]:
        """
        Find raw IOC values within the same category that resolve
        to the same normalized identity (e.g. differing only by
        case), and report them as duplicate occurrences of one
        logical IOC.

        `app.extractor.extract_iocs()` already de-duplicates exact
        raw string matches per category, so anything found here is
        specifically a representation mismatch (case, trailing dot,
        ...), not a re-detection of the extractor's own
        deduplication.
        """

        results: list[CorrelationResult] = []

        for ioc_type, values in sorted(iocs.items()):

            groups: dict[str, list[str]] = {}

            for raw_value in values:
                normalized = normalize_ioc_value(ioc_type, raw_value)
                groups.setdefault(normalized, []).append(raw_value)

            for normalized, raw_values in sorted(groups.items()):

                if len(raw_values) < 2:
                    continue

                occurrence_count = len(raw_values)

                # Pair every later occurrence with the first
                # (alphabetically earliest) raw form, rather than
                # every occurrence with every other occurrence.
                # This keeps the result count linear in the number
                # of duplicate occurrences instead of quadratic,
                # while still surfacing every duplicate value.
                sorted_raw_values = sorted(raw_values)
                canonical = sorted_raw_values[0]

                for other_value in sorted_raw_values[1:]:

                    results.append(
                        CorrelationResult(
                            relationship_type=RELATIONSHIP_DUPLICATE_IOC,
                            primary=CorrelatedEvidence(
                                ioc_type=ioc_type,
                                value=canonical,
                                normalized_value=normalized,
                            ),
                            related=CorrelatedEvidence(
                                ioc_type=ioc_type,
                                value=other_value,
                                normalized_value=normalized,
                            ),
                            reason=(
                                f"Same {ioc_type} value appears "
                                f"{occurrence_count} times in this "
                                "investigation under different "
                                "representations."
                            ),
                        )
                    )

        return results

    # ------------------------------------------------------------
    # Priority 2: cross-category association the data supports
    # ------------------------------------------------------------

    def _correlate_domain_url_hosts(
        self,
        iocs: dict[str, list[str]],
    ) -> list[CorrelationResult]:
        """
        Link an extracted domain to an extracted URL whose host is
        that domain (exact match) or a subdomain of it.

        This is the "Domain <-> URL" example given in PHASE3_PART3B
        section 8, and is directly supported by data already on the
        investigation -- no external lookup is performed.
        """

        results: list[CorrelationResult] = []

        domains = sorted(set(iocs.get("domains", [])))
        urls = sorted(set(iocs.get("urls", [])))

        if not domains or not urls:
            return results

        for domain in domains:

            normalized_domain = _normalize_domain(domain)

            for url in urls:

                host = _url_host(url)

                if host is None:
                    continue

                is_exact = host == normalized_domain
                is_subdomain = host.endswith(f".{normalized_domain}")

                if not (is_exact or is_subdomain):
                    continue

                reason = (
                    f"URL host matches extracted domain {domain!r} exactly."
                    if is_exact
                    else (
                        f"URL host is a subdomain of extracted "
                        f"domain {domain!r}."
                    )
                )

                results.append(
                    CorrelationResult(
                        relationship_type=RELATIONSHIP_DOMAIN_URL_HOST,
                        primary=CorrelatedEvidence(
                            ioc_type="domains",
                            value=domain,
                            normalized_value=normalized_domain,
                        ),
                        related=CorrelatedEvidence(
                            ioc_type="urls",
                            value=url,
                            normalized_value=_normalize_url(url),
                        ),
                        reason=reason,
                    )
                )

        return results

    # ------------------------------------------------------------
    # Priority 4: existing threat-intelligence association
    # ------------------------------------------------------------

    # Maps each enrichable IOC category to the TI category key it is
    # stored under in `investigation.threat_intelligence`, and the
    # field name that holds the indicator value within each record.
    # This is the same mapping `InvestigationWorkspacePage` already
    # uses to build `_threat_intel_by_value` -- kept in one place
    # here so all four categories are correlated identically.
    _TI_LINK_CATEGORIES: tuple[tuple[str, str, str], ...] = (
        ("sha256", "hashes", "sha256"),
        ("ipv4", "ips", "ip"),
        ("domains", "domains", "domain"),
        ("urls", "urls", "url"),
    )

    def _correlate_threat_intel_links(
        self,
        iocs: dict[str, list[str]],
        threat_intelligence: dict[str, Any],
    ) -> list[CorrelationResult]:
        """
        Link each enrichable IOC (SHA256, IPv4, domain, URL) to its
        own existing enrichment record, if one is present in
        `investigation.threat_intelligence`.

        All four enrichable categories are handled identically (see
        `_TI_LINK_CATEGORIES`); this method reads that existing data
        as-is and does not call VirusTotal or fabricate a verdict.
        """

        results: list[CorrelationResult] = []

        for ioc_type, ti_category, value_field in self._TI_LINK_CATEGORIES:

            results.extend(
                self._correlate_threat_intel_links_for_category(
                    iocs,
                    threat_intelligence,
                    ioc_type,
                    ti_category,
                    value_field,
                )
            )

        return results

    def _correlate_threat_intel_links_for_category(
        self,
        iocs: dict[str, list[str]],
        threat_intelligence: dict[str, Any],
        ioc_type: str,
        ti_category: str,
        value_field: str,
    ) -> list[CorrelationResult]:
        """
        Link IOCs of a single category to their existing enrichment
        records. Shared helper behind `_correlate_threat_intel_links`
        so each of the four enrichable categories (SHA256, IPv4,
        domain, URL) gets identical treatment without duplicating
        four near-identical blocks.
        """

        results: list[CorrelationResult] = []

        values = sorted(set(iocs.get(ioc_type, [])))

        if not values:
            return results

        records_by_value: dict[str, dict[str, Any]] = {
            record[value_field]: record
            for record in threat_intelligence.get(ti_category, [])
            if record.get(value_field)
        }

        for value in values:

            record = records_by_value.get(value)

            if record is None:
                continue

            verdict = record.get("verdict", "Unknown")
            detection_ratio = record.get("detection_ratio", "N/A")

            results.append(
                CorrelationResult(
                    relationship_type=RELATIONSHIP_THREAT_INTEL_LINK,
                    primary=CorrelatedEvidence(
                        ioc_type=ioc_type,
                        value=value,
                        normalized_value=normalize_ioc_value(ioc_type, value),
                    ),
                    related=CorrelatedEvidence(
                        ioc_type="threat_intelligence",
                        value=value,
                        normalized_value=normalize_ioc_value(ioc_type, value),
                    ),
                    reason=(
                        f"VirusTotal verdict for this indicator: {verdict} "
                        f"({detection_ratio} detections)."
                    ),
                )
            )

        return results
