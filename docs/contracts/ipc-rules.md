# IPC Rules

**Status:** Documentation Foundation (Phase 4A).
**Related:** `docs/architecture/05-ipc-architecture.md`, ADR-006,
`docs/security/ipc-security-model.md`.

## CURRENT STATE

No IPC boundary exists today (CONFIRMED — single in-process application, Master Plan §1.1).

## TARGET STATE (PROPOSED — hard rules, not guidelines)

1. All frontend-to-backend communication goes through the local HTTP+SSE sidecar
   (`docs/architecture/05-ipc-architecture.md`) — there is no secondary or fallback channel.
2. React never calls Python directly; it calls the sidecar's HTTP origin, which Tauri hands
   it at startup (dynamic port, never hard-coded).
3. Rust never calls into Python domain logic; Rust's only relationship to the sidecar is
   process supervision (spawn/health-check/kill) and relaying the assigned port.
4. Every command payload is validated against its schema (`command-model.md`) *before* it
   reaches any domain logic — malformed or unexpected payloads are rejected with
   `INVALID_COMMAND_PAYLOAD` (`error-model.md`), not best-effort parsed.
5. The event stream (`event-model.md`) is the sole mechanism for the backend to push
   information to the frontend proactively — there is no polling endpoint as a substitute.
6. The sidecar binds to `127.0.0.1` only, never `0.0.0.0` — named explicitly as a top
   security risk to avoid (Master Plan Top-10 security risks, #4).

## MIGRATION NOTES

These rules apply from the very first Phase 4D implementation and are structural — several
are enforced by the architecture itself (e.g. rule 3 has no code path violating it, per
ADR-006), not solely by developer discipline.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding.
