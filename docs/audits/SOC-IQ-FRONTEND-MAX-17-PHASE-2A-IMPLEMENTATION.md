# SOC-IQ FRONTEND MAX-17 — PHASE 2A IMPLEMENTATION

## 1. Baseline Metadata

- Phase: MAX-17 Phase 2A (implementation of the single finding
  selected in Phase 1's forensic audit)
- Selected finding: **MAX17-F-01** — No route-change focus
  management; SPA navigation can strand keyboard/AT users (P1)

### Baseline discrepancy (must be disclosed, not glossed over)

The Phase 2A task brief names the authoritative baseline as
`SOC-IQ-FRONTEND-MAX-16-FINAL-CLOSURE-FULL-PROJECT.zip`, and the
Phase 1 forensic audit records that baseline's SHA-256 as
`bc18fb1d1d7c1ad476290be5759bd26afcf8a5c0b04a814b0ead886dd719abf9`
with an 834-file count.

The project archive actually supplied for this Phase 2A session is a
**different** file:

```text
Filename:     SOC-IQ-FRONTEND-MAX-16-PHASE-2A-IMPLEMENTED-FULL-PROJECT.zip
SHA-256:      8a0ec3737ae3c9efc4f3a604fc156913b4f05355da7d1e11e549d5f651ead959
Entry count:  747 files (before this phase's additions)
```

This is a real, verified mismatch — different filename, different
SHA-256, different file count — not a copy of the audit's stated
baseline. I did not paper over this by silently treating it as
equivalent. Everything below (diff, scope audit, file counts) is
computed against the archive that was actually provided, since that
is the only baseline available to work from in this session; no
attempt was made to fetch or reconstruct the audit's originally-named
`FINAL-CLOSURE` artifact. This discrepancy is carried into the final
verdict below as a documented condition, not silently resolved.

## 2. Files Changed

Exactly the files the Phase 1 audit's own "in-scope" list (§10)
anticipated, and no others:

```text
M  frontend/src/app/shell/ContentRegion.tsx
M  frontend/src/pages/components/PageLayout.tsx
A  frontend/src/app/shell/routeFocus.live.test.tsx
A  frontend/src/pages/components/PageLayout.test.tsx
```

Confirmed by a full recursive diff against the supplied baseline
(`diff -rq`, excluding `node_modules`/build output): these four paths
are the *only* differences anywhere in the entire project tree,
frontend or otherwise. No backend, Python, Rust, Tauri, packaging,
CI, or database file was touched (§16/§15).

None of the explicitly out-of-scope files were modified:
`CommandPalette.tsx`, `CommandPaletteContainer.tsx`,
`RestartExhaustedNotification.tsx`, `ErrorBoundary.tsx`,
`NavigationGroup.tsx`, `NavigationRegion.tsx` are all byte-identical
to the baseline.

## 3. Implementation Summary

### `PageLayout.tsx`

Added `tabIndex={-1}` to the existing `<main className="page-layout"
aria-label={label}>` element. No other prop, structure, or landmark
semantics changed. This is the one addition needed to let the new
shell-level mechanism move real DOM focus onto a page's landmark
without adding it to the page's normal (Tab-key) sequential
navigation order.

### `ContentRegion.tsx`

Added a route-change focus effect, colocated in this file rather than
`AppShell.tsx` because `ContentRegion` is the one shell element that
actually wraps the routed page content on every navigation path this
finding covers.

- **Trigger**: `useLocation().pathname` (not the full `location`
  object and not `location.key`). This was a deliberate choice made
  after reading `InvestigationWorkspacePage.tsx`: its own tab
  switcher (MAX7-F-02) persists the active tab via
  `setSearchParams(..., { replace: true })`, which changes
  `location.key` without changing `location.pathname`, and which
  already moves real DOM focus to the newly-selected tab itself
  (`WorkspaceTabs.selectAndFocusTab`). Keying on `pathname` alone
  means the new shell-level effect only ever fires for an actual
  page-to-page navigation, and never re-fires (and never fights) that
  already-correct local tab-focus behavior. This satisfies §6's "must
  not fight" requirement concretely, not just by leaving the other
  files unmodified.

- **Mechanism**: on a pathname change, the effect makes an
  unconditional first attempt to find and focus the current page's
  `main.page-layout` inside `ContentRegion`'s own container (this is
  what actually overrides a still-connected, still-focused sidebar
  `NavLink` from the *previous* page — the specific gap the audit
  documents for the sidebar path). It then attaches a
  `MutationObserver`, scoped to that same container
  (`childList`/`subtree`), that re-attempts the focus whenever the
  DOM changes *and* focus is currently "stranded" — defined as
  `document.activeElement` being `document.body`, `null`, or a node
  no longer connected to the document. This second layer exists
  because every route is code-split (MAX8-F-01): the first thing that
  renders after a navigation is often `RouteLoadingFallback` (itself
  a `<PageLayout>`), which is later unmounted and replaced by the
  real page once its chunk resolves — and `InvestigationWorkspacePage`
  separately swaps between its own loading/error/success
  `<PageLayout>`s while its data fetch is in flight. Each such swap is
  a real DOM removal, which is what sends focus to `document.body` in
  jsdom and real browsers alike; the observer catches that and
  re-anchors focus to whichever `main.page-layout` exists at that
  moment, without ever touching focus that a page's own local logic
  has already placed somewhere sensible.
