# SOC-IQ Frontend MAX-18 — Phase 2A-7 Audit

**MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.**
**This checkpoint: cross-system regression + behavioral audit of the
complete Phase 2A implementation ahead of release integration. Not
the independent Phase 2B audit. No new feature, no rewrite.**

## Baseline

| | |
|---|---|
| Supplied file | `SOC-IQ-FRONTEND-MAX-18-2A-6-FULL-PROJECT.zip` |
| Supplied SHA-256 | `38fa7c75eff9c65cae20be601582ec5708e31ea90acfa201c3fc04027505bb99` |
| Supplied entry count | 856 |
| Supplied byte size | 7,306,333 (uncompressed content); 2,758,374 (archive) |
| Pre-change verification | fresh `npm ci` clean (159 packages); `npx vitest run` — 97 test files, 1368 tests, 0 failed; `npx tsc --noEmit` — 0 errors; `npm run build` — clean |

## Changed files

**None, functionally.** Diffing the extracted 2A-6 zip against the
2A-5 audit's own supplied upload found only the expected new audit
document (`docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-6.md`) — with one
correction:

**Packaging defect found and fixed this checkpoint**: the 2A-6
output zip's `-x "*.git*"` exclusion pattern also matched (and
dropped) `.gitignore` and `.github/workflows/ci.yml`, neither of
which is version-control internals — both were present in the 2A-5
input and are ordinary repository files. This was a packaging
mistake in how the 2A-6 archive was assembled, not a source-code
change to MAX18-F-01, and not a deliberate scope decision. Both
files are restored, byte-identical to the 2A-5 input, in this
checkpoint's output. No other file was affected — every other path
in the 2A-6 upload matched the 2A-5 baseline exactly.

Net changed files in this checkpoint's output relative to the 2A-5
baseline:
- `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-6.md` — new (carried over)
- `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-7.md` — new (this document)
- `.gitignore`, `.github/workflows/ci.yml` — restored to their 2A-5
  content (present in 2A-5, wrongly absent from 2A-6, fixed here)

No file under `frontend/src`, `src-tauri/src`, `keystore-core/src`,
`sidecar-core/src`, or `app/` differs from the 2A-5 baseline.

## Workflow matrix

All 15 required workflows were traced to a specific passing test and
re-run in this checkpoint's own `npx vitest run`, not assumed from
prior audit claims:

| # | Workflow | Verified in |
|---|---|---|
| 1 | Theme edit → navigation | `settingsNavigationGuard.live.test.tsx` blocks 2/7/11 (Theme is one of the two real per-field controls exercised throughout) |
| 2 | Export Directory edit → navigation | same file, same blocks — `ExportDirectoryControl` exercised alongside Theme in block 7's "multiple dirty fields" |
| 3 | VirusTotal key edit → navigation | `SettingsPage.dirtyAggregate.live.test.tsx` "required combination matrix" (VirusTotal-only dirty case) + `settingsNavigationGuard.live.test.tsx` block 7 |
| 4 | Multiple simultaneous dirty fields | dirty-aggregate matrix (all 7 non-clean permutations) + guard block 7 |
| 5 | Successful save | dirty-aggregate "saving clears only the saved control's contribution"; guard block 8 |
| 6 | Failed save | dirty-aggregate "a failed save preserves that control's dirty contribution"; guard block 9 |
| 7 | Retry | `useSettingsFieldSave.test.tsx` / `useVirustotalKeySave.test.tsx` retry-after-error cases |
| 8 | Stay | guard block 3, block 13 (Escape-as-Stay) |
| 9 | Leave | guard block 4 (destination reached, edit discarded) |
| 10 | Sidebar navigation | guard block 11 |
| 11 | CommandPalette navigation | guard block 10 |
| 12 | History navigation where supported | guard block 12 (hash commit behavior for Stay vs. Leave) |
| 13 | Browser/tab close protection | `useSettingsBeforeUnloadGuard.test.tsx` blocks 1–7 |
| 14 | Settings remount | dirty-aggregate "unmount/remount"; guard sync test "fresh mount after unmount"; beforeunload block 6 |
| 15 | Repeated dirty/clean cycles | beforeunload "going dirty → clean → dirty again registers a fresh single listener"; guard block 13's "Escape does not leave the guard stuck" |

All 15 passed in this checkpoint's execution.

## Focus matrix — actual DOM focus assertions

Each item below is asserted with a real `document.activeElement`
check against jsdom's live DOM (via Testing Library), not a
prop/state proxy for focus. Confirmed by reading the assertions
directly, not just the test names:

- **Confirmation focus**: `SettingsNavigationGuardDialog.live.test.tsx`,
  "focus entry" — asserts focus moves onto the dialog container the
  moment `pending` becomes true, and "never leaves focus stranded on
  document.body".
- **Stay focus**: same file, "Stay returns focus appropriately" —
  asserts `document.activeElement` is restored to whatever element
  held it before the dialog opened.
