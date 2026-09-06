# PHASE 4D SSE — PART 4A IMPLEMENTATION: PART 3 AUDIT + FRONTEND EVENTSOURCE INTEGRATION

**Status: PART 4A OF THE FINAL 3-PART SSE COMPLETION SEQUENCE. Phase 4D is
NOT frozen.**

This audits the already-completed Part 3 SSE transport, then wires the
frontend's placeholder `useEventStream` hook to a real, native `EventSource`
connection. It does **not** implement Tauri command wiring, does not
freeze Phase 4D, and does not claim Tauri is compiled or verified.

---

## 1. Checkpoint verification

Performed before any edit, against the uploaded ZIP directly (not the
filename, not the prompt):

| Check | Result |
|---|---|
| `app/application/events.py`, `broker.py`, `execution.py` | Present |
| `EventBroker`, `get_application_broker()` | Present, `app/application/broker.py:320` |
| `AnalyzeReportCommandHandler` / `EnrichIocCommandHandler` broker publication | Present, `app/application/handlers.py` (`_publish()` closures at lines ~343, ~450) |
| `enrich_ioc` running-event-loop fix | Present — `run_blocking()` via `app/application/execution.py`, confirmed by `EnrichIocEventLoopRegressionTests` passing |
| `app/api/app.py` SSE implementation | Present — real `StreamingResponse`, `text/event-stream`, SSE framing, heartbeat, disconnect cleanup, broker subscribe/unsubscribe |
| `docs/phase4/PHASE4D_SSE_PART{1,2,3}_IMPLEMENTATION.md` | All present |
| All 10 Phase 4D commands | Confirmed via `COMMAND_HANDLERS` |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| `frontend/src/` architecture | Present — `shared/api/`, `shared/events/`, `shared/hooks/`, `app/providers/`; `shared/state/`, `shared/types/`, `features/` exist but are empty |
| Existing `useEventStream.ts` / event types | Present — **placeholder/no-op**, by design (see §4) |
| Tauri bridge/scaffold | Present — `src-tauri/src/sidecar.rs` (process supervision only); no `#[tauri::command]` registered anywhere in `src-tauri/src/` |

No discrepancy from "Part 3 already implemented" was found. Proceeded to
audit, then implementation.

---

## 2. Part 3 audit result: **PASS**

Checked directly against `PHASE4D_SSE_ARCHITECTURE_DECISION.md` and Part
3's own doc, not just re-read Part 3's claims:

**A. `GET /events`** — confirmed by reading `app/api/app.py` line-by-line:
returns `StreamingResponse(..., media_type="text/event-stream")`, no
longer 501. `_format_sse_event()` renders `id:`/`event:`/`data:` +
blank-line framing from `Event.to_dict()` unchanged — no second event
schema. `_format_sse_heartbeat()` returns only `": heartbeat\n\n"`, an SSE
comment line with no `event_id`, never passed through
`EventBroker.publish()` — structurally cannot enter the broker or consume
subscriber queue capacity (no code path exists from the heartbeat
function to `publish()`).

**B. Subscription lifecycle** — `_sse_event_stream()` subscribes on entry,
unsubscribes in a `finally` block that covers normal completion, client
disconnect (`request.is_disconnected()`), and any exception. No
GC-reliant cleanup.

**C. Multiple subscribers** — each connection gets its own `Subscription`
(Part 1's bounded, drop-oldest queue); `Subscription.get()` runs via
`asyncio.to_thread`, so one slow/idle connection cannot block the shared
event loop or another connection.

**D. Broker lifecycle** — `get_application_broker()` is the sole
accessor; no request-local broker; no second broker instantiated
anywhere in `app/api/app.py`. One real gap, already known: no explicit
`EventBroker.shutdown()` call is wired into a FastAPI startup/shutdown
hook — Part 3's own doc lists this under its "Remaining work" section
(deferred, not missed). This part's own file boundary (§15 of the Part
4A task) says backend changes should be zero and any necessary backend
change must be stopped-on-and-documented rather than made silently — so
this was left alone rather than "fixed" here.

