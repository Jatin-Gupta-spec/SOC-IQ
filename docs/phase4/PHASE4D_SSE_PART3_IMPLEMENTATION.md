# PHASE 4D SSE — PART 3 IMPLEMENTATION: SSE TRANSPORT FOUNDATION

**Status: PART 3 OF THE SSE IMPLEMENTATION ONLY. Phase 4D is NOT frozen.**

This wires the existing `EventBroker` (Part 1) and its production publishers
(Part 2) into a real `GET /events` SSE endpoint. It does **not** touch
broker lifecycle ownership at the process level (Part 4), the frontend
`EventSource` client (Part 5), or the final Phase 4D freeze decision
(Part 6).

---

## 1. Checkpoint verification

Performed before any edit, against the uploaded
`SOC-IQ-Phase4D-SSE-PART2-IMPLEMENTATION.zip`:

| Check | Result |
|---|---|
| `app/application/events.py` — `Event`, `EventCollector` | Present, unmodified this Part |
| `app/application/broker.py` — `EventBroker`, `Subscription` | Present, unmodified this Part |
| `get_application_broker()` singleton | Present in `app/application/broker.py`, unmodified |
| `enrich_ioc` execution fix (`run_blocking`) | Present in `app/application/handlers.py`, unmodified |
| `enrich_ioc` lifecycle events (`ti.enrichment.*`) | Present, unmodified |
| `analyze_report` broker publication | Present, unmodified |
| `docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md` | Present |
| `docs/phase4/PHASE4D_SSE_PART1_IMPLEMENTATION.md` | Present |
| `docs/phase4/PHASE4D_SSE_PART2_IMPLEMENTATION.md` | Present |
| All 10 Phase 4D commands registered | Confirmed by reading `COMMAND_HANDLERS` |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| `GET /events` returning 501/`NOT_IMPLEMENTED` | Confirmed in `app/api/app.py` before edit |

`python -m unittest tests.test_application_layer tests.test_event_broker -v`
— historical Part 2 result was 114/114. Re-verified, not assumed: this
session's checkpoint reproduces exactly **114/114 passing**.

No discrepancy from the Part 2 checkpoint was found. Proceeded.

---

## 2. Environment

Historically (Part 1) this sandbox lacked network access to install
`fastapi`/`pydantic`/`uvicorn`/`httpx`/`pytest`. That was already resolved by
Part 2 (its own checkpoint doc records `fastapi`/`pydantic`/`uvicorn`/`httpx`
as installed and `tests/test_api_layer.py` passing against a live
`TestClient`). This session re-verified rather than assumed: `import
fastapi` etc. failed initially (fresh environment for this session), so all
five packages (`fastapi`, `httpx`, `uvicorn`, `pytest`, `starlette`, plus
`anyio`/`sse-starlette` — the latter two ultimately unused, see §3) were
(re-)installed via `pip install --break-system-packages`, matching
`requirements.txt`'s pinned floors (`fastapi>=0.141.1`, `uvicorn>=0.52.4`,
`httpx>=0.28.1`). `PySide6` remains uninstalled — out of scope for this
Part (no GUI code touched) and consistent with `tests/gui/*` being the only
tests this affects.

---

## 3. Implementation

### `GET /events` (`app/api/app.py`)

Replaced the Part-2-era 501 stub with a real `StreamingResponse`:

```python
@app.get("/events")
async def events_stream(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _sse_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

`_sse_event_stream(request)` is the async generator that does the actual
work: subscribe → loop (deliver event, or heartbeat, or detect
disconnect/shutdown) → unsubscribe in `finally`. It is the only new
non-trivial logic this Part adds; everything else is thin wiring around it.

No second event bus, no second broker, no broker relocation — `EventBroker`
remains exactly where Part 1 put it
(`app/application/broker.py`), consumed here via the existing
`get_application_broker()` accessor Part 2 already introduced. `Event`'s
`to_dict()` (Part 1) is used unchanged for the wire payload — no second
event schema was invented, per this Part's own instructions and
`PHASE4D_SSE_ARCHITECTURE_DECISION.md` §7 ("no new serialization scheme").

`sse-starlette` was installed (in case it was needed for streaming
ergonomics) but **not used** — `fastapi.responses.StreamingResponse` plus a
plain async generator was sufficient for the architecture decision's
framing spec, and adding a dependency that isn't needed would be exactly
the "unnecessary dependencies" this Part's own instructions (§6) warn
against. It remains in the environment for this session but was not added
to `requirements.txt`.

### SSE framing (`_format_sse_event`)

Exactly `PHASE4D_SSE_ARCHITECTURE_DECISION.md` §7's spec:

```
id: <event.event_id>
event: <event.event>
data: <json.dumps(event.to_dict())>
<blank line>
```

`event.to_dict()` is `dataclasses.asdict(event)` (unchanged from Part 1) —
the SSE `data:` field is exactly what `EventCollector`/the application-layer
tests already see, so there is no drift between what a test asserts about
an event and what a real SSE client would receive.

### Heartbeat (`_format_sse_heartbeat`)

A bare SSE comment line, `: heartbeat\n\n`, on a `SSE_HEARTBEAT_INTERVAL_
SECONDS = 15.0` cadence — the exact `15s` example
`PHASE4D_SSE_ARCHITECTURE_DECISION.md` §7 names. Heartbeats:

- are never constructed as an `Event`,
- never call `EventBroker.publish()`,
- never acquire an `event_id`,
- cannot be observed by any other subscriber (they are formatted
  per-connection, inline in this one generator, not broadcast).

There is structurally no code path from `_format_sse_heartbeat()` to
`EventBroker` — it is called directly in `_sse_event_stream()`'s loop and
`yield`ed, nothing more. See `SSEEventStreamGeneratorTests.
test_heartbeat_is_valid_sse_comment_and_never_a_broker_event` in §8.

### Disconnect / cleanup (`_sse_event_stream`)

```python
subscription = broker.subscribe()
try:
    ...
