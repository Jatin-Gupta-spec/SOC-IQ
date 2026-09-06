# PHASE 4D SSE — PART 2 IMPLEMENTATION: HANDLER EVENT INTEGRATION + ENRICH_IOC EXECUTION FIX

**Status: PART 2 OF THE SSE IMPLEMENTATION ONLY. Phase 4D is NOT frozen.**

This wires `EventBroker` (Part 1) into the production command/event path and
fixes a pre-existing `enrich_ioc` event-loop hazard. It does **not**
implement the FastAPI SSE endpoint, does not touch `GET /events`, and does
not modify the frontend or Tauri/Rust code.

---

## 1. Checkpoint verification

Performed before any edit, against the uploaded
`SOC-IQ-Phase4D-SSE-PART1-IMPLEMENTATION.zip`:

| Check | Result |
|---|---|
| `EventBroker` exists | Yes — `app/application/broker.py`, unmodified structure from Part 1 |
| `EventCollector` still exists | Yes — `app/application/events.py`, untouched in this Part |
| 10 Phase 4D commands remain registered | Yes — confirmed by reading `COMMAND_HANDLERS` and every `if name ==` branch in `dispatch()` |
| `/events` is still 501 | Yes — `app/api/app.py`, not modified this Part |
| Part 1 implementation doc exists | Yes — `docs/phase4/PHASE4D_SSE_PART1_IMPLEMENTATION.md` |
| Part 1 broker tests exist | Yes — `tests/test_event_broker.py`, 37 tests |
| `python -m unittest tests.test_application_layer -v` passes | Yes — 67 tests, before any Part 2 edit |
| No FastAPI SSE implementation already exists | Confirmed — `app/api/app.py`'s `/events` route still returns the Part-1-era `501` stub |

No discrepancy from the Part 1 checkpoint was found. Proceeded.

---

## 2. Audit of current event publication (Stage 1)

Read `app/application/handlers.py`, `app/application/broker.py`,
`app/application/events.py`, and `app/api/app.py` in full before editing.

- **Event creation**: only `AnalyzeReportCommandHandler.handle()` constructed
  `Event` objects. `EnrichIocCommandHandler` emitted none.
- **EventCollector usage**: `AnalyzeReportCommandHandler` only; a local
  variable, discarded by `dispatch()` (`response, _collector = ...`).
