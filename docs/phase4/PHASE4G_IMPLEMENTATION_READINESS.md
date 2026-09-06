# SOC-IQ — Phase 4G Implementation Readiness Audit

**Status:** Audit / planning checkpoint only. No production code changed.
**Baseline consumed:** Phase 4E Part 2D (frozen) — 204/204 tests, 0 tsc errors, build PASS, verified unchanged.

---

## A. Phase 4G objective

Per the authoritative Master Plan (§26 migration table), **Phase 4G = "Application shell"**:
building the frontend navigation shell (sidebar, routing, command-palette skeleton) as a
**navigable shell against mock domain data**. Real dashboard data is explicitly deferred to
4H.

Layered onto that, the frozen Part 2D checkpoint and the sidecar-lifecycle architecture
document assign Phase 4G one more concrete, already-scoped responsibility: **wiring the
already-built sidecar projection infrastructure into that shell** — composition-root call to
`sidecarSnapshotReconciler.initialize()`, and a status-bar/connection-indicator component
that consumes it. This is *not* part of the "mock data" scope — it's real/live from day one,
because the sidecar plumbing is infrastructure-level (not domain content) and already
complete and frozen.

## B. Authoritative scope — citations

- `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md`, §26 table, row
  `4G`: *"Application shell | frontend nav | Sidebar, routing, command palette skeleton |
  Navigable shell against mock data."*
- `docs/architecture/13-frontend-information-architecture.md`, Migration Notes: *"Navigation
  shell is Phase 4G (Master Plan §26), built against a mock-data version of the above
  structure before real dashboard data is wired in Phase 4H."* (This scopes the **eight
  domain nav destinations** — Dashboard, Analyze, Investigations, etc. — as mock in 4G, not
  the sidecar status.)
- `docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md`, §14 ("UI Ownership"):
  *"When Phase 4G's navigation shell lands, its status bar/connection-indicator component
  becomes a **consumer** of `useSidecarStatus()`."* §33 confirms building the shell itself
  was out of scope for that (earlier) document, but explicitly reserves the integration
  point for 4G.
- `docs/phase4/PHASE4E_P3_PART2D_FREEZE.md`, §7–§8: confirms, as of the frozen baseline, no
  composition root yet calls `sidecarSnapshotReconciler.initialize()`, and states this and
  all UI consumption (status bar, connection indicator, restart-exhausted toast/banner) are
  deferred to Phase 4G.
- `frontend/src/app/router.tsx` and `frontend/src/app/App.tsx` (source comments, both
  currently in the repo): independently confirm the same split — no router library, no
  nav chrome, no feature screens yet; explicitly reserved for 4G, citing the same IA doc.

**Discrepancy check (task §3):** the five documents named in the task brief
(`PHASE4_FRONTEND_ARCHITECTURE.md`, `SOC-IQ_PHASE4_FRONTEND_DESIGN_FINAL.md`,
`SOC-IQ_PHASE4_PART2_AUDIT.md`, `SOC-IQ_FRONTEND_FINAL_AUDIT.md`,
`PHASE4_PART1_ARCHITECTURE_AUDIT.md`) **do not exist anywhere in this project** (confirmed
by full-tree search). They appear to be stale references, not present in this repository.
This is reported per the task brief's own instruction rather than silently substituted. The
scope above is instead reconstructed from the documents that *do* exist and that are
internally consistent with each other (master plan + IA doc + sidecar-lifecycle doc +
Part 2D freeze doc). No hard stop is raised on this alone, since a coherent, cross-confirmed
scope was recoverable from real files — but this should be corrected before 4G execution
begins, in case the missing docs contain constraints not captured here.

## C. Current architecture (as found in the repository)

