"""
Phase 4N -- full-stack integration tests, HTTP transport in, real SQLite
database out.

WHY THIS FILE EXISTS
---------------------
tests/test_api_layer.py already proves the FastAPI transport (app/api/app.py)
correctly dispatches to app.application.handlers.COMMAND_HANDLERS -- but its
own module docstring says only read-only commands (list_investigations,
get_investigation, /health, /events) are exercised through TestClient. It
explicitly defers the mutating analyze_report path with this note:

    "the mutating/long-running analyze_report path is already proven at
    the application layer, without a live DB/network dependency, by
    tests/test_application_layer.py; re-exercising it through HTTP would
    require either mocking the transport (defeating the point of this
    file) or hitting the real database ... out of scope for a
    transport-wiring test."

That gap is exactly what Phase 4N (full-stack integration, per
docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md S26)
exists to close: proving frontend-command-shape-in -> HTTP -> command
dispatch -> real repository -> real SQLite -> HTTP response ->
investigation is genuinely retrievable, dashboard-visible, and
exportable, as ONE proven path rather than three separately-proven
layers stitched together only in documentation.

DESIGN, PER THE PHASE 4N TESTING RULES
----------------------------------------
- Uses fastapi.testclient.TestClient against the real `app` object (same
  transport tests/test_api_layer.py uses) -- no mocked transport.
- Uses the real InvestigationRepository / SQLite database -- no mocked
  repository or in-memory fake.
- Uses app.analyzer.analyze_report unmodified (the real extraction ->
  scoring -> persistence pipeline) against a real fixture file in
  samples/.
- The one genuine external boundary (VirusTotal) is not mocked here --
  it is simply not configured (no API key), which is a real, honest
  code path (threat_intelligence status "unavailable" /
  "not_attempted"), not a stubbed success. This keeps the test
  deterministic and offline without pretending a network call happened.
- analyze_report is NOT injectable at the repository level (see
  tests/test_application_layer.py's module docstring -- a confirmed,
  documented architectural gap, not something this file works around).
  Consistent with that file's own precedent, this test snapshots and
  restores the real database/soc_iq.db file around each test rather
  than pretending an injection seam exists that doesn't. This is a
  known limitation for true test isolation, not a defect introduced
  here -- fixing it would mean making the handler's repository
  injectable, which is out of Phase 4N's scope (no architectural
  rewrite).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import app
from app.config import DATABASE_PATH


class _DatabaseSnapshotMixin:
    """Snapshot/restore database/soc_iq.db around a test, matching the
    precedent set by AnalyzeReportCommandHandlerTests in
    tests/test_application_layer.py. Also usable to force a genuinely
    empty database by removing the file entirely before the test runs
    (the repository recreates the schema on first use -- see
    app/database/repository.py's _initialize_database)."""

    def _snapshot_database(self) -> None:
        self._db_backup: Path | None = None
        if DATABASE_PATH.exists():
            fd, backup_path = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            shutil.copy2(DATABASE_PATH, backup_path)
            self._db_backup = Path(backup_path)

    def _restore_database(self) -> None:
        if self._db_backup is not None:
            shutil.copy2(self._db_backup, DATABASE_PATH)
            self._db_backup.unlink(missing_ok=True)
        elif DATABASE_PATH.exists():
            # No prior file existed -- leave the environment as we found it.
            DATABASE_PATH.unlink(missing_ok=True)


class AnalyzeReportFullStackHTTPIntegrationTests(
    _DatabaseSnapshotMixin, unittest.TestCase
):
    """
    Acceptance criterion A from the Phase 4N task brief:

        Input report -> extraction -> TI enrichment -> risk scoring ->
        investigation persistence -> returned investigation ID ->
        frontend-visible investigation

    exercised end-to-end through the real HTTP transport, with every
    layer genuine except the network-bound VT provider (not configured,
    not mocked -- see module docstring).
    """

    def setUp(self) -> None:
        self._snapshot_database()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self._restore_database()

    def test_analyze_report_persists_and_is_retrievable_through_http(self) -> None:
        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")

        # A: analyze_report over real HTTP -> real pipeline -> real DB.
        analyze_response = self.client.post(
            "/commands/analyze_report",
            json={"report_path": str(sample)},
        )
        self.assertEqual(analyze_response.status_code, 200)
        analyze_body = analyze_response.json()
        self.assertTrue(analyze_body["success"], msg=analyze_body.get("error"))

        investigation_summary = analyze_body["data"]["investigation"]
        investigation_id = investigation_summary["investigation_id"]
        self.assertIsInstance(investigation_id, int)

        # B: the same investigation is retrievable through a *separate*
        # HTTP request/response cycle -- proving persistence actually
        # happened in SQLite, not just in an in-process return value.
        get_response = self.client.post(
            "/commands/get_investigation",
            json={"investigation_id": investigation_id},
        )
        self.assertEqual(get_response.status_code, 200)
        get_body = get_response.json()
        self.assertTrue(get_body["success"], msg=get_body.get("error"))
        self.assertEqual(
            get_body["data"]["investigation_id"], investigation_id
        )
        self.assertEqual(get_body["data"]["report_name"], sample.name)

        # C: Dashboard -- the freshly-persisted investigation is
        # reflected in the aggregate dashboard command, proving the
        # dashboard reads from the same real database rather than a
        # separately-seeded fixture.
        dashboard_response = self.client.post(
            "/commands/get_dashboard_summary", json={}
        )
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_body = dashboard_response.json()
        self.assertTrue(dashboard_body["success"], msg=dashboard_body.get("error"))
        self.assertGreaterEqual(
            dashboard_body["data"]["metrics"]["total_reports"], 1
        )

        # D: Reporting -- export_report against the just-created
        # investigation, over HTTP, proving the reporting layer can
        # read what analyze_report (also over HTTP) just wrote.
        export_response = self.client.post(
            "/commands/export_report",
            json={
                "investigation_id": investigation_id,
                "export_format": "json",
                "output_path": str(Path(tempfile.gettempdir()) / "phase4n_export.json"),
            },
        )
        self.assertEqual(export_response.status_code, 200)
        export_body = export_response.json()
        self.assertTrue(export_body["success"], msg=export_body.get("error"))

    def test_analyze_report_error_path_propagates_honestly_through_http(self) -> None:
        """E: Error path -- a genuinely missing report file produces a
        real domain-level REPORT_NOT_FOUND error, propagated through the
        handler and the HTTP envelope unchanged (not swallowed into a
        200/success, not turned into a 500)."""

        response = self.client.post(
            "/commands/analyze_report",
            json={"report_path": "/nonexistent/report/path.txt"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "REPORT_NOT_FOUND")


class AnalysisOptionsHTTPIntegrationTests(_DatabaseSnapshotMixin, unittest.TestCase):
    """
    Phase 4N Part 2 -- acceptance criterion B (Analysis options).

    tests/test_analyzer_pipeline_options.py already proves each option
    flag (extract_iocs/enrich_ti/score_risk) is genuinely enforced at
    the domain layer (app.analyzer.analyze_report). What it does not
    cover -- and what this class adds -- is that the *same* enforcement
    survives the full path a real frontend request actually takes:
    JSON body -> AnalyzeReportRequest/AnalysisOptions DTO validation ->
    handler -> domain pipeline -> persisted investigation, all through
    the real HTTP transport. This is a genuinely new integration point
    (DTO parsing of the `options` sub-object over the wire), not a
    re-run of the already-covered domain-level enforcement.
    """

    def setUp(self) -> None:
        self._snapshot_database()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self._restore_database()

    def test_enrich_ti_false_is_honored_through_http_and_persists_disabled(
        self,
    ) -> None:
        sample = Path("samples") / "report4.txt"
        response = self.client.post(
            "/commands/analyze_report",
            json={
                "report_path": str(sample),
                "options": {
                    "extract_iocs": True,
                    "enrich_ti": False,
                    "score_risk": True,
                },
            },
        )
        body = response.json()
        self.assertTrue(body["success"], msg=body.get("error"))
        # The handler forwards the validated options back in the
        # envelope (app/application/handlers.py
        # AnalyzeReportCommandHandler.handle) -- proving the DTO the
        # wire payload was parsed into is the same one that reached the
        # domain pipeline, not a silently-defaulted copy.
        self.assertEqual(body["data"]["options"]["enrich_ti"], False)

        investigation_id = body["data"]["investigation"]["investigation_id"]
        ti_response = self.client.post(
            "/commands/get_threat_intelligence",
            json={"investigation_id": investigation_id},
        )
        ti_body = ti_response.json()
        self.assertTrue(ti_body["success"], msg=ti_body.get("error"))
        # Disabled-stage semantics (per
        # tests/test_analyzer_pipeline_options.py's
        # EnrichTiEnforcementTests): reason is "not_attempted", never
        # the failure reason "error"/"missing_api_key" a *ran-but-failed*
        # stage would produce -- proving this was skipped, not silently
        # broken.
        self.assertEqual(
            ti_body["data"]["threat_intelligence"]["reason"], "disabled"
        )

    def test_malformed_options_are_rejected_before_any_pipeline_work_over_http(
        self,
    ) -> None:
        sample = Path("samples") / "report4.txt"
        response = self.client.post(
            "/commands/analyze_report",
            json={
                "report_path": str(sample),
                "options": {"enrich_ti": "yes"},  # not a bool
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "INVALID_COMMAND_PAYLOAD")

        # G/Security corollary: rejecting the request must not have
        # persisted anything -- confirmed via a second, independent HTTP
        # call, not just by trusting the error response.
        list_response = self.client.post("/commands/list_investigations", json={})
        matching = [
            inv
            for inv in list_response.json()["data"]
            if inv["report_name"] == sample.name
        ]
        self.assertEqual(matching, [])


class SecretLeakageHTTPRegressionTests(_DatabaseSnapshotMixin, unittest.TestCase):
    """
    Phase 4N Part 2 S4 -- security regression, exercised for real rather
    than asserted from reading code: attempt to save a real (fake-value)
    VirusTotal API key over the actual HTTP transport, then inspect
    every response/event byte this session produces for that literal
    value. Confirms docs/security/secret-management-model.md's
    "log-safe, disk-unsafe" intent holds at the wire level, not just by
    source inspection.

    MAX19A-F-01 update: `save_settings(virustotal_api_key=...)` used to
    reach the real, read-only production SecretStore
    (RustKeystoreHandoffSecretStore) and fail there with
    SecretStoreReadOnlyError -- reachable, always-failing dead
    capability. It is now rejected earlier, at the DTO layer
    (`SaveSettingsRequest.__post_init__`), with a `CommandValidationError`
    pointing callers at the real write path (`keystore_set_secret`).
    Either way the key was never actually persisted by this call, so
    the leakage properties this class checks hold unchanged.
    """

    def setUp(self) -> None:
        self._snapshot_database()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self._restore_database()

    def test_saved_api_key_never_appears_in_the_save_response_envelope(
        self,
    ) -> None:
        marker_secret = "PHASE4N-SECURITY-REGRESSION-CANARY-KEY-abc123"

        response = self.client.post(
            "/commands/save_settings",
            json={"virustotal_api_key": marker_secret},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()

        # ARCHITECTURE NOTE (MAX19A-F-01, superseding the Phase 4O
        # Security Part 1B-2 / ADR-008 note this test used to carry):
        # `save_settings(virustotal_api_key=...)` used to be fully
        # wired end-to-end and reach the real, read-only production
        # SecretStore (RustKeystoreHandoffSecretStore), where it
        # deterministically failed with SecretStoreReadOnlyError --
        # dead capability, reachable over the same HTTP endpoint the
        # frontend uses for Theme/Export Directory, that could never
        # once succeed. `SaveSettingsRequest.__post_init__` now rejects
        # this field outright, before the request ever reaches
        # SettingsService/the secret store at all, with a
        # CommandValidationError pointing callers at the real,
        # live write path (`keystore_set_secret`, direct Tauri IPC).
        #
        # The security property this test exists to check -- the
        # secret must never appear in the response payload -- still
        # holds, and now holds for a stronger reason: the value never
        # reaches any store call, real or fake, at all.
        self.assertNotIn(marker_secret, response.text)

        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "INVALID_COMMAND_PAYLOAD")
        self.assertIn("keystore_set_secret", body["error"]["message"])

    def test_analysis_events_and_investigation_responses_never_carry_the_key(
        self,
    ) -> None:
        marker_secret = "PHASE4N-SECURITY-REGRESSION-CANARY-KEY-def456"
        # Per MAX19A-F-01, this save_settings call is now rejected
        # outright at the DTO layer (see the test above) and never
        # reaches any store -- exactly as before this fix, when it
        # reached the real read-only production store and failed there
        # instead. Either way, the marker was never actually persisted;
        # this test's job is only to confirm it never echoes back
        # through any other command's response, which holds regardless
        # of which layer rejects the save.
        self.client.post(
            "/commands/save_settings", json={"virustotal_api_key": marker_secret}
        )

        sample = Path("samples") / "report4.txt"
        analyze_response = self.client.post(
            "/commands/analyze_report", json={"report_path": str(sample)}
        )
        self.assertNotIn(marker_secret, analyze_response.text)

        investigation_id = analyze_response.json()["data"]["investigation"][
            "investigation_id"
        ]
        for command, payload in (
            ("get_investigation", {"investigation_id": investigation_id}),
            ("get_threat_intelligence", {"investigation_id": investigation_id}),
            ("get_dashboard_summary", {}),
        ):
            resp = self.client.post(f"/commands/{command}", json=payload)
            self.assertNotIn(
                marker_secret,
                resp.text,
                msg=f"secret leaked via /commands/{command}",
            )


class ThreatIntelAsyncTransportRegressionTest(_DatabaseSnapshotMixin, unittest.TestCase):
    """
    R1 CLOSURE -- was `ThreatIntelAsyncTransportDefectRegressionTest`
    (Phase 4N audit), which pinned down a confirmed defect rather than
    fixing it: `app.threat_intel.service.ThreatIntelService._lookup_raw`
    bridges its provider's `async lookup_raw()` onto a synchronous
    caller via `asyncio.run(...)`, and `app/api/app.py`'s
    `POST /commands/{name}` route is `async def` -- so calling that
    chain inline, on the request coroutine's own thread, hit a hard
    `RuntimeError: asyncio.run() cannot be called from a running event
    loop` the moment threat-intel enrichment was reached through the
    real HTTP transport, masked by app/analyzer.py's broad `except
    Exception` into `{"status": "unavailable", "reason": "error"}`.

    R1 fixed this at `AnalyzeReportCommandHandler.handle()`
    (app/application/handlers.py): `domain_analyze_report` now runs via
    `run_blocking()` (app/application/execution.py) -- the same
    worker-thread boundary `EnrichIocCommandHandler` already used for
    this exact hazard -- so `asyncio.run()` inside `_lookup_raw` always
    executes on a plain worker thread that never has a running event
    loop of its own, regardless of the calling (request) thread's own
    loop state.

    This class now proves the *corrected* behavior, still through the
    real HTTP transport (no direct handler call, per R1's requirement
    C) -- and is a genuine regression test: it fails on the pre-fix
    implementation (see the masked `"error"` reason class docstring
    above described) and passes on the corrected one.
    """

    def setUp(self) -> None:
        self._snapshot_database()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self._restore_database()

    def test_no_api_key_reason_is_honest_missing_api_key_not_masked_error(
        self,
    ) -> None:
        """
        With no VirusTotal API key configured (this test's environment),
        the *honest* domain outcome is `MissingAPIKeyError` propagating
        out of `ThreatIntelService.enrich_results` uncaught, which
        `app/analyzer.py` translates into
        `{"status": "unavailable", "reason": "missing_api_key"}`.

        Before R1, that `MissingAPIKeyError` was never reached: the
        nested `asyncio.run()` raised `RuntimeError` first, on the very
        first indicator lookup, and app/analyzer.py's broad `except
        Exception` caught *that* instead, producing the generic
        `reason: "error"` -- masking the real, more specific reason.
        Asserting `"missing_api_key"` here therefore proves both that
        the `RuntimeError` no longer occurs AND that the real provider
        code path (as far as its own "no key" check) was genuinely
        reached through the real async HTTP transport -- not merely
        that some exception was caught.
        """

        sample = Path("samples") / "report4.txt"
        response = self.client.post(
            "/commands/analyze_report", json={"report_path": str(sample)}
        )
        body = response.json()
        self.assertTrue(body["success"], msg=body.get("error"))

        investigation_id = body["data"]["investigation"]["investigation_id"]

        ti_response = self.client.post(
            "/commands/get_threat_intelligence",
            json={"investigation_id": investigation_id},
        )
        ti_body = ti_response.json()
        self.assertTrue(ti_body["success"], msg=ti_body.get("error"))
        threat_intelligence = ti_body["data"]["threat_intelligence"]
        self.assertEqual(threat_intelligence["status"], "unavailable")
        self.assertEqual(threat_intelligence["reason"], "missing_api_key")

    def test_provider_is_actually_invoked_and_its_result_reaches_the_response(
        self,
    ) -> None:
        """
        R1 requirement D: using the project's existing
        dependency-injection seam for the VirusTotal provider
        (`app.threat_intel.virustotal_provider.VirusTotalProvider`,
        the same class `ThreatIntelService()` constructs by default --
        see that module and `ThreatIntelService.__init__`), replace
        only its `lookup_raw()` coroutine with a fake that returns a
        fixed, successful raw VirusTotal-shaped result -- no real
        network call, no `VirusTotalClient` involved -- and prove,
        through the real async HTTP transport (`AnalyzeReportCommandHandler`
        -> `analyzer.analyze_report` -> `ThreatIntelService.enrich_results`
        -> `VirusTotalProvider.lookup_raw`), that:

        1. the fake provider is genuinely invoked (call count > 0);
        2. the fixed result it returns reaches the persisted
           investigation's `threat_intelligence` payload, retrieved via
           a *separate* HTTP request/response cycle
           (`get_threat_intelligence`), the same persistence-proof
           pattern `AnalyzeReportFullStackHTTPIntegrationTests` already
           uses above;
        3. enrichment status is `"ok"` -- not `"unavailable"` -- which
           is only reachable if every one of `report4.txt`'s IPs/
           domains/URLs was looked up without a nested-event-loop
           `RuntimeError` aborting the very first lookup.
        """

        fake_raw_result = {
            "found": True,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 12,
            "undetected": 3,
            "reputation": 0,
            "last_analysis_date": None,
            "permalink": "https://example.invalid/r1-fake-vt-result",
        }

        async def fake_lookup_raw(self, ioc):  # noqa: ANN001 -- test double
            fake_lookup_raw.calls.append(ioc.value)
            return dict(fake_raw_result)

        fake_lookup_raw.calls = []

        sample = Path("samples") / "report4.txt"

        with unittest.mock.patch(
            "app.threat_intel.virustotal_provider.VirusTotalProvider.lookup_raw",
            new=fake_lookup_raw,
        ):
            response = self.client.post(
                "/commands/analyze_report", json={"report_path": str(sample)}
            )

        body = response.json()
        self.assertTrue(body["success"], msg=body.get("error"))

        # 1. The fake provider was genuinely invoked -- report4.txt's
        # extracted IOCs are 3 IPs, 2 URLs, and 1 SHA256 hash (0
        # domains -- app.extractor's "domains" pattern does not match
        # any of report4.txt's domain-shaped strings independently of
        # the URLs that already contain them), so a fully successful
        # enrichment invokes the provider exactly 6 times. Confirmed
        # directly against app.extractor.extract_iocs rather than
        # assumed from the sample file's prose "Domains" section
        # header.
        self.assertEqual(len(fake_lookup_raw.calls), 6)

        investigation_id = body["data"]["investigation"]["investigation_id"]

        # 2. Retrieved via a SEPARATE HTTP request/response cycle --
        # proving the result was actually persisted, not merely
        # returned in-process from the same call.
        ti_response = self.client.post(
            "/commands/get_threat_intelligence",
            json={"investigation_id": investigation_id},
        )
        ti_body = ti_response.json()
        self.assertTrue(ti_body["success"], msg=ti_body.get("error"))
        threat_intelligence = ti_body["data"]["threat_intelligence"]

        # 3. status "ok": every requested indicator succeeded -- only
        # reachable if the nested-event-loop RuntimeError does not
        # abort enrichment on the very first lookup.
        self.assertEqual(threat_intelligence["status"], "ok")
        self.assertEqual(threat_intelligence["coverage"]["succeeded"], 6)
        self.assertEqual(threat_intelligence["coverage"]["failed"], 0)

        # The fixed fake result genuinely reached the persisted,
        # HTTP-retrieved payload (not just "some result" -- this exact
        # one, verdict-annotated by the real _format_verdict path).
        self.assertEqual(len(threat_intelligence["ips"]), 3)
        for enriched_ip in threat_intelligence["ips"]:
            self.assertEqual(enriched_ip["permalink"], fake_raw_result["permalink"])
            self.assertEqual(enriched_ip["verdict"], "Clean")


class EmptyDatabaseHTTPIntegrationTests(_DatabaseSnapshotMixin, unittest.TestCase):
    """
    F: Empty path -- no investigations -> command response -> an honest
    empty state, exercised against a genuinely empty (freshly-created,
    not just filtered) real SQLite database, through real HTTP.
    """

    def setUp(self) -> None:
        self._snapshot_database()
        DATABASE_PATH.unlink(missing_ok=True)
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self._restore_database()

    def test_list_investigations_is_honestly_empty(self) -> None:
        response = self.client.post("/commands/list_investigations", json={})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"], msg=body.get("error"))
        self.assertEqual(body["data"], [])

    def test_dashboard_summary_is_honestly_zeroed(self) -> None:
        response = self.client.post("/commands/get_dashboard_summary", json={})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"], msg=body.get("error"))
        self.assertEqual(body["data"]["metrics"]["total_reports"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
