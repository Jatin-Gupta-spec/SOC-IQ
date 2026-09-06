# Phase 4H-P4 — Full Project Audit, Windows Fix, and SOC Product Comparison

**Baseline:** `SOC-IQ-Phase4H-P4-DASHBOARD-FINAL-POLISH-COMPLETE-FULL-PROJECT.zip`
**Status:** COMPLETE / VERIFIED

## 1. Windows Filename Collision

**Confirmed by direct source inspection.**

- `frontend/src/shared/notifications/RestartExhaustedNotification.tsx` — the presentational
  component, exports `RestartExhaustedNotification` (function) and
  `RestartExhaustedNotificationProps` (interface).
- `frontend/src/shared/notifications/restartExhaustedNotification.ts` — the notification
  store, exports `RestartExhaustedNotificationState`, `RestartExhaustedNotificationListener`,
  `RestartExhaustedNotificationStore` (class), and the singleton instance
  `restartExhaustedNotification`.

These two filenames differ only by the case of the first letter (`R` vs `r`) — safe on
case-sensitive filesystems (Linux/macOS), but Windows' case-insensitive-by-default filesystem
resolves both to the same file, producing the reported Vite error.

### Fix applied

- Renamed `restartExhaustedNotification.ts` → `restartExhaustedNotificationStore.ts`.
- Renamed its co-located test `restartExhaustedNotification.test.ts` →
  `restartExhaustedNotificationStore.test.ts` for consistency (not itself part of the
  collision — `.test.ts` vs `.test.tsx` differ by extension, not case only — but left
  matching the source file it tests).
- Updated all 8 import sites across the repo to the new path:
  - `shared/notifications/RestartExhaustedNotification.live.test.tsx`
  - `shared/notifications/restartExhaustedNotificationStore.test.ts`
  - `shared/notifications/RestartExhaustedNotification.tsx`
  - `shared/notifications/RestartExhaustedNotification.test.tsx`
  - `shared/notifications/useRestartExhaustedNotification.test.tsx`
  - `shared/notifications/useRestartExhaustedNotification.ts`
  - `app/App.tsx`
  - `app/shell/AppShell.live.test.tsx`
- Did **not** rename the exported symbol `restartExhaustedNotification` (verified still
  present, unchanged, at its original line).
- Did **not** touch sidecar lifecycle, restart policy/scheduler/tracker, Rust/Tauri,
  sidecar-core, or command transport.

### Verification

- Repo-wide search confirms zero remaining references to the old filename
  (`restartExhaustedNotification.ts`) anywhere in `frontend/src`.
- `npx vitest run`, `npx tsc --noEmit`, and `npm run build` all pass (see §5).

## 2. Repo-Wide Case-Sensitivity Sweep

Performed a case-insensitive filename collision scan across the **entire** repository (all
of `app/`, `frontend/`, `database/`, `docs/`, `samples/`, `sidecar-core/`, `src-tauri/`,
`tests/`), excluding `node_modules`, `.git`, `target`, `dist`, `__pycache__`.

**Result: no other case-only filename collisions exist in the project.** The known
`RestartExhaustedNotification` pair was the only instance.

## 3. Other Windows-Compatibility Checks

- No `.sh` (bash-only) scripts exist anywhere in the repository.
- `frontend/package.json` scripts (`dev`, `build`, `typecheck`, `test`, `tauri`) are all
  cross-platform `vite`/`tsc`/`vitest`/`tauri` invocations with no shell-specific syntax.
- Grep sweep for slash-delimited string literals in Python source flagged five files
  (`app/api/app.py`, `app/reporting/html_exporter.py`, `app/reporting/markdown_exporter.py`,
  `app/reporting/pdf_exporter.py`, `app/services/correlation_service.py`); inspected each
  match — all are FastAPI route strings (`"/health"`, `"/events"`) or HTML/text content, not
  filesystem path construction. No genuine Unix-only path assumption found.
- `src-tauri/tauri.conf.json`'s `frontendDist` and `beforeDevCommand` use relative paths with
  forward slashes, which Tauri/Node resolve correctly on Windows.

No new Windows-compatibility defects found beyond the known collision.

## 4. Dashboard Bugs Found and Fixed

These were found while running the existing test suite as part of verification — genuine
correctness defects, not stylistic changes, and squarely within the Dashboard's own scope
(not a frozen area).

### 4a. `humanize()` label casing (Category A — real data incorrectly represented)

`dashboardViewModel.ts`'s `humanize()` helper converts backend enum values (e.g.
`"FAILED"`, `"CRITICAL"`) into display labels. Its regex
(`.replace(/\b\w/g, c => c.toUpperCase())`) only uppercases the first character of each
word — it never lowercases the rest. Because the backend's status/severity vocabulary is
already all-uppercase, the "fix" was a no-op: `"FAILED"` rendered as `"FAILED"`, not
`"Failed"`.

