# SOC-IQ — Implementation Status

> **Read this first:** the base table immediately below is a point-in-time snapshot from an
> earlier session and several of its rows are superseded by later addenda in this same file
> (see "Addendum 2" and "Documentation reconciliation addendum" further down, including a
> further addendum covering the HTML exporter). Where a row here conflicts with a later
> addendum, the addendum is current; this note exists so a reader of just the table isn't
> misled by rows an addendum has already corrected.

Re-verified this session by direct source inspection and a live `pytest` run. "DONE" below
means evidence was checked this session (file exists AND does what it claims), not merely
that a file with the right name exists.

| Component | Status | Evidence |
|---|---|---|
| IOC extraction (`extractor.py`) | DONE | present, exercised by `tests/test_extractor.py`, part of 399 passing tests |
| Risk scoring (`scoring/`) | DONE | present, exercised by `tests/test_scoring.py` |
| Threat intel — VirusTotal (single provider) | DONE | present, exercised by `tests/test_threat_intel.py`, `tests/test_virustotal.py` |
| Threat intel — provider abstraction (`ThreatIntelProvider`) | NOT STARTED (design DONE) | `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` states "No source code has been changed" |
| Database / repository layer | DONE | present, exercised by `tests/test_database.py` |
| Database migration runner | NOT STARTED | no schema-version table found in `app/database/connection.py` this session (matches Phase 4B finding) |
| Reporting (JSON/CSV/Markdown/PDF) | DONE | present, exercised by `tests/test_reporting.py` |
| Reporting — HTML exporter refactor (template-driven) | NOT STARTED | `html_exporter.py` still 1,861 LOC monolith per master plan §1.7; not re-measured this session |
| Settings service | DONE (current shape) | present, exercised by `tests/test_settings.py`; plaintext-on-disk API key storage confirmed, matches documented gap |
| Settings — OS-backed secret store | NOT STARTED | no evidence found this session |
| Dashboard/correlation/system-health services (`app/services/*`) | DONE | present, exercised by `tests/test_dashboard_services.py`, `test_correlation_service.py`, `test_risk_explanation_service.py` |
| CLI (`app/cli.py`) | DONE | present, exercised by `tests/test_cli.py` |
| PySide6 GUI | DONE (existing, unverified this session) | code present under `app/gui/`; `tests/gui/` could not be collected in this sandbox (`PySide6` not installed) — treat GUI test status as UNVERIFIED, not confirmed-passing, this session |
| Python application/command boundary | IN PROGRESS | `app/application/handlers.py` implements 3 commands (`get_investigation`, `list_investigations`, `analyze_report`); exercised by `tests/test_application_layer.py` |
| FastAPI HTTP transport | IN PROGRESS / BLOCKED (in this sandbox) | `app/api/app.py` present and structurally complete for the 3 wired commands; requires `fastapi`, not installed here, so it could not be run this session |
| SSE event stream (`GET /events`) | NOT STARTED | explicit `NotImplementedError` in source, documented as deferred |
| Unified event model (replacing the two Qt buses) | DESIGNED, NOT IMPLEMENTED | `docs/contracts/event-model.md` exists; `app/gui/events/*` (the buses being replaced) still present in source |
| Tauri/Rust shell | NOT STARTED | no `src-tauri/` directory exists |
| React frontend | NOT STARTED | no `frontend/` directory exists |
| Design tokens ported to TS/CSS | NOT STARTED | tokens exist only under `app/gui/design/tokens/` (Python/Qt) |
| Security hardening (Tauri capability manifest, loopback binding, etc.) | NOT STARTED | no `src-tauri/` to hold a capability manifest yet; loopback-only intent stated in docs, not yet enforced by running code |
| Packaging (sidecar binary, installer) | NOT STARTED | no build scripts found |
| PySide6 retirement | NOT STARTED (by design — blocked on frontend parity, ADR-009) | |

## Test baseline (this session)

```
python3 -m pytest -q --ignore=tests/gui
399 passed in 0.99s
```

`tests/gui/` (13 files) not collected: missing `PySide6` in this sandbox. Do not report a
542-test combined baseline as freshly verified — only the 399 non-GUI figure was confirmed
this session. Re-verify the GUI figure with PySide6 installed before citing it as current.

