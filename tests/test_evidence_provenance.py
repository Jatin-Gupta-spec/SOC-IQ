"""
Regression tests for SOC-IQ Phase A4-P1 -- Evidence Provenance &
Investigation Integrity.

Covers:

* app.extractor.compute_source_provenance -- source-hash correctness
  (same bytes -> same SHA-256, changed bytes -> different SHA-256),
  the actual-accepted-bytes-not-decoded-text distinction, and that the
  existing §20 size-cap / non-UTF-8 rejection behavior is preserved.
* app.database.migrations/0002_add_source_provenance.sql -- applies
  cleanly against both a fresh database and a real pre-A4-P1
  (post-0001) database with existing rows.
* app.database.repository.InvestigationRepository -- source_sha256 /
  source_size_bytes persist and round-trip; a legacy row (NULL in
  both new columns) still loads safely as `None`, never a fabricated
  value.
* app.services.investigation_integrity.build_integrity_summary --
  every field, across the honest sentinel states
  app.analyzer.analyze_report already writes for a
  disabled/unavailable/not-yet-run pipeline stage.
* app.services.evidence_provenance.build_evidence_provenance_summary
  -- OBSERVED / ENRICHED / DERIVED counts.
* app.application.dto.InvestigationSummaryDTO -- exposes the new
  source fields.
* app.application.handlers -- the new `get_investigation_integrity`
  command, both via its handler class directly and via the
  `dispatch()` seam / `COMMAND_HANDLERS` table.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app.application.dto import GetInvestigationIntegrityRequest
from app.application.errors import INVESTIGATION_NOT_FOUND
from app.application.handlers import (
    COMMAND_HANDLERS,
    GetInvestigationIntegrityCommandHandler,
    dispatch,
)
from app.application.dto import InvestigationSummaryDTO
from app.database.connection import DatabaseConnection
from app.database.migration_runner import run_migrations
from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.exceptions import ReportReadError
from app.extractor import MAX_REPORT_SIZE_BYTES, compute_source_provenance
from app.services.evidence_provenance import build_evidence_provenance_summary
from app.services.investigation_integrity import build_integrity_summary


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="malware_report.txt",
        iocs={"ipv4": ["1.2.3.4"], "domains": ["evil.example"], "sha256": []},
        threat_intelligence={"status": "ok", "hashes": [], "coverage": {"succeeded": 1}},
        risk_score=42,
        severity="MEDIUM",
        confidence=0.75,
        ioc_score=10,
        threat_intel_score=0,
        cve_score=0,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


# ==========================================================
# app.extractor.compute_source_provenance
# ==========================================================


class TestComputeSourceProvenance:
    def test_same_bytes_produce_same_sha256(self, tmp_path):
        content = b"IOC report: 10.0.0.1 evil.example.com"

        path_a = tmp_path / "a.txt"
        path_b = tmp_path / "b.txt"
        path_a.write_bytes(content)
        path_b.write_bytes(content)

        result_a = compute_source_provenance(path_a)
        result_b = compute_source_provenance(path_b)

        assert result_a.sha256 == result_b.sha256

    def test_changed_bytes_produce_different_sha256(self, tmp_path):
        path = tmp_path / "report.txt"
        path.write_bytes(b"original content")
        first = compute_source_provenance(path)

        path.write_bytes(b"modified content")
        second = compute_source_provenance(path)

        assert first.sha256 != second.sha256

    def test_hash_matches_manual_sha256_of_raw_bytes(self, tmp_path):
        content = b"raw bytes exactly as analyzed \xff\xfe not decoded first"
        # Deliberately includes bytes that are not valid UTF-8 on their
        # own, to make sure the hash is over the *raw* bytes, never a
        # round-tripped/re-encoded string.
        path = tmp_path / "report.bin"
        path.write_bytes(content)

        # This particular content is not valid UTF-8, so decoding must
        # fail -- but the hash must still be computed over the raw
        # bytes, per app.extractor.SourceProvenance's own docstring.
        # Use a UTF-8-safe variant to assert the successful path,
        # and a separate assertion below for the rejection path.
        utf8_content = b"raw bytes exactly as analyzed, no re-encoding"
        path.write_bytes(utf8_content)

        result = compute_source_provenance(path)

        assert result.sha256 == hashlib.sha256(utf8_content).hexdigest()
        assert result.size_bytes == len(utf8_content)
        assert result.text == utf8_content.decode("utf-8")

    def test_oversized_report_is_rejected_same_as_read_report(self, tmp_path):
        path = tmp_path / "oversized.txt"
        path.write_bytes(b"A" * (MAX_REPORT_SIZE_BYTES + 1))

        with pytest.raises(ReportReadError):
            compute_source_provenance(path)

    def test_report_exactly_at_the_cap_is_accepted(self, tmp_path):
        path = tmp_path / "at_cap.txt"
        path.write_bytes(b"A" * MAX_REPORT_SIZE_BYTES)

        result = compute_source_provenance(path)

        assert result.size_bytes == MAX_REPORT_SIZE_BYTES

    def test_non_utf8_report_is_rejected(self, tmp_path):
        path = tmp_path / "binary.bin"
        path.write_bytes(b"\xff\xfe\x00\x01not-utf8")

        with pytest.raises(ReportReadError):
            compute_source_provenance(path)

    def test_missing_file_raises_report_read_error(self, tmp_path):
        with pytest.raises(ReportReadError):
            compute_source_provenance(tmp_path / "does_not_exist.txt")


# ==========================================================
# Migration 0002
# ==========================================================


class TestSourceProvenanceMigration:
    def test_fresh_database_has_new_columns(self, tmp_path):
        db_path = tmp_path / "fresh.db"
        version = run_migrations(db_path)

        # Latest schema version as of MAX-21B-2 (F2 fix,
        # 0004_unique_report_name.sql) -- was 3 prior to that
        # migration.
        assert version == 4

        connection = sqlite3.connect(db_path)
        try:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(investigations);")
            }
        finally:
            connection.close()

        assert "source_sha256" in columns
        assert "source_size_bytes" in columns

    def test_pre_a4_p1_database_migrates_without_losing_data(self, tmp_path):
        """A real post-0001 database (no source_sha256/source_size_bytes
        columns, one existing row) must migrate cleanly to version 2,
        with the existing row's data completely intact and the new
        columns present (and NULL) on it."""

        db_path = tmp_path / "legacy.db"

        # Simulate a database already at schema version 1 (0001 applied,
        # 0002 not yet written), with one real pre-A4-P1 row.
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                CREATE TABLE investigations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_name TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    iocs TEXT NOT NULL,
                    threat_intelligence TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    ioc_score INTEGER NOT NULL,
                    threat_intel_score INTEGER NOT NULL,
                    cve_score INTEGER NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO investigations (report_name, analyzed_at, status, "
                "iocs, threat_intelligence, risk_score, severity, confidence, "
                "ioc_score, threat_intel_score, cve_score) VALUES "
                "('legacy_report.txt', '2025-01-01T00:00:00+00:00', 'COMPLETED', "
                "'{}', '{}', 10, 'LOW', 0.5, 5, 0, 0);"
            )
            connection.execute(
                "CREATE TABLE schema_version (version INTEGER NOT NULL);"
            )
            connection.execute("INSERT INTO schema_version (version) VALUES (1);")
            connection.commit()
        finally:
            connection.close()

        version = run_migrations(db_path)
        # See test_fresh_database_has_new_columns re: version 3 -> 4.
        assert version == 4

        connection = sqlite3.connect(db_path)
        try:
            row = connection.execute(
                "SELECT report_name, source_sha256, source_size_bytes "
                "FROM investigations;"
            ).fetchone()
        finally:
            connection.close()

        assert row[0] == "legacy_report.txt"
        assert row[1] is None
        assert row[2] is None

    def test_migration_is_idempotent(self, tmp_path):
        db_path = tmp_path / "idempotent.db"
        run_migrations(db_path)
        version = run_migrations(db_path)
        # See test_fresh_database_has_new_columns re: version 3 -> 4.
        assert version == 4


# ==========================================================
# InvestigationRepository persistence
# ==========================================================


class TestRepositorySourceProvenance:
    @pytest.fixture()
    def repository(self, tmp_path):
        connection = DatabaseConnection(database_path=tmp_path / "test.db")
        repo = InvestigationRepository(database=connection)
        yield repo
        connection.close()

    def test_source_hash_survives_persistence(self, repository):
        investigation = make_investigation(
            source_sha256="a" * 64,
            source_size_bytes=1234,
        )

        investigation_id = repository.save(investigation)
        loaded = repository.get_by_id(investigation_id)

        assert loaded is not None
        assert loaded.source_sha256 == "a" * 64
        assert loaded.source_size_bytes == 1234

    def test_legacy_row_without_provenance_is_safely_readable(self, repository, tmp_path):
        """A row inserted the pre-A4-P1 way (no source columns supplied,
        relying on SQLite's NULL default) must load with `None` in both
        fields -- not raise, not fabricate a hash."""

        with repository._database as connection:  # noqa: SLF001 -- direct raw
            # insert deliberately bypasses save() to simulate a genuinely
            # pre-A4-P1 row where the new columns were never written.
            cursor = connection.execute(
                """
                INSERT INTO investigations (
                    report_name, analyzed_at, status, iocs,
                    threat_intelligence, risk_score, severity, confidence,
                    ioc_score, threat_intel_score, cve_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    "legacy.txt",
                    "2025-01-01T00:00:00+00:00",
                    "COMPLETED",
                    "{}",
                    "{}",
                    0,
                    "LOW",
                    0.0,
                    0,
                    0,
                    0,
                ),
            )
            connection.commit()
            legacy_id = cursor.lastrowid

        loaded = repository.get_by_id(legacy_id)

        assert loaded is not None
        assert loaded.source_sha256 is None
        assert loaded.source_size_bytes is None