```
frontend/src/
├── main.tsx              → createRoot(...).render(<App/>)
├── app/
│   ├── App.tsx            composition root: ErrorBoundary > ThemeProvider > AppRoutes
│   ├── router.tsx          AppRoutes() — placeholder <main>, NO router library installed
│   └── providers/
│       ├── ErrorBoundary.tsx
│       └── ThemeProvider.tsx
├── shared/
│   ├── api/               client.ts (sidecar origin resolution), types.ts
│   ├── events/             eventSourceManager.ts (domain SSE singleton, ref-counted),
│   │                       useEventStream.ts, useEventStreamStatus.ts, types.ts
│   ├── sidecar/            FROZEN Part 2D — types, validation, eventSubscription,
│   │                       eventProjection, projectionConnector, projectionStore,
│   │                       snapshotReconciliation (+ 8 test files, 204 tests)
│   ├── hooks/useReducedMotion.ts
│   └── styles/tokens/*     color, duration, easing, elevation, opacity, radius,
│                           spacing, typography — all already established
└── styles/{globals,motion,tokens}.css
```

There is **no** `pages/`, `components/`, `shell/`, or `application/` directory yet — these
do not exist in the repo (contrary to what the task brief's §4 asks me to assume might be
there). `frontend/src/app/` is the only composition-root candidate, and it is intentionally
minimal today.

## D. Composition-root location

**`frontend/src/app/App.tsx`** is the composition root. It currently wraps
`ErrorBoundary > ThemeProvider > AppRoutes`. This is where a new provider (or a direct
`useEffect`-driven call, depending on the pattern chosen in 4G-1) should own the
`sidecarSnapshotReconciler.initialize()` / `.dispose()` lifecycle, once the shell is built.
`main.tsx` should not own it directly — it only mounts `<App/>`; lifecycle ownership
belongs one level in, consistent with how `ErrorBoundary`/`ThemeProvider` are already scoped.

No dependency-injection container exists (confirmed — no `container.ts`, no service
locator, no context-based DI framework). The existing pattern is **module-level
singletons** (`sidecarProjection`, `sidecarSnapshotReconciler`, `eventSourceManager`'s
internal `source`), each exposing plain functions/classes, consumed via hooks. Phase 4G
should follow this same pattern rather than introducing a container.

## E. Sidecar ownership (frozen, confirmed by source read)

| Module | Owns | Lifecycle |
|---|---|---|
| `eventSubscription.ts` | the single Tauri `listen()` registration for sidecar events | `SidecarEventSubscription` class; not yet initialized anywhere |
| `projectionConnector.ts` | translates events → projection writes | wired internally to the subscription |
| `projectionStore.ts` | current `SidecarProjectionState`, notify-on-change | `sidecarProjection` singleton |
| `snapshotReconciliation.ts` | `get_sidecar_status` reconciliation, generation-guarded | `SidecarSnapshotReconciler` class, `sidecarSnapshotReconciler` singleton; `initialize()`/`dispose()` idempotent (verified in Part 2D-4) |

**Finding:** no React hook (`useSidecarStatus()`) exists yet. It is referenced only in a
source comment in `eventSubscription.ts` ("...turns a stream of `SidecarDomainEvent`s into a
`useSidecarStatus()`-...") as a forward reference to a not-yet-built consumer layer, and
described prescriptively in the architecture doc §14. **Building this hook is 4G's work, not
something Part 2D already delivered.** It should be a thin wrapper subscribing to
`sidecarProjection`, mirroring `useEventStreamStatus()`'s existing shape exactly (same
directory sibling pattern: `shared/sidecar/useSidecarStatus.ts`).

## F. UI consumer

No candidate component exists yet (no status bar, no shell chrome at all). Per the IA doc's
target nav structure and the sidecar architecture doc §14, the intended consumer is a
**status-bar / connection-indicator element inside the navigation shell itself** — i.e. the
same 4G deliverable that creates the shell also creates this element, rather than a
pre-existing component being retrofitted. No separate "dashboard widget" or "settings page"
placement is indicated anywhere in the docs.

## G. State mapping (backend → UI)

From `PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md` §15 (UI Behavior Matrix, contract
only) and `types.ts`'s `LIFECYCLE_STATES`:

| Backend `LifecycleState` | UI-facing meaning (contract, not styling) |
|---|---|
| `NotStarted` | Idle — no sidecar-dependent UI marked unavailable yet |
| `Starting` | Non-error "starting up" affordance |
| `Running` (healthy) | No lifecycle-specific chrome; sidecar-dependent features enabled |
| *(restart-scheduled / restart-exhausted)* | Surfaced via the dedicated `sidecar:restart_scheduled` / `sidecar:restart_exhausted` events, not as a status enum value |

**Confirmed:** there is no `RESTARTING` lifecycle state in the frozen contract, and Phase 4G
must not invent one (task §18 hard constraint) — restart status is derived from the existing
`RestartScheduledPayload` fields already defined in `types.ts`, not a new enum member.

## H. Error behavior

- **Startup:** if `sidecarSnapshotReconciler.initialize()` fails or the reconciliation
  promise rejects, existing project convention (`ErrorBoundary.tsx`, already in the
  composition root) is the closest analog, but sidecar startup failure is not a React
  render-time error — it's async. Recommendation for 4G-1: initialization failure sets the
  projection to a degraded/unknown state (already representable — `SidecarProjectionState`
  is `SidecarStatus | null`) rather than throwing past the boundary; the shell continues to
  render, degraded, consistent with "the application continues" being the only pattern
  established elsewhere in this codebase (no existing global fatal-error takeover exists to
  reuse).
- **Runtime:** already handled — `finalIntegration.test.ts` and the store's own
  subscriber-isolation tests (§5/§6 of the Part 2D freeze doc) confirm a throwing subscriber
  cannot corrupt the store or block other subscribers. Nothing new needed here.
- **Snapshot correction:** already implemented and frozen (`reconcileSnapshot`,
  generation-guarded against stale async results).
- **Shutdown:** `dispose()` is already idempotent per Part 2D-4; 4G only needs to call it
  from the composition root's own teardown path (there isn't an established
  app-shutdown hook yet in `App.tsx` — this is a small, real gap to close in 4G-1, not
  something to invent a new architecture for).

## I. Event flow (steady state)

```
Tauri (Rust sidecar process)
  → SidecarEventSubscription.listen()      [frozen, unowned by any composition root today]
  → SidecarProjectionConnector.handleEvent
  → SidecarProjectionStore.applyProjectedState / notify()
  → useSidecarStatus() hook                 [NOT YET BUILT — 4G deliverable]
  → status-bar / connection-indicator UI    [NOT YET BUILT — 4G deliverable]
```

## J. Snapshot flow

```
App composition root mount
  → sidecarSnapshotReconciler.initialize()  [NOT YET CALLED ANYWHERE — 4G deliverable]
  → get_sidecar_status (Tauri command)
  → reconcileSnapshot() [generation-guarded against a stale async result]
  → SidecarProjectionStore.applyProjectedState
  → same UI consumer as the event flow above
```

## K. Lifecycle

```
startup:  App mounts → composition root calls initialize() once
           → subscription attaches → snapshot reconciles → store populated
active:    events flow in continuously; store stays current; UI re-renders on notify()
shutdown:  composition root's teardown (new — does not exist yet) calls dispose()
           → idempotent, safe even if initialize() never resolved
```

## L. Motion/interaction plan

Existing primitives to reuse (already present, do not duplicate):
`styles/tokens/duration.ts`, `easing.ts`, `elevation.ts`, `opacity.ts` +
`styles/motion.css` + `shared/hooks/useReducedMotion.ts`.

Where motion is warranted in 4G, per the task's own restart-exhausted requirement (§17) and
external research below: a state-change transition on the status indicator (e.g. opacity/
color transition, respecting `useReducedMotion`), and an appear/disappear transition for the
restart-exhausted toast/banner if one is built as part of 4G. No new token categories appear
necessary — the existing duration/easing/opacity sets are sufficient for a subtle,
non-intrusive transition; this should be confirmed against the actual token *values* (not
just categories) during 4G-4, not assumed here.

## M. Web research

