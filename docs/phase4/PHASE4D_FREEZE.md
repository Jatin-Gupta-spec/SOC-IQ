# SOC-IQ — Phase 4D Freeze Report

**Date:** 2026-08-24
**Audit type:** Final pre-freeze adversarial audit (source re-verification, not a rebuild)
**Classification: CLASS B — FREEZE READY WITH DOCUMENTED ENVIRONMENT BLOCKER**

This document is the freeze record for Phase 4D. It is written from direct
source inspection and a live test run performed in this session, cross-checked
against (but not blindly trusted from) the prior session's
`docs/phase4/PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md` and
`docs/phase4/PHASE4D_FREEZE_REMEDIATION.md`. No implementation source was
changed to produce this freeze. See the accompanying audit report for the
full 21-section breakdown; this document summarizes the freeze-relevant
conclusions only.

---

## 1. Audited checkpoint

`SOC-IQ-Phase4D-CANONICAL-FULL-PROJECT.zip`, extracted fresh into a clean
directory this session. 463 tracked files. No `__pycache__/`,
`.pytest_cache/`, `node_modules/`, `target/`, or nested archives present in
the uploaded archive.

## 2. Implementation scope — 10/10 commands

All 10 planned commands are implemented, DTO-validated, dispatched through a
single `dispatch()` function, and registered in
`app/application/handlers.py::COMMAND_HANDLERS`:

`get_investigation`, `list_investigations`, `analyze_report`,
`delete_investigation`, `search_investigations`, `get_iocs`, `save_settings`,
`export_report`, `enrich_ioc`, `get_threat_intelligence`.

Each traces cleanly: DTO → `dispatch()` → command handler → domain/service
call (`InvestigationService`, `ReportingService`, `SettingsService`,
`ThreatIntelService`) → response envelope (`ok()`/`fail()`). No command
bypasses this path. `app/application/*` and `app/api/*` contain zero real
imports of `PySide6`, `app.gui`, `fastapi`-in-the-application-layer,
`starlette`, or anything Tauri/Rust (grep-confirmed this session; the only
matches are docstring/comment references documenting the *absence* of such
coupling).

## 3. SSE / event architecture

- **Event** (`app/application/events.py`): frozen dataclass, stable
  `event_id` (uuid4, generated once at `Event.create()`), `correlation_id`,
  `to_dict()` used verbatim as the wire payload.
- **EventBroker** (`app/application/broker.py`): thread-safe, bounded
  per-subscriber queues (`deque(maxlen=32)`, drop-oldest with a tracked
  `dropped_count`), per-subscriber isolation, no lock held across a
  potentially-blocking operation, idempotent `shutdown()`/`unsubscribe()`,
  no replay/global history. Verified this session by a full pass of
  `tests/test_event_broker.py` (37/37, including concurrent
  publish/subscribe/unsubscribe cases).
- **SSE transport** (`app/api/app.py`): `GET /events` returns a real
  `StreamingResponse`. Correct SSE framing (`id:`/`event:`/`data:` for real
  events; `: heartbeat` comment frames, never constructed as an `Event` and
  never passed through the broker). Disconnect cleanup via `try/finally`
  unsubscribe, safe under exception, double-close, and broker-initiated
  closure. Each connection gets its own `Subscription`; a slow/idle client
  cannot block another connection because the blocking `Subscription.get()`
  call is bridged onto a thread via `asyncio.to_thread`, not awaited
  directly on the event loop.
