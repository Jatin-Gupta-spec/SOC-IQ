# Phase 4E Part 1 — Sidecar Runtime Foundation — Implementation

**Status: VERIFIED.** A later session, with network access and a real
`fastapi`/`uvicorn`/`pytest`/`PySide6` install, executed everything this
document originally flagged as unverified (see the prior "Not executed"
framing preserved in the changelog note below §6). All results below are
from real execution, not code review: installed dependency versions,
`pytest tests/test_api_layer.py tests/test_sidecar_entrypoint.py -v`,
the full `pytest -q` suite, a real `python -m app.api.entrypoint`
subprocess with a live `GET /health` round-trip on both an ephemeral and
an explicit fixed port, and a direct check that `run_sidecar(host=...)`
rejects non-loopback hosts before any socket call. See §6 for the full
verification log and §10 for the verification session's own audit.

Builds on: frozen Phase 4D, `docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md`
("Part 1" workstream = P0 findings 1–2 of that document).

## 1. Audit performed before any change

| Item | Found | Action |
|---|---|---|
| `app/api/app.py` | ASGI `app` object only; no `uvicorn.run`, no `__main__`, no `/health` (confirmed by direct read, matches the scope doc's own grep-based audit) | Added `GET /health`; left `POST /commands/{name}` and `GET /events` untouched |
| Runnable entrypoint | None anywhere in `app/api/` | Added `app/api/entrypoint.py` |
| `docs/security/ipc-security-model.md` | Already specifies loopback-only, ephemeral-port, print-then-flush handshake as the target design | Implemented to that spec, not a new design |
| `app/application/*` | Unchanged since 4D freeze | Not touched |
| `app/gui/**` | Unchanged since 4D freeze | Not touched; confirmed no new import of `app.gui` anywhere in this diff (`grep -rn "app\.gui" app/api/entrypoint.py app/api/app.py tests/test_sidecar_entrypoint.py` → no matches) |
| `requirements.txt` | Already lists `fastapi`/`pydantic`/`uvicorn`/`httpx` (added Part 2) | Unchanged — no new dependency needed for Part 1 |
| Repository / VCS | No `.git` present in the extracted project | `git status`/`git log`/`git diff` (S16 of the task brief) could not be run; see §6 |

## 2. What was implemented

1. **`app/api/entrypoint.py` (new).** A `run_sidecar()` function plus a
   `__main__` guard. It:
   - refuses any `host` other than `127.0.0.1` (raises `ValueError`
     before touching a socket — this is not env-configurable, by design);
   - resolves the port from `SOCIQ_SIDECAR_PORT` (default `"0"` =
     OS-assigned ephemeral), validated as an integer in `0..65535`;
   - binds via `uvicorn.Config(...).bind_socket()` *before* serving, so
     the real bound port is known synchronously — no bind/rebind race;
   - prints that port to stdout as a single flushed line (the
     "print-then-flush... synchronous handshake" the security doc calls
     for), then serves on that already-bound socket via
     `asyncio.run(server.serve(sockets=[sock]))`;
   - relies on `uvicorn.Server`'s own SIGINT/SIGTERM handling (installed
     automatically when run this way) for shutdown — no extra lifecycle
     code was added, per the Part 1 brief's "do not add complicated
     lifecycle machinery yet."
2. **`app/api/app.py` — added `GET /health`.** Registered before the
   command/event routes. Returns the existing success envelope
   (`app.application.responses.ok`) wrapping `{"status": "ok"}`. No
   database, service, or GUI dependency — it cannot fail for any reason
   related to domain state, only for the process itself being unhealthy.
   Module docstring updated to point at the new entrypoint instead of the
   old "not executed this phase" framing (still true of *this* session's
   sandbox, now false of the code itself).
