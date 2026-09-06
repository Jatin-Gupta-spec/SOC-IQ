# Phase 4E — Sidecar Runtime & Tauri Shell Foundation

**Status:** PROPOSED (architecture/scope definition only — no implementation this document).
**Builds on:** Frozen Phase 4D (`docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md`,
`docs/phase4/PHASE4D_PART2_IMPLEMENTATION.md`), git checkpoint `c1a7f04`.
**Master-plan anchor:** `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md`
§26 already names Phase 4E "Rust/Tauri foundation... Empty Tauri shell that can launch the 4D
sidecar and hit one command... Sidecar lifecycle (spawn/health/kill) proven." This document
does not override that label — it verifies it against the actual frozen 4D state and finds one
real prerequisite gap the master plan's phase table did not surface (§3).

---

## 1. Executive Summary

Phase 4D delivered and froze a command/response/error contract (`app/application/`) and proved
a FastAPI transport (`app/api/app.py`) actually runs, via `TestClient`. It did **not** prove the
transport runs as a standalone, spawnable OS process with a real bound socket — no
`uvicorn.run(...)` call exists anywhere in source. The master plan's Phase 4E goal (a Tauri
shell that spawns the sidecar, health-checks it, and hits one command) is **not yet buildable
against current source**, because there is nothing for Tauri to spawn: `app/api/app.py`
exports an ASGI `app` object, not a runnable program.

**Phase 4E, as scoped here, is two things:**
1. A small, additive Python-side workstream that makes the existing, frozen `app/api/app.py`
   spawnable as a real process (ephemeral port, loopback bind, health endpoint) — closing a gap
   the IPC security model already assumed was closed ("Established in Phase 4D") but wasn't.
2. The master plan's original Tauri-shell workstream: a minimal `src-tauri/` that spawns that
   process, waits for health, invokes one existing command, and kills it cleanly.

Everything else in the master plan's later phases (React frontend, capability-manifest
hardening, GUI retirement, `backend/` package restructuring) is explicitly **out of scope** here
— see §5.

## 2. Current-State Audit (re-verified this session, evidence-based)

| Area | Verified state |
|---|---|
| `app/application/*` | Complete, frozen, 15 tests green (Part 1A/1B) |
| `app/api/app.py` | Complete for 3 commands, runs under `TestClient`; **no `uvicorn.run`, no `__main__`, no health endpoint** — confirmed absent by direct grep |
| `GET /events` | Returns a translated `501 NOT_IMPLEMENTED` envelope (Part 2 fix); still no live event producer |
| `analyze_report` sync/async | Still unresolved — synchronous, full result returned inline; explicitly not decided in 4D |
| Dependency direction (API→Application→Domain, no GUI coupling) | Clean, re-verified by import grep this session |
| `app/services/risk_explanation_service.py` → `app.gui.*` | Still present. Per `docs/architecture/PHASE4B_ARCHITECTURAL_FINDINGS.md` this was flagged to be "resolved before or during Phase 4C" — it was not, in either 4C (design-only) or 4D. It is a **carried-over, overdue** item, not a new one. Confirmed by grep this session: it does not intersect `app/application/` or `app/api/`, so it does not block anything in this document's scope. |
| `src-tauri/`, `frontend/` | Confirmed absent — nothing built yet |
| `backend/` package restructuring (master plan §25 assumed this existed by 4B) | Deliberately deferred by Phase 4D §5.1 ("its own phase... once the API/event contract proven here is stable"). Now unblocked, but **not required** for Phase 4E — Tauri spawns a process by command line, not by Python package path. |
| Two Qt event buses (`app/gui/events/*`) | Untouched, as intended — GUI retirement is master-plan Phase 4O, far later |
| `docs/architecture/IMPLEMENTATION_STATUS.md` | Stale: still says FastAPI transport is "BLOCKED (in this sandbox)" and does not reflect the Part 2/freeze proof. Not corrected in this document per the "audit only, do not touch Phase 4D" instruction — flagged here as a documentation debt for whoever next updates it. |
| Test baseline | **564 passed, 0 failed, 0 skipped** (re-run this session, matches frozen figure exactly) |

