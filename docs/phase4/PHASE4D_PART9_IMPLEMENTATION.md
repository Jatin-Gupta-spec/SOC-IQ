# SOC-IQ — Phase 4D Part 9 — `GET /events` SSE readiness audit

**Status: SSE ARCHITECTURE NOT READY (CLASS C).**
No SSE implementation was added this Part. `GET /events` remains an
honest `501 NOT_IMPLEMENTED`, unchanged. This is **not** a Phase 4D
freeze.

## 1. Checkpoint verification

The Part 8 reconciled checkpoint (`SOC-IQ-Phase4D-Part8-RECONCILED.zip`)
was extracted fresh into a clean directory before any inspection:

| Item | Result |
|---|---|
| All 10 `COMMAND_HANDLERS` entries | Present — confirmed by direct read of the dict literal in `app/application/handlers.py` |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| `docs/phase4/PHASE4D_PART2` through `PART8_IMPLEMENTATION.md` | Present |
| Part 8 reconciliation addendum (§0 of `PART8_IMPLEMENTATION.md`) | Present |
| `app/application/events.py` | Present |
| `app/api/app.py` | Present |
| `GET /events` | Present, returns `501` / `NOT_IMPLEMENTED` |
| Existing event-related tests | Present (`tests/test_application_layer.py`, `tests/test_api_layer.py`) |

No discrepancy from the expected Part 8 checkpoint — this run's own
`SOC-IQ-Phase4D-Part8-RECONCILED.zip` was used as the source, so the
match is exact by construction.

## 2. Tests actually executed

```
python -m unittest tests.test_application_layer -v
```
→ **67/67 passed**, reproduced fresh.

```
python -m unittest discover -s tests -p "test_*.py"
```
→ 94 discovered, **67 passed**, 27 errors — each individually confirmed
to be a `ModuleNotFoundError` for `pytest`, `fastapi`, or `PySide6` at
import time (`tests/test_api_layer.py`, `tests/test_threat_intel*.py`,
`tests/test_virustotal*.py`, `tests/gui/*`, and a handful of others that
import one of those three at module scope), not an assertion failure.

`pytest`, `fastapi`, `PySide6` confirmed absent (`ModuleNotFoundError`
on direct `import`), no network access. `pytest tests/ -q` and
`QT_QPA_PLATFORM=offscreen pytest tests/ -q` could not be attempted —
`pytest` itself is not installed. This matches every prior Part's
declared environment.

## 3. Event architecture audit (source-read, not doc-trusted)

### `app/application/events.py`

67 lines. Defines `Event` (frozen dataclass: `event`, `version`,
`correlation_id`, `investigation_id`, `timestamp`, `payload`) and
`EventCollector`. `EventCollector`'s own docstring states plainly:
*"In-process stand-in for the eventual SSE publisher (S8/S22)."* Its
module docstring is equally explicit: *"This is a schema + in-process
collector, not a live transport... no SSE consumer exists yet."*

`EventCollector.publish()` appends to a plain Python `list` on the
instance. There is no subscribe/unsubscribe method, no queue, no
broadcast, no shared/module-level instance — every `EventCollector` is
constructed fresh, per call, inside a handler's `handle()` method.

### Who actually emits events

Grepped `app/application/handlers.py` for every `EventCollector`/
`.publish(`/`Event.create` call site: **only
`AnalyzeReportCommandHandler`** constructs an `EventCollector` and
publishes to it (`analysis.started` / `analysis.progress` × N /
`analysis.completed` or `analysis.failed`, all sharing one
`correlation_id` from `new_correlation_id("an")`). No other command
handler — including `enrich_ioc`, added in Part 7 as the other
plausibly-long-running command — touches `EventCollector` at all;
`enrich_ioc` is fully synchronous with no event emission whatsoever.
So the entire current event vocabulary is four `analysis.*` events
tied to one command; there is no `investigation.created`,
`investigation.deleted`, `command.started`, or any other event type
anywhere in `app/application/`.

### What happens to the events after they're published

`AnalyzeReportCommandHandler.handle()` returns
`tuple[dict[str, Any], EventCollector]` — the response envelope and the
collector, together. But `dispatch()`'s `analyze_report` branch
(`app/application/handlers.py`) discards the collector immediately:

```python
if name == "analyze_report":
    request = AnalyzeReportRequest(**payload)
    response, _collector = AnalyzeReportCommandHandler().handle(request)
    return response
```

The underscore-prefixed `_collector` is never read again in `dispatch()`
or by `COMMAND_HANDLERS["analyze_report"]`, and `POST /commands/analyze_report`
in `app/api/app.py` calls `handler(payload)` and returns exactly that
same envelope — the events collected during that call are not present
in the HTTP response body and are not published anywhere else. Only
`tests/test_application_layer.py` (calling `AnalyzeReportCommandHandler().handle()`
directly, bypassing `dispatch()`) ever reads the collector's contents,
via `test_analyzes_real_sample_report_and_emits_correct_event_sequence`
and `test_domain_failure_is_translated_and_emits_failed_event`. This
confirms the module docstring's claim precisely: the mechanism exists
"purely so tests can assert on the exact event sequence a command
handler produces," not to feed any live consumer.

### `app/api/app.py` — `GET /events`

Docstring states outright: *"Not implemented this phase: there is no
live command execution to stream from (`AnalyzeReportCommandHandler`
currently runs synchronously and returns its events inline...). Wiring
this to a real `StreamingResponse` over `app.application.events.EventCollector`
is listed as remaining work, not guessed at here."* The route returns a
translated `501`/`NOT_IMPLEMENTED` envelope (added in Part 2 specifically
to stop a bare `NotImplementedError` from leaking as an unhandled 500),
covered by `EventsRouteTests.test_events_stream_returns_translated_not_implemented_error`
in `tests/test_api_layer.py`.

### `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md` — the architecture record

- **§8** (event model): *"schema implemented, no live transport this
  phase... Events are collected into a list and returned alongside the
  response in this phase's reference implementation (no SSE consumer
  exists yet to stream them to)."*
- **§13** (SSE vs WebSocket): the transport choice itself (SSE,
  one-directional) is settled — this is not the open question.
- **§21, "NEW this phase" (never resolved in any later Part):**
  *"whether `analyze_report`'s response should stay synchronous... or
  be made genuinely async once a real SSE consumer exists — the
  contract doc says async: fire-and-acknowledge; this phase's
  reference handler is sync-and-return because there was nothing to
  stream to yet. This needs a decision, not another simplification,
  before `enrich_ioc` or any other long-running command is added."*
  Checked directly: `enrich_ioc` (Part 7) did **not** resolve this —
  it shipped fully synchronous, with no event emission and no async
  handling, sidestepping the question rather than answering it.
