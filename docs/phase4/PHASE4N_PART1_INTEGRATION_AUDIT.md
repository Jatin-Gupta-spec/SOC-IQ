# Phase 4N Part 1 -- Integration Audit & First Real Full-Stack Test

## 0. Phase-map correction (read this first)

The task brief's phase map asserts 4J/4K/4L/4M are all COMPLETE and states
4M is COMPLETE "only if the previous checkpoint explicitly confirmed
closure." **No such closure exists.** Unlike every other completed phase
(4C, 4D, 4H-P4, etc.), there is no `PHASE4M_FREEZE.md` or equivalent
anywhere in `docs/phase4/`, and no `PHASE4L_*` doc exists either.

Source-level audit finds the *work* for 4M genuinely done in code (not
merely claimed): `app/secrets/store.py` (OS-keyring-backed secret store),
`src-tauri/capabilities/default.json` (least-privilege capability
manifest -- `core:default` + exactly `dialog:allow-open` +
`fs:allow-read-file`, no wildcard defaults), `docs/security/*` (8
threat/trust/capability model docs), and 343 lines of
`tests/test_secret_store.py`, all passing. So 4M's *exit criterion*
("Security tests (S20) passing") is met -- but it was never formally
frozen, and the capability manifest's own description header still says
"Phase 4I Rust/Tauri verification fix," not Phase 4M, meaning it predates
whatever 4M's own dedicated deliverable was and there's no doc tying the
two together. **Recommendation: treat 4M as functionally complete but
formally unfrozen** -- worth a real `PHASE4M_FREEZE.md` before anyone
relies on "4M is frozen" as an assumption. Not written here, since
writing it wasn't this session's brief and retroactively declaring
closure on someone else's behalf is exactly the kind of unverified claim
this audit exists to avoid.

## 1. What was audited

Per the brief's AUDIT BEFORE IMPLEMENTING requirement:

- Read `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md`
  S26 (migration table) for 4N's actual exit criterion: "End-to-end flows
  working together / E2E tests green."
- Inspected `app/application/`, `app/api/`, `app/database/`,
  `app/threat_intel/`, `frontend/src/`, `src-tauri/`, `sidecar-core/`,
  `tests/` directly (source, not docs-only).
- Read `tests/test_api_layer.py` and `tests/test_application_layer.py` in
  full. Both modules' own docstrings already document the exact gap this
  session closes: HTTP-transport tests exist only for read-only commands;
  the mutating `analyze_report` command is proven at the handler layer
  (direct Python call, no live event loop) but was never exercised
  through the actual `async def` FastAPI route.

## 2. What was implemented

One new file: `tests/test_integration_e2e.py`. Nothing else changed --
confirmed by a full diff against the untouched upload (see S6).

Five real tests, all using the actual `fastapi.testclient.TestClient`
against the real `app` object, the real `InvestigationRepository`/SQLite
database (snapshotted/restored around each test, following the existing
precedent in `AnalyzeReportCommandHandlerTests`), and the real
`app.analyzer.analyze_report` pipeline against a real fixture in
`samples/`. VirusTotal is not mocked -- it is simply unconfigured (no API
key in `config/settings.json`), which is itself a real code path, not a
stub.

1. **`test_analyze_report_persists_and_is_retrievable_through_http`** --
   acceptance criterion A end-to-end: `POST /commands/analyze_report` →
   real pipeline → real SQLite write → a *separate* `POST
   /commands/get_investigation` call proves persistence (not just an
   in-process return value) → `POST /commands/get_dashboard_summary`
   proves the dashboard reads the same database → `POST
   /commands/export_report` (json) proves reporting can read what
   analysis just wrote. All four over real HTTP.
2. **`test_analyze_report_error_path_propagates_honestly_through_http`**
   -- criterion E: a missing report file produces a real
   `REPORT_NOT_FOUND` error through the full HTTP envelope, not a 500 and
   not a false success.
3. **`test_list_investigations_is_honestly_empty`** /
   **`test_dashboard_summary_is_honestly_zeroed`** -- criterion F: a
   genuinely empty (freshly-created, not filtered) real database returns
   an honest empty/zeroed state through HTTP, not a fabricated one.
