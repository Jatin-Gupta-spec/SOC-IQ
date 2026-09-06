# PHASE 4D — SSE ARCHITECTURE DECISION

**Status: ARCHITECTURE DECISION ONLY. No implementation in this Part.**

This document resolves the sync-vs-async question and the shape of the event
broker/SSE transport left open by `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md`
§21 ("NEW this phase: whether `analyze_report`'s response should stay
synchronous ... This needs a decision, not another simplification, before
`enrich_ioc` or any other long-running command is added."). It does not
implement any of it. Every section below is marked **CURRENT STATE** or
**APPROVED FUTURE ARCHITECTURE** so the two are never conflated.

---

## 1. Current event architecture — CURRENT STATE

Verified directly against the checkpoint (`app/application/events.py`,
`app/application/handlers.py`, `app/api/app.py`; all four command handlers
that touch events were read in full).

| Question | Answer |
|---|---|
| Event creation | Only `AnalyzeReportCommandHandler.handle()` creates events (`analysis.started/progress/completed/failed`). No other handler constructs an `Event`. |
| Event ownership | The `EventCollector` instance is a local variable created and owned by `AnalyzeReportCommandHandler.handle()` for the duration of one call. Nothing outside that call frame holds a reference. |
| Event lifetime | Exactly one Python call stack. The collector is created, populated, returned as part of a `(response, collector)` tuple, and then goes out of scope. `dispatch()` (the one production caller) even unpacks it as `response, _collector = ...handle(request)` and discards it (`handlers.py:481`). |
| Event visibility | Only the caller of `.handle()` directly — currently only `tests/test_application_layer.py`, since `dispatch()` throws the collector away. |
| Event delivery | No — events cannot currently leave the handler's call frame. There is no publish-to-elsewhere step. |
| Event persistence | None. Never written to the database, disk, or any queue. |
| Event replay | Not possible. There is nothing to replay from once the call returns. |
| Event ordering | Defined and correct *within one collector*: `Event`s are appended to a plain `list` in the order `.publish()` is called, so `started → progress× N → completed|failed` is guaranteed for that one collector. There is no ordering guarantee *across* collectors (there's no shared stream for them to be ordered on). |
| Event IDs | No per-event ID field exists. `Event` (frozen dataclass) has `event`, `version`, `correlation_id`, `investigation_id`, `timestamp`, `payload` — no `id`/`event_id`. All events sharing one command execution share one `correlation_id`, but that identifies the *command run*, not the individual event. |
| Multiple consumers | No. One collector, one list, one implicit consumer (whoever called `.handle()`). There's no mechanism for a second consumer to attach. |
| Failure behavior | N/A — there is no delivery step to fail. `EventCollector.publish()` is a synchronous `list.append()`; it cannot itself fail short of an exception in `Event.create()`, which is not caught. |
| Concurrency | Not thread-safe and not designed to be. `EventCollector.events` is a plain `list` with no lock. This is fine today only because each collector is single-owner, single-thread, single-call-frame — the moment a collector (or its replacement) is shared across threads/coroutines, this becomes a real bug, not a latent one. |

**Conclusion:** `EventCollector` is exactly what its own module docstring says
it is — "an in-process stand-in for the eventual SSE publisher," built so
`tests/test_application_layer.py` can assert on event *sequencing and
correlation*, not a transport of any kind. Treating it as one today would be
building on a foundation that was explicitly never designed to be shared,
persisted, replayed, or read concurrently.

`EnrichIocCommandHandler` currently publishes **no events at all** — it is a
plain `ok(self._service.lookup_indicator(...))` call (`handlers.py:311-313`).
The frontend's `EventName` union already anticipates
`ti.enrichment.started/completed/failed` (`frontend/src/shared/events/types.ts`),
but nothing on the backend produces them yet. This is a real gap, not an
oversight in this audit — see §5.

---

## 2. Additional CONFIRMED finding this Part: `enrich_ioc`'s existing event-loop hazard

Not previously documented. Traced the full call chain:

```
EnrichIocCommandHandler.handle()
  → ThreatIntelService.lookup_indicator()
    → ThreatIntelService._lookup_raw()
      → asyncio.run(provider.lookup_raw(ioc))      # service.py:223
        → VirusTotalProvider.lookup_raw()
          → asyncio.to_thread(client.lookup_sha256, ...)   # virustotal_provider.py:261 (etc.)
            → requests.Session.get/post (blocking, virustotal.py)
```

`ThreatIntelService._lookup_raw` bridges the provider's `async def lookup_raw`
onto a synchronous caller by calling **`asyncio.run(...)`** — its own
docstring says exactly this ("bridging its `async lookup_raw()` onto this
method's synchronous callers"). `asyncio.run()` creates a *new* event loop
and raises `RuntimeError: asyncio.run() cannot be called from a running
event loop` if one is already running on that thread.

`app/api/app.py`'s `run_command` is `async def`, and calls
`handler(payload)` — i.e. `dispatch()` — **directly, in the request
coroutine, on the event loop thread**, not via `asyncio.to_thread` or a
threadpool. FastAPI only offloads a route to a worker thread automatically
when the route function itself is a plain `def`; `run_command` is `async
def`, so nothing does that here.

**Consequence, CONFIRMED by reading the code (not run — `fastapi` is not
installed in this sandbox, consistent with
`docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md` §19):** calling
`POST /commands/enrich_ioc` against a running `uvicorn` server today would
raise `RuntimeError` inside `_lookup_raw`, which `dispatch()`'s catch-all
`except Exception` (handlers.py:495) would turn into a generic
`INTERNAL_ERROR` envelope rather than a `501`/validation-style error — i.e.
the failure is currently silent-looking (a normal-shaped error envelope)
rather than loud. `tests/test_api_layer.py` has no `enrich_ioc` test, so this
has never been exercised end-to-end; `tests/test_application_layer.py` only
exercises handlers that don't reach this code path via `dispatch()` in this
checkpoint (enrich_ioc has no application-layer test file entry either —
confirmed by `grep -n enrich_ioc tests/test_api_layer.py` returning nothing).

This is not a hypothetical the SSE decision has to *guess about* — it's a
concrete, already-present sync/async boundary bug, independent of SSE, that
the chosen architecture must not make worse and should ideally close. It
directly informs §4.

---

## 3. Sync vs. async decision — APPROVED FUTURE ARCHITECTURE

**Decision: keep command *execution* synchronous. Add asynchronous, thread-safe
event *distribution* underneath it. This is Option A (with the Option C
escape hatch named explicitly for `enrich_ioc`, not adopted wholesale).**

### Option A — Synchronous commands + thread-safe event broker

- **Complexity:** Low. `dispatch()`, every handler, and every DTO are
  unchanged in shape. Only `EventCollector.publish()` gains a second
  destination (the broker) alongside/instead of its local list.
- **Compatibility with existing handlers/dispatch/DTOs/envelopes:** Full.
  `AnalyzeReportCommandHandler` already collects+returns events in exactly
  the shape needed; only the *sink* changes.
- **FastAPI compatibility:** `POST /commands/{name}` stays `async def` but
  its body remains a synchronous call — safe today, and closes §2's bug
  for every handler *except* the specific blocking span inside
  `enrich_ioc` (see below).
- **Tauri/React compatibility:** No effect — Tauri/React only ever see
  HTTP responses and SSE frames, never Python call semantics.
- **Thread safety:** Required and addressed directly — the broker (§6) is
  the one new piece of shared state, so it is the one piece designed for
  concurrent access from the start (a lock or a thread-safe queue per
  subscriber).
- **Cancellation / timeout:** Command execution has no cancellation model
  today and Option A doesn't add one — a long `analyze_report` or
  `enrich_ioc` call still runs to completion or exception. This is a real
  limitation, named here rather than solved.
- **Long-running commands:** Still block the request thread/coroutine for
  their full duration, same as today. Acceptable for a loopback, single-user
  sidecar (§14 of the existing doc — already-decided trust model), not
  acceptable if SOC-IQ ever serves concurrent multi-user requests.
- **Error propagation:** Unchanged — handlers already translate every
  exception to a `fail()` envelope or a `*.failed` event.
- **Event ordering / multiple SSE clients / disconnect handling:** Owned
  entirely by the broker (§6), not by command execution — this is exactly
  why decoupling transport from execution is the right cut line.
- **Testing complexity:** Lowest of the three options — `dispatch()` stays
  synchronous and directly unit-testable exactly as
  `tests/test_application_layer.py` already does it.
- **Backward compatibility / migration cost:** Smallest. No handler
  signature changes. `EventCollector` is retained, not replaced (§9).
- **Risk of architectural rewrite:** Lowest. This is additive, matching
  the existing project convention (§5.1/§20 of
  `PHASE4D_API_EVENT_ARCHITECTURE.md`: "Additive-only... no existing file
  requires reverting").
- **Impact on existing 10 commands:** Zero required changes to the 9
  commands that don't emit events. `AnalyzeReportCommandHandler` gets one
  new call (`broker.publish(event)` alongside/instead of
  `collector.publish(event)`).

### Option B — Async command execution + async event broker

- **Complexity:** High. Every handler's `.handle()` becomes `async def`;
  `dispatch()` becomes `async def`; `COMMAND_HANDLERS` lambdas become
  coroutines; `InvestigationService`/`ReportingService`/`SettingsService`
  calls (all synchronous, SQLite-backed) would need `asyncio.to_thread`
  wrapping at every call site to avoid blocking the loop, or a rewrite to
  an async DB driver.
- **Compatibility with existing handlers/dispatch:** Breaking. All 10
  handlers change signature; `tests/test_application_layer.py`'s 67
  currently-passing synchronous tests (§ verification below) would need an
  async test runner.
- **Compatibility with DTOs/envelopes:** Unaffected in shape, but every
  call site producing them moves into a coroutine.
- **FastAPI compatibility:** Natural fit *for the transport layer only* —
  but the transport layer is already async today (`app.py`'s routes are
  `async def`); the pain is entirely on the application-layer side, which
  currently has zero async dependency by design (§5.1 of the existing
  doc: "application layer must not depend on FastAPI" — Option B doesn't
  violate that rule directly, but it does import the async programming
  model into a layer that was deliberately kept transport-agnostic and
  synchronous so `tests/test_application_layer.py` could exercise it with
  plain `unittest`).
- **enrich_ioc specifically:** Would *fix* §2's bug directly (no more
  `asyncio.run()` inside a running loop — the call would just be
  `await provider.lookup_raw(ioc)`), but at the cost of rewriting the
  other 9 handlers' calling convention to fix one handler's bug.
- **Thread safety:** Delegated to the event loop's single-thread model —
  simpler *in principle*, but SOC-IQ's domain services are not async-native
  today, so real concurrency still happens via `asyncio.to_thread` calls
  that need the same care as Option A's explicit locking.
- **Testing complexity:** Highest — async test infrastructure across the
  entire application layer, not just the new broker.
- **Migration cost / rewrite risk:** Highest of the three. This is the
  option "selected merely because it looks modern" that §4 of the task
  brief warns against — rejected for that reason plus the concrete cost
  above.

### Option C — Synchronous command API + background worker execution + event broker

- **What it adds over Option A:** long-running commands (`analyze_report`,
  and potentially `enrich_ioc`) are handed to a background
  thread/executor; the HTTP response returns immediately
  (`{"correlation_id": ..., "status": "accepted"}` — the exact shape
  `PHASE4D_API_EVENT_ARCHITECTURE.md` §7 already names as the intended
  eventual response), and all further progress is observable only via
  SSE.
- **Complexity:** Medium — needs a worker pool/executor and a
  status-tracking mechanism (so a client that connects to `/events` after
  the command already started can still get a sane answer), on top of
  everything Option A already needs.
- **Compatibility with existing handlers:** Requires `AnalyzeReportCommandHandler`
  (and, if adopted for it, `EnrichIocCommandHandler`) to change from
  "return the full result" to "return an acceptance, publish results only
  as events" — a real behavior change to the *response contract*, not just
  the transport, that `PHASE4D_API_EVENT_ARCHITECTURE.md` §7 already flags
  as a known future step, not yet taken.
- **enrich_ioc:** Directly relevant — see §5. This is the option that
  would house `enrich_ioc`'s blocking network I/O off the request thread
  *without* the full Option B rewrite.
- **Cancellation / timeout:** The one option that can actually support
  cancellation meaningfully (a background task can be cancelled;
  a synchronous in-request call cannot, short of dropping the whole
  connection).
- **Risk:** Concurrency now spans two things — the broker (shared state,
  Option A already needs this) and the worker pool (shared execution,
  new). More moving parts than Option A, less than Option B.

### Decision matrix (summary)

| Criterion | A: Sync + broker | B: Full async | C: Sync API + background worker |
|---|---|---|---|
| Migration cost | Low | High | Medium |
| Compat. w/ existing 10 handlers | Full | Breaking (all 10) | Full (9), contract change (1–2) |
| Fixes §2 enrich_ioc bug | No (not by itself) | Yes | Yes, if enrich_ioc is moved to it |
| Supports cancellation | No | Partial | Yes |
| Testing complexity | Low | High | Medium |
| Thread safety surface | Broker only | Whole app layer | Broker + worker pool |
| Rewrite risk | Low | High | Medium |

### Chosen architecture

**Option A now, with Option C's background-worker pattern explicitly reserved
for `enrich_ioc`'s blocking network span (§5), not adopted project-wide.**
`analyze_report` stays synchronous end-to-end (it already completes fast
enough in the reference implementation that no bug report or profiling data
in this checkpoint suggests otherwise — inventing an urgency for it would be
guessing). The broker is the only genuinely new piece of shared
infrastructure; it is designed thread-safe from the start because it is the
one place true concurrency (multiple SSE subscribers, one publishing
handler, all potentially on different threads once §5's worker is added) is
real and unavoidable, not because command execution in general needs to
become concurrent.

---

## 4. Why not Option B — explicit justification

Option B is rejected specifically because the actual problem (§2's
`enrich_ioc` bug, and the general "how do events leave a handler" question)
does not require it. `analyze_report`'s handler and 8 of the other 9 command
handlers have no blocking I/O beyond local SQLite access, which is already
fast and synchronous throughout the rest of the codebase (`InvestigationService`,
`SettingsService`, `ReportingService` — none are async). Converting all of
them to `async def` to fix one handler's one blocking call is the
"architectural rewrite" §13 of the task brief explicitly asks not to select
by default. Option C isolates the actual async need to the one place it
exists.

---

## 5. `enrich_ioc` analysis — CURRENT STATE + decision impact

Per §12's instruction, analyzed without modification:

- **Currently synchronous:** Yes, from the handler's perspective —
  `EnrichIocCommandHandler.handle()` is a plain `def`, calls
  `ThreatIntelService.lookup_indicator()` synchronously, and returns.
- **Performs network I/O:** Yes — `VirusTotalProvider.lookup_raw()` →
  `asyncio.to_thread(client.lookup_sha256/_ip/_domain/_url, ...)` →
  `requests.Session` HTTP call (`app/threat_intel/virustotal.py`).
- **Can block for a meaningful amount of time:** Yes — it is a live HTTP
  round trip to VirusTotal, subject to normal internet latency,
  `virustotal.py`'s own configured timeout, and provider rate limiting
  (`RateLimitExceededError` is a mapped exception in `errors.py`, meaning
  this is a known, not hypothetical, failure mode).
- **Needs progress events:** No — a single-indicator lookup is one
  request/response pair with no meaningful intermediate progress (unlike
  `analyze_report`'s multi-stage `progress_callback`). A progress event
  here would have nothing real to report between "started" and "done."
- **Needs started/completed/failed events:** Yes, and this is the concrete
  gap: `EnrichIocCommandHandler` currently emits **none** of the
  `ti.enrichment.*` events the frontend type union already names
  (`frontend/src/shared/events/types.ts`). This is a pre-existing
  half-finished contract, not a new requirement invented by this audit.
- **Needs cancellation:** Desirable but not currently possible for *any*
  command (§3, Option A) — not a new gap specific to `enrich_ioc`.
- **Should SSE stream its lifecycle:** Yes — `ti.enrichment.started` /
  `.completed` / `.failed`, mirroring `analysis.*`'s existing shape,
  sharing one `correlation_id` per lookup (using
  `new_correlation_id("ti")`, mirroring `new_correlation_id("an")`'s
  existing pattern in `events.py`).
- **Should its execution model change:** **Yes, but narrowly.** §2's bug
  means `enrich_ioc` cannot safely run inline inside `run_command`'s
  coroutine once the code actually runs against a live event loop
  (`fastapi`+`uvicorn` installed) — this is not an SSE-driven requirement,
  it is a pre-existing correctness requirement independent of this
  decision. The fix belongs at the `ThreatIntelService._lookup_raw` /
  transport boundary (replace the `asyncio.run()` bridge with either a
  proper `await` inside an async handler for this one command, or route
  the whole synchronous call through `asyncio.to_thread` at the
  `run_command` call site) — **out of scope to actually change in this
  Part** (§17 forbids modifying handlers), but named here as the one
  handler where Option A's "nothing changes" claim does not fully hold.
  The event-emission gap (no `ti.enrichment.*` events today) and the
  event-loop bug are two separate defects; SSE implementation should close
  the first, and closing the second is a prerequisite, not a consequence,
  of adding SSE.

---

## 6. Event broker design — APPROVED FUTURE ARCHITECTURE (not implemented)

### Event object

Extend, not replace, the existing `Event` dataclass (`events.py`). Additions
justified individually:

| Field | Exists today? | Add? | Why |
|---|---|---|---|
| `event`, `version`, `correlation_id`, `investigation_id`, `timestamp`, `payload` | Yes | Keep as-is | Already correct per §8/§9 of the existing architecture doc; no reason to change a working, tested schema. |
| `event_id` | No | **Add** | Needed for SSE's own `id:` field (§7) so a reconnecting client can resume via `Last-Event-ID` — the current schema has no way to reference "this specific event" (only "this command run," via `correlation_id`). `uuid4().hex` or a monotonically increasing broker-assigned sequence number — see Replay, below, for why a sequence number is preferred. |
| `command_name` | No | **Add** | Needed so a filtered/global stream (§7) can distinguish an `analysis.*` event from a `ti.enrichment.*` event without parsing the `event` string's prefix as an implicit contract. Small, cheap, removes a hidden coupling. |
| error info | Already carried in `payload` for `*.failed` events (e.g. `{"code": ..., "message": ...}` in `AnalyzeReportCommandHandler`) | Keep as-is | The existing convention already works and is exercised by tests; no new top-level field needed. |

No other fields are proposed — inventing a `severity` or `source` field
with no current handler that would populate it is exactly the kind of
unjustified addition §6 warns against.

### Publisher

Each command handler is the publisher for its own events, exactly as
`AnalyzeReportCommandHandler` already does — it does not change *who*
publishes, only *where* `.publish()` sends the event. Handlers keep
constructing `Event` objects via `Event.create(...)`, unchanged.

### Broker

A new, small, dedicated class — `EventBroker` — owns distribution. It does
**not** replace `EventCollector` (§9). It is the one new shared,
thread-safe object in the process: one broker instance, created once at
process startup (owned by `app/api/entrypoint.py`, the module that already
owns process-level concerns like the loopback bind — see
`PHASE4D_API_EVENT_ARCHITECTURE.md` §14), holding a set of subscriber
queues.

### Subscriber

A subscriber is a bounded queue (`queue.SimpleQueue` or `asyncio.Queue`
depending on which side of the FastAPI async boundary it's created on — see
§7) registered with the broker via `broker.subscribe() -> Subscription`.
`GET /events` creates one subscription per incoming SSE connection.

### Unsubscribe

`Subscription` is a context manager / has an explicit `.close()`; the SSE
route's `async for` loop over the subscription's queue is wrapped so that a
client disconnect (FastAPI/Starlette signals this via the request's
`is_disconnected()` or the generator being garbage-collected) triggers
`broker.unsubscribe(subscription)` in a `finally` block. No subscription
should be able to outlive its HTTP connection.

### Queue/backpressure

**Bounded queue per subscriber, not one shared unbounded queue.** If a
subscriber's queue is full when a new event is published, the broker drops
the *oldest* unread event for that subscriber (or the newest — see below)
and increments a per-subscriber dropped-event counter, rather than blocking
the publishing handler. A slow SSE client must never be able to make
`analyze_report` or `enrich_ioc` block or fail.

### Buffer size

Small and fixed (e.g. 32 events per subscriber) — justified because SOC-IQ
is a single-user local desktop app (already-decided trust/scale model,
§14 of the existing doc) with at most a handful of concurrent commands in
flight; a subscriber falling more than 32 events behind means the UI is
already stale in a way a bigger buffer wouldn't meaningfully fix. Drop
**oldest-first** (keep the most recent state) rather than newest-first,
since a UI showing "80% progress" is more useful than one stuck at "10%
progress" if some progress events must be discarded.

### Replay

**No replay in the first implementation, and this is a deliberate,
justified cut — not an oversight:** SOC-IQ's commands are short-lived
relative to typical SSE connection setup (a React client mounts, then
subscribes), and `analyze_report`/`enrich_ioc` responses already return
their terminal result synchronously in the HTTP response body (§8 below) —
SSE is a *supplementary* live-progress channel, not the only place the
result is observable. A subscriber that connects after a command has
already finished still gets the correct final state from the command's own
HTTP response; it only misses the *intermediate* progress events, which by
definition are stale/irrelevant once the command is done. Replay would only
matter if SSE became the sole source of truth for command results, which
§8 explicitly rejects. If a future requirement needs "attach a progress bar
to an already-running command," that is new scope, not something this
decision guesses a design for now (naming a fake `investigation_id` replay
API here would be exactly the invention §6 forbids).

### Ordering

Per-subscriber FIFO only. The broker does not guarantee a *global* total
order across all commands' events, only that each individual subscriber
sees events in the order they were published to the broker (a plain queue,
not a priority structure). This matches the existing per-collector
guarantee (§1) and is sufficient because the React client already keys UI
state off `correlation_id`, not off global event sequence.

### Thread safety

The broker's subscriber-set mutation (`subscribe`/`unsubscribe`) and each
subscriber's individual queue push (`publish`) must be safe under
concurrent access, since handler code and SSE connection setup/teardown can
happen from different threads/coroutines (especially once §5's background
worker exists for `enrich_ioc`). A `threading.Lock` around the subscriber
*set* mutation is sufficient — the queues themselves (`queue.SimpleQueue`,
or `asyncio.Queue` bridged via `loop.call_soon_threadsafe`) are already
safe for concurrent producer/single-consumer use, which is the actual
access pattern here (many handlers may publish; exactly one SSE route
reads any given subscriber's queue).

### Shutdown

On process shutdown (already-existing lifecycle in
`app/api/entrypoint.py`), the broker closes all subscriptions, causing
each open SSE connection's `async for` loop to exit cleanly and the
response to close — no dangling connections, no orphaned threads.

---

## 7. SSE contract design — APPROVED FUTURE ARCHITECTURE (not implemented)

`GET /events` (already a real, routed, `501`-returning endpoint in
`app/api/app.py`):

- **HTTP behavior:** `200 OK`, connection held open, `Content-Type:
  text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`
  (standard SSE headers; nothing SOC-IQ-specific here).
- **Media type / framing:** Standard SSE framing — `id: <event_id>\nevent:
  <event.event>\ndata: <json.dumps(event.to_dict())>\n\n` per event, one
  blank-line-terminated block per `Event`. This is exactly what
  `PHASE4D_API_EVENT_ARCHITECTURE.md` §13 already anticipated
  ("`json.dumps(asdict(event))`, no bidirectional need").
- **Event names:** The SSE `event:` field carries the existing `Event.event`
  string (`analysis.progress`, `ti.enrichment.failed`, etc.) unchanged —
  this lets `EventSource.addEventListener("analysis.progress", ...)` work
  directly on the client, matching the frontend's existing `EventName`
  union in `frontend/src/shared/events/types.ts`.
- **Event IDs:** The SSE `id:` field carries the new `event_id` (§6),
  enabling the browser's native `Last-Event-ID` reconnect header — even
  though the broker doesn't implement replay (§6), the field costs nothing
  to include and keeps the contract forward-compatible if replay is added
  later.
- **Payload format:** JSON, exactly `Event.to_dict()`'s existing shape —
  no new serialization scheme.
- **Heartbeat:** A periodic SSE comment line (`: heartbeat\n\n`) every N
  seconds (e.g. 15s) so intermediate proxies/the browser don't time out an
  idle connection during long gaps with no events — standard SSE practice,
  not SOC-IQ-specific.
- **Connection lifecycle:** Client opens once, receives events until it
  closes the tab/component unmounts, or the server shuts down (§6
  Shutdown). The browser's native `EventSource` auto-reconnects on drop —
  no custom reconnect logic needed server-side beyond honoring
  `Last-Event-ID` if/when replay is added.
- **Disconnect behavior:** See §6 Unsubscribe — broker removes the
  subscription; no event loss for *other* subscribers.
- **Error behavior:** A broker-internal error (should not happen in normal
  operation) closes that one subscriber's stream rather than crashing the
  process; it must never propagate back into a command handler's execution.
- **Authentication:** None — matches the already-decided, not-reopened
  trust model (§14 of the existing doc: loopback-only, no auth token).
- **Filtering / investigation scoping:** **Not in the first
  implementation.** SOC-IQ is single-user/single-window; every SSE
  subscriber is, in practice, the one open UI. A global, unfiltered stream
  is the smallest architecture that is actually useful — every event
  already carries `correlation_id` and `investigation_id`, so the *client*
  can filter cheaply without the server needing a query-parameter
  subscription-scope API. Adding server-side filtering later is additive
  (a query param the broker's `subscribe()` can optionally honor); it does
  not need to be designed now.

**Decision: global event stream, not a filtered one**, for exactly the
reason above — filtering would be solving a multi-client/multi-window
problem SOC-IQ does not currently have.

---

## 8. Command → event → SSE flow

```
analyze_report:
  POST /commands/analyze_report
      ↓
  dispatch("analyze_report", payload)
      ↓
  AnalyzeReportCommandHandler.handle()
      ↓ (unchanged: analysis.started / progress×N / completed|failed)
  Event.create(...) ──────────────► EventBroker.publish(event)
      ↓                                       ↓
  response, collector  (unchanged shape)   subscriber queue(s)
      ↓                                       ↓
  HTTP 200 response body                  GET /events SSE frame(s)
  (full InvestigationSummaryDTO,
   returned exactly as today)

enrich_ioc:
  POST /commands/enrich_ioc
      ↓
  dispatch("enrich_ioc", payload)
      ↓
  EnrichIocCommandHandler.handle()      [NEW: publish ti.enrichment.started
      ↓                                  before calling the service, and
  ThreatIntelService.lookup_indicator()  .completed/.failed after — see §5]
      ↓ (§5: needs its blocking-I/O fix,
      ↓  independent of SSE)
  Event.create("ti.enrichment.*", ...) ──► EventBroker.publish(event)
      ↓                                       ↓
  response  (unchanged shape:              subscriber queue(s)
   ok(lookup_indicator result))                ↓
      ↓                                   GET /events SSE frame(s)
  HTTP 200 response body
```

**The normal command HTTP response is never replaced by the event stream.**
Both `analyze_report` and `enrich_ioc` keep returning their full result
synchronously in the `POST /commands/{name}` response body, exactly as
today (`PHASE4D_API_EVENT_ARCHITECTURE.md` §7's existing "known
simplification" is explicitly *kept*, not resolved into the fire-and-forget
model the original contract doc proposed) — SSE is purely an additive,
best-effort progress channel. This is a deliberate decision, not a default:
switching to fire-and-acknowledge (§3, Option C) would be a bigger, riskier
change to the response contract than this phase's evidence justifies, since
nothing in the checkpoint shows `analyze_report` actually taking long enough
in practice to need it.

---

## 9. Disposition of the existing `EventCollector`

**Decision: Option A — retain `EventCollector` as a test helper, unchanged.**

- It is not promoted into the broker. Its entire design point (§1) — a
  disposable, single-owner, per-call-frame list — is the opposite of what
  the broker needs (long-lived, multi-subscriber, thread-safe). Repurposing
  it would mean either bolting broker concerns onto a class
  `tests/test_application_layer.py` already depends on for a different
  purpose, or quietly changing its semantics under that test suite's feet.
- `AnalyzeReportCommandHandler.handle()` keeps building and returning its
  `EventCollector` exactly as today, so the existing 67 passing tests keep
  working unmodified. The *only* addition (when actually implemented, not
  in this Part) is one extra `broker.publish(event)` call alongside each
  existing `collector.publish(event)` call — both sinks receive the same
  `Event` object.
- `EventCollector` remains the thing unit tests assert exact event sequences
  against, in isolation, without needing a running broker or HTTP server —
  preserving exactly the "prove the schema is correct in isolation, before
  Rust or React exist" value `PHASE4D_API_EVENT_ARCHITECTURE.md` §8 already
  named.

---

## 10. FastAPI boundary — APPROVED FUTURE ARCHITECTURE (not implemented)

Audited `app/api/app.py` (109 lines, read in full — see §"Checkpoint
verification" below).

- **The API layer owns the broker's lifecycle** (creates it at startup,
  closes it at shutdown — via `app/api/entrypoint.py`, which already owns
  the process's other lifecycle concerns), but **does not own event
  semantics.** It depends on an event-subscription *interface*
  (`broker.subscribe() -> Subscription`, `subscription.__aiter__` or
  similar), not on any handler's internals.
- **Per-request subscriptions:** Yes — `GET /events` calls
  `broker.subscribe()` once per incoming connection and iterates it,
  translating each `Event` into an SSE frame (§7's framing). This
  translation step (`Event` → SSE text) lives in `app/api/app.py`, not in
  `app/application/events.py` — SSE is a transport concern.
- **The application layer must not depend on FastAPI — maintained.** The
  broker class itself (§6) is proposed to live in `app/application/` (e.g.
  `app/application/broker.py`, alongside `events.py`) using only the
  standard library (`queue`/`threading` or `asyncio`), with zero import of
  `fastapi`/`starlette`. `app/api/app.py` imports *from* `app.application`,
  never the reverse — identical to the existing rule already enforced for
  `COMMAND_HANDLERS`/`dispatch` (`PHASE4D_API_EVENT_ARCHITECTURE.md` §5.1,
  confirmed unbroken by every existing handler and by `app.py`'s own
  imports, all of which point from `app.api` into `app.application`, never
  back).

---

## 11. Frontend boundary — inspected, not implemented

`frontend/src/shared/events/useEventStream.ts` (33 lines) and `types.ts`
(31 lines) read in full.

- The hook is already a deliberate, documented no-op ("This hook fixes the
  SHAPE that feature code will eventually subscribe through, without
  opening a real `EventSource`") — exactly matching this document's
  "design, don't implement" scope.
- `EventName` already lists `ti.enrichment.started/completed/failed`
  alongside the four `analysis.*` names — meaning the frontend scaffold
  already anticipated `enrich_ioc` emitting events, ahead of the backend
  actually doing so (§5's gap).
- **Browser `EventSource` API is sufficient** — SOC-IQ needs a
  one-directional, text/JSON, auto-reconnecting stream, which is exactly
  what `EventSource` provides natively; no need for a custom
  fetch-based SSE client or WebSocket fallback (consistent with
  `PHASE4D_API_EVENT_ARCHITECTURE.md` §13's already-decided SSE-not-WebSocket
  choice).
- **Filtering:** Not needed client-side beyond what `EventName`-scoped
  `addEventListener` already gives "for free," per §7's global-stream
  decision.
- **Reconnect:** Handled automatically by `EventSource`; no custom logic
  needed for the first implementation, since replay isn't offered (§6) —
  a reconnect simply starts receiving new events again, which is
  acceptable for the reasons given in §6 Replay.
- **`event_id`/resume support:** Included in the schema (§6, §7) for
  forward compatibility even though nothing consumes `Last-Event-ID` yet —
  cheap to add now, expensive to retrofit onto every already-deployed
  event later.

No frontend code was added or modified.

---

## 12. Tauri boundary — compatibility check only, not modified

- The proposed architecture is fully transport-neutral at the application
  layer (§10) — the broker and `Event` schema have no knowledge of HTTP,
  SSE framing, or any particular frontend. `React → Tauri → Python
  sidecar/API` continues to mean "Tauri shells the same FastAPI process
  and React talks to it over loopback HTTP/SSE exactly as a browser
  would" — nothing in this decision assumes or requires Tauri-specific IPC.
- **No Qt dependency introduced.** Nothing in §6/§7/§10 touches or imports
  `app.gui` — verified: the proposed `app/application/broker.py` depends
  only on the standard library and `app/application/events.py`.
- **No conflict identified** between this event architecture and the
  existing Rust/Tauri scaffold (out of scope to inspect further per the
  task's explicit Rust/Tauri exclusion) — the contract Tauri needs to
  honor is unchanged from what `PHASE4D_API_EVENT_ARCHITECTURE.md` §14
  already established (loopback bind, OS-process trust boundary).

---

## 13. Adversarial architecture audit

| Attack | Finding | Mitigated by |
|---|---|---|
| Race condition on subscriber set | Real, if unmitigated | §6 Thread safety: lock around subscribe/unsubscribe mutation |
| Deadlock | Not present in the proposed design — no lock is held across a `publish()` call into a subscriber queue *and* a wait on that same queue; publish is fire-into-queue, never a blocking put against an unbounded consumer | Bounded queue with drop-oldest (§6) avoids `queue.Queue.put()` blocking the publisher at all |
| Event loss | Deliberate and bounded, not accidental — see §6 Buffer size / backpressure policy; explicitly documented, not hidden | Drop-oldest policy + per-subscriber dropped-event counter |
| Subscriber leaks | Real risk if a client disconnects without the server noticing | §6 Unsubscribe: `finally`-block cleanup keyed to the SSE route's own connection lifetime, not to an explicit client-sent "goodbye" |
| Unbounded memory | Would occur with an unbounded per-subscriber queue or a broker that never prunes closed subscriptions | Bounded queue (§6) + shutdown/unsubscribe cleanup (§6, §10) |
| Blocking SSE connections | An SSE route that never yields would starve the ASGI event loop | Route implemented as an `async for` over the subscription with `await`s at each yield point — standard FastAPI `StreamingResponse` pattern, not a busy-loop |
| Command starvation | Could occur if command execution and SSE delivery shared a single thread/lock | They don't — commands run on the request path exactly as today (§3 Option A); the broker's lock is held only for the brief subscriber-set mutation, never across a full command execution |
| Duplicate events | Could occur if a handler's retry logic re-published the same `Event` | No handler currently retries (confirmed: no retry logic anywhere in `handlers.py`); not a new risk introduced by this design, and `event_id` (§6) gives a future dedup key if one is ever needed |
| Duplicate subscribers | A client opening two tabs would create two legitimate subscriptions — this is correct behavior (§6 Multiple consumers), not a bug | N/A — each is a distinct subscription with its own bounded queue |
| Ordering problems | Cross-subscriber global ordering is explicitly *not* guaranteed (§6 Ordering) — flagged as a real, accepted limitation, not silently ignored | Per-subscriber FIFO is sufficient for the client-side `correlation_id`-keyed consumption model (§11) |
| Shutdown races | A command mid-execution when the process is asked to shut down could try to `publish()` to an already-closed broker | Broker's `publish()` must be a no-op (not an exception) after shutdown begins — named here as a required behavior, not yet implemented |
| Stale subscribers | A subscription whose SSE connection died without a clean close (network drop) | Same mitigation as Subscriber leaks — connection-lifetime-scoped cleanup, not a client heartbeat/ack protocol (would be over-engineering for a loopback single-user app) |
| Cancellation problems | Named as an accepted limitation in §3 — no command can currently be cancelled once started, broker or not. Not solved by this design; explicitly not claimed to be solved |
| Exception swallowing | A broker `publish()` that silently ate an exception on a full/closed queue would hide bugs | Must count/log dropped events per §6, not swallow silently — logging, not just dropping |
| Transport leakage | SSE framing logic in `app/application/` would leak transport concerns into the application layer | §10: framing translation stays in `app/api/app.py`; broker only handles `Event` objects |
| FastAPI leakage into application | A broker importing `fastapi`/`starlette` types | §10: broker uses only stdlib types; verified no such import is proposed |
| Qt leakage | A broker or event type importing `app.gui` | §12: confirmed no such dependency proposed |
| Tauri leakage | Broker/event design assuming a Tauri-specific transport | §12: none — transport-neutral, HTTP/SSE only |
| Unnecessary async conversion | Converting all 10 handlers to `async def` (Option B) to fix one handler's issue | Rejected explicitly in §4 |
| Unnecessary architectural rewrite | Replacing `EventCollector` wholesale, or moving to fire-and-acknowledge responses project-wide | Rejected in §9 and §8 respectively, each with a stated reason |

**Result: no unmitigated finding.** Every row above either names an existing
mitigation already built into the proposed design (§6/§10) or explicitly
names an accepted, documented limitation (cancellation; cross-subscriber
ordering) rather than a silent gap. This is **not** a PASS on tested code —
none of this is implemented yet (§17) — it is a PASS on the *design*
surviving the listed attack classes on paper.

---

## 14. Migration impact

| File | Required change | Reason | Risk |
|---|---|---|---|
| `app/application/events.py` | Add `event_id`, `command_name` fields to `Event`; add `EventBroker`, `Subscription` classes | §6 event object + broker | Low — additive to a frozen dataclass (new fields), new classes alongside existing ones |
| `app/application/handlers.py` | `AnalyzeReportCommandHandler.handle()`: add `broker.publish(event)` calls alongside existing `collector.publish(event)` calls. `EnrichIocCommandHandler.handle()`: add `ti.enrichment.started/completed/failed` event construction + publish (new for this handler) | §8, §9 flow; §5 gap | Medium — touches two existing, tested handlers; must not change their return shape |
| `app/application/service` layer for `enrich_ioc`'s blocking call (`app/threat_intel/service.py::_lookup_raw`) | Replace the `asyncio.run()` bridge with a call shape safe inside a running event loop (e.g. `await` from an async handler, or `asyncio.to_thread` at the call site) | §2, §5 — pre-existing bug, prerequisite for enrich_ioc SSE | Medium — the one genuine behavior change outside pure addition |
| `app/api/app.py` | Implement `GET /events` for real: `StreamingResponse` over a new `broker.subscribe()` subscription, replacing the current `501` handler | §7, §10 | Medium — replaces a currently-working (if minimal) endpoint; must preserve the `501` behavior only for the "broker not yet started" edge case, if any |
| `app/api/entrypoint.py` | Create the one process-lifetime `EventBroker` instance; wire startup/shutdown hooks (§6 Shutdown) | §6, §10 | Low — additive to existing process lifecycle management |
| `tests/test_application_layer.py` | New tests: broker publish/subscribe, backpressure/drop policy, `enrich_ioc` event emission | §16 freeze criteria | Low — additive test file changes only |
| `tests/test_api_layer.py` | New tests: `GET /events` framing, multi-subscriber, disconnect cleanup (via `TestClient`/`httpx` streaming) | §16 freeze criteria | Medium — needs `fastapi`/`httpx` actually installed to run (currently blocked per §19 of the existing doc) |
| `docs/contracts/event-model.md` | Update to document `event_id`/`command_name` fields and the broker's delivery semantics (no replay, bounded queue, drop-oldest) | Keep contract docs truthful | Low — doc-only |
| `frontend/src/shared/events/useEventStream.ts` | Replace no-op body with a real `EventSource` subscription once `GET /events` is live | §11 | Low, but out of scope for whoever implements the backend half — separate PR |

No file outside this table is expected to require a change for SSE
specifically.

---

## 15. Implementation plan (staged)

**Stage 1 — Event domain contract**
Files: `app/application/events.py`. Add `event_id`, `command_name` to
`Event`; no behavior change to `EventCollector`.
Dependencies: none.
Verification: existing `tests/test_application_layer.py` event-sequence
assertions still pass unmodified (new fields are additive).
Exit criteria: `Event.to_dict()` includes the new fields; no existing test
broken.

**Stage 2 — Broker**
Files: `app/application/events.py` (or a new `app/application/broker.py`).
Add `EventBroker`, `Subscription`, bounded-queue backpressure policy.
Dependencies: Stage 1.
Verification: new unit tests — publish/subscribe, multiple subscribers,
drop-oldest under a full queue, unsubscribe stops delivery.
Exit criteria: broker is thread-safety-tested (concurrent publish from
multiple threads, asserted no lost subscriber-set mutation) and has zero
`fastapi`/`app.gui` imports (grep-verified, per §10/§12).

**Stage 3 — Handler integration**
Files: `app/application/handlers.py`, `app/threat_intel/service.py`
(the `_lookup_raw` fix from §5/§14).
Dependencies: Stage 2.
Verification: `AnalyzeReportCommandHandler`'s existing tests still pass
unmodified (broker publish is additive); new tests confirm `enrich_ioc`
now emits `ti.enrichment.*` events and that `_lookup_raw` no longer raises
when called from a running event loop (regression test for §2's bug).
Exit criteria: both handlers publish to the broker; §2's bug is closed and
has a regression test.

**Stage 4 — SSE transport**
Files: `app/api/app.py`, `app/api/entrypoint.py`.
Dependencies: Stage 2 (broker must exist), Stage 3 (events must be worth
streaming).
Verification: manual/`httpx`-streaming test against a running `uvicorn`
instance (environment-permitting, per §19's existing constraint) — SSE
framing matches §7, `id:`/`event:`/`data:` fields all present and correct.
Exit criteria: `GET /events` returns `200`, not `501`; a real event
published by a command shows up as a correctly-framed SSE message.

**Stage 5 — Tests**
Files: `tests/test_application_layer.py`, `tests/test_api_layer.py`.
Dependencies: Stages 2–4.
Verification: full suite run.
Exit criteria: broker tests, handler-integration tests, and SSE-framing
tests all present and passing; existing 67 tests still pass unmodified.

**Stage 6 — Frontend integration**
Files: `frontend/src/shared/events/useEventStream.ts`.
Dependencies: Stage 4 (a real endpoint must exist to subscribe to).
Verification: manual check against a running sidecar + dev frontend.
Exit criteria: hook opens a real `EventSource`, dispatches to registered
handlers by `EventName`, matches `types.ts`'s existing shape unchanged.

**Stage 7 — Adversarial audit (re-run against real code)**
Files: none (verification-only).
Dependencies: Stages 1–6 complete.
Verification: re-walk every row of §13's table against the *actual*
implementation, not the design — confirm each mitigation is really
present in code, not just in this document.
Exit criteria: no finding regresses from "mitigated" to "unmitigated."

**Stage 8 — Freeze**
Files: `docs/phase4/` (freeze doc, following the existing
`PHASE4C_FREEZE.md` precedent).
Dependencies: Stage 7 passes.
Verification: full regression suite; checkpoint archive.
Exit criteria: §16 below, all satisfied.

---

## 16. Phase 4D freeze criteria

Phase 4D SSE may be frozen only when **all** of the following are true —
each tied to a specific piece of this architecture, not a vague "SSE
works":

1. `EventBroker` has passing unit tests for: publish/subscribe,
   multiple simultaneous subscribers receiving the same event,
   unsubscribe-stops-delivery, and drop-oldest backpressure under a full
   queue (§6, §13).
2. `AnalyzeReportCommandHandler`'s existing event-sequence tests
   (`started → progress×N → completed|failed`, one shared
   `correlation_id`) still pass unmodified, proving Stage 3 was additive
   (§9, §15 Stage 3).
3. `EnrichIocCommandHandler` has a passing test asserting it emits
   `ti.enrichment.started` and exactly one of
   `ti.enrichment.completed`/`ti.enrichment.failed` (§5, §15 Stage 3).
4. A regression test exists proving `ThreatIntelService._lookup_raw` (or
   its replacement) no longer raises `RuntimeError` when invoked from
   inside a running asyncio event loop (§2, §5, §15 Stage 3) — the actual
   bug found in this audit, closed and pinned.
5. `GET /events` returns real SSE frames (`200`, correct
   `Content-Type: text/event-stream`, correct `id:`/`event:`/`data:`
   framing per §7) against at least one published event, tested against a
   running server, not asserted from reading code alone (§15 Stage 4/5).
6. A multi-subscriber test proves two independent `GET /events`
   connections both receive the same published event (§6 Multiple
   consumers, §13).
7. A disconnect test proves that closing one SSE connection does not
   affect delivery to other open subscriptions, and that the broker's
   subscriber set no longer contains the closed one afterward (§6
   Unsubscribe, §13 Subscriber leaks).
8. `grep` confirms zero imports of `fastapi`/`starlette` in
   `app/application/*` and zero imports of `app.gui` in
   `app/application/*` or the new broker/SSE code (§10, §12, §13) —
   the two dependency-direction rules this document commits to.
9. No duplicate event-transport mechanism exists — `EventCollector`
   remains test-only (§9); the broker is the sole production event path.
10. Full existing regression suite passes (`tests/test_application_layer.py`
    at minimum, plus `tests/test_api_layer.py` once runnable in an
    environment with `fastapi`/`httpx` installed — carrying forward the
    known environment gap already flagged in
    `PHASE4D_API_EVENT_ARCHITECTURE.md` §19, not silently dropped here).
11. `docs/contracts/event-model.md` is updated to match the fields and
    delivery semantics actually implemented (§14).
12. A clean checkpoint archive is produced containing the above, matching
    the naming convention `docs/phase4/PHASE4_CHECKPOINT_NAMING.md` already
    establishes.

---

## 17. Explicit statement of what is NOT implemented in this Part

This Part implemented **nothing**. No source file under `app/`, `frontend/`,
or `tests/` was modified. Specifically **not** done, per the task's own
prohibition list:

- SSE was not implemented.
- No `EventBroker` (or any event broker) was created.
- No handler (`AnalyzeReportCommandHandler`, `EnrichIocCommandHandler`, or
  any other) was modified.
- `dispatch()` was not modified.
- No FastAPI route was modified — `GET /events` still returns `501`.
- No React file was modified.
- No Rust/Tauri file was inspected or modified.
- No test file was modified.
- `EventCollector` was not refactored.
- `ThreatIntelService._lookup_raw`'s §2/§5 bug was **identified and
  analyzed**, not fixed.

The only repository change from this Part is this document.

---

## Checkpoint verification (performed before analysis)

- Directly inspected `app/application/{events,handlers,responses,errors,dto}.py`,
  `app/api/app.py`, `app/threat_intel/{service,virustotal_provider,virustotal}.py`,
  `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md` (all 450 lines), and
  `frontend/src/shared/events/{types,useEventStream}.ts` in full.
- Confirmed: `COMMAND_HANDLERS` has exactly 10 entries (mechanically
  counted, not eyeballed).
- Confirmed: `GET /events` returns the documented `501`/`NOT_IMPLEMENTED`
  envelope, unchanged.
- Confirmed: `EventCollector` is exactly the ephemeral, per-call-frame
  object described in §1 — no broker, publish/subscribe, or persistence
  code exists anywhere in the repository (`grep -rn` for
  `StreamingResponse|EventSourceResponse|Queue|Signal|subscribe|publish`
  across `app/` returned no matches outside `app/gui/events/*` — a
  Qt-signal-based, GUI-only mechanism, unrelated to this API/SSE work and
  correctly out of this audit's scope).
- Ran `python -m unittest tests.test_application_layer -v`:
  **67 tests, all passing (`OK`)** — checkpoint matches the expected state
  exactly. No discrepancy found; nothing to stop and report.
- New finding this Part, not in the original checkpoint description: §2's
  `enrich_ioc`/`asyncio.run()` event-loop hazard, confirmed by reading
  `app/threat_intel/service.py` lines 201–223 and
  `app/api/app.py`'s `run_command` (an `async def` calling `dispatch()`
  directly, no thread offload).
