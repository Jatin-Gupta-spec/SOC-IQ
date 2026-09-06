# Phase 4I Remediation — Part 1: Blocker A (Filesystem Bridge)

## Scope

Per the task brief: audit the current checkpoint, remediate Blocker A
only, add/modify Blocker A tests, verify as far as this environment
allows, package a complete-project checkpoint zip. Phase 4J was not
started; the Analysis page/workflow, `AnalysisWorkflow`,
runId/correlationId handling, SSE progress, retry state machine,
`FileDropzone`'s existing accessibility model, the shared design
system, router, `AppShell`, and the sidecar lifecycle (4G/4H) were not
redesigned or rewritten.

## Audit findings

- `src-tauri/capabilities/default.json` granted only `core:default`
  and `get_sidecar_origin` — no `tauri-plugin-dialog` dependency
  existed anywhere in `Cargo.toml`/`Cargo.lock`, and no
  `@tauri-apps/plugin-dialog`/`@tauri-apps/plugin-fs` package existed
  in `frontend/package.json`. The task brief's note that the checkpoint
  "may already contain the previously justified `tauri-plugin-dialog`"
  did not match the actual checked-out state — confirmed absent before
  any change was made.
- `frontend/src/pages/analyze/analysisReportPath.ts::resolveReportPath`
  was an unconditional `{ ok: false, reason: "no-filesystem-capability" }`
  for every input — real user-selected-file analysis could not execute,
  exactly as described.
- `AnalysisInput` (`analysisInput.ts`) had no field capable of carrying
  a real filesystem path.
- `FileDropzone.tsx` was already a real, accessible native
  `<label>` + `<input type="file">` + drag/drop control — correctly
  identified by the brief as not itself the defect (a browser `File`
  never carries a real path, regardless of capability grants).
- `analysisExecution.ts`/`useAnalysisExecution.ts`/`AnalyzePage.tsx`
  already correctly gated `canStart`/`canRetry` on
  `resolveReportPath`'s result and surfaced `blockedReason` — this
  machinery needed no redesign, only a real `ok: true` path to
  exercise it.

## Architecture implemented

```
USER
 -> AnalyzePage's "Browse for Analysis" button (native, Tauri-only)
 -> nativeFileSelection.ts: tauri-plugin-dialog open() -> real absolute path
 -> tauri-plugin-fs readFile(path) -> real bytes (client-side UTF-8 validation only)
 -> AnalysisInput.sourcePath = that real path (toNativeAnalysisInput)
 -> analysisReportPath.ts: resolveReportPath() trusts sourcePath (validated)
 -> analysisExecution.ts: executeAnalysis(reportPath) -> analyze_report command
 -> existing app/application/handlers.py pipeline (unchanged)
```

Browser drag/drop and `<input type="file">` (`FileDropzone`, unchanged)
remain honestly blocked: no fake path is ever synthesized from
`file.name` or otherwise for those two selection paths. This is not a
regression — it is the same limitation the pre-remediation code already
declared, now scoped correctly to only the paths that are structurally
incapable of a real filesystem path (per Tauri/browser security, not
per any capability grant).

## Dependency addition (Cargo.toml §4 disclosure)

`tauri-plugin-dialog` and `tauri-plugin-fs` were added — both official,
first-party `tauri-apps` plugins, the maintained Tauri v2 path for this
exact use case. Full reason/security/bundle disclosure lives in
`src-tauri/Cargo.toml`'s dependency comment and
`src-tauri/capabilities/default.json`'s description field (narrow
permissions only: `dialog:allow-open`, `fs:allow-read-file` — not the
wildcard `dialog:default`/`fs:default`, and no static `fs` path scope).

## Files changed

- `frontend/src/pages/analyze/analysisInput.ts` — added optional
  `sourcePath` field + `toNativeAnalysisInput()`.
- `frontend/src/pages/analyze/analysisReportPath.ts` — `resolveReportPath`
  now resolves `ok: true` for a validated `sourcePath`; added
  `isTrustedAbsolutePath` (non-empty, no NUL, absolute POSIX/Windows/UNC).
- `frontend/src/pages/analyze/nativeFileSelection.ts` — **new**. Wraps
  `tauri-plugin-dialog`'s `open()` and `tauri-plugin-fs`'s `readFile()`;
  typed `NativeFileSelectionResult`; `isNativeFileSelectionSupported()`
  via `@tauri-apps/api/core`'s `isTauri()`.
