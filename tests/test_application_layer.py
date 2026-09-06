"""
Tests for the Phase 4D application/command-handler layer
(app/application/*).

Written with stdlib `unittest`, not pytest: this sandbox has no network
access and pytest is not pre-installed (see
docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S19). Run with:

    python -m unittest tests.test_application_layer -v

get_investigation / list_investigations are tested against a fully
isolated temp-file SQLite database (InvestigationService is injectable).
analyze_report is NOT injectable at the repository level (it constructs
its own InvestigationRepository() internally -- a confirmed, documented
gap, not something this phase's tests paper over), so that test instead
snapshots/restores the real database/soc_iq.db file around the call and
cleans up the investigation row it creates.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from app.application.dto import (
    AnalysisOptions,
    AnalyzeReportRequest,
    CommandValidationError,
    DeleteInvestigationRequest,
    EnrichIocRequest,
    ExportReportRequest,
    GetDashboardSummaryRequest,
    GetInvestigationAggregateSummaryRequest,
    GetInvestigationRequest,
    GetIocsRequest,
    GetSettingsRequest,
    GetThreatIntelligenceRequest,
    GetTimelineRequest,
    ListInvestigationsRequest,
    SaveSettingsRequest,
    SearchInvestigationsRequest,
)
from app.application.broker import EventBroker
from app.application.errors import (
    INVESTIGATION_NOT_FOUND,
    REPORT_NOT_FOUND,
    code_for_exception,
)
from app.application.handlers import (
    AnalyzeReportCommandHandler,
    DeleteInvestigationCommandHandler,
    EnrichIocCommandHandler,
    ExportReportCommandHandler,
    GetDashboardSummaryCommandHandler,
    GetInvestigationAggregateSummaryCommandHandler,
    GetInvestigationCommandHandler,
    GetIocsCommandHandler,
    GetSettingsCommandHandler,
    GetThreatIntelligenceCommandHandler,
    GetTimelineCommandHandler,
    ListInvestigationsCommandHandler,
    SaveSettingsCommandHandler,
    SearchInvestigationsCommandHandler,
    dispatch,
)
from app.config import DATABASE_PATH
from app.database.connection import DatabaseConnection
from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.database.service import InvestigationService
from app.exceptions import DatabaseError, DuplicateInvestigationError
from app.reporting.service import ReportingService
from app.settings.models import ApplicationSettings
from app.settings.repository import SettingsRepository
from app.settings.service import SettingsService
from app.timeline.domain import TimelineEvent, TimelineEventType
from app.timeline.repository import TimelineRepository
from tests.fixtures.fake_secret_store import FakeSecretStore
from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidHashError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
)
from app.threat_intel.service import ThreatIntelService


class _FakeVirusTotalClient:
    """Minimal fake VirusTotal client for EnrichIoc tests -- same
    dependency-injection pattern tests/test_threat_intel.py's
    FakeVirusTotalClient uses (`ThreatIntelService(virustotal=...)`),
    kept local and minimal since only the sha256 path is exercised
    here.
    """

    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.lookups: list[str] = []

    def lookup_sha256(self, sha256: str) -> dict:
        self.lookups.append(sha256)
        if self._error is not None:
            raise self._error
        return dict(self._response or {})


class _FakeSettingsService:
    """Minimal injectable stand-in for `SettingsService`, used by
    `GetThreatIntelligenceCommandHandler` tests that need to control
    `api_key_configured` deterministically rather than depending on
    whatever `SettingsRepository()` happens to find on disk.
    """

    def __init__(self, virustotal_api_key: str = "") -> None:
        self._settings = ApplicationSettings(virustotal_api_key=virustotal_api_key)

    def load_settings(self) -> ApplicationSettings:
        return self._settings


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="phase4d_test_report.txt",
        iocs={"ipv4": ["1.2.3.4"]},
        threat_intelligence={"status": "unavailable", "reason": "not_attempted"},
        risk_score=42,
        severity="MEDIUM",
        confidence=0.75,
        ioc_score=10,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return Investigation(**defaults)


class IsolatedServiceTestCase(unittest.TestCase):
    """Base class giving each test a temp-file-backed InvestigationService."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test_soc_iq.db"
        self.repository = InvestigationRepository(DatabaseConnection(self.db_path))
        self.service = InvestigationService(self.repository)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()


class GetInvestigationCommandHandlerTests(IsolatedServiceTestCase):
    def test_returns_summary_for_existing_investigation(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = GetInvestigationCommandHandler(self.service)

        response = handler.handle(GetInvestigationRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        self.assertEqual(response["data"]["report_name"], "phase4d_test_report.txt")
        self.assertEqual(response["data"]["risk_score"], 42)
        # Nested domain fields must NOT leak into the summary DTO.
        self.assertNotIn("iocs", response["data"])
        self.assertNotIn("threat_intelligence", response["data"])
        # Phase 4J-6: `correlations` is additive and always present.
        self.assertIn("correlations", response["data"])

    def test_returns_not_found_error_for_missing_investigation(self) -> None:
        handler = GetInvestigationCommandHandler(self.service)

        response = handler.handle(GetInvestigationRequest(999999))

        self.assertFalse(response["success"])
        self.assertIsNone(response["data"])
        self.assertEqual(response["error"]["code"], INVESTIGATION_NOT_FOUND)

    def test_request_dto_rejects_non_positive_id(self) -> None:
        with self.assertRaises(CommandValidationError):
            GetInvestigationRequest(0)
        with self.assertRaises(CommandValidationError):
            GetInvestigationRequest(-5)

    def test_returns_real_correlations_for_genuinely_correlated_evidence(self) -> None:
        """Phase 4J-6: exercises the real
        GetInvestigationCommandHandler -> CorrelationService ->
        InvestigationCorrelationDTO path end to end -- not
        CorrelationService directly (see tests/test_correlation_service.py
        for the service's own unit coverage; this is the integration
        assertion the wiring itself needs)."""

        investigation_id = self.service.save(
            make_investigation(
                iocs={
                    "domains": ["evil.com"],
                    "urls": ["https://evil.com/payload.exe"],
                },
            )
        )
        handler = GetInvestigationCommandHandler(self.service)

        response = handler.handle(GetInvestigationRequest(investigation_id))

        self.assertTrue(response["success"])
        correlations = response["data"]["correlations"]
        self.assertEqual(len(correlations), 1)
        self.assertEqual(correlations[0]["relationship_type"], "domain_url_host")
        self.assertEqual(correlations[0]["source"], "evil.com")
        self.assertEqual(correlations[0]["target"], "https://evil.com/payload.exe")
        self.assertTrue(correlations[0]["context"])

    def test_returns_empty_correlations_when_no_explicit_relationship_exists(self) -> None:
        investigation_id = self.service.save(
            make_investigation(iocs={"ipv4": ["1.2.3.4"]})
        )
        handler = GetInvestigationCommandHandler(self.service)

        response = handler.handle(GetInvestigationRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["correlations"], [])


class GetIocsCommandHandlerTests(IsolatedServiceTestCase):
    def test_returns_iocs_for_existing_investigation(self) -> None:
        investigation_id = self.service.save(
            make_investigation(iocs={"ipv4": ["1.2.3.4"], "domains": ["evil.example"]})
        )
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        self.assertEqual(
            response["data"]["iocs"],
            {"ipv4": ["1.2.3.4"], "domains": ["evil.example"]},
        )

    def test_returns_not_found_error_for_missing_investigation(self) -> None:
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(999999))

        self.assertFalse(response["success"])
        self.assertIsNone(response["data"])
        self.assertEqual(response["error"]["code"], INVESTIGATION_NOT_FOUND)

    def test_request_dto_rejects_non_positive_id(self) -> None:
        with self.assertRaises(CommandValidationError):
            GetIocsRequest(0)
        with self.assertRaises(CommandValidationError):
            GetIocsRequest(-5)

    # PD-08-P3: `significance` per IOC category present on the
    # investigation, derived from `app.services.ioc_significance`'s
    # existing pure functions (already covered function-by-function in
    # `tests/test_ioc_detail_context.py`) -- these tests cover this
    # handler's own integration of that module, not the banding logic
    # itself again.

    def test_significance_uses_the_authoritative_weight_and_label_for_each_present_type(
        self,
    ) -> None:
        investigation_id = self.service.save(
            make_investigation(iocs={"ipv4": ["1.2.3.4"], "sha256": ["a" * 64]})
        )
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(investigation_id))

        self.assertEqual(
            response["data"]["significance"],
            {
                "ipv4": {"weight": 1, "significance": "Low"},
                "sha256": {"weight": 6, "significance": "High"},
            },
        )

    def test_significance_covers_every_present_category_with_no_cross_contamination(
        self,
    ) -> None:
        investigation_id = self.service.save(
            make_investigation(
                iocs={
                    "ipv4": ["1.2.3.4"],
                    "domains": ["evil.example"],
                    "urls": ["http://evil.example/x"],
                    "cves": ["CVE-2024-0001"],
                }
            )
        )
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(investigation_id))
        significance = response["data"]["significance"]

        self.assertEqual(set(significance.keys()), {"ipv4", "domains", "urls", "cves"})
        # Each category's own weight/label, not a copy of another
        # category's or the first category's value.
        self.assertEqual(significance["ipv4"], {"weight": 1, "significance": "Low"})
        self.assertEqual(significance["domains"], {"weight": 2, "significance": "Low"})
        self.assertEqual(significance["urls"], {"weight": 3, "significance": "Medium"})
        self.assertEqual(significance["cves"], {"weight": 8, "significance": "High"})

    def test_significance_omits_categories_the_investigation_has_no_iocs_of(self) -> None:
        investigation_id = self.service.save(
            make_investigation(iocs={"ipv4": ["1.2.3.4"]})
        )
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(investigation_id))

        # Only the one real category this investigation actually has --
        # never a fabricated entry for the other nine known categories,
        # and never the entire IOC_WEIGHTS table.
        self.assertEqual(list(response["data"]["significance"].keys()), ["ipv4"])

    def test_significance_is_empty_but_present_for_an_investigation_with_no_iocs(
        self,
    ) -> None:
        investigation_id = self.service.save(make_investigation(iocs={}))
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(investigation_id))

        self.assertEqual(response["data"]["iocs"], {})
        self.assertEqual(response["data"]["significance"], {})

    def test_significance_falls_back_to_the_established_informational_label_for_an_unweighted_type(
        self,
    ) -> None:
        # `IOC_WEIGHTS` covers all ten real persisted categories today,
        # so this only exercises the defensive fallback path -- same
        # one `ioc_type_significance()`/`ioc_type_weight()` have always
        # used (`tests/test_ioc_detail_context.py::
        # test_significance_banding_unknown_type_is_informational`),
        # not a new fallback invented at this layer.
        investigation_id = self.service.save(
            make_investigation(iocs={"some_future_category": ["x"]})
        )
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(investigation_id))

        self.assertEqual(
            response["data"]["significance"]["some_future_category"],
            {"weight": 0, "significance": "Informational"},
        )

    def test_significance_never_appears_in_a_not_found_response(self) -> None:
        handler = GetIocsCommandHandler(self.service)

        response = handler.handle(GetIocsRequest(999999))

        self.assertIsNone(response["data"])


