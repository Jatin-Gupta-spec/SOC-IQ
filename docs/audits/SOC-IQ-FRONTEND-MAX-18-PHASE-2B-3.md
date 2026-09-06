# SOC-IQ FRONTEND — MAX-18 Phase 2B-3: Navigation-Path & Routing Audit

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation.

## 1. Baseline integrity

| Check | Result |
|---|---|
| Input archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-2-FULL-PROJECT.zip` |
| SHA-256 (input) | `70308f1bf1b544f5366f3d4df72acc91b231d450cb76948e39ecc2765b1e0b83` |
| `unzip -t` | `No errors detected in compressed data` |
| Entry count | 864 |
| Byte size | 7,361,110 bytes |
| `npm ci` (frontend/) | 159 packages, clean |
| Baseline `npx vitest run` | 97 test files passed, 1368 tests passed |
| Baseline `npx tsc --noEmit` / `npm run build` | 0 errors, clean |

Baseline test/type/build results match Phase 2B-2's own recorded baseline
exactly — no drift between the two checkpoints' inputs.

## 2. Methodology

This phase drives the real, unmodified `<App/>` (real `HashRouter`, real
`AppShell`) inside jsdom and, following Phase 2B-2's own convention, adds a
temporary, independently-authored harness
(`src/app/__phase2b3_repro__.live.test.tsx`) solely to exercise navigation
paths not already covered by the project's existing `.live.test.tsx`
suite. The harness mocks only `useSettings` and the backend
`runCommand`/`setVirustotalApiKey` calls, identical to every existing
`.live.test.tsx` boundary in this project. After capturing results, the
harness was deleted and `npx vitest run`, `npx tsc --noEmit`, and
`npm run build` were re-run against the restored, unmodified source (§7) —
zero residual change. No production source file was edited, added to, or
removed at any point.

The project's own pre-existing test suite (in particular
`app/shell/settingsNavigationGuard.live.test.tsx`, numbered scenarios 1–14)
was read in full and its coverage cross-checked against the task brief's
Navigation Matrix, Confirmation Matrix, and Edge Cases before deciding
what additional reproduction was needed.

## 3. Navigation Matrix

### Settings clean

| Path | Result |
|---|---|
| Sidebar navigation | Navigates immediately, no dialog (pre-existing scenario 1, re-confirmed) |
| CommandPalette navigation | Navigates immediately, no dialog (pre-existing scenario 10b, re-confirmed) |
| Direct SPA navigation (programmatic `location.hash` change) | Navigates normally |
| History navigation (`history.back()`) | Navigates normally |

All four paths work normally without unnecessary confirmation while
Settings is clean, matching the brief's expectation.

### Settings dirty

| Path | Expected | Actual result |
|---|---|---|
| Sidebar navigation | Blocked pending confirmation | **Blocked** — confirmation dialog opens, hash stays `#/settings` (pre-existing scenarios 2, 11, re-confirmed) |
| CommandPalette navigation | Blocked pending confirmation | **Blocked** — palette closes, confirmation dialog opens in its place (pre-existing scenario 10a, re-confirmed) |
| Direct SPA navigation (`location.hash` assignment) | Unsaved changes cannot be silently discarded | **NOT blocked.** No dialog appears. The hash changes to the new destination, `SettingsPage` unmounts, and the in-progress edit is gone. Reproduced independently: `dialog appeared: false`, `hash after assignment: #/dashboard`, `settings still mounted: false`. |
| History navigation (`history.back()`) | "where supported" | **NOT blocked**, and not interceptable under the current architecture. No dialog appears; `history.back()` silently lands on the previous route and discards the edit. Reproduced independently: `dialog appeared: false`, `hash after back(): #/dashboard`, `settings unmounted: true`. |

### Root cause