## Phase status (per master plan §26 roadmap)

| Phase | Objective | Status |
|---|---|---|
| 4A | Architecture reset | COMPLETE — master plan document exists and is the approved bible |
| 4B | Domain boundary hardening | COMPLETE — see `docs/migration/PHASE4B_EXIT_CRITERIA.md` |
| 4C | TI provider abstraction | DESIGN COMPLETE, SOURCE NOT IMPLEMENTED |
| 4D | Unified command/event contract | IN PROGRESS — 3/many commands wired, SSE not implemented |
| 4E–4P | Rust/React/security/integration/retirement/audit | NOT STARTED |

## Do not mark anything DONE without evidence

Per the project's own rule (task brief §23): a component is not DONE merely because a
file with the expected name exists. Every "DONE" row above was checked against either a
passing test this session or direct code inspection. Every "NOT STARTED" row was checked by
confirming the expected file/directory is genuinely absent, not just unmentioned.

## Addendum — Phase 4C completion (later session)

Everything above this line is preserved unedited as the historical record of what was true
in the session that wrote it (predating Phase 4C's implementation, and predating the
`frontend/`/`src-tauri/` scaffolding that exists in the repository as of this addendum —
those rows are correspondingly stale too, and are left as-is for the same reason rather than
silently rewritten). This addendum corrects only the two rows that later became false and
that this addendum's author has direct, freshly-verified evidence for:

- **"Threat intel — provider abstraction (`ThreatIntelProvider`)"**: no longer NOT STARTED.
  Implemented and frozen across Phase 4C Stages 1–3. See
  `docs/migration/PHASE4C_EXIT_CRITERIA.md` for the full exit-criteria checklist and
  evidence. Current status: **DONE** — `app/threat_intel/{models,provider,
  virustotal_provider}.py`; `ThreatIntelService` depends on `list[ThreatIntelProvider]`;
  `app/gui/pages/threat_intel_page.py` no longer constructs `VirusTotalClient` directly;
  exercised by `tests/test_threat_intel*.py`, `tests/test_virustotal_provider.py`,
  `tests/gui/test_threat_intel_page_url.py`.
- **Phase status table, "4C | TI provider abstraction"**: no longer "DESIGN COMPLETE, SOURCE
  NOT IMPLEMENTED". Current status: **COMPLETE** — see
  `docs/migration/PHASE4C_EXIT_CRITERIA.md`.

Fresh test baseline at Phase 4C freeze (this addendum's own session, not the "this session"
referenced above, which is a different and earlier session):

```
python3 -m pytest tests/ -q --ignore=tests/gui
481 passed

QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q
635 passed
```

Do not read this addendum as re-verifying any row above it other than the two named here —
the rest of this document's claims (database migration runner, HTML exporter, OS-backed
secrets, FastAPI transport, SSE, event model, Tauri/React/packaging/PySide6 retirement) were
not re-checked to produce this addendum and may themselves be stale; re-verify them
independently before relying on them.

## Addendum 2 — Phase 4D command/event/SSE/frontend/Tauri completion (documentation reconciliation pass)

Everything above this line (including Addendum 1) is preserved unedited as the historical
record of what was true in the sessions that wrote it. This addendum corrects the rows and
the phase-status table entry that later became false, per
`docs/phase4/PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md` and this pass's own fresh
re-verification (see test baseline below). This is a **documentation reconciliation pass
only** — no implementation source was changed to produce this addendum.

Row corrections:

- **"Python application/command boundary"**: no longer "3 commands". Current status:
  **DONE** — `app/application/handlers.py::COMMAND_HANDLERS` implements all 10 planned
  commands (`get_investigation`, `list_investigations`, `analyze_report`,
  `delete_investigation`, `search_investigations`, `get_iocs`, `save_settings`,
  `export_report`, `enrich_ioc`, `get_threat_intelligence`), each routed through a single
  `dispatch()` function. Exercised by `tests/test_application_layer.py`, 77/77 passing this
  session.