**Fix:** added `.toLowerCase()` before the per-word uppercase pass, so `"FAILED"` →
`"Failed"`, `"CRITICAL"` → `"Critical"`, etc. Verified by the pre-existing (and previously
failing) `dashboardViewModel.test.ts` assertions, now passing.

**File:** `frontend/src/pages/dashboard/dashboardViewModel.ts`

### 4b. Stale/incomplete `pages.test.tsx` Dashboard content test

`pages.test.tsx`'s `"DashboardPage content"` test asserted the text `"Active Investigations"`,
which contradicts the newer `dashboard.test.tsx` file (which explicitly asserts that text is
**absent** — confirming a deliberate rename to "Investigation Overview" that this older test
was never updated for). Separately, the test never mocked `useDashboard()`, so
`DashboardPage` always rendered in its `loading` state — none of its three assertions could
ever pass regardless of wording.

**Fix:** updated the assertion to "Investigation Overview" (matching the real, current
component title) and added a `useDashboard` mock mirroring the pattern already established
in `dashboard.test.tsx`, so the test actually exercises the loaded-state markup it claims to.

**File:** `frontend/src/pages/pages.test.tsx`

### 4c. Pre-existing TypeScript strict-mode errors (test files only)

`npx tsc --noEmit` reported 11 pre-existing errors in `dashboardViewModel.test.ts` and
`useDashboard.test.tsx`, all `noUncheckedIndexedAccess` violations from unchecked array
indexing (`BASE.recent_investigations[0]`, `calls[0]`, etc. typed as possibly `undefined`).
These predate this session's changes (unrelated files, confirmed not touched by the Windows
fix or 4a/4b).

**Fix:** added non-null assertions (`!`) at each flagged access — test-only, no behavior
change, no production code touched.

**Files:** `frontend/src/pages/dashboard/dashboardViewModel.test.ts`,
`frontend/src/pages/dashboard/useDashboard.test.tsx`

## 5. Missing `requirements.txt`

**Category A finding.** The uploaded baseline had no `requirements.txt` at all, despite:

- `app/api/entrypoint.py`'s own runtime `ImportError` message explicitly telling the operator
  to "See requirements.txt."
- Every prior Phase 4 checkpoint document (`PHASE4D_PART2_IMPLEMENTATION.md`,
  `PHASE4E_PART1_IMPLEMENTATION.md`, `docs/architecture/18-packaging-release-architecture.md`,
  `docs/security/dependency-supply-chain-security-model.md`, etc.) referencing it as an
  existing file with specific documented version floors (`fastapi>=0.141.1`,
  `uvicorn>=0.52.4`, `httpx>=0.28.1`).
- `docs/architecture/CURRENT_STATE.md`'s own directory tree listing it as present.

Backend tests could not even be collected without it (`ModuleNotFoundError: fastapi`,
`uvicorn`).

**Fix:** reconstructed `requirements.txt` by statically enumerating every top-level
third-party import actually used across `app/` and `tests/` (`PySide6`, `dotenv`, `fastapi`,
`reportlab`, `requests`, `rich`, `uvicorn`, plus `pydantic`/`httpx`/`pytest`), using the
documented version floors where a prior phase report stated one, and the verified-working
version in this session's environment otherwise. Minimum-version constraints only (`>=`), no
locking — matching the project's own documented packaging convention.

Re-ran `pip install -r requirements.txt` and the full test suite from a clean environment
using only this file: succeeded (see §7).

## 6. Mock Data Audit

Searched `frontend/src` for mock/fixture/placeholder usage outside test files.

**Dashboard: 100% real data.** `DashboardPage` sources everything through `useDashboard()` →
`get_dashboard_summary` (the real, established Phase 4C+ command). No `mock/` import
anywhere in the Dashboard's component tree. `DashboardOperationalStatus` is explicitly
documented in its own source comment as "the Dashboard's one piece of genuinely live data,"
reading the real sidecar projection — this is accurate, verified by reading the component.

**Six other pages still use `frontend/src/mock/*`:** `AnalyzePage` (partially — the
functional native-file-selection path is real, per Phase 4I; the rest is the mock entry
point), `SettingsPage`, `RiskPage`, `ThreatIntelPage`, `ReportsPage`, `IocExplorerPage`. Every
one of these self-documents its own mock status in a source comment (e.g. `"Risk mock page"`,
`"Threat Intel mock page — provider rows are static mock status only"`, `"IOC Explorer mock
page"`) and the corresponding test in `pages.test.tsx` asserts the honest-non-functional
behavior (disabled controls, "not implemented in this checkpoint" notes, no persistence).

