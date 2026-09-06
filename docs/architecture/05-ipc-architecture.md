# IPC Architecture

**Status:** Documentation Foundation (Phase 4A). Describes the chosen, not-yet-implemented,
communication mechanism between the frontend/Tauri layer and the Python backend.
**Related:** Master Plan §2.2 (full evaluation and rationale), ADR-006, and
`docs/contracts/ipc-rules.md`, `docs/contracts/command-model.md`.

## CURRENT STATE

No IPC exists today because there is no process boundary — PySide6 GUI code calls Python
domain modules in-process, in the same interpreter (CONFIRMED, Master Plan §1.1). The CLI
(`app/cli.py`) is the only existing example of an *alternate entrypoint* into the same domain
core, and it too is in-process, not IPC-based.

## TARGET STATE (PROPOSED — ADR-006)

**Decision:** a local, loopback-only HTTP + Server-Sent-Events service, launched and
supervised by Tauri as a sidecar process.

**Options considered and rejected** (full reasoning: Master Plan §2.2):

| Option | Verdict |
|---|---|
| Rust FFI directly into a Python runtime | Rejected — couples the native/security boundary to a scripting runtime, makes Python packaging Rust's problem |
| stdio line-delimited JSON protocol | Rejected as primary — no free typed-schema tooling, harder to support concurrent streaming progress events, harder to debug independently |
| Named pipes | Rejected — platform-divergent implementation for no benefit over loopback TCP on a single-machine desktop app |
| **Local HTTP/SSE sidecar** | **Chosen** |

**Shape:**

- Tauri launches the Python sidecar bound to `127.0.0.1:<ephemeral-port>`; the port is chosen
  at startup and handed to the frontend via a Tauri command — never hard-coded.
- The port is loopback-only; the Tauri capability manifest denies the frontend any network
  capability except calling that single origin (see `docs/security/ipc-security-model.md`).
- Commands: `POST /commands/{name}` — JSON body, JSON response.
- Events: `GET /events` — a single SSE (or WebSocket) stream the frontend subscribes to once.
- Rust never calls Python domain logic directly. Rust's only involvement is process
  supervision (spawn/health-check/kill) and relaying the assigned port to the frontend — this
  is what keeps "Tauri must not become the business logic layer" true by construction, not by
  convention.

## MIGRATION NOTES

The sidecar is stood up in Phase 4D (Master Plan §26) against a throwaway test client, before
any Rust or React code exists (Phase 4E, 4F) — the IPC contract must be provably correct on
its own before anything is built to depend on it.

## UNKNOWN / REQUIRES VERIFICATION

Whether the eventual FastAPI process needs any OS-level sandboxing beyond loopback binding
(e.g., Windows Firewall scoping) is not yet decided and is not blocking Phase 4D — flagged
here as a future security-hardening question rather than an open architecture question.