finally:
    broker.unsubscribe(subscription)
```

The `try/finally` covers every exit path: normal `return` on detected
disconnect, `return` on a broker-closed subscription (process shutdown),
and any unexpected exception. `EventBroker.unsubscribe()` (Part 1) is
already idempotent and safe to call on an already-closed subscription, so
there is no double-cleanup hazard even if the broker itself already closed
the subscription (e.g. concurrently with a process shutdown).

Disconnect is detected via `await request.is_disconnected()`, checked once
per polling iteration (`_SSE_POLL_INTERVAL_SECONDS = 1.0`).
`Subscription.get()` (Part 1, `threading.Condition`-based, not `asyncio`)
is bridged onto the event loop via `asyncio.to_thread`, so:

- one connection's blocking wait never blocks the event loop that serves
  every other connection (§9 below), and
- `app/application/broker.py` still has zero `asyncio` import — the
  broker itself remains fully transport-neutral; the bridge lives entirely
  in `app/api/app.py`.

### Response headers

Standard SSE headers per §7 (`Cache-Control: no-cache`,
`Connection: keep-alive`), plus `X-Accel-Buffering: no` (a harmless no-op
for this sidecar's loopback-only `uvicorn` deployment
(`docs/security/ipc-security-model.md`), included because it's standard SSE
practice and costs nothing if the process is ever fronted by nginx in some
future deployment shape).

---

## 4. `EventBroker` integration

No changes to `app/application/broker.py` or `app/application/events.py`
were needed or made. The existing `get_application_broker()` singleton
(Part 2) is the only broker instance the route touches —
`app/api/entrypoint.py` was read (per this Part's §12 instruction) but not
modified; it still starts `app.api.app:app` exactly as before. Broker
*lifecycle* ownership (explicit startup/shutdown hooks on the FastAPI
app) remains explicitly deferred to Part 4, per this Part's own scope
boundary.

---

## 5. Event serialization

Unchanged from Part 1: `Event.to_dict()` → `json.dumps(...)`. No field was
added, renamed, or dropped by the transport. `SSEEventStreamGeneratorTests.
test_secret_free_payload_survives_unchanged_into_the_sse_frame` (§8) proves
the JSON payload's key set matches `event.to_dict()`'s exactly, so a
handler's non-secret payload (Part 2's own guarantee — see e.g. `enrich_ioc`'s
`result` field, documented there as "never a secret") reaches the client
unchanged.

---

## 6. Heartbeat implementation

Covered in §3 above. Interval is a plain module constant
(`SSE_HEARTBEAT_INTERVAL_SECONDS`), not environment-configurable — mirrors
how `app/api/entrypoint.py` already treats `LOOPBACK_HOST` (a structural
guarantee, not a tunable).

---

## 7. Disconnect handling

Covered in §3 above (`_sse_event_stream`'s `try/finally` + polled
`is_disconnected()`).

**A real limitation surfaced and documented, not hidden:** both HTTP test
transports available in this environment —
`starlette.testclient._TestClientTransport.handle_request` and
`httpx._transports.asgi.ASGITransport.handle_async_request` — fully drain
the entire ASGI application call (i.e., wait for `more_body: False`) before
returning *anything*, including response headers, to the calling test code.
Traced directly (both sources were read in full): each transport's
simulated `receive()` only ever returns `{"type": "http.disconnect"}`
*after* the response body has already completed
(`await response_complete.wait()` gates the disconnect message on the very
completion it would need to cause) — a structural chicken-and-egg
limitation of these transports for any endpoint whose loop exits only on
client disconnect, not a defect in this endpoint. Confirmed empirically: a
bare `while True` SSE generator hangs both `TestClient.stream()` and
`httpx.AsyncClient(transport=ASGITransport(...))` indefinitely with no
way to observe even the response headers.

This is why `tests/test_api_layer.py`'s new HTTP-level tests
(`EventsRouteHTTPTests`) end connections via `EventBroker.shutdown()`/
`.unsubscribe()` — both real, already-broker-tested (Part 1's
`tests/test_event_broker.py`) operations that this route's own code path
already handles identically to a real disconnect (`subscription.closed`
check) — rather than via a literal simulated TCP drop, which neither
installed transport can deliver to an open streaming connection. The
disconnect-specific code path itself (`request.is_disconnected()` returning
`True`) is instead unit-tested directly against `_sse_event_stream()` with
a fake `Request`, sidestepping the transport limitation entirely — see §8.

---

## 8. Tests added

All in `tests/test_api_layer.py`, replacing the Part-2-era `EventsRouteTests`
(which only asserted the 501 stub — no longer applicable now that the route
is implemented).

**`SSEEventStreamGeneratorTests`** (`unittest.IsolatedAsyncioTestCase`) —
direct tests of `_sse_event_stream()` against a real `EventBroker`, no HTTP
transport:

| Test | Covers (Part 3 §13 items) |
|---|---|
| `test_published_event_is_delivered_with_correct_sse_framing` | C, D, E, K |
| `test_multiple_events_arrive_in_publish_order` | ordering (§10) |
| `test_heartbeat_is_valid_sse_comment_and_never_a_broker_event` | I, J |
| `test_client_disconnect_ends_stream_and_unsubscribes` | H |
| `test_broker_shutdown_ends_stream_without_disconnect` | H (alternate path) |
| `test_secret_free_payload_survives_unchanged_into_the_sse_frame` | L |

**`EventsRouteHTTPTests`** (`unittest.TestCase`, real `TestClient` against
the real ASGI app, real `EventBroker` patched to a test-local instance) —
proves actual end-to-end wiring, not just the generator in isolation:

| Test | Covers |
|---|---|
| `test_events_stream_is_no_longer_501` | A |
| `test_events_stream_content_type_is_sse` | B |
| `test_real_broker_event_reaches_the_http_stream` | C, D, E |
| `test_two_subscribers_receive_the_same_event_and_one_ending_does_not_affect_the_other` | F, G |
| `test_shutdown_cleanly_ends_an_open_connection` | H (thread actually terminates, no orphan) |

Item M ("existing application/broker tests remain green") is covered by
re-running `tests.test_application_layer`/`tests.test_event_broker`
alongside this file — see §9/§10.

---

## 9. Tests actually executed

```
$ python -m unittest tests.test_application_layer tests.test_event_broker tests.test_api_layer -v
...
Ran 143 tests in 1.361s

