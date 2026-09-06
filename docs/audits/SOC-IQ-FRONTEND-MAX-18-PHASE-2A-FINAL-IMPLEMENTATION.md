# SOC-IQ FRONTEND — MAX-18 Phase 2A-8: Final Integration & Release Gate

**Finding:** MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.
**Status:** Final Phase 2A checkpoint. Phase 2B is explicitly out of scope for this document.

## 1. Baseline & artifact identity

| Item | Value |
|---|---|
| Supplied input archive | `SOC-IQ-FRONTEND-MAX-18-2A-7-FULL-PROJECT.zip` |
| Supplied archive SHA-256 | `f0e0d9784369f6a16d2f749c76428bc29f734336dbdbbfac5f766003068caccc` |
| Claimed provenance (per 2A-7 doc) | Output of Phase 2A-7, itself built on 2A-6 → 2A-5 → … → the MAX-17 baseline |

**Disclosure:** this session was given only the single zip above. No separate
`MAX-17`-labeled baseline archive was supplied to this checkpoint, so a
byte-for-byte `diff -rq` against the actual MAX-17 artifact — as the 2A-7 doc
performed against *its* inputs — could not be independently repeated here.
What this checkpoint *can* and does verify independently, without relying on
any prior checkpoint's claims: the current source as extracted from the
supplied zip, by direct inspection, full test execution, typecheck, and
build, plus an mtime-based drift check (below) as a proxy for "what changed
recently" in the absence of a second archive to diff against.

## 2. Defect reproduction — before/after

The defect (MAX18-F-01) is: editing a Settings control and then navigating
away discards the edit with no warning. Verified by direct code inspection
and by the project's own `.live.test.tsx` suites (not just running them
green — reading what they assert):

| Scenario | Mechanism verified | Result |
|---|---|---|
| A — edit Theme, navigate away | `useSettingsFieldSave` sets `dirty` when `value !== savedBaseline`; `useSettingsPageDirty` folds all three controls into one `settingsDirty`; `NavigationGroup`'s link `onClick` calls `settingsNavigationGuard.requestNavigation(path)` before navigating | Confirmation shown |
| B — edit Export Directory, navigate away | Same aggregate/guard path as A, second control | Confirmation shown |
| C — edit VirusTotal key, navigate away | Same aggregate path via `useVirustotalKeySave`; `SettingsNavigationGuardDialog` renders only a fixed, generic "Unsaved changes… Leaving now will discard them" message — no field value, including the key, is read into the dialog | Confirmation shown, key never exposed |
| D — edit multiple controls, navigate | `computeSettingsDirty`/`useSettingsPageDirty` OR-combine the three per-control dirty flags into one boolean; the guard and dialog only ever see that one boolean, not a per-control list | One coherent confirmation |
| E — edit → Save succeeds → navigate | `useSettingsFieldSave.save()` sets `savedBaseline = valueAtRequestTime` on success, so `dirty` becomes `false`; `requestNavigation` returns `"allowed"` when `!dirty` | No confirmation |
| F — edit → Save fails → navigate | On rejection, `useSettingsFieldSave` sets `saveStatus: "error"` but does **not** update `savedBaseline` — `dirty` remains `true` | Confirmation remains active |

Pre-implementation behavior (i.e., with the guard store/dialog/hook absent)
is documented, not independently reproduced in this checkpoint — reverting
the fix to reproduce the "before" state would itself be an unrequested
source change, which the final-diff-audit section of the task brief
prohibits. The "before" state is established instead by the 2A-1 checkpoint
doc's own reproduction record and by the absence of any guard code prior to
these five files' introduction.

## 3. Navigation coverage

| Surface | Verified via |
|---|---|
| Sidebar (`NavigationGroup`) | `onClick` gate at `NavigationGroup.tsx:53`; own test suite |
| Command palette (`CommandPaletteContainer`) | `handleNavigate` gate at `CommandPaletteContainer.tsx:54`; own test suite |
| Normal SPA navigation | Both of the above are the app's only two navigation triggers outside the routed page itself; both gated |
| History (`popstate`/back-forward) | **Explicitly out of scope**, documented in `settingsNavigationGuardStore.ts`'s own "No navigate-then-undo" section — see §9 |
| Leave flow | `SettingsNavigationGuardDialog`'s Leave button → `store.confirmLeave()` → `navigate(targetPath)` |
| Stay flow | Stay button / Escape → `store.cancel()`; edits untouched, dialog closes |
| Repeated navigation | `requestNavigation` while already `pending: true` re-targets `targetPath` and re-notifies rather than stacking a second dialog |
| Rapid navigation | Same code path as "repeated" — no debounce needed since the store is synchronous and idempotent per call |

