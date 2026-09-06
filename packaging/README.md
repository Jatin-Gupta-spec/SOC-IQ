# SOC-IQ Sidecar Packaging (Part 3A-2A)

Freezes the existing Python/FastAPI backend (`app.api.entrypoint`, unmodified) into a
standalone executable that Tauri bundles as an `externalBin` sidecar, so an installed
SOC-IQ desktop application never needs a system Python interpreter.

## Layout

```
packaging/
  pyinstaller/
    socq_backend.spec   -- PyInstaller spec; freezes app/api/entrypoint.py
  scripts/
    build_backend.py    -- runs PyInstaller, then stages the result into
                            src-tauri/binaries/socq-backend-<target-triple>[.exe]
```

## Building the backend sidecar

From the project root, with this project's `requirements.txt` AND `pyinstaller` installed
in the active Python environment:

```sh
pip install -r requirements.txt
pip install pyinstaller
python packaging/scripts/build_backend.py
```

This produces `dist/socq-backend(.exe)` and stages a copy at
`src-tauri/binaries/socq-backend-<target-triple>[.exe]` -- the exact filename
`src-tauri/tauri.conf.json`'s `bundle.externalBin: ["binaries/socq-backend"]` entry expects
Tauri's bundler to find.

**PyInstaller freezes for the host OS it runs on.** To produce the Windows artifact
(`socq-backend-x86_64-pc-windows-msvc.exe`) needed for a real Windows release, this script
must be run on Windows (or via a genuine Windows cross-build toolchain) -- it cannot be
produced on a Linux CI runner or sandbox. Pass `--target-triple` explicitly on a real release
machine rather than relying on this script's rustc-based auto-detection, which falls back to
a platform guess (clearly logged as a guess) when no Rust toolchain is present at all.

## Then building the Tauri application

```sh
cd src-tauri
cargo tauri build
```

`tauri build` bundles the staged `src-tauri/binaries/socq-backend-<target-triple>[.exe]`
into the installer, next to the main `SOC-IQ(.exe)`. At runtime,
`src-tauri/src/lib.rs::production_backend_executable_path()` finds it next to the running
application's own executable and launches it directly -- see that function's doc comment,
and `docs/architecture/18-packaging-release-architecture.md`, for the full resolution
contract (including the source-checkout development fallback when no packaged binary is
present).

## Persistence across runs (resolved -- R2-B / verified R3-B)

This note previously flagged `app/config.py`'s `BASE_DIR` (ephemeral, `__file__`-relative --
correct only for bundled resources) as also being used for the database/logs/exports, which
would have made them non-persistent in a packaged `--onefile` build. That was fixed in R2-B:
mutable, application-owned runtime data (database, logs, settings) now resolves through the
separate `APP_DATA_ROOT` (`platformdirs.user_data_dir(...)`), never through `BASE_DIR`. R3-B's
packaged-executable smoke test independently re-confirmed this: a built `dist/socq-backend`
run with a clean `$HOME` created its database and log file under
`~/.local/share/SOC-IQ/{database,logs}/`, not under the PyInstaller extraction directory. See
`docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md` and this part's own
`docs/audits/SOC-IQ-R3-B-PYTHON-PYINSTALLER-RELEASE-BUILD.md` for the full evidence trail.
