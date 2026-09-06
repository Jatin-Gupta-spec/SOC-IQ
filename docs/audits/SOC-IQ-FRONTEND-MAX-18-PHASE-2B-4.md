# SOC-IQ FRONTEND — MAX-18 Phase 2B-4: Confirmation UX + Focus Accessibility Audit

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation.

## 1. Baseline integrity

| Check | Result |
|---|---|
| Input archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-3-FULL-PROJECT.zip` |
| SHA-256 (input) | `eed33c1c41f7f4084c1c83dcf3fe330fa8dfb8112be3c58ed8c6f019f1366ad5` |
| `unzip -t` | `No errors detected in compressed data` |
| Entry count | 865 |
| Byte size | 7,373,590 bytes |
| `npm ci` (frontend/) | 159 packages, clean |
| Baseline `npx vitest run` | 97 test files passed, 1368 tests passed |
| Baseline `npx tsc --noEmit` / `npm run build` | 0 errors, clean |

Baseline test/type/build results match Phase 2B-3's own recorded baseline
exactly — no drift between the two checkpoints' inputs. (This phase's
input is this session's own Phase 2B-3 output; it was independently
re-verified byte-for-byte against the delivered archive — matching
SHA-256, matching directory diff — before any further work began.)

## 2. Methodology

This phase reviewed `SettingsNavigationGuardDialog.tsx` and its two
pre-existing test files in full
(`app/shell/SettingsNavigationGuardDialog.live.test.tsx`, an isolated
component test using a private store instance and `MemoryRouter`; and
`app/shell/settingsNavigationGuard.live.test.tsx`, which drives the real,
fully-composed `<App/>`), then cross-checked their coverage against every
item in this checkpoint's brief (dialog semantics, accessible name/
description, keyboard operability, Escape, the six-point focus checklist,
and the secret-safety checklist).

Two categories of the brief's checklist were not fully exercised by the
existing suite against the real, fully-composed application (the isolated
dialog test covers focus/keyboard/secret-safety but with a synthetic
`store` and no real sidebar/router context; the full-app test covers
route changes but does not assert `document.activeElement` at every step
of the confirmation lifecycle, nor does it drive the VirusTotal control's
error path together with the guard). A temporary, independently-authored
harness (`src/app/__phase2b4_repro__.live.test.tsx`) was added to close
that gap: it renders the real `<App/>` (real `HashRouter`, real
`AppShell`) and asserts `document.activeElement` directly via real DOM
inspection at each step (pre-click, dialog-open, Stay, Leave, Escape),
plus drives a forced VirusTotal save failure alongside a dirty-navigation
attempt to check secret-safety end-to-end. Console output was intercepted
via `vi.spyOn` (while still forwarding to the real terminal) to check
directly for secret leakage into logged text, not just DOM text. After
capturing results, the harness was deleted and the full verification
suite re-run against the restored, unmodified source (§8) — zero residual
change. No production source file was edited, added to, or removed at
any point.

## 3. Confirmation UX — dialog semantics and accessible name/description

| Requirement | Result | Evidence |
|---|---|---|
| Correct dialog semantics | `role="alertdialog"`, `aria-modal="true"` | Pre-existing isolated test asserts this directly; independently re-confirmed against the real app: `role: alertdialog`, `aria-modal: true` |
| Accessible name is meaningful | `aria-labelledby` resolves to a real, visible heading | Resolved text: `"Unsaved changes"` — a plain, unambiguous name, not a generic "Confirm" or "Alert" |
| Accessible description explains the consequence | `aria-describedby` resolves to text naming the specific loss | Resolved text: `"You have unsaved changes on the Settings page. Leaving now will discard them."` — states what is at risk and what triggers loss, in plain language, not just "Are you sure?" |
| Stay is understandable | Button text is the single word `"Stay"` | Unambiguous, paired with the description above; not a vague "Cancel"/"No" |
| Leave is understandable | Button text is the single word `"Leave"`, additionally styled with the destructive/error color token (`--color-status-error`) | Meaning is carried by the text itself, not by color alone — the color reinforces rather than substitutes for the accessible label, satisfying the "not color-only" convention this codebase already applies elsewhere (`NavigationGroup.tsx`'s own doc comment on active-state, §16) |
| Keyboard users can operate both actions | Both are real `<button type="button">` elements | Confirmed via `tagName`/`getAttribute("type")` assertions — native Enter/Space activation applies with no custom keyboard handling needed for activation itself |
| Escape has intentional behavior | Escape is wired to the same, non-destructive result as Stay | `event.preventDefault()` + `event.stopPropagation()` before calling `handleStay()` — never runs `confirmLeave()`. Independently re-confirmed against the real app: dialog closes, hash stays `#/settings`, the in-progress edit value is unchanged |

