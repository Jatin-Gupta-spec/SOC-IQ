# PHASE 4D SSE — PART 4B IMPLEMENTATION: TAURI BRIDGE + SIDECAR ORIGIN INTEGRATION

**Status: PART 4B OF THE FINAL 3-PART SSE COMPLETION SEQUENCE. Phase 4D is
still NOT frozen** (freeze decision is explicitly out of scope for this
part too — see §9).

This implements the one item Part 4A's own doc left as "what remains for
Part 4B" (§14 there): a real `#[tauri::command]` exposing the sidecar's
origin, backed by the `SidecarProcess` adapter Phase 2A Part 2B already
built but nothing had ever driven. It does **not** touch the SSE
transport, the `EventBroker`, or any Python file.

---

## 1. Checkpoint verification

Performed before any edit, against the uploaded ZIP directly:

| Check | Result |
|---|---|
| `docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md`, Parts 1–3, Part 4A docs | All present, read in full |
| Part 4A's own checkpoint table | Matches this ZIP exactly — no discrepancy found, so no STOP condition applies |
| `app/application/*`, `EventBroker`, SSE transport, `useEventStream` | Present and unchanged from Part 4A's description (confirmed by diff, §8) |
| `src-tauri/src/lib.rs` | Empty shell — `mod sidecar;` declared, not called; no `#[tauri::command]`; matches Part 4A §4's finding exactly |
| `src-tauri/src/sidecar.rs` | Present, real process adapter (Phase 2A Part 2B), never driven by any caller in the running app |
| `frontend/src/shared/api/client.ts` | `getSidecarOrigin()` unconditionally `Promise.reject`s, exactly as Part 4A left it |
| `src-tauri/Cargo.toml` | `sidecar-core` path dependency present; no `@tauri-apps/api` on the frontend side yet |

No discrepancy from Part 4A's documented "what remains" list was found.
Proceeded directly to implementation.

---

## 2. Source audit before writing code

Read directly (not assumed) before any change, per this part's own
instructions:

- `src-tauri/src/main.rs`, `lib.rs`, `sidecar.rs`, `Cargo.toml`,
  `tauri.conf.json`, `capabilities/default.json`.
- `sidecar-core/src/lib.rs` (public API: `Supervisor`, `LifecycleState`,
  `TimeoutConfig`, `SidecarError`) — confirmed `Supervisor::default()`
  gives a 10s startup / 5s shutdown timeout, and `LifecycleState::Running`
  is only reached after `health_check_succeeded()`, i.e. after a real
  `GET /health` 200, not merely after the handshake line is read.
- `app/api/entrypoint.py` — confirmed the real handshake contract: a bare
  decimal port printed to stdout, flushed immediately, before uvicorn
  starts serving; loopback-only bind; `GET /health` requires no DB/domain
  dependency.
- `frontend/src/shared/api/client.ts`, `shared/events/eventSourceManager.ts`
  — confirmed the exact existing contract `getSidecarOrigin()` must keep:
  callers already treat rejection as a normal, retryable "not connected"
  state (a bare `.catch(() => { ... })` with no inspection of the error),
  so changing *why* it rejects requires no frontend caller changes beyond
  `client.ts` itself.
- `docs/contracts/ipc-rules.md`, `docs/security/tauri-capability-model.md`
  — rule 2 ("dynamic port, never hard-coded"), rule 3 (Rust's only
  relationship to the sidecar is process supervision + relaying the
  port), and the capability model's least-privilege / "widen only when a
  specific command needs a specific permission" convention.

**Conclusion:** the "existing sidecar-origin mechanism" this part's own
instructions (§3) say not to route around already exists —
`SidecarProcess` — but nothing in the running application ever
constructs or drives one. That gap, not a missing API design, is the
actual remaining work.

---

## 3. What was implemented

### 3.1 `src-tauri/src/lib.rs` (rewritten)

- Added `SidecarState(Mutex<SidecarProcess>)`, managed via
  `.manage(...)`.
