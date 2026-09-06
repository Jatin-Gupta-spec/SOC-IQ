"""
Phase 4E Part 1 -- tests for app/api/entrypoint.py
(docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md S5, "Findings P0-1").

tests/test_api_layer.py already proves the ASGI `app` object behaves
correctly through TestClient, including the new GET /health route. What
that file cannot prove is the thing Phase 4E Part 1 actually adds: that
the sidecar can be started as a real, standalone OS process with a real
bound socket, and stopped again. So this file:

  1. Exercises run_sidecar()'s loopback-only guard directly (no process
     needed -- the guard raises before any socket is touched).
  2. Exercises the SOCIQ_SIDECAR_PORT parsing helper directly.
  3. Spawns `python -m app.api.entrypoint` as a real subprocess, reads the
     port-handshake line from its stdout, polls GET /health over a real
     TCP socket until it answers (or a bounded timeout elapses), then
     terminates the process and asserts it actually exits -- the
     "spawn/health-check/kill" lifecycle
     PHASE4E_SIDECAR_TAURI_SCOPE.md S9 asks to have proven at the Python
     side (full spawn-from-Rust proof is out of scope for Part 1; no
     src-tauri/ exists yet).

The subprocess test is bounded on every blocking call (connect timeout,
poll timeout, process-wait timeout) specifically so a failure here cannot
hang the suite -- if the sidecar never becomes healthy, the test fails
promptly instead of leaving a suite process hanging, per the Part 1 brief
S10 ("Do not leave the test suite hanging.").
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest

import requests

from app.api.entrypoint import LOOPBACK_HOST, PORT_ENV_VAR, _configured_port, run_sidecar

# Bounds for the subprocess test. Generous enough for a cold interpreter
# start on a loaded CI box, tight enough that a genuinely broken
# entrypoint fails in seconds, not minutes.
_STARTUP_TIMEOUT_SECONDS = 15.0
_POLL_INTERVAL_SECONDS = 0.1
_SHUTDOWN_TIMEOUT_SECONDS = 5.0


class LoopbackGuardTests(unittest.TestCase):
    """run_sidecar() must refuse to bind anywhere but loopback."""

    def test_default_host_constant_is_loopback(self) -> None:
        self.assertEqual(LOOPBACK_HOST, "127.0.0.1")

    def test_run_sidecar_rejects_non_loopback_host(self) -> None:
        # This must raise before touching a socket at all -- if it didn't,
        # this test would need to actually bind 0.0.0.0, which is exactly
        # the thing it's asserting never happens.
        with self.assertRaises(ValueError) as ctx:
            run_sidecar(host="0.0.0.0")

        self.assertIn("loopback", str(ctx.exception).lower())

    def test_run_sidecar_rejects_arbitrary_host(self) -> None:
        with self.assertRaises(ValueError):
            run_sidecar(host="192.168.1.10")


class PortConfigTests(unittest.TestCase):
    """SOCIQ_SIDECAR_PORT parsing -- defaults, valid overrides, bad input."""

    def setUp(self) -> None:
        self._original = os.environ.get(PORT_ENV_VAR)

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop(PORT_ENV_VAR, None)
        else:
            os.environ[PORT_ENV_VAR] = self._original

    def test_defaults_to_ephemeral_zero(self) -> None:
        os.environ.pop(PORT_ENV_VAR, None)
        self.assertEqual(_configured_port(), 0)

    def test_accepts_a_valid_fixed_port(self) -> None:
        os.environ[PORT_ENV_VAR] = "8765"
        self.assertEqual(_configured_port(), 8765)

    def test_rejects_non_integer_value(self) -> None:
        os.environ[PORT_ENV_VAR] = "not-a-port"
        with self.assertRaises(ValueError):
            _configured_port()

    def test_rejects_out_of_range_value(self) -> None:
        os.environ[PORT_ENV_VAR] = "70000"
        with self.assertRaises(ValueError):
            _configured_port()


class SidecarProcessLifecycleTests(unittest.TestCase):
    """
    Real subprocess integration test: spawn, health-poll, kill.

    Like tests/test_api_layer.py's top-level `from fastapi.testclient
    import TestClient`, this file's top-level `from app.api.entrypoint
    import ...` (which pulls in uvicorn) means the whole module fails to
    collect if fastapi/uvicorn aren't installed, rather than skipping --
    consistent with the existing convention in this test suite, not a new
    one introduced here.
    """

    def test_entrypoint_spawns_serves_health_and_terminates_cleanly(self) -> None:
        env = dict(os.environ)
        env[PORT_ENV_VAR] = "0"  # ephemeral -- read the real port below

        process = subprocess.Popen(
            [sys.executable, "-m", "app.api.entrypoint"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        try:
            # Synchronous handshake: the entrypoint's first stdout line is
            # the bound port, per app/api/entrypoint.py's module docstring.
            port_line = process.stdout.readline()
            self.assertTrue(
                port_line.strip().isdigit(),
                f"expected a numeric port on stdout, got {port_line!r} "
                f"(stderr: {process.stderr.read() if process.poll() is not None else '<still running>'})",
            )
            port = int(port_line.strip())
            self.assertGreater(port, 0)

            health_url = f"http://{LOOPBACK_HOST}:{port}/health"
            deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
            last_error: Exception | None = None
            response = None

            while time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail(
                        "sidecar process exited before becoming healthy "
                        f"(returncode={process.returncode}, "
                        f"stderr={process.stderr.read()})"
                    )
                try:
                    response = requests.get(health_url, timeout=1)
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    time.sleep(_POLL_INTERVAL_SECONDS)

            self.assertIsNotNone(
                response, f"sidecar never became healthy; last error: {last_error}"
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["success"])
            self.assertEqual(body["data"], {"status": "ok"})

        finally:
            process.terminate()
            try:
                process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)

        self.assertIsNotNone(
            process.returncode, "sidecar process did not terminate cleanly"
        )


if __name__ == "__main__":
    unittest.main()
