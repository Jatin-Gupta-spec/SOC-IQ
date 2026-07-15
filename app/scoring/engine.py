
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
        "IPv4": 1,
        "Domains": 2,
        "URLs": 3,
        "Emails": 1,
        "MD5": 4,
        "SHA1": 5,
        "SHA256": 6,
        "CVE": 8,
        "Windows File Paths": 2,
        "Windows Registry Keys": 3,
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
            "CVE",
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
    ) -> float:
        """
        Calculate confidence based on
        the amount of collected evidence.
        """
 
        total_iocs = sum(
            len(values)
            for values in iocs.values()
        )
 
        confidence = min(
            total_iocs / 40.0,
            1.0,
        )
 
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