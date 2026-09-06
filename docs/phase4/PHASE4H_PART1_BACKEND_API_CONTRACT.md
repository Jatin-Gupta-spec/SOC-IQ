# Phase 4H Part 1 — Dashboard Backend/API Contract

**Status:** Backend/API contract implemented and tested. Frontend Dashboard
remains on mock data (Part 2 scope) — nothing in this part wires it to real
data.
**Scope:** Per the Master Plan §26 migration table, "4H = real dashboard
data." This part implements only the backend/API contract that exposes
that data; it does not touch the Dashboard frontend.

---

## 1. Audit performed before any change

Source-inspected directly (no pre-existing "Phase 4H readiness audit"
document was present in this checkpoint to consume):

| Item | Finding |
|---|---|
| `app/services/dashboard_*.py` (6 services) | Real, correct business logic, but return GUI-shaped values: `DashboardStatisticsService.get_summary()` returns `dict[str, str]`; `DashboardThreatService.get_threat_status()` returns a `BadgeType` enum member; `DashboardTimelineService.get_timeline()` returns emoji-bearing `TimelineEvent` objects. None of these are JSON-safe or presentation-neutral as-is. |
| `app/gui/controllers/dashboard_controller.py` | The one existing consumer of all six dashboard services (PySide6 GUI). Not touched — its behavior must be identical after this part. |
| `app/application/{dto,handlers,responses,errors}.py` | Established, consistent pattern: frozen-dataclass request DTOs with `__post_init__` validation, explicit response-DTO mapping (never a raw domain object crossing the boundary), a `dispatch()` function with one exception-translation boundary, and a `COMMAND_HANDLERS` dict. Followed exactly for the new command. |
| `Investigation.status` (`app/database/models.py`) | Always `"COMPLETED"` — set once by the dataclass default, never reassigned anywhere in `app/analyzer.py`, `app/database/repository.py`, or any GUI controller. The frontend mock's `open`/`in_progress`/`closed` "investigation workload" vocabulary (`frontend/src/mock/investigations.ts`, consumed by `dashboardViewModel.ts::summarizeInvestigationWorkload`) has **no backend equivalent today** — it is a UI-only concept. |
| `Investigation.threat_intelligence["coverage"]` (`app/services/threat_intel_state.py`) | Already persists `{"requested": int, "succeeded": int}` for every investigation that underwent enrichment — the exact numbers `ThreatIntelService.enrich_results()` produced. This means Threat Intel Coverage % **can** be honestly derived (see §3), contrary to the task brief's assumption that it might need to stay deferred. |
| `frontend/src/shared/api/types.ts` | Self-documented as "mechanical transcription" of the Python DTOs/handlers, one command name per entry. Extended additively (11th entry) rather than restructured. |

## 2. What was implemented

### New command: `get_dashboard_summary`

- **Request:** `GetDashboardSummaryRequest` (`app/application/dto.py`) — no
  fields, mirroring `ListInvestigationsRequest`'s own "explicit empty type"
  reasoning so a future parameter is additive.
- **Handler:** `GetDashboardSummaryCommandHandler`
  (`app/application/handlers.py`) — fetches `InvestigationService
  .list_all()` exactly once, derives every aggregate figure from that one
  in-memory list, and makes exactly one additional call
  (`DashboardInvestigationService.get_recent()`) for
  `recent_investigations`. No per-investigation follow-up query — see §4
  (No N+1) below.
- **Response DTO:** `DashboardSummaryDTO` (`app/application/dto.py`).

### DTO shape

```
DashboardSummaryDTO
├── metrics: DashboardMetricsDTO
│   ├── total_reports: int
│   ├── total_iocs: int
│   ├── high_risk_count: int
│   └── threat_intel_coverage_percent: float | None
├── investigation_status_counts: dict[str, int]   # keyed by the REAL Investigation.status value
├── risk_distribution: dict[str, int]             # keyed by severity
├── ioc_distribution: dict[str, int]              # keyed by ioc_type
└── recent_investigations: list[InvestigationSummaryDTO]   # reused unchanged
```

