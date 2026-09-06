# SOC-IQ Frontend MAX-7 — Phase 2A

## Investigation Workspace + Context Preservation — Implementation Closure

---

### 1. Executive Summary

This phase implemented the subset of `docs/audits/SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT.md`
(Phase 1, audit-only) that the Phase 2A brief scoped in: findings concerning the
Investigation Workspace, investigation identity, context preservation, the selected
investigation, the active workspace tab, evidence/IOC/timeline continuity, and return
behavior. Of the audit's five findings (F-01–F-05), exactly two fall inside that scope:

- **MAX7-F-01 (P0)** — the Analyze → Investigation handoff link pointed at the generic
  `/investigations` list instead of the specific investigation the analyst just created.
- **MAX7-F-02 (P1)** — the Investigation Workspace's active tab (Overview / IOCs / Threat
  Intel / Correlations) lived in local React state only, with no URL representation, so
  a reload, shared link, or browser back/forward always reset it to Overview.

F-03 (list-level search/filter/sort discovery), F-04 (Reports/Investigations
purpose overlap), and F-05 (row-activation affordance) are **out of scope** for this
phase — they concern list-level discovery and page-purpose, not the Investigation
Workspace/identity/context-preservation surface this phase's brief names. They were
**not implemented, and not otherwise touched**.

**Implementation result:** both in-scope findings (F-01, F-02) were resolved with the
smallest correct change in each case — a one-value interpolation for F-01, and an
additive `useSearchParams()`-backed `activeTab` for F-02 that leaves MAX-1's tab
semantics, `useInvestigation()`'s single-fetch-per-investigation contract, and every
other frozen MAX-1–MAX-6 system untouched. TypeScript and the full Vitest suite both
pass clean. A source/diff audit against a pristine second extraction of the baseline
confirms changes are confined to exactly five files, all inside `frontend/src/pages/`
— zero changes to `app/` (backend), `src-tauri/`, `database/`, `packaging/`, or any
frontend system outside the two findings' own call sites.

```text
FRONTEND MAX-7 PHASE 2A — PASS
```

---

### 2. Baseline

- **Baseline checkpoint:** `SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT-FULL.zip`
  (the MAX-7 Phase 1 audit-only checkpoint — no source changes relative to MAX-6's own
  closure baseline; the audit document itself, `docs/audits/SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT.md`,
  was read directly from this checkpoint and confirmed byte-identical to the
  standalone audit document supplied alongside it for this phase).
- **Baseline archive size:** 2,451,607 bytes
- **Baseline entries:** 796
- **Baseline SHA-256:** `99dbaeac5da2eab31884fc4b574c792b2aee06c325cfc2f028252e1e9e6a6103`
- **`.git`:** absent from the baseline, consistent with every prior MAX phase in this
  project. As with MAX-6, all change-tracking in this phase was done by diffing the
  working tree against a second, untouched extraction of the same baseline ZIP, not by
  any Git mechanism.

---

### 3. Scope

**In scope (per the Phase 2A brief), and the only findings implemented:**

- Investigation Workspace
- Investigation identity
- Context preservation
- Selected investigation
- Active workspace tab
- Evidence/IOC/timeline continuity
- Return behavior

**Findings resolved under that scope:** MAX7-F-01, MAX7-F-02 (full write-ups: audit
§5 and §9 respectively).

