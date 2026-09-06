"""
SOC-IQ Part R2-E -- packaged-persistence smoke test.

Builds the real `packaging/pyinstaller/socq_backend.spec` executable (or
reuses an already-built one via --exe), launches it twice against an
isolated, throwaway HOME/XDG_DATA_HOME, and proves the core R2-E
invariant end to end using the actual packaged binary -- not source-mode
Python and not a unit test:

  * Run #1 creates a real investigation (via POST /commands/analyze_report)
    and a real user-selected export, then is terminated.
  * Run #2 is a fresh process launch (a new PyInstaller onefile
    extraction directory) pointed at the SAME persistent HOME, and must
    be able to read back the investigation Run #1 created.
  * The database and log file must resolve outside both runs' extraction
    directories.

This intentionally mirrors the manual verification performed for the
R2-E closure report so the same proof can be re-run on demand (e.g. in
CI, or as a smoke test before a release) rather than only existing as a
one-time forensic transcript.

Usage (from the project root, with the project's requirements AND
pyinstaller installed):

    python packaging/scripts/verify_packaged_persistence.py

Exit code is 0 on success, non-zero on any failed proof point. Prints a
short PASS/FAIL line per check.

Known limitation: this script builds and runs whatever native onefile
executable PyInstaller produces on the host it is run on. On Linux/macOS
that proves the PyInstaller onefile extraction-vs-persistent-data
invariant, but it is not a substitute for running the *Windows* build on
Windows -- see the R2-E closure report for that distinction.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_PATH = PROJECT_ROOT / "packaging" / "pyinstaller" / "socq_backend.spec"

PASS = "PASS"
FAIL = "FAIL"

_results: list[tuple[str, str]] = []


def record(name: str, ok: bool) -> None:
    _results.append((name, PASS if ok else FAIL))
    print(f"[{PASS if ok else FAIL}] {name}")


def build_executable(dist_dir: Path, work_dir: Path) -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(SPEC_PATH),
            "--noconfirm",
            "--distpath",
            str(dist_dir),
            "--workpath",
            str(work_dir),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    candidates = list(dist_dir.glob("socq-backend*"))
    if not candidates:
        raise RuntimeError(f"No socq-backend executable found under {dist_dir}")
    return candidates[0]


def post(port: int, command: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/commands/{command}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def launch(exe: Path, home: Path, port: int, stdout_path: Path) -> subprocess.Popen:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")
    env["SOCIQ_SIDECAR_PORT"] = str(port)
    stdout_f = open(stdout_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [str(exe)],
        env=env,
        stdout=stdout_f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    # Wait for the port handshake line.
    deadline = time.time() + 15
    while time.time() < deadline:
        if stdout_path.stat().st_size > 0:
            break
        time.sleep(0.1)
    return proc


def wait_for_health(port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=2
            ) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.3)
    raise RuntimeError(f"Packaged server never became healthy: {last_err}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=None,
                         help="Reuse an already-built executable instead of building one.")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="socq-r2e-verify-"))
    dist_dir = tmp_root / "dist"
    work_dir = tmp_root / "build"
    home_dir = tmp_root / "home"
    home_dir.mkdir(parents=True)
    export_dir = tmp_root / "user-selected-exports"
    export_dir.mkdir(parents=True)
    sample_report = tmp_root / "probe_report.txt"
    sample_report.write_text(
        "Malware Analysis Report\nIOC: 8.8.8.8\n", encoding="utf-8"
    )

    try:
        exe = args.exe or build_executable(dist_dir, work_dir)
        record("PyInstaller build", True)

        app_data_dir = home_dir / ".local" / "share" / "SOC-IQ"

        # ---- Run #1 ----
        run1_stdout = tmp_root / "run1.stdout"
        proc1 = launch(exe, home_dir, 8731, run1_stdout)
        try:
            wait_for_health(8731)
            record("Packaged launch (run 1)", True)

            result = post(
                8731,
                "analyze_report",
                {"report_path": str(sample_report)},
            )
            investigation_id = result["data"]["investigation"]["investigation_id"]
            record("Real database write via packaged run 1", result["success"])

            export_path = export_dir / "probe-export.json"
            export_result = post(
                8731,
                "export_report",
                {
                    "investigation_id": investigation_id,
                    "output_path": str(export_path),
                    "export_format": "json",
                },
            )
            record(
                "User-selected export honored exactly",
                export_result["success"] and export_path.exists(),
            )
        finally:
            os.killpg(os.getpgid(proc1.pid), signal.SIGTERM)
            proc1.wait(timeout=10)

        db_path = app_data_dir / "database" / "soc_iq.db"
        log_path = app_data_dir / "logs" / "soc_iq.log"
        record("Database persists outside /tmp/_MEI*", db_path.exists() and "_MEI" not in str(db_path))
        record("Log persists outside /tmp/_MEI*", log_path.exists() and "_MEI" not in str(log_path))

        # ---- Run #2 (fresh process, same persistent HOME) ----
        run2_stdout = tmp_root / "run2.stdout"
        proc2 = launch(exe, home_dir, 8732, run2_stdout)
        try:
            wait_for_health(8732)
            record("Packaged launch (run 2, fresh extraction dir)", True)

            readback = post(
                8732, "get_investigation", {"investigation_id": investigation_id}
            )
            record(
                "Investigation from run 1 readable in run 2",
                readback["success"]
                and readback["data"]["investigation_id"] == investigation_id,
            )
        finally:
            os.killpg(os.getpgid(proc2.pid), signal.SIGTERM)
            proc2.wait(timeout=10)

        failed = [name for name, status in _results if status == FAIL]
        print()
        if failed:
            print(f"FAILED CHECKS: {failed}")
            return 1
        print("All packaged-persistence checks passed.")
        return 0
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
