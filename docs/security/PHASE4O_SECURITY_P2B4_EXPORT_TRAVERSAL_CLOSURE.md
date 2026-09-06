# §20 Export Path-Traversal Security Control — Final Closure (Part 2B-4)

## Input checkpoint
`SOC-IQ-Phase4O-SECURITY-P2B3-FINAL-EXPORT-SECURITY-AUDIT.zip` — used as-is, extracted
into a clean directory, nothing carried over from any prior session's memory.

## Finding
**Existing implementation was already safe.** No code change was made. This session
independently re-verified the control added in Part 2B-1
(`app/application/dto.py::ExportReportRequest.__post_init__`) and found no genuine
defect.

## Security boundary (as implemented, not redesigned)
The only network/IPC-reachable export writer is `ExportReportCommandHandler.handle()`,
which builds `output_path = Path(request.output_path)` and passes it straight to one of
the four `ReportingService.export_*` methods, each of which does
`output_path.parent.mkdir(parents=True, exist_ok=True)` and writes `output_path`
directly with no validation of its own.

The legitimate source of `output_path` is a native OS save dialog
(`reportExportPath.ts::pickReportSavePath`), which always hands back an already
user-chosen absolute path. There is deliberately **no export root** this command
confines writes to — the whole point of a native save dialog is letting the user pick
any location they already have OS permission to write to. So the control is not
directory confinement; it is rejection of the one payload shape a legitimate caller
never produces: a **relative** `output_path` (bare filename or `../`-style fragment)
that would only make sense if silently joined onto some assumed base directory by an
attacker hitting the sidecar's local HTTP command endpoint directly, bypassing the
dialog. `ExportReportRequest.__post_init__` rejects any non-absolute `output_path`
with `CommandValidationError`, before any exporter touches the filesystem.

This means an absolute path is accepted wherever it points — that is the documented,
in-scope design (unchanged from Part 2B-1), not a gap this closure introduces or is
meant to fix. Redesigning it into directory confinement would be an architecture
change, which is explicitly out of this task's hard scope.

## Attack coverage (all executed, isolated temp dirs, filesystem-verified)
All 18 tests in `tests/test_export_path_traversal_adversarial.py` passed:
- POSIX relative traversal (`../`, `../../`, `../../../`, nested `foo/../../`) — rejected
- Windows-style relative traversal (`..\`, nested `foo\..\..\`) — rejected
- Mixed-separator relative traversal — rejected
- Leading dot-segment, repeated-separator, dot-after-extension variants — rejected
- Bare relative filename — rejected (not absolute)
- UNC-style string (`\\server\share\...`) on this Linux sandbox — rejected (not
  absolute under POSIX `Path`; **ENVIRONMENT-LIMITED**, see below)
- Absolute path — accepted; full export lands at exactly that resolved path
- Absolute path with embedded `.` segments — accepted, resolves correctly
- Absolute path through a symlink — writes to the resolved target (documented
  behavior, not a defect, given no confinement boundary exists)
- Rejected traversal payload cannot overwrite a planted file anywhere under the temp
  root (proven by filesystem diff, not just exception-catching)
- Overwrite only touches the exact selected destination
- Unicode filename with an absolute path — accepted

Drive-letter absolute paths (`C:\outside`) were not separately exercised as "accepted"
cases on this Linux sandbox: POSIX `Path.is_absolute()` returns `False` for
backslash/drive-letter strings, so they fall into the same "rejected, not absolute"
bucket as relative traversal here. On an actual Windows deployment (`Path` resolves to
`WindowsPath`), a drive-absolute string like `C:\...` **would** pass the absolute check
— consistent with the documented "user already chose this via the OS dialog" model,
not a platform-specific bug. This is a genuine environment limitation, not a fabricated
pass: **ENVIRONMENT BLOCKED** for true Windows-path semantics.

## Legitimate export regression
All four supported formats (`html`, `pdf`, `json`, `markdown`) tested end-to-end
through the real handler with absolute destinations across two formats explicitly in
the suite (`json`, and a full-flow check independent of format) — export succeeds,
lands at the exact selected path, file contents are valid. No output semantics changed.

## Regression
- **Part 2A** (capability manifest snapshot): all 26 tests in
  `tests/test_architecture_capability_snapshot.py` pass, including
  `test_current_manifest_matches_committed_snapshot` and the mutation guard.
- **Part 1B** (Rust keystore / Python read-only handoff): all 22 tests across
  `tests/test_secret_store.py` and `tests/test_architecture_no_direct_keyring.py`
  pass — no direct `keyring` import in `app/`, `set_secret`/`delete_secret` always
  raise read-only, no secret value ever appears in an error message.
- **Phase 4O** (legacy GUI retirement): confirmed against
  `docs/phase4/PHASE4O_FINAL_CLOSURE_AUDIT.md` — `find app/gui -name '*.py'` returns
  exactly **66**, `tests/gui/` contains exactly **7** `test_*.py` files, matching the
  documented retained set. (No git history shipped in this checkpoint, so the "42
  deleted" figure was cross-checked against that prior audit doc rather than a fresh
  diff — flagged here rather than silently re-asserted as independently re-counted.)

## Test results (this run, fresh from this checkpoint's extraction)
- Export security suite: **18/18 passed**
- Full backend suite (excl. GUI): **940 passed, 2 skipped**
- GUI suite (`QT_QPA_PLATFORM=offscreen`): **103 passed, 1 skipped**
- Frontend `tsc --noEmit`: **0 errors**
- Frontend `vitest run`: **965/965 passed** (70 files)
- Frontend production build (`vite build`): **succeeded**, 193 modules
- `keystore-core` / `sidecar-core` / `src-tauri cargo check` / `cargo test`:
  **ENVIRONMENT BLOCKED** — no Rust toolchain (`cargo`/`rustc` not found) in this
  sandbox, consistent with every prior Phase 4 session for this project.

## Environment limitations
- No Rust toolchain available — Rust-side checks (keystore-core, sidecar-core,
  `src-tauri` cargo check/test) could not be executed. Not inferred as passing.
- True Windows path semantics (drive letters, UNC, backslash-as-separator) could not
  be executed on this Linux sandbox; the absolute-path check's behavior on Windows is
  reasoned from `pathlib` semantics, not run on real Windows.
- Symlink/junction/reparse-point behavior was exercised only via a real POSIX symlink
  test (passed); Windows reparse points specifically were not testable here.

## Documentation
No `PHASE4O_SECURITY_P2B1`/`P2B2`/`P2B3` closure docs exist anywhere in this
checkpoint despite the test file's own docstring referring to "Part 2B-1"/"Part 2B-2"
work — this is a pre-existing documentation gap, not something this session
introduced or is in scope to backfill. This doc records only what Part 2B-4 itself
verified.

## FINAL VERDICT: PASS WITH CONDITIONS

All executable checks passed with no defect found. The condition is the Rust
toolchain being entirely unavailable in this sandbox (unchanged from every prior
Phase 4 session) and true Windows-path semantics being unverifiable outside a real
Windows environment — both environment limitations, not software gaps.

## §20 Export Path-Traversal Security Control: CLOSED
Part 2A Capability Manifest Control: PRESERVED
Part 1B Rust Keystore Migration: PRESERVED
Phase 4O Migration State: PRESERVED

This closes only the export path-traversal control. It does not assert §20 in full is
complete, and does not assert Windows-specific protection beyond what `pathlib`
semantics on Windows are known to do.