class GetTimelineCommandHandlerTests(IsolatedServiceTestCase):
    """A4-P2-P3 Part 3: `get_timeline` application-layer tests.

    Uses the same isolated temp-file SQLite database as every other
    handler test in this class (`IsolatedServiceTestCase`) --
    `TimelineRepository` is pointed at that same `self.db_path` so
    `InvestigationService.save()` and `TimelineRepository.append()`
    operate against the same on-disk database, exactly like
    production (`InvestigationService()`/`TimelineRepository()`'s own
    default constructors both resolve to `app.config.DATABASE_PATH`).
    """

    def setUp(self) -> None:
        super().setUp()
        self.timeline_repository = TimelineRepository(DatabaseConnection(self.db_path))

    def test_returns_events_oldest_to_newest_for_existing_investigation(self) -> None:
        investigation_id = self.service.save(make_investigation())

        first = TimelineEvent(
            investigation_id=investigation_id,
            event_type=TimelineEventType.INVESTIGATION_CREATED,
            summary="Investigation created.",
        )
        second = TimelineEvent(
            investigation_id=investigation_id,
            event_type=TimelineEventType.ANALYSIS_COMPLETED,
            summary="Analysis completed.",
            metadata={"ioc_count": 3},
        )
        self.timeline_repository.append(first)
        self.timeline_repository.append(second)

        handler = GetTimelineCommandHandler(self.service, self.timeline_repository)
        response = handler.handle(GetTimelineRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        events = response["data"]["events"]
        self.assertEqual(len(events), 2)
        # Deterministic oldest -> newest ordering, per
        # TimelineRepository.list_for_investigation's own contract --
        # not re-sorted or reversed by the handler.
        self.assertEqual(events[0]["event_id"], first.event_id)
        self.assertEqual(events[0]["event_type"], "investigation.created")
        self.assertEqual(events[1]["event_id"], second.event_id)
        self.assertEqual(events[1]["event_type"], "analysis.completed")
        self.assertEqual(events[1]["metadata"], {"ioc_count": 3})
        # semantics is the controlled vocabulary's documented meaning,
        # not an empty/omitted field.
        self.assertTrue(events[1]["semantics"])
        # Internal database/repository objects must never leak into the
        # response DTO.
        self.assertNotIn("row", events[0])
        self.assertNotIn("connection", events[0])

    def test_returns_valid_empty_result_for_investigation_with_no_events(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = GetTimelineCommandHandler(self.service, self.timeline_repository)

        response = handler.handle(GetTimelineRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        self.assertEqual(response["data"]["events"], [])

    def test_returns_not_found_error_for_missing_investigation(self) -> None:
        handler = GetTimelineCommandHandler(self.service, self.timeline_repository)

        response = handler.handle(GetTimelineRequest(999999))

        self.assertFalse(response["success"])
        self.assertIsNone(response["data"])
        self.assertEqual(response["error"]["code"], INVESTIGATION_NOT_FOUND)

    def test_request_dto_rejects_non_positive_id(self) -> None:
        with self.assertRaises(CommandValidationError):
            GetTimelineRequest(0)
        with self.assertRaises(CommandValidationError):
            GetTimelineRequest(-5)

    def test_investigation_isolation_never_returns_another_investigations_events(
        self,
    ) -> None:
        """Critical security boundary (per the Part 3 brief): a request
        for investigation A's timeline must never include investigation
        B's events, and must never fetch a global/unfiltered timeline
        and filter client-side -- the query itself is always scoped to
        the requested investigation_id."""

        investigation_a = self.service.save(make_investigation(report_name="a.txt"))
        investigation_b = self.service.save(make_investigation(report_name="b.txt"))

        self.timeline_repository.append(
            TimelineEvent(
                investigation_id=investigation_a,
                event_type=TimelineEventType.INVESTIGATION_CREATED,
                summary="Investigation A created.",
            )
        )
        self.timeline_repository.append(
            TimelineEvent(
                investigation_id=investigation_b,
                event_type=TimelineEventType.INVESTIGATION_CREATED,
                summary="Investigation B created.",
            )
        )
        self.timeline_repository.append(
            TimelineEvent(
                investigation_id=investigation_b,
                event_type=TimelineEventType.ANALYSIS_COMPLETED,
                summary="Investigation B analysis completed.",
            )
        )

        handler = GetTimelineCommandHandler(self.service, self.timeline_repository)

        response_a = handler.handle(GetTimelineRequest(investigation_a))
        response_b = handler.handle(GetTimelineRequest(investigation_b))

        self.assertEqual(len(response_a["data"]["events"]), 1)
        self.assertEqual(
            response_a["data"]["events"][0]["summary"], "Investigation A created."
        )
        self.assertTrue(
            all(
                event["investigation_id"] == investigation_a
                for event in response_a["data"]["events"]
            )
        )

        self.assertEqual(len(response_b["data"]["events"]), 2)
        self.assertTrue(
            all(
                event["investigation_id"] == investigation_b
                for event in response_b["data"]["events"]
            )
        )

    def test_malformed_persisted_metadata_is_not_converted_into_plausible_data(
        self,
    ) -> None:
        """Part 2's `_row_to_event` re-raises `ValueError`/`TypeError`
        for an undecodable persisted row rather than fabricating a
        plausible-looking event; this handler must not paper over that
        by catching and substituting anything in its place -- the
        failure must still surface as a translated application error
        (never a fake 200 with invented data)."""

        investigation_id = self.service.save(make_investigation())
        self.timeline_repository.append(
            TimelineEvent(
                investigation_id=investigation_id,
                event_type=TimelineEventType.INVESTIGATION_CREATED,
                summary="Investigation created.",
            )
        )

        # Directly corrupt the persisted metadata JSON, bypassing domain
        # validation entirely -- simulating on-disk corruption/a bug
        # elsewhere, which is exactly the scenario Part 2's safe-failure
        # behavior exists for.
        with DatabaseConnection(self.db_path) as connection:
            connection.execute(
                "UPDATE timeline_events SET metadata = ? WHERE investigation_id = ?",
                ("{not valid json", investigation_id),
            )
            connection.commit()

        handler = GetTimelineCommandHandler(self.service, self.timeline_repository)

        with self.assertRaises((ValueError, TypeError)):
            handler.handle(GetTimelineRequest(investigation_id))

    def test_dispatched_via_command_name(self) -> None:
        investigation_id = self.service.save(make_investigation())
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch("get_iocs", {"investigation_id": investigation_id})

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)


class GetThreatIntelligenceCommandHandlerTests(IsolatedServiceTestCase):
    def test_returns_threat_intelligence_for_existing_investigation(self) -> None:
        ti_payload = {
            "status": "ok",
            "coverage": {"requested": 1, "succeeded": 1},
            "hashes": [],
            "ips": [{"ip": "1.2.3.4", "verdict": "Malicious"}],
            "domains": [],
            "urls": [],
        }
        investigation_id = self.service.save(
            make_investigation(threat_intelligence=ti_payload)
        )
        handler = GetThreatIntelligenceCommandHandler(self.service)

        response = handler.handle(GetThreatIntelligenceRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        # Existing raw payload must remain present and unchanged (backward
        # compatibility for existing consumers).
        self.assertEqual(response["data"]["threat_intelligence"], ti_payload)

    def test_returns_not_found_error_for_missing_investigation(self) -> None:
        handler = GetThreatIntelligenceCommandHandler(self.service)

        response = handler.handle(GetThreatIntelligenceRequest(999999))

        self.assertFalse(response["success"])
        self.assertIsNone(response["data"])
        self.assertEqual(response["error"]["code"], INVESTIGATION_NOT_FOUND)

    def test_request_dto_rejects_non_positive_id(self) -> None:
        with self.assertRaises(CommandValidationError):
            GetThreatIntelligenceRequest(0)
        with self.assertRaises(CommandValidationError):
            GetThreatIntelligenceRequest(-5)

    def test_dispatched_via_command_name(self) -> None:
        investigation_id = self.service.save(make_investigation())
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch(
                "get_threat_intelligence", {"investigation_id": investigation_id}
            )

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)

    def test_states_present_and_enriched_for_indicator_with_a_record(self) -> None:
        ti_payload = {
            "status": "ok",
            "coverage": {"requested": 1, "succeeded": 1},
            "hashes": [],
            "ips": [{"ip": "1.2.3.4", "verdict": "Malicious"}],
            "domains": [],
            "urls": [],
        }
        investigation_id = self.service.save(
            make_investigation(
                iocs={"ipv4": ["1.2.3.4"]},
                threat_intelligence=ti_payload,
            )
        )
        handler = GetThreatIntelligenceCommandHandler(
            self.service,
            settings_service=_FakeSettingsService(virustotal_api_key="a-key"),
        )

        response = handler.handle(GetThreatIntelligenceRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertEqual(
            response["data"]["states"],
            {"ipv4": {"1.2.3.4": "enriched"}},
        )
        # Raw payload is still present, unmodified, alongside the projection.
        self.assertEqual(response["data"]["threat_intelligence"], ti_payload)

    def test_states_reflects_multiple_ioc_types_and_unsupported_type(self) -> None:
        ti_payload = {
            "status": "partial",
            "coverage": {"requested": 2, "succeeded": 1},
            "hashes": [{"sha256": "aaa111", "verdict": "Clean"}],
            "ips": [],
            "domains": [],
            "urls": [],
        }
        investigation_id = self.service.save(
            make_investigation(
                iocs={
                    "sha256": ["aaa111", "bbb222"],
                    "emails": ["a@example.com"],
                },
                threat_intelligence=ti_payload,
            )
        )
        handler = GetThreatIntelligenceCommandHandler(
            self.service,
            settings_service=_FakeSettingsService(virustotal_api_key="a-key"),
        )

        response = handler.handle(GetThreatIntelligenceRequest(investigation_id))

        self.assertEqual(
            response["data"]["states"],
            {
                "sha256": {
                    "aaa111": "enriched",
                    "bbb222": "incomplete_check",
                },
                "emails": {"a@example.com": "unsupported_type"},
            },
        )

    def test_states_reflects_no_api_key_configured(self) -> None:
        investigation_id = self.service.save(
            make_investigation(
                iocs={"ipv4": ["1.2.3.4"]},
                threat_intelligence={
                    "status": "ok",
                    "coverage": {"requested": 1, "succeeded": 1},
                    "ips": [{"ip": "1.2.3.4", "verdict": "Clean"}],
                },
            )
        )
        handler = GetThreatIntelligenceCommandHandler(
            self.service,
            settings_service=_FakeSettingsService(virustotal_api_key=""),
        )

        response = handler.handle(GetThreatIntelligenceRequest(investigation_id))

        self.assertEqual(
            response["data"]["states"],
            {"ipv4": {"1.2.3.4": "no_api_key"}},
        )

    def test_states_empty_dict_when_no_iocs_recorded(self) -> None:
        investigation_id = self.service.save(make_investigation(iocs={}))
        handler = GetThreatIntelligenceCommandHandler(
            self.service,
            settings_service=_FakeSettingsService(virustotal_api_key="a-key"),
        )

        response = handler.handle(GetThreatIntelligenceRequest(investigation_id))

        self.assertEqual(response["data"]["states"], {})

    def test_handlers_module_has_no_app_gui_import(self) -> None:
        """
        Static/import-time architecture gate for Phase 4J-2: importing
        `app.application.handlers` (which now imports
        `app.services.threat_intel_state` for the new `states`
        projection) must not reach into `app.gui` or PySide6, exactly
        like `app.services.threat_intel_state` itself already
        guarantees (see tests/test_threat_intel_state.py).
        """
        probe = (
            "import sys\n"
            "class _Blocker:\n"
            "    def find_module(self, name, path=None):\n"
            "        if name == 'app.gui' or name.startswith('app.gui.'):\n"
            "            raise ImportError(f'blocked: {name}')\n"
            "        if name == 'PySide6' or name.startswith('PySide6.'):\n"
            "            raise ImportError(f'blocked: {name}')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _Blocker())\n"
            "import app.application.handlers\n"
            "print('OK')\n"
        )
        import subprocess
        import sys as _sys

        completed = subprocess.run(
            [_sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("OK", completed.stdout)


class ExportReportCommandHandlerTests(IsolatedServiceTestCase):
    """Phase 4D Part 6: the export_report vertical slice."""

    def setUp(self) -> None:
        super().setUp()
        self._export_tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._export_tmpdir.cleanup()
        super().tearDown()

    def _output_path(self, filename: str) -> Path:
        return Path(self._export_tmpdir.name) / filename

    def test_exports_json_for_existing_investigation(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        output_path = self._output_path("report.json")

        response = handler.handle(
            ExportReportRequest(investigation_id, "json", str(output_path))
        )

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        self.assertEqual(response["data"]["export_format"], "json")
        self.assertEqual(response["data"]["output_path"], str(output_path))
        self.assertTrue(output_path.exists())

    def test_exports_markdown_for_existing_investigation(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        output_path = self._output_path("report.md")

        response = handler.handle(
            ExportReportRequest(investigation_id, "markdown", str(output_path))
        )

        self.assertTrue(response["success"])
        self.assertTrue(output_path.exists())

    def test_exports_html_for_existing_investigation(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        output_path = self._output_path("report.html")

        response = handler.handle(
            ExportReportRequest(investigation_id, "html", str(output_path))
        )

        self.assertTrue(response["success"])
        self.assertTrue(output_path.exists())

    def test_exports_pdf_for_existing_investigation(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        output_path = self._output_path("report.pdf")

        response = handler.handle(
            ExportReportRequest(investigation_id, "pdf", str(output_path))
        )

        self.assertTrue(response["success"])
        self.assertTrue(output_path.exists())

    def test_returns_not_found_error_for_missing_investigation(self) -> None:
        handler = ExportReportCommandHandler(self.service, ReportingService())

        response = handler.handle(
            ExportReportRequest(999999, "json", str(self._output_path("x.json")))
        )

        self.assertFalse(response["success"])
        self.assertIsNone(response["data"])
        self.assertEqual(response["error"]["code"], INVESTIGATION_NOT_FOUND)

    def test_successful_export_records_report_exported_timeline_event(self) -> None:
        """A4-P2-P3 Part 4: a successful export appends a
        `report.exported` TimelineEvent to the exported investigation's
        timeline, scoped to this handler's own (isolated, temp-file)
        database -- never the process-default one."""

        from app.timeline.domain import TimelineEventType
        from app.timeline.repository import TimelineRepository

        investigation_id = self.service.save(make_investigation())
        timeline_repository = TimelineRepository(DatabaseConnection(self.db_path))
        handler = ExportReportCommandHandler(
            self.service, ReportingService(), timeline_repository
        )
        output_path = self._output_path("report.json")

        response = handler.handle(
            ExportReportRequest(investigation_id, "json", str(output_path))
        )
        self.assertTrue(response["success"])

        events = timeline_repository.list_for_investigation(investigation_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, TimelineEventType.REPORT_EXPORTED)
        self.assertEqual(events[0].metadata.get("export_format"), "json")

    def test_failed_export_records_no_timeline_event(self) -> None:
        from app.timeline.repository import TimelineRepository

        timeline_repository = TimelineRepository(DatabaseConnection(self.db_path))
        handler = ExportReportCommandHandler(
            self.service, ReportingService(), timeline_repository
        )

        response = handler.handle(
            ExportReportRequest(999999, "json", str(self._output_path("x.json")))
        )
        self.assertFalse(response["success"])

        # No investigation with id 999999 exists in this isolated db,
        # so list_for_investigation legitimately returns empty -- the
        # assertion that matters is that append() was never reached.
        events = timeline_repository.list_for_investigation(999999)
        self.assertEqual(events, [])

    def test_timeline_append_failure_does_not_fail_export(self) -> None:
        """A4-P2-P3 Part 7: the inline comment above this handler's own
        timeline-append try/except claims "a failure here must never
        fail an already-succeeded export -- same convention as
        AnalyzeReportCommandHandler's _record_timeline_event." Never
        exercised by any test -- this handler's `timeline_repository`
        constructor parameter exists specifically to allow substituting
        a failing double for exactly this proof."""

        investigation_id = self.service.save(make_investigation())
        failing_timeline_repository = unittest.mock.Mock()
        failing_timeline_repository.append.side_effect = RuntimeError(
            "simulated timeline append failure"
        )
        handler = ExportReportCommandHandler(
            self.service, ReportingService(), failing_timeline_repository
        )
        output_path = self._output_path("report.json")

        response = handler.handle(
            ExportReportRequest(investigation_id, "json", str(output_path))
        )

        # The export itself must still succeed and the file must still
        # be written -- the export already completed before the
        # timeline append was attempted.
        self.assertTrue(response["success"], msg=response.get("error"))
        self.assertTrue(output_path.exists())
        failing_timeline_repository.append.assert_called_once()

    def test_not_found_error_is_returned_before_any_export_is_attempted(self) -> None:
        # A missing investigation must short-circuit before ReportingService
        # is ever called -- proven by pointing output_path at a directory
        # that does not exist and asserting no error about that directory
        # surfaces (only INVESTIGATION_NOT_FOUND does).
        handler = ExportReportCommandHandler(self.service, ReportingService())
        bogus_path = Path(self._export_tmpdir.name) / "does" / "not" / "exist" / "x.json"

        response = handler.handle(
            ExportReportRequest(999999, "json", str(bogus_path))
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], INVESTIGATION_NOT_FOUND)
        self.assertFalse(bogus_path.exists())

    def test_request_dto_rejects_non_positive_id(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(0, "json", "out.json")
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(-5, "json", "out.json")

    def test_request_dto_rejects_unsupported_format(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "csv", "out.csv")
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "xml", "out.xml")

    def test_request_dto_rejects_blank_output_path(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "")
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "   ")

    # -- §20 export path-traversal security regression -------------------
    #
    # The only legitimate source of `output_path` is the native OS save
    # dialog (frontend/src/pages/reports/reportExportPath.ts), which always
    # returns an already-absolute, user-chosen destination -- never a bare
    # filename or a relative fragment. Every exporter
    # (app/reporting/*_exporter.py) does
    # `output_path.parent.mkdir(parents=True, exist_ok=True)` and then
    # writes `output_path` directly with no validation of its own, so the
    # DTO boundary is where a relative/traversal `output_path` (which a
    # legitimate caller can never produce) must be rejected -- see
    # docs/security/filesystem-security-model.md TARGET STATE.

    def test_request_dto_rejects_bare_relative_filename(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "report.json")

    def test_request_dto_rejects_relative_subdirectory_path(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "reports/report.json")

    def test_request_dto_rejects_parent_traversal(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "../report.json")
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "../../outside.json")

    def test_request_dto_rejects_windows_style_parent_traversal(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "..\\report.json")
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "..\\..\\report.json")

    def test_request_dto_rejects_nested_relative_traversal(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", "reports/../../outside.json")

    def test_request_dto_accepts_absolute_output_path(self) -> None:
        # Legitimate shape (what the native save dialog always returns)
        # must keep working -- this control is "require absolute", not
        # "reject everything".
        output_path = self._output_path("report.json")
        request = ExportReportRequest(1, "json", str(output_path))
        self.assertEqual(request.output_path, str(output_path))

    def test_traversal_attempt_creates_no_file_anywhere(self) -> None:
        # Proves the actual filesystem outcome, not just that a string
        # check fires: every malicious payload must be rejected before
        # ExportReportCommandHandler / ReportingService / ExportManager
        # ever runs, so no file is created -- not in the temp export
        # root, and not at the traversal target itself.
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        root = Path(self._export_tmpdir.name)
        traversal_target = root.parent / "outside.json"
        self.assertFalse(traversal_target.exists())

        malicious_payloads = [
            "report.json",
            "reports/report.json",
            "../report.json",
            "../../outside.json",
            "..\\report.json",
            "..\\..\\report.json",
            "reports/../../outside.json",
        ]

        for payload in malicious_payloads:
            with self.assertRaises(CommandValidationError):
                ExportReportRequest(investigation_id, "json", payload)

        # Nothing was ever handed to the handler (construction itself
        # failed), so nothing exists anywhere in or around the temp root.
        self.assertFalse(traversal_target.exists())
        self.assertEqual(list(root.iterdir()), [])

    def test_dispatched_via_command_name(self) -> None:
        investigation_id = self.service.save(make_investigation())
        output_path = self._output_path("dispatched.json")
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch(
                "export_report",
                {
                    "investigation_id": investigation_id,
                    "export_format": "json",
                    "output_path": str(output_path),
                },
            )

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        self.assertTrue(output_path.exists())


class GetSettingsCommandHandlerTests(unittest.TestCase):
    """SOC-IQ Part 2A: the get_settings backend read contract."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        settings_path = Path(self._tmpdir.name) / "settings.json"
        self.secret_store = FakeSecretStore()
        self.repository = SettingsRepository(
            settings_path=settings_path,
            secret_store=self.secret_store,
        )
        self.service = SettingsService(self.repository)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_returns_persisted_theme_and_export_directory(self) -> None:
        self.service.update_theme("Light Mode")
        target = str(Path(self._tmpdir.name) / "exports")
        self.service.update_export_directory(target)
        handler = GetSettingsCommandHandler(self.service)

        response = handler.handle(GetSettingsRequest())

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["theme"], "Light Mode")
        self.assertEqual(response["data"]["export_directory"], target)

    def test_reports_credential_configured_true_when_key_set(self) -> None:
        self.service.update_api_key("my-key")
        handler = GetSettingsCommandHandler(self.service)

        response = handler.handle(GetSettingsRequest())

        self.assertTrue(response["data"]["virustotal_api_key_configured"])

    def test_reports_credential_configured_false_when_key_unset(self) -> None:
        handler = GetSettingsCommandHandler(self.service)

        response = handler.handle(GetSettingsRequest())

        self.assertFalse(response["data"]["virustotal_api_key_configured"])

    def test_raw_api_key_never_present_in_response(self) -> None:
        self.service.update_api_key("super-secret-value")
        handler = GetSettingsCommandHandler(self.service)

        response = handler.handle(GetSettingsRequest())

        self.assertNotIn("virustotal_api_key", response["data"])
        self.assertNotIn("super-secret-value", str(response))

    def test_response_data_keys_are_exactly_the_safe_subset(self) -> None:
        handler = GetSettingsCommandHandler(self.service)

        response = handler.handle(GetSettingsRequest())

        self.assertEqual(
            set(response["data"].keys()),
            {"theme", "export_directory", "virustotal_api_key_configured"},
        )

    def test_dispatched_via_command_name(self) -> None:
        with patch(
            "app.application.handlers.SettingsService",
            return_value=self.service,
        ):
            response = dispatch("get_settings", {})

        self.assertTrue(response["success"])
        self.assertIn("theme", response["data"])
        self.assertIn("export_directory", response["data"])
        self.assertIn("virustotal_api_key_configured", response["data"])


class SaveSettingsCommandHandlerTests(unittest.TestCase):
    """Phase 4D Part 5: the save_settings vertical slice."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        settings_path = Path(self._tmpdir.name) / "settings.json"
        # Injects a deterministic in-memory SecretStore rather than the
        # real OS-backed default (Phase 4M Part 2B) -- the API key no
        # longer lives in settings.json, so these tests need a
        # SecretStore collaborator that doesn't depend on an OS
        # credential store being available in CI/sandbox environments.
        self.repository = SettingsRepository(
            settings_path=settings_path,
            secret_store=FakeSecretStore(),
        )
        self.service = SettingsService(self.repository)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_request_dto_rejects_api_key(self) -> None:
        """MAX19A-F-01: `virustotal_api_key` is no longer a live branch
        of this handler -- the DTO rejects it outright, before
        construction ever succeeds, with a `CommandValidationError`
        pointing callers at `keystore_set_secret` (the real, live
        Rust-owned credential write path) rather than letting the
        request reach `SettingsService`/the read-only production
        secret store at all. Supersedes the old `test_updates_api_key`,
        which asserted this call used to *succeed* against an injected
        fake store -- that was never true against the real production
        `RustKeystoreHandoffSecretStore` (see
        SecretLeakageHTTPRegressionTests in test_integration_e2e.py),
        and this DTO-level rejection is the fix.
        """
        with self.assertRaises(CommandValidationError) as ctx:
            SaveSettingsRequest(virustotal_api_key="my-key")

        self.assertIn("keystore_set_secret", str(ctx.exception))

    def test_updates_export_directory(self) -> None:
        handler = SaveSettingsCommandHandler(self.service)
        target = str(Path(self._tmpdir.name) / "exports")

        response = handler.handle(SaveSettingsRequest(export_directory=target))

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], {"field": "export_directory", "updated": True})
        self.assertEqual(self.service.load_settings().export_directory, target)

    def test_updates_theme(self) -> None:
        handler = SaveSettingsCommandHandler(self.service)

        response = handler.handle(SaveSettingsRequest(theme="Light Mode"))

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], {"field": "theme", "updated": True})
        self.assertEqual(self.service.load_settings().theme, "Light Mode")

    def test_updating_one_field_does_not_clobber_others(self) -> None:
        handler = SaveSettingsCommandHandler(self.service)
        target = str(Path(self._tmpdir.name) / "exports")

        handler.handle(SaveSettingsRequest(export_directory=target))
        handler.handle(SaveSettingsRequest(theme="Light Mode"))

        reloaded = self.service.load_settings()
        self.assertEqual(reloaded.export_directory, target)
        self.assertEqual(reloaded.theme, "Light Mode")

    def test_request_dto_rejects_no_field_provided(self) -> None:
        with self.assertRaises(CommandValidationError):
            SaveSettingsRequest()

    def test_request_dto_rejects_more_than_one_field_provided(self) -> None:
        with self.assertRaises(CommandValidationError):
            SaveSettingsRequest(export_directory="x", theme="Light Mode")

    def test_request_dto_rejects_api_key_even_with_another_field_set(self) -> None:
        # virustotal_api_key is rejected before the "exactly one field"
        # check ever runs, regardless of what else is set alongside it.
        with self.assertRaises(CommandValidationError) as ctx:
            SaveSettingsRequest(virustotal_api_key="a", theme="Light Mode")

        self.assertIn("keystore_set_secret", str(ctx.exception))

    def test_request_dto_rejects_non_string_value(self) -> None:
        with self.assertRaises(CommandValidationError):
            SaveSettingsRequest(theme=123)

    def test_dispatched_via_command_name(self) -> None:
        with patch(
            "app.application.handlers.SettingsService",
            return_value=self.service,
        ):
            response = dispatch("save_settings", {"theme": "Light Mode"})

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], {"field": "theme", "updated": True})
        self.assertEqual(self.service.load_settings().theme, "Light Mode")

    def test_dispatched_api_key_payload_is_rejected_as_invalid_payload(self) -> None:
        """MAX19A-F-01, via the same `dispatch()` seam
        `app/api/app.py`'s HTTP route calls -- proves the rejection
        holds at the dispatch layer the frontend/HTTP transport
        actually goes through, not only when constructing the DTO
        directly in-process (the test above this one)."""
        with patch(
            "app.application.handlers.SettingsService",
            return_value=self.service,
        ):
            response = dispatch("save_settings", {"virustotal_api_key": "my-key"})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INVALID_COMMAND_PAYLOAD")
        self.assertIn("keystore_set_secret", response["error"]["message"])
        # Never even reaches SettingsService -- confirmed by the store
        # never having been touched, unlike the old always-fails path.
        self.assertEqual(self.service.load_settings().virustotal_api_key, "")