## 3. The Real Post-4D Gap (why Phase 4E can't start with Rust yet)

`docs/security/ipc-security-model.md` states the loopback-bind, ephemeral-port, health-checkable
sidecar contract is "Established in Phase 4D." `PHASE4D_API_EVENT_ARCHITECTURE.md` §14 itself
already flags the opposite, plainly: *"this phase's code has no `uvicorn.run(...)` call... the
actual bind-address enforcement is UNKNOWN/unverified in running code."* This session's re-audit
confirms §14 is still accurate — nothing added it since.

This matters concretely for Phase 4E: the master plan's stated exit criterion is "sidecar
lifecycle (spawn/health/kill) proven." Rust cannot spawn, health-check, or kill a process that
has no entrypoint, no bound port, and no health route. **This is a P0 finding** — not a new
architectural layer, just the one missing piece between "a FastAPI app object that passes
`TestClient` tests" and "a thing an external process supervisor can manage."

## 4. Findings — Prioritized

### P0 — Must Fix (blocks Phase 4E's own exit criteria)
1. **No runnable sidecar entrypoint.** `app/api/app.py` needs a `__main__`/launcher path that
   calls `uvicorn.run(app, host="127.0.0.1", port=<ephemeral>)`, per
   `docs/security/ipc-security-model.md`'s already-approved design (ephemeral port, loopback
   only, port handed to the frontend via a Tauri command — not hard-coded).
2. **No health endpoint.** Tauri's "spawn/health/kill" contract needs something to poll
   (e.g. `GET /health` returning a trivial `{"status": "ok"}`) that doesn't depend on any
   database or domain state — a pure liveness check, separate from the `/commands/*` surface.

### P1 — Should Fix (during Phase 4E, not blocking, but same-phase-appropriate)
3. **Minimal Tauri shell** (`src-tauri/`) — spawn the sidecar (via the entrypoint from P0-1),
   poll `/health` until ready or timeout, invoke exactly one existing read-only command
   (`list_investigations` is the safest choice — no side effects, already proven), then kill the
   process on shell exit. This is the master plan's literal Phase 4E deliverable.
4. **Process-lifecycle test coverage** — an integration test (Rust-side, or a scripted
   spawn/poll/kill smoke test) proving the sidecar starts, responds, and terminates cleanly; not
   a Python unit test, since nothing Python-side changes behaviorally beyond P0.

### P2 — Later (valid, but explicitly not Phase 4E)
5. `risk_explanation_service.py`'s GUI backward-dependency — real, overdue relative to its own
   original Phase 4C deadline, but doesn't intersect anything Phase 4E touches. Belongs to
   whichever phase does the `backend/` package move (§4.1 of the master plan) or GUI retirement
   prep — not this one.
6. `backend/` package restructuring — unblocked now that 4D is frozen, but not required for a
   Tauri shell to spawn a process by command line. Its own phase, as Phase 4D's own doc already
   proposed.
7. Full Tauri capability-manifest hardening (master plan Phase 4M) — premature before any
   capability is even requested.
8. React frontend (master plan Phase 4F onward) — has no dependency on Phase 4E finishing first
   at the architecture level, but sequenced after per the roadmap; not started here.
9. Resolving the `analyze_report` sync/async decision — not needed to prove sidecar lifecycle
   against a read-only command; remains deferred to whichever phase implements real SSE/streaming
   (master plan Phase 4I territory).
10. `docs/architecture/IMPLEMENTATION_STATUS.md` staleness (§2) — a documentation fix, not an
    architecture change; flagged, not corrected here.

## 5. Phase 4E Goals

- Make the already-frozen `app/api/app.py` runnable as a standalone OS process, loopback-only,
  ephemeral port (P0).
- Add a liveness `/health` route with no domain dependencies (P0).
- Stand up a minimal `src-tauri/` shell able to spawn, health-poll, invoke one command against,
  and cleanly kill that process (P1).