**E. Dependency direction** — re-ran the same check Part 3's own audit
describes: `grep -rn "fastapi\|starlette\|PySide\|PyQt\|tauri" -i
app/application/` returns only doc-comment prose explaining the boundary
is *not* crossed (e.g. `broker.py`'s own docstring naming the frameworks
it does *not* import). Zero actual imports.

**F. Security** — `_format_sse_event()` uses `Event.to_dict()` (plain
`dataclasses.asdict()`) unchanged; it does not add or strip fields, so
whatever guarantee "handlers never place secrets in a payload" already
had continues unchanged into the wire format. No `repr()` use anywhere in
the SSE path.

**G. Existing command behavior** — `app/application/handlers.py` is
byte-identical to the pristine checkpoint (confirmed by `diff -rq`
against a fresh extraction of the uploaded ZIP, §16 below); nothing in
this part touched command semantics.

No defect was found. Nothing in Part 3's source was modified.

---

## 3. Part 3 tests — real execution only

Environment check: `pip install fastapi httpx pytest starlette uvicorn`
→ **blocked** (`ERROR: Could not find a version that satisfies the
requirement fastapi (from versions: none)` — no network egress). This
matches the environment state Part 3's own doc describes as resolved in
*that* session; it is not resolved in *this* session/sandbox, and no
result was fabricated to paper over that.

Ran what is actually executable:

```
python -m unittest tests.test_application_layer -v
```
**Result: 77 passed, 0 failed.**

```
python -m unittest tests.test_event_broker -v
```
**Result: 37 passed, 0 failed.**

**Total: 114/114 passing** — exactly matches the documented Part 2/3
baseline.

`pytest tests/test_api_layer.py -v` (SSE HTTP-boundary tests) —
**blocked**, `fastapi`/`httpx`/`pytest` not importable. The file itself
was inspected directly instead (not executed): it contains real,
specific assertions matching this part's own audit checklist —
`test_events_stream_is_no_longer_501`, `test_events_stream_content_type_is_sse`,
`test_published_event_is_delivered_with_correct_sse_framing`,
`test_heartbeat_is_valid_sse_comment_and_never_a_broker_event`,
`test_secret_free_payload_survives_unchanged_into_the_sse_frame`,
`test_real_broker_event_reaches_the_http_stream`,
`test_two_subscribers_receive_the_same_event_and_one_ending_does_not_affect_the_other`.
These were read, not run, in this session — reported as such rather than
claimed as "passing" without execution.

---

## 4. Frontend architecture inspected

Read before writing any code:

- `frontend/package.json` — dependencies are `react`, `react-dom` only.
  No HTTP client library, no state-management library, **no test runner**
  (no `vitest`/`jest`/`@testing-library/*` anywhere in
  `dependencies`/`devDependencies`).
- `frontend/tsconfig.json` — full strict mode, every flag explicit
  (`noImplicitAny`, `strictNullChecks`, `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`, `noUnusedLocals`/`Parameters`, etc.).
- `frontend/src/shared/api/client.ts` — **no working API base URL
  mechanism exists.** `runCommand()` unconditionally
  `Promise.reject(new SidecarNotConnectedError())`. Its own docstring
  states the reason: Tauri hands React the sidecar's dynamic port at
  startup via a Tauri command that does not exist yet.
- `frontend/src/shared/events/{types.ts,useEventStream.ts}` — the
  existing hook is an intentional no-op (`useEffect` with an empty body);
  `types.ts` hand-mirrors `docs/contracts/event-model.md`'s envelope.
- `frontend/src/app/providers/ErrorBoundary.tsx` — render-time error
  boundary; no state management, no data-fetching layer.
- `frontend/src/shared/state/`, `frontend/src/shared/types/`,
  `frontend/src/features/` — **all empty.** No existing state system, no
  existing UI consumer of event data, nothing to integrate with or avoid
  duplicating beyond what already exists in `shared/api/` and
  `shared/events/`.
- `src-tauri/src/sidecar.rs` — read directly (not assumed from its
  filename). Its own doc comment explicitly lists, as **not implemented
  here, deferred to a later phase**: *"No `#[tauri::command]`
  registration and no wiring into `src-tauri/src/lib.rs`'s
  `tauri::Builder`."* `src-tauri/src/lib.rs` was also checked — no
  `invoke_handler`/`tauri::command` anywhere in the crate.