## 4. Browser protection (`beforeunload`)

`useSettingsBeforeUnloadGuard(settingsDirty)`:

- Registers a listener only on the render where `settingsDirty` is `true`
  (effect keyed on that single boolean).
- Cleans up (removes the listener) on every dependency change and on
  unmount, via the effect's returned cleanup — verified by
  `useSettingsBeforeUnloadGuard.test.tsx`.
- Never registers more than one listener for a given `true` streak, since
  the effect only re-runs on a value change, not on every render.
- `event.returnValue` is fixed to `""`; no field value (including the
  VirusTotal key) is ever read into the handler.

**Documented, honest limitation (unchanged from 2A-5):** jsdom/Vitest can
dispatch a synthetic `beforeunload` event and assert `preventDefault()`/
`returnValue`, but has no browser chrome — it cannot show or suppress an
actual native "leave site?" dialog. That part of this requirement is not,
and cannot be, verified by this test suite; it requires manual verification
in a real browser build.

## 5. Accessibility

`SettingsNavigationGuardDialog`:

- `role="alertdialog"`, `aria-modal="true"`, `aria-labelledby`/
  `aria-describedby` pointing at its own visible heading/body (no duplicate
  `aria-label`).
- Focus moves to the dialog container (`tabIndex={-1}`) the instant it
  becomes pending; Stay/Escape restores focus to whatever had it
  immediately before the dialog opened (captured via
  `document.activeElement`), never stranding focus on `<body>`.
- Leave does not restore focus locally — it hands off to the destination
  route, whose focus is MAX-17's own route-change focus management
  (unaffected by this checkpoint).
- Escape is explicitly handled and mapped to the same non-destructive
  outcome as Stay.
- A minimal Tab/Shift+Tab wrap keeps focus inside the two buttons + dialog
  container while open, consistent with `aria-modal="true"`'s implied
  contract.
- No control value (Theme, Export Directory, or the VirusTotal key) is
  ever rendered into the dialog's DOM.

## 6. Regression gate

| Finding | What was re-verified | Result |
|---|---|---|
| MAX-13 (ErrorBoundary recovery) | `ErrorBoundary.live.test.tsx` | Passing, unaffected |
| MAX-14 (ErrorBoundary fallback focus) | `ErrorBoundary.live.test.tsx` | Passing, unaffected |
| MAX-15 (CommandPalette close focus restoration) | `CommandPalette.live.test.tsx`, `CommandPaletteContainer.live.test.tsx` | Passing, unaffected |
| MAX-16 (RestartExhaustedNotification dismiss focus) | `RestartExhaustedNotification.live.test.tsx` | Passing, unaffected |
| MAX-17 (Route-change destination focus) | `routeFocus.live.test.tsx`, `SettingsNavigationGuardDialog.live.test.tsx`'s own MAX-17 interplay block | Passing, unaffected |

All five remain green in the full suite run (§8) with no modification to
their own source or test files (not present in the changed-file set, §10).

## 7. Test quality audit

Inspected, not just executed:

- `settingsNavigationGuardStore.test.ts` and the `.live.test.tsx` files drive
  real DOM interaction (`fireEvent`/`userEvent`-style clicks and key
  dispatch) and assert on `document.activeElement`, not on internal state
  alone, for every focus claim in §5.
- `useSettingsBeforeUnloadGuard.test.tsx` dispatches a real
  `BeforeUnloadEvent` and asserts `defaultPrevented`/`returnValue`, rather
  than mocking `addEventListener` itself away.
- No test in the changed-file set (§10) mocks `settingsNavigationGuard`,
  `useSettingsFieldSave`, or the dialog's own rendering out of the picture —
  the store under test is a real, freshly-constructed
  `SettingsNavigationGuardStore` instance, not a stub.
- `VirustotalControl.test.tsx`/`.live.test.tsx` assert the key is never
  echoed into the DOM in cleartext outside the masked input itself; the
  guard dialog's own markup (§5) contains no field-value interpolation to
  check against in the first place.
- No test file was found weakened to obtain a green result: every
  guard/dialog/beforeunload test asserts a specific behavioral outcome
  (blocked vs. allowed, listener present vs. absent, focus target) rather
  than a vacuous "does not throw".
- No duplicate coverage masquerading as breadth: `settingsNavigationGuard.
  live.test.tsx` (integration, real router + real DOM) and
  `settingsNavigationGuardStore.test.ts` (unit, store in isolation) test
  different layers of the same feature rather than repeating one another.

## 8. Final verification — commands run in this session

```
npm ci            → added 159 packages, clean
npx vitest run    → 97 test files passed (97), 1368 tests passed (1368)
npx tsc --noEmit  → 0 errors
npm run build     → tsc --noEmit + vite build, clean, ~3.2s
```

