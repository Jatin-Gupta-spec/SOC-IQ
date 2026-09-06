"""
Risk explanation service for SOC-IQ investigations (Phase 3C-1).

Answers "why does this investigation have this risk/severity?" by
deriving explanation context from an investigation's EXISTING risk
assessment, evidence, threat intelligence, and correlations. This
module does not calculate risk -- `RiskScoringEngine` remains the
sole, authoritative source of an investigation's score and
severity (see PHASE3C-1 section 3: "DO NOT CHANGE THE EXISTING RISK
ENGINE").

Design, matching `CorrelationService` (app/services/
correlation_service.py) and `app/services/ioc_detail_context.py`:

  * Framework-independent: no PySide6 import, plain Python only.
  * Read-only: never mutates the `Investigation`, never calls a
    threat-intelligence provider, never writes to the database.
  * Deterministic: identical input always produces an identical
    `RiskExplanation`.
  * Honest: a claim is only stated as a specific numeric
    contribution when the existing scoring engine's own public
    data explicitly supports it (see PHASE3C-1 section 8); anything
    else is described qualitatively rather than invented.

`reasons` on the scoring engine's `RiskScore` output
(app/scoring/models.py) is never persisted onto the database
`Investigation` model (`app/database/models.py` has no `reasons`
field, and it uses `slots=True`, so the attribute cannot exist on a
loaded investigation). This service therefore does not depend on
it -- `_engine_reasons()` below only picks it up via `getattr()` for
the rare in-memory caller that happens to still be holding one,
mirroring the same defensive `hasattr()` pattern already used in
`app/display.py`.
"""

from __future__ import annotations

from typing import Any

from app.database.models import Investigation
from app.services.ioc_detail_context import (
    build_investigation_threat_intel_overview,
)
from app.services.ioc_significance import (
    ioc_type_significance,
    ioc_type_title,
    ioc_type_weight,
)
from app.logger import logger
from app.services.correlation_models import CorrelationReport
from app.services.risk_explanation_models import (
    IocCategoryContribution,
    RiskExplanation,
)


