"""
Risk scoring engine for SOC-IQ investigations.
"""
 
from __future__ import annotations
 
from typing import Any
 
from app.logger import logger
from app.scoring.models import RiskScore
 
 
class RiskScoringEngine:
    """
    Calculates a weighted risk score for
    SOC-IQ investigations.
    """
 
    # ----------------------------------
    # Score Limits
    # ----------------------------------
 
    MAX_SCORE = 100
 
    # ----------------------------------
    # IOC Weights
    # ----------------------------------
 
    IOC_WEIGHTS: dict[str, int] = {
    "ipv4": 1,
    "domains": 2,
    "urls": 3,
    "emails": 1,
    "md5": 4,
    "sha1": 5,
    "sha256": 6,
    "cves": 8,
    "windows_file_paths": 2,
    "windows_registry_keys": 3,
}
 
    # ----------------------------------
    # Severity Thresholds
    # ----------------------------------
 
    LOW_THRESHOLD = 20
    MEDIUM_THRESHOLD = 40
    HIGH_THRESHOLD = 70
 
    def __init__(self) -> None:
        """
        Initialize the scoring engine.
        """
 
        logger.info(
            "Risk scoring engine initialized."
        )
 
    def calculate(
        self,
        iocs: dict[str, list[str]],
        threat_intelligence: dict[str, Any],
    ) -> RiskScore:
        """
        Calculate the investigation
        risk score.
        """
 
        logger.info(
            "Starting risk calculation."
        )
 
        ioc_score = self._calculate_ioc_score(
            iocs,
        )
 
        threat_score = (
            self._calculate_threat_intel_score(
                threat_intelligence,
            )
        )
 
        cve_score = self._calculate_cve_score(
            iocs,
        )
 
        total_score = (
            ioc_score
            + threat_score
            + cve_score
        )
 
        total_score = self.normalize_score(
            total_score,
        )
 
        severity = self._determine_severity(
            total_score,
        )
 
        confidence = self._calculate_confidence(
            iocs,
            threat_intelligence,
        )
 
        reasons: list[str] = []
 
        if ioc_score:
            reasons.append(
                f"IOC score: {ioc_score}"
            )
 
        if threat_score:
            reasons.append(
                f"Threat Intelligence score: "
                f"{threat_score}"
            )

        # `threat_score` above is purely a count of *confirmed*
        # malicious/suspicious hits -- when threat intelligence
        # could not be fully checked (unavailable, partial, rate
        # limited, invalid key, or any status this engine doesn't
        # recognize) that count is legitimately 0 not because
        # nothing was found, but because nothing conclusive could be
        # checked. Nothing above this line reflects that distinction
        # -- a score with zero threat-intel contribution looks
        # identical whether TI ran clean or never ran at all. This
        # makes the gap explicit in `reasons` (which is persisted on
        # the `Investigation`) without inventing a risk contribution
        # for detections that were never actually confirmed.
        ti_status = (
            threat_intelligence.get("status")
            if threat_intelligence
            else None
        )

        if ti_status not in (
            "ok",
            "no_indicators",
        ):
            reasons.append(
                "Threat Intelligence check incomplete "
                f"(status: {ti_status!r}) -- this score does "
                "NOT confirm a clean result, only that nothing "
                "conclusive was found among what could be "
                "checked."
            )
 
        if cve_score:
            reasons.append(
                f"CVE score: {cve_score}"
            )
 
        logger.info(
            "Risk calculation completed."
        )
 
        return RiskScore(
            score=total_score,
            severity=severity,
            confidence=confidence,
            ioc_score=ioc_score,
            threat_intel_score=threat_score,
            cve_score=cve_score,
            reasons=reasons,
        )
 
    def _calculate_ioc_score(
        self,
        iocs: dict[str, list[str]],
    ) -> int:
        """
        Calculate the IOC contribution to the
        overall risk score.
        """
 
        score = 0
 
        for ioc_type, values in iocs.items():
 
            weight = self.IOC_WEIGHTS.get(
                ioc_type,
                0,
            )
 
            score += (
                len(values)
                * weight
            )
 
        logger.debug(
            "IOC score calculated: %d",
            score,
        )
 
        return score
 
    def _calculate_threat_intel_score(
        self,
        threat_intelligence: dict[str, Any],
    ) -> int:
        """
        Calculate the threat intelligence
        contribution.
        """
 
        score = 0
 
        hashes = threat_intelligence.get(
            "hashes",
            [],
        )
 
        for result in hashes:
 
            malicious = int(
                result.get(
                    "malicious",
                    0,
                )
            )
 
            suspicious = int(
                result.get(
                    "suspicious",
                    0,
                )
            )
 
            reputation = result.get(
                "reputation",
            )
 
            score += malicious * 5
            score += suspicious * 2
 
            if (
                reputation is not None
                and reputation < 0
            ):
                score += abs(
                    reputation
                )
 
        logger.debug(
            "Threat Intelligence score: %d",
            score,
        )
 
        return score
 
    def _calculate_cve_score(
        self,
        iocs: dict[str, list[str]],
    ) -> int:
        """
        Calculate additional score for
        discovered CVEs.
        """
 
        cves = iocs.get(
            "cves",
            [],
        )
 
        score = (
            len(cves)
            * 10
        )
 
        logger.debug(
            "CVE score: %d",
            score,
        )
 
        return score
 
    def _calculate_confidence(
        self,
        iocs: dict[str, list[str]],
        threat_intelligence: dict[str, Any] | None = None,
    ) -> float:
        """
        Calculate confidence based on
        the amount of collected evidence.

        Confidence is reduced when threat intelligence was not
        fully completed (unavailable, partial, or any status this
        engine doesn't recognize as a finished check). IOC volume
        alone is not "evidence" of risk absence if the one signal
        capable of confirming maliciousness -- threat-intel lookup
        -- never finished running; halving confidence keeps a
        degraded check from reading as equally trustworthy as a
        completed one, without altering the underlying score.
        """
 
        total_iocs = sum(
            len(values)
            for values in iocs.values()
        )
 
        confidence = min(
            total_iocs / 40.0,
            1.0,
        )

        ti_status = (
            threat_intelligence.get("status")
            if threat_intelligence
            else None
        )

        if ti_status not in (
            "ok",
            "no_indicators",
        ):

            confidence *= 0.5
 
        logger.debug(
            "Confidence calculated: %.2f",
            confidence,
        )
 
        return round(
            confidence,
            2,
        )
 
    def _determine_severity(
        self,
        score: int,
    ) -> str:
        """
        Determine the severity level from
        the calculated score.
        """
 
        if score <= self.LOW_THRESHOLD:
            severity = "LOW"
 
        elif score <= self.MEDIUM_THRESHOLD:
            severity = "MEDIUM"
 
        elif score <= self.HIGH_THRESHOLD:
            severity = "HIGH"
 
        else:
            severity = "CRITICAL"
 
        logger.debug(
            "Severity determined: %s",
            severity,
        )
 
        return severity
 
    def normalize_score(
        self,
        score: int,
    ) -> int:
        """
        Normalize the score to the valid
        range of 0 to MAX_SCORE.
        """
 
        normalized = max(
            0,
            min(
                score,
                self.MAX_SCORE,
            ),
        )
 
        logger.debug(
            "Normalized score: %d",
            normalized,
        )
 
        return normalized
 
    def summarize(
        self,
        risk_score: RiskScore,
    ) -> dict[str, Any]:
        """
        Produce a summary dictionary for
        reporting and persistence.
        """
 
        summary = {
            "score": risk_score.score,
            "severity": risk_score.severity,
            "confidence": risk_score.confidence,
            "ioc_score": risk_score.ioc_score,
            "threat_intel_score": (
                risk_score.threat_intel_score
            ),
            "cve_score": risk_score.cve_score,
            "reasons": list(
                risk_score.reasons
            ),
        }
 
        logger.debug(
            "Risk summary generated."
        )
 
        return summary