- `run()` now: builds the `App` via `.setup(...)` + `.build(...)` (rather
  than `.run(context)` directly), so a `RunEvent::Exit` handler can be
  attached afterward.
- `.setup(...)` spawns a background **OS thread** (not the main/UI
  thread) that calls `SidecarProcess::start()` with a
  `SidecarLaunchConfig` whose `working_directory` is resolved from
  `CARGO_MANIFEST_DIR`'s parent (the project root — where
  `app/api/entrypoint.py` is importable from). Running on a background
  thread means the window opens immediately; it does not wait on the
  sidecar's startup handshake/health-poll sequence.
- Registered `#[tauri::command] get_sidecar_origin`, returning
  `http://127.0.0.1:{port}` only when `SidecarProcess::state() ==
  LifecycleState::Running` (i.e. after a real successful health check,
  not merely after the handshake is read) — never a hardcoded or
  placeholder origin. Uses `try_lock` (not `lock`) so this command never
  blocks the invoking call waiting for the (multi-second) startup
  sequence to finish; a lock contention or a not-yet-`Running` state both
  produce a fast rejection, matching the frontend's existing "reject =
  normal, retryable" contract.
- Added `app.run(|handle, event| ...)` calling
  `SidecarProcess::shutdown()` on `RunEvent::Exit`, so the process
  started by this part's own new code is never left orphaned. This is a
  direct, unavoidable consequence of actually starting the sidecar for
  the first time in this application's history, not additional feature
  scope — see §6 for why it was judged in-bounds.
- `sidecar.rs` and `sidecar-core` were **not modified**. `lib.rs` calls
  only their existing public API (`SidecarProcess::new/start/shutdown`,
  `Supervisor::default`, `LifecycleState`), exactly as Part 2B's own doc
  already anticipated a future caller would.

### 3.2 `src-tauri/capabilities/default.json`

