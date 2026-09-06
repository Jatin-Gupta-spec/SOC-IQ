# Packaging / Release Architecture

**Status:** Sidecar packaging IMPLEMENTED (Part 3A-2A). Tauri bundle/Windows-target
configuration IMPLEMENTED (Part 3A-2B). Windows installer build itself **not yet
verified** — see "IMPLEMENTED vs. REQUIRES A WINDOWS-CAPABLE RELEASE ENVIRONMENT" below.
**Related:** Master Plan §24, §23 (dependency/supply-chain), and
`docs/security/dependency-supply-chain-security-model.md`.

## PART 3A-2B ADDITIONS (Tauri packaging & Windows distribution config)

- `src-tauri/tauri.conf.json`'s `bundle.targets` changed from the bundler default `"all"`
  to the explicit `["msi", "nsis"]` — the two production Windows installer formats this
  project actually ships, per this part's scope (no macOS/Linux bundler targets requested
  or produced).
- `packaging/scripts/build-windows.ps1` added: a thin PowerShell sequencer over the two
  commands `packaging/README.md` already documented separately (`build_backend.py` then
  `cargo tauri build`), so there is one documented, scriptable production build path for a
  real Windows release machine. Not executed in this sandbox (no Windows host, no Rust
  toolchain) — static review only.
- Everything else this part's checklist covers — `externalBin` sidecar wiring,
  `frontendDist`/`beforeBuildCommand`, icon set, `capabilities/default.json`'s narrow
  permission grant, app identity (`productName`/`identifier`/`version`), and the
  `BACKEND_BINARY_NAME`/spec/`externalBin` naming convention — was inspected and found
  already production-correct as left by Part 3A-2A; no changes were needed there.

## CURRENT STATE (Part 3A-2A)

The stale claim this document previously made — "it is a PySide6 desktop app with no bundled
runtime" — is now **outdated and corrected**: `app/gui` (PySide6) is retired per PD-06 and is
not on the Tauri/sidecar's import path at all (confirmed by repository grep: the only
`PySide6` string under `app/` outside `app/gui` is a comment, not an import). The production
architecture actually implemented by this part is:

```text
React/Vite  ->  Tauri (Rust shell)  ->  bundled Python backend executable  ->  FastAPI
```

- The Python backend (`app.api.entrypoint` — unmodified) is frozen into a standalone
  executable, `socq-backend(.exe)`, via PyInstaller. Spec:
  `packaging/pyinstaller/socq_backend.spec`. Build wrapper:
  `packaging/scripts/build_backend.py` (runs PyInstaller, then stages the result into
  `src-tauri/binaries/socq-backend-<target-triple>[.exe]`, the exact filename Tauri's
  `externalBin` bundler expects).
- `src-tauri/tauri.conf.json`'s `bundle.externalBin` now lists `binaries/socq-backend`, so
  `tauri build` bundles the frozen executable into the installed application, next to the
  main `SOC-IQ(.exe)`.
- `src-tauri/src/lib.rs::production_backend_executable_path()` looks for
  `socq-backend(.exe)` next to the running process's own executable
  (`std::env::current_exe()`) at every sidecar launch/restart. If found, that binary is
  launched directly (no `-m app.api.entrypoint` arguments — the frozen executable already
  is that program; see `SidecarLaunchConfig::args`'s doc comment in `src-tauri/src/sidecar.rs`
  for why passing module args to it would be wrong). If not found — an unpackaged dev build,
  or a source checkout that never ran the packaging script — it falls back to the pre-3A-2A
  `python -m app.api.entrypoint` behavior, resolved from `CARGO_MANIFEST_DIR`'s parent
  (development only; never reached in a production installation, which has no `Cargo.toml`
  on disk).
- Dependency management still uses `requirements.txt` with minimum-version constraints, not a
  locked set — **unchanged by this part**; see "Dependency locking" below, still open.

## IMPLEMENTED vs. REQUIRES A WINDOWS-CAPABLE RELEASE ENVIRONMENT

**Implemented and verified in this part's own sandbox (Linux, no Rust toolchain):**
- PyInstaller successfully freezes `app.api.entrypoint` into a single-file executable with no
  dependency on a system Python install.
- The frozen executable was actually run: it printed the expected bare-port-number handshake
  line on stdout and served the real FastAPI app (`/openapi.json` returned HTTP 200 with the
  real route table) on that port.
- `packaging/scripts/build_backend.py` correctly stages the frozen binary under the
  `<name>-<target-triple>[.exe]` convention `tauri.conf.json`'s `externalBin` entry requires.

**Requires a Windows-capable release environment (not verified here — this sandbox has
neither Windows nor a Rust/Cargo toolchain at all):**
- Producing an actual Windows `socq-backend-x86_64-pc-windows-msvc.exe` (PyInstaller freezes
  for the host OS it runs on; a real release build must run this step on Windows, or via a
  proper cross-build toolchain, not this Linux sandbox).
- Compiling `src-tauri` at all (`cargo`/`rustc` are not installed in this sandbox — this is a
  harder blocker than "old Rust version," there is no Rust toolchain here whatsoever), and
  therefore compiling `tauri build`'s Windows installer (MSI/NSIS).
- Confirming `SOC-IQ.exe` actually launches the bundled `socq-backend.exe` on a real Windows
  install (only the production-path-resolution logic and its unit tests were verified here;
  the full installed-application startup path was not).

## STILL-OPEN TARGET-STATE ITEMS (unchanged by this part; not in Part 3A-2A's scope)

- **App-data directory:** `app/config.py`'s `BASE_DIR = Path(__file__).resolve().parent.parent`
  resolves, when frozen by PyInstaller in `--onefile` mode, to that run's ephemeral
  `sys._MEIPASS` extraction directory — meaning the SQLite database, logs, and exports would
  currently be **non-persistent between runs** in a packaged build (a fresh temp directory is
  extracted, and torn down, every process start). This is a real defect for a released
  application, already anticipated by this document's own OS-appropriate-app-data-directory
  target-state item below, but fixing `app/config.py`'s path resolution is a change to
  completed backend code and is explicitly out of this part's scope (task brief §3: "do not
  rewrite completed backend systems"). Flagged here for whichever later part does that work.
- OS-appropriate app-data directory (`%APPDATA%/SOC-IQ` on Windows) for the database, logs,
  and default export location — see the defect note directly above; this is the fix for it.
- Update strategy: Tauri's built-in updater (signed update manifests) — tracked as a **V1**
  goal, not required for an initial packaged release.
- Dependency locking: `requirements.lock` (pip-tools or uv-generated) to replace the current
  minimum-version `requirements.txt`; `Cargo.lock` and `pnpm-lock.yaml` are already committed.
  Full detail: `docs/security/dependency-supply-chain-security-model.md`.
- Logs and database migrations (see `09-database-architecture.md`) already run at sidecar
  startup, before the API server accepts any command — unaffected by this part, and
  unaffected by the frozen-executable change (the migration code path is unchanged; only how
  the process is launched changed).

## MIGRATION NOTES

Packaging work has no dedicated phase number of its own in the Master Plan's phase table —
it is a cross-cutting concern addressed incrementally starting once the Tauri foundation
exists (Phase 4E) and finalized as part of Phase 4N (integration) / 4P (final audit). Part
3A-2A is one increment of that cross-cutting work: the sidecar-freezing and path-resolution
piece specifically, not the full release pipeline (code signing, installer polish, updater).
