# Testing Architecture

**Status:** Documentation Foundation (Phase 4A). No test files have been modified as part of
this documentation pass, and no new tests have been written yet.
**Related:** Master Plan §20.

## CURRENT STATE (CONFIRMED)

542 Python tests, 542 passing, 0 failing, per the checkpoint baseline. Test files live under
`tests/` (top-level unit/integration tests) and `tests/gui/` (GUI-specific tests), with
fixtures under `tests/fixtures/`. This baseline is a hard constraint on every future phase —
no phase in the migration plan (`docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md`
§26) is permitted to leave it broken.

## TARGET STATE (PROPOSED)

| Layer | Approach |
|---|---|
| Python | Existing 542 tests preserved; new tests added for the provider abstraction (`08-threat-intelligence-architecture.md`), command handlers, and event publisher as those are built |
| Contract tests | Golden-file tests against the JSON schemas in `docs/contracts/`, so a backend change that breaks a frontend assumption fails CI before reaching the frontend |
| Rust | Unit tests for capability enforcement — a denied Tauri command must be provably denied, not just declared denied in a manifest |
| React/TypeScript | Component tests (e.g. Vitest/Testing Library) for view models and presentation logic; no business logic is expected to exist in the frontend to test in the first place |
| IPC/E2E | A small number of full-stack tests driving the real Tauri app against the real Python sidecar (not mocks) for the critical paths: analyze → view results → export |
| Security tests | Path-traversal attempts against the export command, malformed-command payloads against the API boundary, and a capability-manifest snapshot test so a future change can't silently widen Tauri permissions |

## MIGRATION NOTES

Each phase in the Master Plan's roadmap (§26) carries its own explicit exit criterion tied to
tests — e.g. Phase 4B: "542 tests still green; no behavior change"; Phase 4I: "backend
enforces options, verified by test"; Phase 4M: "security tests passing." Testing is not a
separate phase at the end; it is a gate on every phase.

## UNKNOWN / REQUIRES VERIFICATION

Whether any existing test currently exercises the interaction between the two current Qt
event buses (see `docs/architecture/06-event-architecture.md`) is **UNKNOWN — VERIFY IN
PHASE 4B**. If none exists, that gap should be closed with a regression test *before* the
buses are replaced, not treated as moot because the buses are being replaced anyway.