`settingsNavigationGuard.requestNavigation()` (the one gate that decides
"allowed" vs. "blocked") is called from exactly two production sites:
`NavigationGroup`'s `NavLink` `onClick` (sidebar) and
`CommandPaletteContainer`'s `handleNavigate` (command palette). Both are
click handlers guarding a specific navigation *trigger*, not the route
change itself. Nothing in the codebase listens for `hashchange` or
`popstate` (confirmed by `grep -rn "popstate|hashchange"` across
`frontend/src`, excluding tests and the guard store's own doc comments,
returning zero listener registrations) — a fact the guard store's own
source comments already state explicitly as a known, accepted
architectural boundary ("no code path... short of committing the
navigation and then reverting it, which this checkpoint's brief explicitly
forbids"). Consequently, any navigation that changes the route without
going through one of those two `onClick` handlers — typing/pasting a new
hash into the address bar, a script setting `location.hash`, or the
browser's own Back/Forward buttons — bypasses the guard entirely. This is
not a new defect introduced since Phase 2A; it is the same limitation
Phase 2A-3, reconfirmed in Phase 2B-1 §4 and Phase 2B-2 §6, already
documented as out of scope for `popstate`/back-forward specifically. What
this phase adds is that **the same gap also covers direct
`location.hash` navigation**, which the task brief's Navigation Matrix
lists as a standard, unqualified path (unlike history navigation, which
the brief itself qualifies "where supported") — i.e., a path the brief
expects to be protected like sidebar/palette clicks, and which currently
is not.

## 4. Confirmation Matrix

Only reachable for paths that actually open the dialog (sidebar,
command palette); direct-hash and history navigation never reach a
pending state to confirm, per §3.

| Path | Stay | Leave |
|---|---|---|
| Sidebar | Cancels; hash stays `#/settings`; edit value preserved (scenario 3) | Navigates to attempted destination; destination renders (scenario 4) |
| CommandPalette | Cancels (implied by shared `store.cancel()`; not re-driven separately, see §6) | Navigates to attempted destination (scenario 10a) |

Both Stay and Leave, for both reachable paths, satisfy the brief's
expectations: Stay leaves `SettingsPage` mounted with dirty state and
edits intact (scenario 3 asserts the edited `<select>` value survives);
Leave navigates and the guard's own `dirty`/`state` are cleared before the
unmount cleanup runs (`confirmLeave()`, `settingsNavigationGuardStore.ts`),
so the stale-guard behavior described next does not occur for these two
paths.

## 5. Edge cases

| Case | Result |
|---|---|
| Repeated navigation attempt | Single open confirmation is re-targeted to the latest destination, not duplicated (scenario 5, re-confirmed) |
| Rapid navigation attempt | Five synchronous clicks produce exactly one `alertdialog`, hash unchanged (scenario 6, re-confirmed) |
| Dirty → Stay → attempt another route | Independently reproduced: Stay dismisses the first confirmation, and a second sidebar click to a different destination opens a fresh, correctly-targeted confirmation (`dialog appeared for second attempt: true`, hash remains `#/settings` until a decision is made) |
| Dirty → Leave → return to Settings → edit again → save → navigate | Pre-existing scenario 4's second case + scenario 8 cover this sequence: a fresh `SettingsPage` mount after Leave starts clean (not falsely dirty from the discarded edit), and a subsequent edit-then-save-then-navigate completes with no confirmation |
| Back/forward where supported | Not supported — see §3. No duplicate confirmations or navigation loops were observed, because no confirmation is ever raised for this path in the first place; the underlying risk here is silent data loss, not a duplicate-dialog or loop defect |

No duplicate confirmations, navigation loops, or navigation-before-
confirmation were observed on any path that does raise a confirmation.
Stale dirty state was checked directly: after a guard-confirmed Leave,
`confirmLeave()` clears `dirty` before `useSettingsNavigationGuardSync`'s
own unmount cleanup runs, and a fresh `SettingsPage` mount is confirmed
not falsely dirty (pre-existing scenario 4's second `it` block, hash
`#/settings` → edit discarded → clean remount → unrelated navigation to
Reports proceeds with no dialog). The guard does not remain active after
a completed Leave on any reachable path.

## 6. MAX-17 regression

Re-confirmed via the pre-existing regression test
(`describe("regression: MAX-17 (route-change focus management)")`):
after a guard-confirmed Leave from Settings to Dashboard, the destination
page's `main.page-layout` landmark receives focus
(`document.activeElement === main`), matching MAX-17's established
route-change focus behavior. This phase did not need to re-drive this
independently; the existing assertion already renders the real component
tree end-to-end exactly as this phase's own harness would.

## 7. Post-harness integrity check

```
npx vitest run   → 97 test files passed (97), 1368 tests passed (1368)
npx tsc --noEmit → 0 errors
npm run build    → clean
```

Identical to §1's baseline and to Phase 2B-2's own results — confirming
the temporary harness left no residue and no production file was altered.

## 8. Output artifact

| Item | Value |
|---|---|
| Archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-3-FULL-PROJECT.zip` |
| Contents | Complete project, plus this document; no other change vs. the Phase 2B-2 input |
| Source modifications | None (temporary harness added and removed within this session only; never present in the packaged output) |

(SHA-256, entry count, and byte size for this specific output archive are
recorded in the delivery message accompanying this document.)

## 9. Interpretation and verdict

Sidebar navigation and CommandPalette navigation — the two paths
`settingsNavigationGuard` actually instruments — behave correctly across
the full Navigation Matrix, Confirmation Matrix, and Edge Cases: clean
navigation is unobstructed, dirty navigation is blocked pending a
decision, Stay/Leave both behave as specified, repeated/rapid attempts
don't duplicate or corrupt the pending confirmation, and no stale dirty
state or guard-after-leave was found. MAX-17's route-change focus
behavior is intact after a guarded Leave.

However, the task brief's Navigation Matrix lists **direct SPA
navigation** as a standard path expected to satisfy "unsaved changes
cannot be silently discarded" while Settings is dirty, on equal footing
with sidebar and command-palette navigation (only history navigation is
qualified "where supported"). Independent reproduction against the real,
unmodified application confirms that a direct route change — a script or
address-bar `location.hash` assignment to a non-Settings route — is
**not intercepted at all**: no confirmation appears, the route changes,
`SettingsPage` unmounts, and the in-progress edit is discarded with no
opportunity to cancel. The same is true of browser Back/Forward
(`history.back()`), which the brief's own "where supported" phrasing
anticipates may be architecturally out of reach — and Phase 2A-3/2B-1/
2B-2 already documented that specific case as an accepted limitation of
the current `HashRouter`/declarative-router design (no synchronous,
cancellable hook into `popstate` short of a navigate-then-revert pattern
the brief explicitly forbids). Direct hash navigation is not covered by
that prior "accepted limitation" framing, since it was never enumerated
or tested in Phase 2A/2B-1/2B-2, and the current brief lists it
unqualified alongside the two paths that are protected.

This is a genuine gap against this checkpoint's own stated expectation,
not a documentation-only nuance: with Settings dirty, a person can lose
in-progress edits by navigating via a mechanism this application itself
exposes (e.g. a deep link, a bookmarked hash URL, or any future
in-app control that changes `location.hash` directly instead of going
through `NavLink`/`useNavigate()`) with no warning at all.

**BLOCKED**

Per this checkpoint's "do not modify implementation" instruction, no fix
is attempted here. Recommended next step for Phase 2B-4 (or a return to
2A-scoped implementation work): either (a) extend
`settingsNavigationGuard` with a `hashchange`/`popstate` listener that
can at least warn via `beforeunload`-style intercept semantics where the
router allows it, scoping any such fix to a documented, testable
boundary rather than a navigate-then-revert; or (b) explicitly re-scope
the task brief to mark direct hash navigation as an accepted limitation
alongside history navigation, if that is the intended product decision —
that determination is outside this audit's own scope.