# ==========================================================
# app.services.investigation_integrity
# ==========================================================


class TestInvestigationIntegritySummary:
    def test_fully_complete_investigation(self):
        investigation = make_investigation(
            source_sha256="a" * 64,
            source_size_bytes=10,
            threat_intelligence={"status": "ok", "hashes": []},
        )

        summary = build_integrity_summary(investigation)

        assert summary.source_identified is True
        assert summary.source_hash_available is True
        assert summary.analysis_completed is True
        assert summary.ioc_extraction_completed is True
        assert summary.threat_intel_attempted is True
        assert summary.threat_intel_complete is True
        assert summary.risk_calculation_completed is True

    def test_legacy_investigation_without_source_hash(self):
        investigation = make_investigation(
            source_sha256=None,
            source_size_bytes=None,
        )

        summary = build_integrity_summary(investigation)

        assert summary.source_hash_available is False
        # Legacy status is independent of source-hash availability.
        assert summary.source_identified is True

    def test_threat_intel_not_attempted(self):
        investigation = make_investigation(
            threat_intelligence={"status": "unavailable", "reason": "not_attempted"},
        )

        summary = build_integrity_summary(investigation)

        assert summary.threat_intel_attempted is False
        assert summary.threat_intel_complete is False

    def test_threat_intel_disabled(self):
        investigation = make_investigation(
            threat_intelligence={"status": "unavailable", "reason": "disabled"},
        )

        summary = build_integrity_summary(investigation)

        assert summary.threat_intel_attempted is False
        assert summary.threat_intel_complete is False

    def test_threat_intel_attempted_but_failed(self):
        investigation = make_investigation(
            threat_intelligence={"status": "unavailable", "reason": "error"},
        )

        summary = build_integrity_summary(investigation)

        assert summary.threat_intel_attempted is True
        assert summary.threat_intel_complete is False

    def test_threat_intel_missing_api_key(self):
        investigation = make_investigation(
            threat_intelligence={"status": "unavailable", "reason": "missing_api_key"},
        )

        summary = build_integrity_summary(investigation)

        assert summary.threat_intel_attempted is True
        assert summary.threat_intel_complete is False

    def test_threat_intel_partial_counts_as_complete(self):
        investigation = make_investigation(
            threat_intelligence={"status": "partial", "hashes": []},
        )

        summary = build_integrity_summary(investigation)

        assert summary.threat_intel_attempted is True
        assert summary.threat_intel_complete is True

    def test_risk_scoring_disabled(self):
        investigation = make_investigation(severity="NOT_SCORED")

        summary = build_integrity_summary(investigation)

        assert summary.risk_calculation_completed is False


