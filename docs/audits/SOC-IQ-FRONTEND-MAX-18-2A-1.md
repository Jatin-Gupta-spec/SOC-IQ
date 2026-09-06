# SOC-IQ Frontend MAX-18 — Phase 2A-1 Audit

**MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.**
**This checkpoint: dirty-state extraction & foundation only.**

## Baseline

The task brief names the authoritative input as
`SOC-IQ-FRONTEND-MAX-17-FINAL-CLOSURE-FULL-PROJECT.zip`
(SHA-256 `7971adb42c7a3cac3e62be564ceb57b08a7628c06963e04bbbe4c7400f3af632`).

**The file actually supplied for this checkpoint has a different name
and hash:**

| | |
|---|---|
| Supplied file | `SOC-IQ-FRONTEND-MAX-17-PHASE-2A-IMPLEMENTED-FULL-PROJECT.zip` |
| Supplied SHA-256 | `891e04f7ca81388cdda98fd8ea9c06ab5dbe5572b0fdf14818de044eed6f14dd` |

No file matching the brief's stated name or hash was available. Work
proceeded from the file actually supplied, since it is a coherent,
buildable, fully-tested SOC-IQ frontend checkpoint (Part 2B-1 Settings
already implemented, all pre-existing tests passing before any change
here). This discrepancy is flagged rather than silently ignored or
papered over with a fabricated matching hash — see **Final Verdict**.

## Files changed

| File | Change |
|---|---|
| `frontend/src/pages/settings/useVirustotalKeySave.ts` | Added `dirty: boolean` to the hook's return value (`value.trim().length > 0`) and documented what "dirty" means for this credential-only, no-persisted-baseline hook. |
| `frontend/src/pages/settings/VirustotalControl.tsx` | Consumes the hook's new `dirty` instead of its own local `trimmedIsEmpty` computation for the Save button's `disabled` condition. Identical resulting behavior — a rename/expose of existing logic, not a new comparison. |
| `frontend/src/pages/settings/settingsDirty.ts` | **New.** Pure `computeSettingsDirty(flags)` combinator and `SettingsDirtyFlags` type — the `settingsDirty` aggregate. |
| `frontend/src/pages/settings/settingsDirty.test.ts` | **New.** Unit tests for the aggregate combinator. |
| `frontend/src/pages/settings/useVirustotalKeySave.test.tsx` | **New.** Dirty-state tests for the hook (initial/dirty/clean/save/failure/unmount). |
| `frontend/src/pages/SettingsPage.live.test.tsx` | **New.** Real-component integration tests proving independent, simultaneous dirty tracking across all three controls as actually rendered on the page. |

`ThemeControl.tsx`, `ExportDirectoryControl.tsx`, and
`useSettingsFieldSave.ts` are **unchanged** — that hook already
exposed a correct, well-tested `dirty` signal (`useSettingsFieldSave.test.tsx`,
pre-existing) covering every "REQUIRED BEHAVIOR" bullet in the task
brief for Theme and Export Directory. Reusing it as-is, rather than
duplicating or rewriting it, follows the brief's own instruction to
prefer the existing local edit/save architecture.

`SettingsPage.tsx` is **unchanged** (see "Known limitations" below for
why the aggregate is not wired into it yet).

## Dirty-state model

Three independent per-control signals, each already the single source
of truth its own control's Save button disables against — no new
duplicate value is held anywhere:

- **`themeDirty`** — `useSettingsFieldSave("theme", persistedTheme).dirty`.
  `true` when the edit buffer differs from the last known-persisted
  theme value. Pre-existing, unchanged.
