# Phase 4H Part 3 — Dashboard Layout & Presentation

**Status:** Implementation complete; frontend runtime verification is environment-blocked because `npm install` could not complete within the available environment/network window. Backend verification remains green.

## 1. Objective

Implement the Dashboard presentation/layout phase on top of the verified Phase 4H-P2 real-data integration checkpoint.

The goal is a stable, analyst-oriented Dashboard composition that prioritizes KPIs, operational state, investigation workload, recent investigations, and risk/IOC distributions while remaining usable at the target desktop sizes.

No backend capability, data contract, navigation model, sidecar boundary, or global design-system primitive was changed.

## 2. Baseline

Starting checkpoint:

`SOC-IQ-Phase4H-P2-DASHBOARD-REAL-DATA-INTEGRATION-COMPLETE-FULL-PROJECT.zip`

P2 remains the authoritative data-integration baseline. P1 remains immutable.

## 3. Layout architecture

The Dashboard now uses one Dashboard-owned 12-column CSS grid:

```text
┌────────────────────────────────────────────────────────────┐
│ KPI  KPI  KPI  KPI                                        │
├───────────────────────┬────────────────────────────────────┤
│ Operational Status    │ Investigation Overview             │
├───────────────────────┼────────────────────────────────────┤
│                       │ Risk Distribution                  │
│ Recent Investigations ├────────────────────────────────────┤
│                       │ IOC Distribution                   │
│                       ├────────────────────────────────────┤
│                       │ Quick Actions                      │
└───────────────────────┴────────────────────────────────────┘
```

Desktop allocation:

- KPI row: 12/12 columns
- Operational Status: 4/12 columns
- Investigation Overview: 8/12 columns
- Recent Investigations: 8/12 columns and spans the lower stack
- Risk Distribution: 4/12 columns
- IOC Distribution: 4/12 columns
- Quick Actions: 4/12 columns

This keeps the primary investigation table visually dominant while keeping the aggregated distributions adjacent rather than stacking every panel vertically.

## 4. Responsive behavior

### 1440px / 900px target

The full 12-column composition is retained. The Dashboard does not introduce a Dashboard-specific page scroll container or a new global layout primitive.

### 1280px desktop target

The same hierarchy remains in place with reduced grid/card gaps and compact card padding. The 12-column allocation is retained because the content still benefits from the side-by-side investigation/distribution relationship.

### ≤900px

The grid changes to six columns so the lower 8/4 relationship can become 4/2 without forcing narrow cards.

### ≤640px

Panels become a single-column flow. The KPI row becomes one column as well.

This breakpoint behavior is intentionally scoped to Dashboard presentation and does not alter the shared `PageLayout` architecture.

## 5. Design-system usage

No replacement primitives were introduced.

The Dashboard continues to use:

- `PageLayout`
- `PageHeader`
- `Card`
- `MetricCard`
- `StatusBadge`
- `DataTable`

Global tokens remain unchanged.

## 6. Risk visualization decision

The existing P2 horizontal distribution bars were retained and refined as the Dashboard's risk visualization.

This is intentionally not a chart-library introduction. The backend already supplies the aggregated severity counts, and the frontend only controls ordering, labels, scale, and presentation.

The design follows the common enterprise-security-dashboard pattern of placing key indicators first and using horizontal severity distributions for quick comparison. ServiceNow and Splunk both document dashboard structures that prioritize key indicators and risk/severity distributions. The implementation adapts that information hierarchy without copying their visual design.

## 7. IOC visualization

The P2 IOC distribution remains a compact horizontal distribution list. No new visualization library was added.

## 8. Timeline

**Not implemented.**

The Timeline remains an unresolved product/documentation decision and is not invented in P3.

## 9. Refresh behavior

**Not implemented.**

P2's single-command fetch behavior remains unchanged. No polling or artificial refresh mechanism was added.

## 10. Investigation workflow states

**Not changed.**

The Dashboard continues to display the backend's persisted investigation-status vocabulary. No `open`, `in_progress`, or `closed` state is introduced.

## 11. Accessibility

The existing semantic sections, table semantics, status text, loading/error states, and keyboard-visible focus conventions remain intact.

The layout does not rely on color alone to communicate state.

## 12. Motion

No feature-specific animation was introduced.

## 13. Files modified

- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/DashboardPage.css`
- `frontend/src/pages/dashboard/DashboardMetrics.css`
- `frontend/src/pages/dashboard/dashboard.test.tsx`

## 14. Files created

- `docs/phase4/PHASE4H_PART3_DASHBOARD_LAYOUT.md`

## 15. Files deleted

None.

## 16. Backend changes

**NONE.**

## 17. Regression scope

The following remain outside the changed surface:

- Investigation Workspace
- `useInvestigation()`
- Threat Intel
- `typedVerdict`
- `tiState`
- Analyze workflow
- sidecar lifecycle
- existing command transport
- Rust/Tauri
- database schema
- existing navigation model

## 18. Verification

Dashboard backend tests:

```text
50 passed
```

Frontend dependency installation:

```text
BLOCKED/TIMED OUT
```

The environment did not complete `npm install` within the available execution window. Therefore `vitest`, TypeScript, and the Vite production build are not claimed as passed.

## 19. Inspiration / research references

The implementation decision was informed by current enterprise-security dashboard patterns emphasizing KPI-first hierarchy, risk/severity distribution, and compact analytical panels:

- ServiceNow CISO Dashboard documentation — KPI/risk-exposure grouping and horizontal risk visualizations.
- Splunk Enterprise Security Executive Summary documentation — key metrics followed by findings/risk panels.
- NetBramha's Netsecop case study — emphasis on information hierarchy and operational clarity in security dashboards.

These references influenced information hierarchy only. SOC-IQ's existing tokens, components, terminology, and architecture remain the source of truth.

## 20. Explicit non-scope

P3 does not:

- add Timeline
- change backend aggregation
- add polling
- add a chart library
- redesign global tokens
- redesign `PageLayout`
- modify navigation
- modify sidecar status
- change investigation workflow semantics
- begin Phase 4H-P4 or later work
