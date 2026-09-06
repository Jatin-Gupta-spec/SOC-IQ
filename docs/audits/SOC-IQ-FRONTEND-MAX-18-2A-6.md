# SOC-IQ Frontend MAX-18 — Phase 2A-6 Audit

**MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.**
**This checkpoint: edge-case stress test + security hardening review of
the complete MAX18-F-01 implementation delivered through Phase 2A-5.
No new feature direction. Verification and documentation only.**

## Baseline

| | |
|---|---|
| Supplied file | `SOC-IQ-FRONTEND-MAX-18-2A-5-FULL-PROJECT.zip` |
| Pre-change verification | `npm ci` clean (159 packages); `npx vitest run` — 97 test files, 1368 tests, 0 failed; `npx tsc --noEmit` — 0 errors; `npm run build` — clean production build |

Nothing under `frontend/src`, `src-tauri/src`, `keystore-core/src`, or
`app/` is newer than the supplied 2A-5 audit document's own timestamp
— confirmed by a filesystem-wide `find -newer` sweep before any
inspection began. The supplied zip is byte-for-byte the state Phase
2A-5 left behind; this checkpoint changed no production or test
source file.

## What this checkpoint actually is

Phase 2A-1 through 2A-5 already built and unit-tested, in order: the
pure dirty combinator (`computeSettingsDirty`), the page-level
aggregate hook (`useSettingsPageDirty`), the in-app SPA navigation
guard (`settingsNavigationGuardStore` + its React bindings +
`SettingsNavigationGuardDialog`), and the browser-native
`beforeunload` guard (`useSettingsBeforeUnloadGuard`). Reading each of
those five checkpoints' own audit documents first confirmed the
required test matrix below was not a gap to fill — it was already
built into the live test suites as the checkpoints were written,
because each prior phase's own brief already demanded exactly this
kind of edge-case coverage before it could be marked done. This
checkpoint's job was to independently verify that claim end to end
(re-run everything from a clean install, read the source directly
rather than trust prior audit prose, and grep for the specific
security properties this brief calls out) and record the result — not
to re-derive or re-implement any of it.

## Required test matrix — verified against the live suite

Every item below was located by name in the test files and confirmed
passing in this checkpoint's own `npx vitest run` (not assumed from
prior audits' claims):

**Dirty-state combinations** — `SettingsPage.dirtyAggregate.live.test.tsx`,
`describe("required combination matrix")`: all seven non-clean
permutations of the three flags (one dirty, two dirty in each of the
three pairings, all three dirty) plus the all-clean case, each
asserted against `computeSettingsDirty`'s real output.

**Save behavior** — same file, `describe("saving clears only the
saved control's contribution")`: a successful partial save (Theme
saved while Export Directory and VirusTotal stay dirty — aggregate
stays `true`), saving every dirty control in turn back to clean, a
failed save preserving that control's contribution, and a failed
VirusTotal save specifically (its buffer-non-empty dirty semantics
are structurally different from the other two controls' persisted-
value diff, so it gets its own case). `useSettingsFieldSave.test.tsx`
and `useVirustotalKeySave.test.tsx` cover retry-after-error at the
single-control level underneath this.

**Navigation** — `settingsNavigationGuard.live.test.tsx`,
numbered `describe` blocks 1 through 14: clean-navigates-immediately,
dirty-blocks-and-opens-confirmation, Stay (route/edits untouched),
Leave (destination reached, local edit discarded so a later revisit
isn't falsely dirty), repeated navigation attempts (single dialog,
re-targeted), rapid/synchronous navigation attempts (no duplicate
dialogs), multiple dirty fields at once, save-clears-protection,
failed-save-preserves-protection, CommandPalette-triggered navigation
(both blocked-while-dirty and clean-passthrough), sidebar navigation
(including the already-active-Settings-link no-op case), hash-based
history behavior (Stay commits no entry, Leave commits exactly the
confirmed destination), and Escape-as-Stay. "Return to Settings after
leaving" is the dirty-discard assertion in block 4's second test:
leaving via a confirmed Leave clears the store, so a later mount of
`SettingsPage` starts clean rather than inheriting the just-discarded
state.

**Browser lifecycle** — `useSettingsBeforeUnloadGuard.test.tsx`,
numbered `describe` blocks 1 through 7: no listener while clean,
exactly one listener once dirty (with `preventDefault()` and
`returnValue` verified on a dispatched event), repeated re-renders at
the same dirty value never duplicating the listener, dirty→clean
removing it, unmount removing it (both while dirty and, as a no-op,
while already clean), a fresh mount after a dirty unmount starting
listener-free, and — matching this brief's "one dirty field vs. all
three" concern at the browser-lifecycle layer specifically — a
`settingsDirty` that is `true` because of several controls still
yielding exactly one listener, never one per contributing control.

All of the above ran clean in this checkpoint's own execution, not
carried over from a prior audit's claim.

## Security audit — VirusTotal API key