- **Event publication**: `analyze_report` (`analysis.started` /
  `.progress` / `.completed` / `.failed`) and `enrich_ioc`
  (`ti.enrichment.started` / `.completed` / `.failed`) each use one
  `correlation_id` per call and publish the *same* `Event` object to both
  the `EventCollector` (test/local sink) and the `EventBroker` (live sink)
  — never two independently-constructed events for one occurrence, so no
  duplicate delivery. No API key or provider secret appears in any observed
  event payload or `str(exception)` message (traced through
  `app/threat_intel/virustotal.py`'s raise sites).
- **Blocking execution bridge**: `enrich_ioc`'s inner
  `asyncio.run()` call (inside `ThreatIntelService._lookup_raw`) is run via
  `run_blocking()` on a small, bounded, lazily-created, process-lifetime
  `ThreadPoolExecutor` (`app/application/execution.py`, `max_workers=4`) —
  safe to call from a thread that already has a running event loop, and does
  not leak a new thread per call.

**Known, documented limitation (not a defect):** `EventBroker.shutdown()` is
not wired to the FastAPI/uvicorn process shutdown path
(`app/api/entrypoint.py` relies on uvicorn's own SIGINT/SIGTERM handling to
close the listening socket; no explicit `broker.shutdown()` call exists).
Because the broker is an in-process singleton with no external resources
(no file handles, no sockets of its own), process exit reclaims it and every
subscription with it — an SSE client that is still connected at shutdown
simply sees its connection dropped, the same as any other in-flight HTTP
request during a hard process stop. This is a scope decision already stated
in `app/api/entrypoint.py`'s own docstring ("no additional lifecycle
machinery is added here... out of scope until the Tauri shell exists"), not
an oversight discovered this session. It does not block freeze.

## 4. Frontend EventSource

`frontend/src/shared/events/eventSourceManager.ts` implements a single,
ref-counted `EventSource` shared across every `useEventStream` call site
(one HTTP connection to `/events` regardless of how many listeners are
mounted), symmetric subscribe/unsubscribe (safe under React StrictMode's
mount→unmount→mount), structural payload validation
(`parseSocIqEvent`) that drops malformed frames without throwing or logging
payload contents, and reliance on the browser's native `EventSource`
reconnect behavior rather than a custom retry loop.
`frontend/src/shared/api/client.ts`'s `getSidecarOrigin()` resolves the
origin via `invoke("get_sidecar_origin")` only when `isTauri()` is true,
and rejects with a typed, retryable error in a plain browser tab.

## 5. Tauri bridge

`src-tauri/src/lib.rs` defines exactly one `#[tauri::command]`
(`get_sidecar_origin`), registered exactly once via
`tauri::generate_handler![get_sidecar_origin]`, called from exactly one
frontend call site. `src-tauri/capabilities/default.json` grants only
`core:default` and the one named `get_sidecar_origin` permission — no
`shell:*`, `fs:*`, or `http:*` capability.

**Environment verification blocker (external, not a source defect):**
`src-tauri`'s dependency graph (specifically the transitive dependency
`dlopen2 0.8.2`, confirmed in `src-tauri/Cargo.lock`) requires the Rust
`edition2024` feature, which needs cargo/rustc ≥1.85. This sandbox has no
Rust toolchain installed at all (`rustc`/`cargo`: not found). This matches
the exact blocker already documented by the prior session (which had cargo
1.75.0 and hit the same `edition2024` error). Per this audit's own
instruction (§15), this is classified as an **ENVIRONMENT VERIFICATION
BLOCKER**, not a claim that the Tauri binary is broken — nothing in source
review of `lib.rs`, `sidecar.rs`, or the capability manifest indicates a
defect. `sidecar-core` (the crate `src-tauri` builds on) does not depend on
`dlopen2` and was reported by the prior session to compile and pass 49/49
tests on its available 1.75.0 toolchain; that specific number is carried
forward from the prior session's record, not independently re-executed
here, since this sandbox has no Rust toolchain at all.

## 6. Test matrix (this session)

| Suite | Command | Result (this session) |
|---|---|---|
| Application layer | `python -m unittest tests.test_application_layer -v` | **77/77 PASS** |
| Event broker | `python -m unittest tests.test_event_broker -v` | **37/37 PASS** |
| API layer (FastAPI TestClient) | `pytest tests/test_api_layer.py -v` | **BLOCKED** — `fastapi` not installed, no network access to install it in this sandbox |
| Sidecar entrypoint | `pytest tests/test_sidecar_entrypoint.py -v` | **BLOCKED** — `uvicorn` not installed, same cause |
| Full non-GUI suite | `pytest tests/ --ignore=tests/gui -q` | **BLOCKED** — `pytest` itself not installed in this sandbox |
| GUI suite | `pytest tests/gui -q` | **BLOCKED** — `PySide6` not installed |
| `sidecar-core` (Rust) | `cargo test` | **BLOCKED** — no Rust toolchain in this sandbox |
| `src-tauri` (Rust) | `cargo check` | **BLOCKED** — no Rust toolchain in this sandbox; would additionally hit the `edition2024` MSRV blocker (§5) even with one |
| Frontend typecheck/build | `npm run typecheck` / `npm run build` | **BLOCKED** — no network access to `npm install` dependencies in this sandbox |

The prior session (`PHASE4D_FREEZE_REMEDIATION.md` §6) recorded, in an
environment with `fastapi`/`uvicorn`/`pytest`/`PySide6`/Rust 1.75.0/npm
network access all available: API layer 29/29, sidecar entrypoint 8/8, full
non-GUI 600/600, GUI 154/154, `sidecar-core` 49/49, frontend typecheck 0
errors, frontend build 44 modules. **This session did not and could not
re-execute those** — they are reported here as the prior session's own
claim, not as independently reproduced this session. What this session did
independently verify by direct execution is the 114 tests above (77 + 37),
plus a full source read of every file named in this report.

