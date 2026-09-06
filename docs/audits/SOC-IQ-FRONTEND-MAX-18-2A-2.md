# SOC-IQ Frontend MAX-18 — Phase 2A-2 Audit

**MAX18-F-01 — Unsaved Settings edits are silently discarded on navigation.**
**This checkpoint: Settings dirty-state aggregation only.**

## Baseline

Authoritative input, per this checkpoint's task brief:

| | |
|---|---|
| Supplied file | `SOC-IQ-FRONTEND-MAX-18-2A-1-FULL-PROJECT.zip` |
| Supplied SHA-256 | `8ff4463e8076d7c882ecdb26be23a8a56ef2f4e8052edfa739ea8b7230b70756` |

Name and hash both match the brief's stated authoritative input — no
discrepancy to flag this checkpoint (contrast Phase 2A-1's audit,
which did have to flag one).

The supplied project already contained Phase 2A-1's foundation work:
`settingsDirty.ts` (`computeSettingsDirty`, `SettingsDirtyFlags`) and
its tests, `useVirustotalKeySave`'s `dirty` flag, and
`SettingsPage.live.test.tsx`. All pre-existing tests passed before any
change in this checkpoint (`npx vitest run` — 92 test files, 1291
tests, 0 failed, prior to this checkpoint's own new test files being
added).

## Objective recap

Phase 2A-1 built `computeSettingsDirty`, a pure combinator, but
deliberately left it unwired — nothing lifted the three controls'
independent `dirty` flags into one place. This checkpoint's entire job
is that wiring: connect Theme, Export Directory, and VirusTotal
dirty-state signals into one reliable `settingsDirty` aggregate inside
`SettingsPage`'s existing architecture, with no second persistence
mechanism and no change to how any value is saved.

## Files changed

