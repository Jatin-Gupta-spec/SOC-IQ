# Phase 4D Part 2 — Closing the Environment-Constrained Gaps

**Status:** Complete for the scope stated below. Builds on
`PHASE4D_API_EVENT_ARCHITECTURE.md` ("Part 1"), which designed the
application/API boundary but could not execute most of it (no network
access to install `fastapi`/`pydantic`/`pytest`/`uvicorn`). This
environment has that access. Part 2's scope is therefore **proving Part
1's design actually runs**, not adding new use cases — see §3 for why no
new commands were implemented.

## 1. Audit performed before any change

| Item | Status found | Action taken |
|---|---|---|
| `app/application/*` (dto, errors, events, handlers, responses) | Fully implemented, Part 1 | Unchanged |
| `app/api/app.py` (FastAPI transport) | Written, never executed (no fastapi installed) | Executed, verified, one bug fixed (§2) |
| `fastapi`/`pydantic`/`uvicorn`/`httpx` | Not installed, install blocked in Part 1's sandbox | Installed here; verified this sandbox has network access to PyPI |
| Full `pytest` suite | Never actually run in Part 1 (`pytest` wasn't installed) — the "558 passed" figure was carried forward from an earlier phase's `unittest`-only run, not re-verified against the real suite | Installed `pytest` + full `requirements.txt`, ran the complete suite for real: **558 passed** (see §5) |
| `get_iocs`, `get_threat_intelligence`, `get_risk`, `export_report`, `delete_investigation`, `search_investigations`, `enrich_ioc` | Explicitly out of scope, Part 1 §22 | **Still not implemented** — see §3 |
| `analyze_report` sync-vs-async | Unresolved, flagged Part 1 §11/§21 | Re-inspected, confirmed still unresolved, **not decided here** — see §4 |
| GUI (`app/gui/**`) | Zero-coupling to `app/application`/`app/api`, confirmed Part 1 | Re-confirmed via import grep (§6); no GUI file touched |

## 2. What was actually implemented this phase

1. **Installed and exercised the real FastAPI transport.** `app/api/app.py`
   now runs against real `fastapi`/`pydantic`/`uvicorn`/`httpx` (versions
   pinned in `requirements.txt`). This resolves Part 1's single largest
   flagged UNKNOWN (§21: "whether the code in §6.4 actually works... not
   executed").
2. **`tests/test_api_layer.py` (new, 6 tests).** Uses
   `fastapi.testclient.TestClient` to drive `POST /commands/{name}` and
   `GET /events` as real HTTP calls through the actual FastAPI app —
   proving routing, JSON (de)serialization, validation-before-domain
   (contract rule from `docs/contracts/ipc-rules.md` #4), and error
   translation all work outside of the transport-agnostic
   `dispatch()` function that `tests/test_application_layer.py` already
   covered directly.
3. **Fixed a real error-boundary bug in `GET /events`.** It previously
   raised a bare `NotImplementedError`, which FastAPI turns into an
   unhandled 500 with a raw traceback — a genuine violation of the
   invariant stated in both `PHASE4D_API_EVENT_ARCHITECTURE.md` §10 and
   `app/application/responses.py`'s own docstring ("never a raised
   exception for expected failure modes"). "SSE isn't wired up yet" is an
   *expected*, documented gap, not a bug, so the route now returns the
   same translated error envelope every other expected failure uses
   (`NOT_IMPLEMENTED` code, HTTP 501) instead of leaking a stack trace.
   This is a boundary fix, not an SSE implementation — see §4 for why SSE
   itself is still not implemented.
4. **`requirements.txt` updated** to declare `fastapi`, `pydantic`,
   `uvicorn`, `httpx` as real dependencies, since they are now genuinely
   exercised by the test suite rather than aspirational.

## 3. Why no new commands were implemented

The Part 2 brief lists `get_iocs`, `get_threat_intelligence`, `get_risk`,
`export_report`, `delete_investigation`, `search_investigations`,
`enrich_ioc` as deferred candidates and says: *"Determine from the
architecture document which of these belong in Part 2... do not
automatically implement all seven."* `PHASE4D_API_EVENT_ARCHITECTURE.md`
does not subdivide this list into a Part-2-scoped subset and a later-scoped
subset — it lists all seven together as "explicitly out of scope this
phase" (§22), with no signal distinguishing any one of them as
next-in-line. No other document in `docs/` (checked `docs/contracts/`,
`docs/phase4/`) makes that call either.

Rather than guess which of the seven an unstated future scope intends —
which would be inventing architecture, the thing both the original brief
and this one explicitly forbid — this phase's scope was read as "make the
already-approved 3-command design actually run," which is unambiguous and
fully verifiable. Implementing any of the seven remains available as a
follow-up once someone scopes which one(s) are next; each would follow the
identical, already-proven pattern (`dto.py` request DTO → `handlers.py`
command handler → existing service call → response DTO), per Part 1 §6.

## 4. Sync/async decision on `analyze_report` — still unresolved, by design

Re-inspected `app/analyzer.py` this phase: `analyze_report` is still a
plain synchronous function; no `asyncio`, no task queue, no background
worker infrastructure exists beyond the GUI's `AnalysisWorker` `QThread`
(untouched, GUI-only). Nothing in this phase's scope resolves the
contract doc's stated intent (fire-and-acknowledge, full result only via
`analysis.completed` event) versus the reference handler's actual
behavior (synchronous, full result returned inline). Per the instruction
not to silently make this call, it is left exactly as Part 1 left it:
`AnalyzeReportCommandHandler` still runs synchronously and returns the
full result immediately, with the same code-comment marker Part 1 left at
the spot where the async boundary would go. This is the same reason
`GET /events` still doesn't stream anything real (§2 above only stopped it
from crashing) — there is still no live producer to stream from.

## 5. Full regression

```
Before Part 2 (re-run for real, not re-quoted from a prior phase):
558 passed

After Part 2:
564 passed, 0 failed, 0 skipped
```

The 6-test delta is exactly `tests/test_api_layer.py`; no existing test
was modified, skipped, or deleted.

## 6. Dependency audit

`grep` over `app/application/*.py` and `app/api/*.py` for any import
touching `app.gui` or `app.gui` importing `app.application`/`app.api`:
zero matches in both directions. Dependency direction is confirmed:
`API → Application → Domain/Services`, with `app/gui/**` remaining a
fully independent caller of the same unmodified domain functions, exactly
as Part 1 left it.

## 7. Remaining Phase 4D work (unchanged from Part 1 §22, re-confirmed)

- `get_iocs`, `get_threat_intelligence`, `get_risk`, `export_report`,
  `delete_investigation`, `search_investigations`, `enrich_ioc` command
  handlers — not implemented (§3).
- A real, streaming `GET /events` SSE implementation — still not
  implemented; the route now fails safely instead of crashing (§2), but
  emits no events.
- The sync-vs-async decision for `analyze_report` — still open (§4).
- The `backend/` package restructuring (Part 1 §5.1) — untouched, out of
  scope.
- Pydantic-native `BaseModel` conversion of the dataclass DTOs — not done;
  the dataclasses remain a deliberate, field-for-field stand-in per Part 1
  §6, and now that `pydantic` is actually installed this conversion is
  unblocked whenever it's scoped.
- Frontend TypeScript type generation (Part 1 §17) — still blocked on the
  same missing runnable `pydantic.BaseModel`/FastAPI app for introspection
  as above; unblocked in principle, not attempted this phase (out of the
  stated Part 2 scope).