- Prove this end-to-end with an automated lifecycle test (P1).

## 6. Non-Goals (explicit, to prevent scope creep)

- No React/TypeScript frontend code (`frontend/`) — master plan Phase 4F+.
- No Tauri capability-manifest hardening beyond the minimum needed to spawn a sidecar and make
  one HTTP call to `127.0.0.1` — full least-privilege manifest is Phase 4M.
- No new application commands beyond the 3 already frozen.
- No SSE/event-streaming implementation — still deferred.
- No resolution of the `analyze_report` sync/async question.
- No `backend/` package restructuring.
- No changes to `app/gui/**`, the two Qt event buses, or any GUI-facing behavior.
- No fix to `risk_explanation_service.py`'s GUI import.
- No modification to `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md` or
  `PHASE4D_PART2_IMPLEMENTATION.md`.

## 7. Target Architecture

```
Current (post-4D freeze)                  Phase 4E changes                    Target (post-4E)
─────────────────────────                 ─────────────────                   ────────────────
app/api/app.py                            + launcher: uvicorn.run(            app/api/app.py
  FastAPI() object only,                    app, host="127.0.0.1",              + runnable entrypoint
  importable, TestClient-only               port=<ephemeral>)                  + GET /health route
  no /health route                        + GET /health route (P0)             (still 3 commands only,
                                                                                 still no SSE)

(nothing)                        ──────►  src-tauri/  (new, minimal)     ──►   src-tauri/
                                             - spawn sidecar subprocess          - spawns Python sidecar
                                             - poll /health until ready          - reads ephemeral port
                                             - call one command                   from stdout/stdin
                                               (list_investigations)             handshake (not hard-coded)
                                             - kill on shell exit                - health-checks it
                                                                                  - proves one command works
                                                                                  - clean shutdown

app/application/*                         UNCHANGED                          app/application/*
app/gui/**                                UNCHANGED                          app/gui/**
tests/ (564 passed)                       + new Rust/lifecycle tests         tests/ (564 Python,
                                                                                unchanged) + new
                                                                                Rust-side lifecycle proof
```

Dependency direction remains: `Tauri (Rust) → spawns → Python sidecar process (API → Application
→ Domain)`. Rust never imports or calls into Python domain logic directly (ADR-004, ADR-006) —
it only manages the process and speaks HTTP to it, exactly as already decided and not reopened
here.

## 8. Migration Strategy (staged, no big-bang)

| Stage | Current | Transitional | Target |
|---|---|---|---|
| 1 | `app/api/app.py` has no entrypoint | Add a `run_sidecar()`/`__main__` function that binds an OS-assigned ephemeral port (`port=0`) and prints/exposes it for the parent process to read | Sidecar is launchable via a single command, port never hard-coded |
| 2 | No health route | Add `GET /health` returning a static payload, registered before any other route, with no DB/service dependency | Tauri can poll liveness independent of domain state |
| 3 | No `src-tauri/` | Scaffold minimal Tauri app; Rust side spawns the Stage-1 entrypoint as a child process and captures its reported port | Tauri owns the process lifecycle |
| 4 | N/A | Rust polls `/health` with a bounded timeout/backoff before declaring the sidecar "ready" | Deterministic startup, no race between UI actions and an unready sidecar |
| 5 | N/A | Rust calls `POST /commands/list_investigations` once, logs/displays the raw response | One proven, real Rust→HTTP→Application→Domain round trip |
| 6 | N/A | Rust terminates the child process on app exit (and on abnormal exit, best-effort) | No orphaned sidecar processes left running |

What stays untouched throughout: `app/application/*`, `app/gui/**`, the two Qt event buses, the
3 existing commands' behavior, all 564 existing tests. What gets added (never migrated/replaced):
the entrypoint + health route (additive to `app/api/app.py`) and the new `src-tauri/` tree.
Nothing is deprecated or removed in this phase.

## 9. Test Strategy

- **Regression:** full existing suite must stay green — 564 passed, 0 failed, 0 skipped, checked
  before and after.