- **No timers**: no `setTimeout`/`setInterval` of any kind is used to
  wait for content to render — the `MutationObserver` reacts to real
  DOM mutations only, per §3/§8's explicit prohibition on arbitrary
  delays.
- **Cleanup**: the observer is disconnected in the effect's cleanup,
  which runs before the next pathname change's effect body — no
  observer ever outlives the navigation it was created for, and no
  stale `<main>` reference is ever retained (the target is re-queried
  fresh on every attempt, never cached).
- **Initial mount**: a `useRef` flag skips the very first render, so
  the mechanism never claims focus on first page load — only on an
  actual subsequent navigation, matching the finding's own framing
  ("when the SPA navigates to a new page").

No `FocusProvider`, context, event bus, store, or new dependency was
introduced. `AppShell.tsx` was left untouched — the mechanism fit
entirely inside `ContentRegion.tsx` plus the one-line `PageLayout.tsx`
change, which is the smaller of the two files §15 named as candidates.

## 4. Navigation Paths Covered

All three paths named in the finding are exercised by real,
`document.activeElement`-asserting tests against the actual
composition root (`App.tsx`, real `HashRouter`, no test-only focus
manager):

- **Sidebar `NavLink` navigation** — clicking a sidebar link moves
  focus off that link and onto the destination page's `<main>`.
- **Whole-row navigation** (`InvestigationsPage`'s
  `window.location.hash` assignment, MAX7-F-05) — activating a
  focused investigation row moves focus onto
  `InvestigationWorkspacePage`'s `<main>`, and the old, now-removed
  `<tr>` is confirmed both unfocused and disconnected.
- **Command-palette navigation** — opening the palette from an
  in-page control, selecting a navigation command, and letting the
  palette close moves focus onto the destination page's `<main>`,
  even though the control that opened the palette is unmounted by the
  navigation.

## 5. Test Coverage