class RiskExplanationService:
    """
    Builds a `RiskExplanation` for one investigation, from data the
    project already computed and persisted:

    Investigation
        -> existing risk score / severity / confidence
        -> existing IOC evidence (`Investigation.iocs`)
        -> existing threat intelligence
           (`Investigation.threat_intelligence`)
        -> existing Phase 3B correlations (`CorrelationReport`,
           optional -- the caller runs `CorrelationService`)
        -> RiskExplanation
    """

    def explain(
        self,
        investigation: Investigation,
        correlation_report: CorrelationReport | None = None,
        api_key_configured: bool = False,
    ) -> RiskExplanation:
        """
        Build the explanation for one investigation.

        Args:
            investigation:
                The investigation to explain. Required -- an
                explanation with no subject cannot be built safely,
                so a `None` investigation raises rather than
                producing a fabricated/empty result the caller
                might mistake for a real explanation.
            correlation_report:
                Optional Phase 3B correlation result for this same
                investigation (see `CorrelationService.correlate()`
                ). Passed in rather than computed here, so this
                service never has to import `CorrelationService`
                for a concern it does not own. `None` means
                correlation was not evaluated for this explanation
                -- distinct from a report that was evaluated and
                found zero relationships.
            api_key_configured:
                Whether a VirusTotal API key is currently
                configured, forwarded to
                `build_investigation_threat_intel_overview()`
                unchanged (see that function's docstring). Defaults
                to False so a caller that omits it gets the
                honest "nothing could have been checked without a
                key" reading rather than an assumed-available one.

        Returns:
            A `RiskExplanation`. Safe to build even for an
            investigation with no IOCs, no threat intelligence, and
            no correlation data -- every section degrades to an
            honest "nothing here" statement rather than raising.
        """

        if investigation is None:
            raise ValueError(
                "RiskExplanationService.explain() requires an "
                "Investigation; received None."
            )

        logger.info(
            "Building risk explanation for investigation %r.",
            investigation.investigation_id,
        )

        warnings: list[str] = []

        ioc_categories, ioc_breakdown_verified = (
            self._build_ioc_categories(investigation)
        )

        if not ioc_breakdown_verified and investigation.iocs:
            warnings.append(
                "The per-category IOC point breakdown did not sum "
                "to this investigation's recorded IOC score, so "
                "individual category point values are omitted from "
                "the narrative. The recorded IOC score itself is "
                "still the existing engine's authoritative figure."
            )

        ti_overview = build_investigation_threat_intel_overview(
            investigation,
            api_key_configured,
        )

        malicious_count, suspicious_count = (
            self._count_threat_intel_verdicts(investigation)
        )

        if correlation_report is not None:
            correlation_evaluated = True
            correlation_relationship_count = len(
                correlation_report.results
            )
            correlation_summary = self._correlation_summary_text(
                correlation_report
            )
        else:
            correlation_evaluated = False
            correlation_relationship_count = 0
            correlation_summary = (
                "Correlation data was not evaluated for this "
                "explanation."
            )

        engine_reasons = self._engine_reasons(investigation)

        narrative = self._build_narrative(
            investigation=investigation,
            ioc_categories=ioc_categories,
            ioc_breakdown_verified=ioc_breakdown_verified,
            ti_overview=ti_overview,
            malicious_count=malicious_count,
            suspicious_count=suspicious_count,
            correlation_evaluated=correlation_evaluated,
            correlation_relationship_count=(
                correlation_relationship_count
            ),
            correlation_summary=correlation_summary,
        )

        if ti_overview["state"] not in (
            "enriched",
            "not_enriched",
        ):
            warnings.append(
                "Threat-intelligence coverage for this "
                "investigation is incomplete -- absence of "
                "malicious findings does not mean the unchecked "
                "indicators are clean."
            )

        explanation = RiskExplanation(
            investigation_id=investigation.investigation_id,
            report_name=investigation.report_name,
            score=investigation.risk_score,
            severity=investigation.severity,
            confidence=investigation.confidence,
            ioc_score=investigation.ioc_score,
            threat_intel_score=investigation.threat_intel_score,
            cve_score=investigation.cve_score,
            ioc_categories=ioc_categories,
            ioc_breakdown_verified=ioc_breakdown_verified,
            threat_intel_state=ti_overview["state"],
            threat_intel_message=ti_overview["message"],
            threat_intel_short_label=ti_overview["short_label"],
            threat_intel_requested=ti_overview["requested"],
            threat_intel_succeeded=ti_overview["succeeded"],
            threat_intel_malicious_hash_count=malicious_count,
            threat_intel_suspicious_hash_count=suspicious_count,
            correlation_evaluated=correlation_evaluated,
            correlation_relationship_count=(
                correlation_relationship_count
            ),
            correlation_summary=correlation_summary,
            engine_reasons=engine_reasons,
            narrative=narrative,
            warnings=warnings,
        )

        logger.info(
            "Risk explanation built for investigation %r "
            "(%d IOC categories, correlation_evaluated=%s).",
            investigation.investigation_id,
            len(ioc_categories),
            correlation_evaluated,
        )

        return explanation

    # ------------------------------------------------------------
    # IOC evidence
    # ------------------------------------------------------------

    def _build_ioc_categories(
        self,
        investigation: Investigation,
    ) -> tuple[list[IocCategoryContribution], bool]:
        """
        Build the per-category IOC breakdown and verify it against
        the investigation's existing, persisted `ioc_score`.

        Uses `ioc_type_weight()` (`app/gui/utils/
        ioc_significance.py`), which reads
        `RiskScoringEngine.IOC_WEIGHTS` -- the exact table
        `RiskScoringEngine._calculate_ioc_score()` sums over. This
        is a transparent decomposition of an already-computed
        number using the engine's own public weights, not a new
        calculation (see PHASE3C-1 section 3).

        Returns:
            A tuple of `(categories, verified)`. `verified` is True
            only when every category's `count * weight` sums
            exactly to `investigation.ioc_score` -- if the engine's
            weighting ever changes in a way this decomposition does
            not track, this catches the drift instead of silently
            presenting a wrong breakdown.
        """

        iocs = investigation.iocs or {}

        categories: list[IocCategoryContribution] = []

        for ioc_type in sorted(iocs.keys()):

            values = iocs.get(ioc_type) or []

            count = len(values)

            if count == 0:
                continue

            weight = ioc_type_weight(ioc_type)

            categories.append(
                IocCategoryContribution(
                    ioc_type=ioc_type,
                    ioc_type_title=ioc_type_title(ioc_type),
                    count=count,
                    weight=weight,
                    significance=ioc_type_significance(ioc_type),
                    points=count * weight,
                )
            )

        # Deterministic ordering: highest point contribution first,
        # tie-broken by category key, so identical input always
        # yields an identical list (matches
        # `CorrelationService.correlate()`'s ordering guarantee).
        categories.sort(
            key=lambda category: (
                -category.points,
                category.ioc_type,
            )
        )

        verified = (
            sum(category.points for category in categories)
            == investigation.ioc_score
        )

        return categories, verified

    # ------------------------------------------------------------
    # Threat intelligence
    # ------------------------------------------------------------

    # The four enrichable TI categories, counted identically. Kept
    # alongside the other category tables in this codebase (e.g.
    # `CorrelationService._TI_LINK_CATEGORIES`) so a malicious
    # IP/domain/URL verdict is counted the same way a malicious
    # SHA256 verdict already was.
    _TI_VERDICT_CATEGORIES: tuple[str, ...] = (
        "hashes",
        "ips",
        "domains",
        "urls",
    )

    def _count_threat_intel_verdicts(
        self,
        investigation: Investigation,
    ) -> tuple[int, int]:
        """
        Count existing "Malicious" / "Suspicious" verdicts already
        recorded on this investigation's threat-intelligence
        enrichment (`ThreatIntelService`'s own `verdict` field --
        see app/threat_intel/service.py). Does not call any
        provider and does not reinterpret raw detection counts into
        a new verdict.

        Counts across all four enrichable categories (hashes, ips,
        domains, urls) so a malicious IP/domain/URL is reflected in
        the analyst-facing explanation just as a malicious SHA256
        already was.
        """

        threat_intelligence = (
            investigation.threat_intelligence or {}
        )

        records: list[dict[str, Any]] = []

        for category in self._TI_VERDICT_CATEGORIES:
            records.extend(
                threat_intelligence.get(category, []) or []
            )

        malicious_count = sum(
            1
            for record in records
            if record.get("verdict") == "Malicious"
        )

        suspicious_count = sum(
            1
            for record in records
            if record.get("verdict") == "Suspicious"
        )

        return malicious_count, suspicious_count

    # ------------------------------------------------------------
    # Correlation
    # ------------------------------------------------------------

    def _correlation_summary_text(
        self,
        correlation_report: CorrelationReport,
    ) -> str:
        """
        Describe the existing Phase 3B correlation result as
        context only -- never converted into additional risk (see
        PHASE3C-1 section 10).
        """

        summary = correlation_report.summary

        if summary.relationship_count == 0:
            return (
                "No supported deterministic relationships were "
                "identified among this investigation's evidence."
            )

        return (
            f"{summary.relationship_count} relationship(s) were "
            f"identified across {summary.correlated_evidence_count} "
            "of this investigation's evidence item(s). Related "
            "evidence was identified; this is contextual and is "
            "not an additional contribution to the risk score."
        )

    # ------------------------------------------------------------
    # Engine reasons (rarely present -- see module docstring)
    # ------------------------------------------------------------

    def _engine_reasons(
        self,
        investigation: Investigation,
    ) -> list[str]:
        """
        Return `reasons` if the caller's `Investigation` instance
        happens to carry them, else an empty list. See module
        docstring: this is normally empty for any investigation
        loaded from the database.
        """

        reasons = getattr(investigation, "reasons", None)

        if not reasons:
            return []

        return list(reasons)

    # ------------------------------------------------------------
    # Narrative
    # ------------------------------------------------------------

    def _build_narrative(
        self,
        *,
        investigation: Investigation,
        ioc_categories: list[IocCategoryContribution],
        ioc_breakdown_verified: bool,
        ti_overview: dict[str, Any],
        malicious_count: int,
        suspicious_count: int,
        correlation_evaluated: bool,
        correlation_relationship_count: int,
        correlation_summary: str,
    ) -> list[str]:
        """
        Build human-readable explanation sentences, each grounded
        in already-computed data.

        Per-category IOC point values are only ever named in the
        narrative when `ioc_breakdown_verified` is True; otherwise
        contributing categories are described by significance only
        ("High-weight IOC category contributes to the existing risk
        assessment"), matching PHASE3C-1 section 8's example of a
        supported vs. unsupported claim.
        """

        sentences: list[str] = [
            f"This investigation is rated {investigation.severity} "
            f"with a risk score of {investigation.risk_score}/100 "
            f"(confidence {investigation.confidence:.2f})."
        ]

        if ioc_categories:

            category_names = ", ".join(
                category.ioc_type_title
                for category in ioc_categories
            )

            if ioc_breakdown_verified:

                top = ioc_categories[0]

                sentences.append(
                    f"{investigation.ioc_score} of the total score "
                    f"come from extracted IOC evidence across "
                    f"{len(ioc_categories)} categor"
                    f"{'y' if len(ioc_categories) == 1 else 'ies'} "
                    f"({category_names}). The largest single "
                    f"contributor is {top.ioc_type_title} "
                    f"({top.significance.lower()}-significance, "
                    f"{top.count} indicator"
                    f"{'s' if top.count != 1 else ''})."
                )

            else:

                sentences.append(
                    f"{investigation.ioc_score} of the total score "
                    "come from extracted IOC evidence across "
                    f"{len(ioc_categories)} categor"
                    f"{'y' if len(ioc_categories) == 1 else 'ies'} "
                    f"({category_names}); high-weight categories in "
                    "this evidence contribute to the existing risk "
                    "assessment."
                )

        else:

            sentences.append(
                "No IOC evidence was extracted for this "
                "investigation, so IOC evidence contributes "
                "nothing to the total score."
            )

        if investigation.cve_score:

            cve_count = len(
                (investigation.iocs or {}).get("cves", [])
            )

            sentences.append(
                f"{investigation.cve_score} additional point(s) "
                f"come from {cve_count} discovered CVE identifier"
                f"{'s' if cve_count != 1 else ''}, which the "
                "existing engine scores separately from the "
                "general IOC weighting above."
            )

        if investigation.threat_intel_score:

            verdict_bits = []

            if malicious_count:
                verdict_bits.append(
                    f"{malicious_count} indicator(s) flagged Malicious"
                )

            if suspicious_count:
                verdict_bits.append(
                    f"{suspicious_count} indicator(s) flagged Suspicious"
                )

            verdict_text = (
                f" ({', '.join(verdict_bits)})"
                if verdict_bits
                else ""
            )

            sentences.append(
                f"{investigation.threat_intel_score} additional "
                "point(s) come from threat-intelligence "
                f"enrichment{verdict_text}."
            )

        sentences.append(ti_overview["message"])

        if correlation_evaluated:
            sentences.append(correlation_summary)

        return sentences
