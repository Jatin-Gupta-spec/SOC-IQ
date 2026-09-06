"""
Runnable sidecar process entrypoint for app.api.app:app.

Phase 4E Part 1 (docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md S5, "Findings
P0-1"): app/api/app.py exports an ASGI `app` object that TestClient can
drive, but nothing in source could actually start it as a standalone OS
process with a real bound socket -- there was no `uvicorn.run(...)` call
anywhere. This module is that missing piece, and only that: it starts the
existing FastAPI application, on loopback, on a port, and stops cleanly.
It contains no business/domain logic -- see the dependency-direction rule
in PHASE4E_SIDECAR_TAURI_SCOPE.md S7 ("Entrypoint -> FastAPI ->
Application -> Domain") and docs/contracts/ipc-rules.md.

Loopback + ephemeral port, per docs/security/ipc-security-model.md:
  - The sidecar binds to 127.0.0.1 only, never 0.0.0.0. This is not
    configurable via environment variable or CLI flag here -- the only way
    to change it is to edit this module, which keeps "accidentally
    listening on the LAN" from being one bad env var away.
  - The port is ephemeral by default (OS-assigned, i.e. bound with
    port 0) and is never hard-coded. It can be pinned to a fixed value via
    the SOCIQ_SIDECAR_PORT environment variable for local debugging or
    tests that need a predictable port, but production/Tauri usage is
    expected to leave it at the default (0) and read the real bound port
    from the handshake below.

Port handoff (docs/security/ipc-security-model.md "port-handoff race",
PHASE4E_SIDECAR_TAURI_SCOPE.md S10 risk #2): the socket is bound via
uvicorn's own Config.bind_socket() *before* the server starts serving, so
the actual OS-assigned port is known up front -- there is no
bind-then-rebind race. That port is written to stdout as a single decimal
integer, flushed immediately, before uvicorn logging or request handling
begins. A parent process (a test, a script, eventually Tauri) that spawns
this module should read exactly one line from stdout to learn the port,
synchronously, before doing anything else -- this is the "print-then-flush
... synchronous handshake" the security doc calls for, not a best-effort
log line to be scraped.

Shutdown: uvicorn.Server installs its own SIGINT/SIGTERM handlers when run
this way (via asyncio.run in the main thread) and exits its serve loop
on either signal, closing the listening socket. That is sufficient for
this phase's objective ("the process can be started and stopped
predictably") -- no additional lifecycle machinery is added here; that is
explicitly out of scope until the Tauri shell exists (S15/S6 non-goals).
"""

from __future__ import annotations

import asyncio
import os

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover - exercised only when uvicorn
    # is actually installed; mirrors app/api/app.py's own fastapi guard.
    raise ImportError(
        "app.api.entrypoint requires uvicorn, which is not installed in "
        "this environment. See requirements.txt."
    ) from exc

from app.api.app import app

# The sidecar never binds anywhere but loopback -- see module docstring.
# Deliberately not read from an environment variable: unlike the port,
# there is no legitimate reason for this to vary at runtime, and making it
# configurable would turn "bind only to loopback" from a structural
# guarantee into a value someone could mis-set.
LOOPBACK_HOST = "127.0.0.1"

# Optional: pin a fixed port for local debugging or tests that need a
# predictable address. Unset (or "0") means "OS-assigned ephemeral port",
# which is the expected mode for real sidecar usage per
# docs/security/ipc-security-model.md.
PORT_ENV_VAR = "SOCIQ_SIDECAR_PORT"


def _configured_port() -> int:
    """
    Read the requested port from PORT_ENV_VAR, defaulting to 0
    (OS-assigned/ephemeral). Raises ValueError on a malformed or
    out-of-range value rather than silently falling back -- a typo in this
    environment variable should fail loudly, not quietly bind to the
    wrong port.
    """

    raw = os.environ.get(PORT_ENV_VAR, "0")

    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{PORT_ENV_VAR} must be an integer, got {raw!r}"
        ) from exc

    if not 0 <= port <= 65535:
        raise ValueError(
            f"{PORT_ENV_VAR} must be between 0 and 65535, got {port}"
        )

    return port


def run_sidecar(
    *,
    host: str = LOOPBACK_HOST,
    port: int | None = None,
    log_level: str = "warning",
) -> None:
    """
    Start the sidecar and block until it is stopped (SIGINT/SIGTERM, or a
    caller-supplied cancellation for the async server, e.g. in tests).

    `host` is accepted as a parameter (rather than hard-coded inline) so a
    test can assert the loopback-only contract by calling this function
    with a non-loopback value and observing the rejection below -- it is
    not meant to be overridden in real use, and nothing in this module
    reads a host from the environment.
    """

    if host != LOOPBACK_HOST:
        raise ValueError(
            f"Refusing to bind sidecar to {host!r}: the sidecar must bind "
            f"to loopback ({LOOPBACK_HOST}) only. See "
            "docs/security/ipc-security-model.md."
        )

    resolved_port = _configured_port() if port is None else port

    config = uvicorn.Config(app, host=host, port=resolved_port, log_level=log_level)
    server = uvicorn.Server(config)

    # Bind now, synchronously, so the real port is known before anything
    # else happens -- see "Port handoff" in the module docstring.
    sock = config.bind_socket()
    bound_port = sock.getsockname()[1]

    print(bound_port, flush=True)

    asyncio.run(server.serve(sockets=[sock]))


if __name__ == "__main__":
    run_sidecar()
