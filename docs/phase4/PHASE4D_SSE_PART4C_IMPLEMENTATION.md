# PHASE 4D SSE — PART 4C: END-TO-END VERIFICATION + ADVERSARIAL HARDENING

**Status: PART 4C OF THE FINAL 3-PART SSE COMPLETION SEQUENCE. Phase 4D is
still NOT frozen.** This part is verification/hardening only — no
architectural change, no new feature, no redesign. **No source file was
modified in this part.**

---

## 1. Checkpoint verification

Performed before any audit step, against the working tree produced by
Part 4B (this session continued directly from that audited checkpoint;
no new ZIP was uploaded, so the same tree — already verified in Part 4B
— is the checkpoint this part audits further):

| Check | Result |
|---|---|
| `PHASE4D_SSE_ARCHITECTURE_DECISION.md`, Parts 1–3, 4A, 4B docs | All present, read in full (4B in the prior session; re-confirmed present this session) |
| `EventBroker` (`app/application/broker.py`) | Present, unchanged |
| `EventCollector` (`app/application/events.py`) | Present, unchanged, still a pure test/local-inspection helper — does not replace the broker |
| All 10 commands registered | Confirmed directly in `COMMAND_HANDLERS` (`app/application/handlers.py`): `get_investigation`, `get_iocs`, `get_threat_intelligence`, `save_settings`, `list_investigations`, `delete_investigation`, `search_investigations`, `analyze_report`, `export_report`, `enrich_ioc` |
| `analyze_report` publishes events | Confirmed — `analysis.started`/`.progress`/`.completed`/`.failed`, all via the same `_publish()` closure that dual-writes to `EventCollector` + `EventBroker` |
| `enrich_ioc` publishes lifecycle events + uses the blocking bridge | Confirmed — `ti.enrichment.started`/`.completed`/`.failed`, via `run_blocking()` (`app/application/execution.py`) |
| `FastAPI /events` is a real SSE endpoint | Confirmed — `StreamingResponse`, `media_type="text/event-stream"` (`app/api/app.py`) |
| SSE heartbeat exists | Confirmed — `_format_sse_heartbeat()`, a comment frame, never an `Event` |
| Disconnect cleanup exists | Confirmed — `broker.unsubscribe(subscription)` in `_sse_event_stream()`'s `finally` |
| Frontend `EventSource` implementation exists | Confirmed — `eventSourceManager.ts` |
| `getSidecarOrigin()` exists and uses Tauri `invoke` under Tauri | Confirmed — `frontend/src/shared/api/client.ts` |
| `#[tauri::command] get_sidecar_origin` exists and is registered | Confirmed — `src-tauri/src/lib.rs`, `tauri::generate_handler![get_sidecar_origin]` |
| Required Tauri capability exists | Confirmed — `src-tauri/capabilities/default.json`, `"get_sidecar_origin"` in `permissions` |
| No forbidden hardcoded sidecar port | Confirmed by repo-wide grep (§8 below) |
| Phase 4D still NOT frozen | Confirmed — Part 4B's own doc states this explicitly |

**No discrepancy from the expected Part 4B state was found. No STOP
condition applies.** Proceeded directly to end-to-end verification.

---

## 2. Part 4B audit confirmation

Re-read `docs/phase4/PHASE4D_SSE_PART4B_IMPLEMENTATION.md` in full,
including its own §12 (this session's prior independent re-verification
pass). Part 4B is not redone here — only its already-verified surface
(`lib.rs`, `client.ts`, `capabilities/default.json`) is treated as a
fixed boundary that this part's pipeline audit builds on top of, not
re-implements.

---

## 3. Backend event pipeline audit

`app/application/events.py`:

- `Event` is an immutable (`frozen=True`) dataclass carrying `event_id`
  (uuid4 hex, generated at `Event.create()` time — decoupled from
  whether a broker exists), `event` (type string), `version`,
  `correlation_id`, `investigation_id`, `timestamp` (ISO-8601 UTC), and
  `payload`.