All seven requirements are met, and none rely solely on the isolated
component test's synthetic store — the accessible-name/description and
Escape results above were independently re-verified against the real,
fully-composed application in this phase's own harness.

## 4. Focus audit

Using real DOM inspection (`document.activeElement`) against the real,
fully-composed `<App/>`:

| # | Check | Result |
|---|---|---|
| 1 | Focus entering confirmation | `document.activeElement === dialogEl` immediately once `state.pending` becomes `true` (confirmed both in the isolated test and independently in this phase's full-app harness) |
| 2 | Focus while confirmation is open | Contained by the dialog's own Tab/Shift+Tab wrap (pre-existing isolated tests: Tab from Leave → Stay, Shift+Tab from Stay → Leave, Shift+Tab from the dialog container itself before any Tab → Leave) — background content is unreachable by keyboard while `aria-modal="true"` is in effect |
| 3 | Stay focus behavior | Restores focus to whatever had it immediately before the dialog opened. Independently re-confirmed against the real app with a real, user-focused sidebar link as the pre-click focus holder: `activeElement === trigger` after Stay, not `document.body` |
| 4 | Leave focus behavior | Clears the pending state; the dialog's own restore-on-idle effect does not distinguish Stay from Leave (it would restore to the same previously-focused element if that element still exists), but the destination route's `ContentRegion` MAX-17 effect fires afterward and takes over — confirmed end-to-end: after Leave from a dirty Settings edit, `document.activeElement === container.querySelector("main.page-layout")` on the Dashboard destination |
| 5 | No focus stranded on `document.body` | Confirmed at every checkpoint above: pre-click activeElement was the sidebar link (not body); on dialog-open activeElement is the dialog (not body); after Stay activeElement is the restored trigger (not body); after Leave activeElement is the destination's `main` landmark (not body) |
| 6 | No focus on detached DOM nodes | The isolated test's "does not crash or strand focus... when trigger no longer exists" case removes the previously-focused element from the document before clicking Leave and asserts no throw and `pending: false`; the dialog's own restore effect explicitly guards with `document.contains(target)` before calling `.focus()`. Independently re-confirmed in this phase's harness: `document.activeElement !== null && !document.contains(document.activeElement)` is `false` after Leave (i.e. the active element, whatever it is, is always attached) |

No gaps found in the six-point focus checklist.

## 5. Secret-safety audit

| Surface | Result |
|---|---|
| Dialog content | Confirmed via source read (the dialog's JSX contains exactly two static strings, no interpolation from any control's state) and independently re-confirmed at runtime: with a synthetic secret value entered into the VirusTotal field and a dirty-navigation attempt triggered, the opened dialog's `textContent` does not contain the secret |
| Accessible description | The `aria-describedby`-resolved text was checked directly against the same synthetic secret value — not present |
| `aria-label` | The dialog uses `aria-labelledby`/`aria-describedby` (pointing at its own visible text), not a separate `aria-label` that could carry different content; both pre-existing and this phase's independent checks cover the resolved text these attributes point to |
| Snapshots | No `toMatchSnapshot`/`toMatchInlineSnapshot` usage exists anywhere in this project (confirmed via project-wide grep) — there is no snapshot surface for a secret to leak through |
| Logs | `console.error`/`console.warn`/`console.log` were intercepted in this phase's harness while a synthetic secret was present in the VirusTotal edit buffer and a save failure was forced; the secret did not appear in any captured call. The one production `console.error` call in this codebase's guard-adjacent code (`settingsNavigationGuardStore.ts`'s subscriber-exception handler) logs a fixed string plus the caught error object, never any Settings field value |
| Error text | `useVirustotalKeySave.ts`'s `describeSaveError()` only ever surfaces `error.message` from a `KeystoreWriteError`/generic `Error` — `setVirustotalApiKey()` (`shared/api/client.ts`) never interpolates the credential `value` into any string it throws; independently re-confirmed at runtime with a forced rejection: the rendered `role="alert"` error text was exactly the mocked rejection reason (`"backend unavailable"`), with no trace of the synthetic secret value entered beforehand |

One nuance worth recording precisely: the synthetic secret value **does**
appear in `document.body.innerHTML` at large, because the real,
still-mounted `VirustotalControl`'s `<input>` element legitimately holds
it as its `value` attribute while the user is mid-edit on the page behind
the dialog — that input is a password-type field the person is actively
typing into, not something this finding is about. The requirement's scope
— dialog content, accessible description, `aria-label`, snapshots, logs,
error text — was checked precisely as scoped, and the secret does not
appear in any of those six surfaces. Only dirty-state existence
(a boolean) crosses from `VirustotalControl` into the guard; the value
itself never does (confirmed by source read of `useSettingsPageDirty.ts`,
`settingsDirty.ts`, and `settingsNavigationGuardStore.ts`, none of which
accept or store anything but booleans).

As corroborating (not audited-in-depth, since this checkpoint is
FRONTEND-scoped) evidence: the Rust-side `keystore.rs` funnels every
keystore command's error through a single `describe_error` function
whose own doc comment states it renders an IPC-safe `String`, consistent
with the frontend-side design above never having a secret-bearing string
to receive in the first place.

## 6. Regression checks

| Finding | Result |
|---|---|
| MAX-15 (CommandPalette focus restoration) | Re-run directly: `app/commandPalette/CommandPalette.live.test.tsx` and `app/commandPalette/CommandPaletteContainer.live.test.tsx` (6 tests) pass; `settingsNavigationGuard.live.test.tsx`'s own MAX-15 regression case (closing the palette on a clean Settings page still restores focus to the trigger) also passes |
| MAX-16 (notification focus restoration) | Re-run directly: `shared/notifications/RestartExhaustedNotification.live.test.tsx` passes in full; `settingsNavigationGuard.live.test.tsx`'s own MAX-16 regression case (the restart-exhausted notification and the navigation-guard dialog mount independently without interfering with each other) also passes |
| MAX-17 (route-change focus) | Re-run directly: `app/shell/routeFocus.live.test.tsx` passes in full; `settingsNavigationGuard.live.test.tsx`'s own MAX-17 regression case (destination `main.page-layout` receives focus after a guard-confirmed Leave) also passes; independently re-confirmed in this phase's own full-app harness with real DOM inspection (§4, item 4) |

All three prior findings' behavior is intact.

## 7. Test-environment limitations

- **jsdom does not replicate a real browser's click-focuses-target
  behavior for script-dispatched events.** A `dispatchEvent(new
  MouseEvent("click"))` on an `<a>`/`<button>` does not, by itself, move
  focus to that element the way an actual user click does (focus
  transfer is tied to the browser's native `mousedown` activation
  behavior, which a synthetic `click`-only event does not trigger).
  This phase's own harness initially produced a misleading result because
  of exactly this gap (a sidebar "trigger" was clicked without first
  being focused, so the guard's "restore previously-focused element"
  logic correctly restored to `document.body` — the actual
  previously-focused element — which looked like a stray-focus defect
  until the harness was corrected to `.focus()` the link first, matching
  what a real click does). Once corrected, Stay/Escape both correctly
  restored focus to the real trigger. This is a property of every
  `.live.test.tsx` in this project that drives navigation via
  `dispatchEvent`, not something specific to the navigation guard, and
  it means this class of test can only assert focus-restoration
  correctness relative to whatever focus state the test itself
  establishes beforehand — it cannot independently prove that a real
  browser's own click-focus behavior will produce the same starting
  state a real user's mouse click would. Manual verification in a real
  browser remains the only way to close that residual gap.
- **jsdom has no browser chrome**, so — as already documented in Phase
  2B-1/2B-2/2B-3 — native focus-ring rendering, actual screen-reader
  announcement of `alertdialog`/`aria-live` content, and real assistive-
  technology behavior cannot be observed here; what is verified is the
  DOM's accessibility-relevant attributes and `document.activeElement`,
  which is what assistive technology and the browser's own focus model
  key off, not the rendered visual/audible experience itself.
- This phase's harness necessarily mocks the backend IPC boundary
  (`runCommand`, `setVirustotalApiKey`) and the settings data-fetch hook,
  identical to the mocking boundary every pre-existing `.live.test.tsx`
  in this project already uses. Navigating to Dashboard as this phase's
  Leave-destination required leaving `get_dashboard_summary` permanently
  pending (mirroring the pre-existing suite's own convention) rather than
  resolving it with a guessed data shape, since resolving it with an
  incorrect shape triggered the app's own `ErrorBoundary` and prevented
  the destination's `main` landmark from mounting at all — a harness
  authoring pitfall specific to this checkpoint's own new test, not a
  defect in the application under audit.

## 8. Post-harness integrity check

```
npx vitest run   → 97 test files passed (97), 1368 tests passed (1368)
npx tsc --noEmit → 0 errors
npm run build    → clean
```

Identical to §1's baseline — confirming the temporary harness left no
residue and no production file was altered.

## 9. Output artifact

| Item | Value |
|---|---|
| Archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-4-FULL-PROJECT.zip` |
| Contents | Complete project, plus this document; no other change vs. the Phase 2B-3 input |
| Source modifications | None (temporary harness added and removed within this session only; never present in the packaged output) |

(SHA-256, entry count, and byte size for this specific output archive are
recorded in the delivery message accompanying this document.)

## 10. Interpretation and verdict

Every item in this checkpoint's brief was independently verified against
the real, unmodified application, using real DOM inspection rather than
trusting an existing test's name or description:

- The confirmation dialog has correct `alertdialog` semantics, a
  meaningful accessible name, and a description that explains the actual
  consequence in plain language.
- Stay and Leave are both understandable from their text alone, are real
  `<button>` elements operable by keyboard, and Leave's destructive
  framing is reinforced (not carried solely) by color.
- Escape has an explicit, intentional, non-destructive result identical
  to Stay.
- All six focus-audit points pass: focus enters the dialog on open, stays
  contained while open, is correctly restored on Stay, correctly hands
  off to the destination's MAX-17 focus target on Leave, and never lands
  on `document.body` or a detached node at any checkpoint.
- The VirusTotal secret does not appear in dialog content, its accessible
  description, any `aria-label`, any snapshot (none exist), any captured
  log output, or any error text — only its dirty-state boolean ever
  crosses into the guard.
- MAX-15, MAX-16, and MAX-17 all remain intact.

No blocker was found. Unlike Phase 2B-3, this checkpoint's own brief
(confirmation UX and focus/accessibility on the two paths that do reach a
confirmation) does not encompass the direct-hash/history-navigation gap
that phase identified — that finding stands as previously reported and is
neither resolved nor re-litigated here, since no source change occurred
between that phase's output and this one's input.

**PASS — READY FOR PHASE 2B-5**
