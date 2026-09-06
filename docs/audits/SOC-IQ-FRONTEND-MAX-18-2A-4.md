# SOC-IQ Frontend MAX-18 — Phase 2A-4 Audit

**MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.**
**This checkpoint: confirmation UX + accessibility hardening of the
Settings navigation guard dialog produced in Phase 2A-3.**

## Baseline

| | |
|---|---|
| Supplied file | `SOC-IQ-FRONTEND-MAX-18-2A-3-FULL-PROJECT.zip` |
| Pre-change verification | `npm ci` clean; `npx vitest run` — 95 test files, 1333 tests, 0 failed; `npx tsc --noEmit` — 0 errors |

Re-ran the full suite from the supplied zip before changing anything;
counts matched the 2A-3 audit doc's own claims exactly, so this
checkpoint proceeded from a confirmed-clean starting point rather than
an assumed one.

## What was actually read before writing any code

`SettingsNavigationGuardDialog.tsx` was read directly rather than
trusting the 2A-3 audit doc's accessibility section at face value.
Two real gaps were found that the task brief's checklist calls out and
2A-3 had not closed:

1. **Escape had no handler.** The dialog is `role="alertdialog"`; a
   person pressing Escape (the platform-standard way to dismiss almost
   any dialog) got no response at all.
2. **No focus trap.** `aria-modal="true"` is a promise that background
   content is unreachable while the dialog is open, but nothing
   enforced it: Tab from the Leave button (or Shift+Tab from Stay, or
   from the dialog container itself immediately after it opens) could
   move focus onto the sidebar or another control sitting behind the
   backdrop. Confirmed by grep that no reusable focus-trap primitive
   exists anywhere else in this codebase before adding one here.

Everything else the task brief asks to *verify* — dialog semantics,
accessible name/description, focus entry, no strand on
`document.body`, Stay's focus return, Leave's non-interference with
MAX-17 route-change focus, no secret exposure, MAX-15/16/17
regressions — was already correctly implemented by 2A-3 and is
re-verified below, not re-implemented.

## Changes

### `frontend/src/app/shell/SettingsNavigationGuardDialog.tsx`

One new `handleKeyDown`, wired to the existing `role="alertdialog"`
element's `onKeyDown`:

- **Escape** → `preventDefault()` + `stopPropagation()`, then runs the
  exact same `handleStay()` path the Stay button already used. This
  was a deliberate choice, not the only option: Escape could
  instead have been left unhandled (as it was), or mapped to Leave.
  Mapping it to Stay is the only one of the three that can never
  silently discard a person's edit on an easily-mis-hit key, matching
  the task brief's "no ambiguous or misleading result" spirit even
  though that rule is literally about button wording.
- **Tab / Shift+Tab** → a minimal, dependency-free wrap confined to
  this component: computes the dialog's focusable elements
  (`button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])`,
  currently just the two buttons) on each keypress, and redirects
  Tab-from-last → first, Shift+Tab-from-first-or-from-the-dialog-
  container → last. The dialog-container case matters because
  `dialogRef` is `tabIndex={-1}` and is the *initial* focus target
  (per 2A-3's existing design) — without handling it explicitly, the
  very first Shift+Tab after opening would jump straight past both
  buttons to whatever precedes the dialog in the DOM.

No other line in this file changed. `dialogRef`'s initial-focus
target (the container itself, not a button), the Stay/Leave click
handlers, and the effect that captures/restores
`previouslyFocusedRef` are all untouched.

### `frontend/src/app/shell/SettingsNavigationGuardDialog.live.test.tsx` (new)

Isolated component-level tests — a fresh `SettingsNavigationGuardStore`
instance per test (never the shared singleton), wrapped only in the
`MemoryRouter` the component's `useNavigate()` call requires (mirroring
`CommandPaletteContainer.live.test.tsx`'s own precedent for a
router-dependent component tested without the whole app around it).
15 tests:

| Requirement | Covered by |
|---|---|
| Dialog semantics / accessible name & description | "uses role=alertdialog with aria-modal, and its own visible heading/body name it" |
| Destructive consequence understandable, unambiguous action labels | "communicates the destructive consequence in visible/accessible text, not styling alone" |
| No secret exposure | "never renders a VirusTotal API key or other secret value in the dialog" (asserts the dialog's entire text content, not just a substring check) |
| Focus enters correctly | "moves focus onto the dialog the moment it becomes pending" |
| Focus never falls to `document.body` | "never leaves focus stranded on document.body" |
| Escape has an intentional result | "dismisses the confirmation without discarding the pending edit (same result as Stay)" |
| Escape → focus return | "returns focus to the previously focused element, exactly like Stay" |
| Stay returns focus appropriately | "restores focus to whatever had it before the dialog opened" |
| Leave allows route-change focus behavior | two tests — see "A finding worth recording" below |
| Keyboard navigation / focus containment | three Tab/Shift+Tab tests, including the dialog-container edge case |
| Keyboard activation | confirms Stay/Leave are real `<button type="button">` elements (native Enter/Space activation is a platform guarantee for these, not something this component needs to implement), plus a click-after-keyboard-focus check |

### `frontend/src/app/shell/settingsNavigationGuard.live.test.tsx`

Two new `describe` blocks added to the existing full-app suite (real
`App`, real `HashRouter`, real `AppShell`), continuing its existing
numbering:

- **"13. Escape -> Stay (Phase 2A-4)"** — Escape on a real, dirty,
  fully-composed Settings page dismisses the dialog, keeps the route
  on Settings, and preserves the in-progress edit; a second test
  confirms Escape doesn't leave the guard stuck (a later navigation
  attempt still opens a fresh confirmation).
- **"14. keyboard focus containment (Phase 2A-4)"** — Tab from the
  real Leave button does not escape into the real sidebar behind the
  backdrop; a second test confirms focus is never on `document.body`
  while the confirmation is pending, against the real composed tree.

Nothing else in this file changed — tests 1–12 and the MAX-15/16/17
regression blocks are untouched.

## A finding worth recording (isolated-test correction, not a
production bug)

The first draft of the "Leave allows route-change focus behavior to
occur" isolated test asserted that `document.activeElement` would
*not* be the old trigger element after Leave. That assertion was
wrong, and the isolated-test run caught it (not a later regression):
`SettingsNavigationGuardDialog.tsx`'s restore-on-idle effect does not
distinguish Stay from Leave — it restores focus to whatever
previously had it, if that element is still in the document, for
*either* path. In the full app this is invisible because Leave
triggers a real route change, and `ContentRegion`'s own MAX-17
route-change focus effect fires afterward and wins (already verified
by the pre-existing MAX-17 regression test in
`settingsNavigationGuard.live.test.tsx`). In this file's isolated
setup, nothing unmounts the trigger, so the guard's own restore step
is the last thing to run and legitimately does restore focus to it.

The test was corrected to assert the two things that are actually
true and actually matter: (1) when the trigger is still present,
Leave restores focus to it exactly like Stay would — documented
inline as the real, existing contract, not a Leave-specific
guarantee; and (2) when the trigger no longer exists (simulating a
route change having already unmounted it), the restore step safely
no-ops rather than throwing or stranding focus. No production code
changed as a result of this correction — the component's behavior was
already correct; only the test's expectation was wrong.

## Verification results

Run from `frontend/`, from a completely fresh `npm ci`:

```
npm ci               → 159 packages installed, no errors
npx vitest run       → 96 test files, 1352 tests passed, 0 failed
npx tsc --noEmit     → no errors
npm run build        → tsc --noEmit && vite build succeeded, dist/ produced (209 modules)
```

1333 pre-existing tests (2A-3 baseline, unmodified) + 15 new
(`SettingsNavigationGuardDialog.live.test.tsx`) + 4 new (tests 13/14
in `settingsNavigationGuard.live.test.tsx`) = 1352. No existing test
was weakened, skipped, or deleted.

One transient `tsc --noEmit` error was hit and fixed during
development: the project's `noUncheckedIndexedAccess` flagged
`focusable[0]`/`focusable[focusable.length - 1]` as possibly
`undefined` in the new Tab-trap code; fixed with an explicit cast
after the existing `focusable.length === 0` early-return already
guarantees both indices are in range. No other type error was found
or introduced.

## Diff-scope audit

`diff -rq` against the untouched, unmodified `2A-3` upload (after
removing this session's own `frontend/node_modules` and
`frontend/dist` build artifacts, neither of which existed in the
supplied zip) shows exactly:

- `frontend/src/app/shell/SettingsNavigationGuardDialog.tsx` — modified
- `frontend/src/app/shell/settingsNavigationGuard.live.test.tsx` — modified
- `frontend/src/app/shell/SettingsNavigationGuardDialog.live.test.tsx` — new
- `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-4.md` — new (this document)

`database/soc_iq.db` and `frontend/package-lock.json` are confirmed
byte-identical to the supplied upload. Nothing under `app/` (Python),
`src-tauri/`, `keystore-core/`, or `sidecar-core/` was read or
modified. `router.tsx` and `ContentRegion.tsx` remain untouched from
2A-3.

## Regression checks (MAX-15 / MAX-16 / MAX-17)

Re-run unchanged from 2A-3, all still passing:

- MAX-15 (command palette focus restore) — "still restores focus to
  the trigger after closing the palette on a clean Settings page"
- MAX-16 (restart-exhausted notification) — "still mounts and remains
  independent of the navigation guard dialog"
- MAX-17 (route-change focus management) — "still focuses the
  destination page's main landmark after a guard-confirmed Leave"

None of this checkpoint's changes touch `CommandPalette.tsx`,
`CommandPaletteContainer.tsx`, `RestartExhaustedNotification.tsx`, or
`ContentRegion.tsx` — all three regressions were re-verified rather
than assumed safe by scope alone.

## Secret exposure check (VirusTotal API key)

- `SettingsNavigationGuardDialog`'s rendered text remains exactly the
  two static strings ("Unsaved changes" / the fixed discard-warning
  description) plus the two button labels — nothing from any control's
  edit buffer, including the VirusTotal key field, is interpolated
  into it. The new isolated test asserts the dialog's *entire* text
  content verbatim, not just a substring check, so any future
  accidental interpolation would fail it immediately.
- No new logging was added anywhere in this change.
- `requestNavigation()`'s pending state carries only a `boolean` and a
  route path string (already public in `NAVIGATION_ITEMS`/`COMMANDS`)
  — unchanged from 2A-3, not touched by this checkpoint.

## Scope compliance

- **No `beforeunload`**: not added.
- **No backend/Rust/Tauri**: no file under `app/`, `src-tauri/`,
  `keystore-core/`, or `sidecar-core/` was read or modified.
- **No architecture rewrite**: `settingsNavigationGuardStore.ts`,
  `useSettingsNavigationGuardSync.ts`,
  `useSettingsNavigationGuardState.ts`, `NavigationGroup.tsx`,
  `CommandPaletteContainer.tsx`, `AppShell.tsx`, `router.tsx`, and
  `ContentRegion.tsx` are all byte-identical to the 2A-3 supplied
  input.
- **No unrelated UI redesign**: `SettingsNavigationGuardDialog.css` is
  untouched — no new token, color, spacing, or motion value was
  introduced; the new keyboard behavior needed no new markup beyond
  the `onKeyDown` prop on the existing `role="alertdialog"` element.
- **No F-02, no deferred items**: this checkpoint touches only the
  2A-3 dialog's confirmation UX and accessibility; MAX-18's browser
  back/forward limitation (documented in the 2A-3 audit's own "Known
  limitations" section) is unchanged and was not attempted here, per
  strict scope.

## Final verdict

`PASS — READY FOR MAX-18 PHASE 2A-5`

Escape and Tab/Shift+Tab focus containment — the two real gaps found
by reading the 2A-3 dialog directly rather than trusting its own audit
doc — are now implemented, confined to
`SettingsNavigationGuardDialog.tsx`, and verified by both a new
isolated component test file (15 tests) and two new full-app
regression blocks (4 tests) against the real composed application.
Every other accessibility property the task brief asks to verify was
already correct in 2A-3 and is re-confirmed here rather than assumed.
`npm ci`, `npx vitest run` (96 files / 1352 tests, 0 failed),
`npx tsc --noEmit`, and `npm run build` all pass clean from a fresh
install. Diff-scope audit against the untouched 2A-3 upload confirms
exactly 2 modified files + 2 new files (one of them this document),
nothing else touched. MAX-15/16/17 regressions re-verified passing.
No VirusTotal key or other secret value appears anywhere in the
dialog's rendered output, asserted verbatim by a new test.