- `docs/contracts/ipc-rules.md` rule 2 — *"React never calls Python
  directly; it calls the sidecar's HTTP origin, which Tauri hands it at
  startup (dynamic port, **never hard-coded**)."*

**Conclusion:** there is no legitimate way, in this checkpoint, to open a
real end-to-end `EventSource` connection without either (a) hardcoding an
origin in violation of `ipc-rules.md` rule 2, or (b) inventing Rust
`#[tauri::command]` wiring, which this part's own instructions (§10)
explicitly forbid. This is exactly the situation §10 anticipated:
*"If the desktop runtime needs a different API URL mechanism, document
the requirement for Part 4B rather than creating an ad-hoc workaround
now."* That is what was done — see §9 below.

---

## 5. A real, pre-existing contract bug found and fixed

Before writing the hook, the actual wire shape was re-verified directly
against the producer (`Event.to_dict()` in `app/application/events.py`
via `_format_sse_event()` in `app/api/app.py`), not assumed from the
frontend's own placeholder type or from `event-model.md`'s example JSON.
Two real discrepancies came out of that:

1. **`investigation_id` type.** `event-model.md`'s example shows
   `"investigation_id": "inv-1029"` (a string). The actual Python
   dataclass field is `investigation_id: int | None`
   (`app/application/events.py`), populated from
   `investigation.investigation_id` (`app/database/models.py:51`,
   `investigation_id: int | None = None`) — a plain integer, never
   string-formatted anywhere in the publish path. The frontend's
   `SocIqEvent.investigation_id` was typed `string | null`, matching the
   doc's aspirational example rather than the real wire value. Fixed to
   `number | null`.

   This isn't a guess: `event-model.md` itself has a section titled
   **"KNOWN DUPLICATION"** that names exactly this file
   (`frontend/src/shared/events/types.ts`) as a hand-mirrored type with
   real future schema-drift risk "once events are actually emitted" —
   which, as of Part 3, they now are. This is that drift, caught and
   corrected in this part rather than left live.

2. **`event_id` field.** `Event` is a frozen dataclass with an
   `event_id: str = field(default_factory=_new_event_id)` field, and
   `to_dict()` is exactly `dataclasses.asdict(self)`, so `event_id` is
   present in every `data:` payload — but was absent entirely from the
   frontend's `SocIqEvent` interface. Added.

Both required fixing `types.ts` correctly before the hook could validate
incoming frames against reality rather than against a two-Parts-stale
placeholder.

---

## 6. Frontend implementation

**Files changed (3):**
- `frontend/src/shared/api/client.ts` — added `getSidecarOrigin(): Promise<string>`,
  same unimplemented-and-documented shape as the existing `runCommand()`
  (rejects with `SidecarNotConnectedError` until the Tauri command
  exists). `SidecarNotConnectedError`'s message updated to name the
  actual missing piece (no Tauri command exists) rather than referencing
  "Phase 4E Part 1," which is no longer the current phase.
- `frontend/src/shared/events/types.ts` — the two fixes in §5, plus an
  updated module docstring reflecting that `GET /events` is now live.
- `frontend/src/shared/events/useEventStream.ts` — replaced the no-op
  placeholder with a real subscription backed by the new connection
  manager.

**Files added (2):**
- `frontend/src/shared/events/eventSourceManager.ts` — the actual
  transport logic (see §7).
- `frontend/src/shared/events/useEventStreamStatus.ts` — optional
  connection-status hook for a future UI consumer; adds no UI itself
  (§9 below explains why).

**Backend changes: zero.** Confirmed by `diff -rq` of the full working
tree against a fresh extraction of the uploaded ZIP, excluding only
`frontend/`, `__pycache__`, and `.pytest_cache` — **no output**, i.e. every
non-frontend file is byte-identical to the checkpoint. Within
`frontend/`, `diff -rq` shows exactly the 3 modified + 2 new files above
and nothing else.

---

## 7. `EventSource` behavior

