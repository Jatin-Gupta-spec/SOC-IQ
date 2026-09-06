# SOC-IQ FRONTEND — MAX-18 Phase 2B-1: Independent Baseline & Implementation Integrity Audit

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation.
**Nature of this phase:** independent verification only. No source file was
modified, refactored, or "improved" in the course of this audit.

## 1. Methodology

This audit treats `SOC-IQ-FRONTEND-MAX-18-PHASE-2A-IMPLEMENTED-FULL-PROJECT.zip`
as the sole input and does not reuse the Phase 2A working directory from the
prior session — the archive was re-extracted fresh into a new location, and
every finding below was re-derived from that fresh extraction rather than
carried over from the 2A checkpoint's own conclusions. Where a prior
checkpoint's doc made a specific claim (e.g., "dirty resets on successful
save"), that claim was checked against the actual source line making it
true or false here, not accepted on the strength of a passing test name
alone (per this phase's explicit instruction).

## 2. Baseline integrity

| Check | Result |
|---|---|
| Input archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2A-IMPLEMENTED-FULL-PROJECT.zip` |
| `unzip -t` (integrity) | `No errors detected in compressed data` |
| SHA-256 | `8b9fea074d34a580a89b089af197603f18a5bf75396c34f14a4fcb91d742a962` |
| Entry count | 862 |
| Byte size | 2,729,361 bytes |
| Project completeness | Top-level contents present: `app/`, `frontend/`, `src-tauri/`, `tests/`, `docs/`, `packaging/`, `keystore-core/`, `sidecar-core/`, `database/`, `samples/`, `README.md`, `LICENSE`, `.gitignore`, `.github/`, plus root config files — consistent with a full-project archive, not a partial one |
| Suspicious temporary artifacts | None found — no `node_modules/`, `dist/`, `__pycache__/`, `.pytest_cache/`, `*.tmp`, or `.DS_Store` anywhere in the extracted tree |

## 3. Final verification — commands run independently in this session

```
npm ci            → added 159 packages, clean
npx vitest run    → 97 test files passed (97), 1368 tests passed (1368)
npx tsc --noEmit  → 0 errors
npm run build     → tsc --noEmit + vite build, clean, ~3.4s
```

Identical pass counts to the Phase 2A-8 checkpoint's own run, reproduced
here from a completely independent `npm ci` against the archived
`package-lock.json` rather than reusing any prior `node_modules`.

## 4. Source audit — independent findings

Each item below reflects direct reading of the extracted source in this
session, not a restatement of a prior audit's prose.

**`SettingsPage.tsx`** — calls `useSettingsPageDirty()`, obtains
`settingsDirty` plus three `onDirtyChange` setters, and passes each setter
to the matching control (`ThemeControl`, `ExportDirectoryControl`,
`VirustotalControl`) as `onDirtyChange`. Calls
`useSettingsNavigationGuardSync(settingsDirty)` and
`useSettingsBeforeUnloadGuard(settingsDirty)` with that same aggregate.
Exposes `settingsDirty` as a `data-settings-dirty` attribute (test hook).

**Theme / Export Directory controls (`useSettingsFieldSave.ts`)** — a
single hook shared by both fields. `dirty: value !== savedBaseline`.
`savedBaseline` starts at the field's `persistedValue` and is updated to
`valueAtRequestTime` **only** in the save-success branch; the save-error
branch sets `saveStatus: "error"` and returns without touching
`savedBaseline`. This is a real comparison against a real prior-saved
value, not a hardcoded or vacuous flag.

**VirusTotal control (`useVirustotalKeySave.ts`)** — cannot use the same
diff-against-persisted-value approach, since (by the project's own stated
architecture) the key is never read back from storage into the frontend.
`dirty: value.trim().length > 0` — i.e., "there is unsaved input in the
buffer." On save success, `setValueState("")` runs before `saveStatus:
"success"`, so `dirty` becomes `false` in the same tick. On save failure,
`value` is deliberately left untouched (so the user isn't forced to
retype), so `dirty` stays `true`. This is a different, but equally real,
dirty definition than the other two controls — appropriate given the
no-persisted-baseline constraint, not a shortcut.

**Aggregate (`settingsDirty.ts` / `useSettingsPageDirty.ts`)** —
`computeSettingsDirty` is a plain boolean OR of the three flags above; no
other logic. `useSettingsPageDirty` holds the three flags in local
`useState` (fresh per `SettingsPage` mount) and re-derives the OR via
`useMemo`. Verified this is a real aggregation of the three real per-control
signals traced above, not a stub returning a constant.

**Navigation guard (`settingsNavigationGuardStore.ts`)** —
`requestNavigation(targetPath)` returns `"allowed"` (no state change) when
`!this.dirty` or `targetPath === "/settings"`; otherwise sets
`state = { pending: true, targetPath }` and returns `"blocked"`.
`this.dirty` is written **only** by `setDirty()`, called **only** from
`useSettingsNavigationGuardSync`. That hook forwards `SettingsPage`'s own
`settingsDirty` on every change (one effect) and unconditionally clears
the store's `dirty` on unmount (a second, unmount-only effect) — so the
store's notion of "dirty" cannot outlive the `SettingsPage` instance that
produced it.

**Confirmation mechanism (`SettingsNavigationGuardDialog.tsx`)** — renders
`null` unless `state.pending`; Stay/Escape call `store.cancel()` (state
reset, `dirty` untouched); Leave calls `store.confirmLeave()`, which
returns the pending `targetPath`, clears `state` and `dirty`, and the
component then calls `navigate(targetPath)`. The dialog's JSX contains a
single fixed heading/body string; no prop or state value derived from any
Settings field (Theme value, Export Directory path, or the VirusTotal
buffer) is interpolated anywhere in its render output.

**`beforeunload` (`useSettingsBeforeUnloadGuard.ts`)** — one effect keyed
on `settingsDirty`: registers `handleBeforeUnload` only when `true` on the
render the effect runs, and the effect's cleanup (covering both a value
change to `false` and unmount) removes it. `handleBeforeUnload` calls
`event.preventDefault()` and sets `event.returnValue = ""` — a constant,
never a field-derived string.

**Navigation trigger wiring** — `NavigationGroup.tsx`'s link `onClick` and
`CommandPaletteContainer.tsx`'s `handleNavigate` both call
`settingsNavigationGuard.requestNavigation(path)` and return/branch before
their own navigation call when the result is `"blocked"` — confirmed by
reading both call sites directly, not inferred from a test description.

**Wiring into the shell** — `AppShell.tsx` mounts
`<SettingsNavigationGuardDialog />` as a sibling of the routed content, the
same pattern already used for `CommandPaletteContainer`.

## 5. CHECK — required verifications

| Requirement | Independent finding |
|---|---|
| Dirty state is real | Confirmed — `useSettingsFieldSave` diffs against a real `savedBaseline`; `useVirustotalKeySave` checks real buffer length. Neither is a constant or placeholder. |
| Aggregate state is accurate | Confirmed — `computeSettingsDirty` is an unconditional OR of exactly the three flags `useSettingsPageDirty` collects from the three real controls; no flag is dropped or ignored. |
| Navigation protection is connected | Confirmed — both real navigation triggers (`NavigationGroup`, `CommandPaletteContainer`) call `requestNavigation()` before navigating and respect a `"blocked"` result; `SettingsPage` forwards its live `settingsDirty` into the same store the triggers read. |
| Clean state remains unprotected | Confirmed — `requestNavigation` short-circuits to `"allowed"` with no state mutation and no `notify()` call whenever `!this.dirty`; a clean Settings page therefore produces zero observable guard behavior on navigation. |
| Saved state becomes clean | Confirmed for all three controls — Theme/Export Directory: `savedBaseline` is reassigned to the just-saved value on success, making `dirty` false; VirusTotal: the buffer is cleared to `""` on success, making `dirty` false by the same definition. |
| Failed save remains dirty | Confirmed for all three controls — Theme/Export Directory: `savedBaseline` is left untouched on the error branch; VirusTotal: `value` is left untouched on the error branch. In both cases the pre-existing dirty condition still holds after a failed save. |

No requirement in this table was accepted on the basis of a test's name or
description alone; each was traced to the specific line(s) of
implementation source cited above.

## 6. Verdict

**PASS — READY FOR PHASE 2B-2**

The archive's integrity, completeness, and freedom from build/temp debris
are confirmed independently. A from-scratch `npm ci` reproduces the same
clean results as the Phase 2A checkpoint (97/97 test files, 1368/1368
tests, 0 TypeScript errors, clean build). Direct inspection of every
component named in this phase's Source Audit scope confirms the dirty
tracking, aggregation, navigation guard, confirmation dialog, and
`beforeunload` protection are real, connected implementations — not stubs,
constants, or logic contradicted by what the tests merely claim to cover —
and that all six CHECK requirements hold against the actual source. No
material blocker was found. No source file was modified in the course of
this audit.