## 7. Security findings

- No API key or other secret found in any event payload, SSE frame
  construction, or exception message on the `enrich_ioc`/`analyze_report`
  paths (traced through `virustotal.py`'s raise sites and
  `handlers.py`'s `_publish` call sites).
- `config/settings.json` in the shipped archive has an empty
  `virustotal_api_key`.
- `EventBroker` has no unbounded growth path: per-subscriber capacity is
  fixed at 32 with drop-oldest eviction; there is no global event history
  and no unbounded subscriber count enforced structurally (any number of
  subscribers may connect, each bounded individually — consistent with a
  loopback-only, single-user sidecar, not a public multi-tenant server).
- `export_report`'s `output_path` is accepted as a plain string with no
  path-traversal restriction, mirroring the existing GUI's own
  file-dialog-driven export behavior exactly (`MainWindow._export_report`).
  This is consistent with the project's trust boundary (a loopback-only
  sidecar serving one local, already-trusted user/process — see
  `docs/security/ipc-security-model.md` — not an internet-facing upload
  target), not a newly-introduced gap.
- Error translation is centralized (`app/application/errors.py`,
  MRO-walking `code_for_exception`) so internal exception details do not
  reach the API envelope beyond `str(exception)`; no raw stack trace is
  serialized into a response.

## 8. Dependency-direction / architecture findings

No circular imports, no duplicate dispatch/registration logic, no
GUI/FastAPI/Tauri coupling inside `app/application/`. Domain objects
(`Investigation`) never cross the command boundary directly — every
response DTO is built by an explicit mapping function.

## 9. Documentation reconciliation

`docs/architecture/IMPLEMENTATION_STATUS.md` and
`docs/architecture/CURRENT_STATE.md` each already carry a dated addendum
(added in the prior remediation session, confirmed present and accurate by
this session's own read) correcting every claim this audit's instructions
named as a current-state risk: the 10/10 command count, SSE
implemented-not-stubbed, the frontend and `src-tauri` directories'
existence, and the event model being implemented rather than merely
designed. Both addenda end with the same explicit line:
**"IMPLEMENTATION COMPLETE. NOT YET FROZEN."** — accurate as of the end of
the prior session, and now superseded by this document. No further
documentation edits were required or made this session.

## 10. Known limitations carried into freeze

- `EventBroker.shutdown()` not wired to process shutdown (§3) — accepted,
  non-blocking.
- `src-tauri` compilation remains unverified in every session of this
  project to date, including this one, due to an external Rust
  toolchain/MSRV mismatch, not a source defect (§5).
- Items explicitly out of Phase 4D's scope and unchanged by this audit:
  `ThreatIntelProvider`/`VirusTotalProvider` abstraction (Phase 4C, already
  separately frozen per `docs/phase4/PHASE4C_FREEZE.md`), database migration
  runner, OS-backed secret storage, HTML exporter refactor, PySide6
  retirement.
- This session could not independently reproduce the prior session's
  600/154/49-test non-GUI/GUI/Rust numbers or the frontend
  typecheck/build results (§6) due to sandbox network/toolchain
  restrictions; they are recorded here as reported, not re-verified.

## 11. Freeze decision

**CLASS B — FREEZE READY WITH DOCUMENTED ENVIRONMENT BLOCKER.**

Source architecture is internally consistent with the approved SSE decision
document; all 10 commands are implemented and verified end-to-end for the
portion of the test matrix this sandbox could execute (114/114 passing,
0 failures); no critical or high-severity defect was found in
application-layer, event, SSE-transport, frontend, or Tauri-bridge source
during this session's adversarial read. The only unresolved verification
gaps (`src-tauri` compilation, the wider `pytest`/GUI/frontend-build suites)
are attributable entirely to this sandbox's missing Rust toolchain and lack
of network access to install Python/Node dependencies — not to anything
found wrong in the source — and were already flagged as an equivalent
external blocker by the prior session under a different, older toolchain
version. No unverified functionality is being represented as verified: §6
above states plainly which numbers this session executed directly (114) and
which are carried forward from a prior session's own report (the rest).

**Statement:** No functionality in this document is represented as
runtime-verified in this session beyond what §6 lists as PASS. Everything
else is either direct source inspection or an explicitly-labeled
prior-session claim.
