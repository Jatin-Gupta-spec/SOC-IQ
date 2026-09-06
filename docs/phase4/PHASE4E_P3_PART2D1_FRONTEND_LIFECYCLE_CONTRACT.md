# Phase 4E-P3 Part 2D-1 — Frontend Lifecycle Contract, Types & Runtime Validation

## 1. Scope

This checkpoint (1 of 4 for Part 2D) implements exactly the frontend
contract layer for the already-frozen backend lifecycle architecture:
TypeScript types mirroring the Rust event payloads and
`get_sidecar_status` response, plus runtime validators for each. It
implements no event subscription, no projection store, no
reconciliation, and no UI — those are Parts 2D-2 and 2D-3
respectively, per the task brief.

## 2. Backend contract audited

Read directly, not assumed from prior documentation:

- `src-tauri/src/events.rs` — `EVENT_STATE_CHANGED`,
  `EVENT_RESTART_SCHEDULED`, `EVENT_RESTART_EXHAUSTED`,
  `StateChangeReason`, `StateChangedPayload`,
  `RestartScheduledPayload`, `RestartExhaustedPayload`,
  `SidecarStatus`, `EventSequencer`.
- `src-tauri/src/lib.rs` — the `get_sidecar_status` command body (read
  vs. mutation confirmation) and `SidecarState`'s field set.
- `sidecar-core/src/state.rs` — `LifecycleState`'s `Display` impl, the
  exact 8 wire strings.
- `sidecar-core/src/error.rs` — `SidecarError::code()`'s 9 values.
- `docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md` and
  `PHASE4E_P3_PART2C_RESTART_EVENTS_STATUS_SNAPSHOT_AUDIT.md` — cross-
  checked against, not substituted for, the source above.

**Hard-stop check (task brief §3):** all four required contract
items — `sidecar:state_changed`, `sidecar:restart_scheduled`,
`sidecar:restart_exhausted`, `get_sidecar_status` — are present and
match the architecture doc's description exactly. No stop condition
was triggered; no backend change was made or needed.

None of the four Rust structs this checkpoint mirrors carry a
`#[serde(rename...)]`/`#[serde(rename_all...)]` attribute (confirmed
by direct grep), so serde's default (verbatim Rust field name) is
what actually crosses the wire — every frontend field name below is
the backend's own snake_case name, unchanged, matching the convention
`frontend/src/shared/api/types.ts` already established for the
command contract.

## 3. Frontend types

New location: `frontend/src/shared/sidecar/` (`types.ts`,
`validation.ts`, `validation.test.ts`). No existing directory served
this purpose — `frontend/src/shared/events/` is the pre-existing
Phase 4D SSE contract (`analysis.*`/`ti.enrichment.*`, a Python-
backend HTTP event stream, unrelated to Tauri's `sidecar:*` events —
confirmed by reading its `types.ts`, which documents its own,
different wire producer). `frontend/src/shared/api/` is the Tauri
command-invoke contract, a different transport (`POST /commands/*`
via `runCommand`), not the event-emission contract this checkpoint
covers. A new sibling directory under `shared/` follows the project's
existing `shared/<concern>/` convention rather than overloading either.

## 4. Lifecycle states

`LIFECYCLE_STATES` — the 8 backend states verbatim (`NOT_STARTED`,
`STARTING`, `RUNNING`, `CRASHED`, `STOPPING`, `STOPPED`, `FAILED`,
`TIMEOUT`), transcribed from `LifecycleState`'s `Display` impl. No
`RESTARTING` or other frontend-only state was added.

## 5. Event names

`EVENT_STATE_CHANGED`, `EVENT_RESTART_SCHEDULED`,
`EVENT_RESTART_EXHAUSTED` — string-literal constants matching
`events.rs`'s own constants byte-for-byte, plus a closed
`SIDECAR_EVENT_NAMES` array/`SidecarEventName` union so a future
subscriber (Part 2D-2) has one canonical source instead of scattering
raw strings. No competing spelling (`sidecar:restarting`,
`sidecar:recovered`, `sidecar:started`, `sidecar:crashed`) was
introduced.