Added the single named permission `get_sidecar_origin` to the
`permissions` array, per `docs/security/tauri-capability-model.md`'s own
rule ("widen this file only when a specific, implemented command
requires a specific, named permission"). No `shell:*`, `fs:*`, or
`http:*` plugin capability was added — `get_sidecar_origin` reads only
in-memory Rust state; the sidecar process itself is supervised via
`std::process`/`std::net` directly in `sidecar.rs`, not through any
Tauri plugin.

### 3.3 `frontend/src/shared/api/client.ts` (rewritten)

- `getSidecarOrigin()` now calls `isTauri()` (from
  `@tauri-apps/api/core`) first. If no Tauri runtime is present (plain
  browser tab, `vite dev` opened directly outside `cargo tauri dev`),
  it rejects with `SidecarNotConnectedError` — **preserving exactly the
  existing browser/dev behavior**, per this part's own instruction §2.3.
- If a Tauri runtime is present, it calls the real
  `invoke<string>("get_sidecar_origin")` and returns its result, or
  wraps any rejection (not-yet-`Running`, lock contention, etc.) in the
  same `SidecarNotConnectedError` shape callers already handle.
- `SidecarNotConnectedError`'s constructor now takes a `reason: string`
  so the message names what actually blocked resolution, instead of a
  single hardcoded message. Checked (`grep -rn`) that no other file
  constructs this error — the signature change is safe.
- `runCommand()` is unchanged (still intentionally unimplemented) — a
  typed command client is separate, later work per this part's own
  scope boundary (§2, "Do NOT implement unrelated Phase 4E
  functionality").

### 3.4 `frontend/package.json`

Added `@tauri-apps/api": "^2.1.0"` as a real dependency (previously
absent — confirmed by Part 4A's own audit, §4 there). No other
dependency was added.

---

## 4. Why the sidecar had to actually be started here

Part 4A's §14 "what remains" language — "backed by the port already
captured in `src-tauri/src/sidecar.rs`'s `SidecarProcess`" — presumes a
`SidecarProcess` is running somewhere. It wasn't: Part 2B's own doc
states plainly that "nothing in the running application constructs or
drives a `SidecarProcess` yet." A command that only reads a port that is
never captured would either have to return a permanent error (useless)
or fabricate a value (a hardcoded/placeholder origin — explicitly
forbidden by this part's own §3: "expose the actual running sidecar
origin rather than hardcoding a production URL"). Driving `start()`
from `run()` was therefore not optional scope creep but the minimum
required for `get_sidecar_origin` to ever return a real value — and is
still confined to calling `SidecarProcess`'s existing public API, adding
no new business logic to Rust (`NON_NEGOTIABLE_RULES.md` #2/#3
preserved).

---

## 5. Adversarial audit

| Check | Result |
|---|---|
| Hardcoded origin anywhere in the diff | **PASS** — `grep -n "localhost\|127.0.0.1\|http://"` on the 3 changed source files: the only match is an illustrative example inside a `client.ts` doc comment; the only executable literal `127.0.0.1` is in `lib.rs`'s `format!("http://127.0.0.1:{port}")`, which is not a hardcoded origin — `port` is a real, captured, per-run value, and `127.0.0.1` is the loopback-only bind address `ipc-rules.md` rule 6 and `entrypoint.py` already fix as non-configurable |
| Command returns before the sidecar is actually `Running` | **PASS** — checked against `LifecycleState::Running`, not against "port is `Some`" (which is set earlier, right after the handshake, before the health-check loop even starts) |
| Command blocks the invoking call during startup | **PASS** — `try_lock`, not `lock`; a held lock (startup thread mid-`start()`) is treated as "starting", not awaited |
| Orphaned sidecar process on app exit | **PASS** — `RunEvent::Exit` calls `SidecarProcess::shutdown()`, which (per `sidecar.rs`, unmodified) hard-kills and waits for confirmed exit before returning |
| Business logic added to Rust | **PASS** — `lib.rs` only calls `SidecarProcess`'s and `Supervisor`'s existing public methods; no new domain logic |
| `sidecar.rs` / `sidecar-core` modified | **PASS** — `diff -rq` against the pristine ZIP shows zero changes to either |
| `app/application/`, `app/api/`, any Python file modified | **PASS** — zero Python files in the diff (§8) |
| Frontend browser/dev behavior changed | **PASS** — `isTauri() === false` still rejects with the same error class/shape as before; `eventSourceManager.ts` needed no change |
| Second API client / second state system | **PASS** — `getSidecarOrigin` stays in the existing `client.ts`; `SidecarState` is the only new state, Tauri-managed, not a duplicate of anything |
| Capability over-grant | **PASS** — exactly one named permission added (`get_sidecar_origin`); no plugin `shell:*`/`fs:*`/`http:*` permission introduced |
| Secret logging | **PASS** — the only new log line (`eprintln!` on sidecar startup failure) logs the typed `SidecarError`'s `Display` message only (lifecycle/timeout/reason strings, no payload, no secret) |
| SSE/EventBroker/FastAPI transport touched | **PASS** — zero changes; confirmed by diff |

---

## 6. Verification — what was actually run

This environment has real network egress to `crates.io`/`registry.npmjs.org`/`pypi.org`
and both `cargo`/`rustc` (via `apt-get install cargo rustc`, giving
**1.75.0**) and `node`/`npm` are present — materially more than the
sandbox Parts 2B/4A had (no Rust toolchain at all, no npm registry
access). Verification below reflects what was **actually executed**,
not assumed.

| Check | Result |
|---|---|
| `cargo check` / `cargo test` — `sidecar-core` | **PASS, first real compilation of this crate in the project's history.** 49/49 tests green (13 lifecycle + 23 startup/handshake + 13 supervisor), reproduced identically before and after this part's changes (this part touched no file in `sidecar-core`) |
| `cargo check` — `src-tauri` (with this part's `lib.rs`/`capabilities` changes) | **BLOCKED — not a regression.** `tauri`'s dependency graph transitively requires `indexmap 2.14.0`, whose manifest needs Cargo's `edition2024` support, requiring cargo/rustc **≥1.85**. Reproduced the identical failure on the *pristine, unmodified* checkpoint before making any change, confirming this is a pre-existing toolchain-version gap (matching Part 2B's own finding: "sidecar-core needs ≥1.75; src-tauri's Tauri dependency graph needs ≥1.85"), not something introduced here. No newer rustc is available via `apt` on this image, and the network allowlist does not include `static.rust-lang.org`/`rustup.rs`, so no toolchain upgrade path exists in this sandbox |
| End-to-end handshake simulation (the exact sequence `SidecarProcess::start()` performs) | **PASS, real subprocess.** Ran `python3 -m app.api.entrypoint` directly from the resolved working directory: captured a bare decimal port on stdout (`40137` in this run), then `GET /health` on that port returned `HTTP 200` with `{"success":true,"data":{"status":"ok"},"error":null}`. This is the closest available substitute for compiling and running `src-tauri` itself, and confirms the real process this part's Rust code will spawn/poll actually behaves exactly as `sidecar.rs`'s adapter logic assumes |
| `npm install` (frontend) | **PASS, real install** — 73 packages, including the newly-added `@tauri-apps/api@2.1.0` (network egress to `registry.npmjs.org` succeeded, unlike Part 4A's blocked sandbox) |
| `npm run typecheck` (`tsc --noEmit`, real project `tsconfig.json`) | **PASS, zero errors** — a real full-project typecheck, not the stub-substitution static check Part 4A had to fall back to |
| `npm run build` (`tsc --noEmit && vite build`) | **PASS** — real production build succeeded, 44 modules transformed |
| `python -m pytest tests/ --ignore=tests/gui` | **PASS — 600 passed, 0 failed.** (`tests/gui` fails to *collect*, not to pass/fail, due to `PySide6` not being installed in this sandbox — pre-existing and unrelated to this part's scope; confirmed by the error being a `ModuleNotFoundError` at collection time, not a test failure) |
| `tests/test_api_layer.py` specifically (the SSE HTTP-boundary tests Part 4A could only read) | **PASS, 29/29, actually executed** — including `test_events_stream_is_no_longer_501`, `test_real_broker_event_reaches_the_http_stream`, `test_two_subscribers_receive_the_same_event_and_one_ending_does_not_affect_the_other`, all previously only read, never run |
| `tests/test_sidecar_entrypoint.py` | **PASS, 8/8** — including a real subprocess lifecycle test (`test_entrypoint_spawns_serves_health_and_terminates_cleanly`) |
| `tests.test_application_layer` + `tests.test_event_broker` | **PASS, 114/114**, unchanged from the documented baseline |
| Full-tree diff against the pristine uploaded ZIP | **PASS** — exactly 5 files changed (`src-tauri/src/lib.rs`, `src-tauri/capabilities/default.json`, `frontend/src/shared/api/client.ts`, `frontend/package.json`, `frontend/package-lock.json`) plus `src-tauri/Cargo.lock` (see §7) |

**No Rust unit test for the new `lib.rs` code was added or run** — the
MSRV blocker above means nothing in `src-tauri` compiles in this
sandbox, so a test file would be exactly as unverified as the code
itself; per this project's established practice (Part 2B §5), a test on
top of never-compiled code is not real verification and was not added
to create a false impression of one. `get_sidecar_origin`'s logic
(state check, `try_lock`, format string) was reviewed by hand against
`sidecar-core`'s and `sidecar.rs`'s actual public APIs (§2), not against
assumption.

---

## 7. Incidental fix: stale `Cargo.lock`

While attempting `cargo check`, cargo updated `src-tauri/Cargo.lock` to
add the `sidecar-core` package entry (and its dependency edge) before
failing later on the unrelated `indexmap`/MSRV problem. The pristine
checkpoint's `Cargo.lock` predates Part 2B's `sidecar-core` path
dependency entirely — a gap Part 2B's own doc already flagged as
required future work ("`Cargo.lock` will also need to be
regenerated/updated"). This lockfile update is kept: it is strictly
more correct than the pristine state (the lockfile now actually
reflects `Cargo.toml`'s real dependency graph) and was a side effect of
real tooling, not a hand-edit.

---

## 8. Scope confirmation (full-tree diff)

```
$ diff -rq <pristine ZIP> <working tree> \
    --exclude=__pycache__ --exclude=.pytest_cache \
    --exclude=node_modules --exclude=target --exclude=dist \
    --exclude=Cargo.lock

Files .../frontend/package-lock.json differ   (npm install, new dependency)
Files .../frontend/package.json differ        (added @tauri-apps/api)
Files .../frontend/src/shared/api/client.ts differ  (§3.3)
Files .../src-tauri/capabilities/default.json differ (§3.2)
Files .../src-tauri/src/lib.rs differ          (§3.1)
```

(`Cargo.lock` excluded from this listing only because it was diffed and
explained separately in §7.) No file under `app/application/`,
`app/api/`, `app/gui/`, `src-tauri/src/sidecar.rs`, or `sidecar-core/`
appears — the SSE transport, `EventBroker`, and sidecar-core adapter
this part was explicitly told not to touch are untouched.

---

## 9. Known limitations

1. **`src-tauri` has still never been compiled**, in this session or any
   prior one (Part 2B's same finding). The Rust code in §3.1 is
   source-complete and hand-reviewed against the real `sidecar-core`/
   `sidecar.rs` APIs, and its target process was verified end-to-end via
   direct subprocess execution (§6), but `cargo check`/`cargo build` on
   `src-tauri` itself remains blocked purely by toolchain version, not
   by anything this part could resolve from inside this sandbox.
   **Required before this can be called frozen:** run `cargo check` /
   `cargo test` for `src-tauri` on a machine with cargo/rustc ≥1.85.
2. **Production packaging is unresolved.** `resolve_working_directory()`
   uses `CARGO_MANIFEST_DIR` at compile time, which is correct for a
   source checkout / `cargo tauri dev` layout (the only layout this
   project has) but not for a bundled installer, which would need a
   different resource-path strategy and likely a bundled Python
   interpreter. Desktop packaging remains explicitly out of scope per
   `docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md`'s own non-goals, not
   solved or worked around here.
3. **`python_executable` defaults to `"python"`** (`SidecarLaunchConfig::default()`,
   unchanged from Part 2B). This sandbox's own `python3 -m
   app.api.entrypoint` simulation in §6 used `python3` explicitly to
   prove the entrypoint contract; a real dev machine without a `python`
   alias pointing at a Python 3 interpreter with `requirements.txt`
   installed would need one, or `SidecarLaunchConfig.python_executable`
   overridden. This is an existing Part 2B default, not something
   changed here, and is noted rather than silently worked around.
4. **The Part 3-documented `EventBroker.shutdown()` → FastAPI lifecycle
   gap** (Part 4A §14) remains open — out of this part's scope, not
   addressed here.
5. **No automated Rust test exists yet for `get_sidecar_origin` or the
   new `run()` wiring** — see §6 for why one was not fabricated against
   uncompiled code.

---

## 10. What remains before Phase 4D can be frozen

- Compile and test `src-tauri` on a machine with Rust ≥1.85 (§9.1);
  fix anything that fails.
- A genuine end-to-end run: `cargo tauri dev`, confirm the window opens,
  `getSidecarOrigin()` resolves to a real origin once the sidecar
  reaches `Running`, and `EventSource` on `/events` receives real
  `analysis.*`/`ti.enrichment.*` frames during an actual analysis —
  this part could not perform this because `src-tauri` cannot be built
  here.
- Resolve production packaging (§9.2) if desktop distribution is in
  scope for the next phase.
- Decide on `EventBroker.shutdown()` → FastAPI lifecycle wiring
  (carried over from Part 3/4A).
- Final Phase 4D audit and freeze decision.

---

## 11. Freeze status

**PHASE 4D NOT FROZEN.** This part completed the Tauri bridge's source
code and every check available without a compiling `src-tauri` build —
real `sidecar-core` compilation and tests, a real end-to-end subprocess
simulation of the exact sequence `SidecarProcess::start()` performs, a
real frontend `npm install`/typecheck/build, and the full Python suite
(600/600, including the 29 SSE tests Part 4A could only read). It did
not, and could not in this sandbox, compile `src-tauri` itself — that
remains the one explicit precondition for calling Phase 4D frozen (§10).

---

## 12. Independent re-verification (this session, "audit first" pass)

This session received the FULL PROJECT ZIP containing this checkpoint
and was instructed to audit before trusting this document's own claims.
Every claim above was independently re-run from source, not assumed:

| Check | Re-run result |
|---|---|
| Source audit of `lib.rs`, `sidecar.rs`, `client.ts`, `capabilities/default.json`, `Cargo.toml`, `tauri.conf.json` | Read directly; matches §3's description exactly — one `#[tauri::command]`, one `generate_handler!` registration, one caller (`eventSourceManager.ts`), no hardcoded origin, no duplicate command, no `.catch()` that fabricates a default origin (the one `.catch()` in `eventSourceManager.ts` only sets status to `"unavailable"`, never a substitute URL) |
| Repo-wide grep for `127.0.0.1`/`localhost`/`tauri::command`/`generate_handler`/`getSidecarOrigin`/`invoke(` | Re-run fresh in this session; same findings as §5/§8 |
| `app/application/*.py`, `app/api/*.py` import audit (no Tauri/PySide6/FastAPI-in-application-layer) | Re-run fresh; clean |
| `sidecar-core`: `cargo test` (installed cargo/rustc 1.75.0 via `apt-get install cargo rustc` in this sandbox) | 49/49 passed (23 startup + 13 supervisor + 13 lifecycle-adjacent), matching §6 exactly |
| `src-tauri`: `cargo check` | Reproduced the same MSRV block independently — a transitive dependency (`icu_properties_data` in this run, vs. `indexmap` as named in §6; same root cause) requires the unstable `edition2024` Cargo feature, unsupported on cargo 1.75. Confirms §6/§9.1's finding was not sandbox-specific fabrication |
| `python -m unittest tests.test_application_layer` / `tests.test_event_broker` | 77 + 37 = 114/114, matches baseline |
| `pytest tests/ --ignore=tests/gui` | 600 passed, matches §6 exactly |
| `pytest tests/test_api_layer.py` (SSE HTTP boundary) | 29/29 passed, matches §6 exactly, including `test_events_stream_is_no_longer_501` and `test_real_broker_event_reaches_the_http_stream` |
| `pytest tests/test_sidecar_entrypoint.py` | 8/8 passed, matches §6 exactly |
| `pytest tests/gui` | **154/154 passed** in this session (PySide6 was installable here via `requirements.txt`) — an improvement on §6's "blocked at collection" finding, not a contradiction; still outside this part's own file scope, so no GUI file was touched either way |
| `npm install` / `npm run typecheck` / `npm run build` (frontend) | Real install (73 packages incl. `@tauri-apps/api@2.1.0`), zero typecheck errors, production build succeeded (44 modules) — matches §6 |

**Verdict: the Part 4B bridge, as it exists in this uploaded checkpoint,
is architecturally correct and matches every claim this document made
before this session touched anything.** No implementation was required
or performed this session — per this part's own task rule ("if the
Part 4B bridge is already correct: do not rewrite it, run verification
and produce an audit report"). No source file was modified. The one
still-open precondition for a freeze decision remains unchanged from
§10: compiling `src-tauri` itself needs cargo/rustc ≥1.85, unavailable
in every sandbox this checkpoint has been audited in so far.

**PHASE 4D REMAINS NOT FROZEN.**