- **§22** (remaining work, this phase): explicitly lists *"the `GET
  /events` SSE endpoint against a real running server"* as out of
  scope, alongside several now-completed commands.

No document anywhere in `docs/phase4/` or `docs/contracts/` supersedes
§21's open question or provides a decision on sync-vs-async command
execution once a live stream exists.

### GUI-side event buses (checked, and out of reach)

`app/gui/events/event_bus.py` and `app/gui/events/application_events.py`
do implement live, subscriber-based event buses — but both are built on
`PySide6.QtCore.QObject`/`Signal` (confirmed by direct import at the top
of `event_bus.py`). Per this brief's own boundary rule (§6) and every
prior Part's already-established invariant ("`app.application` never
imports `app.gui`" — see `SearchInvestigationsCommandHandler`'s and
`GetThreatIntelligenceCommandHandler`'s docstrings), these are not
reachable from `app/application/` without either a first-ever
`app.gui` import into that layer or a Qt import into `app/application/`
— both forbidden outright by §6. They are not a substitute event
source for SSE and were not used as one.

## 4. Answering the readiness questions directly

- **Event source** — no provider-neutral, live, application-level
  publisher exists. The only "source" is a per-call, single-command,
  immediately-discarded local list.
- **Event vocabulary** — four events (`analysis.started/progress/completed/failed`),
  scoped to exactly one command. No investigation-lifecycle events, no
  generic command-lifecycle events, no vocabulary for any of the other
  9 commands.
- **Transport contract** — SSE-vs-WebSocket is decided (§13); *what*
  `/events` streams (all application events? one investigation's
  events? command-scoped events?) is not specified anywhere, because
  there is currently only one producer and no consumer contract was
  ever written for it beyond "will be an SSE stream eventually."
- **Connection lifecycle** — heartbeat, disconnect handling,
  subscriber cleanup, backpressure, replay/history, ordering across
  multiple producers, multiple simultaneous clients: none of these are
  specified anywhere in `docs/phase4/` or `docs/contracts/`. §21
  explicitly frames the prerequisite sync/async decision as still
  open, which blocks all of the above from being decidable — you
  cannot design connection lifecycle for a stream whose producer model
  (sync-and-return vs. async-and-publish) hasn't been chosen yet.
- **Serialization** — §8 sketches `data: json.dumps(asdict(event))`
  informally, but this was never implemented or tested, and no `event:`
  field convention was decided.

## 5. Classification

**CLASS C — SSE requires new event infrastructure or architectural
design.**

This is not a small, conservative gap-fill (which would be CLASS B).
The blocking question — whether command execution becomes
async/fire-and-publish, or stays sync-and-return with some other
streaming mechanism layered on top — was explicitly flagged as a
required decision in Part 2 (§21) and has been left unresolved through
Parts 3–8, including through `enrich_ioc` (Part 7), which was the
architecture doc's own named test case for whether this decision could
be deferred further ("before `enrich_ioc` or any other long-running
command is added"). Answering it now, unilaterally, in a Part whose
brief explicitly forbids inventing an event system or redesigning
`ApplicationEvents` "merely to make SSE convenient" (§7 of this Part's
brief), would mean either:

1. Redesigning `AnalyzeReportCommandHandler` (and by extension the
   command-dispatch contract every handler shares) to be async and
   publish to a real, shared, subscribable bus — a genuine
   architectural redesign, not an extraction; or
2. Inventing a synthetic/fake event source under `app/api/` to make
   `/events` stream *something* — explicitly forbidden ("DO NOT create
   a fake SSE endpoint").

Neither is available under this Part's own rules. Per §5 of this Part's
brief: **STOP and report the missing prerequisite** rather than
implement.

## 6. Implementation

**None.** No source files were changed. `GET /events` is untouched and
still returns the same translated `501`/`NOT_IMPLEMENTED` envelope it
returned at the start of this Part, still covered by the same passing
`EventsRouteTests.test_events_stream_returns_translated_not_implemented_error`
test (environment-blocked from execution this Part along with the rest
of `test_api_layer.py`, but unchanged in source and logically
unaffected by anything read this Part).

## 7. Adversarial audit

| Check | Result |
|---|---|
| FastAPI imports under `app/application/` | None (unchanged from Part 8) |
| SSE code under `app/application/` | None |
| Duplicate event buses introduced | None — the pre-existing GUI Qt buses were read, not touched or duplicated |
| Duplicate event publishers | None |
| Leaked Qt signals into `app/application/` | None |
| Leaked Tauri events | None |
| Business logic added to `app/api/` | None — no code added there either |
| Command regressions | None — no command handler touched |
| Source changes of any kind | None — audit-only Part |

**PASS** (vacuously — nothing was implemented to introduce these
defects).

## 8. Prerequisite for a future Part

Before SSE can be implemented, §21's open question needs an actual
decision (not made here, since this Part's brief scopes decisions to
"smallest architecture-consistent interpretation... does not change
existing semantics" — this one does change semantics): does
`analyze_report` (and any future long-running command) move to an
async, publish-to-a-shared-bus execution model, or does `/events` get
served some other way (e.g. polling-based progress via a new query
command, or a bounded in-memory ring buffer keyed by
`correlation_id` that a short-lived SSE connection tails) that doesn't
require making commands themselves async? Both are legitimate answers;
neither has been chosen. That choice belongs to whoever owns Phase 4D's
architecture, not to an unattended audit Part.

## 9. Remaining Phase 4D work

- The sync/async command-execution decision (§8 above) — new,
  surfaced explicitly by this audit as the actual blocker, not merely
  restated from Part 2.
- `GET /events` SSE implementation itself, contingent on the above.
- Everything else already listed as complete in Part 8's reconciliation
  (§10 of `PHASE4D_PART8_IMPLEMENTATION.md`) is unchanged.

## 10. Freeze status

**PHASE 4D NOT FROZEN.** No freeze is claimed or implied by this Part.
This audit found a real, unresolved architectural prerequisite — that
is grounds for continued non-freeze, not for either forcing an
implementation or declaring the phase stuck.

## 11. Final status

**SSE ARCHITECTURE NOT READY.**
