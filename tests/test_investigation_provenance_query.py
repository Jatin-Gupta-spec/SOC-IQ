"""
Tests for Phase A4-P2 Part 2 -- Investigation Provenance & Integrity:
Provenance Surfacing + Query/Read Model.

Covers:

* `app.application.dto.SourceIntegrityDTO` /
  `IOCProvenanceDTO` -- explicit DTO mapping from the domain layer
  (`Investigation`, `app.services.ioc_provenance.IOCProvenance`),
  never a bare domain object crossing the command boundary.
* `app.application.dto.GetInvestigationProvenanceRequest` --
  validation, mirroring `GetInvestigationIntegrityRequest`.
* `app.application.handlers.GetInvestigationProvenanceCommandHandler`
  -- success shape, empty-provenance state, not-found behavior, and
  investigation-scoped isolation (Investigation A never returns
  Investigation B's provenance).
* `app.application.handlers.dispatch` / `COMMAND_HANDLERS` -- the
  `get_investigation_provenance` command is registered and reachable
  through the same seam every other command uses.
* `app.api.app` -- the existing generic `POST /commands/{name}` route
  reaches the new handler with no new route needed.
* Regression -- `get_investigation_integrity` (A4-P1) and
  `get_iocs`/`get_investigation` continue to work unchanged alongside
  the new command.
"""

from __future__ import annotations

import unittest

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.application.dto import (
    CommandValidationError,
    GetInvestigationIntegrityRequest,
    GetInvestigationProvenanceRequest,
    GetIocsRequest,
    IOCProvenanceDTO,
    SourceIntegrityDTO,
)
from app.application.errors import INVALID_COMMAND_PAYLOAD, INVESTIGATION_NOT_FOUND
from app.application.handlers import (
    COMMAND_HANDLERS,
    GetInvestigationIntegrityCommandHandler,
    GetInvestigationProvenanceCommandHandler,
    GetIocsCommandHandler,
    dispatch,
)
from app.database.connection import DatabaseConnection
from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.database.service import InvestigationService
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
    )
    defaults.update(overrides)
    return Investigation(**defaults)


# ==========================================================
# SourceIntegrityDTO
# ==========================================================


class TestSourceIntegrityDTO:
    def test_available_when_hash_present(self):
        investigation = make_investigation(
            source_sha256="a" * 64,
            source_size_bytes=1234,
        )
        dto = SourceIntegrityDTO.from_domain(investigation)

        assert dto.status == "AVAILABLE"
        assert dto.algorithm == "sha256"
        assert dto.sha256 == "a" * 64
        assert dto.size_bytes == 1234
        assert dto.reason is None

    def test_unavailable_for_legacy_investigation(self):
        investigation = make_investigation(
            source_sha256=None,
            source_size_bytes=None,
        )
        dto = SourceIntegrityDTO.from_domain(investigation)

        assert dto.status == "UNAVAILABLE"
        assert dto.algorithm is None
        assert dto.sha256 is None
        assert dto.reason == "legacy_investigation_predates_source_hashing"

    def test_to_dict_shape(self):
        investigation = make_investigation(
            report_name="report4.txt",
            source_sha256="b" * 64,
            source_size_bytes=99,
        )
        as_dict = SourceIntegrityDTO.from_domain(investigation).to_dict()

        assert as_dict == {
            "report_name": "report4.txt",
            "algorithm": "sha256",
            "sha256": "b" * 64,
            "size_bytes": 99,
            "status": "AVAILABLE",
            "reason": None,
        }


# ==========================================================
# IOCProvenanceDTO
# ==========================================================


class TestIOCProvenanceDTO:
    def test_from_domain_flattens_nested_value_objects(self):
        record = IOCProvenance(
            ioc_value="8.8.8.8",
            source=SourceReference(
                report_name="malware_report.txt",
                source_sha256="c" * 64,
            ),
            extraction=ExtractionMethod(ioc_type="ipv4"),
            state=ObservationState.OBSERVED,
        )

        dto = IOCProvenanceDTO.from_domain(record)

        assert dto.to_dict() == {
            "ioc_value": "8.8.8.8",
            "ioc_type": "ipv4",
            "state": "OBSERVED",
            "report_name": "malware_report.txt",
            "source_sha256": "c" * 64,
            "extraction_method": "regex:ipv4",
        }