# ==========================================================
# app.services.evidence_provenance
# ==========================================================


class TestEvidenceProvenanceSummary:
    def test_observed_and_enrichable_counts(self):
        investigation = make_investigation(
            iocs={
                "ipv4": ["1.2.3.4", "5.6.7.8"],
                "domains": ["evil.example"],
                "sha256": ["a" * 64],
                "emails": ["x@example.com"],
            },
            threat_intelligence={
                "status": "ok",
                "coverage": {"succeeded": 3, "requested": 4},
            },
        )

        summary = build_evidence_provenance_summary(investigation)

        assert summary.observed_ioc_count == 5
        # ipv4(2) + domains(1) + sha256(1) = 4 enrichable; emails is not.
        assert summary.enrichable_ioc_count == 4
        assert summary.enriched_ioc_count == 3
        assert summary.threat_intel_status == "ok"
        assert summary.risk_calculated is True

    def test_unavailable_threat_intel_yields_zero_enriched(self):
        investigation = make_investigation(
            iocs={"ipv4": ["1.2.3.4"]},
            threat_intelligence={"status": "unavailable", "reason": "not_attempted"},
        )

        summary = build_evidence_provenance_summary(investigation)

        assert summary.enriched_ioc_count == 0
        assert summary.threat_intel_status == "unavailable"
        assert summary.threat_intel_reason == "not_attempted"

    def test_risk_not_calculated_is_reflected(self):
        investigation = make_investigation(severity="NOT_SCORED")

        summary = build_evidence_provenance_summary(investigation)

        assert summary.risk_calculated is False

    def test_to_dict_round_trips_all_fields(self):
        investigation = make_investigation()
        summary = build_evidence_provenance_summary(investigation)
        payload = summary.to_dict()

        assert set(payload.keys()) == {
            "observed_ioc_count",
            "enrichable_ioc_count",
            "enriched_ioc_count",
            "threat_intel_status",
            "threat_intel_reason",
            "risk_calculated",
        }


