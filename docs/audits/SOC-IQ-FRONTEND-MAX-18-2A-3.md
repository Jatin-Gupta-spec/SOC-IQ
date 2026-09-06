# SOC-IQ Frontend MAX-18 — Phase 2A-3 Audit

**MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.**
**This checkpoint: Settings-local navigation guard (sidebar, CommandPalette, in-app SPA navigation).**

## Baseline

Authoritative input, per this checkpoint's task brief:

| | |
|---|---|
| Supplied file | `SOC-IQ-FRONTEND-MAX-18-2A-2-FULL-PROJECT.zip` |
| Supplied SHA-256 | `baa2e31bf196dbb57c34ea30c5b2ff625b0af29a91c5ea483272da171f50cf78` |
| Entries | 845 files |

Name and hash both match the brief's stated authoritative input — no
discrepancy to flag this checkpoint. The supplied project already
contained Phase 2A-2's foundation work: `settingsDirty.ts`
(`computeSettingsDirty`), `useSettingsPageDirty.ts` (the page-level
aggregate), and the `data-settings-dirty` marker on `SettingsPage`'s
success view. Nothing in the supplied project consumed that aggregate
for navigation — confirmed by grep (no `useNavigate`/`NavLink`
`onClick` reference to it anywhere) — matching Phase 2A-2's own
"Known limitations" section exactly. All pre-existing tests passed
before any change in this checkpoint (`npx vitest run` — 92 test
files, 1291 tests, 0 failed).

## Objective recap

Phase 2A-2 produced a correct, tested `settingsDirty` aggregate, but
scoped entirely inside one `SettingsPage` instance's own local
`useState` — nothing outside that component tree (the sidebar in
`NavigationRegion`, the command palette in `CommandPaletteContainer`,
both siblings of the routed page under `AppShell`, not descendants of
it) could read it. This checkpoint's job is the interception itself:
block navigation away from a dirty Settings page across every
navigation path the current architecture actually exposes, surface a
Stay/Leave confirmation, and make the destination-not-committed
guarantee hold for real — without rewriting the router, without a
generic cross-page unsaved-changes framework, and without a
navigate-then-undo hack for the one path (browser history) that
cannot be intercepted honestly under this architecture.

## Architecture investigated before writing any code

- `App.tsx` uses `HashRouter` + a plain declarative `<Routes>`
  (`router.tsx`) — not a data router (`createBrowserRouter`/
  `RouterProvider`). `useBlocker`/`unstable_usePrompt` require a data
  router and are not available here; the task brief's "do not rewrite
  the router" rules out switching to one for this checkpoint.
- Grepping every `useNavigate()`/`navigate(...)` call site in
  `frontend/src` (excluding tests) found exactly two: `useNavigate()`
  in `CommandPaletteContainer.tsx` (already the palette's sole
  navigation call site) and in `InvestigationWorkspacePage.tsx` (a
  "back to Investigations" button, unreachable from Settings). No
  other in-app trigger — and nothing inside `SettingsPage` or its
  three real controls — issues a route change.
- The sidebar (`NavigationGroup.tsx`) navigates via `NavLink`'s own
  default click handling, not an imperative `navigate()` call.
