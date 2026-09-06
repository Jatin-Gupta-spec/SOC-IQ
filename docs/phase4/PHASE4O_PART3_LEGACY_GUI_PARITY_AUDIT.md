# Phase 4O — Part 3: Legacy GUI Parity Audit

**Status:** AUDIT ONLY. No files under `app/gui/**` or `tests/gui/**` were
deleted, moved, or modified in this part. This document is the missing
Phase 4O Parts 1–3 evidence base that Part 4 (retirement) requires before
any deletion happens.

**Correction to prior checkpoint framing:** Part 4's original instructions
referred to "15 legacy GUI test suites." The actual count under
`tests/gui/*.py` is **12 test-suite files** (14 files total in the
directory once `__init__.py` and `conftest.py` are excluded). All 12 are
audited below; there is no evidence a 13th–15th suite ever existed in this
checkpoint.

---

## 1. Executive Summary

- `app/gui/**` contains **108 Python files** (97 non-`__init__.py`
  production modules + 11 `__init__.py` package markers). `tests/gui/**`
  contains **12 real test-suite files** (+ `conftest.py`, `__init__.py`).
- **No production runtime path reaches `app/gui` at all.** The real
  application entrypoints are `app/cli.py`/`app/main.py` (legacy CLI) and
  `app/api/entrypoint.py` (the Tauri sidecar, launched as
  `python -m app.api.entrypoint` per `src-tauri/src/sidecar.rs`). Neither
  imports anything under `app.gui`. `app/gui/app.py:main()` — the PySide6
  GUI's own bootstrap — is itself never imported from outside `app/gui`,
  so even the legacy desktop app is not wired into any current launcher.
- Every non-test reference to `app.gui` found outside the package itself
  is a **docstring/comment** in `app/application/*` and `app/services/*`
  explicitly documenting that those modules do *not* import `app.gui`
  (architectural boundary notes, not real imports). The one real
  cross-boundary import is `tests/test_threat_intel_state.py`, which
  imports `app.gui.services.ioc_detail_context` on purpose, to prove the
  GUI's compatibility shim re-exports the exact same canonical objects as
  `app.services.threat_intel_state` — i.e. a test that *protects* the
  planned retirement, not a production dependency.
- **Business logic already lives outside `app/gui`.** Both
  `ioc_detail_context` and `ioc_significance` (the two modules Phase 4O's
  framing specifically flagged) have their canonical implementations at
  `app/services/ioc_detail_context.py` and `app/services/ioc_significance.py`.
  The file at `app/gui/services/ioc_detail_context.py` is already a
  documented backward-compatibility shim that only re-exports the same
  objects — it contains no logic of its own.
