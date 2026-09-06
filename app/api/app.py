"""
FastAPI transport (the ASGI `app` object) for the SOC-IQ sidecar. Kept
deliberately thin per docs/contracts/ipc-rules.md: this module's only job
is HTTP-in / dict-out, delegating everything to
app.application.handlers.dispatch (via COMMAND_HANDLERS), which is the
layer actually proven by tests/test_application_layer.py.

This module only defines the ASGI app -- it does not run it. For the
runnable sidecar process (loopback bind, ephemeral port, clean shutdown),
see app/api/entrypoint.py, added in Phase 4E Part 1
(docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md).

Run directly:
    python -m app.api.entrypoint

Or, without the port-handshake behavior entrypoint.py adds:
    uvicorn app.api.app:app --host 127.0.0.1 --port 0
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
except ImportError as exc:  # pragma: no cover - exercised only when fastapi
    # is actually installed; see module docstring.
    raise ImportError(
        "app.api.app requires fastapi, which is not installed in this "
        "environment. See docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S6."
    ) from exc

from app.application.broker import get_application_broker
from app.application.errors import UNKNOWN_COMMAND
from app.application.events import Event
from app.application.handlers import COMMAND_HANDLERS
from app.application.responses import fail, ok
from app.initializer import initialize_application
from app.logger import configure_logger


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """
    Create the persistent application-data directories (database,
    logs, config, exports -- see app.config.APP_DATA_ROOT) and attach
    the file-logging handler before this process serves its first
    request.

    Per docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md Part 15
    item 2: `initialize_application()`/`configure_logger()` previously
    existed but were only ever called from the retired PySide6
    `app/main.py`, which is excluded from the packaged build. This is
    the production sidecar entrypoint (`app/api/entrypoint.py` runs
    this ASGI app via uvicorn), so this is the correct, single
    initialization boundary for it -- directories are created and
    logging is attached exactly once, before
    `app.database.connection.DatabaseConnection` or
    `app.settings.repository.SettingsRepository` perform their first
    real write. Uses the lifespan protocol (rather than the
    deprecated `@app.on_event("startup")`) per current FastAPI
    guidance.
    """

    initialize_application()
    configure_logger(verbose=False)

    yield


app = FastAPI(title="SOC-IQ API", version="0.1.0", lifespan=_lifespan)

# R4-B0 CORS remediation (docs/audits/SOC-IQ-R4-A-INSTALLATION-LAUNCH-VERIFICATION.md
# "R4-A packaged runtime diagnostic" finding): the frontend, when actually
# running inside the packaged Tauri desktop shell, calls this sidecar via a
# real cross-origin `fetch()` -- the WebView's own origin (the Tauri asset
# origin, e.g. `http://tauri.localhost`/`https://tauri.localhost` depending
# on platform, or `http://localhost:1420` under `cargo tauri dev`) is never
# the same origin as `http://127.0.0.1:<ephemeral-port>` this ASGI app binds
# to (see app/api/entrypoint.py). Before this change, this module registered
# no CORS support at all -- confirmed by direct inspection, zero
# `Access-Control-*` handling anywhere in this file -- so every non-"simple"
# cross-origin request (in particular every `POST /commands/{name}` call,
# which sends `Content-Type: application/json` and therefore triggers a
# browser CORS preflight) failed the WebView's own preflight check before
# this application ever saw the real request, surfacing to the frontend as
# a bare `fetch()` "Failed to fetch" TypeError (`shared/api/client.ts`'s
# `CommandNetworkError`) -- while an out-of-browser HTTP client (curl,
# PowerShell `Invoke-WebRequest`, `TestClient`/`httpx` in this project's own
# test suite) never enforces CORS and so never reproduced the failure,
# which is exactly why this was only caught in a real packaged-Windows
# launch, not by any prior automated test.
#
# Scope is deliberately narrow, per the R4-B0 remediation brief: this is a
# single-user, loopback-only desktop sidecar (docs/security/ipc-security-
# model.md) with exactly one legitimate caller (this project's own Tauri
# WebView), so the allowed-origin list is an explicit enumeration of the
# concrete origins that caller can actually present -- never a wildcard --
# and no cookies/credentials are used by this API (every command call is a
# plain bearer-less JSON POST), so `allow_credentials` stays `False`.
#
# `SOCIQ_ALLOWED_ORIGINS`, if set, overrides/extends the built-in list
# with a comma-separated list of additional exact origins -- provided as an
# escape hatch for the real Windows-packaged origin to be confirmed and
# pinned once directly observed (this sandbox has no Tauri/WebView2 runtime
# to observe it in; see the R4-A audit trail), without requiring a second
# source edit once that value is known. Never wildcarded even via this
# variable: values are split on commas and used as literal, exact origins.
_DEFAULT_ALLOWED_ORIGINS = [
    # `cargo tauri dev` (src-tauri/tauri.conf.json's `build.devUrl`).
    "http://localhost:1420",
    # Tauri's packaged WebView asset origin. Tauri v2's default asset
    # protocol serves the frontend from a virtual host named after the
    # app identifier's scheme (`tauri://localhost`) or, on Windows
    # (WebView2), the `https://tauri.localhost` / `http://tauri.localhost`
    # equivalents depending on the installed WebView2 runtime version --
    # all three are listed since this sandbox cannot independently
    # observe which one a real Windows install actually presents (see
    # "Still unproven" in the R4-A diagnostic report).
    "tauri://localhost",
    "https://tauri.localhost",
    "http://tauri.localhost",
]

_extra_origins = [
    origin.strip()
    for origin in os.environ.get("SOCIQ_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_DEFAULT_ALLOWED_ORIGINS, *_extra_origins],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# SSE heartbeat interval, per
# docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md S7 ("every N seconds
# (e.g. 15s)"). A plain module constant, not env-configurable -- there is
# no legitimate reason for this to vary per-deployment for a loopback
# single-user sidecar, consistent with how app/api/entrypoint.py treats
# LOOPBACK_HOST.
SSE_HEARTBEAT_INTERVAL_SECONDS = 15.0

# How long each Subscription.get() call blocks before looping back to
# check for a heartbeat/disconnect. Deliberately shorter than the
# heartbeat interval itself: this is a poll granularity for detecting
# client disconnect and elapsed heartbeat time, not the heartbeat period.
_SSE_POLL_INTERVAL_SECONDS = 1.0


def _format_sse_event(event: Event) -> str:
    """
    Render one `Event` as a standard EventSource-compatible SSE frame, per
    PHASE4D_SSE_ARCHITECTURE_DECISION.md S7 ("Media type / framing"):

        id: <event_id>
        event: <event.event>
        data: <json.dumps(event.to_dict())>
        <blank line>

    Uses `Event.to_dict()` unchanged (no second event schema, per Part 3's
    own instructions) -- `to_dict()` is exactly `dataclasses.asdict()`, so
    the payload is already the same plain-dict/JSON-safe shape
    `EventCollector`/the application tests already rely on. Event payloads
    are constructed exclusively by command handlers (see
    app/application/handlers.py), which never place secrets (e.g. the VT
    API key) into a payload -- this function does not add or strip any
    fields, so that guarantee carries through unchanged into the wire
    format.
    """

    data = json.dumps(event.to_dict())
    return f"id: {event.event_id}\nevent: {event.event}\ndata: {data}\n\n"


def _format_sse_heartbeat() -> str:
    """
    A transport-level SSE comment line, per S7/S8 of the architecture
    decision. Deliberately never constructed as an `Event` and never
    passed through `EventBroker.publish()` -- it has no `event_id`, is
    never seen by any other subscriber's queue, and cannot be confused
    with an application event by a client listening via
    `EventSource.addEventListener(...)` (comment lines fire no such
    listener at all).
    """

    return ": heartbeat\n\n"


async def _sse_event_stream(request: Request) -> AsyncIterator[str]:
    """
    Bridge one HTTP connection to one `EventBroker` `Subscription`.

    Subscribes on entry, unsubscribes in `finally` (covering normal
    completion, client disconnect, and any exception) so a dropped
    connection can never leak a registered subscriber -- per
    PHASE4D_SSE_ARCHITECTURE_DECISION.md S6 Shutdown/Unsubscribe and this
    Part's mandatory disconnect-cleanup requirement.

    `Subscription.get()` is a blocking, thread-based call (see
    app/application/broker.py -- it is built on `threading.Condition`, not
    `asyncio`), so it is run via `asyncio.to_thread` rather than awaited
    directly; this keeps the broker itself fully transport-neutral (no
    `asyncio` import in app/application/broker.py) while still letting
    this async generator yield control back to the event loop -- so one
    slow/idle SSE connection cannot block the event loop the way calling
    a blocking function directly on it would, which in turn is what keeps
    one subscriber from blocking another (S9's "must not affect other
    clients" is a broker-level guarantee already; this loop simply must
    not undermine it by blocking the loop that serves every connection).

    Polls in `_SSE_POLL_INTERVAL_SECONDS` slices (rather than one
    long `get(timeout=None)` call) purely so this generator can also
    notice client disconnect (`request.is_disconnected()`) and elapsed
    heartbeat time promptly, without needing a second concurrent task.
    """

    broker = get_application_broker()
    subscription = broker.subscribe()
    loop = asyncio.get_running_loop()

    try:
        last_heartbeat = loop.time()

        while True:
            if await request.is_disconnected():
                return

            event = await asyncio.to_thread(
                subscription.get, _SSE_POLL_INTERVAL_SECONDS
            )

            if event is not None:
                yield _format_sse_event(event)
                last_heartbeat = loop.time()
                continue

            if subscription.closed:
                # Broker shutdown (or an explicit unsubscribe elsewhere) --
                # nothing further will ever arrive on this subscription.
                return

            now = loop.time()
            if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                yield _format_sse_heartbeat()
                last_heartbeat = now
    finally:
        # Runs on disconnect, on the broker closing this subscription out
        # from under us, and on any exception -- always safe/idempotent
        # per Subscription.close()/EventBroker.unsubscribe()'s own
        # docstrings, so no path out of this generator can leak a live
        # subscriber.
        broker.unsubscribe(subscription)


@app.get("/health")
async def health() -> dict[str, Any]:
    """
    GET /health -- liveness check for the sidecar process, per Phase 4E
    Part 1 (docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md S5/S9).

    Registered first, ahead of the command/event routes, and deliberately
    has no dependency on the database, threat-intel providers, or any
    other domain/service state: its only job is answering "is the process
    up and able to handle HTTP", which is exactly what an external process
    supervisor (Tauri, a test harness, a human with curl) needs to poll
    before treating the sidecar as ready. It must stay this cheap --
    anything that could fail, block, or leak internal state does not
    belong here.
    """

    return ok({"status": "ok"})


@app.post("/commands/{name}")
async def run_command(name: str, request: Request) -> dict[str, Any]:
    """
    POST /commands/{name} -- see docs/contracts/command-model.md,
    docs/contracts/ipc-rules.md rule 4 (validation happens inside each
    handler's request DTO, before any domain logic runs).
    """

    handler = COMMAND_HANDLERS.get(name)

    if handler is None:
        return fail(UNKNOWN_COMMAND, f"No such command: {name!r}")

    payload = await request.json()
    return handler(payload)


@app.get("/events")
async def events_stream(request: Request) -> StreamingResponse:
    """
    GET /events -- SSE stream, per docs/contracts/event-model.md and
    docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md S7 (APPROVED FUTURE
    ARCHITECTURE, now implemented here).

    Phase 4D SSE Part 3: this used to return a translated 501 envelope
    (Part 2's fix for the bare-`NotImplementedError`-as-500 bug -- see
    the prior version of this docstring in git history / Part 2's own
    doc). The underlying gap that 501 documented -- "there is no live
    command execution to stream from" -- is closed now: Part 1 built
    `EventBroker` (app/application/broker.py) and Part 2 wired every
    command handler that creates events to publish into it via
    `get_application_broker()`. This route is the first and only
    consumer of that broker from the transport side, per S6's
    "transport-neutral" requirement -- everything SSE/FastAPI-specific
    (framing, heartbeat, disconnect detection, `StreamingResponse`
    itself) lives in this module, not in app/application/.

    Each connection gets its own independent `Subscription` (bounded,
    drop-oldest, per S6) -- see `_sse_event_stream()` for delivery,
    heartbeat, and disconnect-cleanup behavior. A slow or idle client
    cannot block another connection's subscription, since each has its
    own queue and this generator only ever touches its own.
    """

    return StreamingResponse(
        _sse_event_stream(request),
        media_type="text/event-stream",
        headers={
            # Standard SSE headers per S7 -- nothing SOC-IQ-specific.
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disables response buffering on nginx-fronted deployments;
            # a harmless no-op for the loopback-only uvicorn setup this
            # sidecar actually runs under (docs/security/ipc-security-
            # model.md), included because it costs nothing and is
            # standard SSE practice.
            "X-Accel-Buffering": "no",
        },
    )