| Source | Observed | Relevance | Adapt | Do not copy |
|---|---|---|---|---|
| VS Code Status Bar UX guidelines (code.visualstudio.com) | Two-zone status bar (workspace-level items left, contextual items right); progress uses a loading icon inline, only escalates to a full notification if it needs user attention | Directly analogous to a desktop-shell connection indicator that must stay unobtrusive most of the time | Keep the sidecar indicator as a quiet, always-present icon/label; only escalate to a toast for restart-exhausted (a genuinely actionable state), not for ordinary starting/healthy transitions | Don't copy VS Code's literal two-column layout — SOC-IQ's shell layout is defined by the IA doc, not this |
| Slack connection-issue reporting (slack.com/help + third-party writeups) | A distinction is drawn between a static "Connecting..." (blocked) and a flickering "Reconnecting..." (unstable, retrying) — different visual treatment for each | Directly applicable to `Starting` vs. a restart-in-progress state derived from `RestartScheduledPayload` | Use distinct (but token-driven, not new-color) visual treatment for "first start" vs "recovering from a crash," derived from existing payload fields, not a new lifecycle enum (task §18 forbids that) | Don't copy Slack's specific copy/wording or its full troubleshooting-menu pattern — out of scope for a status indicator |

Given the scope of this checkpoint (planning only), this research is intentionally limited
to validating the *shape* of the interaction (quiet indicator + escalate only for actionable
failure) rather than producing final visual specs, which is 4G-4's job.

## N. Files expected to change (in Phase 4G)

- `frontend/src/shared/sidecar/useSidecarStatus.ts` — **new**, thin hook wrapper (does not
  exist yet, despite being referenced in a comment)
