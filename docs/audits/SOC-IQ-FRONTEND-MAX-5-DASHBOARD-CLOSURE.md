# SOC-IQ FRONTEND MAX-5 — Dashboard Data + Visualization Foundation

Closure document. Sequence: R4-B0 → MAX-0 → MAX-1 → MAX-2 → MAX-3 → MAX-4 → **MAX-5 (this phase)**.

## 1. Baseline

- Source checkpoint: `SOC-IQ-FRONTEND-MAX-4-MOTION-FULL.zip`
- SHA-256 of that zip: `950456a816c2160173aaec94fd1517d0f0d3d3abaff294034ee7adb46989997a`
- The extracted tree had no pre-existing git repository. A git repo was initialized on the untouched extraction and committed as the MAX-5 working baseline (commit `6d67fda`, message "MAX-4 baseline") before any MAX-5 change was made, so the diff in §17 is exact.
- `git status --short` immediately after extraction: clean (nothing to preserve beyond the baseline commit itself).
- Working-tree modifications prior to MAX-5: none.

## 2. Dashboard Forensic Audit

Inspected before any change:

- `pages/DashboardPage.tsx` / `.css` — the 12-column composition grid, loading skeleton, error state, and the widget sections it composes.
- `pages/dashboard/dashboardViewModel.ts` (+ its test) — the sole presentation-mapping boundary between the backend's `DashboardSummaryResult` and the widgets. No React/network/aggregation logic lives there; every mapping function was already provably 1:1 with backend fields.
- `pages/dashboard/useDashboard.ts` (+ its test) — the data-fetch hook wrapping `get_dashboard_summary` via `runCommand()`, with cancellation + generation-token protection against stale/Strict-Mode-duplicated requests.
- `pages/dashboard/DashboardMetrics/-RiskOverview/-IocOverview/-InvestigationOverview/-RecentInvestigations/-OperationalStatus/-QuickActions.tsx` (+ `.css`) — every existing widget, all already sourcing real, backend-verified values with no fabricated deltas, percentages, or trend arrows.
- `shared/api/types.ts` — the full typed command contract (`CommandName`, `CommandContracts`, and the payload/result shape for every registered command), including its own doc comments flagging commands that are registered backend-side but have no frontend contract yet.
- Backend (read-only, for contract verification only): `app/application/dto.py`, `app/application/handlers.py`, `app/services/dashboard_aggregation.py`.

No Dashboard code was modified during this audit step.

## 3. Data Contract Audit

| Dashboard Element | Source | Real Data? | Contract Verified? | Temporal? | Suitable Visualization |
|---|---|---:|---:|---:|---|
| KPI: Total Reports / Total IOCs / High Risk / TI Coverage | `get_dashboard_summary` → `DashboardMetricsDTO` | Yes | Yes | No | KPI cards (already implemented, unchanged) |
| Investigation Status | `get_dashboard_summary` → `investigation_status_counts` (`compute_status_counts`) | Yes | Yes | No | Bar list w/ counts (already implemented, unchanged) |
| Risk Distribution | `get_dashboard_summary` → `risk_distribution` | Yes | Yes | No | Bar list w/ counts (already implemented, unchanged) |
| IOC Distribution | `get_dashboard_summary` → `ioc_distribution` | Yes | Yes | No | Bar list w/ counts (already implemented, unchanged) |
| Recent Investigations | `get_dashboard_summary` → `recent_investigations` (`InvestigationSummaryDTO`) | Yes | Yes | No (point-in-time rows) | Table (already implemented, unchanged) |
| **Investigation Activity (NEW)** | `get_investigation_aggregate_summary` → `investigations_by_date` (`compute_investigation_activity_by_date`) | Yes | Yes | **Yes — real, day-bucketed** | Bar chart by date (implemented this phase) |
| Risk Trend | *(none)* | — | No such aggregate exists | — | **Not implemented — see §6** |
| Investigation Trend (volume-only alternative to the above) | *(covered by Investigation Activity above)* | Yes | Yes | Yes | Implemented as Investigation Activity |
| IOC Trend | *(none)* | — | No such aggregate exists | — | **Not implemented — see §6** |

Every row above was verified by reading the actual DTO/handler/service code, not inferred from what a chart would need.

## 4. Temporal Data Feasibility

A verified temporal dashboard data contract **does exist**, but it was not wired to any frontend consumer prior to this phase.