- **`exportDirectoryDirty`** — `useSettingsFieldSave("export_directory", persistedExportDirectory).dirty`.
  Same mechanism, same hook instance pattern, independent state
  (React `useState` is per-hook-call, so Theme's and Export
  Directory's `dirty` can never leak into each other). Pre-existing,
  unchanged.
- **`virustotalKeyDirty`** — `useVirustotalKeySave().dirty`, added
  this checkpoint. The VirusTotal API key is never read back into the
  frontend (ADR-008 Part 1B-3's approved security boundary,
  unchanged), so there is no persisted value to diff against. "Dirty"
  here means "the trimmed edit buffer is non-empty" — exactly the
  condition that already gated the Save button before this change.

**`settingsDirty`** (aggregate) — `computeSettingsDirty(flags)` in the
new `settingsDirty.ts`: a pure `themeDirty || exportDirectoryDirty ||
virustotalKeyDirty`. See "Known limitations" for why it is not yet
wired into `SettingsPage`.

All three per-control signals are derived, not duplicated: none of
them stores a second copy of the persisted or edited value purely for
dirty-tracking purposes; each is a boolean computed from state the
control already held for its edit/save behavior.

## Test coverage

Against the brief's required list:

| Requirement | Covered by |
|---|---|
| Clean initial state | `useSettingsFieldSave.test.tsx` (pre-existing), `useVirustotalKeySave.test.tsx`, `SettingsPage.live.test.tsx` ("starts every control clean") |
| Edit → dirty | Same three files |
| Successful save → clean | `useSettingsFieldSave.test.tsx` (pre-existing), `useVirustotalKeySave.test.tsx` ("returns to clean once a save resolves") |
| Failed save → dirty | `useSettingsFieldSave.test.tsx` (pre-existing), `useVirustotalKeySave.test.tsx` ("remains dirty after a failed save") |
| Multiple controls dirty simultaneously | `SettingsPage.live.test.tsx` ("all three controls can be dirty at the same time") |
| Saving one control does not clear another's dirty state | `SettingsPage.live.test.tsx` ("saving one control does not clear another dirty control's state", and the failed-save equivalent) |
| Editing values repeatedly | `useSettingsFieldSave.test.tsx` (pre-existing, edit → original value → clean), `useVirustotalKeySave.test.tsx` ("never derives dirty from anything but the buffer's own length") |
| No secret value in logs/test output | `VirustotalControl.test.tsx` / `.live.test.tsx` (pre-existing, static + rendered markup never contains the raw key), `useVirustotalKeySave.test.tsx` ("does not leak the entered credential into a thrown error or rejection value"), `SettingsPage.live.test.tsx` ("never renders the entered VirusTotal key as visible text anywhere on the page") |
| Unmount does not create stale-state behavior | `useVirustotalKeySave.test.tsx` ("does not throw or apply a stale update when a save resolves after unmount"), `SettingsPage.live.test.tsx` ("unmounting with in-flight saves on multiple controls does not throw") |

All new tests exercise real component/hook behavior (real `<select>`/
`<input>` DOM events, real `createRoot`/`act` lifecycles, the actual
`SettingsPage` composition of all three controls) rather than
asserting on internal implementation details — consistent with the
codebase's existing `*.live.test.tsx` convention.

## Verification results

Run from `frontend/`:

```
npm ci               → 159 packages installed, no errors
npx vitest run       → 90 test files, 1262 tests passed, 0 failed
npx tsc --noEmit     → no errors
npm run build        → tsc --noEmit && vite build succeeded, dist/ produced
```

No existing test was weakened, skipped, or deleted to obtain a pass.

## Security considerations

- `virustotalKeyDirty` is derived from `value.trim().length > 0` only
  — never from the value's content, never logged, never compared
  against or exposed to any other state. The `settingsDirty` aggregate
  and its tests operate exclusively on booleans; the raw credential
  string never reaches that combinator.
- No new logging was added anywhere in this change.
- `useVirustotalKeySave`'s existing guarantee — the entered credential
  is cleared from the edit buffer immediately on a successful save,
  and never round-tripped from any backend read — is unchanged.
- New tests assert the entered VirusTotal key never appears in
  `container.textContent` (visible rendered text) at the
  `SettingsPage` level, on top of the pre-existing per-component
  guards.

## Scope compliance

No navigation interception, `beforeunload` handling, confirmation
dialog, autosave, global unsaved-changes framework, router change,
CommandPalette change, backend/Rust/Tauri change, AI work, or visual
redesign was introduced. `ThemeControl`, `ExportDirectoryControl`, and
`useSettingsFieldSave` were left untouched rather than rewritten,
since their existing dirty-tracking already satisfied the brief.
`SettingsPage.tsx` itself was not modified (see below).

## Known limitations

- **`settingsDirty` is implemented but not wired into `SettingsPage`.**
  Nothing in this checkpoint consumes an aggregate "is anything on
  this page unsaved" signal — that starts with Phase 2A-2's navigation
  interception. Lifting each control's `dirty` up into `SettingsPage`
  state now, with no reader for it, would mean carrying dead
  page-level state through this checkpoint purely so a later phase
  doesn't have to add it — exactly the kind of premature plumbing the
  brief's phase boundaries (2A-1 foundation vs. 2A-2 consumption) are
  structured to avoid. `computeSettingsDirty` is written, exported,
  and independently tested so 2A-2 has one correct place to call it
  from.
- **Baseline mismatch**, described under "Baseline" above: the
  supplied project does not match the brief's named/hashed
  authoritative input. Everything in this document describes work
  done against the file actually supplied.

## Final verdict

`BLOCKED`

Not blocked on the engineering work itself — dirty-state tracking for
all three controls is implemented, tested, and verified per the brief
(`npm ci`, `npx vitest run`, `npx tsc --noEmit`, `npm run build` all
pass clean). Blocked specifically on the baseline discrepancy above:
this checkpoint was built from
`SOC-IQ-FRONTEND-MAX-17-PHASE-2A-IMPLEMENTED-FULL-PROJECT.zip`
(SHA-256 `891e04f7ca81388cdda98fd8ea9c06ab5dbe5572b0fdf14818de044eed6f14dd`),
not the brief's named
`SOC-IQ-FRONTEND-MAX-17-FINAL-CLOSURE-FULL-PROJECT.zip`
(SHA-256 `7971adb42c7a3cac3e62be564ceb57b08a7628c06963e04bbbe4c7400f3af632`).
Confirm which baseline is authoritative before this checkpoint is
treated as the input to Phase 2A-2.
