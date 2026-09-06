# PHASE 4D SSE — PART 1 IMPLEMENTATION: CORE EVENT BROKER

**Status: PART 1 OF THE SSE IMPLEMENTATION ONLY. Phase 4D is NOT frozen.**

This implements the core, transport-neutral event infrastructure decided in
`docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md` (final; not reopened
here). It does **not** implement SSE itself, does not touch `GET /events`,
and does not wire the broker into any command handler's production path.

---

## 1. Checkpoint verification

Performed before any edit, against the uploaded
`SOC-IQ-Phase4D-SSE-ARCHITECTURE-DECISION.zip` state (this session's working
directory already held that exact checkpoint — verified, not assumed, by
diffing against a fresh extraction of the zip after this Part's work was
done; see §9):

| Check | Result |
|---|---|
| `COMMAND_HANDLERS` entry count | 10 (mechanically counted) |
| `GET /events` | Returns `501`/`NOT_IMPLEMENTED`, unchanged |
| `EventCollector` | The existing ephemeral, per-call-frame test helper — unchanged shape |
| `EventBroker` | Did not exist anywhere in the repository (`grep -rn "class EventBroker"` returned nothing) |
| `python -m unittest tests.test_application_layer -v` | 67 tests, all passing |
| `docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md` present | Yes |

No discrepancy found. Proceeded with implementation as scoped.

---

## 2. Architecture implemented

Exactly the "smallest correct architecture" `PHASE4D_SSE_ARCHITECTURE_
DECISION.md` §6 resolved on, scoped to its Part-1-relevant pieces only:

```
synchronous command handlers   (unchanged — no handler modified this Part)
         ↓
    EventBroker                (NEW — app/application/broker.py)
         ↓
   SSE transport                (NOT implemented this Part)
         ↓
   frontend EventSource         (NOT implemented this Part)
```

The sync/async decision was not reopened. No handler was converted to
`async`. `EventCollector` was not replaced.

---

## 3. Event contract status

**One additive change, no redesign**, per the Part 1 task's Stage 1
instruction to preserve the existing `Event` shape wherever possible:

- Added `event_id: str = field(default_factory=_new_event_id)` to the
  `Event` frozen dataclass (`app/application/events.py`), appended after
  all existing fields so no caller relying on positional construction (none
  exists in production code or tests — confirmed by grep, §7) breaks.
- `_new_event_id()` generates a `uuid4().hex` string at `Event.create()`
  time — the same pattern `new_correlation_id()` already uses, not a
  broker-assigned sequence number. `PHASE4D_SSE_ARCHITECTURE_DECISION.md`
  §6 named a sequence number as an option specifically for *replay*
  support; that same document's §6 also decided against implementing
  replay in this phase, so a decoupled, handler-side id is the smaller
  choice that still satisfies what an id is actually needed for right now
  (a stable per-event identity for a future SSE `id:` field) — documented
  in `_new_event_id()`'s own docstring, not just here.