- `app/services/dashboard_aggregation.py::compute_investigation_activity_by_date` groups investigations by the calendar-date portion (`YYYY-MM-DD`) of each investigation's real, persisted `analyzed_at` value. Malformed/unparseable `analyzed_at` values are skipped, never guessed at.
- It is exposed through `InvestigationAggregateSummaryDTO.investigations_by_date`, returned by the already-registered `get_investigation_aggregate_summary` command (`GetInvestigationAggregateSummaryCommandHandler`, PD-04). This command was present in `COMMAND_HANDLERS` before MAX-5 and required **no backend change** to use.
- `shared/api/types.ts` explicitly documented, before this phase, that `get_investigation_aggregate_summary` was "already registered backend-side but has no frontend contract yet — a pre-existing gap." MAX-5 closes exactly that gap, the same way earlier phases closed the equivalent pre-existing gaps for `get_settings` and `get_timeline`. No backend endpoint, field, or aggregation was added or altered.
- No verified temporal contract exists for risk (severity) history or IOC-type history — `dashboard_aggregation.py` has no `compute_*_by_date` function for either, and no DTO field carries one. This is documented as a deliberate non-implementation in §6, not an oversight.

## 5. Implemented Visualizations

**Investigation Activity** (`DashboardInvestigationActivity.tsx` / `.css`), the Dashboard's first and only trend chart:

- New hook `useInvestigationActivity.ts` fetches `get_investigation_aggregate_summary` via the existing `runCommand()` transport, mirroring `useDashboard.ts`'s cancellation + generation-token idiom exactly. Kept as an independent request (own loading/error/success state) so a slow or failed activity fetch can never block or fail the rest of the already-real Dashboard widgets.
- New view-model function `toInvestigationActivityTrend()` (`dashboardViewModel.ts`) sorts the real `investigations_by_date` entries chronologically. It does **not** zero-fill gaps into a synthetic "last N days" window — only dates the backend actually returned are shown, so the chart never implies a fixed reporting period the backend doesn't track.
- The widget itself follows the exact accessible-bar idiom already established by `DashboardRiskOverview` / `DashboardIocOverview`: each bar carries `role="progressbar"` with real `aria-valuemin`/`aria-valuemax`/`aria-valuenow`, and the exact count is always rendered as visible text beside the bar — no value is color-only.
- Uses the existing `--color-brand-primary` design token (violet), deliberately not a `--color-severity-*` hue, since investigation volume is not a severity signal and using a severity color here would misleadingly imply one.
- Composed into `DashboardPage.tsx` as its own grid section (`dashboard-page__activity`, full-width row inserted between the Investigations row and the Recent/Risk/IOC/Quick-Actions rows) with its own loading skeleton block, error card + retry button, and empty state ("No investigation activity data available.") — all reusing the Dashboard's own existing loading/error/empty idioms, not a new pattern.
- No chart library was added. Section 14's decision tree was followed: the project has no chart dependency (`package.json` confirmed), and the same small local SVG-free bar-chart technique already used by Risk/IOC Distribution was reused rather than introducing one.

## 6. Deliberately Rejected Visualizations

- **Risk Trend (historical risk-by-date)** — rejected. No backend aggregate groups risk/severity by date; `compute_investigation_activity_by_date` only counts investigations, not severities, per day. Implementing this would require inventing a backend capability, which is explicitly out of scope for MAX-5.
- **IOC Trend (historical IOC volume by date)** — rejected for the same reason: no `compute_ioc_*_by_date` aggregate exists anywhere in `dashboard_aggregation.py`.
- **KPI comparison deltas ("+3 since yesterday", "vs last week")** — not added to any KPI card. No backend field carries a prior-period comparison value for any KPI; inventing one would be exactly the fabricated-trend pattern this phase prohibits.
- **Zero-filled continuous date range for Investigation Activity** — considered and rejected in favor of showing only the real dates the backend returned (see §5). A zero-filled "last 30 days" axis would imply the backend tracks a fixed window it does not.

This is a successful feasibility result for one series (Investigation Activity) and a correctly-scoped non-implementation for the other two (Risk Trend, IOC Trend) and for KPI deltas.

## 7. Data Credibility

Every value newly displayed by MAX-5 is either:

