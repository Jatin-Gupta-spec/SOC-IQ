# SOC-IQ FRONTEND — MAX-18 Phase 2B-8: Final Independent Closure Gate

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation.

This document is the final, independent closure determination for
MAX-18. It does not modify source, does not implement fixes, and does
not begin MAX-19.

## 1. Input identity

| Item | Value |
|---|---|
| Phase 2B baseline input (this session) | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-7-FULL-PROJECT.zip` |
| SHA-256 (as received) | `568e7c35a181b77a5aaeae28bf72244d4d92c61158d55906fec7aaabcff91ac4` |
| `unzip -t` | `No errors detected in compressed data` |
| Entry count | 869 files |
| No source file was modified during this audit. | — |

The Phase 2A input identity and the Phase 2B-1 through 2B-7 chain are
recorded in their own prior audit documents
(`docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-*.md`,
`docs/audits/SOC-IQ-FRONTEND-MAX-18-PHASE-2B-1.md` through `-7.md`) and
are not re-derived here; this checkpoint only re-verifies current,
observable behavior against the unmodified archive above.

## 2. Final defect determination

**Question:** Can an analyst currently make unsaved Theme, Export
Directory, or VirusTotal Settings changes and navigate away without
receiving an appropriate warning?

**Answer: No**, for every navigation path this application itself
mediates. Verified directly from source (not from test names alone):

- `SettingsPage.tsx` computes one `settingsDirty` aggregate
  (`useSettingsPageDirty` → `computeSettingsDirty`, OR of the three
  controls' own `dirty` flags) and feeds it to two independent
  consumers: `useSettingsNavigationGuardSync` (in-app guard) and
  `useSettingsBeforeUnloadGuard` (browser-native guard).
- `NavigationGroup.tsx` (sidebar) and `CommandPaletteContainer.tsx`
  both call `settingsNavigationGuard.requestNavigation(path)` before
  acting on a link/command, and abandon that navigation if the result
  is `"blocked"` — confirmed by direct inspection of both files, not
  only their tests.
- `SettingsNavigationGuardDialog.tsx` renders only while a navigation
  is blocked, offering **Stay** (`store.cancel()`) and **Leave**
  (`store.confirmLeave()` then `navigate()`), with Escape mapped to
  the same non-destructive outcome as Stay, a Tab/Shift+Tab focus
  trap, and focus capture/restore.
- One documented, architectural exception: browser **back/forward**
  and direct hash edits are not interceptable under this app's
  `HashRouter` — `popstate` fires only after the URL/history stack has
  already changed, and this checkpoint's brief (consistent with prior
  2A-3 scope) forbids a navigate-then-revert workaround. This is
  called out explicitly in `settingsNavigationGuardStore.ts`'s own doc
  comment and is not covered by any test — it is a real, acknowledged
  gap, not a false negative.

## 3. Full verification (exact commands, exact results — this session)

```bash
npm ci
npx vitest run
npx tsc --noEmit
npm run build
```

| Command | Result |
|---|---|
| `npm ci` | 159 packages added, clean install. `npm audit`: 2 vulnerabilities (1 moderate, 1 high), both pre-existing transitive dev-only advisories in the unmodified lockfile, unrelated to MAX-18 and out of this checkpoint's scope. |
| `npx vitest run` | **97 test files passed, 1368 tests passed.** 0 failures. |
| `npx tsc --noEmit` | **0 errors.** |
| `npm run build` | **Clean** — `tsc --noEmit && vite build` succeeded, 210 modules transformed, `SettingsPage-*.js`/`.css` chunks emitted, no warnings. |

## 4. Final acceptance matrix

| Area | Result | Basis |
|---|---|---|
| Theme dirty detection | PASS | `useSettingsFieldSave.test.tsx`; direct source read of `ThemeControl`/`useSettingsFieldSave` |
| Export Directory dirty detection | PASS | `useSettingsFieldSave.test.tsx`, `exportDirectoryBrowse.test.ts` |
| VirusTotal dirty detection | PASS | `VirustotalControl.test.tsx` |
| Aggregate dirty state | PASS | `settingsDirty.test.ts`, `useSettingsPageDirty.test.tsx` |
| Successful save clears protection | PASS | `useSettingsFieldSave.test.tsx` |
| Failed save preserves protection | PASS | `useSettingsFieldSave.test.tsx` |
| Multiple dirty controls | PASS | `useSettingsPageDirty.test.tsx`; `computeSettingsDirty` OR-over-three-flags coverage |
| Sidebar navigation | PASS | `NavigationGroup.tsx` source read + `NavigationRegion.test.tsx` |
| CommandPalette navigation | PASS | `CommandPaletteContainer.tsx` source read |
| History navigation (back/forward, hash edit) | **Documented limitation, not covered** | No interception possible under `HashRouter`'s `popstate` model; explicitly documented in `settingsNavigationGuardStore.ts`; no test exists for it |
| Stay | PASS | `SettingsNavigationGuardDialog.tsx` source read + `settingsNavigationGuardStore.test.ts` |
| Leave | PASS | same |
| Beforeunload | PASS / documented browser limitation | `useSettingsBeforeUnloadGuard.ts`; native dialog text/appearance cannot be exercised in jsdom |
| Confirmation semantics | PASS | Stay/Leave/Escape all resolve to one of exactly two intentional outcomes; no silent-discard path |
| Keyboard accessibility | PASS | Escape handled; Tab/Shift+Tab trap implemented |
| Focus entry | PASS | dialog receives focus on becoming pending |
| Focus return | PASS | previously-focused element restored on Stay |
| Destination focus | PASS | MAX-17 route-change focus management, unaffected, takes over on Leave |
| No body focus | PASS | focus never falls through to `<body>` in the capture/restore logic |
| No secret leakage | PASS | `settingsDirty.ts` takes booleans only; VirusTotal edit buffer never reaches the aggregate |
| MAX-13 regression | PASS | `ErrorBoundary.live.test.tsx` |
| MAX-14 regression | PASS | same file, focus-behavior block |
| MAX-15 regression | PASS | `CommandPalette.live.test.tsx` |
| MAX-16 regression | PASS | `RestartExhaustedNotification.live.test.tsx` |
| MAX-17 regression | PASS | `routeFocus.live.test.tsx` |
| Full test suite | PASS | 97 files / 1368 tests, this session |
| TypeScript | PASS | 0 errors, this session |
| Production build | PASS | clean, this session |
| Scope compliance | PASS | no source modified during this audit; no stray temp artifacts in the input archive |

**Material vs. non-material split:** every row above is PASS except
history/back-forward navigation, which is a real, permanent
architectural limitation of intercepting `HashRouter` `popstate`
events (not a testing gap or an oversight) and the already-accepted
`beforeunload` native-dialog-text limitation common to all browsers.
Neither blocks the finding's actual harm scenario — silent, ordinary
in-app discard — from being closed.

## 5. Accessibility, security, and browser-lifecycle results

- **Accessibility:** `role="alertdialog"`, `aria-modal`, labelled/described
  by visible text, focus capture-on-open and restore-on-Stay, Escape
  mapped to Stay's outcome, and a dependency-free Tab/Shift+Tab trap
  confined to this dialog.
- **Security:** the dirty aggregate is boolean-only by construction
  (`SettingsDirtyFlags`); the VirusTotal edit buffer's actual value is
  never passed into `computeSettingsDirty` or any guard state.
- **Browser lifecycle:** in-app navigation (sidebar, command palette)
  is fully guarded; tab/window close and reload are guarded via
  `beforeunload`; browser back/forward and direct hash edits are not
  guarded, and are documented as such rather than silently unhandled.

## 6. Regression result

MAX-13 through MAX-17 all re-verified passing in this session's own
`npx vitest run`, using the exact, unmodified test files already in
the archive — no new or edited test files were introduced by this
audit.

## 7. Environmental limitations

- Two pre-existing, transitive, dev-server-only `npm audit` advisories
  in the unmodified lockfile (fixable only by an out-of-scope
  `vite@8` major upgrade).
- `beforeunload`'s native browser dialog text/appearance cannot be
  exercised under jsdom; the listener registration/deregistration
  lifecycle itself is fully tested.
- Browser back/forward and direct hash-URL edits are not interceptable
  under the current `HashRouter`/declarative-router architecture (see
  §2 and §4).

## 8. Remaining conditions

None that block closure. The one open item (history/back-forward
navigation) is a standing, architectural condition rather than an
open defect — it existed identically at every prior 2A/2B checkpoint
and is unchanged by this audit.

## 9. Scope audit

No source file was created, modified, or deleted during this audit.
No fix was implemented. No refactor was performed. No MAX-19 work was
started. The only new artifacts from this checkpoint are this document
and the closure ZIP referenced below.

## 10. Final verdict

> **MAX-18 CLOSED — PASS WITH CONDITIONS**

Condition: browser back/forward and direct hash-URL navigation away
from Settings with unsaved edits remain unguarded, as a documented,
permanent architectural limitation of this application's router — not
a material defect in the finding's original scope (ordinary in-app
navigation and browser close/reload), both of which are fully closed.

MAX-19 readiness is not declared by this document; it is out of scope
for this checkpoint per the task brief.