class ListInvestigationsCommandHandlerTests(IsolatedServiceTestCase):
    def test_returns_all_investigations_as_summaries(self) -> None:
        self.service.save(make_investigation(report_name="a.txt"))
        self.service.save(make_investigation(report_name="b.txt"))
        handler = ListInvestigationsCommandHandler(self.service)

        response = handler.handle(ListInvestigationsRequest())

        self.assertTrue(response["success"])
        report_names = {item["report_name"] for item in response["data"]}
        self.assertEqual(report_names, {"a.txt", "b.txt"})

    def test_returns_empty_list_when_no_investigations(self) -> None:
        handler = ListInvestigationsCommandHandler(self.service)

        response = handler.handle(ListInvestigationsRequest())

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], [])


class GetDashboardSummaryCommandHandlerTests(IsolatedServiceTestCase):
    """Phase 4H Part 1: the get_dashboard_summary aggregate command."""

    def test_returns_zeroed_summary_for_empty_database(self) -> None:
        handler = GetDashboardSummaryCommandHandler(self.service)

        response = handler.handle(GetDashboardSummaryRequest())

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        data = response["data"]
        self.assertEqual(
            data["metrics"],
            {
                "total_reports": 0,
                "total_iocs": 0,
                "high_risk_count": 0,
                "threat_intel_coverage_percent": None,
            },
        )
        self.assertEqual(data["investigation_status_counts"], {})
        self.assertEqual(data["risk_distribution"], {})
        self.assertEqual(data["ioc_distribution"], {})
        self.assertEqual(data["recent_investigations"], [])

    def test_aggregates_metrics_across_investigations(self) -> None:
        self.service.save(
            make_investigation(
                report_name="a.txt",
                iocs={"ipv4": ["1.1.1.1", "2.2.2.2"]},
                severity="LOW",
                threat_intelligence={"coverage": {"requested": 2, "succeeded": 2}},
            )
        )
        self.service.save(
            make_investigation(
                report_name="b.txt",
                iocs={"domains": ["evil.example"]},
                severity="CRITICAL",
                threat_intelligence={"coverage": {"requested": 1, "succeeded": 0}},
            )
        )
        handler = GetDashboardSummaryCommandHandler(self.service)

        response = handler.handle(GetDashboardSummaryRequest())

        self.assertTrue(response["success"])
        data = response["data"]
        self.assertEqual(data["metrics"]["total_reports"], 2)
        self.assertEqual(data["metrics"]["total_iocs"], 3)
        self.assertEqual(data["metrics"]["high_risk_count"], 1)
        # (2 + 0) succeeded / (2 + 1) requested * 100 = 66.7
        self.assertEqual(data["metrics"]["threat_intel_coverage_percent"], 66.7)
        self.assertEqual(data["risk_distribution"], {"LOW": 1, "CRITICAL": 1})
        self.assertEqual(data["ioc_distribution"], {"ipv4": 2, "domains": 1})
        self.assertEqual(data["investigation_status_counts"], {"COMPLETED": 2})

    def test_recent_investigations_uses_investigation_summary_dto_shape(self) -> None:
        investigation_id = self.service.save(
            make_investigation(report_name="c.txt", risk_score=88)
        )
        handler = GetDashboardSummaryCommandHandler(self.service)

        response = handler.handle(GetDashboardSummaryRequest())

        recent = response["data"]["recent_investigations"]
        self.assertEqual(len(recent), 1)
        entry = recent[0]
        self.assertEqual(entry["investigation_id"], investigation_id)
        self.assertEqual(entry["report_name"], "c.txt")
        self.assertEqual(entry["risk_score"], 88)
        # Same omission guarantee as get_investigation/list_investigations:
        # the large nested fields never leak into a summary shape.
        self.assertNotIn("iocs", entry)
        self.assertNotIn("threat_intelligence", entry)

    def test_recent_investigations_respects_configured_limit(self) -> None:
        for index in range(7):
            self.service.save(make_investigation(report_name=f"r{index}.txt"))
        handler = GetDashboardSummaryCommandHandler(self.service, recent_limit=3)

        response = handler.handle(GetDashboardSummaryRequest())

        self.assertEqual(len(response["data"]["recent_investigations"]), 3)

    def test_response_is_json_serializable_and_leaks_no_gui_objects(self) -> None:
        self.service.save(make_investigation())
        handler = GetDashboardSummaryCommandHandler(self.service)

        response = handler.handle(GetDashboardSummaryRequest())

        # Must round-trip through json.dumps with no custom encoder --
        # a BadgeType/TimelineEvent/raw Investigation leaking in would
        # fail this immediately.
        reserialized = json.loads(json.dumps(response))
        self.assertEqual(reserialized, response)

    def test_dispatched_via_command_name(self) -> None:
        self.service.save(make_investigation(report_name="dispatched.txt"))
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch("get_dashboard_summary", {})

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["metrics"]["total_reports"], 1)

    def test_rejects_unexpected_payload_fields(self) -> None:
        response = dispatch("get_dashboard_summary", {"limit": 5})

        self.assertFalse(response["success"])
        from app.application.errors import INVALID_COMMAND_PAYLOAD

        self.assertEqual(response["error"]["code"], INVALID_COMMAND_PAYLOAD)