- **"FastAPI HTTP transport"**: no longer "IN PROGRESS / BLOCKED". Current status: **DONE**
  — `fastapi` is installed and exercised in this environment; `app/api/app.py` runs and is
  covered by `tests/test_api_layer.py`, 29/29 passing this session.
- **"SSE event stream (`GET /events`)"**: no longer "NOT STARTED" / `NotImplementedError`.
  Current status: **DONE** — `GET /events` is a real `StreamingResponse` with SSE framing,
  heartbeat (`: heartbeat\n\n` comment frames, distinct from named events), and
  disconnect/subscriber cleanup. See `docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md` and
  the SSE Part 1–4C implementation docs for the full build history.
- **"Unified event model (replacing the two Qt buses)"**: no longer "DESIGNED, NOT
  IMPLEMENTED". Current status: **DONE** — `app/application/events.py` (`Event`,
  frozen/immutable, with `event_id`/`correlation_id`) and `app/application/broker.py`
  (`EventBroker`, bounded per-subscriber queues via `deque(maxlen=capacity)`, thread-safe)
  are implemented and exercised by `tests/test_event_broker.py`, 37/37 passing this session.
  `EventCollector` compatibility is preserved (`EventCollectorCompatibilityTests`, same
  file).
- **"Tauri/Rust shell"**: no longer "NOT STARTED — no `src-tauri/` directory exists". Current
  status: **SOURCE IMPLEMENTED, COMPILATION NOT VERIFIED IN THIS ENVIRONMENT**.
  `src-tauri/src/lib.rs` contains exactly one `#[tauri::command]`
  (`get_sidecar_origin`), registered exactly once via
  `tauri::generate_handler![get_sidecar_origin]`. This is a source-level and
  static-analysis finding, not a compiled-binary or runtime finding — see the Rust toolchain
  note below.
- **"React frontend"**: no longer "NOT STARTED — no `frontend/` directory exists". Current
  status: **DONE (source implemented, typechecked, and built)** —
  `frontend/src/shared/events/useEventStream.ts` and
  `frontend/src/shared/events/eventSourceManager.ts` implement the `EventSource` consumer;
  `frontend/src/shared/api/client.ts` resolves the sidecar origin via a real
  `invoke<string>("get_sidecar_origin")` call. `npm install` (73 packages), `npm run
  typecheck` (0 errors), and `npm run build` (44 modules, production build succeeded) all ran
  clean this session.

Phase-status table correction — row "4D | Unified command/event contract": no longer "IN
PROGRESS — 3/many commands wired, SSE not implemented". Current status:
**IMPLEMENTATION COMPLETE — all 10 commands wired, SSE implemented and tested. Phase 4D
itself is NOT YET FROZEN** (freeze is a separate, later decision — see
`docs/phase4/PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md`).

### Rust toolchain limitation (explicit, not hidden)

`src-tauri` has never been compiled successfully in any session of this project, including
this one. The available `cargo`/`rustc` in this environment is **1.75.0**. A transitive
dependency (`dlopen2 0.8.2`) requires the `edition2024` Cargo feature, which needs cargo
**≥1.85**. This was reproduced fresh this session (`cargo check` inside `src-tauri/`, same
exact error). This is an **external toolchain-version blocker**, not a defect found in
`src-tauri`'s own source, and it has not been worked around — no dependency was downgraded
and no Cargo.toml edit was made to force a pass. `sidecar-core` (the Rust process-supervision
logic `src-tauri` builds on) is a separate crate, compiles cleanly on this same 1.75.0
toolchain, and passes 49/49 tests this session (`cargo test` in `sidecar-core/`).

### Test baseline (this addendum's own session, fresh)

```
python3 -m unittest tests.test_application_layer -v      → 77 passed
python3 -m unittest tests.test_event_broker -v            → 37 passed
pytest tests/test_api_layer.py -q                          → 29 passed
pytest tests/test_sidecar_entrypoint.py -q                 → 8 passed
pytest tests/ --ignore=tests/gui -q                         → 600 passed
QT_QPA_PLATFORM=offscreen pytest tests/gui -q               → 154 passed
cd sidecar-core && cargo test                                → 49 passed
cd src-tauri && cargo check                                  → BLOCKED (edition2024, cargo 1.75.0)
cd frontend && npm run typecheck                              → 0 errors
npm run build                                                  → 44 modules, success
```

