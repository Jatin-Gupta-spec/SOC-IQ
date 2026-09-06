#!/usr/bin/env python3
"""
SOC-IQ Part 3A-2A packaging build script.

Runs PyInstaller against ``packaging/pyinstaller/socq_backend.spec`` and
then stages the resulting single-file executable into
``src-tauri/binaries/`` under the exact filename Tauri's ``externalBin``
bundling expects: ``<name>-<target-triple>[.exe]`` (see
https://v2.tauri.app/develop/sidecar/ -- "a binary with the same name
and a -$TARGET_TRIPLE suffix must exist on the specified path").

This script does not invent that convention -- it mirrors it exactly so
`src-tauri/tauri.conf.json`'s ``bundle.externalBin: ["binaries/socq-backend"]``
entry has a real file to find at Tauri-build time.

Usage:
    python packaging/scripts/build_backend.py [--target-triple TRIPLE]

If ``--target-triple`` is omitted, this script tries ``rustc -Vv`` (the
same source Tauri's own docs recommend for finding the host triple) and
falls back to a best-effort guess from ``platform``/``sys`` if rustc is
not installed in this environment (e.g. this sandbox, which has no Rust
toolchain at all -- see this part's final report, "Environment-Blocked").
The guess is clearly logged as a guess; it is never silently trusted for
a release build.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_FILE = PROJECT_ROOT / "packaging" / "pyinstaller" / "socq_backend.spec"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
BINARIES_DIR = PROJECT_ROOT / "src-tauri" / "binaries"

BASE_NAME = "socq-backend"


def _detect_target_triple() -> tuple[str, bool]:
    """Return (triple, was_guessed)."""
    try:
        out = subprocess.run(
            ["rustc", "-Vv"], capture_output=True, text=True, check=True
        ).stdout
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip(), False
    except (OSError, subprocess.CalledProcessError):
        pass

    # No Rust toolchain available (true in this sandbox). Best-effort
    # guess from the running platform, clearly flagged as a guess --
    # NOT a substitute for running this on/for the real release target.
    machine = platform.machine().lower()
    arch = "x86_64" if machine in ("x86_64", "amd64") else machine
    system = platform.system().lower()
    if system == "windows":
        return f"{arch}-pc-windows-msvc", True
    if system == "darwin":
        return f"{arch}-apple-darwin", True
    return f"{arch}-unknown-linux-gnu", True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-triple",
        default=None,
        help="Rust target triple to stage the binary under "
        "(e.g. x86_64-pc-windows-msvc). Auto-detected via rustc if omitted.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the PyInstaller invocation and only (re)stage an "
        "already-built dist/ artifact. Useful for re-running staging "
        "after manually inspecting the PyInstaller output.",
    )
    args = parser.parse_args()

    if not args.skip_build:
        print(f"[build_backend] Running PyInstaller: {SPEC_FILE}")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                str(SPEC_FILE),
                "--noconfirm",
                "--distpath",
                str(DIST_DIR),
                "--workpath",
                str(BUILD_DIR),
            ],
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            print("[build_backend] PyInstaller build FAILED.", file=sys.stderr)
            return result.returncode

    exe_suffix = ".exe" if platform.system().lower() == "windows" else ""
    # The spec's EXE() block has no matching COLLECT() step, i.e. this
    # is a PyInstaller --onefile-style build: the single executable
    # lands directly at dist/<name>, not dist/<name>/<name>.
    built_exe = DIST_DIR / f"{BASE_NAME}{exe_suffix}"
    if not built_exe.is_file():
        print(
            f"[build_backend] Expected build output not found: {built_exe}",
            file=sys.stderr,
        )
        return 1

    triple, guessed = (args.target_triple, False) if args.target_triple else _detect_target_triple()
    if guessed:
        print(
            f"[build_backend] WARNING: no Rust toolchain found; guessed "
            f"target triple '{triple}'. For a real release build, pass "
            f"--target-triple explicitly or run this on the actual "
            f"target/build machine.",
        )

    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    dest_suffix = ".exe" if triple.endswith("windows-msvc") or triple.endswith("windows-gnu") else exe_suffix
    dest = BINARIES_DIR / f"{BASE_NAME}-{triple}{dest_suffix}"
    shutil.copy2(built_exe, dest)
    print(f"[build_backend] Staged sidecar binary: {dest}")
    print(f"[build_backend] Size: {dest.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