class GetInvestigationAggregateSummaryCommandHandlerTests(IsolatedServiceTestCase):
    """PD-04: the get_investigation_aggregate_summary aggregate command
    (docs/phase4/PD04_CROSS_INVESTIGATION_AGGREGATE_COMMANDS.md)."""

    def test_returns_zeroed_summary_for_empty_database(self) -> None:
        handler = GetInvestigationAggregateSummaryCommandHandler(self.service)

        response = handler.handle(GetInvestigationAggregateSummaryRequest())

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        data = response["data"]
        self.assertEqual(data["total_investigations"], 0)
        self.assertEqual(data["status_counts"], {})
        self.assertEqual(data["severity_distribution"], {})
        self.assertEqual(data["ioc_distribution"], {})
        self.assertIsNone(data["threat_intel_coverage_percent"])
        self.assertEqual(data["investigations_by_date"], {})

    def test_single_investigation_aggregates_correctly(self) -> None:
        analyzed_at = datetime(2026, 3, 14, 9, 30, tzinfo=UTC)
        self.service.save(
            make_investigation(
                report_name="solo.txt",
                iocs={"ipv4": ["1.1.1.1"]},
                severity="HIGH",
                analyzed_at=analyzed_at,
                threat_intelligence={"coverage": {"requested": 1, "succeeded": 1}},
            )
        )
        handler = GetInvestigationAggregateSummaryCommandHandler(self.service)

        response = handler.handle(GetInvestigationAggregateSummaryRequest())

        data = response["data"]
        self.assertEqual(data["total_investigations"], 1)
        self.assertEqual(data["status_counts"], {"COMPLETED": 1})
        self.assertEqual(data["severity_distribution"], {"HIGH": 1})
        self.assertEqual(data["ioc_distribution"], {"ipv4": 1})
        self.assertEqual(data["threat_intel_coverage_percent"], 100.0)
        self.assertEqual(data["investigations_by_date"], {"2026-03-14": 1})

    def test_multiple_investigations_totals_are_correctly_combined(self) -> None:
        self.service.save(
            make_investigation(
                report_name="a.txt",
                iocs={"ipv4": ["1.1.1.1", "2.2.2.2"]},
                severity="LOW",
                status="COMPLETED",
                threat_intelligence={"coverage": {"requested": 2, "succeeded": 2}},
                analyzed_at=datetime(2026, 3, 14, 9, 0, tzinfo=UTC),
            )
        )
        self.service.save(
            make_investigation(
                report_name="b.txt",
                iocs={"domains": ["evil.example"]},
                severity="CRITICAL",
                status="COMPLETED",
                threat_intelligence={"coverage": {"requested": 1, "succeeded": 0}},
                analyzed_at=datetime(2026, 3, 14, 15, 0, tzinfo=UTC),
            )
        )
        self.service.save(
            make_investigation(
                report_name="c.txt",
                iocs={"ipv4": ["3.3.3.3"], "domains": ["another.example"]},
                severity="LOW",
                status="COMPLETED",
                threat_intelligence={"coverage": {"requested": 0, "succeeded": 0}},
                analyzed_at=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
            )
        )
        handler = GetInvestigationAggregateSummaryCommandHandler(self.service)

        response = handler.handle(GetInvestigationAggregateSummaryRequest())

        data = response["data"]
        self.assertEqual(data["total_investigations"], 3)
        self.assertEqual(data["status_counts"], {"COMPLETED": 3})
        self.assertEqual(data["severity_distribution"], {"LOW": 2, "CRITICAL": 1})
        self.assertEqual(
            data["ioc_distribution"], {"ipv4": 3, "domains": 2}
        )
        # (2 + 0 + 0) succeeded / (2 + 1 + 0) requested * 100 = 66.7
        self.assertEqual(data["threat_intel_coverage_percent"], 66.7)
        self.assertEqual(
            data["investigations_by_date"],
            {"2026-03-14": 2, "2026-03-15": 1},
        )

    def test_malformed_threat_intelligence_json_is_skipped_not_fatal(self) -> None:
        self.service.save(
            make_investigation(
                report_name="malformed.txt",
                threat_intelligence={"coverage": {"requested": "not-a-number"}},
            )
        )
        handler = GetInvestigationAggregateSummaryCommandHandler(self.service)

        response = handler.handle(GetInvestigationAggregateSummaryRequest())

        self.assertTrue(response["success"])
        self.assertIsNone(response["data"]["threat_intel_coverage_percent"])

    def test_response_is_json_serializable(self) -> None:
        self.service.save(make_investigation())
        handler = GetInvestigationAggregateSummaryCommandHandler(self.service)

        response = handler.handle(GetInvestigationAggregateSummaryRequest())

        reserialized = json.loads(json.dumps(response))
        self.assertEqual(reserialized, response)

    def test_dispatched_via_command_name(self) -> None:
        self.service.save(make_investigation(report_name="dispatched.txt"))
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch("get_investigation_aggregate_summary", {})

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["total_investigations"], 1)

    def test_rejects_unexpected_payload_fields(self) -> None:
        response = dispatch(
            "get_investigation_aggregate_summary", {"unexpected": True}
        )

        self.assertFalse(response["success"])
        from app.application.errors import INVALID_COMMAND_PAYLOAD

        self.assertEqual(response["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_repository_failure_is_translated_not_raised(self) -> None:
        """Mirrors the same repository-failure -> translated-error-envelope
        guarantee `dispatch()`'s own docstring establishes for every
        command (see the broad `except Exception` there)."""
        broken_service = unittest.mock.Mock()
        broken_service.list_all.side_effect = RuntimeError("db unavailable")
        handler = GetInvestigationAggregateSummaryCommandHandler(broken_service)

        with self.assertRaises(RuntimeError):
            handler.handle(GetInvestigationAggregateSummaryRequest())

        # dispatch() itself, not the handler alone, is the boundary that
        # translates this into a response envelope -- confirmed via the
        # command-name path used by the API/sidecar layer.
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=broken_service,
        ):
            response = dispatch("get_investigation_aggregate_summary", {})

        self.assertFalse(response["success"])
        self.assertIsNotNone(response["error"])


class SearchInvestigationsCommandHandlerTests(IsolatedServiceTestCase):
    """Phase 4D Part 3: the search_investigations vertical slice."""

    def test_returns_matching_investigations_as_summaries(self) -> None:
        self.service.save(make_investigation(report_name="target.txt"))
        self.service.save(make_investigation(report_name="other.txt"))
        handler = SearchInvestigationsCommandHandler(self.service)

        response = handler.handle(SearchInvestigationsRequest("target.txt"))

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        report_names = {item["report_name"] for item in response["data"]}
        self.assertEqual(report_names, {"target.txt"})

    def test_returns_empty_list_when_no_match(self) -> None:
        self.service.save(make_investigation(report_name="other.txt"))
        handler = SearchInvestigationsCommandHandler(self.service)

        response = handler.handle(SearchInvestigationsRequest("nope.txt"))

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], [])

    def test_blank_report_name_short_circuits_to_empty_list(self) -> None:
        """Per HistoryController.search_by_report_name: blank input is
        "no search term", not a query -- and must not reach the
        repository at all."""
        self.service.save(make_investigation(report_name="anything.txt"))
        handler = SearchInvestigationsCommandHandler(self.service)

        response = handler.handle(SearchInvestigationsRequest("   "))

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], [])

    def test_request_dto_rejects_non_string_report_name(self) -> None:
        with self.assertRaises(CommandValidationError):
            SearchInvestigationsRequest(123)

    def test_dispatched_via_command_name(self) -> None:
        self.service.save(make_investigation(report_name="target.txt"))
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch(
                "search_investigations", {"report_name": "target.txt"}
            )

        self.assertTrue(response["success"])
        report_names = {item["report_name"] for item in response["data"]}
        self.assertEqual(report_names, {"target.txt"})