| File | Change |
|---|---|
| `frontend/src/pages/settings/useSettingsPageDirty.ts` | **New.** `useSettingsPageDirty()` — holds the three per-control `dirty` booleans as local `useState`, re-derives `settingsDirty` via the Phase 2A-1 `computeSettingsDirty` combinator, and exposes one stable setter per control (`handleThemeDirtyChange`, `handleExportDirectoryDirtyChange`, `handleVirustotalKeyDirtyChange`). |
| `frontend/src/pages/settings/useSettingsPageDirty.test.tsx` | **New.** Hook-level tests: initial state, the full required combination matrix, per-flag independence, and fresh-mount isolation. |
| `frontend/src/pages/settings/ThemeControl.tsx` | Added an optional `onDirtyChange?: (dirty: boolean) => void` prop; a `useEffect` reports the control's existing `dirty` value (from `useSettingsFieldSave`, unchanged) whenever it changes. No new dirty logic — a notification of an existing value. |
| `frontend/src/pages/settings/ExportDirectoryControl.tsx` | Same addition, same pattern, same source (`useSettingsFieldSave`'s `dirty`). |
| `frontend/src/pages/settings/VirustotalControl.tsx` | Same addition, reporting `useVirustotalKeySave`'s existing `dirty` (Phase 2A-1). Only the boolean crosses this new callback — never the edit buffer itself. |
| `frontend/src/pages/SettingsPage.tsx` | Calls `useSettingsPageDirty()` and passes its three handlers to the three controls' new `onDirtyChange`. Wraps the existing success-view JSX in a `display: contents` `<div data-settings-dirty={settingsDirty}>` — a non-visual marker exposing the aggregate for tests and for whatever Phase 2A-3 ends up consuming it from. No control's rendering, save flow, or the loading/error views changed. |
| `frontend/src/pages/SettingsPage.dirtyAggregate.live.test.tsx` | **New.** Real-component integration tests: the full required combination matrix at the page level, saving-clears-only-that-control, failed-save preservation, unmount/remount isolation, and a secret-handling check on the new marker. |

`useSettingsFieldSave.ts`, `useVirustotalKeySave.ts`, and
`settingsDirty.ts` are **unchanged** — each already had a correct,
independently-tested `dirty` signal or combinator; this checkpoint
only had to connect them, not re-derive them.

## Dirty-state model (updated)

```
ThemeControl            ──dirty──▶ onDirtyChange ──▶ handleThemeDirtyChange
ExportDirectoryControl  ──dirty──▶ onDirtyChange ──▶ handleExportDirectoryDirtyChange   } useSettingsPageDirty
VirustotalControl       ──dirty──▶ onDirtyChange ──▶ handleVirustotalKeyDirtyChange
                                                              │
                                                              ▼
                                            computeSettingsDirty(flags)
                                                              │
                                                              ▼
                                                     settingsDirty (SettingsPage)
```

Each arrow into `useSettingsPageDirty` carries a boolean only, sourced
entirely from state each control already held for its own Save-button
`disabled` condition (Phase 2A-1). `useSettingsPageDirty` stores no
field value, no persisted baseline, and no edit buffer — three
booleans and their OR, nothing else. `SettingsPage` itself introduces
no second persistence mechanism and does not alter `save_settings` /
`keystore_set_secret` call sites, argument shapes, or timing in any
control.

## Test coverage

Against the brief's required combination table and behavior bullets:

| Requirement | Covered by |
|---|---|
| clean/clean/clean → clean | `useSettingsPageDirty.test.tsx`, `SettingsPage.dirtyAggregate.live.test.tsx` |
| dirty/clean/clean → dirty | Same two files |
| clean/dirty/clean → dirty | Same two files |
| clean/clean/dirty → dirty | Same two files |
| dirty/dirty/clean → dirty | Same two files |
| dirty/clean/dirty → dirty | Same two files |
| clean/dirty/dirty → dirty | Same two files |
| dirty/dirty/dirty → dirty | Same two files |
| Saving Theme clears only Theme's contribution | `SettingsPage.dirtyAggregate.live.test.tsx` ("saving Theme while Export Directory and VirusTotal stay dirty leaves the aggregate dirty"), and "saving every dirty control in turn returns the aggregate to clean" |
| Export remains dirty if still unsaved | Same "saving Theme…" test — Export Directory's contribution is still reflected after Theme alone is saved |
| VirusTotal remains dirty if still unsaved | Same test — VirusTotal's contribution is still reflected after Theme alone is saved |
| Failed save preserves dirty state | `SettingsPage.dirtyAggregate.live.test.tsx` ("a failed save preserves that control's dirty contribution", "a failed VirusTotal save preserves the aggregate as dirty") |
| Unmount/remount does not falsely report dirty | `useSettingsPageDirty.test.tsx` ("a new hook instance never inherits a previous instance's dirty state"), `SettingsPage.dirtyAggregate.live.test.tsx` ("a fresh mount never falsely reports dirty…", "unmounting with in-flight saves on multiple controls does not throw and does not falsely mark a later remount dirty") |
| Secret values remain protected | `SettingsPage.dirtyAggregate.live.test.tsx` ("the VirusTotal edit buffer never leaks into the dirty aggregate's own markup") — the marker carries only the boolean; `container.textContent` is asserted not to contain the entered value, on top of the pre-existing per-component and Phase 2A-1 page-level guards |

All new tests exercise real hook/component behavior (real `<select>`/
`<input>` DOM events, real `createRoot`/`act` lifecycles, the actual
`SettingsPage` composition of all three controls) — consistent with
the codebase's existing `*.live.test.tsx` convention. No existing test
was weakened, skipped, or deleted.

## Verification results

Run from `frontend/`:

```
npm ci               → 159 packages installed, no errors
npx vitest run       → 92 test files, 1291 tests passed, 0 failed
npx tsc --noEmit     → no errors
npm run build        → tsc --noEmit && vite build succeeded, dist/ produced
```

## Security considerations

- `onDirtyChange` on all three controls carries a `boolean` only —
  the VirusTotal edit buffer's actual contents never cross this or
  any other new boundary added in this checkpoint. `useSettingsPageDirty`
  itself never receives, stores, or logs a field value.
- No new logging was added anywhere in this change.
- `data-settings-dirty` renders one of the literal strings `"true"` /
  `"false"` — never a value, a diff, or anything derived from a
  control's edit buffer.
- `SettingsPage.dirtyAggregate.live.test.tsx` asserts the entered
  VirusTotal key never appears in `container.textContent` after being
  typed, on top of the pre-existing per-component and Phase 2A-1
  page-level guards for the same property.

## Scope compliance

No navigation interception, `beforeunload` handling, confirmation
dialog, autosave, global (cross-page) dirty-state store, router
change, CommandPalette change, backend/Rust/Tauri change, AI work, or
visual redesign was introduced. The new `data-settings-dirty` marker
uses `display: contents` specifically so it adds no layout, box, or
visual difference to the rendered page — verified by `npm run build`
producing a normal `dist/` and by no existing rendering test (static
or live) needing any change to keep passing. `ThemeControl`,
`ExportDirectoryControl`, `VirustotalControl`'s existing markup,
labels, save/error/retry flows, and the non-functional mock sections
below them are otherwise unchanged. `useSettingsFieldSave.ts`,
`useVirustotalKeySave.ts`, and `settingsDirty.ts` were left untouched,
since each already satisfied this checkpoint's needs as-is.

## Known limitations

- **`settingsDirty` is aggregated and exposed but still not consumed
  for any user-facing behavior.** Per this checkpoint's explicit scope
  boundary, nothing reads `data-settings-dirty` (or could import
  `useSettingsPageDirty`'s value) to block navigation, warn on close,
  or autosave — that is Phase 2A-3's job. This checkpoint's contract
  ends at "the aggregate is correct, tested, and observable."
- The `data-settings-dirty` marker is the only externally observable
  surface for the aggregate from outside `SettingsPage`. If Phase
  2A-3 needs the aggregate value itself (not just a DOM marker) — e.g.
  to gate a router-level guard — it will need to either read this
  attribute, lift `useSettingsPageDirty`'s return value further up
  through a prop/callback on `SettingsPage`, or hoist the hook one
  level higher. No such lifting was added here, since nothing in this
  checkpoint consumes it yet and speculative plumbing for an
  unspecified future consumer would be exactly the "global dirty-state
  infrastructure" the brief says not to build.

## Final verdict

`PASS — READY FOR MAX-18 PHASE 2A-3`

All required combinations verified, all required behaviors (save
clears only its own field, failed save preserves dirty, unmount/
remount does not falsely report dirty, secret values stay protected)
tested against real component/hook behavior. `npm ci`, `npx vitest
run`, `npx tsc --noEmit`, and `npm run build` all pass clean with no
existing test weakened or removed. No out-of-scope work (navigation
guards, dialogs, `beforeunload`, autosave, global state, backend/Rust/
Tauri, unrelated UI) was introduced.