# ==========================================================
# GetInvestigationProvenanceRequest
# ==========================================================


class TestGetInvestigationProvenanceRequest:
    def test_valid_id_accepted(self):
        request = GetInvestigationProvenanceRequest(investigation_id=1)
        assert request.investigation_id == 1

    def test_zero_rejected(self):
        with pytest.raises(CommandValidationError):
            GetInvestigationProvenanceRequest(investigation_id=0)

    def test_negative_rejected(self):
        with pytest.raises(CommandValidationError):
            GetInvestigationProvenanceRequest(investigation_id=-5)

    def test_non_int_rejected(self):
        with pytest.raises(CommandValidationError):
            GetInvestigationProvenanceRequest(investigation_id="1")  # type: ignore[arg-type]

    def test_bool_rejected(self):
        # bool is an int subclass in Python -- explicitly excluded,
        # mirroring GetInvestigationRequest/GetIocsRequest.
        with pytest.raises(CommandValidationError):
            GetInvestigationProvenanceRequest(investigation_id=True)  # type: ignore[arg-type]


# ==========================================================
# GetInvestigationProvenanceCommandHandler
# ==========================================================


class TestGetInvestigationProvenanceCommand:
    @pytest.fixture()
    def repository(self, tmp_path):
        connection = DatabaseConnection(database_path=tmp_path / "test.db")
        repo = InvestigationRepository(database=connection)
        yield repo
        connection.close()

    def test_handler_returns_source_integrity_and_ioc_provenance(self, repository):
        investigation = make_investigation(
            source_sha256="d" * 64,
            source_size_bytes=42,
        )
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationProvenanceCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationProvenanceRequest(investigation_id=investigation_id)
        )

        assert response["success"] is True
        data = response["data"]

        assert data["investigation_id"] == investigation_id
        assert data["report_name"] == "malware_report.txt"

        assert data["source_integrity"]["status"] == "AVAILABLE"
        assert data["source_integrity"]["sha256"] == "d" * 64

        # 2 ipv4 + 1 domains + 0 sha256 = 3 provenance records.
        assert len(data["ioc_provenance"]) == 3
        assert all(item["state"] == "OBSERVED" for item in data["ioc_provenance"])
        values = {item["ioc_value"] for item in data["ioc_provenance"]}
        assert values == {"1.2.3.4", "8.8.8.8", "evil.example"}

    def test_handler_reflects_legacy_missing_source_hash(self, repository):
        investigation = make_investigation(
            source_sha256=None,
            source_size_bytes=None,
        )
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationProvenanceCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationProvenanceRequest(investigation_id=investigation_id)
        )

        data = response["data"]
        assert data["source_integrity"]["status"] == "UNAVAILABLE"
        # IOC provenance is still available even though the source hash
        # is not -- partial availability, never "investigation invalid".
        assert len(data["ioc_provenance"]) == 3

    def test_handler_returns_empty_list_for_investigation_with_no_iocs(self, repository):
        investigation = make_investigation(
            iocs={"ipv4": [], "domains": [], "sha256": []},
        )
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationProvenanceCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationProvenanceRequest(investigation_id=investigation_id)
        )

        assert response["success"] is True
        assert response["data"]["ioc_provenance"] == []

    def test_handler_returns_not_found_for_missing_investigation(self, repository):
        service = InvestigationService(repository=repository)
        handler = GetInvestigationProvenanceCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationProvenanceRequest(investigation_id=999999)
        )

        assert response["success"] is False
        assert response["error"]["code"] == INVESTIGATION_NOT_FOUND

    def test_investigation_a_never_returns_investigation_bs_provenance(self, repository):
        # Security/correctness requirement: cross-investigation isolation.
        investigation_a = make_investigation(
            report_name="report_a.txt",
            iocs={"ipv4": ["1.1.1.1"], "domains": [], "sha256": []},
            source_sha256="a" * 64,
            source_size_bytes=10,
        )
        investigation_b = make_investigation(
            report_name="report_b.txt",
            iocs={"ipv4": ["2.2.2.2"], "domains": ["only-in-b.example"], "sha256": []},
            source_sha256="b" * 64,
            source_size_bytes=20,
        )
        id_a = repository.save(investigation_a)
        id_b = repository.save(investigation_b)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationProvenanceCommandHandler(service=service)

        response_a = handler.handle(
            GetInvestigationProvenanceRequest(investigation_id=id_a)
        )
        response_b = handler.handle(
            GetInvestigationProvenanceRequest(investigation_id=id_b)
        )

        data_a = response_a["data"]
        data_b = response_b["data"]

        assert data_a["investigation_id"] == id_a
        assert data_b["investigation_id"] == id_b

        values_a = {item["ioc_value"] for item in data_a["ioc_provenance"]}
        values_b = {item["ioc_value"] for item in data_b["ioc_provenance"]}

        assert values_a == {"1.1.1.1"}
        assert values_b == {"2.2.2.2", "only-in-b.example"}
        assert values_a.isdisjoint(values_b)

        assert data_a["source_integrity"]["sha256"] == "a" * 64
        assert data_b["source_integrity"]["sha256"] == "b" * 64

        # Every provenance record's own source reference also points
        # back at its own investigation's report, never the other one's.
        assert all(
            item["report_name"] == "report_a.txt" for item in data_a["ioc_provenance"]
        )
        assert all(
            item["report_name"] == "report_b.txt" for item in data_b["ioc_provenance"]
        )

    def test_command_is_registered_in_command_handlers_table(self):
        assert "get_investigation_provenance" in COMMAND_HANDLERS

    def test_dispatch_rejects_invalid_investigation_id(self):
        response = dispatch("get_investigation_provenance", {"investigation_id": -1})

        assert response["success"] is False
        assert response["error"]["code"] == INVALID_COMMAND_PAYLOAD

    def test_dispatch_rejects_unexpected_payload_fields(self):
        response = dispatch(
            "get_investigation_provenance",
            {"investigation_id": 1, "unexpected": True},
        )

        assert response["success"] is False
        assert response["error"]["code"] == INVALID_COMMAND_PAYLOAD