class DeleteInvestigationCommandHandlerTests(IsolatedServiceTestCase):
    """Phase 4D Part 2: the delete_investigation vertical slice."""

    def test_deletes_existing_investigation(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = DeleteInvestigationCommandHandler(self.service)

        response = handler.handle(DeleteInvestigationRequest(investigation_id))

        self.assertTrue(response["success"])
        self.assertTrue(response["data"]["deleted"])
        self.assertEqual(response["data"]["investigation_id"], investigation_id)
        # Confirm it is actually gone, not just reported as gone.
        self.assertIsNone(self.service.get_by_id(investigation_id))

    def test_missing_id_returns_success_with_deleted_false(self) -> None:
        """Per PHASE4B_COMMAND_INVENTORY.md: a missing id is a normal
        False result, not an error -- this preserves that domain
        semantic unchanged rather than reinterpreting it as
        INVESTIGATION_NOT_FOUND."""
        handler = DeleteInvestigationCommandHandler(self.service)

        response = handler.handle(DeleteInvestigationRequest(999999))

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertFalse(response["data"]["deleted"])
        self.assertEqual(response["data"]["investigation_id"], 999999)

    def test_request_dto_rejects_non_positive_id(self) -> None:
        with self.assertRaises(CommandValidationError):
            DeleteInvestigationRequest(0)
        with self.assertRaises(CommandValidationError):
            DeleteInvestigationRequest(-5)

    def test_dispatched_via_command_name(self) -> None:
        investigation_id = self.service.save(make_investigation())
        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch(
                "delete_investigation", {"investigation_id": investigation_id}
            )

        self.assertTrue(response["success"])
        self.assertTrue(response["data"]["deleted"])


class DispatchTests(IsolatedServiceTestCase):
    """Exercises the transport-agnostic dispatch() seam app/api/app.py calls into."""

    def test_unknown_command_returns_unknown_command_error(self) -> None:
        response = dispatch("no_such_command", {})
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "UNKNOWN_COMMAND")

    def test_malformed_payload_returns_invalid_command_payload(self) -> None:
        response = dispatch("get_investigation", {"investigation_id": "not-an-int"})
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INVALID_COMMAND_PAYLOAD")

    def test_missing_required_field_returns_invalid_command_payload(self) -> None:
        response = dispatch("get_investigation", {})
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INVALID_COMMAND_PAYLOAD")

    def test_search_investigations_rejects_non_string_report_name(self) -> None:
        response = dispatch("search_investigations", {"report_name": 123})
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INVALID_COMMAND_PAYLOAD")


class AnalyzeReportCommandHandlerTests(unittest.TestCase):
    """
    Exercises the one long-running command against real domain code
    (app.analyzer.analyze_report), including the event sequence it
    produces. See module docstring for why the real database/soc_iq.db
    file is snapshotted/restored here rather than injected.
    """

    def setUp(self) -> None:
        self._db_backup = None
        if DATABASE_PATH.exists():
            fd, backup_path = tempfile.mkstemp(suffix=".db")
            import os

            os.close(fd)
            shutil.copy2(DATABASE_PATH, backup_path)
            self._db_backup = Path(backup_path)

    def tearDown(self) -> None:
        if self._db_backup is not None:
            shutil.copy2(self._db_backup, DATABASE_PATH)
            self._db_backup.unlink(missing_ok=True)

    def test_rejects_missing_report_path(self) -> None:
        handler = AnalyzeReportCommandHandler()
        response, collector = handler.handle(
            AnalyzeReportRequest("/nonexistent/report/path.txt")
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], REPORT_NOT_FOUND)
        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].event, "analysis.failed")

    def test_request_dto_rejects_empty_path(self) -> None:
        from app.application.dto import AnalyzeReportRequest

        with self.assertRaises(CommandValidationError):
            AnalyzeReportRequest("")

    def test_analyzes_real_sample_report_and_emits_correct_event_sequence(self) -> None:
        from app.application.dto import AnalyzeReportRequest

        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        handler = AnalyzeReportCommandHandler()
        response, collector = handler.handle(AnalyzeReportRequest(str(sample)))

        self.assertTrue(
            response["success"], msg=response.get("error")
        )
        self.assertIn("investigation", response["data"])
        self.assertIn("correlation_id", response["data"])

        # Every event shares exactly one correlation_id.
        correlation_ids = {event.correlation_id for event in collector.events}
        self.assertEqual(len(correlation_ids), 1)
        self.assertEqual(
            response["data"]["correlation_id"], next(iter(correlation_ids))
        )

        # Sequence: started -> N x progress -> completed, in order.
        names = [event.event for event in collector.events]
        self.assertEqual(names[0], "analysis.started")
        self.assertEqual(names[-1], "analysis.completed")
        self.assertTrue(all(name == "analysis.progress" for name in names[1:-1]))

        # investigation_id is absent on started/progress, present on completed.
        self.assertIsNone(collector.events[0].investigation_id)
        self.assertIsNotNone(collector.events[-1].investigation_id)

        # Clean up the row this test created so re-running it doesn't
        # collide with the analyzer's own duplicate-report-name check.
        InvestigationService().delete(
            collector.events[-1].investigation_id
        )


class AnalyzeReportTimelineEmissionTests(unittest.TestCase):
    """
    A4-P2-P3 Part 4: `AnalyzeReportCommandHandler` now appends a
    persisted `TimelineEvent` per completed pipeline stage (in
    addition to the pre-existing ephemeral `Event`s asserted by
    `AnalyzeReportCommandHandlerTests` above). These are two
    different, non-competing mechanisms -- see
    `app.timeline.domain`'s module docstring -- so this is a
    separate test class rather than an extension of that one.
    """

    def setUp(self) -> None:
        self._db_backup = None
        if DATABASE_PATH.exists():
            fd, backup_path = tempfile.mkstemp(suffix=".db")
            import os

            os.close(fd)
            shutil.copy2(DATABASE_PATH, backup_path)
            self._db_backup = Path(backup_path)

    def tearDown(self) -> None:
        if self._db_backup is not None:
            shutil.copy2(self._db_backup, DATABASE_PATH)
            self._db_backup.unlink(missing_ok=True)

    def test_new_investigation_records_full_timeline(self) -> None:
        from app.application.dto import AnalyzeReportRequest
        from app.timeline.domain import TimelineEventType
        from app.timeline.repository import TimelineRepository

        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        handler = AnalyzeReportCommandHandler()
        response, _ = handler.handle(AnalyzeReportRequest(str(sample)))
        self.assertTrue(response["success"], msg=response.get("error"))

        investigation_id = response["data"]["investigation"]["investigation_id"]

        try:
            events = TimelineRepository().list_for_investigation(investigation_id)
            event_types = [event.event_type for event in events]

            # All default-options stages recorded, in pipeline order,
            # every event scoped to this one investigation. A4-P2-P3
            # Part 6 adds CORRELATION_COMPLETED (unconditional, like
            # ANALYSIS_STARTED/COMPLETED -- there is no `correlate`
            # option to gate it on) between RISK_CALCULATED and
            # ANALYSIS_COMPLETED, closing the vocabulary's last
            # previously-unwired member.
            self.assertEqual(
                event_types,
                [
                    TimelineEventType.INVESTIGATION_CREATED,
                    TimelineEventType.REPORT_IMPORTED,
                    TimelineEventType.ANALYSIS_STARTED,
                    TimelineEventType.IOC_EXTRACTION_COMPLETED,
                    TimelineEventType.TI_ENRICHMENT_COMPLETED,
                    TimelineEventType.RISK_CALCULATED,
                    TimelineEventType.CORRELATION_COMPLETED,
                    TimelineEventType.ANALYSIS_COMPLETED,
                ],
            )
            self.assertTrue(
                all(
                    event.investigation_id == investigation_id
                    for event in events
                )
            )
        finally:
            InvestigationService().delete(investigation_id)

    def test_duplicate_report_records_no_new_timeline_events(self) -> None:
        """Re-analyzing an already-known report_name returns the
        existing investigation (result["existing"] is True) and must
        not append a second copy of investigation.created/... to a
        timeline that already recorded those facts once."""

        from app.application.dto import AnalyzeReportRequest
        from app.timeline.repository import TimelineRepository

        sample = Path("samples") / "report4.txt"
        handler = AnalyzeReportCommandHandler()

        first, _ = handler.handle(AnalyzeReportRequest(str(sample)))
        self.assertTrue(first["success"], msg=first.get("error"))
        investigation_id = first["data"]["investigation"]["investigation_id"]

        try:
            events_after_first = TimelineRepository().list_for_investigation(
                investigation_id
            )

            second, _ = handler.handle(AnalyzeReportRequest(str(sample)))
            self.assertTrue(second["success"], msg=second.get("error"))
            self.assertTrue(second["data"]["existing"])

            events_after_second = TimelineRepository().list_for_investigation(
                investigation_id
            )
            self.assertEqual(len(events_after_first), len(events_after_second))
        finally:
            InvestigationService().delete(investigation_id)

    def test_disabled_stage_records_no_event_for_that_stage(self) -> None:
        from app.application.dto import AnalyzeReportRequest, AnalysisOptions
        from app.timeline.domain import TimelineEventType
        from app.timeline.repository import TimelineRepository

        sample = Path("samples") / "sample_report.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        handler = AnalyzeReportCommandHandler()
        response, _ = handler.handle(
            AnalyzeReportRequest(
                str(sample),
                options=AnalysisOptions(score_risk=False),
            )
        )
        self.assertTrue(response["success"], msg=response.get("error"))
        investigation_id = response["data"]["investigation"]["investigation_id"]

        try:
            events = TimelineRepository().list_for_investigation(investigation_id)
            event_types = {event.event_type for event in events}
            self.assertNotIn(TimelineEventType.RISK_CALCULATED, event_types)
            self.assertIn(TimelineEventType.ANALYSIS_COMPLETED, event_types)
        finally:
            InvestigationService().delete(investigation_id)

    def test_correlation_completed_event_matches_correlation_service(self) -> None:
        """A4-P2-P3 Part 6: the recorded `correlation.completed` event's
        metadata must be the same, real `CorrelationService` output the
        investigation actually has -- never a placeholder/zero, and never
        independently recomputed by this test in a way that could drift
        from the handler's own call (both call the same real service)."""

        from app.application.dto import AnalyzeReportRequest
        from app.services.correlation_service import CorrelationService
        from app.timeline.domain import TimelineEventType
        from app.timeline.repository import TimelineRepository

        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        handler = AnalyzeReportCommandHandler()
        response, _ = handler.handle(AnalyzeReportRequest(str(sample)))
        self.assertTrue(response["success"], msg=response.get("error"))
        investigation_id = response["data"]["investigation"]["investigation_id"]

        try:
            investigation = InvestigationService().get_by_id(investigation_id)
            expected_report = CorrelationService().correlate(investigation)

            events = TimelineRepository().list_for_investigation(investigation_id)
            correlation_events = [
                event
                for event in events
                if event.event_type == TimelineEventType.CORRELATION_COMPLETED
            ]

            self.assertEqual(
                len(correlation_events),
                1,
                "exactly one correlation.completed event for a new investigation",
            )

            recorded = correlation_events[0]
            self.assertEqual(
                recorded.metadata["relationship_count"],
                expected_report.summary.relationship_count,
            )
            self.assertEqual(
                recorded.metadata["correlated_evidence_count"],
                expected_report.summary.correlated_evidence_count,
            )
            # This investigation's own correlation events never claim a
            # relationship with any other investigation -- see the
            # metadata's own field names (no other investigation_id
            # appears anywhere in this payload).
            self.assertNotIn("other_investigation_id", recorded.metadata)
        finally:
            InvestigationService().delete(investigation_id)

    def test_correlation_failure_does_not_fail_analysis_or_record_event(self) -> None:
        """A4-P2-P3 Part 7: `AnalyzeReportCommandHandler`'s own docstring/
        comment (see the try/except around `self._correlation_service.
        correlate(...)`) claims a `CorrelationService` failure "must not
        fail an already-succeeded analysis any more than a timeline-write
        failure would." That claim was never exercised by any test --
        the handler's `correlation_service` constructor parameter exists
        specifically to allow substituting a failing double for exactly
        this proof. This does not change behavior; it proves the
        already-implemented resilience actually holds."""

        from app.application.dto import AnalyzeReportRequest
        from app.timeline.domain import TimelineEventType
        from app.timeline.repository import TimelineRepository

        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        failing_correlation_service = unittest.mock.Mock()
        failing_correlation_service.correlate.side_effect = RuntimeError(
            "simulated correlation failure"
        )

        handler = AnalyzeReportCommandHandler(
            correlation_service=failing_correlation_service
        )
        response, _ = handler.handle(AnalyzeReportRequest(str(sample)))

        # The analysis itself must still succeed -- a correlation failure
        # is logged and swallowed, never propagated to the caller.
        self.assertTrue(response["success"], msg=response.get("error"))
        investigation_id = response["data"]["investigation"]["investigation_id"]

        try:
            failing_correlation_service.correlate.assert_called_once()

            events = TimelineRepository().list_for_investigation(investigation_id)
            event_types = [event.event_type for event in events]

            # No fabricated correlation.completed event for a call that
            # never actually completed (Part 6's data-integrity rule:
            # never turn a failure into fake data).
            self.assertNotIn(TimelineEventType.CORRELATION_COMPLETED, event_types)

            # Every other pipeline-stage event still recorded and the
            # pipeline still reached its own completion event -- one
            # failed stage's swallowed exception does not silently
            # discard or truncate the rest of the timeline.
            self.assertEqual(
                event_types,
                [
                    TimelineEventType.INVESTIGATION_CREATED,
                    TimelineEventType.REPORT_IMPORTED,
                    TimelineEventType.ANALYSIS_STARTED,
                    TimelineEventType.IOC_EXTRACTION_COMPLETED,
                    TimelineEventType.TI_ENRICHMENT_COMPLETED,
                    TimelineEventType.RISK_CALCULATED,
                    TimelineEventType.ANALYSIS_COMPLETED,
                ],
            )
        finally:
            InvestigationService().delete(investigation_id)

    def test_timeline_append_failure_does_not_fail_analysis(self) -> None:
        """A4-P2-P3 Part 7: `_record_timeline_event`'s own docstring
        claims "a failure to record a timeline event must never fail the
        analysis itself." Never exercised by any test -- the handler's
        `timeline_repository` constructor parameter exists specifically
        to allow substituting a failing double for exactly this proof.
        Proves the existing swallow-and-log behavior actually holds when
        every single append() call fails, not just one."""

        from app.application.dto import AnalyzeReportRequest

        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        failing_timeline_repository = unittest.mock.Mock()
        failing_timeline_repository.append.side_effect = RuntimeError(
            "simulated timeline append failure"
        )

        handler = AnalyzeReportCommandHandler(
            timeline_repository=failing_timeline_repository
        )
        response, _ = handler.handle(AnalyzeReportRequest(str(sample)))

        # The analysis itself must still succeed -- the investigation is
        # already durably saved before any timeline append is attempted.
        self.assertTrue(response["success"], msg=response.get("error"))
        investigation_id = response["data"]["investigation"]["investigation_id"]

        try:
            # Every pipeline stage still attempted its append -- the
            # failure of one append must not stop later stages from
            # trying to record their own event. All 8 default-options
            # stages call _record_timeline_event (see
            # test_new_investigation_records_full_timeline's own 8-item
            # event_types list for the same count).
            self.assertEqual(failing_timeline_repository.append.call_count, 8)
        finally:
            InvestigationService().delete(investigation_id)