# ==========================================================
# app.application.dto.InvestigationSummaryDTO
# ==========================================================


class TestInvestigationSummaryDTOProvenance:
    def test_from_domain_includes_source_fields(self):
        investigation = make_investigation(
            investigation_id=1,
            source_sha256="b" * 64,
            source_size_bytes=99,
        )

        dto = InvestigationSummaryDTO.from_domain(investigation)
        payload = dto.to_dict()

        assert payload["source_sha256"] == "b" * 64
        assert payload["source_size_bytes"] == 99

    def test_from_domain_reflects_missing_source_hash(self):
        investigation = make_investigation(investigation_id=1)

        payload = InvestigationSummaryDTO.from_domain(investigation).to_dict()

        assert payload["source_sha256"] is None
        assert payload["source_size_bytes"] is None


# ==========================================================
# GetInvestigationIntegrityCommandHandler / dispatch
# ==========================================================


class TestGetInvestigationIntegrityCommand:
    @pytest.fixture()
    def repository(self, tmp_path):
        connection = DatabaseConnection(database_path=tmp_path / "test.db")
        repo = InvestigationRepository(database=connection)
        yield repo
        connection.close()

    def test_handler_returns_integrity_and_evidence(self, repository):
        investigation = make_investigation(
            source_sha256="c" * 64,
            source_size_bytes=42,
        )
        investigation_id = repository.save(investigation)

        from app.database.service import InvestigationService

        service = InvestigationService(repository=repository)
        handler = GetInvestigationIntegrityCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationIntegrityRequest(investigation_id=investigation_id)
        )

        assert response["success"] is True
        data = response["data"]
        assert data["source_sha256"] == "c" * 64
        assert data["source_size_bytes"] == 42
        assert data["integrity"]["source_hash_available"] is True
        assert "observed_ioc_count" in data["evidence"]

    def test_handler_returns_not_found_for_missing_investigation(self, repository):
        from app.database.service import InvestigationService

        service = InvestigationService(repository=repository)
        handler = GetInvestigationIntegrityCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationIntegrityRequest(investigation_id=999999)
        )

        assert response["success"] is False
        assert response["error"]["code"] == INVESTIGATION_NOT_FOUND

    def test_command_is_registered_in_command_handlers_table(self):
        assert "get_investigation_integrity" in COMMAND_HANDLERS

    def test_dispatch_rejects_invalid_investigation_id(self):
        response = dispatch("get_investigation_integrity", {"investigation_id": -1})

        assert response["success"] is False
