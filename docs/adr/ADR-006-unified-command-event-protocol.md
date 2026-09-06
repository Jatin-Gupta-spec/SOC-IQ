# ADR-006: Local HTTP + SSE Sidecar as the Sole IPC Mechanism

**Status:** Proposed
**Related:** Master Plan §28, §2.2, §15, and `docs/architecture/05-ipc-architecture.md`,
`docs/architecture/06-event-architecture.md`.

## Context

The frontend (React, inside Tauri) needs to communicate with the Python domain core across a
process boundary that does not exist in the current in-process PySide6 architecture. Multiple
IPC mechanisms are technically viable.

## Problem

Choosing an IPC mechanism without an explicit evaluation risks picking one that is hard to
test, hard to debug, or platform-divergent, or that indirectly forces business logic into
Rust (e.g. an FFI approach would require Rust to hold a Python binding).

## Decision

A local, loopback-only (`127.0.0.1`) HTTP service with a Server-Sent-Events endpoint, run as
a Python sidecar process launched and supervised by Tauri. Commands are
`POST /commands/{name}`; events stream over a single `GET /events` subscription. Full
evaluation table: `docs/architecture/05-ipc-architecture.md`.

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Rust FFI into a Python runtime | Couples the native/security boundary to a scripting runtime; makes Python packaging Rust's problem |
| stdio line-delimited JSON | No free typed-schema tooling; harder to support concurrent streaming progress events; harder to debug independently of Tauri |
| Named pipes | Platform-divergent implementation (Windows named pipes vs. Unix domain sockets) for no benefit over loopback TCP on a single-machine desktop app |

## Rejected Alternatives (explicit)

A full REST-over-internet-exposed service (binding to `0.0.0.0`) — never seriously
considered; explicitly called out as a top security risk to avoid (Master Plan Top-10
security risks, #4: "local HTTP sidecar accidentally bound to `0.0.0.0` instead of
`127.0.0.1`").

## Consequences

- Positive: mature, independently testable Python web stack (FastAPI); debuggable with
  ordinary HTTP tooling during development; the same server can in principle serve
  CLI/automation use cases later without new protocol work.
- Negative: introduces a new process-supervision responsibility for Rust (health-checking,
  restart-on-crash) that the current in-process architecture never needed.

## Security Implications

Loopback-only binding is the primary mitigation keeping this local service from being
reachable off-machine; full detail and additional mitigations (command validation, no
frontend network capability) in `docs/security/ipc-security-model.md`.

## Migration Implications

This is the Phase 4D deliverable (Master Plan §26) and is built and contract-tested *before*
any Rust or React code exists, so the protocol is proven correct in isolation first.
