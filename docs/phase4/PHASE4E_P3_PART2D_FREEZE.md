# Phase 4E-P3 Part 2D — Freeze Record

**Status: COMPLETE / FROZEN**

This document is the consolidated freeze record for Part 2D
(checkpoints 2D-1 through 2D-4). It supersedes nothing —
`PHASE4E_P3_PART2D1_FRONTEND_LIFECYCLE_CONTRACT.md` and the sub-
checkpoint doc comments inside `frontend/src/shared/sidecar/*.ts`
remain the detailed record for their own layers; this document is
the top-level summary the 2D-4 audit produced.

## 1. Checkpoint chain

| Checkpoint | Delivered | Status |
|---|---|---|
| 2D-1 | `types.ts`, `validation.ts` — wire contract + runtime validators | Frozen |
| 2D-2 | `eventSubscription.ts` — real Tauri `listen()` ownership, sequence filtering | Frozen |
| 2D-3A | `projectionStore.ts` — the one authoritative projection container | Frozen |
| 2D-3B | `eventProjection.ts`, `projectionConnector.ts` — event → store wiring | Frozen |
| 2D-3C | `snapshotReconciliation.ts` — `get_sidecar_status` integration, race-safe reconciliation, startup/shutdown ordering | Frozen |
| 2D-3D | `finalIntegration.test.ts` — full real-chain hardening tests (async startup gap, full-chain multi-subscriber, combined shutdown, notification-storm, validation-boundary) | Frozen |
| 2D-4 | This freeze audit | Complete |

## 2. Final architecture

```
Tauri events (sidecar:state_changed / restart_scheduled / restart_exhausted)
     |
     v
SidecarEventSubscription        (2D-2 — sole listen() owner)
     |
     v
SidecarProjectionConnector      (2D-3B — sole event->store wiring)
     |
     v
SidecarProjectionStore          (2D-3A — the one authoritative projection)
     ^
     |
SidecarSnapshotReconciler       (2D-3C — owns startup ordering, dispose,
     |                             generation-guarded race safety)
     v
get_sidecar_status (Tauri command)
```

`SidecarSnapshotReconciler` (`snapshotReconciliation.ts`) is the
composition point: `initialize()` registers the connector
synchronously, then awaits `subscription.start()` before requesting a
snapshot, then reconciles it against the store's live state.

## 3. Verified backend contracts (source-read this checkpoint)

- `sidecar:state_changed` — `StateChangedPayload` (`src-tauri/src/events.rs`):
  `state`, `previous_state`, `reason: Option<StateChangeReason>`,
  `sequence: u64`, `generation: u32`, `timestamp: String`. Matches
  `types.ts` field-for-field.
- `sidecar:restart_scheduled` — `RestartScheduledPayload`: `attempt`,
  `delay_ms`, `sequence`, `timestamp`. Matches.
- `sidecar:restart_exhausted` — `RestartExhaustedPayload`: `attempts`,
  `code`, `sequence`, `timestamp`. Matches.
- `get_sidecar_status` (`src-tauri/src/lib.rs`) — returns `SidecarStatus`
  read from four independent locks (`process`, `scheduler`,
  `restart_tracker`, `events`), `sequence` via
  `EventSequencer::current_sequence()` (a peek, never an allocation).
  Matches `types.ts`/`snapshotReconciliation.ts`'s documented
  assumptions exactly.
- `LifecycleState` (`sidecar-core/src/state.rs`) — exactly 8 variants
  (`NotStarted`, `Starting`, `Running`, `Stopping`, `Stopped`, `Failed`,
  `Timeout`, `Crashed`); no `Restarting` variant exists anywhere in the
  backend. Matches `LIFECYCLE_STATES` in `types.ts`.
- `SidecarError::code()` (`sidecar-core/src/error.rs`) — exactly 9
  values. Matches `KNOWN_SIDECAR_ERROR_CODES` in `types.ts`.

Note: `state.rs` and `error.rs` physically live under
`sidecar-core/src/`, not `src-tauri/src/` — a path assumption in this
checkpoint's own task brief that source inspection corrected (§3's
"resolve documentation/source mismatch using source as authority").

Rust test execution (`cargo test`) was not possible in this
environment (no `cargo` toolchain available); backend correctness was
instead verified by direct source read against every frontend
assumption, and backend file integrity was verified by full-tree
SHA-256 comparison against the 2D-3D baseline (§6).

## 4. Sequence invariant

The frontend projection only ever advances according to a backend-
issued `sequence: u64`, and never regresses to an older accepted
value. Tested (via `reconcileSnapshot()`'s 8-case matrix and the
full-chain race tests in `snapshotReconciliation.test.ts` /
`finalIntegration.test.ts`):

- event 11 → snapshot 10 ⇒ final 11 (stale snapshot rejected)
- snapshot 10 → event 11 ⇒ final 11
- event 11 → event 12 → snapshot 10 ⇒ final 12
- event 10 → snapshot 11 ⇒ final 11 (newer snapshot applied)
- equal-sequence snapshot (documented decision): applied — corrects
  restart-accounting fields without moving `sequence` backwards

No frontend code allocates, regenerates, or reinterprets a sequence;
verified by source read of `eventSubscription.ts`,
`eventProjection.ts`, and `snapshotReconciliation.ts`.

## 5. Lifecycle invariant

Repeated `initialize()` while in flight or active returns the same
promise (no duplicate registration). `dispose()` is idempotent and
safe before `initialize()` has ever run. `initialize()` → `dispose()`
→ `initialize()` yields exactly one fresh active connection. A stale
async result from a superseded lifecycle (generation-guarded) cannot
mutate a newer lifecycle's state. All verified by
`snapshotReconciliation.test.ts`'s `lifecycle` suite and
`finalIntegration.test.ts`'s combined shutdown-safety pass.

## 6. Test results (this checkpoint, re-run against the actual project)

```
tsc --noEmit   : 0 errors
vitest run     : 8 test files, 204 tests passed, 0 failed, 0 skipped
npm run build  : success
```

Matches the Part 2D-3D baseline exactly (no regressions).

Backend integrity: `src-tauri/` and `sidecar-core/` are byte-for-byte
identical to the Part 2D-3D baseline (full-tree SHA-256 comparison,
28 files, 0 differences).

## 7. Findings

- **Informational / Deferred**: No application composition root calls
  `sidecarSnapshotReconciler.initialize()` yet. This is explicit,
  documented, intentional deferral —
  `PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md` states plainly
  that visual/status-bar integration belongs to **Phase 4G** (the
  navigation shell), a separate later phase, not Part 2D. This is
  Case 1 of the 2D-4 brief's own decision tree, not a scope conflict.
- **Informational**: The project has no `.git` repository, so
  `git status`/`git log` (requested by both 2D-3D's and 2D-4's task
  briefs) could not be run; file-level SHA-256 comparison against the
  prior checkpoint's archive was used instead.
- No duplicate authoritative sidecar state store found.
- No duplicate `listen()` owner found (`eventSubscription.ts` only).
- No duplicate `get_sidecar_status` caller found
  (`snapshotReconciliation.ts` only).
- No polling (`setInterval`/`setTimeout`) in the sidecar module.
- No unauthorized UI or backend changes.

No Critical, High, or Medium findings.

## 8. Deferred beyond Part 2D

- Wiring `sidecarSnapshotReconciler.initialize()` into an application
  composition root — Phase 4G (navigation shell).
- Any UI consumption of the projection (status bar, connection
  indicator, toast/banner on restart-exhausted) — Phase 4G.
- Snapshot polling, if ever required — a separate, not-yet-made
  architectural decision (not authorized by Part 2D).