- `frontend/src/shared/sidecar/useSidecarStatus.test.ts` — **new**
- `frontend/src/app/App.tsx` — **modified**, add initialize()/dispose() lifecycle ownership
- `frontend/src/app/router.tsx` — **modified**, add real router library + route table (per
  IA doc's eight destinations) once 4G-1/4G-2 land
- `frontend/src/pages/*`, `frontend/src/shell/*` or similar — **new**, shell chrome
  (sidebar, status bar / connection indicator, command palette skeleton) — exact directory
  naming to be decided in 4G-1, none exists today
- `frontend/package.json` — **modified**, add a router dependency (none installed today)
- `docs/phase4/PHASE4G_*` implementation/freeze docs — **new**, per this project's own
  checkpoint-naming convention (`PHASE4_CHECKPOINT_NAMING.md`)

## O. Files that MUST NOT change

- `src-tauri/` — no backend changes authorized by this checkpoint
- `sidecar-core/` — no backend changes authorized by this checkpoint
- `frontend/src/shared/sidecar/types.ts`, `validation.ts`, `eventSubscription.ts`,
  `eventProjection.ts`, `projectionConnector.ts`, `projectionStore.ts`,
  `snapshotReconciliation.ts`, and their existing test files — frozen Part 2D
  infrastructure; consume, do not modify, unless a source-level defect is discovered (none
  was found during this audit)

## P. Implementation sequence (proposed, derived from the artifacts above — not assumed)

1. **4G-1 — Composition-root wiring:** add router dependency; wire
   `sidecarSnapshotReconciler.initialize()`/`.dispose()` into `App.tsx`'s mount/unmount;
   build `useSidecarStatus()`.
2. **4G-2 — Navigation shell (mock data):** sidebar + eight routes from the IA doc, routed
   against mock domain data, per Master Plan's own exit criteria for this phase.
3. **4G-3 — Status projection consumer:** status-bar/connection-indicator component
   consuming `useSidecarStatus()` — real, not mocked.
4. **4G-4 — Restart-exhausted notification + motion:** toast/banner per task §17's
   trigger/severity/duplicate-suppression/accessibility requirements, using existing motion
   tokens.
5. **4G-5 — Command palette skeleton:** per Master Plan's 4G deliverable list.
6. **4G-6 — Integration tests + final audit/freeze.**

## Q. Risks

- **Missing source docs (§B):** five referenced documents don't exist in this repo; scope
  was reconstructed from what does exist and cross-confirmed, but should be verified with
  whoever authored the task brief before 4G-1 starts, in case those documents carried
  additional, uncaptured constraints.
- **No router chosen yet:** `router.tsx` deliberately avoided picking one; 4G-1 needs an
  explicit decision (react-router is the de facto default for this stack, but that's a
  4G-1 decision, not one this audit should make).
- **No established app-shutdown hook:** `App.tsx` has no teardown path today; `dispose()`
  needs somewhere real to be called from, which is a small but genuine gap, not automatically
  solved by "wire it into App.tsx."
- **Restart-exhausted UI has no home yet:** no toast/notification infrastructure exists in
  the frontend at all today (confirmed by file search) — 4G-4 is building this from
  scratch, not reusing an existing component, contrary to what task §10 assumes might be
  found.

## R. Hard stops

**None identified that block starting Phase 4G.** The one genuine ambiguity (§B — whether
4G's "mock data" scoping covers the sidecar status indicator) was resolved by direct source
citation (sidecar architecture doc §14/§33), not by assumption, and does not conflict with
the master-plan/IA-doc "mock data" language once "domain content" vs. "infra chrome" are
distinguished. The missing named documents (§B) are reported as a finding, not escalated to
a hard stop, since a coherent scope was independently recoverable.

## S. Definition of Done (for Phase 4G, not this checkpoint)

- [ ] Navigation shell renders all eight IA-doc destinations against mock data, 1440×900
      dashboard-adjacent layout constraints respected where applicable
- [ ] `useSidecarStatus()` hook exists, tested, mirrors `useEventStreamStatus()`'s shape
- [ ] `sidecarSnapshotReconciler.initialize()`/`dispose()` owned by `App.tsx`'s lifecycle,
      idempotency re-verified in an integration test
- [ ] Status-bar/connection-indicator shows live (not mocked) sidecar state
- [ ] Restart-exhausted toast/banner implemented per task §17's full behavior list
- [ ] No new lifecycle enum values invented; no duplicate event bus; no duplicate
      snapshot-store
- [ ] `src-tauri/`, `sidecar-core/`, and frozen Part 2D sidecar files byte-identical to this
      checkpoint's baseline
- [ ] `tsc --noEmit` 0 errors, `vitest run` all passing (baseline 204 + new 4G tests),
      `npm run build` succeeds

---

## Implementation record — Phase 4G Part 1 (Composition Root + Sidecar Lifecycle Integration)

**Status:** COMPLETE.

### Actual composition root

`frontend/src/app/App.tsx`. A `useEffect(() => {...}, [])` calls
`startSidecarLifecycle()` on mount and its returned `stop()` on unmount — the
sole owner of the sidecar lifecycle's startup/shutdown, exactly as planned in
§D/§E above.

### Actual lifecycle owner

`frontend/src/app/sidecarLifecycle.ts` — a new, deliberately non-React plain
function (`startSidecarLifecycle(reconciler = sidecarSnapshotReconciler)`),
not a hook or provider component. It adds no lifecycle state of its own: it
calls the frozen `SidecarSnapshotReconciler`'s already-idempotent
`initialize()`/`dispose()` exactly once each, and additionally subscribes to
the reconciler's existing `onDiagnostic()` channel to log a
`snapshot_fetch_failed` diagnostic to `console.error` (the project's
established error-logging convention, per `ErrorBoundary.tsx`) — using the
frozen reconciler's own existing error-reporting seam rather than inventing a
new one, since `initialize()` itself never rejects for a documented snapshot
failure (see `SidecarReconciliationOutcome`'s doc comment).

**Deviation from the readiness document:** §D/§N of the readiness document
listed building `useSidecarStatus()` as part of 4G-1. This implementation
does not build it. Rationale: this checkpoint's own task brief (§12) is
explicit that no UI-consumption work happens yet, and a hook with no
consumer would be dead code — it is deferred to the checkpoint that actually
builds the status-bar/connection-indicator consumer, where it can be
written and tested against a real usage site instead of speculatively now.

### Actual startup sequence

```
App mounts
  → useEffect runs once (empty dependency array)
  → startSidecarLifecycle(sidecarSnapshotReconciler)
      → subscribes to reconciler.onDiagnostic() (this module's own, new)
      → reconciler.initialize()             [frozen, Part 2D-3C]
          → connector.initialize()           [frozen, Part 2D-3B, synchronous]
          → subscription.start()             [frozen, Part 2D-2, real Tauri listen()]
          → fetchStatus() / get_sidecar_status
          → reconcileSnapshot() + store.applyProjectedState()  [frozen, Part 2D-3A/3C]
  → returns { stop } to the effect's cleanup slot
```

### Actual shutdown sequence

```
App unmounts (or effect re-runs — it never will, given the empty
dependency array, but the cleanup path is identical either way)
  → stop()
      → unsubscribes this module's own diagnostic listener
      → reconciler.dispose()                [frozen, Part 2D-3C, idempotent]
          → connector.dispose()              [frozen, Part 2D-3B — unsubscribes
                                               its own onEvent() registration only;
                                               does NOT stop the underlying Tauri
                                               listen() — that remains
                                               SidecarEventSubscription's own,
                                               separate, unowned-by-this-checkpoint
                                               lifecycle, exactly per
                                               projectionConnector.ts's documented
                                               ownership boundary]
```

This last point is worth stating plainly since it is easy to assume
otherwise: calling `stop()` does **not** tear down the raw Tauri event
registration. It tears down the *projection* — the connector stops
forwarding events into the store, and a fresh `initialize()` afterward
re-establishes a clean, single, non-duplicated forwarding path. This is the
frozen Part 2D-3B design, not something this checkpoint changed or worked
around.

### Async-race / duplicate-initialization behavior

Verified directly (not assumed) via the new integration test suite,
reusing the real frozen classes with only the two external boundaries
(Tauri `listen()`, `get_sidecar_status`) faked — the same harness pattern
`shared/sidecar/finalIntegration.test.ts` already established:

- Calling `startSidecarLifecycle()` twice over the *same* reconciler
  instance does not double-register any Tauri listener (Test B).
- Disposing while `initialize()` is still in flight discards the pending
  snapshot as superseded — the store is never mutated by it (Test D),
  exercising the frozen reconciler's own generation guard end-to-end
  through this new composition-root entry point rather than only at the
  reconciler's own unit-test layer.
- `initialize()` → `dispose()` → `initialize()` again (Test E) yields
  exactly one fresh, non-duplicated forwarding path.
- A rejected snapshot fetch never throws past `startSidecarLifecycle()`,
  is logged via the diagnostic channel, and leaves the reconciler `"active"`
  and the app shutdown-safe afterward (Test F).

### Tests added

`frontend/src/app/sidecarLifecycle.test.ts` — 7 tests (Test A–F, with Test F
split into two cases), all using real Part 2D objects per §11's requirement.

### Files changed (complete list)

| File | Classification |
|---|---|
| `frontend/src/app/App.tsx` | Required Phase 4G change (modified) |
| `frontend/src/app/sidecarLifecycle.ts` | Required Phase 4G change (new) |
| `frontend/src/app/sidecarLifecycle.test.ts` | Test (new) |
| `docs/phase4/PHASE4G_IMPLEMENTATION_READINESS.md` | Documentation (this section appended) |

No other file in the tree differs from the Part 2D-4 checkpoint baseline
(full-tree SHA-256 comparison — see final report).

### Test results (this checkpoint)

```
tsc --noEmit   : 0 errors
vitest run     : 9 test files, 211 tests passed, 0 failed, 0 skipped
                 (204 baseline + 7 new)
npm run build  : success
```

Backend integrity: `src-tauri/` and `sidecar-core/` byte-for-byte identical
to the Part 2D-4 baseline. Part 2D sidecar integrity: all seven frozen
production files (`types.ts`, `validation.ts`, `eventSubscription.ts`,
`eventProjection.ts`, `projectionConnector.ts`, `snapshotReconciliation.ts`,
`projectionStore.ts`) and their existing test files byte-for-byte
identical.