# ==========================================================
# API layer -- POST /commands/get_investigation_provenance
# ==========================================================


class GetInvestigationProvenanceRouteTests(unittest.TestCase):
    """The existing generic `/commands/{name}` route (app/api/app.py)
    reaches the new handler through `COMMAND_HANDLERS` -- no new route
    was added. Only validation-only / not-found assertions are made
    here (mirroring tests/test_api_layer.py's own stated constraint):
    this file does not control the contents of the real database, so
    it makes no assertion that depends on specific persisted data.
    """

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_validation_error_never_reaches_domain(self) -> None:
        response = self.client.post(
            "/commands/get_investigation_provenance", json={"investigation_id": -1}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_not_found_is_translated_not_raised(self) -> None:
        response = self.client.post(
            "/commands/get_investigation_provenance",
            json={"investigation_id": 999999999},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVESTIGATION_NOT_FOUND)


# ==========================================================
# Regression -- existing commands unaffected
# ==========================================================


class TestExistingCommandsUnaffected:
    @pytest.fixture()
    def repository(self, tmp_path):
        connection = DatabaseConnection(database_path=tmp_path / "test.db")
        repo = InvestigationRepository(database=connection)
        yield repo
        connection.close()

    def test_get_investigation_integrity_still_works(self, repository):
        investigation = make_investigation(source_sha256="e" * 64, source_size_bytes=7)
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationIntegrityCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationIntegrityRequest(investigation_id=investigation_id)
        )

        assert response["success"] is True
        assert response["data"]["source_sha256"] == "e" * 64

    def test_get_iocs_still_works(self, repository):
        investigation = make_investigation()
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetIocsCommandHandler(service=service)

        response = handler.handle(GetIocsRequest(investigation_id=investigation_id))

        assert response["success"] is True
        assert response["data"]["iocs"]["ipv4"] == ["1.2.3.4", "8.8.8.8"]

    def test_build_ioc_provenance_still_pure_and_unchanged(self, repository):
        # A4-P2.1's factory keeps working unmodified underneath the new
        # query/read model added in this part.
        investigation = make_investigation()
        records = build_ioc_provenance(investigation)
        assert len(records) == 3