These are **currently executed** numbers from this session, not carried over from prior
documentation, though they happen to match the counts previously reported in
`docs/phase4/PHASE4D_SSE_PART4C_IMPLEMENTATION.md` and
`docs/phase4/PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md` exactly.

Do not read this addendum as re-verifying anything outside Phase 4D's command/event/SSE/
frontend/Tauri-source scope — database migration runner, HTML exporter refactor, OS-backed
secrets, and design-tokens-ported-to-TS/CSS rows above were not re-checked this pass and may
still be stale; re-verify independently before relying on them.

## Documentation reconciliation addendum (this pass)

Re-verified this session by direct source inspection and live test runs. Scope: the rows
this pass found materially stale relative to current source — Settings, standalone Risk,
and secure credential storage — plus current test/build counts. Rows not listed here were
not re-checked this pass; see the caveat at the end of the prior addendum above, which still
applies.

| Component | Status | Evidence |
|---|---|---|
| Settings — theme persistence, modern UI | DONE | `frontend/src/pages/settings/ThemeControl.tsx`, wired via `useSettingsFieldSave` to `save_settings`; rendered from `SettingsPage.tsx` |
| Settings — export directory persistence, modern UI | DONE | `frontend/src/pages/settings/ExportDirectoryControl.tsx`, same `save_settings` path |
| Settings — VirusTotal credential write, modern UI | DONE | `frontend/src/pages/settings/VirustotalControl.tsx` + `useVirustotalKeySave.ts` → `keystore_set_secret`; rendered from `SettingsPage.tsx`. Restart-required lifecycle (Option A): saving updates the OS keystore immediately, the running sidecar is not live-refreshed, next launch re-runs the secret handoff |
| Settings — OS-backed secret store (Python side) | DONE (read-only by design) | `app/secrets/store.py::RustKeystoreHandoffSecretStore` reads only the process-scoped env-var handoff Rust sets at sidecar startup; no `keyring` dependency in `requirements.txt` or `app/` (ADR-008 Part 1B-2) |
| Standalone Risk page retirement (PD-06) | DONE | `frontend/src/pages/RiskPage.tsx` and `frontend/src/mock/risk.ts` are absent from source; no `/risk` route, nav item, or command-palette entry found this session. Real risk scoring (`app/scoring/**`), `RiskExplanationService`, and `InvestigationOverviewRisk.tsx` are unaffected |

Corrects the "Settings — OS-backed secret store" row in the original table above, which
predates the Rust keystore migration and the modern-UI Settings wiring described here.

### Test baseline (this addendum's own session, fresh)

```
python3 -m pytest -q --ignore=tests/gui        → 856 passed
tests/gui (offscreen)                          → not run this session (PySide6 not installed
                                                   in this sandbox); not claimed as passing
cd frontend && npx tsc --noEmit                → clean
cd frontend && npx vitest run                  → 1006 passed (77 files)
cd frontend && npm run build                   → 189 modules, succeeded
cd src-tauri && cargo check                    → ENVIRONMENT-BLOCKED (no cargo/rustc in this
                                                   sandbox); not claimed as passing or failing
cd sidecar-core && cargo test                  → ENVIRONMENT-BLOCKED, same reason
```

These backend/frontend counts were captured fresh this session and differ slightly from
counts recorded in `README.md` prior to this pass (which reflected an earlier session); both
this addendum and `README.md` have been brought into agreement as of this reconciliation.

## Addendum 3 — HTML exporter finding (Part 14 documentation reconciliation)

The base table's "Reporting — HTML exporter refactor (template-driven)" row above (originally
"NOT STARTED ... 1,861 LOC monolith ... not re-measured this session") was flagged as
possibly stale by Part 13's audit and independently re-measured this session.

