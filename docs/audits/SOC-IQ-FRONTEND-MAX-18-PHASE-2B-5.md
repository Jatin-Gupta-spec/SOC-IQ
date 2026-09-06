# SOC-IQ FRONTEND — MAX-18 Phase 2B-5: Browser Lifecycle + Beforeunload Audit

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation (this checkpoint's slice: leaving the *browser/
document context* — tab close, window close, reload, or a browser-chrome
URL change — rather than in-app SPA navigation, which Phase 2B-4 and
earlier already closed).

## 1. Baseline integrity

| Check | Result |
|---|---|
| Input archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-4-FULL-PROJECT.zip` |
| SHA-256 (input) | `f6f6ecd02c07080e2c17a1e64dc08980f4e94039eb7d96bbb562262af03e7501` |
| `unzip -t` | `No errors detected in compressed data` |
| Entry count | 866 |
| Byte size | 7,390,955 bytes |
| `npm install` (frontend/) | 159 packages, clean; `package-lock.json` pre-existing and untouched |
| `npx vitest run` (full suite) | 97 test files passed, 1368 tests passed |
| `npx tsc --noEmit` | 0 errors, clean |

No drift from Phase 2B-4's own recorded baseline (97 files / 1368 tests,
clean typecheck). This phase's input is this session's own Phase 2B-4
output.

## 2. Scope and methodology

The task brief asks for independent verification of one specific,
narrow surface: the browser-native `beforeunload` protection for dirty
Settings state, plus a duplicate-listener audit and an explicit
source-proof/unit-test-proof/browser-limitation split. No source edits
were made at any point; this is a read-only review plus an unmodified
re-run of the existing suite.

Reviewed in full:

- `frontend/src/pages/settings/useSettingsBeforeUnloadGuard.ts` — the
  hook itself (single call site, single effect).
- `frontend/src/pages/settings/useSettingsBeforeUnloadGuard.test.tsx` —
  its dedicated test file (16 tests across 8 `describe` blocks).
- `frontend/src/pages/SettingsPage.tsx` — the one wiring call site
  (`useSettingsBeforeUnloadGuard(settingsDirty)`, line 129).
- `frontend/src/pages/settings/settingsDirty.ts` and
  `useSettingsPageDirty.ts` — the aggregate this hook consumes, to
  confirm it carries no per-control field values, only booleans.
- `frontend/src/pages/settings/useSettingsFieldSave.ts` — to confirm
  the underlying save→dirty-reset mechanism this hook's protection
  ultimately reacts to (Theme/Export Directory path).
- A whole-frontend `grep` for every `beforeunload` occurrence outside
  this hook's own file and its test, to rule out a second, competing,
  or leftover registration anywhere else in the codebase.

Independently re-ran (unmodified source, unmodified tests):
`npx vitest run src/pages/settings/useSettingsBeforeUnloadGuard.test.tsx`,
the full `src/pages/settings/` + `SettingsPage` slice, and the full
project suite (§1), plus `npx tsc --noEmit`.

## 3. Beforeunload matrix

| Case | Result | Evidence |
|---|---|---|
| **Clean** — no active protection listener should exist | **Pass** | `useSettingsBeforeUnloadGuard`'s effect early-returns before calling `addEventListener` whenever `settingsDirty` is `false` (lines 111–114). Test suite §1 ("clean → no listener") renders `dirty={false}` and asserts zero `beforeunload` `addEventListener` calls and a `null` handler lookup — both pass. |
| **Dirty** — protection listener should exist | **Pass** | The same effect calls `window.addEventListener("beforeunload", handleBeforeUnload)` exactly once when `settingsDirty` is `true` on the render the effect runs (line 116). Test suite §2 renders `dirty={true}` and asserts exactly one `beforeunload` add call, and that invoking the captured handler calls `preventDefault()` and sets `returnValue` to `""`. Both pass. |
| **Dirty → Save** — protection should be removed after successful save | **Pass (by composition, not by this hook's own code)** | This hook has no knowledge of "save" as a concept — it only reacts to `settingsDirty` flipping to `false`. That flip is guaranteed by `useSettingsFieldSave.ts`: on a resolved `save_settings` call, `setSavedBaseline(valueAtRequestTime)` runs (lines ~86–90), and `dirty` is derived as `value !== savedBaseline` — so a successful save always drives that control's own `dirty` to `false`. `computeSettingsDirty` (`settingsDirty.ts`) is a plain OR of the three controls' flags with no memory of history, so once every control's own dirty flag is `false`, the aggregate is `false` on the very next render, and `useSettingsBeforeUnloadGuard`'s effect (keyed on that aggregate) tears down the listener via its cleanup function — mechanically identical to the "dirty → clean" case the test file exercises directly (§4, "removes the listener when settingsDirty flips to false"; passes). There is no separate "on save" code path in this hook to audit beyond that composition, which is exactly per its own doc comment's stated design (no new dirty logic, only a second consumer of the one existing boolean). |
| **Dirty → Leave Settings** — the listener should clean up appropriately | **Pass** | "Leaving Settings" while staying inside the SPA is in-app routing, mediated by React unmounting `SettingsPage` (and, separately, by `useSettingsNavigationGuardSync`/`SettingsNavigationGuardDialog`, which are Phase 2A-3/2B-4's concern, not this hook's). On unmount, React's effect-cleanup rule runs this hook's cleanup unconditionally, which is a no-op if no listener was ever added (clean) or a real `removeEventListener` if one was (dirty). Test suite §5 ("unmount removes the listener") covers both: unmounting while dirty asserts exactly one removal call; unmounting while clean asserts zero removal calls (not merely zero *net* listeners — an unconditional call would still show up in `removeSpy`, and it does not). Both pass. |
| **Unmount** — no stale listener should remain | **Pass** | Same mechanism as above. Test suite §5's third case additionally invokes the (would-be) handler post-unmount and asserts `null` — i.e., not just that a removal call happened, but that nothing observable remains registered. Passes. |
| **Remount** — behavior should initialize correctly | **Pass** | The hook holds no state across mounts — `useEffect` with a fresh dependency array on a fresh component instance runs from scratch each time, so a remount cannot inherit a previous instance's listener. Test suite §6 explicitly simulates a real remount (unmount, discard the container, create a new container + root) for both a remount that starts clean (asserts total adds still equals the first mount's single registration, and no handler is invocable) and one that starts dirty (asserts a second, independent single registration, and that its handler behaves correctly). Both pass. |

**Net result: 6/6 matrix rows pass**, with the "Dirty → Save" row passing
on the strength of a cross-file composition argument (§ above) rather
than a save-specific line inside this hook, since the hook by design
contains no save-awareness of its own.

## 4. Duplicate-listener audit

| Concern | Finding |
|---|---|
| **Duplicate listeners** | Not present. The effect's dependency array is `[settingsDirty]` alone; React only re-runs an effect when a dependency's value actually changes, so a re-render with the *same* `settingsDirty` value — an unrelated parent re-render, or a second control independently going dirty while the aggregate was already `true` — does not re-run the effect and therefore cannot add a second listener. Test suite §3 exercises exactly this: three consecutive re-renders with `dirty={true}` still show `addEventListener` called only once and `removeEventListener` called zero times. Passes. |
| **Stale closures** | Not present. `handleBeforeUnload` is a top-level, argument-free function — it closes over nothing from a render, reads no props/state, and derives nothing from `settingsDirty` or any field value at call time. There is no captured variable that could go stale between registration and invocation. |
| **Stale dirty state** | Not present at the browser-guard layer. The guard's own state is nothing more than "is a listener currently attached," which is kept in lockstep with `settingsDirty` by the effect/cleanup pair on every value change — there is no separate cached copy of the dirty flag inside this hook to go stale. (Whether the *aggregate itself* could go stale is a `useSettingsPageDirty`/`SettingsPage` concern, out of this checkpoint's scope; `useSettingsNavigationGuardSync`'s own unmount-clears-the-store behavior, audited in Phase 2A-3, is the analogous guard against staleness on that side and this hook does not duplicate or need it, since it holds no store of its own.) |
| **Cleanup failure** | Not present. React guarantees the effect's returned cleanup runs before every subsequent effect invocation and on unmount; the cleanup here is an unconditional `removeEventListener` call with the exact same function reference that was added (`handleBeforeUnload` is a single stable top-level reference, never recreated per-render), so `removeEventListener` is guaranteed to match and remove the correct listener every time. Calling `removeEventListener` for a listener that was never added (the clean-render early-return path) is a documented no-op per the DOM spec, not an error. |
| **Permanent global listener** | Not present. There is no code path that registers `handleBeforeUnload` outside this one effect, and no "always-on" registration anywhere in `SettingsPage` or its mount tree — a whole-frontend `grep -rn "beforeunload"` across `frontend/src` (excluding this hook's own file and test) returned zero other matches. The only two non-comment lines that touch `beforeunload` in the entire frontend are the `addEventListener`/`removeEventListener` pair inside this hook (§3 above). |

## 5. Source-level proof vs. unit-test proof vs. browser/runtime limitation

Per the task brief's explicit instruction, this section separates what
is proven by reading the source, what is proven by the executed test
suite, and what cannot be proven in this project's test environment at
all.

**Source-level proof (read, not executed):**
- The hook registers/deregisters based solely on `settingsDirty`, with
  no other trigger and no per-render duplication path (dependency-array
  reasoning, §4).
- `event.returnValue` is unconditionally set to the literal empty
  string `""`, never to a value derived from `settingsDirty`, a
  control's persisted value, or any edit-buffer contents (in
  particular, the VirusTotal key buffer) — confirmed by reading the
  full 5-line handler body, which takes no parameters beyond the event
  itself and closes over nothing.
- No prompt text is supplied anywhere in this hook or its one caller —
  only `event.preventDefault()` and the legacy `returnValue` fallback,
  matching the brief's note that native browsers ignore custom
  strings and always show their own fixed UI.

**Unit-test proof (executed, this session, against unmodified
source — §1, §3):**
- All 7 matrix-adjacent lifecycle states the brief enumerates (clean,
  dirty, repeated-dirty-render, dirty→clean, unmount-while-dirty,
  unmount-while-clean, remount-clean, remount-dirty — 16 tests across
  8 `describe` blocks) pass, using `window.addEventListener`/
  `removeEventListener` spies filtered to the `"beforeunload"` event
  type plus direct capture-and-invoke of the registered handler
  function.
- The registered handler, when invoked directly, is confirmed (via a
  purpose-built mock event object, not a real jsdom `Event` — see
  below) to call `preventDefault()` and set `returnValue` to exactly
  `""` — never any other value — every time `settingsDirty` is `true`.
- The full project suite (97 files / 1368 tests) and `tsc --noEmit`
  both pass with this hook and its call site unmodified, confirming no
  regression was introduced anywhere else by this checkpoint's (or any
  prior checkpoint's) wiring.

**Browser/runtime limitation (cannot be proven in this environment,
and this audit does not claim otherwise):**
- jsdom (this project's `vitest` environment) implements
  `beforeunload` as a dispatchable DOM event, but has no browser
  chrome and therefore cannot show, suppress, or render text in a
  native "leave site?" confirmation dialog. No test in this project,
  and no claim in this audit, asserts that such a dialog appears,
  is suppressed, or carries any particular wording — that is
  necessarily a manual, real-browser verification step, exactly as
  the task brief anticipates.
- A narrower, related jsdom quirk: per the DOM spec, a real `Event`
  object's `returnValue` getter reflects the boolean canceled flag
  (`!defaultPrevented`) rather than whatever value was last assigned
  to it, so dispatching a genuine jsdom `Event` and reading
  `.returnValue` back could only ever observe `true`/`false`, never
  the literal empty string this hook actually assigns. The test file
  works around this precisely — by capturing the real listener
  function and invoking it with a hand-built mock event whose
  `returnValue` is a plain writable property — rather than either
  skipping the assertion or asserting something jsdom cannot
  faithfully represent. This is a deliberate, documented test-design
  choice, not a proof of native-dialog behavior by another route.

## 6. Conclusion

All six matrix rows in the task brief's beforeunload matrix pass, using
the unmodified existing hook, its unmodified 16-test file, and (for the
save-triggered removal row) a cross-file composition argument grounded
in `useSettingsFieldSave`'s already-existing save→baseline→dirty-reset
mechanism. The duplicate-listener audit found no duplicate listeners,
no stale closures, no stale dirty state at this layer, no cleanup
failure, and no permanent/global listener anywhere in the frontend
outside this hook's single, correctly-scoped effect. No source file was
modified at any point in this review; the full project test suite
(1368 tests) and `tsc --noEmit` both remain clean against the exact
Phase 2B-4 source. Native browser dialog appearance/suppression/text
remains, as the task brief anticipates, a manual real-browser
verification step outside what jsdom/Vitest can exercise — that
limitation is a property of the test environment, not a gap in this
hook or its test coverage.

**Verdict: `PASS — READY FOR PHASE 2B-6`**