4. **`test_threat_intel_enrichment_silently_fails_through_real_async_transport`**
   -- see S3. Pins down a real, previously-undiscovered defect as an
   explicit, tracked assertion instead of leaving it buried in a log line.

## 3. Defect found -- NOT fixed, flagged for sign-off

`app.threat_intel.service.ThreatIntelService._lookup_raw` bridges its
provider's `async lookup_raw()` onto a synchronous caller via
`asyncio.run(provider.lookup_raw(ioc))`. Every existing test invokes
`analyze_report` synchronously (no event loop already running), so this
has always passed. `app/api/app.py`'s `POST /commands/{name}` route is
`async def` -- exactly how the real sidecar serves every command from the
real Tauri frontend. Calling `asyncio.run()` from inside an already-running
event loop is a hard `RuntimeError`, so **real threat-intel enrichment
silently fails on every `analyze_report` call made through the actual
production transport**, regardless of whether a VirusTotal API key is
configured. `app/analyzer.py`'s broad `except Exception` catches it and
the investigation still saves successfully with
`threat_intelligence.status = "unavailable"` -- but with
`reason = "error"`, masking what should be the more specific
`"missing_api_key"` a user with no configured key ought to see.

This is a genuine integration regression, exactly the kind Phase 4N exists
to surface -- and it sits inside `app/threat_intel/`, one of the frozen
areas the brief names explicitly ("Threat Intel provider architecture").
Per the brief's own rule ("If any frozen file is modified: STOP and
explain why before proceeding"), **it has not been touched.** This
report is that stop-and-explain. A fix (likely: run the coroutine via
`asyncio.run_coroutine_threadsafe` against a dedicated loop, or make
`_lookup_raw`'s sync/async bridging environment-aware) is a reasonable
next step, but is a decision for the next part, not this one.

## 4. Regression results (all real, all executed this session)

| Suite | Result |
|---|---|
| `pytest tests/ -q --ignore=tests/gui` | **763 passed, 1 skipped** (758 baseline + 5 new) |
| `pytest tests/gui -q` (offscreen) | **153 passed, 1 skipped** |
| `npx tsc --noEmit` (frontend) | **0 errors** |
| `npx vitest run` (frontend) | **965 passed** (70 files) |
| `npm run build` | not separately re-run this session (tsc + vitest both clean; no frontend files touched) |
| `cargo check` / `cargo test` | **ENVIRONMENT BLOCKED** -- no Rust toolchain (`cargo`/`rustc` not found) in this sandbox, consistent with every prior Phase 4 session on this project |

## 5. Environment blockers

- Rust: no toolchain available at all. `src-tauri`/`sidecar-core` changes
  (none made this session) remain unverifiable by `cargo` in this
  sandbox, as in every previous checkpoint.
- Browser/Tauri runtime: not available; no real end-to-end
  frontend-clicking-through-the-app verification was possible. The HTTP
  contract layer is verified for real instead (S2), which is the
  furthest this sandbox can honestly reach.

## 6. Diff audit

`diff -rq` against the untouched upload (excluding caches/build
artifacts and the local SQLite file, which the empty-state test
legitimately touches transiently and always restores) shows exactly one
change: `tests/test_integration_e2e.py` added. Dashboard, Reporting,
Threat Intel *implementation*, Analysis architecture, sidecar lifecycle,
database schema, and security-hardening implementation are all
byte-identical to the upload.

## 7. Explicitly not done in this part

- Full 20-row integration matrix (frontend entry point → command → …) for
  every SCOPE item -- this part focused on closing the one concretely
  documented, highest-value gap (mutating command through real async
  transport) plus the defect it surfaced, rather than producing a
  comprehensive matrix as a separate deliverable. Worth doing as a
  focused follow-up if useful.
- Any fix to the threat-intel async bridging defect (S3) -- flagged, not
  implemented, pending sign-off.
- A `PHASE4M_FREEZE.md` -- flagged as missing (S0), not authored here.
- Sidecar lifecycle / Rust-side integration tests -- blocked by the
  absent Rust toolchain (S5).
- Phase 4O -- not started, per the brief.
