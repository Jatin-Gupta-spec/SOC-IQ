# Phase 4B — Query Inventory

**Status:** Phase 4B (Source-Verified). Separates read operations from the commands in
`PHASE4B_COMMAND_INVENTORY.md`, so that a future React frontend consumes queries rather than
re-deriving this logic itself.

Classification: `domain query` (pure computation, no I/O) · `repository query` (raw
persistence read) · `application query` (orchestrates repository + computation for one
use case) · `presentation-only transformation` (reshapes an already-fetched result for
display, must not be re-implemented in React as if it were a query).

## Investigation queries

| Query | Current owner | Classification | Notes |
|---|---|---|---|
| Get investigation by ID | `InvestigationService.get_by_id` → `InvestigationRepository.get_by_id` | repository query | Also exposed via `HistoryController.get_investigation` |
| List all investigations | `InvestigationService.list_all` → `InvestigationRepository.list_all` | repository query | No caller found in the files read this pass — flag as possibly unused, or used by a page outside scope |
| Find by report name | `InvestigationService.find_by_report_name` | repository query | Used both by `analyze_report` (duplicate check) and `HistoryController.search_by_report_name` |
| Check existence by report name | `InvestigationService.investigation_exists` → `exists_by_report_name` | repository query | Used by `analyze_report` |
| Get latest by report name | `InvestigationService.get_latest_by_report_name` | **application query** | Not a raw repository call — applies explicit `max()` ordering logic in the service layer rather than trusting repository order (see Logic Preservation Matrix, deliberate design choice) |
| Find by severity | `InvestigationService.find_by_severity` | repository query | No caller found in files read this pass |
| Find recent (limit N) | `InvestigationService.find_recent` | repository query | Used by `HistoryController.get_recent_investigations` and `DashboardInvestigationService.get_recent` |
| Count all | `InvestigationService.count` | repository query | Used by `HistoryController.get_total_investigations` |

## Dashboard queries

| Query | Current owner | Classification | Notes |
|---|---|---|---|
| Dashboard summary | `DashboardStatisticsService.get_summary` | application query | Aggregates over `InvestigationService` |
| Threat status + badge | `DashboardThreatService.get_threat_status` | application query | Returns `(str, BadgeType)` — `BadgeType` is a UI-adjacent enum (`app/services/models.py`) that should become a plain status string/enum at the API boundary, with badge *color* mapping left to the frontend (presentation) |
| Latest investigation (dashboard view) | `DashboardInvestigationService.get_latest` | application query | Thin wrapper — worth confirming at Phase 4D whether this duplicates `InvestigationService.get_latest_by_report_name` in intent (different signature: no report-name filter) |
| Recent investigations (dashboard view) | `DashboardInvestigationService.get_recent` | application query | |
| Dashboard timeline | `DashboardTimelineService.get_timeline` | application query, **with an embedded presentation-only transformation** | `_icon_for_severity` maps severity → icon name inside the same class; should be split per Controller/Service Inventory |
| IOC distribution | `DashboardIOCDistributionService.get_distribution` | application query | Uses `collections.Counter` — pure aggregation, no external calls |
| Threat feed | `DashboardThreatFeedService.get_feed` | application query | |
| System status | `SystemHealthService.get_status` | application query | Touches multiple subsystems (DB, VirusTotal config, repository, analysis engine) in one call — a candidate for splitting into 4 separate health-check queries in the target API, since a React health widget will likely want to poll/display them independently |

## IOC / risk / correlation queries

| Query | Current owner | Classification | Notes |
|---|---|---|---|
| IOC significance / weight / title for a type | `app.services.ioc_significance` (`ioc_type_significance`, `ioc_type_title`, `ioc_type_weight`) | domain query (wraps `RiskScoringEngine`, no I/O) | PD-08-P3: this note previously read `app.gui.utils.ioc_significance` and flagged the module as mis-located under `app/gui/utils/`; as of this checkpoint the module already lives under `app/services/`, has zero Qt/PySide6 dependency, and is consumed by both `RiskExplanationService` (PD-08-P1) and `GetIocsCommandHandler` (PD-08-P3) — the relocation this note called for has already happened, and the "architectural violation" note no longer applies |
| Investigation threat-intel overview (per-IOC) | `app.services.ioc_detail_context.build_investigation_threat_intel_overview` | application query | PD-08-P3: this note previously read `app.gui.services.ioc_detail_context` and flagged it as mis-located alongside the row above; as of this checkpoint it also already lives under `app/services/` |
| Risk explanation | `RiskExplanationService.explain` | application query | Read-only, deterministic given the same `Investigation` + optional `CorrelationReport` |
| Correlation report | `CorrelationService.correlate` | domain query | Pure function of an `Investigation`, no I/O, no mutation |
| Correlation context (presentation shape) | `app.gui.services.investigation_correlation_context` | presentation-only transformation | Reshapes `CorrelationReport` for display; must not be re-derived independently in React — React should request the same `CorrelationReport` and apply its own view logic, or the API should expose this shape directly as a documented DTO, not both |

## History queries

| Query | Current owner | Classification | Notes |
|---|---|---|---|
| Recent investigations (history view) | `HistoryController.get_recent_investigations` | application query (thin wrapper over the investigation query of the same name) | |
| Search by report name | `HistoryController.search_by_report_name` | application query | Includes blank-input short-circuit logic — must be preserved, not just the repository call |
| Total investigation count | `HistoryController.get_total_investigations` | application query | |

## Threat-intelligence queries

Not independently verified this pass — `app/threat_intel/service.py` and
`app/threat_intel/virustotal.py` are outside the stated Phase 4B file list
(`app/services/`, `app/gui/controllers/`, `app/gui/services/`). `SystemHealthService.
_virustotal_status` implies at least one query exists ("is a VirusTotal key configured /
is the service reachable"), but its exact shape is a **remaining unknown** — see
Architectural Findings.

## Settings queries

Not independently verified this pass — `app/settings/service.py` is outside the stated file
list. `SystemHealthService` clearly reads settings (constructor takes `SettingsService`),
confirming at least a "get current settings" query exists, but its exact surface is a
**remaining unknown**.

## Reporting queries

Not independently verified this pass — `app/reporting/service.py` is outside the stated file
list, despite being imported from `app/gui/*`. **Remaining unknown**, flagged for follow-up
before this inventory can be called complete (see Command Inventory's note on
`export_report`).

## Why this split matters for the frontend boundary

Two entries above are explicitly marked "presentation-only transformation": the dashboard
timeline's severity→icon mapping, and the correlation-context reshaping. Both currently live
next to genuine application queries in the same file/module. Carrying that pattern forward
into the API layer would let React re-implement business classification logic locally (e.g.
its own severity→icon rules drifting from the backend's), which is exactly the failure mode
`07-state-architecture.md` and this phase's brief (§11: "This will later prevent React from
becoming a second business-logic layer") both call out. Recommendation for Phase 4D: the API
returns raw domain/application query results (severity as a string, not an icon name); icon
mapping is a frontend design-system concern, not a backend query.