- **`command_name`**, which the architecture decision's §6 table also
  listed as a candidate field, was **deliberately not added** in this Part:
  its only justified use (§7 of that document) was for a *filtered* SSE
  stream, and §7 explicitly chose a global, unfiltered stream for the first
  implementation. Adding an unused field now would be exactly the
  unjustified schema growth `PHASE4D_SSE_ARCHITECTURE_DECISION.md` §6
  itself warns against ("Do not invent fields without explaining why they
  are needed"). Deferred, not forgotten — noted here so a later part
  doesn't have to rediscover why it's missing.
- No other field, method, or behavior of `Event` or `EventCollector`
  changed.

---

## 4. EventBroker implementation

New file: `app/application/broker.py`. Two classes:

### `Subscription`

- Wraps a `collections.deque(maxlen=capacity)` — the drop-oldest mechanism
  is the deque's own `maxlen` eviction, not custom logic, which keeps the
  hot path (`_put`) small and hard to get wrong.
- `get(timeout=None)` blocks on a `threading.Condition` until an event
  arrives, the subscription closes, or the timeout elapses; `get_nowait()`
  and `drain()` are non-blocking variants.
- Tracks `dropped_count` — incremented whenever a publish evicts an
  unread event, so backpressure is observable rather than silent (per
  `PHASE4D_SSE_ARCHITECTURE_DECISION.md` §6/§13's requirement that drops
  be counted, not swallowed).
- `close()` is idempotent, stops future delivery, and wakes any blocked
  `get()` — but does not discard events already queued before the close.

### `EventBroker`

- `subscribe()` / `unsubscribe(subscription)` / `publish(event)` /
  `shutdown()` / `subscriber_count()`, plus a `subscription()` context
  manager for convenience (tests; possibly a future non-HTTP consumer).
- `publish()` snapshots the subscriber set under the broker's lock, then
  releases that lock **before** pushing into any individual `Subscription`
  — each subscription has its own separate lock, so the broker is never
  holding two locks across a call that could block. `Subscription._put()`
  itself never blocks (drop-oldest, not block-on-full), so this ordering
  rules out the specific deadlock shape ("broker lock, then subscriber
  lock, while something else holds subscriber lock and wants broker lock")
  by construction — no subscriber operation ever tries to acquire the
  broker's lock.
- `subscribe()`/`publish()` after `shutdown()` degrade gracefully (a
  pre-closed subscription; a silent no-op) rather than raising, so a
  command handler mid-execution during process shutdown never fails or
  blocks because of the broker.

**Minimal API surface, no HTTP/SSE concerns**, per the Stage 2 instruction
not to prematurely design transport into the broker — no `Content-Type`,
no framing, no `async def` anywhere in this file. The eventual SSE route
(a later Part) will call `broker.subscribe()`, iterate
`subscription.get(...)` (likely via `asyncio.to_thread` or an
`asyncio.Queue`-based adapter, itself a Part-2+ decision, not made here),
and call `broker.unsubscribe()` on disconnect.

**Confirmed zero disallowed imports** — `app/application/broker.py`
imports only `threading`, `collections.deque`, `contextlib.contextmanager`,
`typing.Iterator`, and `app.application.events.Event`. `grep -rniE
"fastapi|starlette|PySide6|app\.gui|tauri" app/application/` matches only
comments/docstrings (including this file's own docstring, explaining what
it deliberately excludes) and pre-existing prose in `dto.py`/`handlers.py`
about *not* depending on `app.gui` — no actual import statement anywhere in
`app/application/` references any of those.

---

## 5. EventCollector compatibility

**No handler was modified in this Part.** `EventCollector` is untouched —
confirmed byte-for-byte via diff against the checkpoint zip (§9) for every
file except `app/application/events.py`, whose only change is the additive
`event_id` field (§3).

The Part 1 task's Stage 3 instruction was conditional: "Where architecture
requires handlers to emit to both EventCollector and EventBroker, make the
smallest clean integration necessary." Nothing in this Part's scope
requires that yet — the broker is fully testable, and its coexistence with
`EventCollector` fully provable, without wiring either into
`AnalyzeReportCommandHandler` or any other handler. `PHASE4D_SSE_
ARCHITECTURE_DECISION.md`'s own staged migration plan (§15) lists "Stage 3
— Handler integration" as a distinct step *after* "Stage 2 — Broker" — this
implementation Part corresponds to that document's Stage 1+2, not its
Stage 3. Wiring `broker.publish(event)` alongside the existing
`collector.publish(event)` calls in `AnalyzeReportCommandHandler` (and
adding the missing `ti.enrichment.*` events to `EnrichIocCommandHandler`,
per the architecture decision's §5 finding) is exactly the kind of
"unrelated Phase 4D command" change this Part's task explicitly scoped out
("Do NOT modify: ... unrelated Phase 4D commands ... unless a directly
verified dependency makes it unavoidable") — no such dependency exists,
since `tests/test_event_broker.py` proves the coexistence directly (see
`EventCollectorCompatibilityTests.test_same_event_object_can_go_to_both_
collector_and_broker`), without needing a real handler to demonstrate it.

This is deferred to a later Part, not silently dropped — see §11.

---

## 6. Files changed

| File | Change | Type |
|---|---|---|
| `app/application/events.py` | Added `event_id` field + `_new_event_id()` helper; docstring updated to mention the broker's existence | Modified (additive) |
| `app/application/broker.py` | `EventBroker`, `Subscription` | New |
| `tests/test_event_broker.py` | 37 tests covering Stage 4's full checklist | New |
| `docs/phase4/PHASE4D_SSE_PART1_IMPLEMENTATION.md` | This document | New |

**No other file was modified.** Confirmed by diffing this Part's working
tree against a fresh extraction of the checkpoint zip: `app/application/
handlers.py` and `app/api/app.py` are byte-identical to the checkpoint;
every file outside `app/application/{events,broker}.py`,
`tests/test_event_broker.py`, and this doc is untouched (§9).

`app/threat_intel/*`, `app/database/*`, `app/reporting/*`, `src-tauri/*`,
`frontend/*`, and every existing Phase 4C/4D file were **not** modified —
none was needed, and the task's source boundary explicitly excluded them
absent a verified dependency, which did not arise.

---

## 7. Tests executed

```
python -m unittest tests.test_application_layer -v
python -m unittest tests.test_event_broker -v
```

Both run from this Part's working tree, in this sandbox (no `fastapi`/
`pytest` installed or needed for either — both use stdlib `unittest`,
matching the existing project convention).

`grep -n "Event(" tests/test_application_layer.py` confirms no test
constructs an `Event` positionally (all go through `Event.create(...)` or
read attributes by name), which is why appending `event_id` at the end of
the dataclass's field list could not break that file — verified, not
assumed.

---

## 8. Test results

```
tests.test_application_layer: Ran 67 tests in 0.156s — OK
tests.test_event_broker:      Ran 37 tests in 0.079s — OK
```

**Regression count vs. checkpoint baseline: 67/67 still passing, unchanged
— no test was weakened, skipped, or deleted.** 37 new tests added, all
passing, covering every item in the Part 1 task's Stage 4 checklist:

1. Broker creation — `BrokerCreationTests` (2)
2. Single subscriber receives events — `SingleSubscriberTests` (2)
3. Multiple subscribers each receive their own events —
   `MultipleSubscriberTests.test_each_subscriber_gets_its_own_copy`
4. Subscriber isolation —
   `MultipleSubscriberTests.test_subscriber_isolation_one_draining_does_not_affect_other`,
   `test_unsubscribing_one_does_not_affect_other`
5. FIFO ordering within one subscriber —
   `OrderingTests.test_fifo_ordering_within_one_subscriber`
6. Bounded queue behavior — `BoundedQueueTests.test_queue_never_exceeds_capacity`
7. Drop-oldest behavior —
   `BoundedQueueTests.test_drop_oldest_keeps_most_recent_events`,
   `test_drop_oldest_increments_dropped_count`, `test_no_drop_when_under_capacity`
8. Unsubscribe — `UnsubscribeTests.test_unsubscribed_subscriber_stops_receiving`,
   `test_unsubscribe_removes_from_broker_count`
9. Repeated subscribe/unsubscribe —
   `UnsubscribeTests.test_repeated_subscribe_unsubscribe_cycles`,
   `test_double_unsubscribe_is_safe`
10. Publish with no subscribers — `PublishWithNoSubscribersTests` (2)
11. Clean shutdown — `ShutdownTests` (5, including a blocked-getter wakeup test)
12. Concurrent publish safety —
    `ConcurrencyTests.test_concurrent_publish_from_multiple_threads`
13. Concurrent subscribe/unsubscribe safety —
    `ConcurrencyTests.test_concurrent_subscribe_unsubscribe_safety`
14. No cross-subscriber ordering guarantee incorrectly assumed —
    `OrderingTests.test_no_cross_subscriber_ordering_guarantee_is_assumed`
    (asserts only the guarantee that *does* hold — per-subscriber FIFO —
    without asserting anything about inter-subscriber timing)
15. EventCollector compatibility — `EventCollectorCompatibilityTests` (3)

Plus 5 `EventContractTests` covering Stage 1 (event_id presence,
uniqueness, serialization, and that all pre-existing fields/frozen-ness are
unaffected).

---

## 9. Adversarial audit

Re-examined the actual implementation (not just the design) against every
item the Part 1 task listed:

| Attack | Finding | Status |
|---|---|---|
| Race conditions | Subscriber-set mutation guarded by one lock; each `Subscription`'s queue guarded by its own separate lock; no shared mutable state accessed outside a lock | **PASS** — `test_concurrent_publish_from_multiple_threads`, `test_concurrent_subscribe_unsubscribe_safety` (8 and 6 threads respectively) pass with zero exceptions and correct final counts |
| Deadlocks | `publish()` never holds the broker lock while acquiring a subscription lock (snapshots subscriber list first, releases broker lock, then calls `_put()` per subscriber); no subscription method ever acquires the broker's lock — no cycle possible | **PASS** — all concurrency tests complete without hanging (each has a `timeout` on `thread.join()`, and none timed out) |
| Unbounded memory | Every subscriber's queue is `deque(maxlen=capacity)` — physically incapable of exceeding capacity, not just policy-limited | **PASS** — `test_queue_never_exceeds_capacity` asserts `len(subscription) <= 5` after every one of 50 publishes |
| Subscriber leaks | `unsubscribe()`/`shutdown()` both remove from the internal `set` and close the subscription; verified no reference is retained by the broker afterward | **PASS** — `test_unsubscribe_removes_from_broker_count`, `test_shutdown_closes_existing_subscriptions` |
| Duplicate delivery | Each subscriber has its own independent deque; `publish()` iterates the subscriber snapshot exactly once per call, calling `_put()` exactly once per subscriber per event | **PASS** — `test_each_subscriber_gets_its_own_copy` shows exactly one copy per subscriber, not duplicated within one |
| Accidental replay | No storage of delivered events anywhere; `popleft()`/`get()` remove from the deque on read; nothing re-delivers to a new subscriber | **PASS** — `test_publish_with_no_subscribers_then_subscribe_gets_nothing` proves a late subscriber gets nothing from before it subscribed |
| Queue starvation | N/A in this Part — there is no consumer competing with a producer for CPU in a way that could starve; `get()`'s blocking wait uses a `Condition`, not a busy-loop | **PASS** (nothing to starve yet — no async/threaded consumer exists in production code this Part) |
| Shutdown races | `shutdown()` takes the broker lock, flips `_shut_down`, snapshots and clears the subscriber set, then closes each — a `publish()` racing this either sees the old snapshot (delivers, harmlessly, to a subscription that's about to close) or the post-shutdown no-op; either outcome is safe | **PASS** — `test_shutdown_then_publish_does_not_raise`, `test_shutdown_wakes_blocked_getter` |
| Lock held during blocking operations | Verified by inspection: the only blocking operation is `Subscription.get()`'s `Condition.wait()`, which by definition releases the lock while waiting (stdlib `threading.Condition` semantics) — no other method blocks while holding a lock | **PASS** |
| One subscriber blocking another | `publish()`'s per-subscriber `_put()` never blocks (append to a bounded deque is O(1), non-blocking even when full — it evicts, doesn't wait) | **PASS** — `test_concurrent_publish_does_not_cross_deliver_between_subscribers` confirms both subscribers get all 100 events even under concurrent publish from one thread |
| Application-layer dependency violations | No `fastapi`/`starlette`/`PySide6`/`app.gui`/Tauri import anywhere in `app/application/` (verified by grep, §4) | **PASS** |
| Duplicate event infrastructure | `EventCollector` and `EventBroker` are two distinct, independently-usable classes with no shared state and no inheritance between them — confirmed by `test_same_event_object_can_go_to_both_collector_and_broker`, which shows they don't interfere, not that they're secretly the same mechanism | **PASS** |

**Result: PASS on every item**, verified against running code and passing
tests in this Part — not a paper design review (that was Part 0). No item
required a "NOT TESTED due to environment limitations" designation; nothing
in this Part's scope needed `fastapi`, `pytest`, or any package not already
available.

---

## 10. Environment limitations

None specific to this Part's own code — everything implemented and tested
here uses only the Python standard library. The environment-level gap
already documented in `PHASE4D_API_EVENT_ARCHITECTURE.md` §19 (no
`fastapi`/`pytest` installed, no network access to install them) is
unchanged and still applies to any *future* part that touches
`app/api/app.py` or needs `fastapi.testclient`/`httpx` — not relevant to
this Part, since nothing here imports or requires them (§4).

---

## 11. Remaining SSE work

Everything explicitly deferred, per this Part's own scope and the
architecture decision's staged plan:

- **Handler integration** (architecture decision §15 Stage 3): wire
  `broker.publish(event)` into `AnalyzeReportCommandHandler` alongside the
  existing `collector.publish(event)` calls; add the missing
  `ti.enrichment.started/completed/failed` events to
  `EnrichIocCommandHandler` (§5 of this doc; §5 of the architecture
  decision).
- **The `enrich_ioc` event-loop fix** (`ThreatIntelService._lookup_raw`'s
  `asyncio.run()`-inside-a-running-loop hazard, architecture decision §2)
  — a prerequisite for safely emitting `ti.enrichment.*` events from the
  request path, not yet touched.
- **SSE transport** — `GET /events` still returns `501`; no
  `StreamingResponse`, no SSE framing, no heartbeat.
- **Frontend integration** — `useEventStream.ts` is still the documented
  no-op; no `EventSource` wired up.
- **Process-lifetime broker instance** — no singleton `EventBroker` is
  created or owned by `app/api/entrypoint.py` yet; this Part only provides
  the class, not its production wiring.
- **Tauri/Rust** — untouched, as scoped.

---

## 12. Freeze status

**Phase 4D is NOT frozen.** This Part implements only two of the eight
stages in the architecture decision's implementation plan (§15: "Stage 1 —
event domain contracts" and "Stage 2 — broker"). None of the twelve freeze
criteria in `PHASE4D_SSE_ARCHITECTURE_DECISION.md` §16 are yet satisfied —
in particular, criteria 5–7 (real SSE frames, multi-subscriber over an
actual HTTP connection, disconnect handling over a real connection) require
the SSE transport this Part explicitly does not implement. No
`PHASE4D_FREEZE.md` or equivalent was created.

---

## 13. Full project ZIP

See §9 above (this document) for the diff-based verification performed
before packaging; build/verification commands and result are recorded
alongside the zip below.

### Correction to the Part 0 checkpoint zip, found during this Part's verification

Diffing this Part's fresh extraction against the *previous* checkpoint
(`SOC-IQ-Phase4D-SSE-ARCHITECTURE-DECISION.zip`, delivered at the end of
Part 0) initially showed 5 unexpected differences: `app/reporting/
builder.py`, `app/gui/design/theme/stylesheet_builder.py`, `app/gui/
widgets/dashboard/ioc_distribution_widget.py`, `app/services/dashboard_
ioc_distribution_service.py`, and `src-tauri/build.rs` all appeared "only
in" this Part's extraction.

Investigated rather than assumed benign: these files were **not** created
or modified by this Part. Diffing this Part's working tree against a
fresh extraction of the *original* project zip (from before Part 0)
confirmed all 5 files are legitimate, pre-existing project source,
untouched throughout. The actual defect was in **Part 0's own zip-build
command**, whose exclude patterns (`-x "*build*" -x "*dist*"`) matched
those strings as *substrings anywhere in a path* — `builder.py`,
`stylesheet_builder.py`, `build.rs` all contain `build`; `ioc_
distribution_widget.py` and `dashboard_ioc_distribution_service.py` both
contain `dist` (from "distribution"). Part 0's delivered zip silently
omitted these 5 real source files as a result.

This Part's zip-build command uses path-anchored patterns instead
(`-x "*/build/*" -x "*/dist/*"`, matching only an actual directory
segment named `build`/`dist`, e.g. a Rust `target/` or JS `dist/` output
folder — not any filename containing those letters), and was verified
(§9) to include all 5 files correctly. This Part's zip is a superset of
Part 0's intended content, not just Part 0's content plus this Part's
own changes — flagged here rather than silently carried forward, since a
future part treating Part 0's zip as ground truth would otherwise
silently lose those 5 files again.