- **Connection model:** one shared, module-level `EventSource`,
  ref-counted across every `useEventStream()` call site
  (`eventSourceManager.ts`). The first `subscribe()` triggers connection;
  the connection closes the instant the last subscriber unsubscribes.
  This avoids one HTTP connection per hook call/per component — multiple
  components subscribing to different event names still share one
  `/events` connection, consistent with the backend already treating
  each *connection* (not each event name) as one `Subscription`.
- **URL construction:** `${origin.replace(/\/+$/, "")}/events` — origin
  comes only from `getSidecarOrigin()`, never hardcoded, per
  `ipc-rules.md` rule 2.
- **Event routing:** `addEventListener(eventName, handler)` per distinct
  `EventName` currently subscribed to, attached/detached as subscribers
  come and go — matches the backend's `event:` line naming exactly, so
  `EventSource`'s native named-event dispatch does the routing; no
  parallel routing table duplicating what the browser already does.
- **Payload validation:** `parseSocIqEvent()` structurally checks every
  field's type against the real wire shape (§5) before constructing a
  `SocIqEvent`; returns `null` on any mismatch rather than casting.
  `JSON.parse` failures are also caught and treated as `null`. No raw
  `JSON.parse(...) as SocIqEvent` cast exists anywhere in this
  implementation.
- **Malformed-payload handling:** a `null` parse result is dropped with a
  `console.warn` containing only the event name and byte length — never
  the payload body — so a malformed or unexpected frame cannot crash the
  React tree and cannot leak potentially sensitive payload content to the
  console.
- **Heartbeat:** requires no frontend code at all. `: heartbeat\n\n` is an
  SSE comment; native `EventSource` does not fire `onmessage` or any
  `addEventListener` callback for comment lines — this was verified
  against the SSE spec's comment-line behavior, not assumed.
- **Error handling:** `onerror` inspects `readyState` — `CONNECTING`
  (browser is auto-retrying) maps to status `"connecting"`, `CLOSED` maps
  to `"unavailable"`. No exception escapes to the caller; nothing is
  thrown into a React render path.
