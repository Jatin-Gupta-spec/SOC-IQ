# SOC-IQ FRONTEND — MAX-18 Phase 2B-6: Security + Failure-State Audit

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation. This checkpoint's slice: an independent
security review of the VirusTotal API key edit path, and a
failure-state sweep of every save/unmount/navigation permutation the
task brief lists, to determine whether any of them can silently
discard unsaved changes or expose the secret.

## 1. Baseline integrity

| Check | Result |
|---|---|
| Input archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-5-FULL-PROJECT.zip` |
| SHA-256 (input) | `12abd4ce9d8d201f51921b0612add41e030e902d767bffc0eb594e12341e072d` — matches this session's own record of the Phase 2B-5 output byte-for-byte |
| `unzip -t` | `No errors detected in compressed data` |
| `npm install` (frontend/) | 159 packages, clean; `package-lock.json` pre-existing and untouched |
| `npx vitest run` (full suite) | 97 test files passed, 1368 tests passed — identical to Phase 2B-5's own recorded baseline, no drift |
| `npx tsc --noEmit` | 0 errors, clean |
| Targeted security-relevant subset (`VirustotalControl.test.tsx`, `VirustotalControl.live.test.tsx`, `useVirustotalKeySave.test.tsx`, `settingsNavigationGuardStore.test.ts`, `SettingsNavigationGuardDialog.live.test.tsx`, `settingsNavigationGuard.live.test.tsx`, `settingsDirty.test.ts`, `useSettingsPageDirty.test.tsx`, `useSettingsFieldSave.test.tsx`, `useSettingsBeforeUnloadGuard.test.tsx`) | 10 files, 125 tests, all passing |

No source file was modified at any point during this review. This
phase's input is this session's own Phase 2B-5 output.

**Toolchain limitation, disclosed up front:** the Rust-side keystore
tests (`src-tauri/src/keystore.rs`) were reviewed by reading source only
— no `cargo`/`rustc` toolchain is available in this container, so those
tests could not be independently re-executed this session. Where this
audit relies on Rust-layer behavior, it is marked **source-level proof
only**, not unit-test proof from this session.

## 2. Threat surface

The VirusTotal API key is the only credential-class value anywhere in
MAX-18's scope. Its edit path is:

```
VirustotalControl (password input, local useState buffer)
  -> useVirustotalKeySave (edit buffer, dirty flag, save/retry state)
  -> setVirustotalApiKey() (shared/api/client.ts, direct Tauri invoke())
  -> keystore_set_secret (src-tauri/src/keystore.rs, Rust)
  -> OS-native credential store (keystore_core)