Read directly (not inferred from comments) for this checkpoint:
`useVirustotalKeySave.ts`, `VirustotalControl.tsx`, the compiled
`useVirustotalKeySave`/`VirustotalControl` output inside
`dist/assets/SettingsPage-*.js`, `shared/api/client.ts`'s
`setVirustotalApiKey`, `src-tauri/src/keystore.rs`, and
`src-tauri/src/sidecar.rs`'s `apply_secret_handoff`. Checked against
every item this brief's "SECURITY AUDIT" section lists:

- **Logs**: `grep -rn "console\.(log|warn|error|info|debug)"` across
  `frontend/src` for any hit also mentioning `key`/`secret`/`token`/
  `password`/`value` returns nothing. The only `console.error` calls
  anywhere near this feature are generic, argument-free-of-payload
  subscriber/error logs (`SettingsNavigationGuardStore.notify`'s
  "subscriber threw", the app's top-level `ErrorBoundary`) that never
  receive the credential. On the Rust side, `keystore.rs`'s four
  commands never print anything at all; `sidecar.rs`'s two
  `eprintln!` diagnostics in `apply_secret_handoff` fire only on the
  `Unavailable`/unreachable-`InvalidInput` branches and print a fixed
  string plus the keystore's own non-secret failure reason — never
  the credential.
- **Confirmation text**: `useSettingsBeforeUnloadGuard`'s
  `handleBeforeUnload` sets `event.returnValue` to the fixed literal
  `""` only, confirmed again this checkpoint by re-reading the source
  and by its dedicated "no secret exposure" test. The in-app
  `SettingsNavigationGuardDialog`'s confirmation copy
  ("You have unsaved changes on the Settings page. Leaving now will
  discard them.") is a static string with no interpolation of any
  field value — confirmed in both `SettingsNavigationGuardDialog.tsx`
  and the compiled bundle.
- **Accessibility labels**: `VirustotalControl.tsx`'s only
  `role`/`aria-*` usage is on its status paragraphs
  (`role="status"`/`aria-live="polite"` for success, `role="alert"`
  for error) and the label text is always the fixed strings shown
  above — `saveStatus.message` (the only interpolated value in that
  region) is sourced from `describeSaveError`, which only ever
  returns `KeystoreWriteError`/`Error.message` or the fixed unknown-
  error string, never the entered key. No `aria-label` anywhere in
  this control is built from the edit-buffer value.
- **Test snapshots**: no `toMatchSnapshot()`/snapshot fixtures exist
  anywhere under `frontend/src` for this feature (or at all — this
  project uses assertion-based Testing Library queries throughout,
  confirmed by grep for `toMatchSnapshot` returning no hits).
- **URL/query parameters**: `setVirustotalApiKey` (`client.ts`) calls
  `keystore_set_secret` through Tauri's `invoke()`, which serializes
  arguments over Tauri's IPC channel (process-local, not a network
  request) as a structured payload, not a URL — there is no
  `fetch`/`XMLHttpRequest`/query-string construction anywhere in this
  path. The one place this codebase does build URLs
  (`runCommand`/`getSidecarOrigin` in `client.ts`) is the unrelated
  Python-sidecar HTTP bridge for `save_settings`/`get_settings`/
  `analyze_report`, which never carries the VirusTotal key.
- **Generated documentation**: this document and every prior 2A-*
  audit document quote only code shape, hook names, and fixed UI
  copy — never a credential value, real or example. `grep` for a
  plausible VirusTotal-key-shaped token (VirusTotal keys are 64 hex
  characters) across `docs/` returns nothing.
- **Error messages**: `describeSaveError` (both
  `useSettingsFieldSave.ts` and `useVirustotalKeySave.ts`) only ever
  surfaces `error.message` from a caught `Error`/`KeystoreWriteError`
  or a fixed unknown-error string — it never constructs a message
  from the field's own edit-buffer value. On the Rust side,
  `keystore.rs`'s `describe_error` wraps `KeystoreError`'s `Display`
  impl, which that type's own doc comment (and `keystore-core`'s unit
  tests) guarantee never contains a secret value.