## 6. Payload shapes

`StateChangedPayload`, `RestartScheduledPayload`,
`RestartExhaustedPayload`, and `SidecarStatus` — each a direct,
field-for-field transcription of its Rust counterpart, with a
per-field doc table (field / Rust type / required / meaning / backend
source) in `types.ts`'s doc comments, per task brief §7's
requirement. `Option<T>` fields (`StateChangedPayload.reason`,
`SidecarStatus.restart_pending_attempt`) are typed `T | null`
(serde_json's actual `Option::None -> null` encoding), not `T |
undefined` — Tauri IPC payloads cross JSON, which has no
`undefined`. All Rust `u32`/`u64` fields are typed `number` (JSON has
one numeric type). Every interface field is `readonly` (task brief
§20: prevent accidental mutation of a received snapshot).

`StateChangeReason.code` and `RestartExhaustedPayload.code` remain
typed `string`, not a closed union — `SidecarError::code()` returns
`&'static str` from a `match`, not a serialized Rust enum, so a
closed frontend union would assert a stronger contract than the
backend actually gives. `KNOWN_SIDECAR_ERROR_CODES` is provided
separately as documentation of the 9 current values, not as the
field's type.

## 7. Runtime validation

`validation.ts` implements `isStateChangedPayload`,
`isRestartScheduledPayload`, `isRestartExhaustedPayload`, and
`isSidecarStatus` as small, pure, hand-written type predicates — no
schema-validation library was added. Each composes from shared
primitives: `isPlainObject`, `isNonNegativeInteger` (finite, integral,
`>= 0` — the actual constraint a Rust unsigned integer implies over
JSON), `isLifecycleState` (membership in the 8-state list), and
`isBackendTimestamp` (structural match against the exact RFC 3339
UTC-seconds shape `events.rs::format_rfc3339` produces, plus a
calendar-validity round-trip check, e.g. rejecting
`"2026-02-30T00:00:00Z"`).

Two fields get a domain-specific lower bound beyond "non-negative
integer", both traced to the Rust types that produce them rather than
invented: `RestartScheduledPayload.attempt` and
`RestartExhaustedPayload.attempts` must be `>= 1`
(`RestartTracker::decide`'s `self.attempts + 1`/`Exhausted{attempts}`
construction never produces `0`), and `SidecarStatus.
restart_pending_attempt`, when non-null, follows the same `>= 1` rule
for the same reason.

## 8. Error handling boundary

Validators return `false` on any malformed input; none throw. This
lets a future subscriber (Part 2D-2) implement `receive -> validate ->
valid: process / invalid: reject + diagnostic` without wrapping the
validation call itself in `try`/`catch`. No frontend lifecycle error
code was invented; the existing `code`/`message` shape
(`StateChangeReason`) is represented as-is, unexpanded, per task
brief §17. `SidecarNotConnectedError` (`shared/api/client.ts`) was not
touched.

## 9. Sequence semantics

`sequence: number` is carried through unchanged on every payload type
as an opaque ordering value — never regenerated, reinterpreted as a
timestamp, reset locally, or turned into a render counter (task brief
§18). The backend's `EventSequencer` remains the sole authority; this
checkpoint adds no sequence-comparison or dedup logic at all (that is
Part 2D-2's job).

## 10. Immutability

Every payload/status interface field is declared `readonly`, matching
the project's existing TypeScript conventions
(`strictPropertyInitialization`/`exactOptionalPropertyTypes` already
enabled in `tsconfig.json`). No mutation helper was added.

## 11. Tests

`validation.test.ts` — 47 focused unit tests via the project's
existing Vitest setup (no new test framework added), covering:
all 8 valid lifecycle states accepted, `RESTARTING`/random
string/empty string rejected; valid/missing-field/invalid-field cases
for `StateChangedPayload` (including malformed and calendar-invalid
timestamps, and a malformed nested `reason`); the same shape of
coverage for `RestartScheduledPayload` and `RestartExhaustedPayload`
(including the 1-based `attempt`/`attempts` lower bound); and
`SidecarStatus` (pending-restart and exhausted snapshots accepted,
each field's invalid case rejected). No existing test was modified or
deleted.

### Executed

```
npm install         — 114 packages, 0 errors
npx tsc --noEmit     — 0 errors (whole frontend/src tree)
npx vitest run       — 2 test files, 57 tests, 0 failures
                        (47 new + the pre-existing 10 in
                        shared/api/client.test.ts — unmodified,
                        confirmed still passing, no regression)
npm run build        — tsc --noEmit && vite build: 44 modules
                        transformed, built successfully
```

All four commands were actually run in this session, not assumed.
`node_modules/` and `dist/` were deleted after verification — build
artifacts, not source, and not part of the frozen baseline's file
inventory.

### Static / manual

- Field-by-field cross-reference of every TypeScript interface against
  the actual current Rust struct definitions (§2).
- Confirmation (grep) that no Rust struct mirrored here carries a
  `#[serde(rename...)]` attribute, validating the "preserve snake_case
  verbatim" decision in §2 rather than assuming it.

## 12. Security considerations

No secret, PID, process handle, launch argument, environment
variable, or OS internal is represented in any type here — this
mirrors the backend's own payloads, which already exclude all of
those (Part 2C's audit, §H of that report). No new dependency was
added, so no new supply-chain surface was introduced. Runtime
validation exists specifically so a compromised or buggy sidecar
process emitting malformed IPC data cannot silently corrupt whatever
frontend state consumes it in Part 2D-2/2D-3 — validated input is the
only thing that boundary will ever accept.

## 13. Files changed

```
Production frontend files added:    2  (types.ts, validation.ts)
Production frontend files modified: 0
Backend production files modified:  0
Tests added:                        1  (validation.test.ts, 47 tests)
Documentation added:                1  (this file)
```

Confirmed by direct diff against the frozen Part 2C archive: `diff -rq`
across `src-tauri/` and `sidecar-core/` (excluding this session's own
`sidecar-core/target/` build cache) reports zero differences; the only
change under `frontend/` is the new `frontend/src/shared/sidecar/`
directory. `frontend/package-lock.json` is byte-identical to the Part
2C baseline — `npm install` did not rewrite it.

## 14. Deferred Part 2D-2/2D-3 work

Explicitly not implemented in this checkpoint, per task brief §13/§14/§15:

- **Part 2D-2**: event subscription — `listen()` ownership, listener
  deduplication, cleanup on unmount, sequence-based drop/dedup
  filtering.
- **Part 2D-3**: snapshot reconciliation and the projection store
  (`useSidecarStatus()` or equivalent) that Part 2D-2's subscriber and
  a future `get_sidecar_status` call will feed.
- **Part 2D-4** (per the task brief's own final report template):
  integration audit + freeze across all of Part 2D.
- No UI (status cards, badges, notifications, restart banners,
  dialogs, animations, dashboard integration) exists yet.

## 15. Limitations

- No live Tauri runtime/webview was exercised in this session — `npm
  run build`/`vitest run` confirm the code compiles and the pure
  validator logic behaves correctly, but do not confirm an actual
  `sidecar:*` event payload from a running backend deserializes and
  validates successfully end-to-end. That end-to-end path is
  necessarily Part 2D-2's concern (it owns the actual `listen()`
  call).
- `src-tauri`/`sidecar-core` were not rebuilt in this session (no
  backend change was made, so no rebuild was required); their
  standing toolchain limitation (documented in the Part 2C report) is
  unchanged and irrelevant to this checkpoint's own verification,
  which is entirely frontend-side.
