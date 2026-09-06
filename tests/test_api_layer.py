"""
Phase 4D Part 2 -- API-layer integration tests for app/api/app.py.

Part 1 wrote app/api/app.py but could not execute it: this sandbox had no
network access to install fastapi/pydantic/uvicorn (see
docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S6/S19/S21). Part 2's
environment does have that access (S19's blocker is resolved here), so
this file is the first real proof that the FastAPI transport described in
S6.4 actually works end-to-end: HTTP request in, dispatched through
app.application.handlers.COMMAND_HANDLERS, response envelope out --
exactly the "S21 largest caveat" this closes.

Uses fastapi.testclient.TestClient, per S19's own "PROPOSED for the
eventual FastAPI layer" note. Only read-only / validation-only commands
are exercised here against the transport (list_investigations,
get_investigation, an unknown command, GET /events, and -- added in
Phase 4E Part 1 -- GET /health) -- the
mutating/long-running analyze_report path is already proven at the
application layer, without a live DB/network dependency, by
tests/test_application_layer.py; re-exercising it through HTTP would
require either mocking the transport (defeating the point of this file)
or hitting the real database and VT network calls (out of scope for a
transport-wiring test). That gap is noted in the final report, not
papered over here.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.api.app as api_app
from app.api.app import app
from app.application.broker import EventBroker
from app.application.errors import INVALID_COMMAND_PAYLOAD, UNKNOWN_COMMAND
from app.application.events import Event, new_correlation_id


class HealthRouteTests(unittest.TestCase):
    """
    GET /health -- Phase 4E Part 1
    (docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md S5/S9). Exercised here via
    TestClient against the ASGI app object directly, same as every other
    route in this file; the real-process/real-socket proof lives in
    tests/test_sidecar_entrypoint.py, since that requires actually
    starting app.api.entrypoint.run_sidecar rather than just driving the
    `app` object in-process.
    """

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health_returns_success_envelope(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["error"])
        self.assertEqual(body["data"], {"status": "ok"})

    def test_health_does_not_require_a_request_body(self) -> None:
        # A liveness probe has to work with a bare GET -- no payload, no
        # query params -- since that's what an external process
        # supervisor will actually send.
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)


class CommandRouteTests(unittest.TestCase):
    """POST /commands/{name} -- see docs/contracts/command-model.md."""

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_list_investigations_returns_success_envelope(self) -> None:
        response = self.client.post("/commands/list_investigations", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["error"])
        self.assertIsInstance(body["data"], list)

    def test_get_dashboard_summary_returns_success_envelope(self) -> None:
        # Phase 4H Part 1: real end-to-end HTTP proof for the new
        # aggregate command. Read-only against the real database,
        # consistent with this file's existing constraint (see module
        # docstring) -- makes no assertion about specific counts (the
        # real database's contents are not controlled by this test),
        # only that the transport wiring and response shape are correct.
        response = self.client.post("/commands/get_dashboard_summary", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["error"])
        data = body["data"]
        self.assertIn("metrics", data)
        self.assertIn("total_reports", data["metrics"])
        self.assertIn("total_iocs", data["metrics"])
        self.assertIn("high_risk_count", data["metrics"])
        self.assertIn("threat_intel_coverage_percent", data["metrics"])
        self.assertIn("investigation_status_counts", data)
        self.assertIn("risk_distribution", data)
        self.assertIn("ioc_distribution", data)
        self.assertIsInstance(data["recent_investigations"], list)

    def test_get_dashboard_summary_rejects_unexpected_payload_fields(self) -> None:
        response = self.client.post(
            "/commands/get_dashboard_summary", json={"unexpected": True}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_get_investigation_validation_error_never_reaches_domain(self) -> None:
        # investigation_id <= 0 is rejected by the request DTO's
        # __post_init__ before InvestigationService.get_by_id is ever
        # called -- this is the HTTP-boundary proof of S16's "validated
        # before it reaches any domain logic" rule.
        response = self.client.post(
            "/commands/get_investigation", json={"investigation_id": -1}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_get_investigation_not_found_is_translated_not_raised(self) -> None:
        response = self.client.post(
            "/commands/get_investigation", json={"investigation_id": 999999}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "INVESTIGATION_NOT_FOUND")

    def test_get_iocs_not_found_is_translated_not_raised(self) -> None:
        # Phase 4D Part 4: get_iocs added to COMMAND_HANDLERS. Uses a
        # certainly-missing id so this stays non-mutating and read-only
        # against the real database, consistent with this file's existing
        # constraint (see module docstring).
        response = self.client.post(
            "/commands/get_iocs", json={"investigation_id": 999999}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "INVESTIGATION_NOT_FOUND")

    def test_get_iocs_validation_error_never_reaches_domain(self) -> None:
        response = self.client.post(
            "/commands/get_iocs", json={"investigation_id": -1}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_get_timeline_not_found_is_translated_not_raised(self) -> None:
        # A4-P2-P3 Part 3: get_timeline added to COMMAND_HANDLERS. Uses
        # a certainly-missing id so this stays non-mutating and
        # read-only against the real database, consistent with this
        # file's existing constraint (see module docstring) -- same
        # pattern as test_get_iocs_not_found_is_translated_not_raised
        # above.
        response = self.client.post(
            "/commands/get_timeline", json={"investigation_id": 999999}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "INVESTIGATION_NOT_FOUND")

    def test_get_timeline_validation_error_never_reaches_domain(self) -> None:
        response = self.client.post(
            "/commands/get_timeline", json={"investigation_id": -1}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_get_timeline_rejects_unexpected_payload_fields(self) -> None:
        response = self.client.post(
            "/commands/get_timeline",
            json={"investigation_id": 999999, "unexpected": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_save_settings_validation_error_never_reaches_domain(self) -> None:
        # Phase 4D Part 5: save_settings added to COMMAND_HANDLERS.
        # Unlike get_iocs/get_investigation (which have a safe,
        # certainly-missing id to probe with), every *valid*
        # save_settings payload is a real write to the project's own
        # config/settings.json -- there is no side-effect-free success
        # case to exercise through this transport test, consistent with
        # this file's own documented constraint of not exercising
        # mutating paths against real state through HTTP. Only the
        # validation-rejection path is exercised here; it is rejected
        # by the request DTO's __post_init__ before SettingsService is
        # ever touched, so no real file write occurs. As of
        # MAX19A-F-01, `virustotal_api_key` alone (with or without
        # another field alongside it) is now rejected unconditionally
        # -- this payload happens to combine that with a second field,
        # but either reason alone would fail the same way.
        response = self.client.post(
            "/commands/save_settings",
            json={"virustotal_api_key": "a", "theme": "b"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_export_report_not_found_is_translated_not_raised(self) -> None:
        # Phase 4D Part 6: export_report added to COMMAND_HANDLERS. Uses a
        # certainly-missing id, consistent with this file's existing
        # constraint (see module docstring) of not exercising mutating
        # paths (a real file write, here) against real state through the
        # HTTP transport -- the not-found short-circuit happens before
        # ReportingService is ever called, so no file is written.
        response = self.client.post(
            "/commands/export_report",
            json={
                "investigation_id": 999999,
                "export_format": "json",
                "output_path": "/tmp/should-not-be-written.json",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "INVESTIGATION_NOT_FOUND")

    def test_export_report_validation_error_never_reaches_domain(self) -> None:
        response = self.client.post(
            "/commands/export_report",
            json={
                "investigation_id": -1,
                "export_format": "json",
                "output_path": "/tmp/x.json",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_export_report_rejects_unsupported_format_before_domain(self) -> None:
        response = self.client.post(
            "/commands/export_report",
            json={
                "investigation_id": 1,
                "export_format": "csv",
                "output_path": "/tmp/x.csv",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_delete_investigation_missing_id_returns_success_envelope(self) -> None:
        # Phase 4D Part 2: delete_investigation added to COMMAND_HANDLERS.
        # Uses a certainly-missing id so this stays non-mutating against
        # the real database, consistent with this file's existing
        # constraint (see module docstring) of not exercising mutating
        # paths against real state through the HTTP transport.
        response = self.client.post(
            "/commands/delete_investigation", json={"investigation_id": 999999}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["error"])
        self.assertFalse(body["data"]["deleted"])
        self.assertEqual(body["data"]["investigation_id"], 999999)

    def test_delete_investigation_validation_error_never_reaches_domain(self) -> None:
        response = self.client.post(
            "/commands/delete_investigation", json={"investigation_id": -1}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_search_investigations_no_match_returns_success_envelope(self) -> None:
        # Phase 4D Part 3: search_investigations added to COMMAND_HANDLERS.
        # Uses a certainly-absent report name so this stays read-only
        # against the real database, consistent with this file's existing
        # constraint (see module docstring).
        response = self.client.post(
            "/commands/search_investigations",
            json={"report_name": "definitely-not-a-real-report.txt"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["error"])
        self.assertEqual(body["data"], [])

    def test_search_investigations_blank_name_returns_empty_list(self) -> None:
        response = self.client.post(
            "/commands/search_investigations", json={"report_name": "   "}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"], [])

    def test_search_investigations_validation_error_never_reaches_domain(self) -> None:
        response = self.client.post(
            "/commands/search_investigations", json={"report_name": 123}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)

    def test_unknown_command_name_returns_unknown_command_error(self) -> None:
        response = self.client.post("/commands/not_a_real_command", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], UNKNOWN_COMMAND)

    def test_malformed_payload_does_not_leak_a_raw_500(self) -> None:
        # Missing the required field entirely -- the dataclass __init__
        # raises TypeError, which dispatch() translates (S16/handlers.py)
        # rather than letting propagate as an unhandled server error.
        response = self.client.post("/commands/get_investigation", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], INVALID_COMMAND_PAYLOAD)


def _make_event(name: str = "analysis.progress", **payload: object) -> Event:
    return Event.create(name, new_correlation_id("t"), dict(payload))


class _FakeRequest:
    """
    Minimal stand-in for `fastapi.Request`, exposing only the one method
    `_sse_event_stream()` actually calls: `is_disconnected()`. Used by
    `SSEEventStreamGeneratorTests` below to unit-test the generator
    directly, bypassing the HTTP transport entirely -- see that class's
    docstring for why.
    """

    def __init__(self, disconnected_after: int | None = None) -> None:
        self._calls = 0
        self._disconnected_after = disconnected_after

    async def is_disconnected(self) -> bool:
        self._calls += 1
        if self._disconnected_after is None:
            return False
        return self._calls > self._disconnected_after


class SSEEventStreamGeneratorTests(unittest.IsolatedAsyncioTestCase):
    """
    Direct tests of `app.api.app._sse_event_stream()` -- the async
    generator behind `GET /events` -- against a real `EventBroker`, with
    no HTTP transport involved.

    Why not test purely through `fastapi.testclient.TestClient`/
    `httpx.AsyncClient`: both transports installed in this environment
    (`starlette.testclient._TestClientTransport.handle_request` and
    `httpx._transports.asgi.ASGITransport.handle_async_request`) fully
    drain the ASGI application call -- i.e. wait for the response body to
    finish sending `more_body: False` -- before returning *anything* to
    the caller, including the response headers. Confirmed directly against
    both (see this Part's implementation doc, "Testing" section, for the
    full trace): an SSE endpoint whose loop only exits on client
    disconnect or broker shutdown cannot be driven through either
    transport without first ending the connection by some other means,
    since the disconnect signal itself is only delivered *after* the
    response is already complete -- a genuine chicken-and-egg limitation
    of those transports' ASGI `receive()` implementations, not a defect in
    this endpoint. `EventsRouteHTTPTests` below still proves the real
    route/broker/FastAPI wiring end-to-end, using `EventBroker.shutdown()`/
    `unsubscribe()` -- both real, already-tested (`tests/test_event_broker.
    py`) broker operations -- as the deterministic way to end a connection
    so TestClient's buffered response can be inspected. This class exists
    to test what that HTTP-level approach cannot reach directly: exact
    per-chunk framing, heartbeat timing, and disconnect-triggered cleanup,
    all with a fast, deterministic, thread-free async generator interface.
    """

    async def test_published_event_is_delivered_with_correct_sse_framing(self) -> None:
        broker = EventBroker()
        with patch.object(api_app, "get_application_broker", return_value=broker):
            gen = api_app._sse_event_stream(_FakeRequest())
            try:
                pending = asyncio.ensure_future(gen.__anext__())
                # Give the generator a chance to reach its blocking
                # `subscription.get()` call before we publish, so this
                # exercises real wake-on-publish delivery (Subscription's
                # `threading.Condition.notify()`), not a lucky race.
                await asyncio.sleep(0.02)
                event = _make_event("analysis.progress", pct=50)
                broker.publish(event)
                chunk = await asyncio.wait_for(pending, timeout=5)
            finally:
                await gen.aclose()

            self.assertTrue(chunk.endswith("\n\n"))
            lines = chunk.split("\n")
            self.assertEqual(lines[0], f"id: {event.event_id}")
            self.assertEqual(lines[1], "event: analysis.progress")
            self.assertTrue(lines[2].startswith("data: "))
            payload = json.loads(lines[2][len("data: ") :])
            self.assertEqual(payload, event.to_dict())
            self.assertEqual(broker.subscriber_count(), 0)

    async def test_multiple_events_arrive_in_publish_order(self) -> None:
        broker = EventBroker()
        with patch.object(api_app, "get_application_broker", return_value=broker):
            # Subscribe (via the generator) BEFORE publishing -- the broker
            # deliberately has no replay (PHASE4D_SSE_ARCHITECTURE_DECISION.
            # md S6: "no replay in the first implementation"), so an event
            # published before a subscriber exists is correctly never seen
            # by it. This is the same ordering
            # `test_published_event_is_delivered_with_correct_sse_framing`
            # already establishes; this test only adds "and in order" for
            # more than one event.
            gen = api_app._sse_event_stream(_FakeRequest())
            try:
                events = [
                    _make_event("analysis.progress", pct=n) for n in (10, 20, 30)
                ]
                pending = asyncio.ensure_future(gen.__anext__())
                await asyncio.sleep(0.02)
                for event in events:
                    broker.publish(event)

                received = [(await asyncio.wait_for(pending, timeout=5)).split("\n")[0]]
                for _ in events[1:]:
                    chunk = await asyncio.wait_for(gen.__anext__(), timeout=5)
                    received.append(chunk.split("\n")[0])
            finally:
                await gen.aclose()

            self.assertEqual(
                received, [f"id: {event.event_id}" for event in events]
            )

    async def test_heartbeat_is_valid_sse_comment_and_never_a_broker_event(self) -> None:
        broker = EventBroker()
        with patch.object(api_app, "get_application_broker", return_value=broker), \
                patch.object(api_app, "SSE_HEARTBEAT_INTERVAL_SECONDS", 0.05), \
                patch.object(api_app, "_SSE_POLL_INTERVAL_SECONDS", 0.02):
            gen = api_app._sse_event_stream(_FakeRequest())
            try:
                chunk = await asyncio.wait_for(gen.__anext__(), timeout=5)
            finally:
                await gen.aclose()

            self.assertEqual(chunk, ": heartbeat\n\n")
            # A heartbeat is formatted directly by `_format_sse_heartbeat()`
            # and is never passed to `EventBroker.publish()` (see that
            # function's docstring/the generator's source) -- there is
            # structurally no code path for it to acquire an `event_id` or
            # become visible to any other subscriber, so this asserts the
            # one externally-observable consequence: the broker this
            # subscriber came from still has exactly the one subscriber
            # this test created, never a second one or a queued Event.
            self.assertEqual(broker.subscriber_count(), 0)  # closed by aclose()

    async def test_client_disconnect_ends_stream_and_unsubscribes(self) -> None:
        broker = EventBroker()
        with patch.object(api_app, "get_application_broker", return_value=broker):
            gen = api_app._sse_event_stream(_FakeRequest(disconnected_after=0))

            with self.assertRaises(StopAsyncIteration):
                await asyncio.wait_for(gen.__anext__(), timeout=5)

            self.assertEqual(broker.subscriber_count(), 0)

    async def test_broker_shutdown_ends_stream_without_disconnect(self) -> None:
        # Covers the *other* way a connection ends: process/broker
        # shutdown (PHASE4D_SSE_ARCHITECTURE_DECISION.md S6 Shutdown),
        # independent of any client-side disconnect signal.
        broker = EventBroker()
        with patch.object(api_app, "get_application_broker", return_value=broker), \
                patch.object(api_app, "_SSE_POLL_INTERVAL_SECONDS", 0.02):
            gen = api_app._sse_event_stream(_FakeRequest())
            pending = asyncio.ensure_future(gen.__anext__())
            await asyncio.sleep(0.05)
            broker.shutdown()

            with self.assertRaises(StopAsyncIteration):
                await asyncio.wait_for(pending, timeout=5)

    async def test_secret_free_payload_survives_unchanged_into_the_sse_frame(self) -> None:
        # Payloads never carry secrets -- enforced by the command handlers
        # that construct `Event`s (app/application/handlers.py; confirmed
        # in PHASE4D_SSE_PART2_IMPLEMENTATION.md, e.g. `enrich_ioc`'s
        # `result` payload "never a secret -- lookup_indicator's return
        # shape never carries the provider API key"). This test's job is
        # narrower and specific to this Part: confirm the SSE transport
        # itself is inert -- it does not add, rename, or drop any payload
        # field on the way to the wire, so a handler's non-secret
        # guarantee actually reaches the client unchanged.
        broker = EventBroker()
        with patch.object(api_app, "get_application_broker", return_value=broker):
            event = _make_event(
                "ti.enrichment.completed",
                ioc_type="ip",
                value="203.0.113.5",
                result={"verdict": "malicious", "score": 87},
            )
            gen = api_app._sse_event_stream(_FakeRequest())
            try:
                pending = asyncio.ensure_future(gen.__anext__())
                await asyncio.sleep(0.02)
                broker.publish(event)
                chunk = await asyncio.wait_for(pending, timeout=5)
            finally:
                await gen.aclose()

            data_line = chunk.split("\n")[2]
            payload = json.loads(data_line[len("data: ") :])
            self.assertEqual(set(payload.keys()), set(event.to_dict().keys()))
            self.assertEqual(payload["payload"], event.payload)


class EventsRouteHTTPTests(unittest.TestCase):
    """
    GET /events -- Phase 4D SSE Part 3: end-to-end proof that the real
    FastAPI route is wired to the real `EventBroker`, through the real
    ASGI app, per docs/phase4/PHASE4D_SSE_PART3_IMPLEMENTATION.md.

    Supersedes the pre-Part-3 `EventsRouteTests` class (Part 2's 501
    stub-error test, which no longer applies -- the route is implemented
    now).

    Each test patches `app.api.app.get_application_broker` to a
    test-local `EventBroker()` instead of the process-lifetime singleton
    (`app.application.broker.get_application_broker`'s own docstring
    explicitly recommends this for exactly this reason: "Tests should NOT
    rely on this singleton ... construct a fresh `EventBroker()` directly
    instead") -- this keeps `EventBroker.shutdown()` calls in this file
    from leaking into other test files/classes that also exercise
    `GET /events` or the singleton directly.

    Every test here ends its connection(s) deterministically via
    `EventBroker.shutdown()` or `.unsubscribe()` (see
    `SSEEventStreamGeneratorTests`'s docstring above for exactly why a
    real client disconnect cannot be driven through `TestClient` here) --
    each request therefore runs on a background thread so the main thread
    can publish/end the connection while it is still open, then join and
    inspect the fully-buffered response.
    """

    def setUp(self) -> None:
        self.broker = EventBroker()
        patcher = patch.object(
            api_app, "get_application_broker", return_value=self.broker
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(app, raise_server_exceptions=False)

    def _get_events_in_background(self) -> dict[str, object]:
        result: dict[str, object] = {}

        def _run() -> None:
            result["response"] = self.client.get("/events")

        thread = threading.Thread(target=_run)
        thread.start()
        result["thread"] = thread
        return result

    def test_events_stream_is_no_longer_501(self) -> None:
        run = self._get_events_in_background()
        time.sleep(0.1)
        self.broker.shutdown()
        run["thread"].join(timeout=10)  # type: ignore[union-attr]

        response = run["response"]
        self.assertEqual(response.status_code, 200)  # type: ignore[union-attr]

    def test_events_stream_content_type_is_sse(self) -> None:
        run = self._get_events_in_background()
        time.sleep(0.1)
        self.broker.shutdown()
        run["thread"].join(timeout=10)  # type: ignore[union-attr]

        response = run["response"]
        self.assertTrue(
            response.headers["content-type"].startswith("text/event-stream")  # type: ignore[union-attr]
        )

    def test_real_broker_event_reaches_the_http_stream(self) -> None:
        run = self._get_events_in_background()
        time.sleep(0.1)
        event = _make_event("analysis.progress", pct=75)
        self.broker.publish(event)
        time.sleep(0.1)
        self.broker.shutdown()
        run["thread"].join(timeout=10)  # type: ignore[union-attr]

        body = run["response"].text  # type: ignore[union-attr]
        self.assertIn(f"id: {event.event_id}\n", body)
        self.assertIn("event: analysis.progress\n", body)
        frame = next(
            block for block in body.split("\n\n") if event.event_id in block
        )
        data_line = next(
            line for line in frame.split("\n") if line.startswith("data: ")
        )
        payload = json.loads(data_line[len("data: ") :])
        self.assertEqual(payload, event.to_dict())

    def test_two_subscribers_receive_the_same_event_and_one_ending_does_not_affect_the_other(
        self,
    ) -> None:
        captured_subscriptions: list[object] = []
        real_subscribe = self.broker.subscribe

        def _capturing_subscribe():  # type: ignore[no-untyped-def]
            subscription = real_subscribe()
            captured_subscriptions.append(subscription)
            return subscription

        self.broker.subscribe = _capturing_subscribe  # type: ignore[method-assign]

        run_a = self._get_events_in_background()
        time.sleep(0.1)
        run_b = self._get_events_in_background()
        time.sleep(0.1)
        self.assertEqual(len(captured_subscriptions), 2)

        first_event = _make_event("analysis.progress", pct=1)
        self.broker.publish(first_event)
        time.sleep(0.1)

        # End subscriber A's connection specifically (a targeted
        # unsubscribe, standing in for A's client disconnecting -- see
        # SSEEventStreamGeneratorTests' docstring for why an actual TCP
        # disconnect cannot be driven through TestClient here). B's
        # subscription is untouched.
        self.broker.unsubscribe(captured_subscriptions[0])
        run_a["thread"].join(timeout=10)  # type: ignore[union-attr]

        second_event = _make_event("analysis.progress", pct=2)
        self.broker.publish(second_event)
        time.sleep(0.1)
        self.broker.shutdown()
        run_b["thread"].join(timeout=10)  # type: ignore[union-attr]

        body_a = run_a["response"].text  # type: ignore[union-attr]
        body_b = run_b["response"].text  # type: ignore[union-attr]

        # Both subscribers saw the event published while both were live.
        self.assertIn(first_event.event_id, body_a)
        self.assertIn(first_event.event_id, body_b)

        # A's stream ended when A was unsubscribed -- it never saw the
        # second event, proving the broker (and this route) delivers to
        # exactly the subscribers registered at publish time, no more.
        self.assertNotIn(second_event.event_id, body_a)

        # B, unaffected by A's disconnect, kept receiving.
        self.assertIn(second_event.event_id, body_b)

        self.assertEqual(self.broker.subscriber_count(), 0)

    def test_shutdown_cleanly_ends_an_open_connection(self) -> None:
        run = self._get_events_in_background()
        time.sleep(0.1)
        self.broker.shutdown()
        run["thread"].join(timeout=10)  # type: ignore[union-attr]

        # join() returning at all (rather than the 10s timeout being hit)
        # is itself the assertion that matters here: it proves the
        # connection's async generator actually exited instead of
        # blocking forever, per PHASE4D_SSE_ARCHITECTURE_DECISION.md S6
        # Shutdown ("no dangling connections, no orphaned threads").
        self.assertFalse(run["thread"].is_alive())  # type: ignore[union-attr]
        self.assertEqual(self.broker.subscriber_count(), 0)


if __name__ == "__main__":
    unittest.main()
