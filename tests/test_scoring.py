"""
Regression tests for the SOC-IQ risk scoring engine
(app.scoring.engine.RiskScoringEngine).

Covers per-type IOC weighting, risk score composition, severity
thresholds, empty input, and assorted edge cases.
"""

from __future__ import annotations

import pytest

from app.scoring.engine import RiskScoringEngine
from app.scoring.models import RiskScore


@pytest.fixture()
def engine():
    return RiskScoringEngine()


# ==========================================================
# IOC weighting
# ==========================================================


@pytest.mark.parametrize(
    "ioc_type,weight",
    [
        ("ipv4", 1),
        ("domains", 2),
        ("urls", 3),
        ("emails", 1),
        ("md5", 4),
        ("sha1", 5),
        ("sha256", 6),
        ("cves", 8),
        ("windows_file_paths", 2),
        ("windows_registry_keys", 3),
    ],
)
def test_ioc_weight_applied_per_type(engine, ioc_type, weight):
    score = engine._calculate_ioc_score({ioc_type: ["value1", "value2"]})

    assert score == weight * 2


def test_unknown_ioc_type_contributes_zero_weight(engine):
    score = engine._calculate_ioc_score({"unknown_type": ["a", "b", "c"]})

    assert score == 0


def test_ioc_score_sums_across_multiple_types(engine):
    score = engine._calculate_ioc_score(
        {
            "ipv4": ["1.1.1.1"],  # weight 1 -> 1
            "domains": ["a.com", "b.com"],  # weight 2 -> 4
            "sha256": ["c" * 64],  # weight 6 -> 6
        }
    )

    assert score == 1 + 4 + 6


def test_ioc_score_empty_dict_is_zero(engine):
    assert engine._calculate_ioc_score({}) == 0


def test_ioc_score_ignores_empty_value_lists(engine):
    assert engine._calculate_ioc_score({"domains": []}) == 0


# ==========================================================
# CVE score
# ==========================================================


def test_cve_score_multiplies_by_ten(engine):
    score = engine._calculate_cve_score({"cves": ["CVE-2024-0001", "CVE-2024-0002"]})

    assert score == 20


def test_cve_score_missing_key_is_zero(engine):
    assert engine._calculate_cve_score({}) == 0


# ==========================================================
# Threat intelligence score
# ==========================================================


