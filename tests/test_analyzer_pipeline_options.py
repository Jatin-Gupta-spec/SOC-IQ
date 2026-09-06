"""
Phase 4I Remediation, Blocker B, Part 2B: proves analyze_report's three
optional pipeline stages (extract_iocs / enrich_ti / score_risk) are
genuinely SKIPPED -- not run-and-discarded -- when their flag is False,
and that the disabled result is honest (no fabricated IOCs/TI/risk).

Written with stdlib unittest (no pytest network dependency), matching
tests/test_application_layer.py's own convention and rationale.

Like AnalyzeReportCommandHandlerTests in test_application_layer.py,
analyze_report is not repository-injectable, so each test snapshots/
restores the real database/soc_iq.db file and uses a uniquely-named
report file per test -- reusing one filename across tests would trip
the duplicate-investigation short-circuit (`exists_by_report_name`)
and silently skip re-running the pipeline on the second test.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app.analyzer import analyze_report
from app.config import DATABASE_PATH
from app.database.service import InvestigationService

_SAMPLE_REPORT_TEXT = (
    "SOC-IQ Test Report\n"
    "Suspicious IP: 203.0.113.55\n"
    "Suspicious domain: malicious-example.com\n"
    "Suspicious URL: http://malicious-example.com/payload\n"
    "SHA256: "
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n"
)


class _PipelineOptionsTestCase(unittest.TestCase):
    """Shared DB snapshot/restore + unique-report-path helper."""

    def setUp(self) -> None:
        self._db_backup = None
        if DATABASE_PATH.exists():
            fd, backup_path = tempfile.mkstemp(suffix=".db")
            import os

            os.close(fd)
            shutil.copy2(DATABASE_PATH, backup_path)
            self._db_backup = Path(backup_path)

        self._tmpdir = tempfile.mkdtemp()
        self._created_investigation_ids: list[int] = []

    def tearDown(self) -> None:
        for investigation_id in self._created_investigation_ids:
            InvestigationService().delete(investigation_id)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        if self._db_backup is not None:
            shutil.copy2(self._db_backup, DATABASE_PATH)
            self._db_backup.unlink(missing_ok=True)

    def _unique_report_path(self, prefix: str) -> Path:
        # Unique filename per test/call -- report_path.name is the
        # duplicate-investigation key, so reusing one across tests
        # would make the second call return the cached investigation
        # instead of re-running the pipeline.
        path = Path(self._tmpdir) / f"{prefix}-{uuid.uuid4().hex}.txt"
        path.write_text(_SAMPLE_REPORT_TEXT, encoding="utf-8")
        return path

    def _analyze(self, prefix: str, **kwargs) -> dict:
        report_path = self._unique_report_path(prefix)
        result = analyze_report(report_path, **kwargs)
        investigation = result["investigation"]
        if investigation.investigation_id is not None:
            self._created_investigation_ids.append(investigation.investigation_id)
        return result


class ExtractIocsEnforcementTests(_PipelineOptionsTestCase):
    def test_extract_iocs_true_executes_extraction(self) -> None:
        with patch(
            "app.analyzer.extract_iocs", wraps=__import__(
                "app.extractor", fromlist=["extract_iocs"]
            ).extract_iocs
        ) as spy:
            result = self._analyze(
                "iocs-true", options={"extract_iocs": True, "enrich_ti": False, "score_risk": False}
            )

        spy.assert_called_once()
        # Real extraction ran: the fixture text has a real IPv4 in it.
        self.assertIn(
            "203.0.113.55", result["investigation"].iocs.get("ipv4", [])
        )

    def test_extract_iocs_false_skips_extraction_entirely(self) -> None:
        with patch("app.analyzer.extract_iocs") as spy:
            spy.side_effect = AssertionError(
                "extract_iocs must not be called when extract_iocs=False"
            )
            result = self._analyze(
                "iocs-false", options={"extract_iocs": False, "enrich_ti": False, "score_risk": False}
            )

        spy.assert_not_called()
        # Honest empty result -- same shape a real (empty) extraction
        # would return, not a fabricated hit.
        investigation = result["investigation"]
        self.assertEqual(investigation.iocs.get("ipv4"), [])
        self.assertNotIn("203.0.113.55", investigation.iocs.get("ipv4", []))


class EnrichTiEnforcementTests(_PipelineOptionsTestCase):
    def test_enrich_ti_true_executes_enrichment(self) -> None:
        # No VirusTotal API key is configured in this sandbox, so a real
        # attempt raises MissingAPIKeyError -- analyze_report's existing
        # (unchanged) except-branch catches it and records
        # reason="missing_api_key". What this test proves is that the
        # service *was instantiated and invoked* (i.e. the stage ran),
        # not that it produced a network-verified hit.
        from app.analyzer import ThreatIntelService as RealThreatIntelService

        with patch(
            "app.analyzer.ThreatIntelService", wraps=RealThreatIntelService
        ) as spy:
            result = self._analyze(
                "ti-true", options={"extract_iocs": True, "enrich_ti": True, "score_risk": False}
            )

        spy.assert_called_once()
        # The stage ran (service constructed); with no API key configured
        # the honest existing outcome is reason="missing_api_key", which
        # is itself proof the code path executed rather than being skipped.
        self.assertEqual(
            result["investigation"].threat_intelligence.get("reason"),
            "missing_api_key",
        )

    def test_enrich_ti_false_skips_enrichment_entirely(self) -> None:
        with patch("app.analyzer.ThreatIntelService") as spy:
            spy.side_effect = AssertionError(
                "ThreatIntelService must not be instantiated when enrich_ti=False"
            )
            result = self._analyze(
                "ti-false", options={"extract_iocs": True, "enrich_ti": False, "score_risk": False}
            )

        spy.assert_not_called()
        threat_intelligence = result["investigation"].threat_intelligence
        self.assertEqual(threat_intelligence.get("status"), "unavailable")
        self.assertEqual(threat_intelligence.get("reason"), "disabled")
        self.assertEqual(threat_intelligence.get("hashes"), [])


class ScoreRiskEnforcementTests(_PipelineOptionsTestCase):
    def test_score_risk_true_executes_scoring(self) -> None:
        from app.analyzer import RiskScoringEngine as RealEngine

        with patch(
            "app.analyzer.RiskScoringEngine", wraps=RealEngine
        ) as spy:
            result = self._analyze(
                "risk-true", options={"extract_iocs": True, "enrich_ti": False, "score_risk": True}
            )

        spy.assert_called_once()
        self.assertIn(
            result["investigation"].severity, {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        )

    def test_score_risk_false_skips_scoring_entirely(self) -> None:
        with patch("app.analyzer.RiskScoringEngine") as spy:
            spy.side_effect = AssertionError(
                "RiskScoringEngine must not be instantiated when score_risk=False"
            )
            result = self._analyze(
                "risk-false", options={"extract_iocs": True, "enrich_ti": False, "score_risk": False}
            )

        spy.assert_not_called()
        investigation = result["investigation"]
        # Honest "not scored" sentinel, not a fabricated 0-risk verdict:
        # distinguishable from any real LOW/MEDIUM/HIGH/CRITICAL severity.
        self.assertEqual(investigation.severity, "NOT_SCORED")
        self.assertEqual(investigation.risk_score, 0)
        self.assertEqual(investigation.confidence, 0.0)
        self.assertEqual(investigation.ioc_score, 0)
        self.assertEqual(investigation.threat_intel_score, 0)
        self.assertEqual(investigation.cve_score, 0)


class AllOptionsTrueBackwardCompatibilityTests(_PipelineOptionsTestCase):
    def test_all_options_true_preserves_normal_analysis_behavior(self) -> None:
        result = self._analyze(
            "all-true", options={"extract_iocs": True, "enrich_ti": True, "score_risk": True}
        )
        investigation = result["investigation"]
        self.assertIn(
            "203.0.113.55", investigation.iocs.get("ipv4", [])
        )
        self.assertIn(investigation.severity, {"LOW", "MEDIUM", "HIGH", "CRITICAL"})
        self.assertNotEqual(investigation.severity, "NOT_SCORED")

    def test_options_none_is_backward_compatible_with_pre_blocker_b_callers(
        self,
    ) -> None:
        # The exact pre-Part-2A call shape: no `options` kwarg at all.
        result = self._analyze("no-options-kwarg")
        investigation = result["investigation"]
        self.assertIn("203.0.113.55", investigation.iocs.get("ipv4", []))
        self.assertNotEqual(investigation.severity, "NOT_SCORED")
        self.assertNotEqual(
            investigation.threat_intelligence.get("reason"), "disabled"
        )

    def test_omitted_keys_in_a_partial_options_dict_default_to_true(self) -> None:
        # Only extract_iocs specified -- enrich_ti/score_risk must still
        # default to True (same rule AnalysisOptions enforces one layer
        # up, mirrored here at the domain layer).
        result = self._analyze("partial-options", options={"extract_iocs": True})
        investigation = result["investigation"]
        self.assertNotEqual(investigation.severity, "NOT_SCORED")
        self.assertNotEqual(
            investigation.threat_intelligence.get("reason"), "disabled"
        )


class ProgressEventHonestyTests(_PipelineOptionsTestCase):
    def test_disabled_stages_do_not_emit_misleading_progress_messages(self) -> None:
        messages: list[str] = []

        def on_progress(percent: int, message: str) -> None:
            messages.append(message)

        self._analyze(
            "progress-honesty",
            options={"extract_iocs": False, "enrich_ti": False, "score_risk": False},
            progress_callback=on_progress,
        )

        joined = " | ".join(messages)
        self.assertIn("Skipping IOC extraction", joined)
        self.assertIn("Skipping Threat Intelligence", joined)
        self.assertIn("Skipping Risk Scoring", joined)
        # Must not claim the disabled stages ran.
        self.assertNotIn("Extracting Indicators of Compromise", joined)
        self.assertNotIn("Running Threat Intelligence", joined)
        self.assertNotIn("Calculating Risk Score", joined)

    def test_enabled_stages_still_emit_their_normal_progress_messages(self) -> None:
        messages: list[str] = []

        def on_progress(percent: int, message: str) -> None:
            messages.append(message)

        self._analyze(
            "progress-normal",
            options={"extract_iocs": True, "enrich_ti": True, "score_risk": True},
            progress_callback=on_progress,
        )

        joined = " | ".join(messages)
        self.assertIn("Extracting Indicators of Compromise", joined)
        self.assertIn("Running Threat Intelligence", joined)
        self.assertIn("Calculating Risk Score", joined)


class DependencyOrderingTests(_PipelineOptionsTestCase):
    def test_risk_scoring_with_extraction_disabled_scores_from_empty_iocs(
        self,
    ) -> None:
        # extract_iocs=False -> empty-but-present iocs dict is what risk
        # scoring (still enabled) consumes -- it must not error, and it
        # must not manufacture IOC-derived score contribution from data
        # that was never extracted.
        result = self._analyze(
            "dep-order",
            options={"extract_iocs": False, "enrich_ti": False, "score_risk": True},
        )
        investigation = result["investigation"]
        self.assertEqual(investigation.ioc_score, 0)
        self.assertIn(investigation.severity, {"LOW", "MEDIUM", "HIGH", "CRITICAL"})


class DisabledStageFailureBehaviorTests(_PipelineOptionsTestCase):
    def test_enabled_stage_failure_still_propagates_as_before(self) -> None:
        with patch("app.analyzer.extract_iocs") as spy:
            spy.side_effect = RuntimeError("boom")
            report_path = self._unique_report_path("failure")
            with self.assertRaises(RuntimeError):
                analyze_report(
                    report_path,
                    options={"extract_iocs": True, "enrich_ti": False, "score_risk": False},
                )


class PersistenceTests(_PipelineOptionsTestCase):
    def test_disabled_stage_result_persists_and_reloads_consistently(self) -> None:
        result = self._analyze(
            "persistence",
            options={"extract_iocs": False, "enrich_ti": False, "score_risk": False},
        )
        investigation_id = result["investigation"].investigation_id
        self.assertIsNotNone(investigation_id)

        reloaded = InvestigationService().get_by_id(investigation_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.severity, "NOT_SCORED")
        self.assertEqual(reloaded.threat_intelligence.get("reason"), "disabled")
        self.assertEqual(reloaded.iocs.get("ipv4"), [])


if __name__ == "__main__":
    unittest.main()