- **EventBroker reachability**: nowhere in production code. Part 1's module
  docstring confirmed this explicitly ("no caller exists in production code
  yet in this Part; only tests ... construct and use this").
- **dispatch()'s ability to publish broker events**: none — no import of
  `app.application.broker` in `handlers.py` before this Part.
- **Broker ownership**: undecided by Part 1 on purpose. `app/api/entrypoint.py`
  (the eventual FastAPI-process owner per the architecture decision) does
  not yet construct or hold a broker, and won't until the SSE transport
  itself is built (Part 3+). Since command handlers need to publish *now*,
  this Part introduces a process-lifetime singleton owned by
  `app/application/broker.py` itself (§4 below) — the application layer,
  not the transport layer, since that's the layer with the actual
  publisher today.
- **Accidental handler-owned brokers**: none found; none introduced.

Confirmed: one broker, application-owned, not handler-owned.

---

## 3. Event publication integration (Stage 2)

`AnalyzeReportCommandHandler` and `EnrichIocCommandHandler` each publish
every event to **both** sinks via one local `_publish(event)` closure per
handler call:

```python
def _publish(event: Event) -> None:
    collector.publish(event)
    self._broker.publish(event)
```

Each logical event (`analysis.started`, `analysis.progress`,
`analysis.completed`, `analysis.failed`, `ti.enrichment.started`,
`ti.enrichment.completed`, `ti.enrichment.failed`) is constructed exactly
once and passed through this one closure — never two separately-constructed
`Event` objects for one occurrence, which is what would make the collector
and broker diverge or double-publish.

`analyze_report`'s synchronous return contract is unchanged: it still
returns `(response, EventCollector)` from `.handle()`, and `dispatch()`
still unpacks and discards the collector, returning only `response`. Broker
publication is a pure side effect, additive to the existing return value.

---

## 4. EventCollector compatibility

`app/application/events.py` was not modified in this Part.
`EventCollector` — its class definition, `publish()`, `as_dicts()` — is
byte-for-byte unchanged. Every existing consumer of a returned
`EventCollector` (all of `tests/test_application_layer.py`'s
`AnalyzeReportCommandHandlerTests`) continues to work unmodified, and
continues to see exactly the events it saw before this Part — the broker is
an additional destination, not a replacement.

---

## 5. `enrich_ioc` execution-model finding (Stage 3)

Re-read, without modification, exactly as instructed:

- `ThreatIntelService.lookup_indicator()` → `_lookup_raw()` →
  **`asyncio.run(provider.lookup_raw(ioc))`** at `app/threat_intel/service.py:223`
  (confirmed directly, matching the architecture decision's own finding —
  not assumed from the doc).
- `VirusTotalProvider.lookup_raw()` bridges onto the blocking VT client via
  `asyncio.to_thread(client.lookup_sha256/_ip/_domain/_url, ...)`.
- `app/api/app.py`'s `POST /commands/{name}` route (`run_command`) is
  `async def` and calls `handler(payload)` (→ `dispatch()`) **directly, on
  the request coroutine's own thread** — nothing wraps this in
  `asyncio.to_thread` or an executor.

**Confirmed hazard, unchanged from the architecture decision's diagnosis:**
once FastAPI/uvicorn actually run this route (not installed in this
sandbox — see §11), a live `enrich_ioc` call would execute `asyncio.run()`
on a thread that already has a running event loop, raising
`RuntimeError: asyncio.run() cannot be called from a running event loop`.
`dispatch()`'s catch-all `except Exception` would turn this into a generic
`INTERNAL_ERROR` envelope — a normal-shaped failure that hides a real bug
rather than surfacing it loudly.

---

## 6. Execution-model fix (Stage 4)

**New module: `app/application/execution.py`.** `ThreatIntelService`,
`VirusTotalProvider`, and `VirusTotalClient` are **not modified** — the fix
is entirely a new, narrow boundary in the application layer, exactly as the
task brief's "prefer a narrow execution boundary" instruction asked for.

### What it does

`run_blocking(fn, *args, **kwargs)` submits `fn(*args, **kwargs)` to a
small, lazily-constructed, process-lifetime `concurrent.futures.
ThreadPoolExecutor` (`max_workers=4`) and blocks the calling thread on
`future.result()`.

`EnrichIocCommandHandler.handle()` now calls:

```python
result = run_blocking(self._service.lookup_indicator, request.ioc_type, request.value)
```

instead of calling `self._service.lookup_indicator(...)` directly.

### Why this is correct and sufficient

`asyncio.run()` only raises when a running event loop already exists on
**the thread that calls it**. A `ThreadPoolExecutor` worker thread is a
plain new OS thread with no event loop of its own — so the `asyncio.run()`
inside `_lookup_raw` is always safe there, *regardless* of whether the
thread that called `run_blocking()` has a running loop. This closes the
hazard without needing `ThreatIntelService` (or anything downstream of it)
to know or care whether it's being called from sync code, from inside a
running event loop, or from a worker thread — exactly the "smallest correct
fix" the task brief asked for.

### Why it satisfies every Stage 4 requirement

| # | Requirement | How it's satisfied |
|---|---|---|
| 1 | Existing synchronous callers continue to work | `handle()`'s Python-level synchronous-call/return contract is unchanged; `run_blocking()` still blocks and returns/raises like a normal call |
| 2 | FastAPI can safely invoke `enrich_ioc` later | The blocking `asyncio.run()` span now always executes off the request thread, so a future `async def run_command()` calling `dispatch()` directly can never hit the nested-loop `RuntimeError` |
| 3 | No `asyncio.run()` inside an already-running event loop | Proven directly — see §9's regression tests, which actually execute the call from inside a running loop |
| 4 | No project-wide async rewrite | Only `EnrichIocCommandHandler` changed; the other 9 handlers are untouched |
| 5 | No FastAPI dependency inside app/application | `execution.py` imports only `threading`, `concurrent.futures`, `typing` |
| 6 | No GUI dependency inside app/application | Same — no `PySide6`/`app.gui` import anywhere in `app/application/*` (verified by grep, §10) |
| 7 | No duplicated VirusTotal logic | `execution.py` is generic — it knows nothing about VirusTotal, threat intel, or IOCs; it only runs an arbitrary callable on a worker thread |
| 8 | No direct `VirusTotalClient` construction in application layer | Confirmed by grep — none exists (§10) |
| 9 | `ThreatIntelService`/provider abstraction remains intact | `app/threat_intel/*` is untouched — 0 lines changed |

### Why a bounded, process-lifetime pool (not per-call)

A pool created once and reused (mirroring the `EventBroker` singleton's own
process-lifetime pattern) means repeated `enrich_ioc` calls reuse a small,
bounded set of worker threads rather than spawning a new thread per call —
verified directly: 20 sequential calls used exactly 1 worker thread; 12
concurrent calls peaked at exactly 4 (the configured `max_workers`) and
returned to steady state afterward (§9).

---

## 7. Event contract implemented (Stage 5)

Three lifecycle events for `enrich_ioc`, matching
`frontend/src/shared/events/types.ts`'s existing `EventName` union exactly
(that union already named these three strings; nothing on the backend
produced them until now):

| Event | When | Payload |
|---|---|---|
| `ti.enrichment.started` | Before the lookup begins | `{"ioc_type": str, "value": str}` |
| `ti.enrichment.completed` | On success | `{"ioc_type": str, "value": str, "result": <full verdict-annotated dict>}` |
| `ti.enrichment.failed` | On any exception from `lookup_indicator` | `{"ioc_type": str, "value": str, "code": str, "message": str}` |

All three share one `correlation_id`, generated via
`new_correlation_id("ti")` — mirroring `analyze_report`'s existing
`new_correlation_id("an")` convention.

No `progress` event: per the architecture decision (§5), a single-indicator
lookup is one request/response pair with nothing meaningful to report
between "started" and "done" — not implemented, matching "do not invent
excessive event types."

The `completed` payload embeds the full result (the same
verdict/detection-ratio-annotated dict the command's own HTTP response
carries) specifically so a future SSE/frontend consumer does not need a
second provider call to understand what happened, per the task brief.

**Failure handling detail:** `EnrichIocCommandHandler.handle()` still does
no *translation* of its own — on exception, it publishes
`ti.enrichment.failed` (with `code_for_exception(error)` already computed,
so the event's `code` matches what `dispatch()`'s outer boundary will
independently arrive at) and then **re-raises the original exception
unchanged**. `dispatch()`'s existing generic exception boundary performs
the actual envelope translation, exactly as before this Part —
`EnrichIocCommandHandlerTests`/`EnrichIocDispatchErrorTranslationTests`
confirm both the event and the translated envelope independently.

---

## 8. Security / secret-leakage analysis

- `lookup_indicator()`'s return shape (`{"sha256"/"ip"/..., "found",
  "malicious", "suspicious", "harmless", "undetected", "verdict",
  "detection_ratio"}`) never carries the VirusTotal API key or any other
  configuration secret — confirmed by reading `ThreatIntelService.
  _format_verdict()` and the provider's response mapping; the events'
  `"result"` payload is exactly this shape, so nothing new is exposed by
  putting it in an event.
- The `started`/`failed` payloads carry only `ioc_type` and `value` (the
  indicator itself — already user-supplied input, not a secret) plus,
  for `failed`, the already-public `code`/`message` from `errors.py`'s
  existing `TI_*` mapping.
- `test_failed_event_emitted_and_reaches_broker_on_provider_error` asserts
  no `api_key`/`apikey` substring appears anywhere in any published
  event's payload.
- No event payload embeds a full report or any other large document —
  `enrich_ioc`'s payloads are all single-indicator-sized, not "giant report
  contents."

---

## 9. Tests executed

Command: `python -m unittest tests.test_application_layer -v`

**Result: all 77 tests pass** (67 pre-existing + 3 pre-existing `enrich_ioc`
tests updated for the new tuple return shape + 10 new tests added this
Part — see breakdown below). 0 failures, 0 errors.

Command: `python -m unittest tests.test_event_broker -v`

**Result: all 37 Part 1 tests still pass, unmodified.**

Combined: `python -m unittest tests.test_application_layer tests.test_event_broker -v`
→ **114 tests, all passing.**

### New tests added, by Stage 7 checklist item

**Broker integration (items 1-3)** — `AnalyzeReportBrokerIntegrationTests`:
- `test_events_reach_both_the_collector_and_the_broker_without_duplication`
  — asserts the collector's 1 event and the broker's 1 delivered event
  share the same `event_id` (not merely the same count).
- `test_default_broker_is_the_shared_application_broker` — asserts a
  handler constructed with no explicit `broker=` publishes to
  `get_application_broker()`'s singleton.

**enrich_ioc (items 4-10)** — `EnrichIocCommandHandlerTests`:
- `test_returns_enrichment_for_valid_sha256` — extended to assert the
  `started`→`completed` sequence, shared `correlation_id`, and payload
  contents.
- `test_started_and_completed_events_reach_the_broker` — asserts the
  broker's delivered events match the collector's, by `event_id`.
- `test_failed_event_emitted_and_reaches_broker_on_provider_error` —
  asserts `started`→`failed` sequence, correct IOC identity in the payload,
  and no secret material present.
- `test_handler_default_broker_is_the_shared_application_broker`.
- Existing `test_dispatched_via_command_name` / error-translation tests
  (`EnrichIocDispatchErrorTranslationTests`) unmodified in behavior, still
  pass — confirming `dispatch()`'s external envelope contract and
  provider-neutral error translation are exactly as before this Part.

**Event-loop regression (items 11-13, CRITICAL)** —
`EnrichIocEventLoopRegressionTests`:
- `test_enrich_ioc_from_a_running_event_loop_does_not_raise` — actually
  calls `handler.handle()` **synchronously, from inside a coroutine running
  on an active `asyncio.run()` loop** (the exact shape the architecture
  decision named as the hazard). Asserts `asyncio.get_running_loop().
  is_running()` was `True` at call time, that no exception was raised, and
  that the correct result and event sequence were produced.
- `test_enrich_ioc_failure_from_a_running_event_loop_still_translates_correctly`
  — same running-loop shape, but with a failing fake client; asserts the
  *original* domain exception (`InvalidHashError`) still propagates
  unchanged — confirming the fix changes only which thread runs the
  blocking call, not what it returns or raises.

Both tests were **actually executed**, not stubbed — this sandbox has no
network access but `_FakeVirusTotalClient` requires none; `fastapi` is not
required for this test since it reproduces the hazard shape directly with
`asyncio.run()`, not by instantiating the ASGI app.

**Concurrency (items 14-16)** — `EnrichIocConcurrencyTests`:
- `test_concurrent_enrichments_do_not_corrupt_each_others_results` — 8
  handlers, 8 threads, each with a distinct fake client/expected result;
  asserts every thread's result matches its own input, not another
  thread's.
- `test_broker_publication_is_thread_safe_under_concurrent_enrichment` — 10
  concurrent `handle()` calls sharing one `EventBroker`; asserts the
  subscriber receives exactly `2n` events (no loss, no duplication) with
  uncorrupted, correctly-attributed payloads.
- `test_one_failed_enrichment_does_not_poison_subsequent_requests` — one
  handler fails (via `ThreatIntelConnectionError`), then 6 more handlers
  run successfully through a fresh `ThreadPoolExecutor` of callers, sharing
  the same underlying `run_blocking()` worker pool; all 6 succeed.

### Additional manual verification (not `unittest`, run directly in this session)

- 20 sequential `enrich_ioc` calls → exactly 1 worker thread created
  (pool reuse, no leak).
- 12 concurrent `enrich_ioc` calls (artificially slowed fake client) →
  worker-thread count peaked at exactly 4 (`max_workers`), never exceeded
  it, and returned to steady state after completion (no leak, no
  unbounded growth).

---

## 10. Adversarial audit (Stage 8)

| Item | Result |
|---|---|
| Nested `asyncio.run()` | **PASS** — the only `asyncio.run()` call site remains `app/threat_intel/service.py:223`, unmodified; it now always executes on a fresh worker thread with no pre-existing loop, verified by the running-event-loop regression tests (§9) |
| Deadlocks | **PASS** — no new lock is held across a blocking call; the executor's and broker singleton's locks each guard only a lazy-construction check and are released immediately |
| Thread leaks | **PASS** — verified directly: bounded, reused pool; see manual verification in §9 |
| Executor leaks | **PASS** — exactly one `ThreadPoolExecutor` instance ever constructed (module-level, lock-guarded lazy init) |
| Duplicate events | **PASS** — `test_events_reach_both_the_collector_and_the_broker_without_duplication` and the concurrency test's exact `2n`-event count both confirm no duplication |
| Duplicate brokers | **PASS** — `get_application_broker()` is the single production source; `test_default_broker_is_the_shared_application_broker` (both handler test classes) confirms handlers actually use it by default |
| Handler-specific broker creation | **PASS** — grepped `handlers.py`: no handler constructs an `EventBroker()` itself; both accept an injectable `broker=` param defaulting to the shared singleton |
| Race conditions | **PASS** — `EnrichIocConcurrencyTests`, all 3 tests, actually exercised with real threads |
| Shared mutable state | **PASS** — limited to the two lock-guarded singletons (broker, executor); both were already designed thread-safe (broker: Part 1; executor: stdlib `ThreadPoolExecutor.submit` is documented thread-safe) |
| Secret leakage | **PASS** — see §8 |
| Oversized event payloads | **PASS** — all `enrich_ioc` payloads are single-indicator-sized; `analyze_report`'s payloads are unchanged from Part 1/pre-existing behavior |
| FastAPI imports in application layer | **PASS** — grepped every `app/application/*.py` import line; none |
| Qt imports in application layer | **PASS** — same grep; none |
| Tauri imports in application layer | **PASS** — same grep; none |
| `VirusTotalClient` imports outside the allowed threat-intel boundary | **PASS** — none in `app/application/*` |
| Changes to existing command contracts | **PASS with one documented exception** — `dispatch()`'s external, HTTP-facing contract for all 10 commands is unchanged. `EnrichIocCommandHandler.handle()`'s *internal* Python return shape changed from a bare `dict` to `(dict, EventCollector)`, mirroring `AnalyzeReportCommandHandler`'s pre-existing precedent exactly — required by Stage 5's own instruction to implement lifecycle events, and is not reachable from outside `app/application` (only `dispatch()` calls `.handle()` directly in production, and its own external contract is unchanged) |
| Changes to existing `EventCollector` semantics | **PASS** — `app/application/events.py` not modified this Part |

---

## 11. Environment limitations

Confirmed still absent in this sandbox (no network access to install):
`pytest`, `fastapi`, `httpx`, `uvicorn`, `PySide6`.

- `tests/test_threat_intel.py`, `tests/test_virustotal_provider.py`, and
  other `pytest`-based threat-intel test files fail to *import* with
  `ModuleNotFoundError: No module named 'pytest'` — reproduced directly;
  this is a **pre-existing environment limitation, not a regression**
  introduced by this Part (these files import `pytest` at module level and
  were equally unrunnable before any Part 2 edit).
- `tests/test_api_layer.py` and `tests/test_sidecar_entrypoint.py` require
  `fastapi`, also not installed — not run, not fabricated. `app/api/app.py`
  was not modified this Part, so this is unrelated to Part 2's changes.
- The event-loop regression tests (§9, Stage 7 items 11-13) do **not**
  require `fastapi` — they reproduce the exact hazard shape
  (`asyncio.run()`'s own running loop, synchronous call from inside it)
  directly with stdlib `asyncio`, which is sufficient to prove the fix
  without needing a real ASGI server. This was a deliberate test-design
  choice, not a workaround for a missing dependency — the same hazard
  would reproduce identically under real `uvicorn`, since the mechanism
  (`RuntimeError` from a nested `asyncio.run()`) is a property of
  `asyncio` itself, not of FastAPI.

No test result in this document was fabricated. Every number above comes
from an actual `python -m unittest` run in this session (§9), plus two
direct manual scripts for thread-pool bounding (also §9, explicitly labeled
as run outside `unittest`).

---

## 12. Files changed

- **New:** `app/application/execution.py` — narrow thread-execution
  boundary (`run_blocking`).
- **Modified:** `app/application/broker.py` — added
  `get_application_broker()` process-lifetime singleton accessor. The
  `EventBroker`/`Subscription` classes themselves are unchanged.
- **Modified:** `app/application/handlers.py` — `AnalyzeReportCommandHandler`
  and `EnrichIocCommandHandler` now publish to both `EventCollector` and
  `EventBroker`; `EnrichIocCommandHandler.handle()` now runs the blocking
  lookup via `run_blocking()` and returns `(response, EventCollector)`;
  `dispatch()`'s `enrich_ioc` branch updated to unpack that tuple (its own
  external return shape is unchanged). No other handler or command branch
  touched.
- **Modified:** `tests/test_application_layer.py` — updated 3 pre-existing
  `enrich_ioc` tests for the new tuple contract; added 10 new tests across
  4 new/extended test classes (`AnalyzeReportBrokerIntegrationTests`,
  extended `EnrichIocCommandHandlerTests`,
  `EnrichIocEventLoopRegressionTests`, `EnrichIocConcurrencyTests`).
- **New:** this document.

**Not modified:** `app/application/events.py`, `app/application/dto.py`,
`app/application/errors.py`, `app/application/responses.py`,
`app/threat_intel/*` (any file), `app/api/*` (any file), `frontend/*`,
`src-tauri/*`, `tests/test_event_broker.py`, any of the other 9 command
handlers.

---

## 13. Remaining Phase 4D SSE work (explicitly deferred, per Part 2 scope)

- `GET /events` SSE implementation (real `StreamingResponse`, SSE framing,
  headers) — `app/api/*`.
- Heartbeat / keep-alive frames.
- Client-disconnect → `broker.unsubscribe()` wiring, tied to the FastAPI
  request lifecycle.
- `app/api/entrypoint.py` wiring the broker into process startup/shutdown
  (`broker.shutdown()` on process exit) — currently the singleton has no
  shutdown call site anywhere in production code; this is intentionally
  out of scope until the SSE transport that would need it exists.
- Frontend `useEventStream.ts` implementation.
- Tauri event integration.
- Any cancellation/timeout model for long-running commands (named as an
  explicit, un-solved limitation in the architecture decision itself,
  §3 Option A).

---

## 14. Freeze status

**Phase 4D is NOT frozen.** This Part is additive, internal to
`app/application/*`, and does not implement or claim to implement SSE.
`PHASE4D_FREEZE.md` was not created or modified.

---

## 15. Full project ZIP

See packaging step, §16 below (this session) / the delivered file path.