- **Leave route focus**: same file, "Leave allows route-change focus
  behavior to occur" — asserts the pre-dialog trigger is not left
  focused post-Leave (the MAX-17 effect takes over), and a dedicated
  case asserts no crash/no stranding when that trigger element no
  longer exists.
- **MAX-15 CommandPalette restoration**: `CommandPalette.live.test.tsx`
  "restores focus to the previously focused control on Escape" /
  "...on backdrop dismiss" / "...when the previous target survives"
  each assert `document.activeElement` against the captured
  pre-open element; `CommandPaletteContainer.live.test.tsx` and both
  `routeFocus.live.test.tsx` Test 4 and `settingsNavigationGuard.live.test.tsx`'s
  own MAX-15 regression block repeat this check in the presence of
  the new Settings guard and route-focus machinery.
- **MAX-16 notification dismissal**: `RestartExhaustedNotification.live.test.tsx`
  TEST 1–3 and TEST 6 assert `document.activeElement` is never
  `document.body` after dismiss, is never the just-removed Dismiss
  button, and falls back to a defined element when the prior target
  is detached — each a direct DOM read, not a callback-invocation
  check.
- **MAX-17 destination `<main>` focus**: `routeFocus.live.test.tsx`
  Tests 1–3 and 7 assert `document.activeElement` is the destination
  page's `<main class="page-layout">` element after sidebar,
  whole-row, and command-palette navigation, including through a
  repeated A→B→C→A sequence; `settingsNavigationGuard.live.test.tsx`'s
  own MAX-17 regression block repeats this specifically for a
  guard-confirmed Leave.

**No `document.body`-stranded-focus failures** were found across any
of the above — every test that checks for this explicitly (dialog
entry/exit, notification dismiss, palette close, guard confirm)
asserts the negative case directly rather than only asserting the
positive outcome.

## Security matrix

Re-confirmed from the 2A-6 audit's own source-level inspection,
re-verified directly against this checkpoint's extracted source
rather than carried over as a claim:

| Surface | Result |
|---|---|
| Logs | No `console.*` call anywhere in the Settings/navigation-guard/beforeunload code paths receives the VirusTotal edit-buffer value; Rust-side `eprintln!` diagnostics in `apply_secret_handoff` print only fixed strings and the keystore's own non-secret failure reason |
| Confirmation text | `handleBeforeUnload` sets `event.returnValue` to the fixed literal `""` only; `SettingsNavigationGuardDialog`'s copy is a static string with no interpolation |
| Accessibility labels | `VirustotalControl`'s `role`/`aria-*` usage carries only fixed strings and `saveStatus.message` (sourced from `describeSaveError`, never the entered key) |
| Test snapshots | No `toMatchSnapshot()` usage anywhere in the project |
| URL/query parameters | `keystore_set_secret` travels over Tauri's structured IPC `invoke()`, never a URL; the unrelated HTTP bridge (`save_settings`/`get_settings`) never carries the VirusTotal key |
| Generated documentation | This document and all prior 2A-* audits quote code shape and fixed UI copy only; no plausible VirusTotal-key-shaped token appears anywhere under `docs/` |
| Error messages | `describeSaveError` in both field-save hooks surfaces only `Error`/`KeystoreWriteError` messages or a fixed unknown-error string, never the field's own buffer |
| Serialized dirty-state metadata | `SettingsDirtyFlags`/`computeSettingsDirty` are boolean-only; the rendered `data-settings-dirty` DOM attribute carries a boolean, never a field value — asserted directly by the dirty-aggregate suite's "secret handling" case |

