# SOC-IQ FRONTEND — MAX-18 Phase 2B-7: Full Regression + Scope Audit

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation. This checkpoint is the final broad,
independent regression before MAX-18 closure: full verification
commands, a regression matrix across MAX-13 through MAX-18, a complete
MAX-18 workflow audit, a scope audit against a specific forbidden list,
and a test-quality inspection of the MAX-18 test suite itself.

## 1. Baseline integrity

| Check | Result |
|---|---|
| Input archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-6-FULL-PROJECT.zip` |
| SHA-256 (input) | `92837ec6f089ea7ed0e83c29aa72dac7e6748fff3751eaf11c5810469cc7e039` — matches this session's own record of the Phase 2B-6 output byte-for-byte |
| `unzip -t` | `No errors detected in compressed data` |

This phase's input is this session's own Phase 2B-6 output.

## 2. Full verification (exact commands, exact results)

```bash
npm ci
npx vitest run
npx tsc --noEmit
npm run build
```

| Command | Result |
|---|---|
| `npm ci` | 159 packages added, clean. `npm audit`: 2 vulnerabilities (1 moderate, 1 high) — both trace to a transitive `esbuild`/`vite` **dev-server-only** advisory (GHSA-67mh-4wv8-2f99), fixable only via a breaking `vite@8` upgrade. This is a pre-existing dev-dependency condition in the unmodified `package-lock.json`, unrelated to MAX-18 or to anything on this checkpoint's scope list (§5) — noted for the record, not remediated, since remediation would itself be an out-of-scope dependency change this checkpoint does not authorize. |
| `npx vitest run` | **97 test files passed, 1368 tests passed.** Identical to Phase 2B-5's and Phase 2B-6's own recorded baselines — no drift. |
| `npx tsc --noEmit` | **0 errors, clean.** |
| `npm run build` | **Clean** — `tsc --noEmit && vite build` succeeded, 210 modules transformed, all expected chunks emitted (`SettingsPage-*.js`/`.css` among them), build finished in 2.45s with no warnings or errors. |

No source file was modified at any point in this review.

## 3. Regression matrix (MAX-13 → MAX-18)

| Checkpoint | Behavior | Result | Evidence |
|---|---|---|---|
| **MAX-13** — ErrorBoundary recovery | Catches a render-time error, shows the fallback, and a recovery action clears the error state and re-renders the children; catches the error again on a second detonation with no speculative retry machinery. | **Pass** — 11/11 tests in this file, including both catch-behavior and recovery-behavior describe blocks. | `app/providers/ErrorBoundary.live.test.tsx`, describe blocks "catch behavior" and "recovery behavior" |
| **MAX-14** — ErrorBoundary fallback focus | Focus moves into the fallback alert as soon as an error is caught; the fallback remains a valid non-tabbable-by-default programmatic focus target; re-focuses correctly if the same error is caught again after reset; does not strand focus on the removed "Try again" button once recovery succeeds. | **Pass** — same 11/11 test file, describe block "focus behavior" (5 tests). | `app/providers/ErrorBoundary.live.test.tsx`, describe block "focus behavior" |
| **MAX-15** — CommandPalette focus restoration | Focus returns to the pre-open trigger when the palette closes without navigating. | **Pass** — re-confirmed directly in this session's run of `CommandPalette.live.test.tsx`, and independently re-exercised as an explicit regression check inside MAX-17's own test file (`routeFocus.live.test.tsx`, Test 4: "CommandPalette still restores focus to the pre-open trigger when it closes without navigating (MAX-15)"). | `app/commandPalette/CommandPalette.live.test.tsx`; `app/shell/routeFocus.live.test.tsx` Test 4 |
| **MAX-16** — RestartExhaustedNotification focus restoration | Focus is correctly managed on dismiss, including across repeated dismiss/reappear cycles using the current target rather than a stale one. | **Pass** — 7/7 tests in `RestartExhaustedNotification.live.test.tsx`, describe block "focus management on dismiss (MAX16-F-01)". | `shared/notifications/RestartExhaustedNotification.live.test.tsx` |
| **MAX-17** — Route-change destination focus | Sidebar navigation, whole-row activation, and command-palette navigation all move focus to the destination page's `<main>`; repeated navigation (A→B→C→A) focuses each destination correctly every time. | **Pass** — 5/5 tests in `routeFocus.live.test.tsx`. | `app/shell/routeFocus.live.test.tsx`, describe block "Route-change focus management (MAX17-F-01)" |
| **MAX-18** — Unsaved Settings protection | See §4 below for the full workflow breakdown; summary here: dirty aggregation, in-app navigation guard, confirmation dialog, and browser `beforeunload` guard all independently re-verified passing. | **Pass** — 22 test files / 228 tests across every MAX-18-touched test file, re-run this session. | §4 |

Every regression-matrix item passes using the exact, unmodified test
files already in the archive — this audit added no new test files and
changed none.

## 4. MAX-18 complete workflow audit

| Item | Audited behavior | Result | Evidence |
|---|---|---|---|
| **Theme** | Edits set `dirty` (`value !== savedBaseline`); a successful save clears it; a failed save preserves it. | **Pass** | `useSettingsFieldSave.test.tsx` |
| **Export Directory** | Same `useSettingsFieldSave` mechanism as Theme, plus its own directory-browse integration (`exportDirectoryBrowse.ts`). | **Pass** | `useSettingsFieldSave.test.tsx`; `exportDirectoryBrowse.test.ts` (7 tests); `ExportDirectoryControl.live.test.tsx`, `ExportDirectoryControl.browse.test.tsx` (17 tests combined) |
| **VirusTotal** | Edit-buffer-only `dirty` (non-empty check, never a stored-value diff, since the value is never read back); save clears the buffer on success, preserves it on failure for retry. | **Pass** | `useVirustotalKeySave.ts`; `VirustotalControl.live.test.tsx` |
| **Multiple dirty fields** | `computeSettingsDirty`'s OR over three flags validated across all 8 boolean combinations, including "returns to false only once every flag returns to false"; re-confirmed end-to-end (Theme + Export Directory both dirty still blocks navigation, Leave discards both together). | **Pass** | `settingsDirty.test.ts` (7 tests); `useSettingsPageDirty.test.tsx` (13 tests); `settingsNavigationGuard.live.test.tsx` describe block 7 |
| **Successful save** | Clears the relevant control's own dirty flag; once every control is clean, the aggregate goes false and both guards (in-app, browser) release. | **Pass** | `useSettingsFieldSave.test.tsx`; `useVirustotalKeySave` success branch; `settingsNavigationGuard.live.test.tsx` describe block 8 |
| **Failed save** | Preserves the edit buffer and keeps `dirty` true for both credential and non-credential controls — independently re-confirmed in Phase 2B-6 and re-run clean this session. | **Pass** | `useSettingsFieldSave.test.tsx` ("resolves to error... `dirty` is `true`"); `VirustotalControl.live.test.tsx`; `settingsNavigationGuard.live.test.tsx` describe block 9 |
| **Stay** | Dismisses the confirmation dialog, keeps the route on Settings, preserves the edit; Escape produces the identical result. | **Pass** | `settingsNavigationGuard.live.test.tsx` describe blocks 3, 13 |
| **Leave** | Navigates to the originally-attempted destination; a later visit to Settings is not falsely dirty (guard store cleared on unmount). | **Pass** | `settingsNavigationGuard.live.test.tsx` describe block 4 |
| **Sidebar** | `NavLink`'s `onClick` consults `requestNavigation()` before any default navigation; blocked while dirty, allowed when clean; the already-active Settings link is never intercepted. | **Pass** | `app/navigation/NavigationGroup.tsx`; `settingsNavigationGuard.live.test.tsx` describe blocks 2, 11 |
| **CommandPalette** | `handleNavigate` consults the same guard before `navigate()`; blocked while dirty, allowed when clean. | **Pass** | `app/commandPalette/CommandPaletteContainer.tsx`; `settingsNavigationGuard.live.test.tsx` describe block 10 |
| **History where supported** | Stay commits no history entry (hash never changes); Leave commits exactly the confirmed destination. | **Pass** | `settingsNavigationGuard.live.test.tsx` describe block 12 |
| **beforeunload** | Registers only while dirty, never duplicates across re-renders, removes on clean/unmount/remount — independently audited in full in Phase 2B-5, re-run clean this session with no source change since. | **Pass** | `useSettingsBeforeUnloadGuard.test.tsx` (16 tests); Phase 2B-5's own audit |
| **Focus** | Dialog receives focus the moment it becomes pending, restores it to the pre-trigger element on Stay/Escape, keeps keyboard focus contained (Tab/Shift+Tab wrap) while open, and never lets focus fall to `document.body`. | **Pass** | `SettingsNavigationGuardDialog.live.test.tsx` describe blocks "focus entry", "keyboard focus containment" |
| **Cleanup** | Guard store's `dirty` flag is unconditionally cleared on `SettingsPage` unmount regardless of cause; `beforeunload` listener is unconditionally removed on unmount; neither can outlive the component instance that set them. | **Pass** | `useSettingsNavigationGuardSync.test.tsx` (7 tests); `useSettingsBeforeUnloadGuard.test.tsx` §5–6 |
| **Repeated cycles** | Rapid/repeated navigation attempts re-target a single open confirmation rather than opening a second; multiple synchronous clicks never open more than one dialog; dismiss/reappear and dirty→clean→dirty cycles all behave correctly on each repetition. | **Pass** | `settingsNavigationGuard.live.test.tsx` describe blocks 5, 6; `useSettingsBeforeUnloadGuard.test.tsx` §4 ("dirty → clean → dirty again"); `RestartExhaustedNotification.live.test.tsx` TEST 6 |

**Totals for this section:** 22 test files, 228 tests, all passing,
re-run in this session against the unmodified Phase 2B-6 source.

## 5. Scope audit

| Item | Result | Evidence |
|---|---|---|
| **MAX18-F-02** | Not introduced. No reference to this finding ID appears anywhere in `frontend/src` outside historical audit documentation (`docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-7.md` and the Phase 2A final-implementation doc), both of which record it as "no match" / out of scope, not as something implemented. | `grep -rln "MAX18-F-02"` across the repo |
| **MAX17-F-02** | Not introduced. Same pattern — referenced only in prior audit docs recording it as explicitly deferred/out of scope for MAX-17 and MAX-18 alike, never implemented. | `grep -rln "MAX17-F-02"` across the repo |
| **MAX9-F-01** | Not fixed. `frontend/package.json`'s `description` field still reads the same stale text every prior phase back to MAX-9 has recorded verbatim ("Analyze, Risk, and Settings remain mock/placeholder..."), independently re-read this session. | `package.json`'s `description` field, read directly this session |
| **High Contrast Dark** | Not newly introduced as a feature. `"High Contrast Dark"` is a pre-existing string in `ThemeControl.tsx`'s `THEME_OPTIONS` array, present since Part 2B-1/MAX-12 (per that file's own doc comment: "the only two theme values the established legacy Qt implementation supports... no light theme, no new theme architecture"). MAX-18 did not touch this array or add any theming logic — its only change to `ThemeControl.tsx` was adding the `onDirtyChange` prop/effect. | `ThemeControl.tsx` lines 5–12 (doc comment + `THEME_OPTIONS` constant) |
| **DataTable virtualization** | Not introduced. A repository-wide search for `virtualiz` (case-insensitive stem, catching "virtualize"/"virtualization"/"virtualized") returned zero matches anywhere in `frontend/src`. | `grep -rli "virtualiz"` → no results |
| **Backend changes** | Not introduced. A repository-wide search for `MAX-18`/`MAX18` under `app/` (the Python backend) returned zero matches. | `grep -rln "MAX-18\|MAX18" app/` → no results |
| **Rust/Tauri changes** | Not introduced. Same search under `src-tauri/` returned zero matches — MAX-18's `keystore_set_secret` Tauri command (referenced by `setVirustotalApiKey`) is the pre-existing, already-approved (ADR-008/Part 7/Part 8) command; nothing under `src-tauri/src/` was touched by this finding's own work. | `grep -rln "MAX-18\|MAX18" src-tauri/` → no results |
| **AI** | Not introduced. `package.json`'s dependency list is unchanged from every prior phase this arc has recorded: `@tauri-apps/api`, `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-fs`, `react`, `react-dom`, `react-router-dom` (deps) and `@tauri-apps/cli`, `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `jsdom`, `typescript`, `vite`, `vitest` (devDeps) — no LLM/AI SDK of any kind. | `package.json` dependency/devDependency lists, read directly this session |
| **Unrelated redesign** | Not introduced. Every file MAX-18 touched (enumerated below) sits inside `pages/settings/`, `app/shell/`, `app/navigation/`, or `app/commandPalette/` — the exact surfaces a Settings-unsaved-changes guard needs. No Dashboard, Investigations, Investigation Workspace, Reports, or Analyze page file carries any MAX-18 reference. | `grep -rl "MAX-18\|MAX18" frontend/src` (excluding tests) — 15 files, all within the four directories above |
| **Architecture rewrite** | Not introduced. `settingsNavigationGuardStore.ts`'s own doc comment explicitly records the decision *against* introducing a generic global unsaved-changes framework or a React-context-based architecture, in favor of a narrow, Settings-specific singleton — the opposite of a rewrite. `npm run build`'s emitted chunk list (§2) matches the same page-per-chunk structure (`DashboardPage`, `InvestigationsPage`, `ReportsPage`, `AnalyzePage`, `InvestigationWorkspacePage`, `SettingsPage`, `DataTable`, etc.) this project has used throughout, with no new or renamed top-level chunk. | `settingsNavigationGuardStore.ts` doc comment; `npm run build` output |