class AnalysisOptionsTests(unittest.TestCase):
    """
    Phase 4I Blocker B, Part 2A: `AnalysisOptions` construction/defaults/
    validation, plus `AnalyzeReportRequest.options` normalization. No
    analyzer-stage enforcement is exercised here -- that is PART 2B.
    """

    def test_constructs_with_explicit_values(self) -> None:
        options = AnalysisOptions(
            extract_iocs=False, enrich_ti=True, score_risk=False
        )
        self.assertFalse(options.extract_iocs)
        self.assertTrue(options.enrich_ti)
        self.assertFalse(options.score_risk)

    def test_defaults_are_all_true(self) -> None:
        options = AnalysisOptions()
        self.assertTrue(options.extract_iocs)
        self.assertTrue(options.enrich_ti)
        self.assertTrue(options.score_risk)

    def test_from_payload_none_returns_defaults(self) -> None:
        options = AnalysisOptions.from_payload(None)
        self.assertEqual(options, AnalysisOptions())

    def test_from_payload_accepts_existing_instance(self) -> None:
        existing = AnalysisOptions(extract_iocs=False)
        self.assertIs(AnalysisOptions.from_payload(existing), existing)

    def test_from_payload_accepts_partial_dict_and_fills_defaults(self) -> None:
        options = AnalysisOptions.from_payload({"extract_iocs": False})
        self.assertFalse(options.extract_iocs)
        self.assertTrue(options.enrich_ti)
        self.assertTrue(options.score_risk)

    def test_from_payload_rejects_non_object(self) -> None:
        with self.assertRaises(CommandValidationError):
            AnalysisOptions.from_payload(["extract_iocs"])

    def test_from_payload_rejects_unknown_key(self) -> None:
        with self.assertRaises(CommandValidationError):
            AnalysisOptions.from_payload({"extract_iocs": True, "bogus": True})

    def test_rejects_non_boolean_value(self) -> None:
        with self.assertRaises(CommandValidationError):
            AnalysisOptions(extract_iocs="true")  # type: ignore[arg-type]

    def test_to_dict_round_trips(self) -> None:
        options = AnalysisOptions(extract_iocs=False, enrich_ti=False, score_risk=True)
        self.assertEqual(
            options.to_dict(),
            {"extract_iocs": False, "enrich_ti": False, "score_risk": True},
        )

    def test_analyze_report_request_defaults_options_when_omitted(self) -> None:
        request = AnalyzeReportRequest("/nonexistent/report/path.txt")
        self.assertEqual(request.options, AnalysisOptions())

    def test_analyze_report_request_accepts_raw_dict_options(self) -> None:
        request = AnalyzeReportRequest(
            "/nonexistent/report/path.txt",
            options={"extract_iocs": False, "enrich_ti": True, "score_risk": True},
        )
        self.assertIsInstance(request.options, AnalysisOptions)
        self.assertFalse(request.options.extract_iocs)

    def test_analyze_report_request_accepts_analysis_options_instance(self) -> None:
        options = AnalysisOptions(score_risk=False)
        request = AnalyzeReportRequest("/nonexistent/report/path.txt", options=options)
        self.assertIs(request.options, options)

    def test_analyze_report_request_rejects_malformed_options(self) -> None:
        with self.assertRaises(CommandValidationError):
            AnalyzeReportRequest(
                "/nonexistent/report/path.txt", options={"extract_iocs": "yes"}
            )

    def test_analyze_report_request_rejects_unknown_option_key(self) -> None:
        with self.assertRaises(CommandValidationError):
            AnalyzeReportRequest(
                "/nonexistent/report/path.txt", options={"unknown_flag": True}
            )

    def test_raw_json_payload_dispatch_preserves_options(self) -> None:
        # Simulates the exact frontend -> API -> dispatch path: a plain
        # dict (as parsed from JSON) with a nested `options` object, fed
        # straight into dispatch() rather than constructed in Python.
        response = dispatch(
            "analyze_report",
            {
                "report_path": "/nonexistent/report/path.txt",
                "options": {
                    "extract_iocs": False,
                    "enrich_ti": True,
                    "score_risk": True,
                },
            },
        )
        # Missing report -> REPORT_NOT_FOUND, but the options must have
        # been accepted (not rejected as INVALID_COMMAND_PAYLOAD) to get
        # that far -- proving raw JSON -> DTO -> dispatch preserved them
        # through validation rather than choking on the nested object.
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], REPORT_NOT_FOUND)

    def test_dispatch_rejects_malformed_options_before_touching_the_analyzer(
        self,
    ) -> None:
        from app.application.errors import INVALID_COMMAND_PAYLOAD

        response = dispatch(
            "analyze_report",
            {
                "report_path": "/nonexistent/report/path.txt",
                "options": {"extract_iocs": "not-a-bool"},
            },
        )
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_report_path_only_payload_is_still_backward_compatible(self) -> None:
        # The exact pre-Blocker-B payload shape: no `options` key at all.
        response = dispatch(
            "analyze_report", {"report_path": "/nonexistent/report/path.txt"}
        )
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], REPORT_NOT_FOUND)

    def test_handler_forwards_options_into_started_event_and_response(self) -> None:
        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        handler = AnalyzeReportCommandHandler()
        request = AnalyzeReportRequest(
            str(sample),
            options=AnalysisOptions(extract_iocs=True, enrich_ti=False, score_risk=True),
        )
        response, collector = handler.handle(request)

        self.assertTrue(response["success"], msg=response.get("error"))
        # The application command/handler received the options (proving
        # request -> command boundary), and forwarded them into both the
        # analysis.started event and the response envelope (proving
        # handler -> event/response boundary), AND into the real
        # analyzer pipeline (Part 2B) -- see
        # AnalyzeReportPipelineEnforcementIntegrationTests below for
        # end-to-end stage-gating proof through dispatch().
        expected = {"extract_iocs": True, "enrich_ti": False, "score_risk": True}
        self.assertEqual(response["data"]["options"], expected)
        self.assertEqual(collector.events[0].event, "analysis.started")
        self.assertEqual(collector.events[0].payload["options"], expected)

        InvestigationService().delete(collector.events[-1].investigation_id)


class AnalyzeReportPipelineEnforcementIntegrationTests(unittest.TestCase):
    """
    Phase 4I Blocker B, Part 2B, required test #8: proves the full
    raw-JSON -> DTO -> dispatch() -> AnalyzeReportCommandHandler ->
    domain_analyze_report path preserves options all the way to real
    pipeline enforcement -- not just to the DTO/handler boundary (that
    is AnalysisOptionsTests' job) and not by calling app.analyzer
    directly (that is test_analyzer_pipeline_options.py's job).
    """

    def setUp(self) -> None:
        self._db_backup = None
        if DATABASE_PATH.exists():
            fd, backup_path = tempfile.mkstemp(suffix=".db")
            import os

            os.close(fd)
            shutil.copy2(DATABASE_PATH, backup_path)
            self._db_backup = Path(backup_path)
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        if self._db_backup is not None:
            shutil.copy2(self._db_backup, DATABASE_PATH)
            self._db_backup.unlink(missing_ok=True)

    def _write_report(self, name: str) -> str:
        path = Path(self._tmpdir) / name
        path.write_text(
            "Suspicious IP: 198.51.100.23\nSuspicious domain: evil-example.net\n",
            encoding="utf-8",
        )
        return str(path)

    def test_raw_json_dispatch_disables_extraction_end_to_end(self) -> None:
        report_path = self._write_report("dispatch-iocs-false.txt")

        response = dispatch(
            "analyze_report",
            {
                "report_path": report_path,
                "options": {
                    "extract_iocs": False,
                    "enrich_ti": False,
                    "score_risk": False,
                },
            },
        )

        self.assertTrue(response["success"], msg=response.get("error"))
        investigation_id = response["data"]["investigation"]["investigation_id"]

        # Verify against the persisted row (not just the summary DTO,
        # which deliberately omits iocs/threat_intelligence) that the
        # real pipeline actually skipped every disabled stage.
        stored = InvestigationService().get_by_id(investigation_id)
        self.assertEqual(stored.iocs.get("ipv4"), [])
        self.assertNotIn("198.51.100.23", stored.iocs.get("ipv4", []))
        self.assertEqual(stored.threat_intelligence.get("reason"), "disabled")
        self.assertEqual(stored.severity, "NOT_SCORED")

        InvestigationService().delete(investigation_id)

    def test_raw_json_dispatch_default_options_runs_full_pipeline(self) -> None:
        report_path = self._write_report("dispatch-default.txt")

        # No `options` key at all -- the exact pre-Blocker-B payload.
        response = dispatch("analyze_report", {"report_path": report_path})

        self.assertTrue(response["success"], msg=response.get("error"))
        investigation_id = response["data"]["investigation"]["investigation_id"]

        stored = InvestigationService().get_by_id(investigation_id)
        self.assertIn("198.51.100.23", stored.iocs.get("ipv4", []))
        self.assertNotEqual(stored.severity, "NOT_SCORED")
        self.assertNotEqual(stored.threat_intelligence.get("reason"), "disabled")

        InvestigationService().delete(investigation_id)