- Given the above, the complete set of paths that can move a person
  *away from* Settings is: sidebar `NavLink` clicks, and the command
  palette's `handleNavigate`. Both are interceptable *before* they
  commit a route change, because both run through code this
  checkpoint owns (a `NavLink` `onClick` prop; the palette
  container's own `navigate()` call site).
- Browser back/forward and a direct hash edit are **not** in that
  set: `popstate` fires only after `window.location`/the history
  stack have already changed, and `popstate` itself is not
  cancellable. The only way to make that path "interceptable" would
  be to let the navigation commit and then revert it — the exact
  navigate-then-undo pattern the task brief prohibits. See "Known
  limitations" below for the full accounting.

## Design

`pages/settings/settingsNavigationGuardStore.ts` is the one new piece
of shared state, deliberately narrow: a Settings-specific singleton
(mirroring `RestartExhaustedNotificationStore`'s own class-based,
subscribe/notify shape), not a page-agnostic unsaved-changes
framework. Its entire public surface:

| Member | Purpose |
|---|---|
| `setDirty(dirty)` | Written only by `useSettingsNavigationGuardSync`; records whether the currently-mounted `SettingsPage` instance is dirty. |
| `requestNavigation(targetPath)` | The one decision point every trigger calls *before* navigating. Returns `"allowed"` (not dirty, or the target is Settings itself) or `"blocked"` (opens the pending confirmation). Never navigates itself. |
| `cancel()` | Stay: dismisses the pending confirmation; never touches `dirty`. |
| `confirmLeave()` | Leave: returns the attempted destination and clears both the pending confirmation and `dirty`. |
| `getState()` / `subscribe()` | Read/observe the pending confirmation, for the dialog. |

```
SettingsPage's settingsDirty (Phase 2A-2, unchanged)
        │
        ▼  useSettingsNavigationGuardSync (new, 2A-3)
        │    - forwards settingsDirty -> store.setDirty() on every change
        │    - clears store.setDirty(false) unconditionally on unmount
        ▼
settingsNavigationGuard (singleton store)
        │
        ├── NavigationGroup's NavLink onClick ──▶ requestNavigation(item.path)
        │        "blocked" → event.preventDefault(); "allowed" → NavLink navigates as before
        │
        ├── CommandPaletteContainer.handleNavigate ──▶ requestNavigation(path)
        │        "blocked" → close palette, no navigate(); "allowed" → navigate(path); close()
        │
        └── SettingsNavigationGuardDialog (mounted once in AppShell)
                 subscribes to store; Stay → cancel(); Leave → confirmLeave() then navigate(target)
```

Unmount-clearing (`useSettingsNavigationGuardSync`'s second effect) is
what makes "must not use stale dirty state" hold unconditionally:
`dirty` cannot outlive the `SettingsPage` instance it describes, so a
later, unrelated navigation from a different page can never be
spuriously blocked by a previous visit's leftover state — proven by
`useSettingsNavigationGuardSync.test.tsx`'s "fresh mount after
unmount" case and the live suite's "discards the local edit" test.

## Files changed

| File | Change |
|---|---|
| `frontend/src/pages/settings/settingsNavigationGuardStore.ts` | **New.** The guard singleton described above: `requestNavigation`/`cancel`/`confirmLeave`/`setDirty`/`getState`/`subscribe`. |
| `frontend/src/pages/settings/settingsNavigationGuardStore.test.ts` | **New.** Pure store-level unit tests (isolated instances, never the shared singleton): initial state, clean/dirty decisions, Stay, Leave, repeated/rapid requests, multiple-dirty-fields equivalence, save-clears / failed-save-preserves, stale-state clearing, subscription (including a throwing-listener isolation case). |
| `frontend/src/pages/settings/useSettingsNavigationGuardState.ts` | **New.** `useSyncExternalStore` hook exposing the store's pending state to the dialog. |
| `frontend/src/pages/settings/useSettingsNavigationGuardSync.ts` | **New.** The bridge hook `SettingsPage` calls: forwards `settingsDirty` into the store and clears it unconditionally on unmount. |
| `frontend/src/pages/settings/useSettingsNavigationGuardSync.test.tsx` | **New.** Hook-level tests against an isolated store instance: forwarding, unmount-clears-even-while-dirty, unmount-clears-even-when-already-clean, no-clear-on-mere-rerender, fresh-mount-after-unmount. |
| `frontend/src/pages/SettingsPage.tsx` | Adds one call: `useSettingsNavigationGuardSync(settingsDirty)`, right after the existing Phase 2A-2 aggregate is computed. No control's rendering, save flow, loading/error views, or the existing `data-settings-dirty` marker changed. |
| `frontend/src/app/navigation/NavigationGroup.tsx` | Every rendered `NavLink` gets an `onClick` that calls `settingsNavigationGuard.requestNavigation(item.path)` and `event.preventDefault()`s on `"blocked"`. Identical for every item — no Settings-specific branching in this component; the guard itself decides. |
| `frontend/src/app/commandPalette/CommandPaletteContainer.tsx` | `handleNavigate` now consults the guard before calling `navigate()`. `"blocked"` closes the palette and returns without navigating; `"allowed"` runs the unchanged `navigate(path); close();`. |
| `frontend/src/app/shell/SettingsNavigationGuardDialog.tsx` | **New.** The Stay/Leave confirmation: `role="alertdialog"`, focus capture/restore mirroring `CommandPalette.tsx`'s MAX15-F-01 pattern, renders `null` when nothing is pending. |
| `frontend/src/app/shell/SettingsNavigationGuardDialog.css` | **New.** Minimal styling reusing only existing tokens (`styles/tokens.css`) and the existing `.transition-fade` utility — no new visual system. |
| `frontend/src/app/shell/AppShell.tsx` | Mounts `<SettingsNavigationGuardDialog />` as one more sibling, alongside `CommandPaletteContainer`, for the identical "needs router context, must survive every route change" reason. |
| `frontend/src/app/shell/settingsNavigationGuard.live.test.tsx` | **New.** Full-app live tests (real `App`, real `HashRouter`, real `AppShell`) — see coverage table below. |

`router.tsx`, `useSettingsFieldSave.ts`, `useVirustotalKeySave.ts`,
`settingsDirty.ts`, `useSettingsPageDirty.ts`, `CommandPalette.tsx`,
and `ContentRegion.tsx` are **unchanged** (byte-identical to the
supplied input) — each already had exactly what this checkpoint
needed, or falls outside this checkpoint's "routing integration
strictly necessary for the guard" boundary.

## Test coverage

All required behaviors from the task brief, against
`settingsNavigationGuard.live.test.tsx` (full-app, live DOM) unless
noted:

| # | Requirement | Covered by |
|---|---|---|
| 1 | clean Settings → navigation succeeds | "1. clean Settings -> navigation succeeds" |
| 2 | dirty Settings → navigation blocked pending decision | "2. dirty Settings -> navigation blocked pending decision" |
| 3 | Stay → URL/route remains Settings | "3. Stay -> URL/route remains Settings" |
| 4 | Leave → destination reached | "4. Leave -> destination reached" (both cases, including the discard-on-Leave check) |
| 5 | repeated navigation attempts | "5. repeated navigation attempts" + store unit test "re-targets the single pending confirmation" |
| 6 | rapid navigation attempts | "6. rapid navigation attempts" (5 synchronous clicks → exactly one dialog) |
| 7 | multiple dirty fields | "7. multiple dirty fields" (Theme + Export Directory both dirty; Leave discards both) |
| 8 | save clears protection | "8. save clears protection" |
| 9 | failed save preserves protection | "9. failed save preserves protection" |
| 10 | CommandPalette navigation | "10. CommandPalette navigation" (both the blocked-then-confirmed case and the clean/immediate case) |
| 11 | sidebar navigation | "11. sidebar navigation" (direct interception case, and the already-active-Settings-link non-interception case) |
| 12 | history behavior where supported | "12. history behavior where supported" (Stay commits no history entry; Leave commits exactly the confirmed destination) — see "Known limitations" for what "supported" excludes and why |

Regression coverage for MAX-15/16/17, all against the real,
co-mounted production tree:

| Finding | Covered by |
|---|---|
| MAX-15 (command palette focus restore) | "still restores focus to the trigger after closing the palette on a clean Settings page" |
| MAX-16 (restart-exhausted notification) | "still mounts and remains independent of the navigation guard dialog" |
| MAX-17 (route-change focus management) | "still focuses the destination page's main landmark after a guard-confirmed Leave" |

Store- and hook-level isolation tests supplement the live suite:

- `settingsNavigationGuardStore.test.ts` (16 tests) — pure decision
  logic, every method, in isolation from React/DOM/router, including
  a throwing-subscriber case proving one bad listener cannot corrupt
  store state or block delivery to the rest.
- `useSettingsNavigationGuardSync.test.tsx` (7 tests) — the
  forwarding/unmount-clearing contract in isolation, against a fresh
  store instance per test.

## Verification results

Run from `frontend/`:

```
npm ci               → 159 packages installed, no errors
npx vitest run       → 95 test files, 1333 tests passed, 0 failed
npx tsc --noEmit     → no errors
npm run build        → tsc --noEmit && vite build succeeded, dist/ produced
```

1291 pre-existing tests (Phase 2A-2 baseline) + 42 new (16 store + 7
sync-hook + 19 live) = 1333. No existing test was weakened, skipped,
or deleted; `npx vitest run` on the unmodified 92-file baseline still
passes unchanged file-for-file.

## A test-infrastructure finding worth recording

Early runs of the live suite failed non-deterministically-looking, in
a way that turned out to be fully deterministic: React Router v7's
declarative `<Routes>`, on an in-place navigation to a route whose
`React.lazy()` chunk has not yet resolved, keeps the *previously
committed* route's content on screen rather than swapping to the
`<Suspense>` fallback immediately. That is invisible to a real user
(it resolves within the same task), but it meant this file's first
draft of `waitForRouteToSettle()` — which only polled while a
`"Loading "` substring was present in the DOM, mirroring
`router.live.test.tsx`'s helper — returned instantly for this case,
since no such fallback text ever appears; assertions then ran against
the *old*, still-mounted Settings page. Confirmed by instrumenting
`useSettingsFieldSave`'s own mount/unmount effects and `AppRoutes`'s
`useLocation()` render during debugging: `pathname` updated correctly
on every navigation, but the previous route's component tree stayed
mounted until a later real-timer tick. The fix — unconditionally
ticking a handful of real timers before falling through to the
original `"Loading "` watch — is confined to this checkpoint's own new
test file; no production code changed as a result, and no other test
file in the suite exhibited or needed this.

## Security considerations

- `settingsNavigationGuard` stores exactly two pieces of state: a
  `boolean` (`dirty`) and, while a confirmation is pending, the
  attempted destination `string` (a route path already public in
  `NAVIGATION_ITEMS`/`COMMANDS`). No field value, edit buffer, or
  VirusTotal key material crosses this or any other new boundary
  added in this checkpoint.
- `SettingsNavigationGuardDialog`'s rendered text is static
  ("Unsaved changes" / the fixed description) — nothing from any
  control's edit buffer is interpolated into it.
- No new logging was added anywhere in this change.

## Scope compliance

- **Router**: `router.tsx` is byte-identical to the supplied input.
  No switch to a data router, no new route, no change to
  `PAGE_BY_NAVIGATION_ID` or the catch-all/redirect behavior.
- **No generic global unsaved-changes framework**: the guard store
  knows only about Settings — `SETTINGS_NAVIGATION_PATH` is its only
  route-shaped concept, and it exposes no API another page's dirty
  state could plug into without its own, separately-reviewed wiring.
- **No `beforeunload`**: not added; out of scope per the brief.
- **No confirmation UI polish**: `SettingsNavigationGuardDialog` reuses
  existing tokens and the existing `.transition-fade` utility only,
  at the same weight `CommandPalette.css` already established for an
  equivalent overlay+dialog pair.
- **No navigate-then-undo**: verified by construction — grep confirms
  no call to `history.back()`/`pushState()`/`replaceState()` or any
  `popstate`/`hashchange` listener exists anywhere in the new code.
  `requestNavigation()` only ever answers before a caller's own
  (unmodified) navigation call runs.
- **No duplicate confirmations, no loop**: `settingsNavigationGuard`
  holds exactly one `state` object; `requestNavigation()` re-targets
  it rather than stacking a second one (test 5/6), and `confirmLeave()`
  clears both the pending confirmation and `dirty` before the caller's
  `navigate()` runs, so there is no path back into a blocked decision
  for the same attempt.
- **MAX-17 route-focus unaffected**: `ContentRegion.tsx` is
  byte-identical to the supplied input; the regression test above
  confirms a guard-confirmed Leave still ends with focus on the
  destination page's `<main>` landmark.
- **Backend/Rust/Tauri**: untouched — no file under `app/`
  (Python), `src-tauri/`, `keystore-core/`, or `sidecar-core/` was
  read or modified for this checkpoint.

## Known limitations

- **Browser back/forward and direct hash edits are not intercepted.**
  `popstate` fires only after the URL and history stack have already
  changed, and is not itself cancellable — there is no synchronous,
  pre-commit hook into that under the current `HashRouter`/declarative
  `<Routes>` architecture short of letting the navigation commit and
  then reverting it, which this checkpoint's brief explicitly
  prohibits and which no code in this change attempts. This is a real,
  intentional gap in coverage, not an oversight: closing it correctly
  would require either adopting a data router (`RouterProvider` +
  `useBlocker`, itself a "rewrite the router" change explicitly out of
  scope) or a `beforeunload`-style native prompt (also explicitly out
  of scope, and inapplicable to in-app hash changes regardless).
  Test 12 ("history behavior where supported") covers what *is*
  achievable today: the guard's own Stay/Leave decisions commit
  correctly to browser history (no stray entry on Stay; exactly the
  confirmed destination on Leave) — it does not, and cannot yet,
  cover a raw back/forward button press while dirty.
- **The guard has no knowledge of *which* fields are dirty**, only the
  already-OR'd `settingsDirty` aggregate from Phase 2A-2 — by design
  (task brief's "Settings-local protection mechanism", not a
  field-level one). The confirmation dialog's copy is therefore
  generic ("unsaved changes") rather than naming specific fields.
- **A second, unrelated Settings-like page adopting this same pattern
  would need its own store instance and its own wiring** —
  `settingsNavigationGuard` is intentionally not parameterized by
  route or reusable as-is for another page, per the brief's "no
  generic global unsaved-changes framework" boundary. Generalizing it
  is explicitly not this checkpoint's job.

## Final verdict

`PASS — READY FOR MAX-18 PHASE 2A-4`

All twelve required behaviors verified against the real, fully
composed application (`App` → `HashRouter` → `AppShell` → sidebar +
command palette + confirmation dialog, real `SettingsPage` with real
Theme/Export Directory/VirusTotal controls). MAX-15/16/17 regression
checks pass unchanged. `npm ci`, `npx vitest run` (95 files / 1333
tests, 0 failed), `npx tsc --noEmit`, and `npm run build` all pass
clean. `router.tsx` and `ContentRegion.tsx` are untouched.
Decision-before-commit, no navigate-then-undo, no duplicate
confirmations, and no stale dirty state are each verified by a
dedicated test, not merely asserted. The one architecturally
unreachable path (browser back/forward / direct hash edits) is
documented above rather than worked around with a prohibited pattern.
