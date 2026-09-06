# SOC-IQ Frontend — MAX-10 Export & Filesystem Security Remediation — Closure

## 1. Baseline

Exact source ZIP: `SOC-IQ-FRONTEND-MAX-10-FINAL-FULL.zip` (uploaded as
`SOC-IQ-FRONTEND-MAX-10-FINAL-FULL__1_.zip`).

This phase is a targeted remediation on top of that baseline. No restart, no
redesign, no MAX-11 work performed.

## 2. Audit findings

**MAX-AUDIT-01 (P1).** `frontend/src/pages/reports/reportExportPath.ts` and
`frontend/src/pages/investigations/investigationsCsvExportPath.ts` both call
`save()` from `@tauri-apps/plugin-dialog`, but `src-tauri/capabilities/default.json`
granted only `dialog:allow-open` — not `dialog:allow-save`. Under Tauri's ACL, the
save dialog would be denied at runtime even though both call sites are fully
exercised (and therefore look "correct") in mocked unit tests.

**MAX-AUDIT-02 (P1).** `docs/security/filesystem-security-model.md`'s "TARGET
STATE" described export writes happening inside the Rust/Tauri layer, with the
Python sidecar never touching a frontend-supplied path. The actual implementation
has the frontend pass an absolute `output_path` into the sidecar's
`export_report`/`export_investigations_csv` HTTP commands, and Python performs the
write. Backend validation only proves the path is absolute — it cannot prove the
value originated from the trusted native save dialog rather than a request crafted
directly against the sidecar's local endpoint. Documentation and implementation
were out of alignment.

## 3. Root cause

**MAX-AUDIT-01:** The capability manifest was last updated for the *open*-file
flow (`nativeFileSelection.ts`) and never revisited when the *save* flow
(`reportExportPath.ts`, `investigationsCsvExportPath.ts`) was added in a later
phase — a straightforward omission, not a deliberate scoping decision (the doc
comments in both files assume the save dialog "just works" the same way `open()`
does, which is true for the JS API surface but not for the Tauri ACL).

**MAX-AUDIT-02:** The original Phase 4A design intent (Rust performs the write)
was documentation only — it was never implemented, and no in-repo evidence (code,
tests, ADR follow-up) shows it was later built and then regressed. The Python
sidecar performing the write is the actual, long-standing architecture; the
documentation simply never caught up to it.

## 4. Files changed

- `src-tauri/capabilities/default.json` — added `dialog:allow-save` permission;
  updated `description` to be accurate and current.
- `tests/fixtures/capability_manifest.snapshot.json` — regenerated via the
  project's own `python -m tests.architecture.update_capability_snapshot --write`
  to reflect the new, deliberate manifest state.
- `docs/security/filesystem-security-model.md` — rewritten to document the actual
  implemented trust boundary (Outcome B) instead of the never-built aspirational
  Rust-write design, and to explain why that stronger design was not restored in
  this phase.
- `docs/security/tauri-capability-model.md` — updated to reflect `dialog:allow-save`
  now being granted; corrected the stale "not yet granted" note; retitled the
  target-state section as historical design intent.
- `tests/test_bulk_csv_export_path_traversal_adversarial.py` — **new file**.
  Adversarial path-security parity tests for `export_investigations_csv`, mirroring
  the existing `export_report` adversarial suite (which already existed and needed
  no changes).

No other files were modified. No React architecture, API client, DTOs, command
architecture, Tauri sidecar lifecycle, export abstractions, design system, or error
model were touched.

## 5. Changes made

1. Granted the minimum additional Tauri capability (`dialog:allow-save`) required
   for both real desktop export workflows (report export, investigations CSV
   export) to open the native save dialog. No broader filesystem, shell, or dialog
   permission was added.
2. Investigated the actual export architecture end to end (frontend save-dialog
   modules → typed command client → Python DTO validation → per-format exporters)
   and confirmed the current absolute-path validation is the correct, deliberate
   security control for this architecture, not a placeholder.
3. Brought `docs/security/filesystem-security-model.md` and
   `docs/security/tauri-capability-model.md` into alignment with the real,
   implemented boundary (Outcome B) instead of the never-built target design.
4. Closed a test-coverage parity gap: `export_investigations_csv` now has the same
   class of adversarial path-security proof `export_report` already had (traversal
   payloads rejected with zero filesystem trace, absolute paths and symlinks
   resolve and write to exactly the expected location, sibling files are left
   untouched).

## 6. Security boundary