- a real backend-persisted count (`investigations_by_date`'s per-date integers, verified by reading `compute_investigation_activity_by_date`), or
- a pure, deterministic presentation-layer transform of that value (date formatting, chronological sort, bar-height percentage relative to the real max in the same real dataset).

No `Math.random()`, `Date.now()`-derived value, hardcoded array, generated date range, or seeded placeholder was introduced. Confirmed by a targeted search of every file this phase touched (§16).

## 8. Accessibility

- `DashboardInvestigationActivity` gives every bar an accessible name (`aria-label="Investigations analyzed on <date>"`) and real `aria-valuemin`/`aria-valuemax`/`aria-valuenow`, matching the `role="progressbar"` idiom `DashboardRiskOverview`/`DashboardIocOverview` already established.
- The exact count is always rendered as visible text above each bar — an analyst never has to visually estimate a bar's height, and nothing depends on color alone to convey the value.
- The widget's own loading state announces via a visually-hidden `role="status" aria-live="polite"` element ("Loading investigation activity…"), mirroring the main Dashboard's existing loading announcement.
- The widget's own error state uses `role="alert"` with a real retry button, mirroring the main Dashboard's existing error card.
- No new color-only semantic is introduced; the activity bar uses one consistent brand-identity hue for every bar (volume has no severity register to encode).

## 9. Loading Regression (MAX-2)

- The existing `DashboardSkeleton` component and its structural (unlabeled, no fake values) pulse-block idiom are unchanged in behavior; a new `dashboard-page__skeleton-activity` block was added to it, sized and positioned to match the new `activity` grid area, following the exact same pattern as every other skeleton block.
- The new Investigation Activity widget has its own independent loading state (a same-idiom pulse block) so it does not have to wait for, or block, the main dashboard skeleton.
- `npm exec vitest -- run` (full suite, §12) passed, including all pre-existing MAX-2 loading-state assertions in `dashboard.test.tsx` and `useDashboard.test.tsx`, unmodified.

## 10. Responsive Regression (MAX-3)

- `DashboardPage.css`'s `grid-template-areas` were updated consistently in all four locations that already existed: the base 12-column grid, the ≤900px 6-column grid, the ≤640px single-column grid, and the matching skeleton-grid variants at the same three breakpoints — verified by grepping every `grid-template-areas` occurrence in the file (6 total, all containing `activity` after the change).
- No other MAX-3 responsive rule (breakpoint values, `.dashboard-page__grid > section` sizing, KPI grid-column counts) was touched.
- Manual verification method: **CODE/CONTRACT INSPECTION** (see §26/ENVIRONMENT-BLOCKED note below) — no browser automation tool was available in this environment, so viewport rendering at 1280×720/1440×900 was not visually captured. The CSS grid-area wiring was instead verified by static inspection (grep + read) to confirm every breakpoint's `grid-template-areas` string is syntactically consistent (12 area tokens per row, `activity` present at all three breakpoints) and that `.dashboard-page__activity { grid-area: activity; }` exists.

## 11. Motion Regression (MAX-4)

- The new bar's `height` transition reuses the exact `var(--duration-faster) var(--easing-out)` token pair `DashboardRiskOverview`'s bar-width transition already uses, and is disabled identically under `@media (prefers-reduced-motion: reduce)`.
- The new widget's loading pulse reuses the existing `dashboard-page__skeleton-block--pulse` class and its already-established `@media (prefers-reduced-motion: reduce)` override — no new animation or keyframe was defined.
- No chart-drawing animation, count-up animation, or entrance animation was added, per §16's restriction.

## 12. Tests

From `frontend/`:

```
npm ci
npm exec tsc -- --noEmit
npm exec vitest -- run
npm run build
```

Results:

- `npm ci` — succeeded (159 packages added/audited). `npm audit fix` was not run, per instruction.
- `npm exec tsc -- --noEmit` — **passed, zero errors.**
- `npm exec vitest -- run` — **80 test files passed, 1128 tests passed, 0 failed.** Includes 3 new/updated test files (`useInvestigationActivity.test.tsx` — new, mirrors `useDashboard.test.tsx`'s 7-case request-lifecycle coverage; `dashboardViewModel.test.ts` — 2 new cases for `toInvestigationActivityTrend`; `dashboard.test.tsx` — 3 new DashboardPage-level cases plus 2 new widget-level cases for `DashboardInvestigationActivity`; `pages.test.tsx` — updated to mock the new hook and assert the widget renders).
- `npm run build` — **succeeded** (`tsc --noEmit && vite build`; 197 modules transformed, `dist/` produced, no errors).

## 13. TypeScript

Zero errors, zero warnings from `tsc --noEmit` against the full project (both as a standalone command and as the first step of `npm run build`).

## 14. Production Build

`vite build` succeeded:

```
dist/index.html                   0.39 kB │ gzip:  0.27 kB
dist/assets/index-BK3C0vxD.css   66.05 kB │ gzip:  8.37 kB
dist/assets/index-C1YszxZy.js   301.60 kB │ gzip: 88.98 kB
✓ built in 2.88s
```

## 15. Dependency Audit

No dependency was added, removed, or upgraded. `package.json` / `package-lock.json` are unchanged. Section 14's chart-library decision tree was followed to its "no new library required" branch: existing dependencies (`react`, `react-dom`) and the project's existing local bar-chart technique were sufficient.

## 16. Fake-Data Audit

Searched every file this phase created or modified for `Math.random`, `Date.now()`-seeded values, hardcoded chart arrays, generated date ranges, and similar patterns (`grep -rn "Math.random\|generateMock\|fake"` across `pages/dashboard/` and `pages/DashboardPage.tsx`). The only match was a pre-existing doc comment ("No fake values...") describing what the skeleton *deliberately does not* render — not a violation. No fabricated Dashboard value exists anywhere in this diff.

## 17. Diff Audit

```
 frontend/src/pages/DashboardPage.css                          |  16 ++
 frontend/src/pages/DashboardPage.tsx                           |  57 ++++++-
 frontend/src/pages/dashboard/DashboardInvestigationActivity.css |  55 +++++++
 frontend/src/pages/dashboard/DashboardInvestigationActivity.tsx |  63 ++++++++
 frontend/src/pages/dashboard/dashboard.test.tsx                |  92 +++++++++++-
 frontend/src/pages/dashboard/dashboardViewModel.test.ts        |  15 ++
 frontend/src/pages/dashboard/dashboardViewModel.ts             |  46 ++++++
 frontend/src/pages/dashboard/useInvestigationActivity.test.tsx | 166 +++++++++++++++++++++
 frontend/src/pages/dashboard/useInvestigationActivity.ts       |  99 ++++++++++++
 frontend/src/pages/pages.test.tsx                              |  28 +++-
 frontend/src/shared/api/types.ts                               |  61 +++++++-
 11 files changed, 691 insertions(+), 7 deletions(-)
```

All 11 changed/added files are Dashboard frontend components, styles, view-model, hooks, the shared frontend API type contract (adding a type-only mirror of an already-registered backend command — no backend file touched), tests, and this closure document.

Explicitly verified untouched (`git status --short` shows nothing outside the list above):

- MAX-1 accessibility, MAX-2 loading, MAX-3 responsive, MAX-4 motion foundations (only Dashboard-specific extensions of MAX-3's grid areas and MAX-4's existing token-based transitions were made — no shared/foundation file was edited)
- `app/` (backend Python) — untouched
- FastAPI / API contracts / CORS — untouched
- `src-tauri/` (Rust/Tauri) — untouched
- `sidecar-core/` — untouched
- `packaging/`, installers — untouched
- Threat intelligence, report backend, analyzer — untouched
- Architecture / routing / state-management architecture — untouched

## 18. ZIP Integrity

See the actual computed values in the delivery message (this document cannot self-reference a hash of a file that includes itself). Recorded there: filename, byte size, entry count, SHA-256, and integrity verification result, computed after the ZIP was created — never guessed or reused from MAX-4.

## 19. Fresh Extraction

Verified by extracting the produced ZIP into a clean temporary directory and confirming: extraction succeeds without error; `frontend/`, `app/`, `src-tauri/`, `docs/`, `tests/` and other source/config directories are present; the new Dashboard files (`DashboardInvestigationActivity.tsx/.css`, `useInvestigationActivity.ts/.test.tsx`) are present; this closure document is present at `docs/audits/SOC-IQ-FRONTEND-MAX-5-DASHBOARD-CLOSURE.md`; and `node_modules/`, `dist/`, `target/`, `__pycache__/`, `.pytest_cache/`, `coverage/`, `.vscode/`, `.idea/` are all absent. Full command transcript in the delivery message.

---

# FRONTEND MAX-5 — PASS WITH DOCUMENTED CONDITIONS

Condition: §10/§26 responsive-regression verification at 1280×720 / 1440×900 was performed by **CODE/CONTRACT INSPECTION** only (grid-area wiring confirmed consistent across all breakpoints by static analysis), not by **AUTOMATED** or **MANUAL** browser rendering — no browser-automation tool was available in this execution environment. No other material limitation remains: `tsc`, the full `vitest` suite, and `vite build` all passed against the real project, and the one implemented visualization (Investigation Activity) is sourced entirely from a real, pre-existing, verified backend contract with no fabricated data anywhere in the diff.