class AnalyzeReportBrokerIntegrationTests(unittest.TestCase):
    """PHASE4D_SSE_PART2_IMPLEMENTATION.md Stage 7 'Broker integration'
    (items 1-3). Uses the fast, no-real-analysis failure path (missing
    report path) rather than re-running the full sample-report analysis
    already covered above -- what's under test here is the
    collector/broker fan-out, not analyze_report's domain behavior
    (already covered by AnalyzeReportCommandHandlerTests).
    """

    def test_events_reach_both_the_collector_and_the_broker_without_duplication(
        self,
    ) -> None:
        broker = EventBroker()
        handler = AnalyzeReportCommandHandler(broker=broker)

        with broker.subscription() as sub:
            response, collector = handler.handle(
                AnalyzeReportRequest("/nonexistent/report/path.txt")
            )
            delivered = sub.drain()

        self.assertFalse(response["success"])
        # EventCollector still receives its own events, unchanged.
        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].event, "analysis.failed")
        # The broker receives the SAME single event -- not zero (broker
        # unreachable), not two (duplicated because both sinks are
        # active).
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0].event_id, collector.events[0].event_id)

    def test_default_broker_is_the_shared_application_broker(self) -> None:
        from app.application.broker import get_application_broker

        handler = AnalyzeReportCommandHandler()

        with get_application_broker().subscription() as sub:
            handler.handle(AnalyzeReportRequest("/nonexistent/report/path.txt"))
            delivered = sub.drain()

        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0].event, "analysis.failed")


class ErrorTranslationUnitTests(unittest.TestCase):
    """
    Part 1B: `code_for_exception` (app/application/errors.py) was imported
    and used by AnalyzeReportCommandHandler but had zero direct test
    coverage -- these pin its mapping behavior in isolation, independent of
    any handler.
    """

    def test_maps_known_domain_exceptions_to_their_documented_codes(self) -> None:
        self.assertEqual(code_for_exception(DatabaseError("boom")), "DATABASE_ERROR")
        self.assertEqual(
            code_for_exception(DuplicateInvestigationError("r.txt")),
            "DUPLICATE_INVESTIGATION",
        )
        self.assertEqual(
            code_for_exception(RateLimitExceededError("slow down")),
            "TI_RATE_LIMITED",
        )

    def test_unmapped_exception_falls_back_to_internal_error(self) -> None:
        self.assertEqual(code_for_exception(ValueError("unrelated")), "INTERNAL_ERROR")