**Outcome B implemented** (see decision rationale in Section 7 of the phase spec
and in `docs/security/filesystem-security-model.md`'s "WHY NOT THE ORIGINAL
RUST-WRITE DESIGN" section).

The application does **not** cryptographically prove that a given `output_path`
came from the native save dialog rather than from any other request able to reach
the sidecar's local HTTP command endpoint. That gap is now explicitly documented
rather than implied away. The actual, enforced guarantees are:

- The only capability that lets the frontend obtain a destination path at all is
  `dialog:allow-save` / `dialog:allow-open` — no `fs:allow-write*` capability is
  granted, so Tauri's ACL gives JavaScript no way to write a file directly.
- `output_path` must be a non-empty, absolute path; a relative or bare filename is
  rejected outright at the DTO boundary before any exporter runs
  (`app/application/dto.py`).
- A request is confined to writing exactly the one path it names — no directory
  listing, no arbitrary read, no delete/rename — proven adversarially (traversal
  rejected with no filesystem trace; absolute paths and symlinks resolve and write
  to exactly the predicted location; sibling files are untouched).

Restoring the stronger native (Rust-mediated write) boundary was evaluated and
rejected for this phase because it requires a new architecture layer (either
duplicating five format-specific exporters in Rust, or a redundant Python-write +
Rust-copy step) — out of scope under Rule B (preserve existing architecture, no
architecture rewrite).

## 7. Tests

| Command | Result |
|---|---|
| `python -m pytest tests/test_architecture_capability_snapshot.py -q` | 22 passed |
| `python -m pytest tests/test_bulk_csv_export_path_traversal_adversarial.py tests/test_export_path_traversal_adversarial.py tests/test_bulk_csv_export.py -q` | 67 passed, 3 subtests passed |
| `python -m pytest -q` (full backend suite) | **1245 passed**, 2 warnings, 3 subtests passed |
| `npm test` (frontend, `vitest run`) | **1187 passed** (82 test files) |
| `npm run typecheck` (`tsc --noEmit`) | clean, no errors |
| `npm run build` (`tsc --noEmit && vite build`) | succeeded, 201 modules transformed |
| `cargo check` (src-tauri) | **ENVIRONMENT-BLOCKED** — see Section 8 |
| `cargo test` (src-tauri) | **ENVIRONMENT-BLOCKED** — see Section 8 |

## 8. Runtime verification

- **STATIC VERIFIED:** `src-tauri/capabilities/default.json` is valid JSON;
  `dialog:allow-save` is present in the `permissions` array; no unrelated
  permission was added or removed (confirmed by full-tree diff against the
  baseline ZIP — only the four intended files changed, plus one new test file).
- **VERIFIED (Python-based capability guard):** `tests/test_architecture_
  capability_snapshot.py` canonicalizes the real manifest and `tauri.conf.json`
  security fields and compares them against a committed, deliberately-updated
  baseline snapshot — this is the project's actual regression mechanism for the
  capability surface, and it passed (22/22). This does not require compiling Rust.
- **ENVIRONMENT-BLOCKED — real Tauri/native-dialog verification:** no desktop
  runtime is available in this environment (headless container, no windowing
  system, no webview). The real save-dialog IPC path could not be exercised
  end to end.
- **ENVIRONMENT-BLOCKED — `cargo check`/`cargo test`:** the only Rust toolchain
  installable in this environment (via `apt-get install cargo rustc`, since
  `rustup`'s distribution domains are not in the environment's network allow-list)
  is `rustc`/`cargo` 1.75.0. The project's `Cargo.toml` declares
  `rust-version = "1.77"`, and dependency resolution concretely failed with
  `feature 'edition2024' is required ... not stabilized in this version of Cargo
  (1.75.0)` while resolving a transitive dependency (`dlopen2_derive v0.4.3`).
  This is a pre-existing environment/toolchain limitation, not something
  introduced by this remediation — no `.rs` source file was modified in this
  phase (only the `capabilities/default.json` manifest, which is plain JSON and
  is independently verified by the passing capability-snapshot test above).
  Environment blocked real Tauri/native-dialog verification.

No check above is reported as PASS from static inspection alone; the two
environment-blocked items are reported as such, not converted to PASS.

## 9. Regression assessment

- Full backend suite: 1245/1245 passed, no failures, no skips beyond what already
  existed in the baseline.
- Full frontend suite: 1187/1187 passed across 82 files, including the existing
  `reportExportPath.test.ts`, `useReportExport.test.tsx`,
  `investigationsCsvExportPath.test.ts`, and `useInvestigationsCsvExport.test.tsx`
  — none needed changes, since the capability grant is invisible to mocked unit
  tests by design (that invisibility is exactly what let MAX-AUDIT-01 slip through
  originally).
- `tsc --noEmit` and the Vite production build both succeed cleanly.
- A full-tree diff against the original baseline ZIP confirms only the five files
  listed in Section 4 differ or are new — no unrelated product area, page, or
  component was touched.
- No architecture, DTO, command, or export-abstraction change was made anywhere in
  the frontend, Rust, or Python layers; only a capability grant, a test-parity
  addition, and documentation corrections.

## 10. Remaining conditions

- Real Tauri/native-dialog runtime verification remains unexecuted — genuinely
  environment-blocked, not skipped by choice. A future phase with a working
  desktop/webview runtime (or CI with the pinned Rust toolchain the project
  actually targets) should run `cargo tauri dev`/`cargo test` and manually exercise
  both export flows end to end.
- `cargo check`/`cargo test` remain environment-blocked for the same toolchain
  reason. Since no `.rs` file changed in this phase, this is a pre-existing gap in
  this environment's tooling, not a new risk introduced here — but it should be
  closed the next time a Rust-side change is made, in an environment with a
  Rust toolchain meeting the project's declared `rust-version = "1.77"`.
- The trust-boundary gap documented in Section 6 (no cryptographic proof that
  `output_path` originated from the save dialog) is a deliberate, accepted,
  now-explicit condition of Outcome B — not something left "to fix later" — but a
  future phase could revisit restoring the stronger Rust-mediated write path if
  that architecture investment is prioritized.