Two new test files, both exercising the real production mechanism
(no fake test-only focus manager, no manual "focus the destination
inside the test" shortcuts):

### `frontend/src/pages/components/PageLayout.test.tsx` (3 tests)

Direct, narrow coverage of the one `PageLayout` change: `<main>`
renders with `tabindex="-1"`, never a positive `tabIndex`, and the
existing landmark role/`aria-label`/class are unchanged. Satisfies
required Test 6 (§12).

### `frontend/src/app/shell/routeFocus.live.test.tsx` (5 tests)

Mounts the real `App` (real `HashRouter`, real `AppShell`,
`ContentRegion`, `PageLayout`) via `react-dom/client` + `act`,
mirroring this project's own established `.live.test.tsx` convention
(`navigation.live.test.tsx`, `AppShell.live.test.tsx`,
`CommandPaletteContainer.live.test.tsx`). `useInvestigationsList` is
mocked at its module boundary (same convention as
`InvestigationsPage.test.tsx`) so the whole-row path has real,
deterministic rows; `InvestigationWorkspacePage`'s own data fetch is
left real and unmocked, exactly like `router.live.test.tsx`'s
existing `/investigations/:id` case — it fails fast in this jsdom
environment (no Tauri runtime) and renders its own real error state,
which is still a genuine `<PageLayout>`-owned `<main>`.

- **Test 1 — Sidebar route navigation**: passes.
- **Test 2 — Whole-row navigation**: passes.
- **Test 3 — Command-palette navigation**: passes (closes the
  specific gap the Phase 1 audit's own reproduction steps documented).
- **Test 4 — CommandPalette focus-restoration regression (MAX-15)**:
  passes — closing the palette *without* navigating still restores
  focus to the pre-open trigger, proving the new pathname-keyed
  effect never fires for that path and never fights MAX-15's own
  logic.
- **Test 7 — Repeated navigation (A → B → C → A)**: passes — each of
  four consecutive navigations, including the return to a
  previously-visited path, correctly re-focuses its own destination.

**Test 5 (RestartExhaustedNotification regression, MAX-16)** and the
historical regression coverage for `ErrorBoundary`/MAX-14 are not
duplicated in this new file — `RestartExhaustedNotification.tsx` and
`ErrorBoundary.tsx` were not modified, and their own existing test
files (`AppShell.live.test.tsx`'s notification suite,
`ErrorBoundary`'s own tests) already assert their behavior directly
and are confirmed still passing as part of the full suite run below.
Writing a second, duplicate assertion of unmodified behavior in the
new file was judged unnecessary rather than skipped by oversight.

**Test 6 (main not in natural Tab order)**: covered by
`PageLayout.test.tsx` above, not duplicated in `routeFocus.live.test.tsx`.

## 6. Exact `document.activeElement` Results

All assertions below are live, from the actual `npx vitest run`
output (not paraphrased):

| Test | Assertion | Result |
|---|---|---|
| Sidebar nav | `document.activeElement === reportsMain` (Reports page `<main>`) after clicking the Reports link | **PASS** |
| Sidebar nav | `document.activeElement !== reportsLink` | **PASS** |
| Whole-row nav | `document.activeElement === workspaceMain` after activating a focused investigation row | **PASS** |
| Whole-row nav | `document.activeElement !== row`; `document.contains(row) === false` | **PASS** |
| Command palette nav | `document.activeElement === dashboardMain` after selecting "Dashboard" from the palette | **PASS** |
| Command palette nav | `document.activeElement !== searchInput`; `document.contains(searchInput) === false` | **PASS** |
| MAX-15 regression | `document.activeElement === analyzeLink` after Escape-closing the palette with no navigation | **PASS** |
| Repeated nav | `document.activeElement` correctly tracks each of Analyze → Settings → Dashboard main in turn | **PASS** |

## 7. MAX-15 Regression Result

**PASS.** `CommandPalette`'s own pre-open-capture/restore-on-close
behavior is untouched (`CommandPalette.tsx` and
`CommandPaletteContainer.tsx` are byte-identical to baseline), and
Test 4 above directly proves it still works end-to-end through the
real shell: closing the palette without navigating restores focus to
the exact control that opened it. This is possible precisely because
the new `ContentRegion` effect is keyed on `pathname`, which does not
change when the palette closes without navigating — the new
mechanism never even runs for this case.

## 8. MAX-16 Regression Result

**PASS (via unmodified file + full suite).**
`RestartExhaustedNotification.tsx` was not modified. The full
`vitest run` below includes `AppShell.live.test.tsx`'s existing
notification suite (mount/exhaust/dismiss/rerender/route-change
scenarios), and all of those tests pass unchanged.

## 9. Full Vitest Result

```text
npx vitest run

 Test Files  87 passed (87)
      Tests  1238 passed (1238)
   Duration  ~56s
```

Baseline (Phase 1, before this implementation): 85 test files, 1230
tests, all passing. This phase adds exactly 2 test files and 8 tests
(3 in `PageLayout.test.tsx`, 5 in `routeFocus.live.test.tsx`) — the
delta (87−85 files, 1238−1230 tests) matches exactly. Zero failures,
zero skipped, both before and after.

## 10. TypeScript Result

```text
npx tsc --noEmit
Result: PASS — zero errors, zero output
```

## 11. Build Result

```text
npm run build   (tsc --noEmit && vite build)
Result: PASS — 202 modules transformed, all chunks emitted,
        built in ~2.5s, no warnings
```

Chunk count and per-page code-splitting (MAX8-F-01) are unchanged —
this phase added no new dependency and no new chunk boundary.

## 12. Diff / Scope Verification

```text
diff -rq <baseline>/frontend <implementation>/frontend
  (excluding node_modules, dist)

Only in implementation: frontend/src/app/shell/routeFocus.live.test.tsx
Only in implementation: frontend/src/pages/components/PageLayout.test.tsx
Files ContentRegion.tsx differ
Files PageLayout.tsx differ

diff -rq <baseline> <implementation> --exclude=frontend
  (entire rest of the repository)

(no output — zero differences)
```

Scope matches exactly what §15 anticipated
(`AppShell.tsx`/`ContentRegion.tsx`/`PageLayout.tsx` as candidates;
`AppShell.tsx` in the end needed no change). No file outside these
four was touched anywhere in the project.

## 13. Known Limitations

1. **Baseline provenance mismatch** (see §1): the project archive
   actually available this phase does not match the filename or
   SHA-256 the Phase 1 audit named as authoritative. The diff/scope
   audit above is accurate *relative to the archive actually
   supplied*, but is not a diff against the specific
   `FINAL-CLOSURE` artifact the audit originally referenced. This
   should be reconciled before treating this implementation as
   final — either by confirming the supplied archive is in fact
   equivalent in relevant content, or by re-running this diff against
   the correctly-named baseline.
2. **`InvestigationWorkspacePage`'s real data fetch is left
   unmocked** in the new live test, matching this project's own
   existing precedent (`router.live.test.tsx`) — it exercises the
   page's real error state (no Tauri runtime in jsdom), not its
   success state. The focus mechanism itself does not distinguish
   between the workspace's loading/error/success states (all three
   render the same `main.page-layout` shape via `PageLayout`), so
   this is not expected to be a gap in coverage of the *focus*
   behavior specifically — but it does mean the success-state
   `<main>` is never directly exercised as the focus target in this
   file.
3. **The "stranded focus" recovery check** (`document.body`,
   `null`, or a detached node) is a heuristic, not an exhaustive
   proof that no other DOM mutation could ever move focus to
   `document.body` for a reason unrelated to a page-content swap. In
   this codebase, `ContentRegion`'s subtree only ever contains routed
   page content (the sidebar, command palette, and restart
   notification are all mounted as `ContentRegion` siblings in
   `AppShell`, outside the observed subtree), and no page in this
   project currently performs a periodic/polling re-render of its own
   `<main>` — so this risk is assessed as low for the current
   codebase, but is worth re-checking if a future page adds polling
   or periodic re-rendering of its top-level content.
4. Per the task brief's explicit instruction, **MAX17-F-02**
   (investigations search/filter/sort state lost on navigating to a
   workspace and back) was not addressed — it remains open exactly as
   the Phase 1 audit deferred it.

## 14. Phase 2A Verdict

# PASS WITH CONDITIONS

The implementation itself is complete, minimal, matches the
finding's required architecture and scope exactly, and is fully
verified: all three required navigation paths pass real
`document.activeElement` assertions, both cited historical
regressions (MAX-15, MAX-16) are confirmed intact, the full test
suite passes with the expected exact delta, and TypeScript/build are
both clean.

The **condition** is entirely about baseline provenance, not the
implementation's correctness: the archive available this session does
not match the filename/SHA-256 the Phase 1 audit named as the
authoritative `MAX-16-FINAL-CLOSURE` baseline (§1, §13-1). This
should be reconciled — confirming the two are equivalent, or
re-basing this diff onto the correctly-named artifact — before this
phase is treated as closed against that specific baseline claim.

Phase 2A is **not** MAX-17 closure. MAX17-F-02 and MAX17-F-03 remain
open/deferred as recorded in the Phase 1 audit. Phase 2B (closure) and
any search for a MAX-18 candidate are out of scope for this document.