No occurrence of the credential value was found in any of the eight
categories, in source or in a fresh production build's output.
Secret-storage/persistence path (`keystore_set_secret`,
`RustSecretStore`, `apply_secret_handoff`'s env-var-only handoff) is
confirmed byte-identical to the 2A-5 baseline.

## Test results

```
npx vitest run  →  97 test files passed (97)
                    1368 tests passed (1368)
                    0 failed
```

Every regression named in this checkpoint's brief was located by
name and confirmed passing in this run (not carried over from a
prior audit's claim):

- **MAX-13 ErrorBoundary**: `ErrorBoundary.live.test.tsx`, "catch
  behavior" — all 4 cases pass.
- **MAX-14 ErrorBoundary focus**: same file, "focus behavior" — all
  5 cases pass, including the document.body-stranding check above.
- **MAX-15 CommandPalette restoration**: passes in
  `CommandPalette.live.test.tsx`, `CommandPaletteContainer.live.test.tsx`,
  `routeFocus.live.test.tsx` Test 4, and
  `settingsNavigationGuard.live.test.tsx`'s own regression block —
  four independent confirmations, all green.
- **MAX-16 notification dismissal**: `RestartExhaustedNotification.live.test.tsx`
  — all 5 numbered focus-management tests pass, plus a dedicated
  independence check inside the settings-navigation-guard suite.
- **MAX-17 destination `<main>` focus**: `routeFocus.live.test.tsx`
  — all 5 tests pass (Tests 1, 2, 3, 4, 7), plus the
  settings-navigation-guard suite's own MAX-17 regression block.

## Build results

```
npx tsc --noEmit  →  0 errors
npm run build     →  tsc --noEmit + vite build, clean
                      dist/assets/SettingsPage-DYYxedOf.js  12.12 kB (gzip 3.43 kB)
                      dist/assets/index-Cvz_C-Vd.js         215.66 kB (gzip 70.13 kB)
                      built in ~3.1–3.5s across repeated runs
```

`npm ci` reports 2 pre-existing `npm audit` advisories in dev
dependencies, unchanged from every prior 2A-* checkpoint and
unrelated to MAX18-F-01 — left untouched per this checkpoint's "no
unrelated cleanup" scope boundary.

## Scope audit

Diffing the extracted 2A-6 project against the 2A-5 baseline
(excluding `node_modules`/`dist`, which are build artifacts absent
from both source zips) found:

- Zero changes under `frontend/src` — every Settings/navigation-guard/
  beforeunload source and test file is byte-identical to 2A-5.
- Zero changes under `src-tauri/src`, `keystore-core/`,
  `sidecar-core/`, or `app/` (Python).
- One new file (`docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-6.md`) —
  documentation only.
- Two files (`.gitignore`, `.github/workflows/ci.yml`) missing from
  the 2A-6 upload due to a packaging-tool exclusion-pattern mistake,
  not a source edit — restored in this checkpoint's output (see
  "Changed files" above).

The implementation remains limited to MAX18-F-01's five real
production files (`settingsDirty.ts`, `useSettingsPageDirty.ts`,
`settingsNavigationGuardStore.ts` + its two hook consumers,
`SettingsNavigationGuardDialog.tsx`, `useSettingsBeforeUnloadGuard.ts`)
plus their wiring into `SettingsPage.tsx`, `NavigationGroup.tsx`, and
`CommandPaletteContainer.tsx` — all completed in Phases 2A-1 through
2A-5 and untouched since.

## Deferred items — confirmed still deferred

Grepped `frontend/src` for each named item; none appear anywhere in
source:

- **MAX9-F-01** — no match.
- **High Contrast Dark** — no match. `ThemeControl`'s option list
  (`["Dark Mode (SOC-IQ Standard)", "High Contrast Dark"]`) still
  only *offers* the label as a persisted string Theme can save; the
  frontend's own `ThemeControl.tsx` comment ("SOC-IQ currently
  renders its one standard dark theme regardless of which option is
  chosen") confirms no visual theme-switching implementation exists
  — the option is stored, never applied.
- **DataTable virtualization** — no match; `DataTable.tsx` (used by
  Reports/Investigations) shows no windowing/virtualization logic.
- **MAX17-F-02** — no match.
- **MAX18-F-02** — no match.

## Known limitations

- Native `beforeunload` dialog appearance/suppression remains
  unverifiable in jsdom/Vitest, as documented since Phase 2A-5; what
  is verified here is listener lifecycle and the handler's
  `preventDefault()`/`returnValue` behavior on a synthetic dispatch.
- Browser back/forward (`popstate`) interception remains explicitly
  out of scope, as documented in `settingsNavigationGuardStore.ts`'s
  own "No navigate-then-undo" section — this store only ever answers
  a pre-navigation `requestNavigation()` call; it does not intercept
  history-API navigation already in flight.
- The two pre-existing `npm audit` dev-dependency advisories remain
  unremediated (unrelated to MAX18-F-01, out of this checkpoint's
  scope).
- This checkpoint's packaging-defect finding (missing `.gitignore`/
  `.github`) applied to the 2A-6 *output archive* only; it never
  affected the frontend project itself, which was never packaged
  without those files prior to 2A-6.

## Final verdict

`PASS — READY FOR MAX-18 PHASE 2A-8`

All 15 required workflows, the full focus matrix (verified via real
`document.activeElement` DOM assertions with no `document.body`
stranding anywhere), and the eight-surface security matrix are
independently re-confirmed against the actual 2A-6 source in this
checkpoint, not inherited from prior audit claims. `npx vitest run`
(97 files / 1368 tests), `npx tsc --noEmit`, and `npm run build` all
pass clean from a fresh install. The scope audit confirms the
implementation remains limited to MAX18-F-01's five production files
and their three wiring points, with zero drift from the 2A-5
baseline under `frontend/src`, `src-tauri/src`, `keystore-core/`,
`sidecar-core/`, or `app/`. All five named deferred items (MAX9-F-01,
High Contrast Dark, DataTable virtualization, MAX17-F-02, MAX18-F-02)
remain absent from source. One packaging defect in the prior
checkpoint's output archive — an overbroad exclusion pattern that
also dropped `.gitignore` and `.github/workflows/ci.yml` — was found
and corrected in this checkpoint's output; it was a zip-assembly
mistake, not a source change, and no source file was affected.