**Explicitly out of scope, and confirmed untouched:** MAX7-F-03, MAX7-F-04, MAX7-F-05
(list-level search/filter/discovery, Reports/Investigations purpose overlap, row
activation — audit §8/§10/§12); backend/Python (`app/`), Rust/Tauri (`src-tauri/`),
database, packaging, and any frontend system not directly implicated by F-01 or F-02.
MAX-1 accessibility, MAX-2 loading, MAX-3 responsive, MAX-4 motion, MAX-5
dashboard/data, and MAX-6 design-system work were all preserved as frozen systems (see
§6 below for how each finding's implementation specifically avoided touching them).

---

### 4. Findings Verified Before Implementation

Both findings were independently re-verified against this phase's actual source
(not assumed from the audit's own text) before any change was made:

- **F-01:** confirmed `frontend/src/pages/analyze/AnalysisResultSummary.tsx`'s handoff
  rendered `href={`#${investigationsPath}`}` with `result.investigationId` read only to
  gate whether a link renders at all, never interpolated into the `href` — exactly as
  the audit describes. Confirmed the correct pattern already exists at three other call
  sites (`DashboardRecentInvestigations.tsx`, and the row links inside
  `InvestigationsPage.tsx`/`ReportsPage.tsx`), all building `/investigations/{id}`.
- **F-02:** confirmed `InvestigationWorkspacePage.tsx`'s `activeTab` was
  `useState<WorkspaceTabId>("overview")`, and that `app/router.tsx`'s only
  investigation-scoped route is the bare `/investigations/:investigationId` with no
  `?tab=`/nested-route representation — exactly as the audit describes.

---

### 5. Implementation

#### 5.1 MAX7-F-01 — Analyze → Investigation deep link

**File:** `frontend/src/pages/analyze/AnalysisResultSummary.tsx`

The handoff link's `href` now interpolates the real investigation id:

```diff
- href={`#${investigationsPath}`}
+ href={`#${investigationsPath}/${result.investigationId}`}
```

This is the one-value fix the audit's own "Recommended direction" describes — no new
navigation mechanism, no new route (`InvestigationRoute`/`InvestigationWorkspacePage`
already handle any valid numeric id). The `investigationsPath` prop's doc comment was
updated to describe the new behavior; no other logic in the component changed. The
`result.investigationId !== null` guard that decides whether to render a link at all
was left exactly as-is.

#### 5.2 MAX7-F-02 — Active tab as URL state

**File:** `frontend/src/pages/investigation/InvestigationWorkspacePage.tsx`

`activeTab` moved from local `useState` to the URL's `?tab=` query parameter via
`useSearchParams()` (already available from the `react-router-dom` this file already
imports `useNavigate` from):

- **Read:** `activeTab` is derived on every render from `searchParams.get("tab")`,
  validated against `WORKSPACE_TABS`' real ids by a new `isWorkspaceTabId()` type
  guard. A missing, empty, or unrecognized value (a stale bookmark, a hand-edited link)
  falls back to `"overview"` — never a blank panel, never a thrown error.
- **Write:** `setActiveTab` calls `setSearchParams()` with a functional updater
  (`URLSearchParams` `set`/`delete`) and `{ replace: true }`, so switching tabs updates
  the current history entry's query string rather than pushing a new one — the browser
  back button still returns an analyst to this investigation at whichever tab was last
  active, without turning every tab click (including every `ArrowRight`/`ArrowLeft`/
  `Home`/`End` keypress) into its own back-stack entry. Selecting "overview" deletes the
  `?tab=` param entirely rather than writing `?tab=overview`, keeping the default-state
  URL clean and matching every existing Dashboard/Investigations/Reports row link (none
  of which carry a `?tab=` value, and all of which should — and now do — resolve to
  Overview).

**What this deliberately did not change:**

- **MAX-1 (accessibility):** `WorkspaceTabs`' roving-tabindex, `role="tab"`/`role="tabpanel"`
  wiring, and `ArrowRight`/`ArrowLeft`/`Home`/`End` keyboard handling are byte-for-byte
  unchanged — they still call the same `onSelectTab`/`setActiveTab` prop they always
  did; only where that prop's state now lives changed, not how it's invoked or how
  focus is managed.
- **Single-fetch-per-investigation:** `useInvestigation(investigationId)` is still the
  only fetch boundary; tab selection is still purely a local render choice that never
  triggers a new fetch. Switching tabs does not re-render `useInvestigation`'s inputs.
- **IOC search/filter reset behavior:** `InvestigationIocWorkspace`'s own
  investigation-id-keyed reset logic was not touched.

---

### 6. Preserved Systems

Confirmed untouched by this phase, by direct diff (§9) and by inspection:

- MAX-1 accessibility architecture (tab semantics, roving tabindex, keyboard handling)
- MAX-2 loading skeletons
- MAX-3 responsive/overflow CSS
- MAX-4 motion tokens/utilities
- MAX-5 Dashboard data contracts (`DashboardRecentInvestigations.tsx` was read, for its
  existing correct deep-link pattern, but not modified)
- MAX-6 `Button`/`Card`/`DataTable`/`PageHeader` architecture
- Backend/Python (`app/`), Rust/Tauri (`src-tauri/`), database, packaging
- MAX7-F-03/F-04/F-05 (out of this phase's scope; not implemented)

---

### 7. Tests

**Updated (2 files)** — both asserted the pre-fix, buggy handoff `href` and now assert
the corrected one:

- `frontend/src/pages/analyze/AnalysisResultSummary.test.tsx` — `"renders an
  accessible, real link straight to that investigation's own workspace when an
  investigation id exists (MAX7-F-01)"` now asserts `href="#/investigations/7"`.
- `frontend/src/pages/AnalyzePage.execution.test.tsx` — asserts
  `href="#/investigations/9"` for the composed-page handoff.

**Added (new `describe` block, 1 file)** —
`frontend/src/pages/investigation/InvestigationWorkspacePage.test.tsx`, `"URL-represented
tab state (MAX7-F-02)"`, using a small `LocationProbe` helper (renders
`useLocation()`'s `pathname + search` into the DOM) to assert on the real router state
a reload/shared-link/back-button scenario would observe:

- defaults to Overview with no `?tab=` param on first render
- selects the tab named by an existing `?tab=` param on first render (deep link/reload)
- falls back to Overview, without throwing, for an unrecognized `?tab=` value
- writes `?tab=` when a tab is clicked
- removes `?tab=` (rather than writing `?tab=overview`) when returning to Overview
- keeps `ArrowRight` keyboard selection (MAX-1) in sync with the URL
- supports switching between several tabs in a row, with the URL always reflecting
  only the latest selection

All pre-existing MAX-1 accessibility tests (semantics, roving tabindex, keyboard
navigation, mouse-interaction regression) were run unmodified and continue to pass
against the new state source.

**Run results:**

```text
npm.cmd exec tsc -- --noEmit     → PASS (clean, zero errors)
npm.cmd exec vitest -- run       → PASS — 81 test files, 1143 tests, 0 failures
```

(Executed in this environment as `npx tsc --noEmit` / `npx vitest run` after
`npm install`; equivalent to the `npm.cmd` invocations on a Windows dev machine.)

---

### 8. Source / Diff Audit

Diffed the full working tree against a second, untouched extraction of the baseline
ZIP (`SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT-FULL.zip`). Excluding `frontend/node_modules`
(created by this phase's own `npm install`, required to run `tsc`/`vitest`, and
excluded from the delivered ZIP per §9), exactly five files differ, all under
`frontend/src/pages/`:

```text
frontend/src/pages/analyze/AnalysisResultSummary.tsx
frontend/src/pages/analyze/AnalysisResultSummary.test.tsx
frontend/src/pages/AnalyzePage.execution.test.tsx
frontend/src/pages/investigation/InvestigationWorkspacePage.tsx
frontend/src/pages/investigation/InvestigationWorkspacePage.test.tsx
```

No changes anywhere under `app/`, `src-tauri/`, `database/`, `packaging/`,
`keystore-core/`, `sidecar-core/`, `tests/`, or any other `frontend/src/` path
(including `router.tsx`, `InvestigationRoute.tsx`, `investigationRouteParams.ts`,
`InvestigationsPage.tsx`, `ReportsPage.tsx`, `DashboardRecentInvestigations.tsx`, and
every MAX-1–MAX-6 shared component) — confirming no scope leakage beyond the two
in-scope findings' own call sites.

---

### 9. Full Project ZIP

- **Filename:** `SOC-IQ-FRONTEND-MAX-7-PHASE-2A-FULL.zip`
- **Contents:** complete Phase 2A project state, excluding only
  `node_modules/`, `dist/`, `target/`, `__pycache__/`, `.pytest_cache/`, `coverage/`,
  `.vscode/`, `.idea/`, and any prior ZIP checkpoint (none were present in the working
  tree at any point in this phase — confirmed by search, §8).
- Exact entry count, size, and SHA-256 are recorded in the final response accompanying
  this closure document (computed after archive creation, per this phase's mandatory
  ZIP-verification procedure) rather than duplicated here to avoid two sources of truth
  for the same figures.

---

### 10. Remaining Work

- MAX7-F-03/F-04/F-05 remain open, unimplemented, and out of this phase's scope —
  available for a future phase if the brief is extended to list-level
  discovery/reporting UX.
- MAX-6's own carried-forward gap (rendered/viewport verification at 1280×720 and
  1440×900) was not re-attempted here; no dev server or browser was available in this
  environment, consistent with every prior phase in this project.

---

### 11. Final Verdict

Both in-scope MAX-7 findings (F-01, F-02) are implemented with the smallest correct
change in each case, verified against real source before and after, covered by
updated/new focused tests, and confirmed via diff to touch nothing outside their own
call sites. TypeScript and the full test suite pass clean.

```text
FRONTEND MAX-7 PHASE 2A — PASS
```

**Do not begin Phase 2B.**
