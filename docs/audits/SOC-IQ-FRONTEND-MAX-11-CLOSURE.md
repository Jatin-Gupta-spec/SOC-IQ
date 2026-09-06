# SOC-IQ Frontend MAX-11 — Phase 2B Post-Implementation Re-Audit + Closure

## 1. Authoritative Baseline

- Input archive: `SOC-IQ-FRONTEND-MAX-11-PHASE-2A-CHECKPOINT-FULL.zip`, extracted
  and inspected directly (`bash_tool`/`view`), not summarized from prior docs.
- Contains `docs/audits/SOC-IQ-FRONTEND-MAX-11-FORENSIC-AUDIT.md` (Phase 1) and
  `docs/audits/SOC-IQ-FRONTEND-MAX-11-PHASE-2A-HIGHEST-LEVERAGE-CLOSURE.md`
  (Phase 2A), both read in full before verification began.
- No `.git` directory present — filesystem/mtime-based provenance used, same
  constraint as every prior MAX phase in this project.

## 2. MAX-11 Audit Reference (Phase 1)

Zero P0/P1 findings. One new P2 finding selected: **MAX11-F-01** — the Export
Directory setting (`ExportDirectoryControl.tsx`) had no native folder picker,
only a hand-typed text field. Two P3 items carried forward unselected
(Reports `DataTable` lacking column sort; `MAX9-F-01`, a stale
`package.json` description).

## 3. Selected Direction

Add a native "Browse…" folder-picker button to `ExportDirectoryControl`,
reusing the exact `tauri-plugin-dialog` pattern already established by
`nativeFileSelection.ts` (Analyze page), with no new Tauri capability grant.

## 4. Phase 2A Implementation Summary (as re-verified this phase)

Independently re-derived, not copied from the Phase 2A closure doc's prose:

- **New:** `frontend/src/pages/settings/exportDirectoryBrowse.ts` —
  `isDirectoryBrowseSupported()` + `pickExportDirectory()`, a typed
  `ok`/`reason` result, never throws. Correctly omits `plugin-fs`/`readFile`
  (unlike its `nativeFileSelection.ts` model) because a directory picker only
  ever needs to return a path, not file bytes — a deliberate, justified
  divergence from its reference pattern, not a missed detail.
- **Modified:** `ExportDirectoryControl.tsx` — renders a `variant="secondary"`
  "Browse…" button (Tauri-only, via `isDirectoryBrowseSupported()`) that
  fills the field through the existing `setValue` and does **not** save on
  the analyst's behalf; a dialog failure surfaces through its own
  `role="alert"` slot independent of `saveStatus`; cancellation is a silent
  no-op.
- **New:** `exportDirectoryBrowse.test.ts` (7 tests), `ExportDirectoryControl.
  browse.test.tsx` (9 tests).

## 5. Verification Performed This Phase (fresh, independent)

All commands run directly against the extracted archive in this session —
none of the numbers below are taken on faith from the Phase 2A closure doc.

| Check | Command | Result |
|---|---|---|
| Install | `npm ci` | 159 packages added, 160 audited — matches claimed baseline dependency count, no new package |
| Types | `npx tsc --noEmit` | **0 errors** |
| Tests | `npm test -- --run` | **84 test files passed (84), 1203 tests passed (1203), 0 failures** |
| Build | `npm run build` | **Clean** — `tsc --noEmit` + `vite build`, 202 modules transformed, no errors/warnings beyond baseline shape |
| Targeted re-run | `vitest run` on the 3 affected files | 3 files, 24 tests, all pass (7 + 9 + 8 from `ExportDirectoryControl.live.test.tsx`, which is the pre-existing, unmodified non-Tauri fallback suite) |

Every number in the Phase 2A closure doc's §12/§14 was independently
reproduced exactly (test file count, test count, module count, error counts).

## 6. Diff Forensics / Scope Verification

Timestamp-based diff (mtime clustering: baseline files cluster at one
timestamp; the four claimed files cluster ~10 minutes later, isolated from
everything else) plus targeted `find` sweeps of `app/`, `src-tauri/`,
`database/`, `keystore-core/`, `sidecar-core/`, `packaging/`, `tests/`, and
`frontend/` outside `src/`:

- **Exactly 4 files changed** under `frontend/src/pages/settings/`, matching
  the Phase 2A closure doc's own claim precisely: 1 modified
  (`ExportDirectoryControl.tsx`), 3 new (`exportDirectoryBrowse.ts`,
  `exportDirectoryBrowse.test.ts`, `ExportDirectoryControl.browse.test.tsx`).