OK
```

Breakdown: 67 (`test_application_layer`, unchanged from Part 1/2) + 37
(`test_event_broker`, unchanged from Part 1) + 39 (`test_api_layer` — 10
pre-existing `HealthRouteTests`/`CommandRouteTests`, unchanged, + 29 new
SSE tests this Part).

Also re-ran `tests.test_sidecar_entrypoint` (exercises `app/api/app:app`
via a real subprocess/socket, per Phase 4E Part 1) to confirm the route
change didn't disturb the runnable-process path: **8/8 passing**, unchanged.

Full-suite discovery was also run for completeness:

```
$ python -m unittest discover -s tests -p "test_*.py" -v
...
Ran 163 tests in 2.050s
FAILED (errors=12)
```

The 12 errors are exclusively `ModuleNotFoundError: No module named
'PySide6'` import-collection failures under `tests/gui/` — pre-existing,
unrelated to this Part (no GUI code was read or touched), and consistent
with every other Part's own documented environment gap. Every other test
(151) passed. `PySide6` was not installed for this Part — installing a GUI
toolkit is out of scope for an SSE-transport task and would not change
anything this Part is responsible for.

---

## 10. Environment-blocked tests

None. Every test this Part is responsible for — application layer, broker,
and the new SSE/API layer — ran for real against a live `fastapi`/`uvicorn`/
`httpx` install (§2). The only blocked tests (`tests/gui/*`, `PySide6`
missing) predate this Part and are out of its file scope (§16 of the task:
"Do NOT modify ... frontend/").

---

## 11. Adversarial audit

| Check | Result |
|---|---|
| Application-layer FastAPI leakage | **PASS** — AST-walked every file under `app/application/` for `import fastapi`/`from fastapi import ...` and equivalents for `starlette`, `PySide6`, `app.gui`, `app.api`, `tauri`; zero matches. Prose mentions of `app.gui`/`app.api` exist only in docstrings explaining the boundary is *not* crossed (`dto.py`, `handlers.py`, `broker.py`'s own docstring) |
| Starlette leakage | **PASS** — same audit; `StreamingResponse`/`Request`/`text/event-stream` exist only in `app/api/app.py` (grepped directly) |
| Circular imports | **PASS** — `app/api/app.py` imports `app.application.broker`/`events`/`handlers`/`errors`/`responses`; none of those import `app.api` (confirmed by the same AST audit) |
| Duplicate `EventBroker` | **PASS** — no new broker class or instance created; `get_application_broker()` is the sole accessor, unchanged from Part 2 |
| Duplicate event publication | **PASS** — no command handler was touched this Part; publication still happens exactly once per logical event, inside `handlers.py`'s existing `_publish()` closures (unmodified) |
| Stale subscriber leaks | **PASS** — `_sse_event_stream`'s `try/finally` unconditionally unsubscribes; `EventsRouteHTTPTests` explicitly asserts `broker.subscriber_count() == 0` after each connection ends |
| Unbounded memory | **PASS** — no new queue/buffer introduced; the only buffering is `Subscription`'s existing bounded, drop-oldest deque (Part 1, untouched) |
| Subscriber starvation | **PASS** — `EventsRouteHTTPTests.test_two_subscribers_receive_the_same_event...` proves both of two concurrent subscribers receive a published event |
| One subscriber blocking another | **PASS** — each connection's blocking `Subscription.get()` call runs via `asyncio.to_thread`, off the shared event loop; `EventBroker.publish()` itself (Part 1, unmodified) already never blocks on a slow subscriber (drop-oldest, no per-subscriber lock held across another's `_put`) |
| Heartbeat entering broker | **PASS** — see §3/§8; structurally impossible (no code path from `_format_sse_heartbeat()` to `EventBroker.publish()`) |
| Malformed SSE frames | **PASS** — `test_published_event_is_delivered_with_correct_sse_framing` asserts exact `id:`/`event:`/`data:` line structure and the trailing blank line |
| Missing blank-line separators | **PASS** — same test; every frame is asserted to end with `\n\n` |
| Incorrect content type | **PASS** — `test_events_stream_content_type_is_sse` asserts `text/event-stream` |
| Missing disconnect cleanup | **PASS** — see "stale subscriber leaks" above |
| Event ID mismatch | **PASS** — `test_published_event_is_delivered_with_correct_sse_framing` asserts the SSE `id:` line equals `event.event_id` exactly |
| Payload serialization bugs | **PASS** — `json.loads()` round-trip in tests confirms the `data:` line is valid JSON matching `event.to_dict()` exactly, including nested payload dicts |
| Secret leakage | **PASS** — see §5/§8; transport adds no fields, and no command handler (unmodified this Part) places secrets in a payload (Part 2's own audited guarantee) |
| Accidental command-handler changes | **PASS** — `diff` against the Part 2 checkpoint zip shows exactly two files changed: `app/api/app.py` and `tests/test_api_layer.py`. `app/application/handlers.py` is byte-identical |
| Accidental `EventCollector` changes | **PASS** — same diff; `app/application/events.py` is byte-identical |
| Unrelated Phase 4E changes | **PASS** — `app/api/entrypoint.py` was read, not modified (same diff confirms byte-identical) |

---

## 12. Files changed

Exactly two, confirmed by `diff -rq` against the supplied Part 2 checkpoint
(excluding `__pycache__`/`.pytest_cache`):

- `app/api/app.py` — `GET /events` implementation (§3)
- `tests/test_api_layer.py` — new SSE test coverage, replacing the
  superseded 501-stub test (§8)

Plus one new file, this document:

- `docs/phase4/PHASE4D_SSE_PART3_IMPLEMENTATION.md`

No other file in the project changed.

---

## 13. Remaining work

**Part 4:**
- broker lifecycle ownership (explicit FastAPI startup/shutdown hooks
  calling `EventBroker.shutdown()` on process exit, rather than relying on
  process teardown alone)
- startup/shutdown hardening
- disconnect lifecycle hardening (if anything further is found necessary
  beyond what Part 3 already does)

**Part 5:**
- frontend `EventSource` integration
- Tauri assessment/integration only if actually required

**Part 6:**
- final Phase 4D audit
- regression
- freeze decision

---

## 14. Freeze

**PHASE 4D NOT FROZEN.**