Wire example (non-empty database):

```json
{
  "success": true,
  "data": {
    "metrics": {
      "total_reports": 12,
      "total_iocs": 340,
      "high_risk_count": 3,
      "threat_intel_coverage_percent": 87.5
    },
    "investigation_status_counts": { "COMPLETED": 12 },
    "risk_distribution": { "LOW": 6, "MEDIUM": 3, "HIGH": 2, "CRITICAL": 1 },
    "ioc_distribution": { "ipv4": 120, "domains": 80, "sha256": 140 },
    "recent_investigations": [ /* InvestigationSummaryDTO[], same shape get_investigation already returns */ ]
  },
  "error": null
}
```

### New shared module: `app/services/dashboard_aggregation.py`

Pure, side-effect-free functions over an already-fetched
`list[Investigation]` — no I/O, no Qt, no domain-service calls:

- `compute_ioc_distribution` — extracted unchanged from
  `DashboardIOCDistributionService.get_distribution`.
- `compute_dashboard_metrics` — extracted unchanged (as typed `int`s
  instead of strings) from `DashboardStatisticsService.get_summary`.
- `compute_severity_distribution` — new; full per-severity breakdown
  (the existing statistics service only ever collapsed HIGH+CRITICAL
  into one `high_risk` count).
- `compute_status_counts` — new; groups by the real `status` field
  (see §3.2).
- `compute_threat_intel_coverage_percent` — new; see §3.1.

`DashboardIOCDistributionService` and `DashboardStatisticsService` were
refactored to delegate to this module. **Their public method
signatures, return types, and return values are unchanged** — this is
purely "extract the existing calculation so it has one implementation
instead of two," per the task brief's own guidance. The GUI controller
that consumes them (`app/gui/controllers/dashboard_controller.py`) was
not modified and needed no changes; existing/added tests confirm
identical output.

## 3. Two decisions the task brief specifically asked to resolve carefully

### 3.1 Threat Intel Coverage %

**Not deferred.** Source inspection found this genuinely, honestly
derivable: every investigation's persisted `threat_intelligence["coverage"]`
dict already carries `requested`/`succeeded` integer counts (the same
counts `ThreatIntelService.enrich_results()` produced and
`app.services.threat_intel_state` already reuses elsewhere in the
application layer). `compute_threat_intel_coverage_percent` sums those
counts across every investigation and computes a percentage —
introducing no new semantics, only an aggregation of numbers that
already exist.

- Returns `None` (never `0.0`) when zero lookups were ever requested
  across the whole database — an empty DB, or one where TI was never
  run. `0.0` is reserved for the real "every request failed" case, so
  the two are never conflated.
- Malformed/non-integer coverage data for a given investigation is
  skipped for that investigation rather than guessed at or crashed on.

### 3.2 "Investigation workload"