- The React frontend has **proven equivalents** for the large majority of
  legacy GUI behavior (investigation workspace, IOC display, dashboard,
  reporting export dispatch, threat-intel indicator detection). It has
  **two confirmed, real gaps**:
  1. The legacy "Why this risk?" narrative/contributing-evidence drill-down
     (`RiskExplanationWidget`) has a backend service
     (`app/services/risk_explanation_service.py`) but **no frontend
     consumer** — `InvestigationOverviewRisk.tsx` only renders
     score/severity/confidence, not the narrative or contributing points.
  2. The legacy per-category "Risk Significance" badge
     (`IOCSummaryWidget`, backed by `ioc_type_significance()`) has **no
     rendered equivalent** anywhere in `frontend/src` — `grep` for
     "significance" across `frontend/src` returns zero non-test hits.
  3. Bulk CSV export of investigation history
     (`app/gui/utils/csv_exporter.py`, invoked from `history_page.py`) has
     **no modern equivalent**, and this is already a *documented,
     deliberate* exclusion in `app/application/dto.py` (the modern
     `export_report` command is single-investigation; the legacy CSV
     exporter takes a list, "wrapping it here would be inventing
     behavior").
- **Verdict for Part 4:** the majority of `app/gui` (Qt-specific chrome,
  design tokens, presentation widgets with a proven React equivalent) is a
  credible retirement candidate *once Part 4 does its own file-by-file
  confirmation*, but the two UI-behavior gaps and the CSV bulk-export gap
  are real, unresolved product questions, not implementation details — see
  §7/§8. This audit does not by itself authorize deleting any specific
  file; it hands Part 4 an evidence base to work from.

---

## 2. Legacy GUI Inventory (`app/gui/**`)

108 files total, grouped by directory. Counts exclude `__init__.py`.

| Group | Files | Responsibility | Business logic? |
|---|---|---|---|
| `controllers/` | 3 (+`__init__`) | `analyze_controller.py`, `dashboard_controller.py`, `history_controller.py` — thin bridges from GUI to `app.services`/`app.database`. No logic of their own; each explicitly delegates. | No — delegation only |
| `pages/` | 10 (+`__init__`) | Top-level Qt pages: `dashboard_page.py`, `analyze_page.py`, `history_page.py`, `investigation_workspace.py`, `ioc_viewer_page.py`, `risk_dashboard_page.py`, `settings_page.py`, `threat_intel_page.py`, `component_showcase_page.py` | `threat_intel_page.py` contains indicator-type detection regexes (sha256/ipv4/domain/url) — presentation-adjacent parsing, not domain logic; others are pure Qt composition |
| `widgets/` | 31 (+`__init__`, `dashboard/__init__`) | Qt widgets: dashboard tiles, IOC detail/summary/details widgets, risk gauge/summary/explanation widgets, investigation header/metrics/statistics/timeline widgets, threat-intel widgets, sidebar/panel/section chrome | `risk_explanation_widget.py` and `ioc_summary_widget.py` render domain output (`RiskExplanation`, `ioc_type_significance()`) but compute nothing themselves |
| `components/` | 26 (+`__init__`s) | Generic Qt design-system primitives: buttons, cards, feedback (empty state, dropzone, skeleton, toast), layout, navigation, timeline | Pure presentation, Qt-specific, no business logic |
| `services/` | 3 | `analysis_service.py` (delegates to `app.analyzer`), `investigation_correlation_context.py` (formats `CorrelationReport` for display), `ioc_detail_context.py` (**compatibility shim only** — re-exports `app.services.ioc_detail_context`) | Display formatting only; canonical logic lives in `app.services.*` |
| `workers/` | 2 | `analysis_worker.py` — QThread wrapper around `AnalyzeController` | No — threading plumbing only |
| `models/` | 2 | `investigation_table_model.py`, `investigation_proxy_model.py` — Qt `QAbstractTableModel`/proxy for investigation history list | Presentation/sorting logic, Qt-specific |
| `events/` | 3 | `event_bus.py`, `application_state.py`, `application_events.py` — an in-process pub/sub + shared state object used only within the Qt widget tree | Qt-app-lifetime state, not domain logic |
| `design/` | 17 | `tokens/*` (colors, spacing, typography, radius, elevation, opacity, duration, easing), `theme/*` (palette, stylesheet builder, font factory, theme manager), plus empty `animations/`, `effects/`, `icons/` packages | Pure Qt styling constants — a parallel, Qt-specific token system to `frontend/src/styles/tokens` (React side is out of scope per frozen-area rules; these are not shared) |
| `styles/theme.py` | 1 | Legacy stylesheet string, appears superseded by `design/theme/stylesheet_builder.py` (needs Part 4 confirmation of which is live) | No |
| `utils/` | 2 | `csv_exporter.py` (bulk CSV export — **no modern equivalent**, see §7), `badge_mapping.py` (maps significance/severity strings to Qt badge styles) | `csv_exporter.py` has real behavior with no modern owner |
| root (`app.py`, `main_window.py`) | 2 | GUI bootstrap (`app.py:main()`) and the top-level `MainWindow` (page routing, export dispatch, shutdown) | `MainWindow._export_report`'s format-dispatch is the documented ancestor of the modern `export_report` command per `app/application/dto.py`'s own docstring — logic already ported |

---

## 3. Production Dependency Graph

Search performed across the entire project for `app.gui`, `from app.gui`,
`import app.gui`, dynamic imports, string references, entrypoints,
packaging, CLI, and config references.

**Result: zero production (non-test, non-comment) imports of `app.gui`
exist anywhere outside `app/gui` itself.**

| Location | Nature of the hit | Classification |
|---|---|---|
| `app/services/dashboard_aggregation.py`, `app/services/threat_intel_state.py`, `app/application/broker.py`, `app/application/dto.py`, `app/application/handlers.py` | Comments/docstrings *documenting the absence* of an `app.gui` import (architectural boundary notes) | Not a dependency — informational only |
| `tests/test_application_layer.py`, `tests/test_threat_intel_state.py` | Subprocess-isolated tests that **block** `app.gui`/`PySide6` imports and assert the application layer still imports cleanly | B — test-only, and its purpose is to *guarantee* the non-dependency Part 4 needs |
| `tests/test_threat_intel_state.py::TestGuiCompatibilityReExport` | Real `from app.gui.services import ioc_detail_context` | B — test-only; verifies the compat shim re-exports the same objects as the canonical module, i.e. protects safe retirement rather than blocking it |
| `tests/test_dashboard_services.py` | Commented-out reference to `DashboardController` (dead comment, not live code) | Not a dependency |
| `src-tauri/src/sidecar.rs` | Confirms the real sidecar entrypoint is `python -m app.api.entrypoint` | Confirms classification A does not include `app.gui` |
| `requirements.txt` | `PySide6>=6.11.2` still listed | Dependency exists only because `app/gui` and `tests/gui` still import PySide6 directly; becomes removable only once those are retired (see §9 Dependency note for Part 4) |
| No `pyproject.toml`/`setup.py`/packaging entrypoint references `app.gui` | — | C — confirms `app/gui` has no packaging/console-script entrypoint |
| `app/gui/app.py:main()` | Not imported by anything outside `app/gui` (checked: no root launcher script, no `app/main.py`/`app/cli.py` reference) | C — dead even as a standalone desktop-app entrypoint under the current launch configuration |

**Classification summary for all of `app/gui/**` as a whole: Class C
(dead/unreachable from production) for every production module, and Class
B (test-only) for the fact that `tests/gui/**` exercises it directly.**
No module falls into Class A (runtime-reachable) or Class D (unclear) —
the evidence is unambiguous on reachability. Reachability is not, by
itself, sufficient to retire a file — behavioral parity and test coverage
still have to be proven per module (§4–§6).

---

## 4. Legacy → React Equivalence Matrix

Evidence-based, from actual source in `frontend/src/**`, not filenames.

| Legacy behavior | Legacy source | Modern equivalent | Evidence | Classification |
|---|---|---|---|---|
| Investigation workspace shell, tabs, empty state | `pages/investigation_workspace.py` | `pages/investigation/InvestigationWorkspacePage.tsx` | Component + `InvestigationWorkspacePage.test.tsx` | PROVEN_EQUIVALENT |
| IOC summary per category | `widgets/ioc_summary_widget.py` | `pages/investigation/InvestigationOverviewIOC.tsx`, `InvestigationIocWorkspace.tsx` | Both normalize `iocsByType` from `investigationWorkspaceModel.ts`, tested | PROVEN_EQUIVALENT for counts/listing |
| IOC per-category "Risk Significance" badge | `widgets/ioc_summary_widget.py` (`ioc_type_significance()`) | — | `grep -i significance frontend/src` → zero non-test hits | **NO_EQUIVALENT** |
| Single-IOC detail view (type, value, TI state) | `widgets/ioc_detail_dialog.py`, `services/ioc_detail_context.py` (shim) | `InvestigationIocWorkspace.tsx`'s `IocDetail` panel | Reads `type`, `value`, `tiState` from normalized `IocRow` | PROVEN_EQUIVALENT (canonical logic already lives in `app.services.ioc_detail_context`, consumed by the API layer that feeds this component) |
| Threat-intel indicator type detection (sha256/ipv4/domain/url regex) | `pages/threat_intel_page.py` | Backend `ThreatIntelService`/API-side detection (per `app/application/dto.py` docstring, the frontend now goes through the `export_report`/lookup command layer, not a duplicated regex set) | `app/application/dto.py:421-435` documents the regex was ported to avoid duplication | PROVEN_EQUIVALENT |
| Threat-intel raw payload / provider detail | `widgets/threat_intelligence_details_dialog.py` | `pages/investigation/ProviderDetail.tsx` | Renders `rawThreatIntelligence` generically, no assumed schema | PROVEN_EQUIVALENT |
| Threat-intel summary widget, drill-down | `widgets/threat_intelligence_widget.py` | `pages/investigation/InvestigationThreatIntel.tsx`, `InvestigationOverviewThreatIntel.tsx` | Component + tests present | PROVEN_EQUIVALENT |
| Risk score/severity/confidence display | `widgets/risk_summary_widget.py`, `widgets/risk_gauge_widget.py` | `pages/investigation/InvestigationOverviewRisk.tsx` | Reuses `isInvestigationScored`/`severityTone`/`formatConfidence` | PROVEN_EQUIVALENT |
| "Why this risk?" narrative + contributing evidence + correlation drill-down | `widgets/risk_explanation_widget.py`, backed by `app/services/risk_explanation_service.py` | — | No component reads `RiskExplanationService` output; `InvestigationOverviewRisk.tsx` is score-only; `grep -i "narrative\|contributing\|explanation"` in frontend returns no relevant hits | **NO_EQUIVALENT** — backend logic exists, frontend consumer does not |
| Correlation display (relationship rows) | `services/investigation_correlation_context.py` | `pages/investigation/investigationCorrelationsModel.ts` + `InvestigationCorrelations.tsx` | Independently derives correlations from normalized data; own test suite | PROVEN_EQUIVALENT (parallel implementation, not a port of the GUI module, but behaviorally equivalent) |
| Dashboard KPIs / hero / queue / status widgets | `widgets/dashboard/*.py`, `controllers/dashboard_controller.py` | `pages/dashboard/*.tsx`, `dashboardViewModel.ts`, `useDashboard.ts` | Backend `DashboardStatisticsService`/`DashboardThreatService`/`SystemHealthService` are shared by both GUI controller and (per Phase 4H docs) the modern dashboard API | PROVEN_EQUIVALENT |
| Report export dispatch (HTML/PDF/JSON/Markdown) | `main_window.py:_export_report` | `pages/reports/useReportExport.ts`, `reportExportPath.ts` | Same 4 formats; `app/application/dto.py`'s `ExportReportRequest` docstring names `MainWindow._export_report` as its direct ancestor | PROVEN_EQUIVALENT |
| Bulk CSV export of investigation history | `utils/csv_exporter.py`, `pages/history_page.py` | — | No `csv` reference anywhere in `frontend/src`; `app/application/dto.py` explicitly documents this was deliberately excluded because it operates on a list, not one investigation | **LEGACY_ONLY** (documented, deliberate gap — not an oversight) |
| Investigation history list/search | `controllers/history_controller.py`, `models/investigation_table_model.py` | `pages/InvestigationsPage.tsx`, `investigationsViewModel.ts`, `useInvestigationsList.ts` | Full test coverage on modern side | PROVEN_EQUIVALENT |
| Analyze/run-analysis workflow | `pages/analyze_page.py`, `controllers/analyze_controller.py`, `workers/analysis_worker.py` | `pages/AnalyzePage.execution.test.tsx`, `analysisExecution.ts`, `useAnalysisExecution.ts` | Modern side drives the same `AnalysisService`/`analyze_report` path via commands/events instead of a QThread worker | PROVEN_EQUIVALENT (transport differs by design — SSE/event bus vs QThread signal — behavior does not) |
| Settings page | `pages/settings_page.py` | Not located under `frontend/src/pages` in this inventory | — | **UNCERTAIN** — needs Part 4 to confirm whether settings behavior was intentionally deferred or is simply out of this audit's file list; flagged, not classified further here |
| Qt design tokens/theme system | `design/tokens/*`, `design/theme/*`, `styles/theme.py` | `frontend/src/styles/tokens/*` | Independent, framework-specific token systems (Qt stylesheet strings vs CSS variables) — not meant to be equivalent line-for-line, just both implement "the design system" for their own framework | PROVEN_EQUIVALENT at the *system* level (frontend already has its own complete token architecture, which is frozen per the top-level instructions — no migration/reuse implied) |
| Generic Qt UI primitives (buttons, cards, feedback states) | `components/**` | `frontend/src/shared/components/*` | e.g. `FileDropzone.tsx` + tests mirror `feedback/file_dropzone.py`'s behavior (drag/drop, validation) | PROVEN_EQUIVALENT |

---

## 5. Legacy GUI Test-Suite Matrix (all 12 files in `tests/gui/`)

| Legacy test | Legacy behavior protected | Production module(s) under test | Modern equivalent | Modern test | Coverage | Safe to retire? |
|---|---|---|---|---|---|---|
| `test_application_state_selected_ioc.py` | Select/clear an IOC independent of current investigation; switching investigation clears selection | `app/gui/events/application_state.py` | Selection state lives in `InvestigationIocWorkspace.tsx`'s row-selection (React `useState`, not a shared `ApplicationState` singleton) | `InvestigationIocWorkspace.test.tsx` | PARTIAL — same *outcome* (selecting an IOC shows its detail, switching investigation resets it) but the *mechanism* differs (no global event-bus state object to test in React) | UNCERTAIN — behaviorally covered, but the exact invariant this suite pins (`ApplicationState` semantics) is Qt-specific plumbing with no 1:1 React analog to verify against |
| `test_export_continuity.py` | Export dispatches to HTML/PDF/JSON/Markdown exporters correctly per format; filename defaults per format | `app/gui/main_window.py` (`_export_report`) | `pages/reports/useReportExport.ts`, `reportExportPath.ts` | `useReportExport.test.tsx`, `reportExportPath.test.ts` | YES — same 4 formats, same underlying `ReportingService`, format→filename logic covered on the modern side | YES |
| `test_investigation_analyst_context.py` | Workspace empty state when no investigation selected; header card shows TI overview; IOC/TI widgets show honest empty states | `pages/investigation_workspace.py`, `widgets/investigation_header_card.py` (via `widgets/*`) | `InvestigationWorkspacePage.tsx`, `InvestigationHeaderCard.tsx`, `InvestigationOverviewThreatIntel.tsx`, `InvestigationOverviewIOC.tsx` | `InvestigationWorkspacePage.test.tsx`, `InvestigationHeaderCard.test.tsx`, `InvestigationOverviewThreatIntel.test.tsx`, `InvestigationOverviewIOC.test.tsx` | YES — each empty-state case has a direct modern test | YES |
| `test_investigation_workspace_risk_explanation.py` | `RiskExplanationWidget` narrative, contributing evidence, empty/error states, drill-downs to IOC/correlation | `widgets/risk_explanation_widget.py`, `pages/investigation_workspace.py` | None (see §4 — `InvestigationOverviewRisk.tsx` is score-only) | none | **NO** — no modern component renders narrative/contributing-evidence/drill-down | **NOT SAFE** |
| `test_investigation_workspace_threat_intel.py` | TI column show/hide by lookup presence; double-click enriched cell navigates; `select_hash()` routing | `widgets/ioc_details_widget.py`, `pages/investigation_workspace.py` | `InvestigationThreatIntel.tsx`, `InvestigationIocWorkspace.tsx` | `InvestigationThreatIntel.test.tsx`, `InvestigationIocWorkspace.test.tsx` | PARTIAL — column show/hide and enrichment-state rendering covered; the specific "double-click cell → navigate to TI tab and select row" interaction was not confirmed present in the modern test files reviewed | UNCERTAIN — needs a targeted look at whether cross-tab navigation-on-click exists in the modern router/tab model before retiring |
| `test_investigation_workspace_url.py` | Unified TI lookup indexes hash/IP/domain/URL; IOC selection routes enrichable types with TI attached | `pages/investigation_workspace.py`, `widgets/ioc_details_widget.py` | `investigationWorkspaceModel.ts`, `InvestigationIocWorkspace.tsx` | `investigationWorkspaceModel.test.ts`, `InvestigationIocWorkspace.test.tsx` | YES — normalization layer already groups by all real IOC categories including URL | YES |
| `test_ioc_detail_experience.py` | "View Details" enable/disable by selection; emits type+value; dialog renders TI states; drill-down reuse | `widgets/ioc_details_widget.py`, `widgets/ioc_detail_dialog.py`, `pages/investigation_workspace.py` | `InvestigationIocWorkspace.tsx`'s `IocDetail` panel | `InvestigationIocWorkspace.test.tsx` | PARTIAL — selection-driven detail display is covered; the dialog-specific "only offer view-full-record when enriched" conditional was not confirmed 1:1 in the modern panel | UNCERTAIN |
| `test_ioc_summary_risk_relevance.py` | Per-category "Risk Significance" badge; TI coverage label vs honest "unknown"/"Not Supported" | `widgets/ioc_summary_widget.py` | `InvestigationOverviewIOC.tsx` covers the honest-label behavior; **no component covers the Significance badge** (§4) | `InvestigationOverviewIOC.test.tsx` (partial) | PARTIAL — TI-coverage-label honesty is covered; significance badge is **not** | **NOT SAFE** (mixed suite — do not retire wholesale; the honesty-label assertions may be redundant with modern tests, but the significance-badge assertions protect behavior with no modern equivalent) |
| `test_ioc_summary_url.py` | URL/IPv4/domain/SHA256 all recognized as enrichable; unsupported types stay "Not Supported"; URL enriched state shown | `widgets/ioc_summary_widget.py` | `InvestigationOverviewIOC.tsx`, `InvestigationIocWorkspace.tsx` | Respective test files | YES — enrichable-type set and honest-label behavior both covered | YES |
| `test_ioc_viewer_page_defect_fix.py` | Regression pin for an `investigation.id` vs `investigation_id` attribute-name bug in `IOCViewerPage.refresh()` | `pages/ioc_viewer_page.py` | N/A — this is a Qt-specific defect in Qt-specific code; the modern frontend never had this bug class (TypeScript's typed `investigationId` field, not a Python attribute-name typo) | — | N/A — the *class* of defect this test protects against cannot recur in the modern stack | YES, but retire *because the risk class no longer applies*, not because a modern test proves the same behavior — document this distinction, don't just delete silently |
| `test_phase3e_acceptance.py` | End-to-end: non-hash-only malicious findings are not lost through scoring/correlation/risk-explanation/GUI/every export format | `app/scoring`, `app/services/correlation_service.py`, `risk_explanation_service.py`, GUI workspace, `app/reporting/*` | Backend portions (`tests/test_*` for scoring/correlation/risk-explanation) are re-verified independently of the GUI at the backend layer; the GUI-specific assertion (`test_d_gui_workspace_ti_section_displays_non_hash_records`) has no direct modern-frontend counterpart confirmed | Backend-side coverage exists (`tests/` suite, 780 passing, includes scoring/correlation/risk-explanation modules) | PARTIAL — the non-GUI 3/4 of this suite's assertions are backed by backend tests independent of `app/gui`; the GUI-display assertion is not proven equivalent on the frontend | UNCERTAIN for the GUI-specific assertion only; the backend-facing assertions in this file are redundant with existing backend tests and could be trimmed, but the file as a whole should not be deleted until the GUI-display assertion has a frontend counterpart |
| `test_threat_intel_page_url.py` | Indicator-type regex detection (URL/IP/domain/SHA256); worker construction without real QThread/network calls; result-rendering callbacks for each state (found/not-found/no-key/error) | `pages/threat_intel_page.py` | Indicator detection: ported per `app/application/dto.py:421-435`; result-rendering states: `InvestigationThreatIntel.tsx`/`ProviderDetail.tsx` render found/error/empty states | Respective test files | PARTIAL — detection logic is proven ported at the backend/DTO layer; the specific worker-construction and per-state-callback assertions are Qt-threading-specific and have no direct 1:1 frontend test, though the *rendered outcomes* are covered | UNCERTAIN for the Qt-threading-specific assertions; YES for the detection-logic assertions (already proven ported) |

**Summary:** 4 of 12 suites are cleanly **YES** (safe to retire once Part 4
independently re-confirms). 1 suite (`test_ioc_viewer_page_defect_fix.py`)
is a **YES with a documented rationale difference** (defect class doesn't
exist in the new stack, not "same behavior, different test"). 2 suites are
**NOT SAFE** (`risk_explanation`, and the significance-badge half of
`ioc_summary_risk_relevance`). The remaining 5 are **UNCERTAIN**, each for
a specific, named reason above — not a blanket "needs more time."

---

## 6. Business-Logic Audit

Independent search across all of `app/gui/**` for parsing, scoring,
normalization, domain transformation, validation, persistence, API calls,
threat-intel logic, investigation logic, report generation, and
state-machine logic.

| Finding | Location | Verdict |
|---|---|---|
| `ioc_detail_context` | `app/gui/services/ioc_detail_context.py` | **Confirmed shim only** — re-exports `TI_STATE_*` constants and `build_investigation_threat_intel_overview`/`build_ioc_detail_context` from `app.services.ioc_detail_context` verbatim (`from app.services.ioc_detail_context import (...)  # noqa: F401`). No independent definitions. Canonical owner: `app/services/ioc_detail_context.py`. |
| `ioc_significance` | No `app/gui/services/ioc_significance.py` exists | **Never duplicated in `app/gui`** — `app/gui/widgets/ioc_summary_widget.py` imports `ioc_type_significance` directly from `app.services.ioc_significance`; `app/gui/utils/badge_mapping.py` only maps significance *strings* to Qt badge *styles* (presentation, not the significance computation itself). Canonical owner: `app/services/ioc_significance.py`. |
| Indicator-type regex detection | `app/gui/pages/threat_intel_page.py` | Real parsing logic, but `app/application/dto.py` (lines ~421–435) documents this was already extracted/ported to the application layer to avoid duplication — the GUI's copy is the historical original, not the sole owner. |
| CSV export | `app/gui/utils/csv_exporter.py` | Real, self-contained business logic (writes investigations to CSV) with **no duplicate elsewhere** and **no modern port** — this is genuine legacy-only behavior, not presentation. See §7. |
| Correlation display formatting | `app/gui/services/investigation_correlation_context.py` | Formats `CorrelationReport` for display; the actual correlation *computation* is `app.services.correlation_service.CorrelationService`, imported (not reimplemented) here. Formatting-only. |
| `MainWindow._export_report` format dispatch | `app/gui/main_window.py` | `app/application/dto.py`'s own docstring names this as the direct ancestor of the modern `export_report` command, i.e. already treated as ported/superseded by the application layer's own authors. |
| Everything else scanned (`controllers/`, `workers/`, `models/`, `events/`, `components/`, `design/`) | — | No parsing/scoring/normalization/validation/persistence/API-call logic found; these are Qt presentation, threading, and state-plumbing only. |

**Conclusion:** the two modules named in the original Phase 4O framing
(`ioc_detail_context`, `ioc_significance`) are confirmed already
externalized with zero duplication risk. One additional real business-logic
module (`csv_exporter.py`) was found with no modern owner — this needs a
product decision, not a code migration, before Part 4 can act on it (see
§7).

---

## 7. Safe-Retirement Candidates

Presented as **candidate groups** pending Part 4's own file-by-file
re-confirmation immediately before deletion (per the master instructions:
"Only remove modules that P3 proved are... [criteria]... after those
checks pass" — this audit provides the evidence, Part 4 still re-checks
at the moment of deletion).

- **Qt design-system primitives with proven React equivalents:**
  `components/buttons/*`, `components/cards/*`, `components/feedback/*`,
  `components/layout/*`, `components/navigation/*`, `components/timeline/*`,
  `components/base_widget.py` — no production import, framework-specific,
  React side already has its own complete component set.
- **Qt-specific design tokens/theme:** `design/tokens/*`, `design/theme/*`,
  `styles/theme.py` — no production import, and per frozen-area rules the
  frontend's own token system is untouched/unaffected by removing these.
- **Controllers/services/workers that are pure delegation:**
  `controllers/analyze_controller.py`, `controllers/dashboard_controller.py`,
  `controllers/history_controller.py`, `services/analysis_service.py`,
  `workers/analysis_worker.py` — no independent logic, backing services
  (`app.services.*`, `app.database.*`) already consumed directly by the
  modern stack.
- **Pages/widgets with a PROVEN_EQUIVALENT row in §4** and a **YES row in
  §5** for their corresponding test: `history_page.py` +
  `test_export_continuity.py`'s non-CSV assertions,
  `ioc_viewer_page.py` (with the documented defect-class caveat above),
  `investigation_table_model.py`/`investigation_proxy_model.py`.
- **Dead/orphaned entrypoint:** `app/gui/app.py`, `app/gui/main_window.py`
  — confirmed unreachable from any current launcher (§3), and their
  export-dispatch/routing logic is confirmed already ported (§4, §6).

## 8. Not-Safe-to-Retire Candidates

- **`app/gui/widgets/risk_explanation_widget.py`** and its test
  `test_investigation_workspace_risk_explanation.py` — no frontend
  consumer of `RiskExplanationService` exists yet. Retiring this leaves a
  real analyst-facing feature (the narrative "why this risk" explanation)
  with zero UI anywhere, legacy or modern.
- **The significance-badge assertions in
  `test_ioc_summary_risk_relevance.py`** and the corresponding rendering
  in `widgets/ioc_summary_widget.py` — no frontend equivalent exists for
  the per-category Risk Significance badge.
- **`app/gui/utils/csv_exporter.py`** and its call site in
  `pages/history_page.py` — real behavior, no modern equivalent, and
  already flagged by the project's own architecture docs as a deliberate
  gap rather than an oversight. This is a product decision (is bulk CSV
  export still a required feature?), not a code question.
- **`PySide6` dependency in `requirements.txt`** — remains required as
  long as any of the above remain, and as long as `tests/gui/**` exists at
  all.

## 9. Needs-Follow-Up Candidates

- **`pages/settings_page.py`** — no corresponding page was found under
  `frontend/src/pages`; needs a direct answer on whether settings
  behavior is out of scope for this audit, deferred to a later phase, or
  genuinely missing.
- **`pages/component_showcase_page.py`** — appears to be an internal
  dev/QA tool for browsing the Qt design system rather than end-user
  functionality; needs a decision on whether it needs a modern equivalent
  or can simply be dropped as tooling.
- **The five UNCERTAIN test suites in §5** — each needs the specific,
  narrow check named in that row (e.g., "does the modern tab model support
  click-to-navigate from an enriched TI cell") before a retire/keep call
  can be made; none of them are uncertain for lack of investigation time,
  each has a concrete, named gap in the evidence.
- **`styles/theme.py` vs `design/theme/stylesheet_builder.py`** — both
  appear to build Qt stylesheets; Part 4 should confirm which one
  `MainWindow`/`ApplicationShell` actually uses at runtime before treating
  the other as dead weight.

---

## 10. Test/Regression Results (this session, fresh)

```
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/gui -q     → 142 passed
python3 -m pytest tests/ --ignore=tests/gui -q                → 780 passed
cd frontend && npx vitest run                                  → 965 passed (70 test files)
cd frontend && npx tsc --noEmit                                → 0 errors
cd frontend && npm run build                                   → success (193 modules)
cargo check / cargo test (sidecar-core, src-tauri)              → ENVIRONMENT-BLOCKED (no cargo/rustc in this container)
```

Note on the GUI test count: a prior addendum in
`docs/architecture/IMPLEMENTATION_STATUS.md` reported 154 passing under
`QT_QPA_PLATFORM=offscreen pytest tests/gui`. This session's fresh run
gets **142**. This has not been root-caused in this audit-only part — no
GUI files were touched, so the discrepancy is not attributable to any
change made here. Flagging per the instruction not to trust historical
counts without rerunning them; Part 4 should investigate this
discrepancy (likely candidates: environment/dependency version drift, or
that addendum's count including/excluding something differently) before
relying on either number.

## 11. Frozen-Area Verification

No files under any frozen area were created, modified, or deleted this
session:

- Dashboard (Phase 4H): unchanged
- Reporting (Phase 4L): unchanged
- Threat Intel architecture: unchanged
- Integration (Phase 4N): unchanged
- Investigation Workspace: unchanged
- Analysis workflow: unchanged
- Tauri/sidecar source: unchanged
- database schema: unchanged
- command/event contracts: unchanged
- frontend design system / React app shell: unchanged

This session's only filesystem actions were: installing Python packages
(`PySide6`, `requirements.txt`) and `npm` packages into the (gitignored,
non-source) dependency caches, running test/build commands, and writing
this one new document. No `app/gui`, `tests/gui`, `frontend/src`, backend
source, Rust source, or database/contract file was edited.

## 12. Recommended Next Steps for Part 4

1. **Resolve the two open UI gaps as product decisions first**, not code
   decisions: is the "Why this risk?" narrative still required in the
   modern app, and is the per-category significance badge still required?
   If yes to either, Part 4 should scope a small frontend task to wire the
   existing backend service before touching `risk_explanation_widget.py`
   or the significance half of `ioc_summary_widget.py`. If no, document
   that decision explicitly — do not infer it.
2. **Decide on `csv_exporter.py`/bulk CSV export** — same as above, this
   is a feature-continuity question the codebase cannot answer for itself.
3. For the **YES group** in §5/§7, Part 4 re-confirms each file
   individually immediately before deletion (no new import appeared,
   modern test still passes) and removes production file + test together.
4. For the **UNCERTAIN group**, resolve each named gap with a targeted
   check (the specific question is already written per-row in §5) before
   deciding.
5. Re-run the full regression suite (§10) after each batch of removals,
   not only at the end, and re-investigate the 142-vs-154 GUI test-count
   discrepancy independent of the retirement work, since it predates this
   audit.
6. Only after the above, search for stale `app.gui` residue project-wide
   per the master instructions' "Legacy Residue Search" step — this audit
   already found zero live production references (§3), so that pass
   should be confirmatory, not investigative.

## 13. Explicit Statement

**No files under `app/gui/**` or `tests/gui/**` were deleted, renamed, or
modified as part of Phase 4O Part 3.** This part produced one new file:
`docs/phase4/PHASE4O_PART3_LEGACY_GUI_PARITY_AUDIT.md`.