Full, unfiltered output was captured for each command in this session; no
failures were observed, so none required investigation.

## 9. Known environmental limitations (carried forward, still accurate)

- Native `beforeunload` dialog appearance/suppression cannot be exercised in
  jsdom/Vitest (§4) — verified here at the listener-lifecycle level only;
  real-browser manual verification remains outstanding.
- Browser back/forward (`popstate`) is explicitly out of this finding's
  scope, per `settingsNavigationGuardStore.ts`'s own documented boundary —
  this guard only ever answers a pre-navigation `requestNavigation()` call
  from in-app triggers; it does not intercept in-flight history-API
  navigation.
- Two pre-existing `npm audit` dev-dependency advisories are unchanged and
  out of this checkpoint's scope (unrelated to MAX18-F-01).

## 10. Scope audit

No second archive was available to run a literal `diff -rq` against a named
MAX-17 baseline (§1). As a substitute check performed directly against the
supplied source, files under `frontend/src` newer than the project's
`README.md` (i.e., touched after the initial project scaffold) were
enumerated:

```
frontend/src/app/commandPalette/CommandPaletteContainer.tsx
frontend/src/app/navigation/NavigationGroup.tsx
frontend/src/app/router.tsx
frontend/src/app/shell/AppShell.tsx
frontend/src/app/shell/SettingsNavigationGuardDialog.css
frontend/src/app/shell/SettingsNavigationGuardDialog.live.test.tsx
frontend/src/app/shell/SettingsNavigationGuardDialog.tsx
frontend/src/app/shell/settingsNavigationGuard.live.test.tsx
frontend/src/pages/SettingsPage.tsx
frontend/src/pages/settings/settingsNavigationGuardStore.test.ts
frontend/src/pages/settings/settingsNavigationGuardStore.ts
frontend/src/pages/settings/useSettingsBeforeUnloadGuard.test.tsx
frontend/src/pages/settings/useSettingsBeforeUnloadGuard.ts
frontend/src/pages/settings/useSettingsFieldSave.ts
frontend/src/pages/settings/useSettingsNavigationGuardState.ts
frontend/src/pages/settings/useSettingsNavigationGuardSync.test.tsx
frontend/src/pages/settings/useSettingsNavigationGuardSync.ts
```

17 files, all of them either the guard/dialog/beforeunload implementation
and its own tests, or the three wiring points (`NavigationGroup`,
`CommandPaletteContainer`, `AppShell`) + `SettingsPage.tsx` + the one
pre-existing save-lifecycle file (`useSettingsFieldSave.ts`) that dirty
detection depends on.

- `frontend/src/app/router.tsx` is in this list by mtime but contains no
  `MAX-18`/`MAX18` marker and no textual reference to the guard, dialog, or
  navigation-guard store — its content shows no attributable change for
  this finding. Flagging this rather than silently omitting it: either the
  file was touched and reverted to identical content at some point in the
  2A-1…2A-7 chain, or its timestamp was refreshed by packaging/extraction
  without a content edit. Either way, nothing in its current content is
  MAX18-F-01-related, and it required no action here.
- Zero changed files under `src-tauri/src`, `app/` (Python backend),
  `keystore-core/`, or `sidecar-core/` by the same mtime check — consistent
  with "no backend/Rust/Tauri changes, no AI changes."
- No file outside the 17 above, and no deferred item named in prior
  checkpoints (MAX9-F-01, High Contrast Dark, DataTable virtualization,
  MAX17-F-02, MAX18-F-02), shows any change.

## 11. Final verdict

**IMPLEMENTATION COMPLETE — READY FOR PHASE 2B**

All defect-reproduction scenarios (A–F) behave as specified against the
current source; all in-app navigation surfaces are gated; `beforeunload`
protection is correctly scoped and lifecycle-clean within jsdom's known
limits; accessibility requirements (semantics, focus capture/restore, no
secret exposure, keyboard operation) are met by direct code inspection;
MAX-13 through MAX-17 remain green; `npx vitest run` (97/97 files, 1368/1368
tests), `npx tsc --noEmit`, and `npm run build` all pass clean from a fresh
`npm ci`; and the scope audit finds only the 17 files attributable to
MAX18-F-01 changed under `frontend/src`, with zero changes under the
backend/Rust/Tauri trees. The one open item is the standing, previously
documented jsdom limitation on native `beforeunload` dialog
appearance/suppression (§9), which is an environmental constraint, not a
defect in this implementation, and requires a manual real-browser check
outside this session rather than blocking this checkpoint.

MAX-18 is **not** declared closed by this document. Phase 2B has **not**
been started or performed here.
