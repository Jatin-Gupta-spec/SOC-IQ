"""
R4-B0 CORS remediation -- regression tests for app/api/app.py's
`CORSMiddleware` registration.

Context (docs/audits/SOC-IQ-R4-A-INSTALLATION-LAUNCH-VERIFICATION.md,
"R4-A packaged runtime diagnostic" section): a real Windows install of
the packaged Tauri application showed the Dashboard failing with
`Network failure calling command "get_dashboard_summary": Failed to
fetch`, while a direct out-of-browser HTTP call (PowerShell
`Invoke-WebRequest`) against the same running sidecar succeeded. Root
cause: `app/api/app.py` had zero CORS support, and the frontend's
`fetch()` call (`frontend/src/shared/api/client.ts::runCommand`) is a
genuine cross-origin request from the Tauri WebView's own origin to
`http://127.0.0.1:<port>` -- a non-"simple" `POST` with
`Content-Type: application/json` triggers a browser CORS preflight
(`OPTIONS`) that, with no CORS middleware registered, this backend had
no way to answer correctly, so the WebView aborted the request before
this application ever produced a real response (matching the bare,
status-code-less `fetch()` TypeError seen in the field).

`fastapi.testclient.TestClient` (used throughout this project's
existing `tests/test_api_layer.py`) does not enforce CORS at all -- the
same reason the field failure was never caught by that suite -- so
these tests instead assert on the actual `Access-Control-*` response
headers the middleware adds, which is what a real browser/WebView
enforces, rather than merely on HTTP status codes.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import app

client = TestClient(app)

# One of the concrete origins app/api/app.py's `_DEFAULT_ALLOWED_ORIGINS`
# allows -- see that module's doc comment for why this specific set was
# chosen (the real Tauri packaged-WebView origin on Windows was not
# independently observable in this environment; this is one of the
# documented candidates).
_ALLOWED_ORIGIN = "http://tauri.localhost"
_DISALLOWED_ORIGIN = "https://evil.example.com"


def test_preflight_for_dashboard_command_is_permitted_for_allowed_origin() -> None:
    """
    The exact preflight the real WebView sends before
    `runCommand("get_dashboard_summary", {})`'s POST: an OPTIONS request
    with `Access-Control-Request-Method: POST` and
    `Access-Control-Request-Headers: content-type`. Must succeed and
    grant exactly the access the real POST needs.
    """
    response = client.options(
        "/commands/get_dashboard_summary",
        headers={
            "Origin": _ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


def test_actual_cross_origin_post_succeeds_and_carries_cors_header() -> None:
    """
    The real request the preflight above is a gatekeeper for: a
    cross-origin POST with a JSON body and an Origin header, exactly as
    the WebView's own `fetch()` sends it. Must return the normal 200 +
    envelope (proving the command dispatch itself is untouched by this
    change) AND carry `Access-Control-Allow-Origin` (proving the
    browser/WebView would actually be permitted to read the response --
    the specific thing that was missing before this fix).
    """
    response = client.post(
        "/commands/get_dashboard_summary",
        json={},
        headers={"Origin": _ALLOWED_ORIGIN, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN

    body = response.json()
    assert body["success"] is True
    assert body["error"] is None


def test_disallowed_origin_receives_no_cors_grant() -> None:
    """
    Scope check: this must not be a wildcard fix. A preflight from an
    origin that is not in the explicit allow-list must not receive an
    `Access-Control-Allow-Origin` header -- Starlette's CORSMiddleware
    represents a disallowed preflight as a plain 400 with no CORS
    headers, which is exactly the "no grant" outcome this test pins.
    """
    response = client.options(
        "/commands/get_dashboard_summary",
        headers={
            "Origin": _DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_dev_server_origin_is_still_permitted() -> None:
    """
    `cargo tauri dev`'s `devUrl` (`src-tauri/tauri.conf.json`,
    `http://localhost:1420`) must remain permitted, so this change does
    not regress the existing development workflow.
    """
    response = client.options(
        "/commands/get_dashboard_summary",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:1420"


def test_health_endpoint_unaffected_by_cors_change() -> None:
    """Sanity check: the unrelated /health route still behaves exactly
    as before -- this change must not alter any existing route's own
    behavior, only add the middleware layer around all of them."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}


def test_unknown_command_still_returns_the_existing_fail_envelope() -> None:
    """Another unrelated-behavior guard: an unknown command name must
    still produce the pre-existing UNKNOWN_COMMAND fail envelope, cross-
    origin or not -- CORS is a browser-enforced access control, not a
    second application-level validation layer, and must not change what
    this route itself returns."""
    response = client.post(
        "/commands/not_a_real_command",
        json={},
        headers={"Origin": _ALLOWED_ORIGIN, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNKNOWN_COMMAND"