```

MAX-18's own additions (Phase 2A/2B, this and prior checkpoints) sit
entirely upstream of `setVirustotalApiKey()`: the `dirty` aggregate
(`settingsDirty.ts`/`useSettingsPageDirty.ts`), the in-app navigation
guard (`settingsNavigationGuardStore.ts`,
`SettingsNavigationGuardDialog.tsx`), and the browser `beforeunload`
guard (`useSettingsBeforeUnloadGuard.ts`, audited in Phase 2B-5). Every
one of those consumes only a `boolean` (or, for the navigation guard, a
route-path `string`) — never the credential's plaintext. The threat
this audit checks for is specifically whether any of MAX-18's own
logic — not the pre-existing, separately-approved (ADR-008/Part 7/Part
8) keystore write path itself — creates a new avenue for the secret to
reach: application state outside `useVirustotalKeySave`'s own buffer,
the DOM/accessibility tree, `console` output, a URL, a test snapshot, or
this project's own documentation.

## 3. VirusTotal secret audit

| Surface | Observation | Source evidence |
|---|---|---|
| **Dirty-state representation** | `useVirustotalKeySave`'s `dirty` is `value.trim().length > 0` — a boolean derived from the buffer's *length*, never the buffer's contents. `VirustotalControl` forwards only this boolean via `onDirtyChange`. `useSettingsPageDirty` stores three booleans (`themeDirty`, `exportDirectoryDirty`, `virustotalKeyDirty`) and `computeSettingsDirty` is a plain OR over them — no field ever named or valued. | `useVirustotalKeySave.ts` (return statement); `VirustotalControl.tsx` (`onDirtyChange?.(dirty)`); `settingsDirty.ts` (`computeSettingsDirty`); `useSettingsPageDirty.ts` (three `useState<boolean>` + `useMemo`) |
| **Navigation guard** | `SettingsNavigationGuardStore`'s only mutable fields are `dirty: boolean` and `state: SettingsNavigationGuardState` (`{pending:false}` or `{pending:true, targetPath: string}`, where `targetPath` is a route like `/dashboard` — never a field value). `requestNavigation()`/`cancel()`/`confirmLeave()` take/return only these. | `settingsNavigationGuardStore.ts` (class fields, lines ~112–120; `SettingsNavigationGuardState` type) |
| **Confirmation dialog** | `SettingsNavigationGuardDialog`'s entire rendered text is two fixed strings ("Unsaved changes" / "You have unsaved changes on the Settings page. Leaving now will discard them.") plus two static button labels — nothing interpolated from any control. An existing, dedicated test asserts the dialog's `textContent` **exactly**, byte-for-byte, ruling out any interpolation, and separately asserts it does not match `/virustotal/i` or `/api[_-]?key/i`. | `SettingsNavigationGuardDialog.tsx` (JSX body, lines ~206–220); `SettingsNavigationGuardDialog.live.test.tsx`, `"never renders a VirusTotal API key or other secret value in the dialog"` |
| **Accessibility tree** | The credential input is `type="password"` with `autoComplete="off"` and `spellCheck={false}` — the standard, browser-native mechanism that keeps a field's value out of the accessibility tree's exposed value/name and out of spellcheck-related network calls. The dialog's `aria-labelledby`/`aria-describedby` point only at the two static strings above (also independently confirmed by test, §above). No `aria-label`, `aria-valuetext`, or similar attribute anywhere in the VT/dialog code is ever set from the edit buffer. | `VirustotalControl.tsx` (`<input type="password" ... autoComplete="off" spellCheck={false} />`); `SettingsNavigationGuardDialog.live.test.tsx` accessible-name/description tests |
| **Logs** | A whole-directory search for `console.` under `pages/settings/`, `shared/api/client.ts`, and `app/shell/SettingsNavigationGuardDialog.tsx` found exactly one call, in `settingsNavigationGuardStore.ts`'s `notify()` — it logs a caught *listener exception* (`error`), never the store's own `dirty`/`targetPath` state and never any control's edit buffer. `setVirustotalApiKey()`'s own doc comment states the value is never logged, retained, or echoed by that function, and its implementation (`invoke("keystore_set_secret", { name, value })`) performs no logging of `value` at all. | `settingsNavigationGuardStore.ts` line 239 (`console.error("SOC-IQ: settings navigation guard subscriber threw", error)`); `client.ts` `setVirustotalApiKey()` |
| **Error messages** | On a rejected save, `describeSaveError()` returns either a `KeystoreWriteError`'s `.message` or a generic fallback string — never the attempted value. `KeystoreWriteError`'s own message is built from a `reason` string that originates from the Rust command's `Result::Err`, which `keystore.rs`'s `describe_error()` produces (source-level proof only, §1) — and, more directly verifiable in this session, an existing frontend test asserts the rendered error banner's `textContent` **does not contain** the exact entered fixture value after a rejected save, only the safe error text. | `useVirustotalKeySave.ts` (`describeSaveError`); `VirustotalControl.live.test.tsx`, `"on failure: shows a safe error, ... preserves the entered value for retry"` — asserts `expect(container.textContent).not.toContain("fake-test-key-123")` |
| **URLs** | Neither `SettingsNavigationGuardStore` nor any navigation call site (`NavigationGroup.tsx`, `CommandPaletteContainer.tsx`, `SettingsNavigationGuardDialog.tsx`) ever builds a URL/query string from a control's value — the only string that reaches `navigate()` is a fixed route path (`/dashboard`, `/settings`, etc.) already present in the app's static route table. | `NavigationGroup.tsx` (`requestNavigation(item.path)`); `CommandPaletteContainer.tsx` (`requestNavigation(path)`); `SettingsNavigationGuardDialog.tsx` (`navigate(targetPath)`) |
| **Snapshots** | A repository-wide search for `*.snap` files found none — this project does not use snapshot testing anywhere, so there is no snapshot artifact that could have captured a secret. | `find . -iname "*.snap"` → no results |
| **Documentation** | A search of `docs/` for a plausible embedded-secret pattern (`virustotal...key: "..."`-shaped literals) found none. This audit document itself contains no real credential — there is no "real" key anywhere in this repository to begin with; the value lives only in the OS-native keystore, outside source control, per the already-approved ADR-008/Part 7 architecture. Where this document or the source code's own tests reference a value, it is always an explicitly-fake fixture literal (e.g. `"fake-test-key-123"`, `"new-key-value"`), never a production credential. | `grep -rniE` sweep of `docs/`; `VirustotalControl.live.test.tsx` fixture literals |
| **Test output** | This session's own executed test runs (§1) produced no unexpected string matching a credential-like pattern; the only such strings observed anywhere are the fixture literals above, which are already present, as fixtures, in the unmodified source this audit is reviewing — not something this audit introduced or amplified. | This session's `vitest run` stdout |

**Conclusion of this section:** no MAX-18 logic (dirty aggregate,
navigation guard, `beforeunload` guard, or confirmation dialog) reads,
stores, forwards, or displays the VirusTotal API key's value at any
point. Every one of the ten checklist items resolves to "boolean/route
only, never the value," backed by either direct source reading or an
existing, currently-passing test that asserts the negative
(`not.toMatch`/`not.toContain`) directly. This audit's own documentation
contains no real key.

## 4. Failure-state sweep

| Case | Behavior | Silently discards unsaved changes? | Evidence |
|---|---|---|---|
| **Failed save** (Theme/Export Directory) | `useSettingsFieldSave`'s rejection branch sets `saveStatus: {status:"error", message}` and does **not** touch `savedBaseline` — `dirty` (`value !== savedBaseline`) stays `true`. | **No.** | `useSettingsFieldSave.ts` (error branch); `useSettingsFieldSave.test.tsx`, `"resolves to error, preserving the real error message, on a failed save"` — explicitly asserts `dirty` is `true` afterward |
| **Failed save** (VirusTotal) | `useVirustotalKeySave`'s rejection branch sets the error status and does **not** clear `value` — the edit buffer, and therefore `dirty` (non-empty check), is preserved. | **No.** | `useVirustotalKeySave.ts` (error branch, comment: "the entered credential is not cleared here so the user does not have to retype it"); `VirustotalControl.live.test.tsx`, `"on failure: ... preserves the entered value for retry"` |
| **Partial save** (ambiguous/malformed backend response) | `runCommand()` is binary: every failure mode (network error, non-2xx HTTP, malformed JSON body, backend-reported failure) rejects the promise — there is no code path that resolves with a partial or ambiguous "kind of succeeded" result. A rejection is handled identically to any other failed save (row above); the VT credential path (`setVirustotalApiKey`) is a separate, simpler `invoke()` call with the same binary resolve/reject shape. | **No** — no partial-success state exists to discard from. | `client.ts` (`runCommand`'s doc comment: "Never silently turns a failure into a fake success, never swallows an error"); `client.ts` (`setVirustotalApiKey`, single try/catch around one `invoke()` call) |
| **Repeated failed save** | Nothing in either save hook counts or special-cases attempt number — `save()` is re-invocable after an `"error"` state exactly the same way regardless of how many prior attempts failed, and each failure independently re-applies the same "preserve buffer / keep dirty true" behavior above. Directly exercised twice in sequence (reject, then a second attempt that succeeds) for both controls. | **No.** | `useSettingsFieldSave.test.tsx`, `"retries by calling save again after a failure"`; `VirustotalControl.live.test.tsx`, same test as above continues on to click Retry and succeed |
| **Retry** | Both controls' `save()` is unconditionally safe to call again from an `"error"` state (only a no-op guard against calling while already `"saving"` or, for VT, against an empty trimmed buffer) — retry reuses the exact same edit buffer the failed attempt used, never a stale or re-derived one. | **No.** | Same evidence as "Repeated failed save" row |
| **Unmount during dirty state** | React's effect-cleanup guarantees fire regardless of *why* `SettingsPage` unmounts: `useSettingsBeforeUnloadGuard` removes its listener (Phase 2B-5, re-confirmed this session), and `useSettingsNavigationGuardSync`'s second effect unconditionally clears the navigation-guard store's `dirty` flag on unmount so no stale state can block a later, unrelated visit. Neither of these two cleanups is what *prevents* data loss on unmount, though — losing the in-memory edit buffer on an actual unmount is expected (the component's local state is destroyed); what prevents an *unconfirmed* unmount from happening in the first place is the guard itself (row below). | **No new silent-discard path** — an unmount that happens *because the person clicked Leave* is an informed choice, not a silent one; see the next row for the one case where an unmount can happen without that choice. | `useSettingsBeforeUnloadGuard.ts`; `useSettingsNavigationGuardSync.ts` (both effects); Phase 2B-5's own audit (`SOC-IQ-FRONTEND-MAX-18-PHASE-2B-5.md`, §3, "Unmount") |
| **Navigation attempt during dirty state** | Both in-app trigger sites (`NavigationGroup.tsx`'s `NavLink onClick`, `CommandPaletteContainer.tsx`'s `handleNavigate`) call `settingsNavigationGuard.requestNavigation(path)` **before** calling `navigate()`/allowing the link's default action, and structurally cannot reach the navigate step when the result is `"blocked"`. Confirmed end-to-end (real router, real sidebar, real palette) for both trigger sites while dirty, including with multiple controls dirty simultaneously. | **No**, for the sidebar and command-palette paths. | `NavigationGroup.tsx`; `CommandPaletteContainer.tsx`; `settingsNavigationGuard.live.test.tsx`, describe blocks 2, 7, 10, 11 |
| **Navigation attempt immediately after save** | A successful save synchronously (within the same `act`/microtask flush) updates `savedBaseline`/clears the VT buffer, which recomputes `dirty` to `false` on the next render, which both guard hooks' effects (keyed on `settingsDirty`) pick up before any subsequent user interaction can occur on a single-threaded event loop. Confirmed directly, full-app: a save resolved, then an immediate sidebar click navigates with **no** confirmation dialog. | **No.** | `settingsNavigationGuard.live.test.tsx`, describe block 8, `"a successful save clears the guard, and navigation succeeds without confirmation"` |
| **Multiple dirty controls** | `computeSettingsDirty` is validated across all 8 boolean combinations of the three flags, including "only once every flag returns to false" (clearing one control while another remains dirty must **not** clear the aggregate). Confirmed again at the full-app level: making Theme and Export Directory both dirty still blocks navigation, and a confirmed Leave discards **both** together (an informed choice, not a per-control partial loss). | **No** — no combination lets one control's clean state mask another's dirty state. | `settingsDirty.test.ts` (all 7 non-trivial cases incl. "returns to false only once every flag returns to false"); `useSettingsPageDirty.test.tsx` (13 tests incl. "clearing only the Theme flag while the others stay dirty keeps the aggregate dirty"); `settingsNavigationGuard.live.test.tsx`, describe block 7 |

### Finding: browser back/forward (same-document `popstate`) is not intercepted by either guard

Independent inspection of every navigation call site (`grep` across
`app/shell/`, `app/navigation/`, `app/commandPalette/`) found exactly
two places that call `settingsNavigationGuard.requestNavigation()`
before navigating: the sidebar `NavLink` and the command palette.
Browser back/forward (and any direct hash edit) under this app's
`HashRouter` fires a same-document `popstate`/`hashchange` event that
neither of MAX-18's two guards can intercept: the in-app navigation
guard has no synchronous, cancellable hook into `popstate` (it would
require committing the navigation and then reverting it, which this
project's own architecture and an earlier checkpoint's brief both rule
out), and `beforeunload` specifically does not fire for same-document
navigation at all — no page unload occurs. **This means a dirty
`SettingsPage` can be silently left, with the in-memory edit buffer
(and, for the VirusTotal control, the still-unsaved credential text)
discarded, via the browser's own back/forward navigation, with no
confirmation of any kind.**

This is **not a new discovery** — it is an already-documented,
deliberate architectural limitation, called out explicitly in
`settingsNavigationGuardStore.ts`'s own doc comment and, per that
comment, previously written up in
`docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-3.md`'s "Known limitations"
section at the checkpoint that built the in-app guard. This audit
independently re-confirms it is still present and still unaddressed as
of this project's current (2B-5) state, and surfaces it again here
because it directly answers this checkpoint's own question ("determine
whether any failure can silently discard unsaved changes") — the
answer for this one specific trigger is yes. No source change is
proposed here: per this checkpoint's brief, source is not to be
modified, and (per the brief's own security principle) this is not a
secret-exposure defect — no VirusTotal value is exposed by this path,
only the existence of unsaved state is lost, exactly as it would be if
the person closed the tab without triggering a native prompt at all.

## 5. Findings and severity

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | VirusTotal secret is never represented, forwarded, logged, or rendered as anything other than a boolean (dirty) or absent entirely, across every surface the brief lists (dirty state, nav guard, dialog, a11y tree, logs, error messages, URLs, snapshots, docs, test output). | N/A — no defect | Verified, no action needed |
| 2 | Failed save, partial/ambiguous save, repeated failure, and retry all leave `dirty` (and the underlying edit buffer) intact for both credential and non-credential controls — no code path silently converts a failure into a discarded edit. | N/A — no defect | Verified, no action needed |
| 3 | Unmount and in-app navigation (sidebar, command palette) while dirty are both correctly gated by the existing guards; navigation immediately after a successful save correctly proceeds without a stale prompt; multiple simultaneously-dirty controls are correctly aggregated in both directions. | N/A — no defect | Verified, no action needed |
| 4 | Browser back/forward (`popstate`) bypasses both the in-app navigation guard and the `beforeunload` guard, silently discarding unsaved Settings edits (including an in-progress, unsaved VirusTotal credential entry — text only, not a stored secret). | **Medium** (data-loss/UX robustness gap in MAX18-F-01's own stated goal; not a secret-exposure vulnerability, since nothing is exposed, only unsaved state is lost) | **Known, pre-existing, previously documented** (Phase 2A-3's own audit); re-confirmed still present; no fix proposed per this checkpoint's do-not-modify-source scope |

No new security defect (secret exposure, logging leak, DOM/accessibility
leak, or URL leak) was discovered. Per the brief's security principle,
no change to secret-storage architecture is recommended, since none was
found to be warranted.

## 6. Conclusion

The VirusTotal API key edit path was traced end to end
(`VirustotalControl` → `useVirustotalKeySave` → `setVirustotalApiKey` →
`keystore_set_secret`), and every one of the ten surfaces the brief
lists was independently checked against source and, where a currently-
executable frontend test already asserts the specific negative, against
this session's own passing test run (97 files / 1368 tests, plus a
125-test targeted re-run of the security-relevant subset). No MAX-18
logic exposes the secret's value anywhere. The eight-case failure-state
sweep found no path by which a failed, partial, or repeatedly-failed
save, a retry, an unmount, or an in-app navigation attempt (immediately
after save or otherwise, with one or several controls dirty) silently
discards unsaved Settings edits. One previously-documented,
architecture-level gap (browser back/forward bypassing both guards) was
independently re-confirmed still present; it is a known limitation
carried forward from Phase 2A-3, not a new defect, and is reported here
rather than fixed, per this checkpoint's explicit no-source-changes
scope. No source file was modified; the full project test suite (1368
tests) and `tsc --noEmit` both remain clean against the exact Phase
2B-5 source.

**Verdict: `PASS — READY FOR PHASE 2B-7`**