- **Reconnection:** relies entirely on native `EventSource`'s built-in
  reconnect (the browser retries automatically after an error unless
  `.close()` was called) rather than adding a second, custom retry layer
  on top of it. This part's own instruction — *"do not introduce
  aggressive retry behavior... if reconnection is implemented, use a
  bounded/backoff strategy and document it"* — is satisfied by **not**
  implementing a second mechanism: the only retry behavior present is the
  browser's own default, which this manager does not override, duplicate,
  or make more aggressive. Origin *re-resolution* (as opposed to the
  already-open connection's own retry) only happens when a genuinely new
  subscriber calls `subscribe()` while the manager is `"idle"` or
  `"unavailable"` — not on a timer, so there is no unbounded background
  polling loop.

---

## 8. Lifecycle / cleanup / React specifics

- `useEventStream()`'s `useEffect` cleanup calls the manager's
  `unsubscribe`, which is symmetric with `subscribe()` — React
  StrictMode's mount→unmount→mount double-invoke in development produces
  subscribe→unsubscribe→subscribe, which is ref-counted correctly rather
  than leaking or double-connecting.
- The event handler is read through a `useRef`, updated on every render,
  and only the ref is captured by the manager's callback — passing a new
  inline arrow function as `handler` on every render (the normal case for
  a component-scoped callback) cannot produce a stale closure, and the
  effect itself only re-runs (re-subscribes) when `eventName` changes,
  not on every render.
- No caller is required to memoize `handler` for correctness.

---

## 9. Connection configuration / Tauri compatibility

No API base URL is hardcoded anywhere in this implementation. The single
resolution point, `getSidecarOrigin()`, is intentionally left
unimplemented (mirrors `runCommand`'s existing, already-approved
pattern) rather than given a `http://localhost:8000` fallback, because
no such fallback is an established project convention — the opposite is
explicitly documented (`ipc-rules.md` rule 2, `client.ts`'s own prior
docstring).

**No Rust changes were made.** No `#[tauri::command]` was added, no
`invoke_handler` registration was touched, and nothing claims Tauri is
verified or compiled. Per §10 of this part's own instructions, the actual
requirement is documented here instead of worked around:

> **Requirement for the next part (frontend/Tauri origin wiring):** a
> `#[tauri::command]` (e.g. `get_sidecar_origin`) must be registered in
> `src-tauri/src/lib.rs`'s `tauri::Builder`, backed by the port
> `src-tauri/src/sidecar.rs`'s `SidecarProcess` already captures from the
> handshake (`app/api/entrypoint.py`'s single-decimal-line-on-stdout
> contract). Once that exists, `shared/api/client.ts`'s
> `getSidecarOrigin()` becomes a real `invoke("get_sidecar_origin")` call,
> and this part's `eventSourceManager.ts` needs no further change — it
> already depends only on `getSidecarOrigin()` resolving to a real
> origin string, not on how that string is obtained.

No status indicator exists anywhere in the current UI to integrate with,
so `useEventStreamStatus.ts` was added as a plain hook only — no status
UI, no chrome, nothing to "demonstrate SSE works" beyond the working
mechanism itself.

---

## 10. Frontend tests

**Blocked — no test runner configured.** `frontend/package.json` has no
`vitest`, `jest`, `@testing-library/react`, or any other test framework in
either `dependencies` or `devDependencies`, and `npm install` (attempted,
to check whether one could be added) failed immediately with a `403
Forbidden` from the npm registry — no network egress in this
environment, so a framework could not be installed even if adding one
were in scope. Adding a new test framework was also out of this part's
"prefer zero new dependencies" / "do NOT install a new testing framework
just for this part unless absolutely necessary" guidance, so none was
added.

**What was done instead, as the closest available substitute:**
- All 5 changed/new TypeScript files were typechecked using a global
  `tsc` (v6.0.3, present in this sandbox outside the project) against
  the project's **actual** `tsconfig.json` compiler options
  (`strict`, `noImplicitAny`, `strictNullChecks`,
  `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`,
  `noUnusedLocals`/`Parameters`, target `ES2022`, lib
  `ES2022`/`DOM`/`DOM.Iterable`), with minimal same-shape stubs standing
  in only for the two things `npm install` would otherwise provide
  (`react`'s `useEffect`/`useRef`/`useState` signatures, and the
  `../api/client` import boundary). **Result: zero errors** across
  `types.ts`, `client.ts`, `eventSourceManager.ts`, `useEventStream.ts`,
  `useEventStreamStatus.ts`.
- This is static verification of syntax/type correctness only — it does
  **not** exercise runtime behavior (actual `EventSource` open/dispatch/
  cleanup, ref-counting across simulated mounts, StrictMode
  double-invoke). That runtime verification remains genuinely blocked by
  the missing test framework and is reported as blocked, not claimed.

---

## 11. Typecheck / build

`npm install` → **blocked**: `npm error code E403 ... 403 Forbidden -
GET https://registry.npmjs.org/yallist/-/yallist-3.1.1.tgz` — no network
egress available to this sandbox.

`npm run typecheck` / `npm run build` (the project's actual `tsc
--noEmit` / `tsc --noEmit && vite build` scripts, read from
`package.json` rather than assumed) → **could not be run** — no
`node_modules`, and it cannot be installed in this environment. See §10
for the substitute static check that was actually performed instead, and
its explicit limits.

---

## 12. Adversarial audit

| Check | Result |
|---|---|
| Duplicate `EventSource` connections | **PASS** — single module-level `source` variable in `eventSourceManager.ts`; `connect()` no-ops if `source !== null` or already `"connecting"` |
| Event listener leaks | **PASS** — `attachedListeners` map is the single source of truth for what's attached; `subscribe()`'s returned unsubscribe removes both the logical subscriber and, if no other subscriber wants that event name, the native listener |
| Stale closures | **PASS** — handler read via `useRef`, updated every render; manager callback only closes over the ref, not the handler value itself |
| Unbounded reconnect loops | **PASS** — no custom retry timer exists at all; relies solely on native `EventSource` retry; origin re-resolution is subscribe-triggered, not timer-driven |
| Malformed JSON crashing UI | **PASS** — `parseSocIqEvent` catches `JSON.parse` exceptions and returns `null`; caller drops and warns, never throws |
| Duplicate event handling | **PASS** — `dispatch()` iterates `subscribers` once per received frame; no double-registration path found |
| Hardcoded API URLs | **PASS** — grepped the 5 changed files for `localhost`/`127.0.0.1`/`http://` literals: the only match is inside a doc comment on `getSidecarOrigin()` giving an illustrative example value (`http://127.0.0.1:54213`); no executable code path contains a literal origin |
| Second API client | **PASS** — `getSidecarOrigin` added to the *existing* `client.ts`, not a new module |
| Second state system | **PASS** — no state library added; manager uses plain module-level variables + `Set`/`Map`, consistent with the project having no state library at all yet |
| Direct backend/internal imports | **PASS** — no Python path, no filesystem path, no direct DB/service import anywhere in `frontend/` |
| Secret logging | **PASS** — the only `console.warn` call logs event name + byte length, never `raw.data` or the parsed payload |
| SSE payload assumptions not supported by backend | **PASS** — `EventName` union still includes `investigation.*` (per `event-model.md`'s documented vocabulary), but no code path fabricates behavior for it; only `analysis.*`/`ti.enrichment.*` are ever actually dispatched, matching what `app/application/handlers.py` actually emits |
| React StrictMode duplication | **PASS by design** — see §8; ref-counted subscribe/unsubscribe symmetry handles double-invoke |
| Tauri architecture conflicts | **PASS** — no Rust file touched; `getSidecarOrigin()`'s contract (return a real origin string, however obtained) is exactly what a future `invoke("get_sidecar_origin")` call would satisfy without further changes to `eventSourceManager.ts` |
| Unnecessary dependencies | **PASS** — zero new npm dependencies added |
| Modifications outside frontend/SSE scope | **PASS** — confirmed via `diff -rq` against a fresh extraction of the uploaded ZIP (§6) |
| Backend dependency direction (re-checked after frontend work) | **PASS** — re-ran the same `app/application/` import grep; unchanged, zero matches, because zero backend files were touched |

---

## 13. Known limitations

1. **No end-to-end connection is actually achievable in this checkpoint.**
   `getSidecarOrigin()` will always reject until a `#[tauri::command]` is
   registered (§9) — every subscription will observe status
   `"unavailable"`, never `"open"`, until that exists. This is the
   expected, documented state, not a defect in this part's code.
2. Runtime behavior (actual browser `EventSource` open/dispatch, ref
   counting under real React mounts) is verified only by static
   typechecking in this session, not by execution — no test framework is
   installed and none could be installed (§10/§11).
3. The Part 3-documented backend gap (no explicit
   `EventBroker.shutdown()` wired to FastAPI lifecycle hooks) remains
   open — out of this part's file boundary, not fixed here.
4. `investigation.*` events remain declared in `EventName` per
   `event-model.md`'s documented vocabulary but are not emitted by any
   current command handler — confirmed by reading
   `app/application/handlers.py` directly, not assumed.

---

## 14. What remains for Part 4B

- Register a `#[tauri::command]` (e.g. `get_sidecar_origin`) in
  `src-tauri/src/lib.rs`, backed by the port already captured in
  `src-tauri/src/sidecar.rs`'s `SidecarProcess`.
- Wire `shared/api/client.ts`'s `getSidecarOrigin()` to the real
  `invoke("get_sidecar_origin")` call.
- End-to-end verification: an actual browser (or Tauri webview) opening
  `/events` and observing real `analysis.*`/`ti.enrichment.*` frames.
- Decide whether/how to wire the still-open `EventBroker.shutdown()` →
  FastAPI lifecycle gap noted in §12 above and in Part 3's own doc.
- Final Phase 4D audit and freeze decision (explicitly out of scope for
  both this part and Part 4B per the task sequence).

---

## 15. Freeze status

**PHASE 4D NOT FROZEN.** This part audited and extended, but did not
complete, the SSE feature — the frontend cannot yet reach a live
connection, and Tauri wiring is untouched by design.

---

## 16. Full-project ZIP

See final report for path. Built from this working tree; verified by
fresh extraction, byte-for-byte `diff -rq` against the pre-extraction
working tree (excluding only `__pycache__`, `.pytest_cache`, and
`node_modules`), re-run of `tests.test_application_layer` +
`tests.test_event_broker` (114/114) from the extracted copy, and manual
confirmation that no cache artifacts were packaged.