**Classification:** intentional, pre-existing, self-documented placeholders — not a Dashboard
regression, not something this P4 pass introduced, and explicitly **future work (Category C)**
per the task's own scope (implementing real backend integration for six additional pages is
well beyond a Dashboard-focused audit and touches areas — Investigation Workspace, Threat
Intel provider architecture — that are frozen for this session). Left unchanged.

## 7. Test Results

### Frontend

```
npm install         → succeeded
npx vitest run       → 66 files, 930/930 tests passed
npx tsc --noEmit      → 0 errors (was 11 before §4c fix)
npm run build         → succeeded (tsc --noEmit && vite build; 190 modules, dist/ produced)
```

### Backend

```
python -m pytest tests/ --ignore=tests/gui -q   → 717 passed
python -m pytest tests/gui -q                    → 154 passed
python -m pytest tests/ -q (combined)            → 871 passed, 0 failed
```

Both runs used only `pip install -r requirements.txt` (the reconstructed file from §5) — no
manual/undocumented package installs beyond that file.

### Rust / Tauri

No Rust toolchain (`cargo`/`rustc`) is present in this sandbox — consistent with every prior
Phase 4 session's finding on this project. `cargo check`/`cargo test` for `sidecar-core` and
`src-tauri` were **not run**. This is a known, previously-documented environment limitation,
not a new regression. No Rust source was modified in this session.

## 8. SOC Product Comparison

Researched current public documentation/reviews for Microsoft Sentinel's Overview dashboard,
Wazuh's dashboard/module structure, and general SOC-dashboard UX patterns, then compared
against SOC-IQ's actual Dashboard source (read directly, not assumed).

| Capability | SOC-IQ | Sentinel / Wazuh (comparable products) | Assessment |
|---|---|---|---|
| KPI summary strip (report/IOC/finding counts) | Has it — `DashboardMetrics`, 4 real KPI cards from `get_dashboard_summary` | Sentinel's Overview page opens with operational and health insight widgets across its main function domains, giving an at-a-glance read on SOC efficiency | SOC-IQ already has it, same information-hierarchy pattern |
| Investigation status distribution | Has it — `DashboardInvestigationOverview`, real backend counts | Sentinel shows a summary of incidents created during the last 24 hours by status, by severity, closed incidents, closing classification | SOC-IQ has the status half; no time-windowed (last-24h) breakdown yet |
| Risk/severity distribution bar | Has it — `DashboardRiskOverview`, severity-ordered with zero-count preservation | Standard in both Sentinel and Wazuh overview dashboards | SOC-IQ already has it |
| IOC-type distribution | Has it — `DashboardIocOverview` | Wazuh's overview surfaces top rule groups/event types in an equivalent role | SOC-IQ already has it |
| Recent investigations list | Has it — `DashboardRecentInvestigations`, real recent records | Sentinel's incidents list serves this role at a larger scale | SOC-IQ already has it, scoped appropriately smaller |
| Live operational/health status | Partially — `DashboardOperationalStatus` reads real sidecar liveness only (single boolean-ish state) | Sentinel tracks unhealthy connectors per-source; ingestion volume, cost | SOC-IQ intentionally does not have per-source health yet — no multi-source ingestion model exists to report on |
| Quick actions / navigation shortcuts | Has it — `DashboardQuickActions`, real in-app links | Both products offer saved views/pinned queries in this role | SOC-IQ already has it |
| Cost/ingestion visibility | Does not have it | Sentinel dashboards explicitly surface daily data ingestion, overage cost, and active vs. inactive analytic rules | Not applicable — SOC-IQ has no cloud ingestion billing model; intentionally out of scope |
| Detection-rule/use-case coverage view | Does not have it | Sentinel workbooks commonly map which data sources are leveraged by existing detection rules | SOC-IQ should consider a lightweight analogue later (e.g. "which IOC types are actually being enriched") once Threat Intel is no longer mock-only |
| Mean-time-to-acknowledge/close metrics | Does not have it | Sentinel surfaces meters for mean time to acknowledge an incident and mean time to close | Future work — requires investigation-lifecycle timestamps SOC-IQ's current data model may not fully track yet; worth a data-model check before promising this |
| Live attack map / global telemetry | Does not have it | Some SIEM marketing dashboards include this | SOC-IQ should NOT copy this — no genuine multi-tenant/geo telemetry backend exists; would be fabricated data |

### UI/UX findings

Sentinel's Overview groups by function domain (incidents, connectors, automation, TI,
analytics), and each widget shows its own last-refresh timestamp since data is pre-calculated per widget rather than fetched live on every view — a pattern SOC-IQ's Dashboard already
loosely mirrors via its `aria-label`led sections (Key metrics / Operational status /
Investigation overview / Recent investigations / Risk distribution / IOC distribution / Quick
actions), just without per-section refresh timestamps (reasonable, since the whole Dashboard
loads as one `get_dashboard_summary` call rather than independently-refreshing widgets).