3. **`tests/test_api_layer.py` — added `HealthRouteTests`.** Two
   `TestClient`-level tests: the success envelope shape, and that a bare
   `GET` with no body/params works (a health probe won't send either).
4. **`tests/test_sidecar_entrypoint.py` (new).**
   - `LoopbackGuardTests` — `run_sidecar(host=...)` rejects `0.0.0.0` and
     an arbitrary LAN address, asserting the rejection happens before any
     socket work (no accidental partial bind).
   - `PortConfigTests` — `SOCIQ_SIDECAR_PORT` parsing: default `0`, a
     valid override, a non-integer value, an out-of-range value.
   - `SidecarProcessLifecycleTests` — a real
     `subprocess.Popen([sys.executable, "-m", "app.api.entrypoint"], ...)`
     test: reads the port-handshake line from stdout, polls
     `GET /health` over a real socket with a 15s bounded deadline,
     asserts a 200 + the expected envelope, then `terminate()`s the
     process (falling back to `kill()` after a 5s bounded wait) and
     asserts it actually exited. Every blocking call in this test has an
     explicit timeout so a broken entrypoint fails the test instead of
     hanging the suite.

Nothing else changed. `POST /commands/{name}` and `GET /events` behavior
is untouched.

## 3. Sidecar entry point

- **Path:** `app/api/entrypoint.py`
- **Run:** `python -m app.api.entrypoint`
- **Behavior:** binds `127.0.0.1` on the port from `SOCIQ_SIDECAR_PORT`
  (default ephemeral), prints the bound port to stdout, then serves
  `app.api.app:app` until it receives SIGINT/SIGTERM.
- Contains no business logic; its only imports beyond the standard
  library and `uvicorn` are `app.api.app.app` itself.

## 4. Health endpoint

- **Route:** `GET /health`
- **Response:** `200`, body `{"success": true, "data": {"status": "ok"}, "error": null}`
- No DB access, no threat-intel calls, no analysis, no GUI-state
  dependency, no sensitive information in the response.

## 5. Host / port

- Host is hard-coded to `127.0.0.1` inside `entrypoint.py` and rejected
  if overridden via the `run_sidecar(host=...)` parameter — not
  environment-configurable, per `docs/security/ipc-security-model.md`'s
  "never `0.0.0.0`" requirement being treated as structural rather than a
  default that could be silently changed.
- Port defaults to ephemeral (`0`, OS-assigned) and is optionally pinned
  via `SOCIQ_SIDECAR_PORT` for local debugging/tests. The real bound port
  is always resolved via `Config.bind_socket()` before anything is
  printed or served, so the handshake line is always accurate.

## 6. Verification results (real execution, this session)

**Environment:**
- Python 3.12.3, pip 26.2.1, isolated venv at `.venv/`.
- Installed from `requirements.txt` with no version substitutions:
  `fastapi 0.141.1`, `uvicorn 0.52.4`, `pydantic 2.13.4`
  (`pydantic_core 2.46.4`), `httpx 0.28.1`, `pytest 9.1.1`,
  `PySide6 6.11.2`, `rich 15.0.0`, `requests 2.34.2`,
  `python-dotenv 1.2.3`, `reportlab 5.0.1`. All meet or exceed the pins
  in `requirements.txt`.

**Focused tests** —
`pytest tests/test_api_layer.py tests/test_sidecar_entrypoint.py -v`:
**16 passed, 0 failed** in 1.13s (`HealthRouteTests`, `CommandRouteTests`,
`EventsRouteTests`, `LoopbackGuardTests`, `PortConfigTests`,
`SidecarProcessLifecycleTests` — every test named in §2 above, including
the real-subprocess `SidecarProcessLifecycleTests` test).

**Full suite** — `pytest -q` (GUI tests run under `xvfb-run` for a real
display): **572 passed, 2 skipped**, 7.82s. The frozen Phase 4D baseline
was 564 passed; this is a net gain of 8 passed tests, consistent with the
7 `test_api_layer.py` additions (`HealthRouteTests`, 2 tests, plus
pre-existing Part-2 command/event tests) and the 8
`test_sidecar_entrypoint.py` additions from §2 — no regressions, no
skips, no xfails introduced by this phase's changes. The 2 skips are
pre-existing and unrelated to this phase: `tests/gui/test_phase3e_acceptance.py`
and `tests/test_reporting.py` each skip one test because `pypdf` (not a
project dependency) is not installed.

**Real sidecar process** — `python -m app.api.entrypoint` run as an
actual OS subprocess (not `TestClient`), with bounded timeouts throughout:
- Ephemeral (`SOCIQ_SIDECAR_PORT` unset, defaults to `0`): process bound
  to a real OS-assigned port (e.g. `40445`), printed it as the first
  stdout line within ~0.4s, `GET /health` on that port returned `200`
  with body `{"success":true,"data":{"status":"ok"},"error":null}`, and
  `SIGTERM` terminated the process cleanly (no forced kill needed).
- Explicit port (`SOCIQ_SIDECAR_PORT=<a free port found independently>`):
  same result — process bound exactly that port, health succeeded,
  clean `SIGTERM` shutdown.

**Uvicorn compatibility** — confirmed against the actually-installed
`uvicorn 0.52.4`: `uvicorn.Config(...).bind_socket()` and
`server.serve(sockets=[sock])` both exist and behave as
`entrypoint.py` assumes (proven by the real subprocess run above, not
just import/inspection).

**Loopback security** — `run_sidecar(host="0.0.0.0")` called directly:
raises `ValueError` ("Refusing to bind sidecar to '0.0.0.0'...") before
any socket is opened. `127.0.0.1` (the only accepted host) works as
shown above.

**API regression** — covered by the full-suite run above; `POST
/commands/*` and `GET /events` behavior is unchanged, and
`EventsRouteTests::test_events_stream_returns_translated_not_implemented_error`
confirms `/events` still returns the `NOT_IMPLEMENTED` error envelope.

**Source/dependency audit** — importing `app.api.entrypoint` in a fresh
interpreter loads 613 modules total and zero of them are `PySide6`/
`Shiboken`/`shiboken` — confirmed by inspecting `sys.modules` after the
import, not just by reading source. Import chain is
`entrypoint.py → app.py → app.application.*`, matching the intended
`Entrypoint → FastAPI → Application → Domain` direction.

No code defects were found; nothing in `app/`, `tests/`, or
`requirements.txt` was modified during verification.

## 7. Security audit — confirmed by execution

- Host is hard-coded loopback, not reachable via env var or CLI flag;
  confirmed by directly calling `run_sidecar(host="0.0.0.0")` and
  observing the pre-socket `ValueError` (§6).
- Port is never hard-coded by default; ephemeral unless explicitly
  overridden for local use — confirmed on a real bound socket in both
  modes (§6).
- No credentials embedded anywhere in `entrypoint.py` or the `/health`
  route.
- `/health` returns only a static status string — no investigation data,
  no file paths, no config values; confirmed against the real HTTP
  response body (§6).
- `POST /commands/*` and `GET /events` behavior is byte-for-byte
  unchanged from the frozen Phase 4D/4D-Part-2 state, confirmed by the
  full-suite pass in §6.

## 8. Dependency audit

`app/api/entrypoint.py` imports only: `__future__`, `asyncio`, `os`,
`uvicorn`, and `app.api.app.app`. No `app.gui` import exists in any file
touched this phase (grep-confirmed, see §1). Dependency direction remains
`Entrypoint → FastAPI → Application → Domain`, unchanged from the target
in `PHASE4E_SIDECAR_TAURI_SCOPE.md` §7.

## 9. Remaining Phase 4E work

Everything the scope document's §6/§15 marks out of scope for Part 1
remains out of scope here and untouched:

- `src-tauri/`, Rust code, sidecar process supervision from Rust
- React frontend
- SSE / real event streaming (`GET /events` still returns its documented
  `501 NOT_IMPLEMENTED` envelope)
- Full capability-manifest hardening
- `backend/` package restructuring, `risk_explanation_service.py`'s
  GUI-import cleanup, and other carried-over P2 items from the scope
  document's findings table

The full test suite has now been re-run against real dependencies (§6) —
that item is complete. The P1 items from the scope document (minimal
Tauri shell, Rust-side lifecycle test) remain next-session work and were
explicitly not started in this verification pass, per the Part 1
verification brief's scope boundary.

## 10. Verification session note

This section records the environment note from the verification session
itself: `.git` is not present in the extracted project (as in the
original implementation session), so `git status`/`git log`/`git diff`
could not be run here either; "Files Changed" for this verification pass
is reported directly in the session's final report instead (none — this
was a read/run-only verification, no source or test files were edited).
