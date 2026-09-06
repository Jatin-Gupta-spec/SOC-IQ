# SOC-IQ Frontend MAX-18 — Phase 2A-5 Audit

**MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.**
**This checkpoint: browser `beforeunload` protection, additive to the
in-app SPA navigation guard completed through Phase 2A-4.**

## Baseline

| | |
|---|---|
| Supplied file | `SOC-IQ-FRONTEND-MAX-18-2A-4-FULL-PROJECT.zip` |
| Pre-change verification | `npm ci` clean; `npx vitest run` — 96 test files, 1352 tests, 0 failed; `npx tsc --noEmit` — 0 errors |

Re-ran the full suite from the supplied zip before changing anything;
counts matched the 2A-4 audit doc's own claims exactly, so this
checkpoint proceeded from a confirmed-clean starting point rather than
an assumed one.

## What was read before writing any code

`SettingsPage.tsx`, `useSettingsPageDirty.ts`,
`useSettingsNavigationGuardSync.ts`, and `settingsNavigationGuardStore.ts`
were all read directly to confirm what already exists before adding
anything: `settingsDirty` (Phase 2A-2's aggregate of the three real
controls' own dirty flags) is the one boolean `SettingsPage` already
computes and already forwards to `settingsNavigationGuard` via
`useSettingsNavigationGuardSync` (Phase 2A-3). That in-app guard is
entirely internal to this application's own router/command-palette
call sites (`NavigationGroup`, `CommandPaletteContainer`) — it is
never consulted by, and has no way to intercept, a tab close, window
close, reload, or a browser-chrome navigation to a different URL.
Those are the "leave the SPA/browser context entirely" cases this
checkpoint's brief calls out, and none of the existing 2A-3/2A-4 work
covers them — confirmed by grep that no `beforeunload` listener exists
anywhere in `frontend/src` before this change.

## Design decision: forward the same aggregate, don't duplicate logic

The new hook, `useSettingsBeforeUnloadGuard`, takes the exact same
`settingsDirty` boolean `SettingsPage` already passes to
`useSettingsNavigationGuardSync` — no new dirty-tracking state, no new
combinator, no read of the three per-control flags individually. It
also does not read from or write to `settingsNavigationGuard`: the
task brief frames this as *additive* to the in-app guard, and the two
are mechanistically independent (one intercepts this app's own route
changes before they happen; the other intercepts the browser's own
unload sequence), so there is no shared state between them to
introduce or keep in sync.

## Changes

### `frontend/src/pages/settings/useSettingsBeforeUnloadGuard.ts` (new)

One hook, one `useEffect` keyed on `settingsDirty`:

```ts
useEffect(() => {
  if (!settingsDirty) {
    return;
  }
  window.addEventListener("beforeunload", handleBeforeUnload);
  return () => {
    window.removeEventListener("beforeunload", handleBeforeUnload);
  };
}, [settingsDirty]);
```

`handleBeforeUnload` calls `event.preventDefault()` (the modern,
spec-correct trigger for the browser's native prompt) and sets
`event.returnValue = ""` (legacy-engine compatibility only, per MDN's
own documented convention for this event) — never a value derived
from any Settings field. This satisfies the task brief's full
lifecycle requirement without any additional bookkeeping:

- **Register only while dirty** — the early return on `!settingsDirty`
  means no listener is ever added for a clean render.
- **Remove when clean** — React's own cleanup-then-rerun rule for a
  changed dependency tears down the previous effect's listener (via
  its returned cleanup) before evaluating the new one; going
  dirty→clean simply hits the early-return branch on the new run,
  which registers nothing, and the old listener has already been
  removed.
- **Remove on unmount** — the same cleanup function React always runs
  on unmount, no separate handling needed.
- **Never duplicate** — the effect's dependency array is
  `[settingsDirty]` alone, so React does not re-run it (and therefore
  does not re-add the listener) for any re-render that leaves
  `settingsDirty`'s value unchanged, regardless of how many times or
  for what reason such a re-render happens.
- **Not a permanent global listener** — the listener only exists for
  the lifetime of a `true` `settingsDirty` value on a mounted
  `SettingsPage`; there is no code path that registers it outside an
  active effect run gated on that value.

`handleBeforeUnload` is a module-level function (not created fresh
inside the hook body) so the exact same function reference is used
for every `addEventListener`/`removeEventListener` pair — irrelevant
to correctness here (the effect's own closure already ties each
add/remove to the right render), but keeps the hook's implementation
minimal and gives the test file one fixed target to reason about.

### `frontend/src/pages/SettingsPage.tsx` (modified)

Two-line addition: import `useSettingsBeforeUnloadGuard` and call
`useSettingsBeforeUnloadGuard(settingsDirty)` immediately after the
existing `useSettingsNavigationGuardSync(settingsDirty)` call. Nothing
else in this file changed — the same doc-comment pattern used for the
2A-2/2A-3 checkpoints was extended with one new section describing
this addition; no rendering, markup, or other hook call was touched.

### `frontend/src/pages/settings/useSettingsBeforeUnloadGuard.test.tsx` (new)

16 tests, organized under the task brief's own seven numbered
lifecycle cases plus one additional secret-exposure check:

| Requirement | Covered by |
|---|---|
| 1. clean → no listener | 2 tests: zero `addEventListener("beforeunload", …)` calls; no handler to invoke |
| 2. dirty → listener registered | 2 tests: exactly one `addEventListener` call; invoking the captured handler calls `preventDefault()` and sets `returnValue` |
| 3. dirty → repeated renders do not duplicate | 2 tests: three same-value re-renders add no further listener; the one registered handler still behaves correctly afterward |
| 4. dirty → clean removes listener | 3 tests: one `removeEventListener` call on the flip; no handler to invoke afterward; a subsequent re-dirty registers a fresh single listener |
| 5. unmount removes listener | 3 tests: removal while dirty; no spurious removal call if never registered; no handler to invoke post-unmount |
| 6. remount behaves correctly | 2 tests: a clean remount after a dirty unmount stays clean; a dirty remount registers its own single listener |
| 7. multiple dirty controls → one effective guard | 1 test: the hook only ever sees the pre-aggregated boolean, so it cannot register more than one listener regardless of how many underlying controls are dirty |
| No secret exposure | 1 test: `returnValue` is always the fixed empty string |

A jsdom-specific note, documented both in this test file's own header
comment and in the hook's doc comment: per the DOM spec, a plain
`Event`'s `returnValue` getter reflects the boolean canceled flag
(`!defaultPrevented`), not whatever value was last assigned to it —
dispatching a real `Event("beforeunload")` and reading `.returnValue`
back can only ever observe `true`/`false` in jsdom, never the literal
`""` this hook assigns. Rather than assert something jsdom cannot
faithfully represent, the tests capture the exact listener function
passed to `window.addEventListener` (via a spy) and invoke it
directly with a purpose-built mock event object whose `returnValue`
is a plain writable property. This verifies both real effects of the
hook's handler — `preventDefault()` called; `returnValue` set to `""`
— precisely, without depending on jsdom's `Event` semantics for
either.

### `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-5.md` (new)

This document.

## Why native-dialog behavior cannot be, and is not, simulated here

Per the task brief's own instruction, this is stated plainly rather
than worked around: jsdom (this project's `vitest` environment) has
no browser chrome. It does not show a native "leave site?" prompt, and
it does not implement the real unload-cancellation sequence a browser
performs when a `beforeunload` listener calls
`preventDefault()`/sets `returnValue`. This is a permanent,
well-documented limitation of jsdom (and of Vitest, which uses it) —
not a gap in this checkpoint's implementation or test coverage. What
*is* mechanically verifiable, and what the new test file actually
verifies, is everything short of the browser's own native UI: the
listener's registration/removal lifecycle, and that the registered
handler performs the two calls (`preventDefault()`, `returnValue`
assignment) that are what actually requests that native prompt from
the browser. Confirming the prompt itself appears/is suppressed
correctly requires manual testing in a real browser (e.g. the Tauri
webview or a Chromium/Firefox dev build), which is outside what an
automated Vitest suite in this environment can exercise.

## Verification results

Run from `frontend/`, from a completely fresh `npm ci`:

```
npm ci               → 159 packages installed, no errors
npx vitest run       → 97 test files, 1368 tests passed, 0 failed
npx tsc --noEmit     → no errors
npm run build        → tsc --noEmit && vite build succeeded, dist/ produced (210 modules)
```

1352 pre-existing tests (2A-4 baseline, unmodified) + 16 new
(`useSettingsBeforeUnloadGuard.test.tsx`) = 1368. No existing test was
weakened, skipped, or deleted. Module count rose from 209 to 210, consistent with exactly one new
source module (`useSettingsBeforeUnloadGuard.ts`) entering the
`SettingsPage` chunk. Confirmed by building the untouched 2A-4 upload
alongside this checkpoint's own build: `SettingsPage-*.js` grew from
11.93 kB (2A-4 baseline) to 12.12 kB (this checkpoint) — a ~0.2 kB
increase, in line with one small added hook plus its import wiring,
not a larger or unrelated change.

No transient type error was hit during development this time — the
hook's types (`BeforeUnloadEvent`, the `useEffect` cleanup-or-`void`
return shape) matched the project's existing `tsconfig.json` strictness
settings without needing any cast or suppression.

## Diff-scope audit

`diff -rq` against the untouched, unmodified `2A-4` upload (excluding
this session's own `frontend/node_modules` and `frontend/dist` build
artifacts, neither of which existed in the supplied zip) shows exactly:

- `frontend/src/pages/SettingsPage.tsx` — modified
- `frontend/src/pages/settings/useSettingsBeforeUnloadGuard.ts` — new
- `frontend/src/pages/settings/useSettingsBeforeUnloadGuard.test.tsx` — new
- `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-5.md` — new (this document)

`database/soc_iq.db` and `frontend/package-lock.json` are confirmed
byte-identical to the supplied upload. Nothing under `app/` (Python),
`src-tauri/`, `keystore-core/`, or `sidecar-core/` was read or
modified. `settingsNavigationGuardStore.ts`,
`useSettingsNavigationGuardSync.ts`,
`useSettingsNavigationGuardState.ts`,
`SettingsNavigationGuardDialog.tsx`, `NavigationGroup.tsx`,
`CommandPaletteContainer.tsx`, `AppShell.tsx`, `router.tsx`, and
`ContentRegion.tsx` are all byte-identical to the 2A-4 supplied input
— the in-app navigation guard from Phases 2A-3/2A-4 is completely
untouched by this checkpoint.

## Security check (no secret exposure)

- `handleBeforeUnload` sets `event.returnValue` to the fixed literal
  `""` only — never a value read from, or derived from, any Settings
  field's edit buffer, including the VirustotalControl API key field.
  There is no code path in this hook that reads any field value at
  all: the hook's entire input is the one `settingsDirty` boolean.
- No new logging was added anywhere in this change.
- The new test file's dedicated "no secret exposure" case asserts
  `returnValue` is exactly `""` when the handler fires, so any future
  accidental interpolation of a field value here would fail it
  immediately.

## Scope compliance

- **Only `beforeunload` lifecycle, hook integration, tests, and
  documentation**: exactly one new hook file, one new test file, a
  two-line integration change to `SettingsPage.tsx` (import + call),
  and this document. No other production file was touched.
- **No control over native confirmation text**: `handleBeforeUnload`
  never sets any string other than the fixed empty `event.returnValue`
  value, and never attempts to construct or pass a custom message —
  consistent with every modern browser already ignoring a custom
  string here and always showing its own fixed text.
- **No API keys/secrets/persisted credentials in the event message**:
  see "Security check" above.
- **No duplicate listeners, no permanent global listener**: verified
  both by the design (single effect gated on one boolean, dependency
  array of exactly `[settingsDirty]`) and by the new test suite's
  tests 3 and 7.
- **No unrelated changes**: the in-app navigation guard
  (`settingsNavigationGuardStore.ts` and everything it touches) is
  byte-identical to the 2A-4 input, confirmed by the diff-scope audit
  above.

## Final verdict

`PASS — READY FOR MAX-18 PHASE 2A-6`

`useSettingsBeforeUnloadGuard` registers a `beforeunload` listener for
exactly as long as `settingsDirty` is `true`, never duplicates it
across re-renders, and removes it both when Settings becomes clean and
on unmount — all as direct, verified consequences of a single
`useEffect` keyed on that one boolean, requiring no additional
bookkeeping. It is purely additive to, and shares no state with, the
Phase 2A-3/2A-4 in-app navigation guard, which the diff-scope audit
confirms is completely untouched. `npm ci`, `npx vitest run` (97
files / 1368 tests, 0 failed), `npx tsc --noEmit`, and `npm run build`
all pass clean from a fresh install. The one new source file and its
16-test companion are the only production and test additions; the
diff-scope audit confirms exactly 1 modified file + 3 new files (one
of them this document), nothing else touched. No API key, secret, or
other field value can reach the `beforeunload` event, verified by a
dedicated test. Native browser-dialog appearance/suppression is
explicitly documented as unverifiable in jsdom/Vitest and left to
manual browser testing, per the task brief's own instruction.