- **Serialized dirty-state metadata**: `computeSettingsDirty` and
  `SettingsDirtyFlags` take and return booleans only — `virustotalKeyDirty`
  is a `boolean`, never the string it's derived from. `useVirustotalKeySave`
  computes that boolean as `value.trim().length > 0`, so even the
  buffer's length is not part of the dirty signal, only its
  non-emptiness. `SettingsPage`'s rendered output does surface the
  page-level `settingsDirty` boolean as a `data-settings-dirty`
  attribute (confirmed in the compiled bundle) — this is the
  documented, intentional "existence of unsaved changes" signal this
  brief explicitly permits ("Dirty state should represent the
  existence of unsaved changes, not expose the underlying secret");
  it carries no field value, control identity, or key content.
  `SettingsPage.dirtyAggregate.live.test.tsx`'s dedicated
  `describe("secret handling")` case asserts this directly by
  inspecting the rendered DOM for the raw edit-buffer text.

No occurrence of the credential value, in whole or in part, was found
in any of the eight categories above, in source or in the compiled
production bundle.

## Secret-storage/persistence path — unchanged

`keystore_set_secret`'s signature, its `RustSecretStore`/`SecretStore`
trait plumbing in `keystore-core`, and `apply_secret_handoff`'s
env-var-only (`Command::env`, never a CLI argument, never written to
disk by this path) handoff into the Python sidecar's process
environment are all byte-identical to the 2A-5 input — confirmed by
diff against the supplied zip. This checkpoint did not touch
`src-tauri/src/keystore.rs`, `src-tauri/src/sidecar.rs`, or any file
under `keystore-core/`.

## Regression — explicitly re-verified

All five, located by name and re-run clean in this checkpoint's own
`npx vitest run`, not carried over from prior audit claims:

- **MAX-13 ErrorBoundary**: `ErrorBoundary.live.test.tsx` —
  catch/recover/re-catch behavior intact.
- **MAX-14 ErrorBoundary focus**: same file, `describe("focus
  behavior")` — focus moves into the fallback alert on catch, never
  moves when nothing throws, and never strands on the removed "Try
  again" control after recovery.
- **MAX-15 CommandPalette focus restoration**: covered from three
  independent angles — `CommandPalette.live.test.tsx`'s own
  `describe("CommandPalette focus restoration (MAX15-F-01)")`,
  `CommandPaletteContainer.live.test.tsx`'s equivalent case, and the
  settings-navigation-guard and route-focus suites' own MAX-15
  regression blocks (a closed palette still returns focus correctly
  even with the Settings guard or route-change focus logic active
  alongside it).
- **MAX-16 notification focus restoration**:
  `RestartExhaustedNotification.live.test.tsx` — dismiss never
  strands focus on `<body>`, never re-focuses a removed control, uses
  a documented fallback when the prior target is detached, and
  handles repeated dismiss/reappear cycles without using a stale
  target; a dedicated regression block elsewhere confirms it remains
  independent of the new Settings navigation guard dialog.
- **MAX-17 route-change focus**: `routeFocus.live.test.tsx`'s own
  seven-test suite, plus dedicated regression blocks inside the
  settings-navigation-guard suite confirming a guard-confirmed Leave
  still focuses the destination's `<main>` landmark correctly.

## Full verification run (this checkpoint)

```
npm ci              → 159 packages, 0 vulnerabilities requiring action
                       (2 pre-existing dev-dependency advisories,
                       unrelated to this feature, unchanged from prior
                       checkpoints — not remediated here per this
                       checkpoint's scope: no unrelated cleanup)
npx vitest run       → 97 test files, 1368 tests, 0 failed
npx tsc --noEmit     → 0 errors
npm run build        → clean production build (tsc --noEmit + vite build)
```

Source-level security inspection (this document's "Security audit"
section above) was performed in addition to, not instead of, the
above.

## Diff-scope audit

No production or test source file differs from the supplied
`SOC-IQ-FRONTEND-MAX-18-2A-5-FULL-PROJECT.zip`. The only addition is:

- `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-6.md` — new (this document)

`database/soc_iq.db` and `frontend/package-lock.json` remain
byte-identical to the supplied upload. Nothing under `app/` (Python),
`src-tauri/`, `keystore-core/`, or `sidecar-core/` was modified.

## Scope compliance

- **No new feature**: zero production source files added, removed, or
  modified. This checkpoint is verification and documentation only.
- **No architectural rewrite**: no file under `frontend/src` was
  touched.
- **No unrelated cleanup**: the two pre-existing `npm audit`
  advisories (dev dependencies, unrelated to MAX18-F-01) were left
  exactly as found.
- **No F-02**: nothing outside the Settings dirty-state/navigation-
  guard/beforeunload feature set was inspected or changed.
- **No deferred work**: every item in the required test matrix and
  security audit was checked directly against source and the live
  test run in this checkpoint, not assumed from prior audits.

## Final verdict

`PASS — READY FOR MAX-18 PHASE 2A-7`

The complete MAX18-F-01 implementation (Phases 2A-1 through 2A-5)
passes its full required edge-case test matrix — dirty-state
combinations, partial/failed/retried saves, repeated and rapid
navigation attempts across sidebar, command palette, and browser
history, and the full `beforeunload` lifecycle including remount
safety — with 97 test files and 1368 tests green from a clean
install, `tsc --noEmit` clean, and a clean production build. A
source-level security inspection covering logs, confirmation text,
accessibility labels, test snapshots, URL/query parameters, generated
documentation, error messages, and serialized dirty-state metadata
found no path by which the VirusTotal API key value reaches any of
those surfaces, in either source or the compiled bundle; dirty state
throughout the feature is boolean-only. The existing
`keystore_set_secret` / `apply_secret_handoff` secret-storage and
handoff path is confirmed unchanged. All five named regressions
(MAX-13 through MAX-17) are independently re-verified passing. This
checkpoint added no production code — it is a verification pass
against Phase 2A-5's implementation, and its only file addition is
this document.