The frontend mock's `open` / `in_progress` / `closed` status vocabulary
does not exist in the persisted domain model — `Investigation.status`
is always `"COMPLETED"` (see §1). Rather than invent that vocabulary
server-side (which the task brief explicitly prohibits — "NEVER
fabricate values"), `investigation_status_counts` groups investigations
by whatever status value is **actually persisted**. Today, in practice,
this will always render as a single `{"COMPLETED": N}` bucket. The
shape is dict-based (not hardcoded to three keys) specifically so it
can show more buckets the day a real workflow-status concept is
introduced, without a contract change — but no such concept is invented
here.

This is flagged as an **open decision** in the final report: a real
"investigation workload" widget (distinct from a raw count-by-status
table) most likely needs an actual product decision about what
workflow states an investigation can be in, which is out of scope for
a backend-contract phase.

## 4. No N+1 frontend design

`GetDashboardSummaryCommandHandler.handle()` performs exactly two
repository-level calls total, regardless of investigation count:

1. `InvestigationService.list_all()` — once, for every aggregate figure
   (`metrics`, `investigation_status_counts`, `risk_distribution`,
   `ioc_distribution`).
2. `DashboardInvestigationService.get_recent()` — once, for
   `recent_investigations` (itself a single `find_recent()` call).

No per-investigation IOC/TI lookup is performed by this handler; all
IOC/TI data needed for the aggregates is already loaded on each
`Investigation` domain object returned by `list_all()`.

## 5. What was deliberately left out (and why)

- **Timeline data.** The Phase 4H brief itself flags Timeline as an
  unresolved product decision. Including it in this DTO would lock a
  wire shape in before that decision is made, so it is absent —
  `DashboardTimelineService` was not touched or wrapped.
- **Operational status.** Already served live via
  `useSidecarStatus()`/`projectSidecarStatusView()` (a real-time Tauri
  IPC channel, not a `POST /commands/{name}` round trip). Duplicating a
  point-in-time copy into this aggregate snapshot would create a
  second, potentially-stale source of truth for the same fact, so it
  is intentionally not part of this DTO.
- **`DashboardThreatService`'s `BadgeType`-based overall threat level**
  (`"NORMAL"` / `"ELEVATED"` / `"CRITICAL ALERT"`). Not part of the six
  required data categories in the task brief, and `BadgeType` is
  exactly the kind of Qt-adjacent enum this phase must not leak into
  the API layer. Left out of scope for this part rather than
  reinterpreted into a new string vocabulary without a product
  decision backing it.
- **`DashboardStatisticsService`'s static `"database": "Connected"`
  field.** Unconditionally hardcoded regardless of actual database
  state (confirmed by source inspection — it is a literal, not a
  check). Carrying it into `DashboardMetricsDTO` would be exactly the
  "fabricated value" this phase's brief prohibits, so it is excluded.

## 6. Command naming

`get_dashboard_summary` was used as-is — inspection of
`app/application/handlers.py::COMMAND_HANDLERS` and
`docs/contracts/command-model.md` found no existing or reserved name
that conflicts with it, and it follows the established `get_<noun>`
convention every other read command in this codebase already uses.

## 7. Frontend

**No frontend production component was modified.**
`frontend/src/shared/api/types.ts` — the shared, self-documented
type-contract file that already mirrors all ten existing commands
1:1 — was extended additively with an eleventh entry
(`get_dashboard_summary`, `DashboardMetrics`, `DashboardSummaryResult`,
`GetDashboardSummaryPayload`) so Part 2 has a compiled, type-checked
contract to consume. `DashboardPage.tsx` and all Dashboard components
remain on `mock/dashboard.ts`, unchanged; `useDashboard()` was not
created.

## 8. Tests added

- `tests/test_dashboard_aggregation.py` (24 tests, new) — every pure
  function in `dashboard_aggregation.py`: empty input, multi-investigation
  aggregation, case-insensitivity, malformed/missing data, the
  `None`-vs-`0.0` TI-coverage distinction, and an explicit regression
  guard that `compute_status_counts` never fabricates
  open/in_progress/closed buckets.
- `tests/test_dashboard_services.py` (+6 tests) — confirms
  `DashboardIOCDistributionService`/`DashboardStatisticsService`'s
  public behavior is byte-for-byte unchanged after delegating to the
  new shared module (including that `get_summary()` still returns
  `dict[str, str]`, not `dict[str, int]`).
- `tests/test_application_layer.py` (+7 tests,
  `GetDashboardSummaryCommandHandlerTests`) — empty database, multi-
  investigation aggregation (including the coverage-percent math),
  `InvestigationSummaryDTO` shape/omission guarantees on
  `recent_investigations`, the configurable `recent_limit`, a full
  `json.dumps` round-trip (the GUI/Qt-leak/JSON-serializability
  check), dispatch-by-name, and payload-validation rejection of
  unexpected fields.
- `tests/test_api_layer.py` (+2 tests) — real HTTP round trip through
  `fastapi.testclient.TestClient` against the real (uncontrolled)
  database, plus payload-validation rejection at the transport layer.

No existing test was deleted, weakened, or had an assertion removed.

## 9. Verification

Backend (real `pytest`, real `fastapi`/`httpx`/`uvicorn` — this
sandbox does have PyPI access; installed and verified rather than
assumed):

```
$ python -m pytest tests/ --ignore=tests/gui -q
717 passed, 1 warning in 4.23s
```

(679 passed before this part's changes; +38 new/added tests, 0
removed, 0 weakened.)

GUI tests run separately, per instructions:

```
$ python -m pytest tests/gui -q
ImportError: No module named 'PySide6'
```

PySide6 is not installed in this sandbox and could not be installed
(large binary wheel; not attempted against the constrained
allowed-domains network policy this environment enforces for
`pip`/`bash_tool`). This is a genuine environment gap, reported as-is
rather than skipped silently — no GUI code was touched in this part,
so this is a pre-existing environment limitation, not a regression
introduced here.

Frontend (real TypeScript compiler — `npm install` + `npx tsc
--noEmit`, not a hand-written stub):

```
$ npx tsc --noEmit
(no output — 0 errors)
```

`node_modules/` was removed after verification (it was not present in
the original checkpoint).

## 10. Backward compatibility

All nine pre-existing commands
(`get_investigation`, `get_iocs`, `get_threat_intelligence`,
`list_investigations`, `search_investigations`, `enrich_ioc`,
`analyze_report`, `save_settings`, `export_report`,
`delete_investigation`) are unmodified — confirmed both by inspection
(no line inside any of their handler classes changed) and by the full
regression suite passing unchanged.

## 11. Scope audit

Confirmed via a full directory diff against the original checkpoint:

**Modified (5 files):**
- `app/application/dto.py`
- `app/application/handlers.py`
- `app/services/dashboard_ioc_distribution_service.py`
- `app/services/dashboard_statistics_service.py`
- `frontend/src/shared/api/types.ts`

**Created (3 files):**
- `app/services/dashboard_aggregation.py`
- `tests/test_dashboard_aggregation.py`
- `docs/phase4/PHASE4H_PART1_BACKEND_API_CONTRACT.md` (this file)

**Test files modified (additive only, 3 files):**
- `tests/test_dashboard_services.py`
- `tests/test_application_layer.py`
- `tests/test_api_layer.py`

**Deleted:** none.

**Confirmed untouched:** Investigation Workspace, Threat Intelligence
page, typed verdicts, Analyze workflow, sidecar lifecycle (Rust/Tauri),
`src-tauri/`, `sidecar-core/`, database schema, all Dashboard frontend
production components (`DashboardPage.tsx`,
`DashboardMetrics`, `DashboardInvestigationOverview`,
`DashboardRecentInvestigations`, `DashboardRiskOverview`,
`DashboardQuickActions`, `DashboardOperationalStatus`), Dashboard
CSS/layout, `useDashboard()` (not created), Timeline UI (not created),
`dashboardViewModel.ts` / `mock/dashboard.ts` (not touched).

## 12. Open decisions carried forward

- **Timeline** — still an unresolved product decision (unchanged from
  before this part).
- **1440×900 / 1280×720 layout strategy** — untouched, out of scope.
- **Recent Investigations placement** — a frontend/Part 2 concern; the
  backend now provides `recent_investigations` but does not prescribe
  where/how it is displayed.
- **Risk visualization** — `risk_distribution` is now available;
  choosing a chart type is a Part 2/design concern.
- **Refresh behavior** — this command is a plain request/response
  snapshot, not a subscription; whether/how often Part 2 polls it is
  undecided here.
- **"Investigation workload" as a genuine SOC-workflow concept** — see
  §3.2. What exists today (`investigation_status_counts`) is an honest
  status-count breakdown, not a workflow-stage breakdown — those are
  different things, and only the former can be built without inventing
  a workflow-status concept the domain model doesn't have.