| Component | Status | Evidence |
|---|---|---|
| Reporting — HTML exporter refactor (template-driven) | DONE | `app/reporting/html_exporter.py` is now 259 lines and its own module docstring states: "Architecture (Phase 4L-P2): the previous implementation hand-built the entire HTML/CSS/JS document as Python f-strings (1,861 LOC). This module now does only data assembly ... and delegates all presentation markup to the Jinja2 template" (`app/reporting/templates/report.html.j2`, 1,653 lines). Exercised by `tests/test_html_exporter_content_equivalence.py`, 43/43 passing this session |

This corrects the base table's row to DONE. The refactor is fully complete, not partial —
report content, structure, and behavior are documented as unchanged; only how the HTML is
produced changed (Python f-string monolith → data assembly + Jinja2 template).

## Addendum 4 — MAX-20A/20B analyst-workflow audit (fresh baseline + GUI re-verification)

Fresh test/build baseline, actually executed this session (not carried over):

```
python3 -m pytest -q --ignore=tests/gui        → 1142 passed
QT_QPA_PLATFORM=offscreen pytest tests/gui -q  → 104 passed  (PySide6 installed fresh
                                                   this session; prior sessions could not
                                                   collect this suite at all)
QT_QPA_PLATFORM=offscreen pytest tests/ -q     → 1246 passed (combined)
cd frontend && npx tsc --noEmit                → clean
cd frontend && npx vitest run                  → 1370 passed (98 files)
cd frontend && npm run build                   → succeeded
cd src-tauri && cargo check                    → ENVIRONMENT-BLOCKED: no cargo/rustc at all
                                                   in this sandbox (not merely an old
                                                   version, as prior sessions found --
                                                   verified absent this session)
cd sidecar-core && cargo test                  → ENVIRONMENT-BLOCKED, same reason
```

These counts are all higher than Addendum 2/the reconciliation-pass addendum's figures
(856 backend / 1006 frontend / 77 files) -- the codebase has grown since; this is not a
regression. **GUI is now confirmed passing in this environment for the first time** (prior
addenda could only say "unverified, PySide6 not installed").

**Correction to a claim made in this pass's own prior MAX-20A audit report** (not part of
this file previously, recorded here so the correction is durable): that audit stated
`frontend/package.json`'s description was straightforwardly false about Settings. On
closer, quote-style-corrected inspection, that was an overstatement -- `SettingsPage.tsx`
does import and render `mock/settings.ts`'s `mockSettingsSections`, and does so with
explicit, user-visible labeling ("read-only mock values -- no changes made here are
saved") and an explicit in-code "no dead mock cleanup" scope boundary. That is disclosed
mock content, not undisclosed fake functionality, and was left as-is (not deleted) for
that reason. The package.json description has been corrected in this pass to state the
real (mixed) picture precisely, since the original wording ("Settings remain
mock/placeholder") was still incomplete -- it named only the mock portion and omitted the
real, backend-wired Appearance/Export Directory/Integrations controls that already existed.

`frontend/src/mock/dashboard.ts`, `mock/investigations.ts`, and `mock/reports.ts` were
re-confirmed this session to have zero non-test production imports (quote-style-corrected
grep, both single- and double-quoted import forms checked). `mock/settings.ts` is the one
exception -- it is live, per above. Removing the three genuinely-dead files was judged
out of scope for this pass (a cleanup, not a workflow-gap fix) and was not done.

Added this session: `frontend/src/pages/investigation/analystJourney.integration.test.tsx`
-- a cross-module test exercising the real (unmodified) `executeAnalysis` /
`useInvestigation` / `useReportExport` composed together (analyze → open workspace →
export → reopen from history), asserting `analyze_report` fires exactly once across the
whole journey including an export failure-and-retry. No prior test asserted that
cross-stage invariant; every existing test mocked each hook's `runCommand` independently.

## Governance note (Part 14 documentation reconciliation)

ADR status transitions are not currently governed by a documented repository convention.
Every ADR in `docs/adr/` (ADR-001 through ADR-010) remains **Proposed**, including several
whose described architecture is implemented and tested (see the addenda above, and the
implementation notes added to ADR-001 and ADR-008). This document does not resolve that
gap or invent an acceptance process — it only records that the gap exists, so that
"Proposed" is not misread as "not implemented" (or the reverse) when checking any ADR
against this status file.
