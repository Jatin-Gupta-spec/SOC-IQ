"""
Unit tests for Phase A4-P2.1 -- IOC Provenance Domain Foundation.

Covers `app.services.ioc_provenance`:

* Valid `SourceReference` / `ExtractionMethod` / `IOCProvenance`
  construction.
* Invalid construction (empty IOC value, empty report name, unknown
  IOC type) raises `app.exceptions.ValidationError`.
* Immutability: `IOCProvenance` (and its component value objects) are
  frozen dataclasses.
* `build_ioc_provenance()`: OBSERVED semantics, one record per
  (ioc_type, value) pair, multiple provenance records for the same
  value across two different investigations/reports, legacy
  investigations (`source_sha256=None`) handled honestly, and
  unknown/blank IOC data skipped rather than raised.
* Regression: this module does not alter
  `app.extractor.extract_iocs` / `IOC_PATTERNS` behavior, and
  `app.services.evidence_provenance` continues to work unchanged
  alongside it.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.database.models import Investigation
from app.exceptions import ValidationError
from app.extractor import IOC_PATTERNS
from app.services.ioc_provenance import (
    ExtractionMethod,
    IOCProvenance,
    ObservationState,
    SourceReference,
    build_ioc_provenance,
)


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="malware_report.txt",
        iocs={
            "ipv4": ["1.2.3.4", "8.8.8.8"],
            "domains": ["evil.example"],
            "sha256": [],
        },
        threat_intelligence={"status": "unavailable", "reason": "not_attempted"},
        risk_score=0,
        severity="NOT_SCORED",
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
        source_sha256="a" * 64,
        source_size_bytes=1234,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


# ==========================================================
# SourceReference
# ==========================================================


class TestSourceReference:

    def test_valid_source_reference(self):
        source = SourceReference(
            report_name="malware_report.txt",
            source_sha256="a" * 64,
        )
        assert source.report_name == "malware_report.txt"
        assert source.source_sha256 == "a" * 64

    def test_source_sha256_optional_for_legacy_records(self):
        source = SourceReference(report_name="legacy_report.txt")
        assert source.source_sha256 is None

    def test_empty_report_name_rejected(self):
        with pytest.raises(ValidationError):
            SourceReference(report_name="")

    def test_blank_report_name_rejected(self):
        with pytest.raises(ValidationError):
            SourceReference(report_name="   ")

    def test_is_immutable(self):
        source = SourceReference(report_name="malware_report.txt")
        with pytest.raises(dataclasses.FrozenInstanceError):
            source.report_name = "other.txt"  # type: ignore[misc]


# ==========================================================
# ExtractionMethod
# ==========================================================


class TestExtractionMethod:

    def test_valid_extraction_method(self):
        method = ExtractionMethod(ioc_type="ipv4")
        assert method.ioc_type == "ipv4"
        assert method.description == "regex:ipv4"

    def test_every_known_ioc_type_is_accepted(self):
        for ioc_type in IOC_PATTERNS:
            method = ExtractionMethod(ioc_type=ioc_type)
            assert method.ioc_type == ioc_type

    def test_unknown_ioc_type_rejected(self):
        with pytest.raises(ValidationError):
            ExtractionMethod(ioc_type="not_a_real_ioc_type")

    def test_is_immutable(self):
        method = ExtractionMethod(ioc_type="ipv4")
        with pytest.raises(dataclasses.FrozenInstanceError):
            method.ioc_type = "domains"  # type: ignore[misc]


# ==========================================================
# IOCProvenance
# ==========================================================


class TestIOCProvenance:

    def test_valid_provenance_defaults_to_observed(self):
        record = IOCProvenance(
            ioc_value="8.8.8.8",
            source=SourceReference(report_name="malware_report.txt"),
            extraction=ExtractionMethod(ioc_type="ipv4"),
        )
        assert record.state == ObservationState.OBSERVED
        assert record.ioc_type == "ipv4"

    def test_derived_state_supported_but_not_default(self):
        record = IOCProvenance(
            ioc_value="8.8.8.8",
            source=SourceReference(report_name="malware_report.txt"),
            extraction=ExtractionMethod(ioc_type="ipv4"),
            state=ObservationState.DERIVED,
        )
        assert record.state == ObservationState.DERIVED

    def test_empty_ioc_value_rejected(self):
        with pytest.raises(ValidationError):
            IOCProvenance(
                ioc_value="",
                source=SourceReference(report_name="malware_report.txt"),
                extraction=ExtractionMethod(ioc_type="ipv4"),
            )

    def test_blank_ioc_value_rejected(self):
        with pytest.raises(ValidationError):
            IOCProvenance(
                ioc_value="   ",
                source=SourceReference(report_name="malware_report.txt"),
                extraction=ExtractionMethod(ioc_type="ipv4"),
            )

    def test_is_immutable(self):
        record = IOCProvenance(
            ioc_value="8.8.8.8",
            source=SourceReference(report_name="malware_report.txt"),
            extraction=ExtractionMethod(ioc_type="ipv4"),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.ioc_value = "1.1.1.1"  # type: ignore[misc]

    def test_to_dict_shape(self):
        record = IOCProvenance(
            ioc_value="8.8.8.8",
            source=SourceReference(
                report_name="malware_report.txt",
                source_sha256="a" * 64,
            ),
            extraction=ExtractionMethod(ioc_type="ipv4"),
        )
        as_dict = record.to_dict()
        assert as_dict == {
            "ioc_value": "8.8.8.8",
            "ioc_type": "ipv4",
            "state": "OBSERVED",
            "source": {
                "report_name": "malware_report.txt",
                "source_sha256": "a" * 64,
            },
            "extraction": {
                "ioc_type": "ipv4",
                "method": "regex:ipv4",
            },
        }


# ==========================================================
# build_ioc_provenance
# ==========================================================


class TestBuildIOCProvenance:

    def test_one_record_per_ioc_value(self):
        investigation = make_investigation()
        records = build_ioc_provenance(investigation)

        # 2 ipv4 + 1 domains + 0 sha256 = 3 records.
        assert len(records) == 3
        assert all(r.state is ObservationState.OBSERVED for r in records)

    def test_records_reference_the_investigations_report(self):
        investigation = make_investigation(report_name="report4.txt")
        records = build_ioc_provenance(investigation)

        assert all(r.source.report_name == "report4.txt" for r in records)

    def test_source_sha256_propagates_when_present(self):
        investigation = make_investigation(source_sha256="b" * 64)
        records = build_ioc_provenance(investigation)

        assert all(r.source.source_sha256 == "b" * 64 for r in records)

    def test_legacy_investigation_has_no_source_hash(self):
        investigation = make_investigation(
            source_sha256=None,
            source_size_bytes=None,
        )
        records = build_ioc_provenance(investigation)

        assert records  # still produces provenance for the IOCs
        assert all(r.source.source_sha256 is None for r in records)

    def test_empty_iocs_produces_no_records(self):
        investigation = make_investigation(
            iocs={ioc_type: [] for ioc_type in IOC_PATTERNS}
        )
        records = build_ioc_provenance(investigation)
        assert records == []

    def test_unknown_ioc_type_key_is_skipped_not_raised(self):
        investigation = make_investigation(
            iocs={"ipv4": ["1.2.3.4"], "not_a_real_type": ["whatever"]}
        )
        records = build_ioc_provenance(investigation)

        assert len(records) == 1
        assert records[0].ioc_type == "ipv4"

    def test_blank_value_is_skipped(self):
        investigation = make_investigation(
            iocs={"ipv4": ["1.2.3.4", "   ", ""]}
        )
        records = build_ioc_provenance(investigation)

        assert len(records) == 1
        assert records[0].ioc_value == "1.2.3.4"

    def test_same_value_across_two_reports_yields_two_provenance_records(self):
        first = make_investigation(
            report_name="report_a.txt",
            iocs={"ipv4": ["8.8.8.8"]},
        )
        second = make_investigation(
            report_name="report_b.txt",
            iocs={"ipv4": ["8.8.8.8"]},
        )

        records = build_ioc_provenance(first) + build_ioc_provenance(second)

        assert len(records) == 2
        assert {r.source.report_name for r in records} == {
            "report_a.txt",
            "report_b.txt",
        }
        assert all(r.ioc_value == "8.8.8.8" for r in records)

    def test_is_pure_does_not_mutate_investigation(self):
        investigation = make_investigation()
        original_iocs = {k: list(v) for k, v in investigation.iocs.items()}

        build_ioc_provenance(investigation)

        assert investigation.iocs == original_iocs
