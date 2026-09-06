# SOC-IQ Frontend MAX-11 Phase 2A — Highest-Leverage Hardening — Closure

## 1. Baseline

Exact input ZIP: `SOC-IQ-FRONTEND-MAX-10-EXPORT-SECURITY-REMEDIATION-FULL.zip`
(SHA-256 `482bffffcfff6d6f6838e8cf21a0b87cfff1cc5cf50b0b2add777d7a2c3d321f`).
This phase's own audit (`SOC-IQ-FRONTEND-MAX-11-FORENSIC-AUDIT.md`) was
performed first, in this same session, against this exact baseline — no
pre-existing MAX-11 audit was assumed or invented (see that document's §2).

## 2. Selected Direction

**MAX11-F-01**: add a native "Browse…" folder picker to the Export
Directory setting (`ExportDirectoryControl.tsx`), matching the exact
`tauri-plugin-dialog` pattern the Analyze page's "Browse for Analysis"
control already established (`nativeFileSelection.ts`), with no new
Tauri capability grant.

## 3. Scope

**Directly required, implemented:**
- New module `frontend/src/pages/settings/exportDirectoryBrowse.ts`:
  `isDirectoryBrowseSupported()` (mirrors `isNativeFileSelectionSupported`)
  and `pickExportDirectory()` (mirrors `pickNativeReportFile`, using
  `open({ multiple: false, directory: true })` instead of a file-mode
  open). Never throws; every outcome is a typed `ok`/`reason` result.
- `ExportDirectoryControl.tsx`: renders a `variant="secondary"` "Browse…"
  button next to the existing text field, Tauri-only
  (`isDirectoryBrowseSupported()`), that fills the field via the
  existing `setValue` from `useSettingsFieldSave` — it does **not** save
  on the analyst's behalf. A cancelled dialog is a silent no-op; a
  genuine dialog failure surfaces through its own `role="alert"` message
  slot, independent of `saveStatus`.
- Tests: `exportDirectoryBrowse.test.ts` (7 tests, mirrors
  `nativeFileSelection.test.ts`'s structure) and a new
  `ExportDirectoryControl.browse.test.tsx` (9 tests) covering Tauri
  detection, fill-without-save, directory-mode dialog options,
  cancellation, dialog failure + recovery, and interaction with the
  existing Save flow.

**Explicitly out of scope (per MAX11-FORENSIC-AUDIT §8, §10):**
- Reports page `DataTable` column sort (real P3 consistency gap,
  deliberately deferred — see audit §8).
- `package.json` stale description fix (`MAX9-F-01`, P3, unrelated
  surface, deliberately deferred).
- Any Tauri capability manifest change (none needed — see §7 below).
- Any backend/`save_settings` contract change — the field is still
  persisted as a plain string, exactly as before.
- Any other Settings field, page, or export/save-dialog call site.
- No architecture rewrite, no framework change, no new dependency
  (`@tauri-apps/plugin-dialog`'s `open()` was already a project
  dependency and already imported elsewhere in the codebase).

## 4. Files Changed

Diff-audited against a fresh, untouched extraction of the baseline ZIP.
Exactly 4 files differ, all under `frontend/src/pages/settings/`:

- **Modified:** `ExportDirectoryControl.tsx`
- **New:** `exportDirectoryBrowse.ts`
- **New:** `exportDirectoryBrowse.test.ts`
- **New:** `ExportDirectoryControl.browse.test.tsx`

Nothing else — no backend (`app/`), no `src-tauri/`, no
`src-tauri/capabilities/`, no other frontend page or shared module,
`database/soc_iq.db` untouched.

## 5. Functional Changes

`ExportDirectoryControl` now offers, only inside a real Tauri runtime, a
"Browse…" button that opens the native OS folder picker and fills the
text field with the analyst's real, OS-confirmed selection. Outside a
Tauri runtime (plain browser tab, the Vitest/jsdom test environment) the
control renders and behaves exactly as before — a plain, hand-typed text
field — with zero change to that path, verified by the pre-existing
`ExportDirectoryControl.live.test.tsx` suite passing unmodified.

## 6. UX Changes

An analyst changing their export directory can now click "Browse…",
pick a real folder from the native OS dialog, and see it populate the
field immediately — then still click the existing "Save" button to
persist it, exactly matching the Analyze page's established
browse-then-confirm pattern. Cancelling the dialog is silent (matches
native OS convention). A dialog failure shows a plain-language message
("Couldn't open the folder picker. You can still type the path
directly.") that does not block the analyst from continuing to type the
path by hand — the picker is additive, never a hard dependency.

## 7. Accessibility

- The "Browse…" button is a real `<button>` (via the shared `Button`
  primitive) — native keyboard reachability, focus, and
  Enter/Space activation for free, no custom ARIA.
- The browse-failure message uses `role="alert"`, matching the existing
  save-error message's own convention in the same component.
- No change to the existing field's `<label htmlFor>` association, or to
  the Save button's existing states.
- `STATIC VERIFIED` only (source-level, jsdom-DOM-level via the new live
  tests) — `ENVIRONMENT-BLOCKED` for real browser/screen-reader
  verification, unchanged from every prior MAX phase (no browser
  automation available in this sandbox).

## 8. Responsive

The new button sits inside the existing `.settings-page__field-row`
flex container (`display: flex; flex-wrap: wrap; align-items:
flex-end; gap: var(--space-md);`), which already wraps its children —
no new CSS was needed or added. `STATIC VERIFIED` (source/layout-rule
level) — `ENVIRONMENT-BLOCKED` for actual 1440×900/1280×720 rendering,
unchanged from prior phases.

## 9. Motion

No new motion introduced. The button uses the existing shared `Button`
component's existing states/transitions verbatim; no new animation,
transition, or timing was added.

## 10. Performance

No new renders, effects, subscriptions, timers, or polling introduced.
`pickExportDirectory()` is a single `await`ed async call triggered only
on click; no effect, no re-fetch, no change to `useSettingsFieldSave`'s
existing hook internals.

## 11. Security

- **No new Tauri capability grant.** `src-tauri/capabilities/default.json`
  is byte-identical to the baseline (confirmed in the diff-audit, §4).
  Verified via `tauri-plugin-dialog`'s own published Rust source
  (`commands.rs`, v2.3.3/v2.7.0 on docs.rs) that `open()`'s `directory`
  option is one field on `OpenDialogOptions`, handled by the single
  `commands::open` command already gated by the already-granted
  `dialog:allow-open` permission — directory mode is not a separate
  command or permission. Classified `STATIC VERIFIED` against the
  plugin's published source; `ENVIRONMENT-BLOCKED` for a live
  `cargo build`/runtime ACL check (no Rust toolchain in this sandbox —
  `cargo`/`rustc` both absent, confirmed via `which`/`--version`,
  consistent with every prior Tauri-touching session in this project).
- The picker only ever returns a path string to the frontend, same as
  `nativeFileSelection.ts`'s existing `open()` call — it does not read
  or write any file, and does not touch `filesystem-security-model.md`'s
  documented trust boundary (frontend never performs the actual write;
  the Python sidecar does, behind the existing `save_settings`/export
  commands, both fully unmodified by this change).
- No new dependency was added (`@tauri-apps/plugin-dialog` was already
  a `package.json` dependency, already imported by
  `nativeFileSelection.ts` and `reportExportPath.ts`/
  `investigationsCsvExportPath.ts`).

## 12. Testing

Exact commands and results, all run fresh in this session:

```
npm ci
  → added 159 packages, audited 160 packages (unchanged from baseline;
    no new npm dependency)

npx tsc --noEmit
  → 0 errors

npm test -- --run
  → Test Files  84 passed (84)   [baseline: 82 passed]
  → Tests       1203 passed (1203)   [baseline: 1187 passed]
  → 0 failures, 0 unhandled errors
  → net new: 16 tests (7 in exportDirectoryBrowse.test.ts, 9 in
    ExportDirectoryControl.browse.test.tsx); 2 new test files

npm run build
  → tsc --noEmit clean, vite build succeeded
  → 202 modules transformed   [baseline: 201]
  → dist/ produced, no build errors or warnings beyond the pre-existing
    baseline output shape
```

No test was removed, weakened, or skipped. The pre-existing
`ExportDirectoryControl.live.test.tsx` (11 tests covering the plain
text-field path) passes completely unmodified, proving the non-Tauri
fallback path is unaffected.

## 13. Environment Limitations

- **No Rust/Tauri toolchain available in this sandbox** (`cargo`,
  `rustc` both absent). `src-tauri` was not compiled, and the capability
  manifest's runtime ACL behavior for directory-mode `open()` was not
  live-verified — only source-verified against the published plugin
  crate (§11). This is `ENVIRONMENT-BLOCKED`, not a software defect, and
  is the same gap present in every prior MAX/Phase-4 session in this
  project.
- **No browser or Tauri runtime automation available.** All
  accessibility/responsive/motion/visual claims in §7–§9 are
  `STATIC VERIFIED` (source-level) or DOM-level via jsdom-based tests,
  not `RUNTIME VERIFIED` in an actual rendered window.
- Backend (Python) test suite was not re-run this phase — no backend
  file was touched (confirmed in the diff-audit, §4), so it is
  unaffected; re-running it would only reconfirm a baseline this phase
  never modified.

## 14. Regression Assessment

| | Baseline | This phase | Delta |
|---|---|---|---|
| Frontend test files | 82 | 84 | +2 |
| Frontend tests | 1187 | 1203 | +16 |
| Frontend test failures | 0 | 0 | 0 |
| TypeScript errors | 0 | 0 | 0 |
| Build modules | 201 | 202 | +1 |
| Build errors | 0 | 0 | 0 |
| Files changed outside scope | — | 0 | 0 |

No test was removed. No existing test was modified. No regression found.

## 15. Remaining Findings

Carried forward from `SOC-IQ-FRONTEND-MAX-11-FORENSIC-AUDIT.md` §8–9,
deliberately not addressed this phase per the hard-scope rule:

- Reports page `DataTable` has no column sort (P3, consistency gap,
  candidate for a future MAX cycle).
- `MAX9-F-01`: `package.json`'s `description` field is stale (P3,
  docs-only, zero runtime effect).

No new finding was introduced by this phase's own change.

## 16. Verdict

```text
MAX-11 PHASE 2A — PASS WITH DOCUMENTED CONDITIONS
```

Conditions: the Tauri capability-coverage claim (§11) and all
accessibility/responsive claims (§7–§8) are source/static-verified only,
pending a real `cargo build` + rendered-runtime check in an environment
with a working Rust toolchain and browser/Tauri automation — the same
standing condition every MAX/Phase-4 session in this project has carried.

Per the task brief's hard stop: **MAX-11 Phase 2A is complete.** No
Phase 2B/3 work, no MAX-12, no unrelated P2/P3 fix (Reports sort,
`package.json` description) was started.

## 17. Final Package Verification

- `SOC-IQ-FRONTEND-MAX-11-PHASE-2A-HIGHEST-LEVERAGE-HARDENING-FULL.zip`
- Size: 2,560,941 bytes
- SHA-256: `8630d8476c78fd20a618b7e8480a1839330aaea6bcea0ec48645bf9af9292b8a`
- `unzip -t`: no errors detected
- Entries: 823 (directories + files); extracted file count: 737
  (baseline 732 + 5 new: `exportDirectoryBrowse.ts`,
  `exportDirectoryBrowse.test.ts`, `ExportDirectoryControl.browse.test.tsx`,
  this closure doc, `SOC-IQ-FRONTEND-MAX-11-FORENSIC-AUDIT.md`)
- No nested checkpoint ZIP present (only match for `.zip` in the entry
  listing is the archive's own `unzip -l` header line, not a contained
  file)
- `node_modules/`, `dist/`, `target/`, `__pycache__/`,
  `.pytest_cache/`, `coverage/`, `.vscode/`, `.idea/` all confirmed
  absent
- Fresh extraction diffed byte-for-byte against the working tree used
  to build it: identical (`diff -rq`: no output, exit 0)
- `.github/workflows/ci.yml`, `.gitignore`, `.python-version` (project
  files outside the exclusion list) confirmed preserved