- **New Python-side test:** a lightweight test (e.g. via `subprocess` + polling, or
  `uvicorn`'s test utilities) that starts the sidecar entrypoint on an ephemeral port and hits
  `GET /health`, confirming Stage 1–2 work without needing Rust yet.
- **New Rust-side lifecycle test:** spawn → wait-for-health → one command call → kill, asserting
  clean process exit and no leaked handles. This is the master plan's literal "sidecar lifecycle
  proven" criterion.
- **Architecture/import test (optional but recommended):** a static check (grep-based, matching
  the pattern already used in this and prior phases' audits) that `src-tauri/`'s Rust code never
  references Python domain modules directly, and that `app/application/`, `app/gui/` remain
  untouched by this phase's diff.

## 10. Risks

1. **Process-lifecycle bugs** (zombie/orphaned sidecar processes on crash) — master-plan top
   risk #1; mitigate with a bounded startup timeout and explicit kill-on-exit/kill-on-panic
   handling in Rust.
2. **Port-handoff race** — if the ephemeral port isn't communicated reliably (e.g. a stdout race
   before Rust starts reading), Tauri could poll the wrong/no port. Mitigate by using a
   synchronous handshake (print-then-flush, or a small handshake file/pipe) before Rust proceeds
   to health-polling.
3. **Scope creep into capability hardening** — easy to over-build the Tauri manifest "while
   we're in there." Mitigate by treating §6's non-goals as a hard boundary for this phase's PR
   review.
4. **False sense that 4D's sidecar was already "done"** — this document exists specifically
   because `docs/security/ipc-security-model.md` asserts the runtime contract was "Established in
   Phase 4D" when it wasn't executed. Future phases should treat status claims in older docs as
   claims to re-verify, not facts, consistent with this project's own established audit practice.

## 11. Deferred Work (explicitly outside Phase 4E)

- React/TypeScript frontend (master plan 4F+).
- Full Tauri capability manifest / least-privilege hardening (4M).
- SSE/live event streaming; `analyze_report` sync/async resolution.
- `backend/` package restructuring.
- `risk_explanation_service.py` GUI-dependency cleanup.
- Any new application commands (`get_iocs`, `enrich_ioc`, etc.).
- Correcting `docs/architecture/IMPLEMENTATION_STATUS.md`'s stale FastAPI status.

## 12. Acceptance Criteria (objective, measurable)

Phase 4E is complete when **all** of the following hold:

1. `app/api/app.py` (or a new thin launcher module alongside it) can be started as a standalone
   process that binds to `127.0.0.1` on an OS-assigned ephemeral port — verified by a passing
   automated test, not manual inspection.
2. `GET /health` returns a 200 with no database/service dependency, verified by the same test.
3. `src-tauri/` exists, compiles, and its lifecycle test passes: spawn → health-ready → one
   successful `POST /commands/list_investigations` call → clean process termination.
4. The full existing Python suite still reports **564 passed, 0 failed, 0 skipped** — zero
   regressions.
5. `grep`-verified: no Rust source references Python modules directly; no file under
   `app/application/`, `app/gui/`, or `app/database/` was modified by this phase's diff.
6. No new application command, no SSE implementation, and no `backend/` restructuring appears in
   the phase's diff (non-goals §6 held).
7. A `PHASE4E_*` completion document records the exact before/after test counts and the
   spawn/health/kill proof, mirroring this project's existing per-phase reporting convention.

## 13. Implementation Stages (summary, maps to §8)

1. Sidecar entrypoint + ephemeral port binding (P0).
2. `/health` route (P0).
3. Minimal `src-tauri/` scaffold with process spawn.
4. Health-poll handshake.
5. One command round-trip (`list_investigations`).
6. Clean shutdown + lifecycle test.
7. Full regression + Phase 4E completion report.

---

**This document is a scope/architecture proposal only. No code in `app/`, `tests/`, or
`docs/phase4/PHASE4D_*` was modified to produce it — verified by `git status` showing a clean
tree against the frozen `c1a7f04` checkpoint (§2).**