def test_threat_intel_score_from_malicious_and_suspicious(engine):
    threat_intel = {
        "hashes": [
            {"malicious": 3, "suspicious": 2, "reputation": None},
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == (3 * 5) + (2 * 2)


def test_threat_intel_score_adds_negative_reputation(engine):
    threat_intel = {
        "hashes": [
            {"malicious": 0, "suspicious": 0, "reputation": -15},
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == 15


def test_threat_intel_score_ignores_positive_reputation(engine):
    threat_intel = {
        "hashes": [
            {"malicious": 0, "suspicious": 0, "reputation": 20},
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == 0


def test_threat_intel_score_empty_hashes_is_zero(engine):
    assert engine._calculate_threat_intel_score({"hashes": []}) == 0


def test_threat_intel_score_missing_hashes_key_is_zero(engine):
    assert engine._calculate_threat_intel_score({}) == 0


# ----------------------------------------------------------------
# Threat intelligence score -- non-hash categories (Phase 3E parity)
# ----------------------------------------------------------------


def test_threat_intel_score_malicious_ipv4_contributes(engine):
    threat_intel = {
        "ips": [
            {"ip": "1.2.3.4", "malicious": 2, "suspicious": 0, "reputation": None},
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == 2 * 5


def test_threat_intel_score_suspicious_ipv4_contributes(engine):
    threat_intel = {
        "ips": [
            {"ip": "1.2.3.4", "malicious": 0, "suspicious": 3, "reputation": None},
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == 3 * 2


def test_threat_intel_score_malicious_domain_contributes(engine):
    threat_intel = {
        "domains": [
            {
                "domain": "evilcorp.com",
                "malicious": 1,
                "suspicious": 0,
                "reputation": None,
            },
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == 1 * 5


def test_threat_intel_score_malicious_url_contributes(engine):
    threat_intel = {
        "urls": [
            {
                "url": "https://evilcorp.com/payload.exe",
                "malicious": 4,
                "suspicious": 0,
                "reputation": None,
            },
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == 4 * 5


def test_threat_intel_score_sums_across_all_four_categories(engine):
    threat_intel = {
        "hashes": [{"malicious": 1, "suspicious": 0, "reputation": None}],
        "ips": [{"ip": "1.2.3.4", "malicious": 1, "suspicious": 0, "reputation": None}],
        "domains": [
            {"domain": "evilcorp.com", "malicious": 0, "suspicious": 1, "reputation": None}
        ],
        "urls": [
            {
                "url": "https://evilcorp.com/payload.exe",
                "malicious": 0,
                "suspicious": 0,
                "reputation": -10,
            }
        ],
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    # hashes: 1*5, ips: 1*5, domains: 1*2, urls: 10
    assert score == 5 + 5 + 2 + 10


def test_threat_intel_score_no_hash_but_malicious_non_hash_still_nonzero(engine):
    """
    A malicious IPv4/domain/URL contributes to the TI score even when
    there is no SHA256 hash at all -- the pre-Phase-3E hash-only
    behavior must not silently drop non-hash indicators.
    """

    threat_intel = {
        "hashes": [],
        "ips": [{"ip": "1.2.3.4", "malicious": 2, "suspicious": 0, "reputation": None}],
        "domains": [
            {"domain": "evilcorp.com", "malicious": 1, "suspicious": 0, "reputation": None}
        ],
        "urls": [
            {
                "url": "https://evilcorp.com/payload.exe",
                "malicious": 1,
                "suspicious": 0,
                "reputation": None,
            }
        ],
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score > 0
    assert score == (2 * 5) + (1 * 5) + (1 * 5)


def test_threat_intel_score_existing_hash_only_behavior_unchanged(engine):
    """
    Hash-only threat intelligence must score identically to the
    pre-Phase-3E behavior.
    """

    threat_intel = {
        "hashes": [
            {"malicious": 3, "suspicious": 2, "reputation": -15},
        ]
    }

    score = engine._calculate_threat_intel_score(threat_intel)

    assert score == (3 * 5) + (2 * 2) + 15


# ==========================================================
# Severity thresholds
# ==========================================================


@pytest.mark.parametrize(
    "score,expected_severity",
    [
        (0, "LOW"),
        (20, "LOW"),
        (21, "MEDIUM"),
        (40, "MEDIUM"),
        (41, "HIGH"),
        (70, "HIGH"),
        (71, "CRITICAL"),
        (100, "CRITICAL"),
    ],
)
def test_severity_thresholds(engine, score, expected_severity):
    assert engine._determine_severity(score) == expected_severity


# ==========================================================
# Score normalization
# ==========================================================


def test_normalize_score_clamps_upper_bound(engine):
    assert engine.normalize_score(500) == RiskScoringEngine.MAX_SCORE


def test_normalize_score_clamps_lower_bound(engine):
    assert engine.normalize_score(-50) == 0


def test_normalize_score_within_range_is_unchanged(engine):
    assert engine.normalize_score(55) == 55


# ==========================================================
# calculate(): empty input / full pipeline
# ==========================================================


def test_calculate_with_empty_input_returns_zero_low_risk(engine):
    result = engine.calculate({}, {})

    assert isinstance(result, RiskScore)
    assert result.score == 0
    assert result.severity == "LOW"
    assert result.ioc_score == 0
    assert result.threat_intel_score == 0
    assert result.cve_score == 0


def test_calculate_with_empty_iocs_and_empty_threat_intel_has_confidence_zero(
    engine,
):
    result = engine.calculate({}, {})

    assert result.confidence == 0.0


def test_calculate_combines_all_three_score_components(engine):
    iocs = {
        "ipv4": ["1.1.1.1"],  # 1
        "cves": ["CVE-2024-0001"],  # ioc weight 8, plus cve bonus 10
    }
    threat_intel = {
        "status": "ok",
        "hashes": [{"malicious": 1, "suspicious": 0, "reputation": None}],
    }

    result = engine.calculate(iocs, threat_intel)

    expected_ioc_score = 1 + 8  # ipv4 + cves weight
    expected_threat_score = 5  # 1 malicious * 5
    expected_cve_score = 10  # 1 cve * 10

    assert result.ioc_score == expected_ioc_score
    assert result.threat_intel_score == expected_threat_score
    assert result.cve_score == expected_cve_score
    assert result.score == (
        expected_ioc_score + expected_threat_score + expected_cve_score
    )


def test_calculate_score_is_normalized_to_max(engine):
    # Enough CVEs to blow past MAX_SCORE.
    iocs = {"cves": [f"CVE-2024-{i:04d}" for i in range(50)]}

    result = engine.calculate(iocs, {})

    assert result.score == RiskScoringEngine.MAX_SCORE
    assert result.severity == "CRITICAL"


def test_calculate_reasons_include_incomplete_ti_status(engine):
    result = engine.calculate({}, {"status": "partial", "hashes": []})

    assert any("incomplete" in reason.lower() for reason in result.reasons)


def test_calculate_reasons_omit_incomplete_note_when_ti_ok(engine):
    result = engine.calculate({}, {"status": "ok", "hashes": []})

    assert not any("incomplete" in reason.lower() for reason in result.reasons)


def test_calculate_reasons_omit_incomplete_note_when_no_indicators(engine):
    result = engine.calculate({}, {"status": "no_indicators", "hashes": []})

    assert not any("incomplete" in reason.lower() for reason in result.reasons)


def test_calculate_reasons_treat_missing_threat_intel_as_incomplete(engine):
    result = engine.calculate({"ipv4": ["1.1.1.1"]}, {})

    assert any("incomplete" in reason.lower() for reason in result.reasons)


# ==========================================================
# Confidence
# ==========================================================


def test_confidence_scales_with_total_ioc_count(engine):
    iocs = {"ipv4": [f"1.1.1.{i}" for i in range(20)]}

    confidence = engine._calculate_confidence(iocs, {"status": "ok"})

    assert confidence == pytest.approx(0.5)


def test_confidence_caps_at_one(engine):
    iocs = {"ipv4": [f"1.1.1.{i}" for i in range(100)]}

    confidence = engine._calculate_confidence(iocs, {"status": "ok"})

    assert confidence == 1.0


def test_confidence_halved_when_ti_incomplete(engine):
    iocs = {"ipv4": [f"1.1.1.{i}" for i in range(20)]}

    complete = engine._calculate_confidence(iocs, {"status": "ok"})
    incomplete = engine._calculate_confidence(iocs, {"status": "partial"})

    assert incomplete == pytest.approx(complete * 0.5)


def test_confidence_with_no_threat_intel_dict_still_halves(engine):
    iocs = {"ipv4": [f"1.1.1.{i}" for i in range(20)]}

    confidence = engine._calculate_confidence(iocs, None)

    assert confidence == pytest.approx(0.25)


# ==========================================================
# summarize()
# ==========================================================


def test_summarize_produces_expected_keys(engine):
    risk_score = engine.calculate(
        {"ipv4": ["1.1.1.1"]},
        {"status": "ok", "hashes": []},
    )

    summary = engine.summarize(risk_score)

    assert set(summary.keys()) == {
        "score",
        "severity",
        "confidence",
        "ioc_score",
        "threat_intel_score",
        "cve_score",
        "reasons",
    }
    assert summary["score"] == risk_score.score
    assert summary["reasons"] == risk_score.reasons


def test_summarize_reasons_is_a_copy_not_same_list(engine):
    risk_score = engine.calculate({"ipv4": ["1.1.1.1"]}, {})

    summary = engine.summarize(risk_score)
    summary["reasons"].append("mutated")

    assert "mutated" not in risk_score.reasons