- **Zero** files touched outside that directory — no backend, no
  `src-tauri/`, no capability manifest, no other frontend page, no shared
  module, no CSS file (confirmed `SettingsPage.css`'s `.settings-page__
  field-row` flex-wrap rule the new button relies on already existed,
  byte-identical, before this change — no new CSS was needed or added).
- **No scope creep found.** No unrelated refactor, no unnecessary
  complexity, no duplicated logic, no abstraction regression, no dead code.
- `src-tauri/capabilities/default.json` independently re-read: still exactly
  `["core:default", "dialog:allow-open", "dialog:allow-save",
  "fs:allow-read-file"]` — the "no new capability grant" claim holds. (This
  is a static/manifest-content check, not a compiled ACL check — no Rust
  toolchain is available in this sandbox, consistent with every prior
  Tauri-touching MAX phase; the underlying claim that `open()`'s
  `directory: true` mode shares `dialog:allow-open` with file-selection mode
  is a property of the published `tauri-plugin-dialog` crate, not something
  re-derivable from this repository alone, and was not re-verified against
  the crate source in this phase.)

## 7. Finding Closure Matrix

| MAX-11 Finding | Original Severity | Current Status | Evidence | Closure |
|---|---|---|---|---|
| MAX11-F-01 (no native export-directory picker) | P2 | **FIXED** | `exportDirectoryBrowse.ts` + `ExportDirectoryControl.tsx` reviewed line-by-line against the original gap description; native "Browse…" button present, Tauri-gated, correctly fills-without-saving; 16 new tests (7+9) exercise support-detection, directory-mode dialog options, fill-without-save, cancellation, dialog failure + recovery, and interaction with the existing Save/dirty/retry flow — all passing | **Closed** |
| Reports `DataTable` no column sort | P3 | Unchanged (deliberately deferred, per audit §8/§10) | `ReportsPage`'s `DataTable` was not part of the diff (confirmed §6) | Not in scope — carried forward |
| `MAX9-F-01` (`package.json` stale description) | P3 | Unchanged, confirmed still present verbatim in `frontend/package.json` | Re-read directly this phase | Not in scope — carried forward |

## 8. Regression / Quality Summary

| Area | Result |
|---|---|
| Phase 2A scope | **PASS** — exactly the 4 claimed files, nothing else |
| Functional behavior | **PASS** — non-Tauri fallback path unchanged (11-test `.live.test.tsx` suite passes unmodified); new Tauri browse path behaves as specified |
| Accessibility | **PASS (STATIC/DOM-level only)** — real `<button>` via shared `Button` primitive (native keyboard/focus semantics), `role="alert"` on the new error slot matching the existing convention; no real browser/screen-reader verification possible in this sandbox (`ENVIRONMENT-BLOCKED`, unchanged standing condition) |
| Responsive behavior | **PASS (STATIC only)** — new button sits inside the pre-existing wrapping flex row; no new CSS added or needed; no rendered-viewport verification possible (`ENVIRONMENT-BLOCKED`, unchanged standing condition) |
| Performance | **PASS** — single awaited async call on click only; no new effects, subscriptions, timers, or re-renders introduced |
| Security | **PASS (manifest-content verified; crate-source claim not re-verified this phase)** — capability manifest byte-identical to baseline; picker returns a path string only, never touches the write path (unchanged Python-sidecar boundary) |
| Regression | **PASS** — 0 test failures, 0 TypeScript errors, 0 build errors; pre-existing suite fully intact |
| TypeScript | **PASS** — `npx tsc --noEmit`: 0 errors |
| Tests | **PASS** — 84/84 files, 1203/1203 tests |
| Production build | **PASS** — clean, 202 modules |

## 9. Remaining Conditions (Non-Blocking)

- Capability-coverage and accessibility/responsive claims remain
  `STATIC VERIFIED`/`ENVIRONMENT-BLOCKED`, not `RUNTIME VERIFIED` — no Rust
  toolchain or browser/Tauri runtime automation is available in this
  sandbox. This is an unchanged, standing condition across every MAX/Phase-4
  session in this project, not a defect introduced by MAX-11.
- This phase did not independently re-verify `tauri-plugin-dialog`'s
  published Rust source for the "one command, one permission, mode-agnostic"
  claim underlying the "no new capability grant" conclusion; it relied on
  confirming the manifest file itself is unchanged, which is the
  repository-level fact within this sandbox's reach.
- Two P3 items (Reports sort, `package.json` description) remain open,
  correctly out of scope for MAX-11 per the hard-scope rule.

## 10. Known Environmental Limitations

- No `.git` — provenance is filesystem/mtime-based, not commit-based.
- No Rust/Tauri toolchain (`cargo`/`rustc` absent) — `src-tauri` was not
  compiled this phase either.
- No real browser or Tauri runtime — all UI-level claims beyond what jsdom
  can exercise are source/static-level.
- Backend (Python) suite was not re-run: no backend file was touched by
  Phase 2A (confirmed in §6), so re-running it would only reconfirm an
  untouched baseline.

## 11. Final Verdict

```
MAX-11: CLOSED WITH CONDITIONS
```

MAX11-F-01 is genuinely resolved — not merely "code changed," but verified
by direct reading of both the picker module and the modified control against
the original gap description, exact reproduction of all test/build numbers,
and confirmation via timestamp forensics that no unrelated file was touched
and no scope crept beyond the four files the implementation claimed. No
regression was found anywhere in the swept surface. The only reason this is
not an unconditional CLOSED is the same standing, non-blocking environmental
condition present in every prior MAX phase: no Rust toolchain and no
real browser/Tauri runtime exist in this sandbox to compile-verify the
capability manifest or visually/interactively verify accessibility and
responsive behavior beyond jsdom.

**MAX-11 is complete.** No MAX-12 work was started or scoped in this phase.