### Functionality findings

SOC-IQ's Dashboard is honestly scoped to what its backend actually aggregates — a strength,
not a gap, relative to products whose dashboards imply capabilities (per-source health,
cost tracking) that require infrastructure SOC-IQ was never meant to have.

### What SOC-IQ does particularly well

Real-data discipline: every Dashboard widget traces to an actual backend field, with
explicit zero-count/no-data handling (`toRiskDistribution` preserves zero counts,
`formatCoverage` shows "No data" rather than fabricating "0%"). This is more disciplined
than several enterprise dashboards that show blank/misleading zeros.

### What SOC-IQ is missing (genuinely, not just "different")

- Time-windowed breakdowns (e.g. "in the last 24h") — currently all-time only.
- Per-source/per-provider operational health, once more than one live data source exists.

### What should be implemented later (Category C, correctly deferred)

- Lifecycle timing metrics (time-to-triage, time-to-close) once the data model supports it.
- Replacing the six remaining mock pages with real backend contracts, one vertical slice at a
  time, matching this project's established pattern.

### What should NOT be copied

- Live/animated attack maps, fabricated global telemetry, or invented MITRE coverage —
  SOC-IQ has no backend capability behind any of these; adding them would violate this
  project's own stated data-honesty priority.

## 9. Regression Check

Ran the full frontend and backend suites (§7) after all fixes — all passing, with no
unexpected file changes outside those listed in §11–§13 below. Frozen areas (Investigation
Workspace, `useInvestigation()`, Threat Intel provider architecture, `typedVerdict`/`tiState`,
Analyze workflow, sidecar lifecycle, Rust/Tauri, database schema, command transport,
application architecture) were not touched — confirmed by diff review of every changed file
against this list.

## 10. Remaining Risks / Open Items

- Rust/Tauri code (`sidecar-core`, `src-tauri`) remains unverified by `cargo check`/`cargo
  test` in every sandbox used across this project's history, including this one. This is a
  standing, previously-documented limitation, not new.
- The reconstructed `requirements.txt` is a best-effort rebuild from actual source imports and
  previously-documented version floors; it has not been cross-checked against any
  now-missing original file, since none was found anywhere in the uploaded baseline or its
  git history (not included in this ZIP).
- Six pages remain on `mock/` data by design; this is documented, tested-for, and out of this
  session's scope, not overlooked.

## 11. Files Modified

- `frontend/src/shared/notifications/RestartExhaustedNotification.live.test.tsx` (import path)
- `frontend/src/shared/notifications/RestartExhaustedNotification.tsx` (import path)
- `frontend/src/shared/notifications/RestartExhaustedNotification.test.tsx` (import path)
- `frontend/src/shared/notifications/useRestartExhaustedNotification.test.tsx` (import path)
- `frontend/src/shared/notifications/useRestartExhaustedNotification.ts` (import path)
- `frontend/src/app/App.tsx` (import path)
- `frontend/src/app/shell/AppShell.live.test.tsx` (import path)
- `frontend/src/pages/dashboard/dashboardViewModel.ts` (humanize() bug fix)
- `frontend/src/pages/pages.test.tsx` (stale assertion + missing mock fix)
- `frontend/src/pages/dashboard/dashboardViewModel.test.ts` (strict-mode non-null assertions)
- `frontend/src/pages/dashboard/useDashboard.test.tsx` (strict-mode non-null assertions)

## 12. Files Created

- `requirements.txt` (reconstructed — see §5)
- `docs/phase4/PHASE4H_P4_FULL_AUDIT_AND_SOC_COMPARISON.md` (this document)

## 13. Files Deleted

None.

## 14. Files Renamed

- `frontend/src/shared/notifications/restartExhaustedNotification.ts` →
  `frontend/src/shared/notifications/restartExhaustedNotificationStore.ts`
- `frontend/src/shared/notifications/restartExhaustedNotification.test.ts` →
  `frontend/src/shared/notifications/restartExhaustedNotificationStore.test.ts`

## 15. Backend Changes

NONE (`app/`, `database/`, `sidecar-core/`, `src-tauri/` source unchanged; only the missing
`requirements.txt` manifest was added at the repo root).

## 16. Intentionally Unchanged (Frozen Areas)

Investigation Workspace, `useInvestigation()`, Investigation normalization, Threat Intel
provider architecture, `typedVerdict`, `tiState`, Analyze workflow (beyond its existing native
file-selection path from Phase 4I, untouched here), sidecar lifecycle, Rust/Tauri
architecture, database schema, existing command transport, existing application architecture,
`get_dashboard_summary`/`DashboardSummaryDTO`/dashboard aggregation (backend), and all six
mock pages listed in §6.
