"""
Tests for PD-08-P1 -- Risk Explanation Modern Backend/Application
Contract (docs/phase4/PD08_P1_RISK_EXPLANATION_BACKEND.md).

Covers:

* `app.application.dto.IocCategoryContributionDTO` /
  `RiskExplanationDTO` -- explicit DTO mapping from the existing
  PHASE3C-1 domain layer (`app.services.risk_explanation_models.
  IocCategoryContribution` / `RiskExplanation`), never a bare domain
  object crossing the command boundary.
* `app.application.dto.GetInvestigationRiskExplanationRequest` --
  validation, mirroring `GetInvestigationProvenanceRequest`.
* `app.application.handlers.GetInvestigationRiskExplanationCommandHandler`
  -- success shape, not-found behavior, investigation-scoped
  isolation (Investigation A never returns Investigation B's
  explanation), correlation wiring, and api_key_configured wiring.
* `app.application.handlers.dispatch` / `COMMAND_HANDLERS` -- the
  `get_investigation_risk_explanation` command is registered and
  reachable through the same seam every other command uses.
* `app.api.app` -- the existing generic `POST /commands/{name}` route
  reaches the new handler with no new route needed.
* Regression -- `get_investigation` / `get_investigation_provenance` /
  `get_investigation_integrity` continue to work unchanged alongside
  the new command, and the underlying `RiskExplanationService`'s own
  (PHASE3C-1) tests are untouched by this part.
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
    GetInvestigationRequest,
    GetInvestigationRiskExplanationRequest,
    IocCategoryContributionDTO,
    RiskExplanationDTO,
)
from app.application.errors import INVALID_COMMAND_PAYLOAD, INVESTIGATION_NOT_FOUND
from app.application.handlers import (
    COMMAND_HANDLERS,
    GetInvestigationCommandHandler,
    GetInvestigationIntegrityCommandHandler,
    GetInvestigationProvenanceCommandHandler,
    GetInvestigationRiskExplanationCommandHandler,
    dispatch,
)
from app.database.connection import DatabaseConnection
from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.database.service import InvestigationService
from app.settings.models import ApplicationSettings
from app.services.risk_explanation_models import (
    IocCategoryContribution,
    RiskExplanation,
)


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="malware_report.txt",
        iocs={
            "ipv4": ["1.2.3.4", "8.8.8.8"],
            "sha256": ["a" * 64],
        },
        threat_intelligence={"status": "unavailable", "reason": "not_attempted"},
        risk_score=17,
        severity="MEDIUM",
        confidence=0.6,
        ioc_score=8,
        threat_intel_score=0,
        cve_score=0,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


class _FakeSettingsService:
    """Minimal injectable stand-in for `SettingsService`, mirroring
    `tests/test_application_layer.py`'s own `_FakeSettingsService` --
    used to control `api_key_configured` deterministically rather
    than depending on whatever `SettingsRepository()` happens to find
    on disk.
    """

    def __init__(self, virustotal_api_key: str = "") -> None:
        self._settings = ApplicationSettings(virustotal_api_key=virustotal_api_key)

    def load_settings(self) -> ApplicationSettings:
        return self._settings


# ==========================================================
# IocCategoryContributionDTO
# ==========================================================


class TestIocCategoryContributionDTO:
    def test_from_domain_flattens_value_object(self):
        contribution = IocCategoryContribution(
            ioc_type="sha256",
            ioc_type_title="SHA256 Hash",
            count=2,
            weight=3,
            significance="High",
            points=6,
        )

        dto = IocCategoryContributionDTO.from_domain(contribution)

        assert dto.to_dict() == {
            "ioc_type": "sha256",
            "ioc_type_title": "SHA256 Hash",
            "count": 2,
            "weight": 3,
            "significance": "High",
            "points": 6,
        }


# ==========================================================
# RiskExplanationDTO
# ==========================================================


class TestRiskExplanationDTO:
    def test_from_domain_flattens_full_shape(self):
        explanation = RiskExplanation(
            investigation_id=7,
            report_name="report.txt",
            score=55,
            severity="HIGH",
            confidence=0.8,
            ioc_score=10,
            threat_intel_score=5,
            cve_score=2,
            ioc_categories=[
                IocCategoryContribution(
                    ioc_type="sha256",
                    ioc_type_title="SHA256 Hash",
                    count=1,
                    weight=6,
                    significance="High",
                    points=6,
                )
            ],
            ioc_breakdown_verified=True,
            threat_intel_state="enriched",
            threat_intel_message="Threat intelligence was checked.",
            threat_intel_short_label="Checked",
            threat_intel_requested=1,
            threat_intel_succeeded=1,
            threat_intel_malicious_hash_count=1,
            threat_intel_suspicious_hash_count=0,
            correlation_evaluated=True,
            correlation_relationship_count=2,
            correlation_summary="2 relationship(s) were identified.",
            engine_reasons=[],
            narrative=["This investigation is rated HIGH with a risk score of 55/100."],
            warnings=[],
        )

        dto = RiskExplanationDTO.from_domain(explanation)
        as_dict = dto.to_dict()

        assert as_dict["investigation_id"] == 7
        assert as_dict["score"] == 55
        assert as_dict["severity"] == "HIGH"
        assert as_dict["ioc_categories"] == [
            {
                "ioc_type": "sha256",
                "ioc_type_title": "SHA256 Hash",
                "count": 1,
                "weight": 6,
                "significance": "High",
                "points": 6,
            }
        ]
        assert as_dict["ioc_breakdown_verified"] is True
        assert as_dict["correlation_evaluated"] is True
        assert as_dict["correlation_relationship_count"] == 2
        assert as_dict["narrative"] == [
            "This investigation is rated HIGH with a risk score of 55/100."
        ]
        assert as_dict["warnings"] == []

    def test_from_domain_preserves_empty_categories(self):
        explanation = RiskExplanation(
            investigation_id=1,
            report_name="empty.txt",
            score=0,
            severity="LOW",
            confidence=0.0,
            ioc_score=0,
            threat_intel_score=0,
            cve_score=0,
        )

        as_dict = RiskExplanationDTO.from_domain(explanation).to_dict()

        assert as_dict["ioc_categories"] == []
        assert as_dict["ioc_breakdown_verified"] is False
        assert as_dict["correlation_evaluated"] is False
        assert as_dict["engine_reasons"] == []


# ==========================================================
# GetInvestigationRiskExplanationRequest
# ==========================================================


class TestGetInvestigationRiskExplanationRequest:
    def test_valid_id_accepted(self):
        request = GetInvestigationRiskExplanationRequest(investigation_id=1)
        assert request.investigation_id == 1

    def test_zero_rejected(self):
        with pytest.raises(CommandValidationError):
            GetInvestigationRiskExplanationRequest(investigation_id=0)

    def test_negative_rejected(self):
        with pytest.raises(CommandValidationError):
            GetInvestigationRiskExplanationRequest(investigation_id=-5)

    def test_non_int_rejected(self):
        with pytest.raises(CommandValidationError):
            GetInvestigationRiskExplanationRequest(investigation_id="1")  # type: ignore[arg-type]

    def test_bool_rejected(self):
        # bool is an int subclass in Python -- explicitly excluded,
        # mirroring GetInvestigationRequest/GetIocsRequest/
        # GetInvestigationProvenanceRequest.
        with pytest.raises(CommandValidationError):
            GetInvestigationRiskExplanationRequest(investigation_id=True)  # type: ignore[arg-type]


# ==========================================================
# GetInvestigationRiskExplanationCommandHandler
# ==========================================================


class TestGetInvestigationRiskExplanationCommand:
    @pytest.fixture()
    def repository(self, tmp_path):
        connection = DatabaseConnection(database_path=tmp_path / "test.db")
        repo = InvestigationRepository(database=connection)
        yield repo
        connection.close()

    def test_handler_returns_risk_explanation_shape(self, repository):
        investigation = make_investigation()
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationRiskExplanationCommandHandler(
            service=service,
            settings_service=_FakeSettingsService(),
        )

        response = handler.handle(
            GetInvestigationRiskExplanationRequest(investigation_id=investigation_id)
        )

        assert response["success"] is True
        data = response["data"]

        assert data["investigation_id"] == investigation_id
        assert data["report_name"] == "malware_report.txt"
        assert data["score"] == 17
        assert data["severity"] == "MEDIUM"
        assert data["confidence"] == 0.6
        assert data["ioc_score"] == 8
        # 2 ipv4 + 1 sha256 = 2 non-empty categories.
        assert len(data["ioc_categories"]) == 2
        assert data["ioc_breakdown_verified"] is True
        assert isinstance(data["narrative"], list) and len(data["narrative"]) > 0
        # Correlation is always evaluated by this handler (mirrors the
        # legacy GUI's own wiring -- see handler docstring).
        assert data["correlation_evaluated"] is True

    def test_handler_reflects_api_key_not_configured(self, repository):
        investigation = make_investigation(
            threat_intelligence={"status": "unavailable", "reason": "not_attempted"},
        )
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationRiskExplanationCommandHandler(
            service=service,
            settings_service=_FakeSettingsService(virustotal_api_key=""),
        )

        response = handler.handle(
            GetInvestigationRiskExplanationRequest(investigation_id=investigation_id)
        )

        data = response["data"]
        assert data["threat_intel_state"] in (
            "not_enriched",
            "no_api_key",
            "incomplete_check",
        )

    def test_handler_returns_not_found_for_missing_investigation(self, repository):
        service = InvestigationService(repository=repository)
        handler = GetInvestigationRiskExplanationCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationRiskExplanationRequest(investigation_id=999999)
        )

        assert response["success"] is False
        assert response["error"]["code"] == INVESTIGATION_NOT_FOUND

    def test_investigation_a_never_returns_investigation_bs_explanation(
        self, repository
    ):
        # Security/correctness requirement: cross-investigation isolation.
        investigation_a = make_investigation(
            report_name="report_a.txt",
            iocs={"ipv4": ["1.1.1.1"], "sha256": []},
            ioc_score=1,
            risk_score=5,
        )
        investigation_b = make_investigation(
            report_name="report_b.txt",
            iocs={"ipv4": [], "sha256": ["b" * 64]},
            ioc_score=6,
            risk_score=40,
        )
        id_a = repository.save(investigation_a)
        id_b = repository.save(investigation_b)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationRiskExplanationCommandHandler(
            service=service,
            settings_service=_FakeSettingsService(),
        )

        response_a = handler.handle(
            GetInvestigationRiskExplanationRequest(investigation_id=id_a)
        )
        response_b = handler.handle(
            GetInvestigationRiskExplanationRequest(investigation_id=id_b)
        )

        data_a = response_a["data"]
        data_b = response_b["data"]

        assert data_a["investigation_id"] == id_a
        assert data_b["investigation_id"] == id_b
        assert data_a["report_name"] == "report_a.txt"
        assert data_b["report_name"] == "report_b.txt"
        assert data_a["score"] == 5
        assert data_b["score"] == 40

        categories_a = {c["ioc_type"] for c in data_a["ioc_categories"]}
        categories_b = {c["ioc_type"] for c in data_b["ioc_categories"]}
        assert categories_a == {"ipv4"}
        assert categories_b == {"sha256"}

    def test_command_is_registered_in_command_handlers_table(self):
        assert "get_investigation_risk_explanation" in COMMAND_HANDLERS

    def test_dispatch_rejects_invalid_investigation_id(self):
        response = dispatch(
            "get_investigation_risk_explanation", {"investigation_id": -1}
        )

        assert response["success"] is False
        assert response["error"]["code"] == INVALID_COMMAND_PAYLOAD

    def test_dispatch_rejects_unexpected_payload_fields(self):
        response = dispatch(
            "get_investigation_risk_explanation",
            {"investigation_id": 1, "unexpected": True},
        )

        assert response["success"] is False
        assert response["error"]["code"] == INVALID_COMMAND_PAYLOAD


# ==========================================================
# API layer -- POST /commands/get_investigation_risk_explanation
# ==========================================================


class GetInvestigationRiskExplanationRouteTests(unittest.TestCase):
    """The existing generic `/commands/{name}` route (app/api/app.py)
    reaches the new handler through `COMMAND_HANDLERS` -- no new route
    was added. Only validation-only / not-found assertions are made
    here (mirroring tests/test_investigation_provenance_query.py's own
    stated constraint): this file does not control the contents of the
    real database, so it makes no assertion that depends on specific
    persisted data.
    """

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_validation_error_never_reaches_domain(self) -> None:
        response = self.client.post(
            "/commands/get_investigation_risk_explanation",
            json={"investigation_id": -1},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_not_found_is_translated_not_raised(self) -> None:
        response = self.client.post(
            "/commands/get_investigation_risk_explanation",
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

    def test_get_investigation_still_works(self, repository):
        investigation = make_investigation()
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationRequest(investigation_id=investigation_id)
        )

        assert response["success"] is True
        assert response["data"]["risk_score"] == 17

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

    def test_get_investigation_provenance_still_works(self, repository):
        investigation = make_investigation()
        investigation_id = repository.save(investigation)

        service = InvestigationService(repository=repository)
        handler = GetInvestigationProvenanceCommandHandler(service=service)

        response = handler.handle(
            GetInvestigationProvenanceRequest(investigation_id=investigation_id)
        )

        assert response["success"] is True
        assert len(response["data"]["ioc_provenance"]) == 3