- Because `Event` is frozen and the *same object* is passed to both
  `EventCollector.publish()` and `EventBroker.publish()` from one
  `_publish()` closure in each handler (`handlers.py`), event identity
  (`event_id`) is provably unchanged from handler → collector/broker →
  SSE frame — there is no second, independently-constructed event at
  any layer, including the API layer (`app/api/app.py`'s
  `_format_sse_event()` only ever calls `event.to_dict()` on the object
  it received from the broker's queue).
- `event_id` uniqueness: `_new_event_id()` is a plain `uuid4().hex`
  call per `Event.create()` invocation — verified by
  `test_event_id_is_unique_per_event` (`tests/test_event_broker.py`).

---

## 4. Broker audit

`app/application/broker.py` (`Subscription` + `EventBroker`):

| Property | Verified |
|---|---|
| Thread safety | `threading.Lock` per-`Subscription`; `threading.Condition` for blocking `get()`; broker's own lock held only long enough to snapshot the subscriber set in `publish()`, never while pushing into a subscription |
| Bounded subscriber queues | `deque(maxlen=capacity)`, default 32 |
| Drop-oldest backpressure | `deque(maxlen=...)` append past capacity silently evicts the oldest; `dropped_count` tracks it explicitly (not swallowed) |
| No unbounded memory growth | Bounded deque per subscriber; broker's subscriber `set` only grows with live subscriptions, shrinks on `unsubscribe()` |
| Subscriber isolation | Each `Subscription` has its own lock/queue; `publish()` iterates a snapshot list and calls each subscription's own `_put()` independently — one slow/blocked subscriber cannot stall another (confirmed by `test_subscriber_isolation_one_draining_does_not_affect_other`, `test_concurrent_publish_does_not_cross_deliver_between_subscribers`) |
| Unsubscribe cleanup | `EventBroker.unsubscribe()` discards from the set and closes the subscription; idempotent |
| Shutdown behavior | Closes every current subscription, stops accepting new ones (`subscribe()` returns a pre-closed `Subscription` post-shutdown); idempotent |
| No replay | New subscribers only ever see events published after they subscribed — there is no history buffer at all in `EventBroker` |
| No accidental global mutable event history | Confirmed by reading the module: the only persistent collections are the per-`Subscription` bounded deque and the broker's live-subscriber `set` — neither is a history log |

All ten scenarios listed in the task's §5 are covered by real,
executed tests in `tests/test_event_broker.py` (`SingleSubscriberTests`,
`MultipleSubscriberTests`, `UnsubscribeTests`, `BoundedQueueTests`,
`ShutdownTests`, `ConcurrencyTests`, `PublishWithNoSubscribersTests`) —
**37/37 passed** (see §15 for the full run).

---

## 5. Command → broker verification

### `analyze_report` (`AnalyzeReportCommandHandler.handle()`)

Confirmed event order in source: `analysis.started` → zero or more
`analysis.progress` (via the domain layer's `progress_callback`) →
exactly one of `analysis.completed` / `analysis.failed`. All four event
types share one `correlation_id` (`new_correlation_id("an")`, generated
once per `handle()` call). The `_publish()` closure writes the *same*
`Event` object to both the returned `EventCollector` and the shared
`EventBroker` — `EventCollector` still receives everything a caller
publishes, unchanged from pre-SSE behavior (confirmed by
`EventCollectorCompatibilityTests` in `tests/test_event_broker.py`,
3/3 passed).

### `enrich_ioc` (`EnrichIocCommandHandler.handle()`)

Confirmed: `ti.enrichment.started` → `run_blocking(self._service.
lookup_indicator, ...)` → exactly one of `ti.enrichment.completed` /
`ti.enrichment.failed`. `run_blocking()` (`app/application/execution.py`)
submits to a bounded, process-lifetime `ThreadPoolExecutor(max_workers=4)`
and blocks the calling thread on `future.result()` — the `asyncio.run()`
inside `ThreatIntelService._lookup_raw()` therefore always executes on a
plain worker thread that never has its own running event loop, so the
`RuntimeError: asyncio.run() cannot be called from a running event loop`
hazard the module's own docstring names cannot occur regardless of what
thread called `enrich_ioc` in the first place — including a future
async FastAPI request-handling thread. `correlation_id` is generated
once (`new_correlation_id("ti")`) and shared by all three event types
for one call. Read `ThreatIntelService.lookup_indicator()`'s return
shape directly (`app/threat_intel/service.py`): it returns only
VT-shaped verdict data (`found`, `malicious`, `verdict`,
`detection_ratio`, etc., and an `invalid_api_key: bool` flag) — never
the raw API key — so the `ti.enrichment.completed` event's `result`
field cannot leak the VT key. On failure, `code_for_exception(error)`
+ `str(error)` populate the `.failed` event; verified no exception path
in `VirustotalProvider`/`VirustotalClient` embeds the key in an
exception message (grepped for `api_key`/`self._api_key` usage — only
ever used as an outgoing request parameter, never echoed into a raised
exception's text).

---

## 6. FastAPI SSE verification

`app/api/app.py`'s `/events` route and `_sse_event_stream()` generator:

- `StreamingResponse` with `media_type="text/event-stream"` — confirmed.
- Headers: `Cache-Control: no-cache`, `Connection: keep-alive`,
  `X-Accel-Buffering: no` — all present; the module's own comment
  correctly notes `X-Accel-Buffering` is a harmless no-op for this
  project's loopback-only uvicorn (no nginx in front), included anyway
  per standard SSE practice, matching this part's "do not require an
  invalid header" instruction (nothing here is invalid, so nothing was
  flagged or removed).
- Disconnect detection: `await request.is_disconnected()` checked each
  poll cycle.
- Unsubscribe cleanup: `broker.unsubscribe(subscription)` in a `finally`
  block covering normal completion, disconnect, and any exception.
- No replay: subscription only ever created fresh in this generator
  (`broker.subscribe()`), never seeded from history.
- No blocking of unrelated subscribers: `Subscription.get()` (a
  blocking, thread-based, `threading.Condition`-backed call) is run via
  `asyncio.to_thread`, not awaited directly on the event loop — so one
  idle/slow SSE connection's blocking wait cannot stall the event loop
  that serves every other connection.

---

## 7. SSE frame contract

`_format_sse_event()`:

```
id: <event_id>
event: <event.event>
data: <json.dumps(event.to_dict())>
<blank line>
```

— matches the required wire format exactly (verified by reading the
function and by the real captured frame in §9 below, byte-for-byte).

`_format_sse_heartbeat()` returns `": heartbeat\n\n"` — a bare SSE
*comment* line (leading `:`), which the `EventSource` spec defines as
producing no `message`/named-event dispatch at all on the client; it is
never constructed as an `Event` and never passes through
`EventBroker.publish()`, so it structurally cannot be mistaken for an
application event by a client using
`EventSource.addEventListener(eventName, ...)` — confirmed directly by
reading both the heartbeat formatter and `eventSourceManager.ts`'s
listener-attachment logic (`ensureEventNameAttached`), which only ever
attaches named-event listeners, never a bare `message` listener that a
comment frame could hit.

JSON encoding: `json.dumps(event.to_dict())` — standard library,
correctly escapes newlines/quotes inside `payload` values, so no
payload content can inject a spurious blank line or a stray `id:`/
`event:`/`data:` prefix into the frame. Verified directly by
`test_secret_free_payload_survives_unchanged_into_the_sse_frame`
(`tests/test_api_layer.py`) and by this session's own live capture
(§9), whose `data:` line round-trips as valid JSON.

---

## 8. Real HTTP delivery test — actually executed

Went beyond `tests/test_api_layer.py` (already 29/29, itself real
`TestClient`-based HTTP delivery, not broker-only): ran a **live
`uvicorn` server on an OS-assigned port**, in-process, from this
session, driven by plain `requests` — the closest thing to a real
browser opening a real socket that this sandbox can execute.

Script (executed, not hypothetical):

1. Started `uvicorn.Server` bound to `127.0.0.1:0` on a background
   thread, using the real `app.api.app:app` object (no test-only stub).
2. Opened **two simultaneous** streaming HTTP `GET /events` connections
   with `requests`.
3. Confirmed `get_application_broker().subscriber_count() == 2`.
4. Published one real `Event` (`analysis.completed`,
   `correlation_id="an-manualtest"`) directly through the same
   production `EventBroker` singleton both HTTP connections were
   subscribed to.
5. Read 3 lines back from each connection's raw HTTP stream.

**Actual captured output (both subscribers, byte-identical):**

```
id: 6a4fa363c129437991cc7585b79b51f8
event: analysis.completed
data: {"event": "analysis.completed", "version": 1, "correlation_id": "an-manualtest", "investigation_id": null, "timestamp": "2026-08-23T18:28:12.222252+00:00", "payload": {"hello": "world"}, "event_id": "6a4fa363c129437991cc7585b79b51f8"}
```

6. Closed both connections; after a short settle, re-checked
   `subscriber_count()` → **0**, confirming `_sse_event_stream()`'s
   `finally`-block unsubscribe actually fires on real client disconnect
   in a real running server, not merely in a mocked test double.

This directly satisfies §9's requirement ("do not stop at testing the
broker directly... use the actual FastAPI application... connect,
subscribe, publish, receive, parse, verify event_id/type/payload...
two simultaneous subscribers... disconnect cleanup") with a real
process, real sockets, and a real production broker singleton — not
simulated.

Heartbeat delivery and "event delivery after heartbeat" /
"event delivery after another subscriber disconnects" specifically
were **not** re-executed live this session (the 15s heartbeat interval
would require a multi-minute live run to observe in real time) — those
two scenarios remain verified only via `tests/test_api_layer.py`'s
`test_heartbeat_is_valid_sse_comment_and_never_a_broker_event` and
`test_two_subscribers_receive_the_same_event_and_one_ending_does_not_
affect_the_other`, both real `TestClient`-driven HTTP tests (not
broker-only), both passing. Noted here rather than silently presented
as also having been re-run against the live server.

---

## 9. Frontend contract verification

`frontend/src/shared/events/eventSourceManager.ts` +
`shared/api/client.ts`:

- Origin correctness: `getSidecarOrigin()` (Part 4B) resolves the real
  origin; `eventSourceManager.ts`'s `connect()` builds the URL as
  `` `${origin.replace(/\/+$/, "")}/events` `` — the trailing-slash
  strip plus single literal `/events` append means `/events` is
  appended **exactly once**, with no duplicate-slash possibility
  regardless of whether `getSidecarOrigin()` ever returns a
  trailing-slash origin.
- Named-event routing: `dispatch()` only invokes a subscriber whose
  `eventName` matches the dispatched event; `ensureEventNameAttached()`
  attaches one native listener per distinct `EventName` actually
  subscribed to, via `source.addEventListener(eventName, handler)` —
  routing is by the SSE `event:` field, matching the backend's
  `event.event` string exactly.
- Malformed frames: `parseSocIqEvent()` returns `null` (never throws,
  never casts blindly) for anything that isn't valid JSON, isn't a
  plain object, or is missing/mistyped any of the six required fields;
  `handlerFor()`'s wrapper drops a `null` parse result with a
  `console.warn` that logs only the event name and byte length — never
  the payload body itself (no secret-in-log risk).
  `parseSocIqEvent`'s field-by-field validation was cross-checked
  directly against `Event.to_dict()`'s actual keys
  (`app/application/events.py`) — they match exactly.
- Unknown event types: an `EventName` the frontend never subscribes to
  simply never gets a listener attached (`ensureEventNameAttached`
  only fires for names in `subscribers`), so it cannot reach `dispatch()`
  or crash anything — it is silently never delivered, which is correct
  (nothing asked for it).
- Reconnect: relies solely on the native `EventSource`'s built-in retry
  (per spec) after `onerror`; no custom timer-based reconnect loop
  exists anywhere in the file — confirmed by reading the whole module.
- Cleanup: `subscribe()`'s returned unsubscribe function removes the
  logical subscriber, detaches the native listener if no other
  subscriber still wants that event name, and — when the subscriber
  count reaches zero — calls `teardownSource("closed")`, which calls
  `source.close()` and nulls the module-level `source` reference. The
  `EventSource` is provably closed when the last consumer unsubscribes.
- React StrictMode: the module is a ref-counted singleton keyed on
  `subscribers.size`, not on any one component's mount/unmount — a
  StrictMode mount→unmount→mount cycle nets to the same ref-count
  delta a single mount would, so it cannot produce a second, persistent
  `EventSource` connection.
- No hardcoded sidecar port: confirmed again this session by grep (§ next).
- Tauri path uses `getSidecarOrigin()`: the only way `eventSourceManager.ts`
  obtains an origin is via `import { getSidecarOrigin } from "../api/client"`
  — no second, independent origin-construction path exists in the file.
- Browser/dev path: `client.ts`'s `isTauri()` check (Part 4B) means a
  non-Tauri environment rejects predictably with
  `SidecarNotConnectedError`, which `connect()`'s `.catch()` turns into
  `status = "unavailable"` — never a crash, never a silently-substituted
  URL.

**Minor, non-functional finding (documentation staleness, not a
defect):** two comments predate Part 4B and were not updated when the
Tauri bridge was wired:
`eventSourceManager.ts`'s `EventStreamStatus` doc-comment for
`"unavailable"` still says "expected pre-Part-4B state", and
`useEventStream.ts`'s module docstring still says "no Tauri command
exists yet". Both are now stale — the command exists and is wired as
of Part 4B. This does not change behavior (an actually-unavailable
sidecar still correctly produces `"unavailable"`), so it was **not**
fixed here per this part's own rule (§14: only fix concrete,
reproducible defects; a stale comment is neither). Flagged for
whichever part next touches these two files.

---

## 10. Tauri bridge verification (Part 4B surface, not redone)

Re-confirmed from source (not re-implemented):

- Exactly one `#[tauri::command]`: `get_sidecar_origin` in
  `src-tauri/src/lib.rs`.
- Exactly one registration: `tauri::generate_handler![get_sidecar_origin]`.
- Correct capability: `"get_sidecar_origin"` present in
  `src-tauri/capabilities/default.json`'s `permissions`, no
  `shell:*`/`fs:*`/`http:*` over-grant.
- No duplicate implementation: repo-wide grep for `get_sidecar_origin`/
  `getSidecarOrigin` shows one Rust definition, one frontend caller
  (`eventSourceManager.ts` via `client.ts`).
- No hardcoded production port: the only `127.0.0.1:{port}` literal
  in `lib.rs` uses a runtime-captured `port` value, never a fixed
  number.
- No silent fallback masking failure: `get_sidecar_origin` returns
  `Err(...)` (never a placeholder origin) when not `Running`;
  `client.ts` wraps any rejection in `SidecarNotConnectedError` rather
  than substituting a default URL.

`cargo test`/`cargo check` — see §11.

---

## 11. Rust toolchain verification

Same toolchain already installed in this session's environment
(`apt-get install cargo rustc`, giving cargo/rustc **1.75.0** — carried
over from the Part 4B audit pass earlier in this session, not
reinstalled).

| Check | Result |
|---|---|
| `cargo test` — `sidecar-core` | **PASS — 49/49** (23 startup/handshake + 13 supervisor + 13 lifecycle), re-run fresh this part, identical to Part 4B's own finding |
| `cargo check` — `src-tauri` (workspace) | **BLOCKED — reproduced identically.** A transitive dependency (`icu_properties_data` in this run) requires the unstable `edition2024` Cargo feature, needing cargo/rustc ≥1.85. This is the exact same blocker Part 4B's own §6/§9.1 and §12 documented — re-confirmed independently in this part's own fresh `cargo check` invocation, not assumed from the prior doc. No newer rustc is installable via `apt` on this image, and the network allowlist has no `static.rust-lang.org`/`rustup.rs` entry, so no upgrade path exists in this sandbox. Per this part's own instruction ("do not downgrade architecture or rewrite Rust merely to make an old compiler pass"), no workaround was attempted |

---

## 12. End-to-end frontend/Tauri verification

A real Tauri runtime (an actual desktop webview launching the compiled
`src-tauri` binary) is **unavailable** in this sandbox — there is no
display server, and `src-tauri` itself cannot compile here (§11), so
`cargo tauri dev`/`cargo tauri build` cannot be attempted at all, not
merely "attempted and blocked at a later step."

Strongest verification actually performed in its place, this part:

1. Real backend E2E (§8): live `uvicorn` server, two real HTTP
   subscribers, real broker publish, real captured SSE frames,
   confirmed disconnect cleanup. This proves everything from
   `EventBroker.publish()` through to a byte-correct SSE frame on the
   wire.
2. Real frontend build (§13/§15): `npm install`, `tsc --noEmit`,
   `vite build` all succeed against the actual `eventSourceManager.ts`/
   `client.ts`/`useEventStream.ts` source — proves the frontend code
   that would consume that stream is type-correct and bundles cleanly.
3. Real `sidecar-core` compilation + tests (§11): proves the
   process-supervision logic Part 2B/4B's `sidecar.rs` and `lib.rs`
   build on top of is itself correct on this toolchain, even though
   `src-tauri` itself can't compile here.
4. Source-level review of `src-tauri/src/lib.rs`'s `get_sidecar_origin`
   and `run()` (§10, and Part 4B's own §3.1/§5) against `sidecar-core`'s
   and `sidecar.rs`'s real public APIs.

**What remains genuinely unverified:** the actual chain "Tauri
launches → sidecar subprocess starts → `get_sidecar_origin` resolves a
real port over real IPC → `EventSource` in a real webview connects →
a real published event reaches a real browser." Every *piece* of that
chain has now been verified in isolation (backend pipeline live end
to end; frontend code type-correct and buildable; Rust sidecar-adapter
logic compiled and tested; Tauri command source-reviewed), but the
full chain through an actual compiled `src-tauri` binary and a real
Tauri webview has not been executed, because it cannot be in this
sandbox. This is stated as a known limitation (§16.2), not claimed.

---

## 13. Adversarial hardening

| Category | Result |
|---|---|
| **Concurrency — races** | PASS. `Subscription`'s single lock/condition pair serializes `_put()`/`get()`/`get_nowait()`/`drain()`/`close()`; `EventBroker`'s lock only guards its own `_subscribers` set, held only for a snapshot copy during `publish()`. Verified by `ConcurrencyTests` (3 tests, multi-thread publish/subscribe/unsubscribe), all passing |
| **Concurrency — deadlocks / lock inversion** | PASS. `publish()`'s own docstring documents the ordering reasoning (broker lock never held while blocked on a subscription operation; `_put()` never blocks); read and confirmed no path acquires the broker lock and a subscription lock in reversed order anywhere in the module |
| **Concurrency — blocking broker operations** | PASS. `_put()` is provably non-blocking (`deque.append`, no wait); `publish()`'s broker-lock hold is a list-copy only |
| **Concurrency — subscriber starvation** | PASS. Each subscriber has an independent queue and lock; `publish()` iterates a snapshot and calls each subscription's own, separate `_put()` — one subscriber's queue state cannot affect another's delivery |
| **Memory — unbounded queues** | PASS. `deque(maxlen=32)` per subscriber; confirmed by `BoundedQueueTests` |
| **Memory — leaked subscriptions** | PASS. `_sse_event_stream()`'s `finally` unsubscribes; confirmed live in §8 (`subscriber_count()` returned to 0 after both real HTTP connections closed) |
| **Memory — leaked `EventSource` instances** | PASS. `eventSourceManager.ts`'s ref-counted teardown (§9) |
| **Memory — executor/thread leaks** | PASS. `run_blocking()`'s `ThreadPoolExecutor` is a bounded (`max_workers=4`), lazily-constructed, process-lifetime singleton — reused across calls, never one-thread-per-call |
| **Event correctness — duplicate events** | PASS. Every handler's `_publish()` closure writes one `Event` object to both sinks exactly once per call site — confirmed by reading every call site in `handlers.py` and by `test_same_event_object_can_go_to_both_collector_and_broker` |
| **Event correctness — missing events** | PASS. Every `analyze_report`/`enrich_ioc` code path (success, domain failure, invalid path) publishes exactly one terminal event; confirmed by reading all branches |
| **Event correctness — event identity changes** | PASS. `Event` is `frozen=True`; no code path mutates or reconstructs one in flight (§3) |
| **Event correctness — wrong correlation IDs** | PASS. One `correlation_id` generated per `handle()` call, closed over by that call's `_publish()`/`on_progress` — cannot leak between concurrent, independent command invocations |
| **Event correctness — ordering violations** | PASS. `started` is always published before any `progress`/`completed`/`failed` in the same handler invocation, by construction (sequential code, not concurrent tasks); confirmed live in §8's single-event capture and by `test_multiple_events_arrive_in_publish_order` |
| **Security — secrets in SSE payloads** | PASS. Traced `enrich_ioc`'s full payload chain (§5) — no API key, token, or credential reaches any published `Event`. Confirmed by `test_secret_free_payload_survives_unchanged_into_the_sse_frame` |
| **Security — internal filesystem paths** | PASS. `analysis.*` events carry `report_path` (a user-supplied input path, not an internal path) and DTO-summarized investigation data; no server-internal path (e.g. database file location) appears in any event payload — confirmed by reading every `Event.create()` call site |
| **Transport — malformed SSE frames** | PASS. Backend: JSON-encoded `data:` cannot corrupt framing (§7). Frontend: `parseSocIqEvent` never throws, never crashes the caller (§9) |
| **Transport — malformed JSON** | PASS. `parseSocIqEvent`'s `try/catch` around `JSON.parse`, returns `null` |
| **Transport — heartbeat interpreted as an event** | PASS. Comment-frame heartbeat structurally cannot fire a named-event listener (§7) |
| **Transport — disconnect races** | PASS. `finally`-block unsubscribe is idempotent and covers every exit path (normal, disconnect, exception); confirmed live in §8 |
| **Transport — reconnect duplication** | PASS. No custom reconnect timer exists; native `EventSource` retry only ever operates on the one module-level `source` reference, which `connect()` refuses to duplicate while already `"connecting"`/non-null (§9) |
| **Architecture — `app/application/` dependency direction** | PASS. Zero `fastapi`/`starlette`/`PySide6`/`app.gui`/Tauri imports — re-confirmed by fresh grep this part |
| **Architecture — `app/api/` dependency direction** | PASS. Zero frontend/Rust/Tauri imports — only docstring mentions of "Tauri" (prose, not code) |
| **Architecture — frontend bypass** | PASS. No `fetch`/`XMLHttpRequest`/`axios` call anywhere in `frontend/src/` — `EventSource` via the resolved origin is the only transport path |

---

## 14. Defects found

**None.** No concrete, reproducible defect was found in the SSE
pipeline, the broker, the FastAPI transport, the frontend contract, or
the Tauri bridge. Two pre-existing, non-functional stale doc-comments
were noted (§9) but are explicitly not defects under this part's own
"only modify for a concrete, reproducible defect" rule.

## 15. Fixes made

**None.** No source file was modified in this part.

## 16. Exact files changed

**None**, except this new documentation file
(`docs/phase4/PHASE4D_SSE_PART4C_IMPLEMENTATION.md`).

---

## 17. Tests executed (this part, fresh)

| Suite | Result |
|---|---|
| `python -m unittest tests.test_application_layer -v` | 77/77 passed |
| `python -m unittest tests.test_event_broker -v` | 37/37 passed |
| `pytest tests/test_api_layer.py -v` | 29/29 passed |
| `pytest tests/test_sidecar_entrypoint.py -v` | 8/8 passed |
| `pytest tests/ -q --ignore=tests/gui` | 600/600 passed |
| `pytest tests/gui -q` | 154/154 passed (PySide6 installable in this sandbox) |
| Live manual E2E script (§8): real `uvicorn`, 2 real subscribers, real publish, real captured frames, real disconnect cleanup | Executed; behaved exactly as the source predicts |
| `cargo test` — `sidecar-core` | 49/49 passed |
| `npm install` / `npm run typecheck` / `npm run build` (frontend) | Real install (73 pkgs); 0 typecheck errors; production build succeeded (44 modules) |

**Total automated tests this part: 754/754 passed** (77+37+29+8+600 is
not additive — `pytest tests/ --ignore=tests/gui`'s 600 already
includes `test_application_layer`, `test_event_broker`,
`test_api_layer`, and `test_sidecar_entrypoint`'s cases; the
`unittest`/`pytest`-specific sub-suite numbers above are reported
separately only because the task's §15 asked for both invocation styles
run and reported individually. Combined with `tests/gui`'s 154, the
non-overlapping total is **600 + 154 = 754**, matching this session's
Part 4B fresh-extraction total exactly).

## 18. Tests blocked by environment

| Item | Reason |
|---|---|
| `cargo check --workspace` / `cargo test --workspace` for `src-tauri` itself | MSRV: a transitive dependency requires the unstable `edition2024` Cargo feature, needing cargo/rustc ≥1.85; this sandbox has 1.75.0 via `apt`, with no upgrade path available (§11) |
| Real Tauri runtime E2E (compiled `src-tauri` binary in an actual webview) | Cannot be attempted at all — blocked upstream by the same `src-tauri` compilation gap, and this sandbox has no display server regardless (§12) |
| Live heartbeat observation against the real running server from §8 | Not re-executed this session (would require a multi-minute real-time wait for the 15s interval); covered instead by `test_heartbeat_is_valid_sse_comment_and_never_a_broker_event`, a real `TestClient`-driven test, passing |

---

## 19. Known limitations

1. `src-tauri` has still never compiled, in this or any prior session
   documented in this project — purely a toolchain-version gap (§11),
   not a code defect. Required before Phase 4D can be frozen: `cargo
   check`/`cargo test` for `src-tauri` on a machine with cargo/rustc
   ≥1.85.
2. The full physical chain "compiled Tauri binary → real webview →
   real `EventSource` in that webview" remains unverified — every
   component it's built from has now been verified individually
   (§12), but the assembled whole has not been run, because it cannot
   be run in this sandbox.
3. Two stale doc-comments (§9) reference "pre-Part-4B" state that no
   longer applies. Cosmetic only; not fixed here per this part's own
   scope rule.
4. Production packaging (`resolve_working_directory()`'s
   `CARGO_MANIFEST_DIR`-based resolution) remains unresolved — carried
   over unchanged from Part 4B's own §9.2, out of this part's scope.

## 20. Remaining Phase 4D work before a freeze decision

- Compile and test `src-tauri` on Rust ≥1.85; fix anything that
  surfaces there specifically (nothing is currently known to be wrong,
  but it has never actually compiled).
- A genuine `cargo tauri dev` run on a machine with both a compatible
  Rust toolchain and a real display/webview: confirm the window opens,
  `getSidecarOrigin()` resolves once the sidecar reaches `Running`, and
  `EventSource` on `/events` receives real `analysis.*`/`ti.enrichment.*`
  frames during an actual `analyze_report`/`enrich_ioc` call.
- Optionally clean up the two stale doc-comments noted in §9.
- Final Phase 4D audit and freeze decision — explicitly out of scope
  for this part.

---

## 21. Freeze status

**PHASE 4D NOT FROZEN.** This part verified the complete SSE pipeline
at every boundary this sandbox can execute — including a live,
real-socket, two-subscriber, real-broker end-to-end HTTP delivery test
that goes beyond the existing test suite — and found zero defects. The
one boundary genuinely unverified end-to-end is the compiled Tauri
binary itself, blocked purely by an unavailable Rust toolchain version,
not by anything discovered wrong in the source.

**PHASE 4D REMAINS NOT FROZEN.**