- `frontend/src/pages/AnalyzePage.tsx` / `.css` — added a "Browse for
  Analysis" button, shown only when `isNativeFileSelectionSupported()`;
  refactored `handleFileSelected` into a shared `handleInputSelected`
  used by both the existing `FileDropzone` path and the new native path.
- `frontend/src/pages/analyze/analysisInput.test.ts`,
  `analysisReportPath.test.ts` — extended.
  `nativeFileSelection.test.ts` — **new** (7 tests).
- `frontend/package.json` / `package-lock.json` — added
  `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-fs` (real `npm install`
  run, lockfile genuinely regenerated).
- `src-tauri/Cargo.toml` — added `tauri-plugin-dialog`, `tauri-plugin-fs`
  with the full dependency-rule disclosure.
- `src-tauri/src/lib.rs` — registered both plugins via `.plugin(...)`
  in `run()`; no new `#[tauri::command]` (both plugins are called
  directly from the frontend via their own JS bindings).
- `src-tauri/capabilities/default.json` — added `dialog:allow-open`,
  `fs:allow-read-file`.

No file outside this list was touched — confirmed by a full recursive
diff against the untouched extraction of the uploaded checkpoint zip
(`node_modules`/`.git`/`dist` excluded from the comparison as
non-source).

## Tests

New/modified, covering the brief's 8 required properties:

1. Native selected report produces a valid backend-readable path —
   `nativeFileSelection.test.ts` ("resolves ok with a real sourcePath
   ..."), `analysisReportPath.test.ts` (POSIX/Windows-drive/UNC cases).
2. Invalid source rejected — `analysisReportPath.test.ts` (empty,
   relative).
3. Missing source rejected — `analysisReportPath.test.ts` (no
   `sourcePath` at all → still `ok: false`), `analysisInput.test.ts`
   ("never sets sourcePath for a browser-selected file").
4. Unsafe path/source handling rejected — `analysisReportPath.test.ts`
   (embedded NUL byte).
5. Real `analyze_report` command receives the correct path —
   pre-existing `analysisExecution.test.ts` ("calls the real
   analyze_report command with the given report path"), unmodified,
   unregressed.
6. Existing file selection behavior preserved —
   `FileDropzone.test.tsx`/`.live.test.tsx` unmodified and still pass
   in full.
7. Browser-only unsupported path behavior remains honest —
   `analysisReportPath.test.ts` ("is blocked for a plain
   browser-selected file").
8. No arbitrary filesystem/command access introduced — enforced by the
   narrow, named capability permissions (no `dialog:default`/`fs:default`,
   no static `fs` scope) and by `nativeFileSelection.ts` only ever
   calling `dialog.open()`/`fs.readFile()`, never any other plugin
   command.

No existing test was weakened, skipped, or deleted.

## Verification actually performed

- `npm install` (real, `frontend/`): succeeded, `package-lock.json`
  genuinely regenerated (159 packages added).
- `npx tsc --noEmit`: **0 errors**.
- `npx vitest run`: **572/572 tests passing**, 45 test files (up from
  44 — `nativeFileSelection.test.ts` is new; every pre-existing test,
  including `FileDropzone`'s and `analysisExecution`'s, passes
  unmodified).
- `npm run build` (`tsc --noEmit && vite build`): **succeeded** — 153
  modules transformed, real `dist/` output produced.
- `cargo check`/`cargo build`: **not run — this environment has no
  Rust toolchain at all** (`cargo`/`rustc` both report "not found"),
  consistent with the majority of this project's prior Phase 4 Rust
  checkpoints. This is reported honestly rather than assumed to pass;
  `Cargo.lock` was **not** regenerated (no `cargo` available to do so
  correctly) and will need `cargo build`/`cargo generate-lockfile` in
  an environment with a working toolchain before this checkpoint's
  Rust changes are compiled for the first time. The task brief's noted
  `icu_locale_core`/edition2024 blocker was not specifically
  re-encountered or re-diagnosed here, since no Rust command could be
  run at all in this environment (a strictly worse starting condition
  than "blocked partway through a build").
- Diff audit: full recursive `diff -rq` against the untouched uploaded
  zip extraction — only the files listed above differ; no unrelated
  churn.

## Honest status

Blocker A is implemented and the frontend side is fully, genuinely
verified (typecheck, full test suite, production build). The Rust
side (plugin registration, capability grant, dependency addition) is
implemented and documented but **not compiled** in this session —
flagged, not silently assumed correct, per the brief's own instruction
not to claim a Rust compilation pass without a real `cargo build`.
Blocker B is explicitly out of scope for this part and was not
started; Phase 4J was not started.
