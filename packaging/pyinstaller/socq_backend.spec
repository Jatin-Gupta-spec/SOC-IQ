# SOC-IQ Part 3A-2A -- Production sidecar packaging.
#
# Freezes `app.api.entrypoint` (the existing FastAPI/uvicorn loopback
# sidecar process -- see that module's own docstring for the
# handshake/port contract this build does NOT change) into a single
# standalone executable that carries its own Python runtime.
#
# This file is the "packaging configuration" artifact called for by
# task brief S6/S12. It freezes the *existing* entrypoint unmodified --
# no application code was rewritten to make this spec work.
#
# Build (from the project root, with the project's requirements AND
# pyinstaller installed in the active environment):
#
#   pyinstaller packaging/pyinstaller/socq_backend.spec --noconfirm
#
# Output: dist/socq-backend/socq-backend(.exe) -- a single onefile
# executable. See packaging/scripts/build_backend.py for the wrapper
# that also copies/renames this into src-tauri/binaries/ with the
# Tauri-expected target-triple suffix.
#
# What is deliberately bundled as data (not code) because
# app/config.py resolves them relative to the package root at import
# time, and PyInstaller's frozen import machinery cannot see plain
# non-.py files on `sys.path` the way a source checkout can:
#   - app/reporting/templates/*.j2   (Jinja2 report template)
#   - app/database/migrations/*.sql  (schema migrations, applied at
#     sidecar startup -- docs/architecture/09-database-architecture.md)
#
# What is deliberately NOT bundled:
#   - app/gui/**            (PySide6 desktop shell -- retired per PD-06,
#     not imported by anything on the app.api.entrypoint import path;
#     see this part's own repository audit for the one-line grep
#     confirming this, and PySide6 is excluded below to keep the
#     frozen artifact free of a GUI toolkit the sidecar never uses)
#   - .env / real API keys   (never read from a file at all -- the
#     VirusTotal credential is handed to this process at spawn time
#     via SOCIQ_SECRET_VIRUSTOTAL_API_KEY, an env var set by the Rust
#     parent for this child's lifetime only; see src-tauri/src/sidecar.rs)
#   - tests/, docs/, frontend/, node_modules/, .git/

import sys
from pathlib import Path

# packaging/pyinstaller/ -> packaging/ -> project root
PROJECT_ROOT = Path(SPECPATH).resolve().parent.parent

block_cipher = None

datas = [
    (
        str(PROJECT_ROOT / "app" / "reporting" / "templates"),
        "app/reporting/templates",
    ),
    (
        str(PROJECT_ROOT / "app" / "database" / "migrations"),
        "app/database/migrations",
    ),
]

# uvicorn/starlette/fastapi/pydantic all do a mix of dynamic and
# conditional imports (event loop backends, HTTP protocol backends,
# lifespan handling, pydantic-core's compiled validators) that
# PyInstaller's static import scan does not always see. Collected
# explicitly rather than guessed one module at a time, per this
# part's "least disruptive supported approach" instruction (S5) --
# these are the standard, documented hooks for freezing a
# FastAPI/uvicorn app, not a speculative migration.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "pydantic.deprecated.decorator",
    "email_validator",
]

excludes = [
    # The retired desktop GUI (PySide6) -- not on the
    # app.api.entrypoint import path; see module docstring above.
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

a = Analysis(
    [str(PROJECT_ROOT / "app" / "api" / "entrypoint.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --onefile equivalent (EXE gets everything -- no separate COLLECT
# step) so the sidecar binary Tauri launches is a single file, matching
# the `externalBin` single-artifact contract (task brief S9).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="socq-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