class DispatchErrorTranslationTests(IsolatedServiceTestCase):
    """
    Part 1B: closes a real gap found by audit -- GetInvestigationCommandHandler
    and ListInvestigationsCommandHandler had no exception-translation of
    their own, and dispatch()'s except clauses only covered
    CommandValidationError/TypeError, so an unexpected domain exception
    (e.g. DatabaseError from the repository) propagated out of dispatch()
    uncaught -- reproduced directly before this fix. These assert the
    fixed behavior: dispatch() now returns a translated fail() envelope
    for every command, never a raised exception, matching
    responses.py's own stated invariant.
    """

    def test_get_investigation_translates_unexpected_service_exception(self) -> None:
        with patch.object(
            InvestigationService, "get_by_id", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch("get_investigation", {"investigation_id": 1})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_list_investigations_translates_unexpected_service_exception(self) -> None:
        with patch.object(
            InvestigationService, "list_all", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch("list_investigations", {})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_get_iocs_translates_unexpected_service_exception(self) -> None:
        with patch.object(
            InvestigationService, "get_by_id", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch("get_iocs", {"investigation_id": 1})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_get_threat_intelligence_translates_unexpected_service_exception(self) -> None:
        with patch.object(
            InvestigationService, "get_by_id", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch("get_threat_intelligence", {"investigation_id": 1})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_get_timeline_translates_unexpected_service_exception(self) -> None:
        """A4-P2-P3 Part 3: `get_timeline`'s own existence check
        (`InvestigationService.get_by_id`) fails the same way every
        other `investigation_id`-keyed command's existence check
        already does -- reuses the exact same fixture/pattern as
        `test_get_iocs_translates_unexpected_service_exception` above,
        deliberately, since both commands perform the identical lookup
        before ever touching their own repository."""

        with patch.object(
            InvestigationService, "get_by_id", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch("get_timeline", {"investigation_id": 1})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_get_timeline_translates_unexpected_repository_exception(self) -> None:
        """Distinct from the test above: here `InvestigationService`
        succeeds (the investigation genuinely exists) and it is
        `TimelineRepository.list_for_investigation` itself that fails
        -- the "repository failure" case the Part 3 brief calls out
        explicitly.

        `InvestigationService.get_by_id` is patched to return a real,
        already-`save()`-assigned `Investigation` (never raising),
        rather than relying on `dispatch()`'s default-constructed
        handler resolving against the real on-disk
        `database/soc_iq.db` -- this test's own isolated `self.service`
        already proves that lookup would succeed; patching the return
        value here keeps this test from touching the real project
        database file at all (the same restraint
        `IsolatedServiceTestCase` exists to provide, extended to a
        `dispatch()`-level test)."""

        investigation_id = self.service.save(make_investigation())
        investigation = self.service.get_by_id(investigation_id)

        with patch.object(
            InvestigationService, "get_by_id", return_value=investigation
        ), patch.object(
            TimelineRepository,
            "list_for_investigation",
            side_effect=DatabaseError("disk gone"),
        ):
            response = dispatch(
                "get_timeline", {"investigation_id": investigation_id}
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_save_settings_translates_unexpected_service_exception(self) -> None:
        # SettingsService.update_theme (and its two siblings) does not
        # catch a repository write failure itself -- only load_settings
        # has its own internal fallback (per app/settings/service.py's
        # own docstring). An OSError from a failed disk write is a real,
        # source-verified failure mode, not an invented one: it is not
        # in the errors.py exception-code map (no per-module exception
        # hierarchy exists for app/settings/*, matching the same gap
        # already documented for app/database/* and app/reporting/* in
        # errors.py's own module docstring), so it is expected to fall
        # through code_for_exception's MRO walk to INTERNAL_ERROR --
        # exactly what this test pins.
        with patch.object(
            SettingsService, "update_theme", side_effect=OSError("disk full")
        ):
            response = dispatch("save_settings", {"theme": "Light Mode"})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")

    def test_delete_investigation_translates_unexpected_service_exception(self) -> None:
        with patch.object(
            InvestigationService, "delete", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch("delete_investigation", {"investigation_id": 1})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_export_report_translates_unexpected_service_exception(self) -> None:
        with patch.object(
            InvestigationService, "get_by_id", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch(
                "export_report",
                {
                    "investigation_id": 1,
                    "export_format": "json",
                    # Absolute -- see §20 export path-traversal regression
                    # above; this test is about DatabaseError translation,
                    # not output_path validation, so the fixture must use
                    # the one shape a real caller (the native save dialog)
                    # actually produces.
                    "output_path": str(Path(tempfile.gettempdir()) / "out.json"),
                },
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_export_report_translates_exporter_write_failure(self) -> None:
        # ReportingService.export_json ultimately raises RuntimeError on an
        # OSError (app/reporting/json_exporter.py) -- not a SOCIQError
        # subclass and not in errors.py's exception-code map (same
        # documented gap as save_settings' OSError case above), so this
        # pins the real, source-verified fallback: INTERNAL_ERROR, not a
        # raised exception reaching dispatch()'s caller.
        investigation_id = self.service.save(make_investigation())
        with patch.object(
            ReportingService,
            "export_json",
            side_effect=RuntimeError("Failed to export JSON report: disk full"),
        ):
            with patch(
                "app.application.handlers.InvestigationService",
                return_value=self.service,
            ):
                response = dispatch(
                    "export_report",
                    {
                        "investigation_id": investigation_id,
                        "export_format": "json",
                        "output_path": "/nonexistent/dir/out.json",
                    },
                )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")

    def test_search_investigations_translates_unexpected_service_exception(self) -> None:
        with patch.object(
            InvestigationService,
            "find_by_report_name",
            side_effect=DatabaseError("disk gone"),
        ):
            response = dispatch(
                "search_investigations", {"report_name": "target.txt"}
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")


class AnalyzeReportErrorTranslationTests(unittest.TestCase):
    """
    Part 1B: AnalyzeReportCommandHandler's `except Exception` branch (the
    domain_analyze_report failure path) was written but never actually
    exercised by a test -- test_rejects_missing_report_path only covers the
    pre-flight path validation, not a genuine domain-layer failure. This
    forces a real exception out of the domain call and asserts the full
    translation + event chain.
    """

    def test_domain_failure_is_translated_and_emits_failed_event(self) -> None:
        with patch(
            "app.application.handlers.domain_analyze_report",
            side_effect=DatabaseError("disk gone"),
        ):
            handler = AnalyzeReportCommandHandler()
            response, collector = handler.handle(
                AnalyzeReportRequest(str(Path("samples") / "report4.txt"))
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

        names = [event.event for event in collector.events]
        self.assertEqual(names, ["analysis.started", "analysis.failed"])

        # started and failed must share one correlation_id.
        correlation_ids = {event.correlation_id for event in collector.events}
        self.assertEqual(len(correlation_ids), 1)

        failed_event = collector.events[-1]
        self.assertEqual(failed_event.payload["code"], "DATABASE_ERROR")
        self.assertIsNone(failed_event.investigation_id)


class EnrichIocCommandHandlerTests(unittest.TestCase):
    """Phase 4D Part 7: the enrich_ioc vertical slice, wrapping the
    confirmed existing `ThreatIntelService.lookup_indicator` operation.

    Part 2 (docs/phase4/PHASE4D_SSE_PART2_IMPLEMENTATION.md, Stage 5)
    changed `EnrichIocCommandHandler.handle()`'s return shape from a bare
    response dict to `(response, EventCollector)`, mirroring
    `AnalyzeReportCommandHandler`'s existing contract, so these tests now
    unpack a tuple. `dispatch("enrich_ioc", ...)`'s own return shape (a
    single response dict) is unchanged -- see the `test_dispatched_via_
    command_name` tests below, which still call `dispatch()` directly
    and still get back one dict, same as before Part 2.
    """

    def test_returns_enrichment_for_valid_sha256(self) -> None:
        fake_client = _FakeVirusTotalClient(
            response={
                "sha256": "a" * 64,
                "found": True,
                "malicious": 10,
                "suspicious": 1,
                "harmless": 60,
                "undetected": 0,
            }
        )
        handler = EnrichIocCommandHandler(
            ThreatIntelService(virustotal=fake_client), broker=EventBroker()
        )

        response, collector = handler.handle(
            EnrichIocRequest(ioc_type="sha256", value="a" * 64)
        )

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["sha256"], "a" * 64)
        self.assertEqual(response["data"]["verdict"], "Malicious")
        self.assertEqual(response["data"]["detection_ratio"], "10/71")
        self.assertEqual(fake_client.lookups, ["a" * 64])

        # Lifecycle events: started -> completed, one correlation_id.
        self.assertEqual([e.event for e in collector.events], [
            "ti.enrichment.started",
            "ti.enrichment.completed",
        ])
        correlation_ids = {e.correlation_id for e in collector.events}
        self.assertEqual(len(correlation_ids), 1)
        started, completed = collector.events
        self.assertEqual(started.payload, {"ioc_type": "sha256", "value": "a" * 64})
        self.assertEqual(completed.payload["ioc_type"], "sha256")
        self.assertEqual(completed.payload["value"], "a" * 64)
        self.assertEqual(completed.payload["result"]["verdict"], "Malicious")

    def test_started_and_completed_events_reach_the_broker(self) -> None:
        fake_client = _FakeVirusTotalClient(
            response={
                "sha256": "c" * 64,
                "found": True,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 71,
                "undetected": 0,
            }
        )
        broker = EventBroker()
        handler = EnrichIocCommandHandler(
            ThreatIntelService(virustotal=fake_client), broker=broker
        )

        with broker.subscription() as sub:
            response, collector = handler.handle(
                EnrichIocRequest(ioc_type="sha256", value="c" * 64)
            )

        self.assertTrue(response["success"])
        delivered = sub.drain()
        # Broker and collector see the SAME two events -- no duplication,
        # no divergence (PHASE4D_SSE_PART2_IMPLEMENTATION.md Stage 7 #1-3).
        self.assertEqual([e.event for e in delivered], [e.event for e in collector.events])
        self.assertEqual([e.event_id for e in delivered], [e.event_id for e in collector.events])

    def test_failed_event_emitted_and_reaches_broker_on_provider_error(self) -> None:
        fake_client = _FakeVirusTotalClient(error=RateLimitExceededError("slow down"))
        broker = EventBroker()
        handler = EnrichIocCommandHandler(
            ThreatIntelService(virustotal=fake_client), broker=broker
        )

        with broker.subscription() as sub:
            with self.assertRaises(RateLimitExceededError):
                handler.handle(EnrichIocRequest(ioc_type="sha256", value="a" * 64))

        delivered = sub.drain()
        self.assertEqual([e.event for e in delivered], [
            "ti.enrichment.started",
            "ti.enrichment.failed",
        ])
        failed_event = delivered[-1]
        self.assertEqual(failed_event.payload["code"], "TI_RATE_LIMITED")
        self.assertEqual(failed_event.payload["ioc_type"], "sha256")
        self.assertEqual(failed_event.payload["value"], "a" * 64)
        # No secret/API-key material anywhere in either event's payload.
        for event in delivered:
            self.assertNotIn("api_key", str(event.payload).lower())
            self.assertNotIn("apikey", str(event.payload).lower())

    def test_handler_default_broker_is_the_shared_application_broker(self) -> None:
        from app.application.broker import get_application_broker

        fake_client = _FakeVirusTotalClient(
            response={
                "sha256": "d" * 64,
                "found": False,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 0,
                "undetected": 0,
            }
        )
        handler = EnrichIocCommandHandler(ThreatIntelService(virustotal=fake_client))

        with get_application_broker().subscription() as sub:
            handler.handle(EnrichIocRequest(ioc_type="sha256", value="d" * 64))

        delivered = sub.drain()
        self.assertEqual([e.event for e in delivered], [
            "ti.enrichment.started",
            "ti.enrichment.completed",
        ])

    def test_request_dto_rejects_unsupported_ioc_type(self) -> None:
        with self.assertRaises(CommandValidationError):
            EnrichIocRequest(ioc_type="email", value="test@example.com")

    def test_request_dto_rejects_blank_value(self) -> None:
        with self.assertRaises(CommandValidationError):
            EnrichIocRequest(ioc_type="sha256", value="   ")

    def test_dispatched_via_command_name(self) -> None:
        fake_client = _FakeVirusTotalClient(
            response={
                "sha256": "b" * 64,
                "found": True,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 70,
                "undetected": 2,
            }
        )
        with patch(
            "app.application.handlers.ThreatIntelService",
            return_value=ThreatIntelService(virustotal=fake_client),
        ):
            response = dispatch(
                "enrich_ioc", {"ioc_type": "sha256", "value": "b" * 64}
            )

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["verdict"], "Clean")
        self.assertEqual(fake_client.lookups, ["b" * 64])


class EnrichIocDispatchErrorTranslationTests(unittest.TestCase):
    """`lookup_indicator` propagates failures directly (unlike
    `enrich_results`), so unlike this file's other
    DispatchErrorTranslationTests cases (which patch a *different*
    exception onto an existing method), these drive
    `EnrichIocCommandHandler`'s one real dependency
    (`ThreatIntelService.lookup_indicator`) through its own documented
    exception paths and assert `dispatch()`'s generic boundary
    translates each to the matching `errors.py` TI_* code.
    """

    def test_invalid_ioc_value_translates_to_ti_invalid_ioc(self) -> None:
        fake_client = _FakeVirusTotalClient(error=InvalidHashError("bad hash"))
        with patch(
            "app.application.handlers.ThreatIntelService",
            return_value=ThreatIntelService(virustotal=fake_client),
        ):
            response = dispatch(
                "enrich_ioc", {"ioc_type": "sha256", "value": "not-a-hash"}
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "TI_INVALID_IOC")

    def test_rate_limit_translates_to_ti_rate_limited(self) -> None:
        fake_client = _FakeVirusTotalClient(error=RateLimitExceededError("slow down"))
        with patch(
            "app.application.handlers.ThreatIntelService",
            return_value=ThreatIntelService(virustotal=fake_client),
        ):
            response = dispatch(
                "enrich_ioc", {"ioc_type": "sha256", "value": "a" * 64}
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "TI_RATE_LIMITED")

    def test_invalid_api_key_translates_to_ti_invalid_api_key(self) -> None:
        fake_client = _FakeVirusTotalClient(error=InvalidAPIKeyError("bad key"))
        with patch(
            "app.application.handlers.ThreatIntelService",
            return_value=ThreatIntelService(virustotal=fake_client),
        ):
            response = dispatch(
                "enrich_ioc", {"ioc_type": "sha256", "value": "a" * 64}
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "TI_INVALID_API_KEY")


class EnrichIocEventLoopRegressionTests(unittest.TestCase):
    """PHASE4D_SSE_PART2_IMPLEMENTATION.md Stage 7 'Event-loop regression'
    (items 11-13) -- CRITICAL, per that Part's task brief: this must
    actually execute the enrichment path from inside a running asyncio
    event loop and confirm no RuntimeError, not merely assert the fix
    exists by inspection.

    Confirmed hazard being regression-tested: before the Part 2 fix,
    `EnrichIocCommandHandler.handle()` called
    `ThreatIntelService._lookup_raw()`, which calls
    `asyncio.run(provider.lookup_raw(ioc))` (service.py:223) directly on
    the calling thread. `asyncio.run()` raises `RuntimeError: asyncio.run()
    cannot be called from a running event loop` if the calling thread
    already has one running -- exactly the situation a future FastAPI
    `async def run_command()` route creates (it calls the dispatch table
    directly on the request coroutine's own thread; see
    docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md S2). This test
    reproduces that exact calling shape (a synchronous call to
    `handler.handle()` made from *inside* a coroutine running on
    `asyncio.run()`'s own loop) without needing fastapi installed.
    """

    def test_enrich_ioc_from_a_running_event_loop_does_not_raise(self) -> None:
        fake_client = _FakeVirusTotalClient(
            response={
                "sha256": "e" * 64,
                "found": True,
                "malicious": 3,
                "suspicious": 0,
                "harmless": 68,
                "undetected": 0,
            }
        )
        handler = EnrichIocCommandHandler(
            ThreatIntelService(virustotal=fake_client), broker=EventBroker()
        )
        request = EnrichIocRequest(ioc_type="sha256", value="e" * 64)

        loop_was_running: list[bool] = []

        async def _call_synchronous_handler_from_coroutine():
            # This is the hazard shape: a plain (non-awaited) call to a
            # synchronous function, made from code that is itself running
            # on an active event loop -- exactly what an async FastAPI
            # route body calling dispatch()/handler.handle() directly
            # would do.
            loop_was_running.append(asyncio.get_running_loop().is_running())
            return handler.handle(request)

        # asyncio.run() here plays the role of uvicorn's own loop --
        # there IS a running loop for the whole duration of this call.
        response, collector = asyncio.run(_call_synchronous_handler_from_coroutine())

        self.assertEqual(loop_was_running, [True])
        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["sha256"], "e" * 64)
        self.assertEqual([e.event for e in collector.events], [
            "ti.enrichment.started",
            "ti.enrichment.completed",
        ])

    def test_enrich_ioc_failure_from_a_running_event_loop_still_translates_correctly(
        self,
    ) -> None:
        fake_client = _FakeVirusTotalClient(error=InvalidHashError("bad hash"))
        handler = EnrichIocCommandHandler(
            ThreatIntelService(virustotal=fake_client), broker=EventBroker()
        )
        request = EnrichIocRequest(ioc_type="sha256", value="not-a-hash")

        async def _call_from_coroutine():
            with self.assertRaises(InvalidHashError):
                handler.handle(request)

        # No RuntimeError from a nested asyncio.run() is raised, and the
        # ORIGINAL domain exception still propagates unchanged (so
        # dispatch()'s outer boundary can still translate it) -- the fix
        # changes *which thread* runs the blocking call, not what it
        # returns or raises.
        asyncio.run(_call_from_coroutine())


class EnrichIocConcurrencyTests(unittest.TestCase):
    """PHASE4D_SSE_PART2_IMPLEMENTATION.md Stage 7 'Concurrency'
    (items 14-16)."""

    def test_concurrent_enrichments_do_not_corrupt_each_others_results(self) -> None:
        broker = EventBroker()
        n = 8
        handlers_and_requests = []
        for i in range(n):
            value = f"{i % 10}" * 64
            fake_client = _FakeVirusTotalClient(
                response={
                    "sha256": value,
                    "found": True,
                    "malicious": i,
                    "suspicious": 0,
                    "harmless": 71 - i,
                    "undetected": 0,
                }
            )
            handler = EnrichIocCommandHandler(
                ThreatIntelService(virustotal=fake_client), broker=broker
            )
            handlers_and_requests.append(
                (handler, EnrichIocRequest(ioc_type="sha256", value=value))
            )

        results: list[tuple[int, dict]] = []
        lock = threading.Lock()

        def run_one(index: int, handler, request) -> None:
            response, _collector = handler.handle(request)
            with lock:
                results.append((index, response))

        threads = [
            threading.Thread(target=run_one, args=(i, h, r))
            for i, (h, r) in enumerate(handlers_and_requests)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(results), n)
        for index, response in results:
            expected_value = f"{index % 10}" * 64
            self.assertTrue(response["success"])
            self.assertEqual(response["data"]["sha256"], expected_value)
            self.assertEqual(response["data"]["malicious"], index)

    def test_broker_publication_is_thread_safe_under_concurrent_enrichment(self) -> None:
        broker = EventBroker(capacity=256)
        n = 10

        with broker.subscription() as sub:
            def run_one(i: int) -> None:
                fake_client = _FakeVirusTotalClient(
                    response={
                        "sha256": "f" * 64,
                        "found": True,
                        "malicious": 0,
                        "suspicious": 0,
                        "harmless": 71,
                        "undetected": 0,
                    }
                )
                handler = EnrichIocCommandHandler(
                    ThreatIntelService(virustotal=fake_client), broker=broker
                )
                handler.handle(EnrichIocRequest(ioc_type="sha256", value="f" * 64))

            threads = [threading.Thread(target=run_one, args=(i,)) for i in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            delivered = sub.drain()

        # Each of the n concurrent calls publishes exactly 2 events
        # (started, completed); the broker must deliver all 2n with no
        # loss, no duplication, and no corrupted/interleaved payloads.
        self.assertEqual(len(delivered), 2 * n)
        started_count = sum(1 for e in delivered if e.event == "ti.enrichment.started")
        completed_count = sum(1 for e in delivered if e.event == "ti.enrichment.completed")
        self.assertEqual(started_count, n)
        self.assertEqual(completed_count, n)
        for event in delivered:
            self.assertEqual(event.payload["ioc_type"], "sha256")
            self.assertEqual(event.payload["value"], "f" * 64)

    def test_one_failed_enrichment_does_not_poison_subsequent_requests(self) -> None:
        broker = EventBroker()

        failing_client = _FakeVirusTotalClient(
            error=ThreatIntelConnectionError("connection reset")
        )
        failing_handler = EnrichIocCommandHandler(
            ThreatIntelService(virustotal=failing_client), broker=broker
        )
        with self.assertRaises(ThreatIntelConnectionError):
            failing_handler.handle(EnrichIocRequest(ioc_type="sha256", value="a" * 64))

        # The shared worker-thread pool (app/application/execution.py) must
        # not be left in a state where a prior exception breaks later
        # submissions -- run several more, including via a fresh
        # ThreadPoolExecutor of callers, and confirm they all succeed.
        def run_and_assert_success(i: int) -> None:
            value = f"{i}" * 64
            fake_client = _FakeVirusTotalClient(
                response={
                    "sha256": value,
                    "found": True,
                    "malicious": 0,
                    "suspicious": 0,
                    "harmless": 71,
                    "undetected": 0,
                }
            )
            handler = EnrichIocCommandHandler(
                ThreatIntelService(virustotal=fake_client), broker=broker
            )
            response, _collector = handler.handle(
                EnrichIocRequest(ioc_type="sha256", value=value)
            )
            assert response["success"], response

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(run_and_assert_success, i) for i in range(6)]
            for future in futures:
                future.result(timeout=10)


if __name__ == "__main__":
    unittest.main()