**Full enumeration of every source file MAX-18 touched** (15 files, all
inside the four expected directories):
`app/commandPalette/CommandPaletteContainer.tsx`,
`app/navigation/NavigationGroup.tsx`,
`app/shell/SettingsNavigationGuardDialog.tsx`, `app/shell/AppShell.tsx`,
`pages/SettingsPage.tsx`,
`pages/settings/useSettingsNavigationGuardSync.ts`,
`pages/settings/useVirustotalKeySave.ts`,
`pages/settings/VirustotalControl.tsx`, `pages/settings/settingsDirty.ts`,
`pages/settings/useSettingsNavigationGuardState.ts`,
`pages/settings/useSettingsBeforeUnloadGuard.ts`,
`pages/settings/ExportDirectoryControl.tsx`,
`pages/settings/settingsNavigationGuardStore.ts`,
`pages/settings/useSettingsPageDirty.ts`, `pages/settings/ThemeControl.tsx`.

This audit itself made no implementation changes — every check above
was performed by reading source and re-running the existing,
unmodified test suite.

## 6. Test quality inspection

| Criterion | Result | Evidence |
|---|---|---|
| **Meaningful behavioral coverage** | Met. 228 tests across 22 files exercise every branch of the MAX-18 workflow (§4), not just the happy path — failure/retry, unmount-while-dirty, remount, repeated cycles, and every non-trivial combination of the three dirty flags are all directly exercised, not merely implied. | §3, §4 |
| **Real DOM behavior** | Met. The full-app tests (`settingsNavigationGuard.live.test.tsx`, `routeFocus.live.test.tsx`, `SettingsNavigationGuardDialog.live.test.tsx`) render the real `<App/>` with a real `HashRouter` and real `AppShell`, and drive it via real DOM events (`.click()`, keydown dispatch) — not a shallow renderer or a synthetic prop-callback harness. | File headers/render helpers in each |
| **Actual focus assertions** | Met. `document.activeElement` is read directly and compared against a specific expected element 18 times across the two files checked (`settingsNavigationGuard.live.test.tsx`: 6, `SettingsNavigationGuardDialog.live.test.tsx`: 12) — never inferred from a mock call or a state flag standing in for focus. | `grep -c "document.activeElement"` on both files |
| **No vacuous assertions** | Met. The only bare `toBeTruthy()` calls found in the MAX-18 test set (`SettingsNavigationGuardDialog.live.test.tsx`, checking `aria-labelledby`/`aria-describedby` are non-empty before dereferencing them via `getElementById` on the next line) are a legitimate existence check ahead of a real content assertion, not a stand-in for one. No `expect(true)`-style filler found anywhere in the set. | Manual read of the two `toBeTruthy()` call sites |
| **No weakened existing tests** | Met, so far as this session can verify without a pre-MAX-18 baseline to diff against. A repository-wide search for `.skip(`, `.todo(`, `xit(`, `xdescribe(`, `it.only(`, or `describe.only(` — every mechanism Vitest offers for silently disabling or narrowing a test — found zero matches anywhere in the entire frontend suite (not just MAX-18's own files). Combined with §2's exact-baseline test count (1368, unchanged across Phase 2B-4 through this phase), there is no evidence of any test having been weakened, skipped, or narrowed at any point in this arc. | `grep -rn ".skip(\|.todo(\|xit(\|xdescribe(\|it.only(\|describe.only("` across `frontend/src` → no results |
| **No secret leakage** | Met — re-confirmed. Phase 2B-6's full ten-surface VirusTotal secret audit already established this; this session's re-run of the same test files (`VirustotalControl.live.test.tsx`, `SettingsNavigationGuardDialog.live.test.tsx`) reproduces the same passing results with no source change since, including the byte-for-byte dialog-text assertion and the failed-save error-banner assertion that explicitly checks the entered fixture value is absent from the rendered error text. | Phase 2B-6 audit (§3 of that document); this session's test re-run |
| **No excessive mocking of the behavior under audit** | Met. `settingsNavigationGuard.live.test.tsx` mocks exactly two seams — `useSettings` (the `get_settings` load) and `runCommand`/`setVirustotalApiKey` (the backend write calls) — both genuinely external to the frontend and appropriate to stub. Every piece of behavior actually under audit (routing, the guard store, the confirmation dialog, dirty aggregation, focus management) runs unmocked, through real React state and real DOM. `useSettingsBeforeUnloadGuard.test.tsx` similarly spies on (rather than replaces) `window.addEventListener`/`removeEventListener`, capturing and directly invoking the real registered handler rather than asserting against a mock standing in for it. | `vi.mock` call sites in `settingsNavigationGuard.live.test.tsx`; spy (not replacement) usage in `useSettingsBeforeUnloadGuard.test.tsx` |

## 7. Conclusion

All four full-verification commands produced clean results with no
drift from the established baseline (1368 tests, 0 typecheck errors, a
clean production build). Every item in the MAX-13 through MAX-18
regression matrix passes using the existing, unmodified test suite. The
complete MAX-18 workflow — both real Settings controls, the credential-
only VirusTotal control, every combination of simultaneously-dirty
fields, success and failure paths, Stay/Leave/Escape, both in-app
navigation triggers, history behavior, the browser `beforeunload`
guard, focus management, cleanup, and repeated cycles — is
independently verified passing, backed by 228 currently-passing tests
across 22 files. The scope audit found no trace of any of the ten
forbidden items: two explicitly-tracked finding IDs remain correctly
un-implemented, one long-standing documentation-only finding remains
correctly un-fixed, "High Contrast Dark" is a pre-existing legacy
option string untouched by MAX-18's own changes, and no virtualization,
backend, Rust/Tauri, AI, unrelated-redesign, or architecture-rewrite
footprint exists anywhere in the fifteen files MAX-18 actually touched.
The MAX-18 test suite itself passes every quality check this
checkpoint asks for: real DOM behavior, genuine focus assertions, no
vacuous or weakened tests, no secret leakage, and mocking confined to
the genuine backend seam rather than the behavior under audit. This
Phase 2B audit made no implementation changes of its own.

**Verdict: `PASS — READY FOR PHASE 2B-8`**
