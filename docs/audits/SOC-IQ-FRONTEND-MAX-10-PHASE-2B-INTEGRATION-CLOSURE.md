# SOC-IQ Frontend MAX-10 — Phase 2B

## Highest-Leverage Direction Deepening & Integration — Closure

---

## 1. Executive Summary

Phase 2B deepens the exact direction Phase 2A implemented —
`DataTable` column sort (`MAX10-F-01`) — by extending it to the
Reports page's Status and Analyzed columns, which read the identical
fields (`status`, `analyzedAt`) from the identical underlying data
source (`useInvestigationsList()`) that the Investigations page
already sorts. `DataTable`'s sort mechanism was already generic and
opt-in per column from Phase 2A; Reports simply hadn't opted in yet,
which meant the same two data points behaved inconsistently — sortable
on one page, not on the other page showing the same values. Fixed with
a two-field change (`sortable: true` + `sortValue`) plus mirrored
tests. TypeScript clean, 1187/1187 tests passing (1180 baseline + 7
new), production build succeeds with an unchanged module count (201).

**Verdict: `MAX-10 PHASE 2B — COMPLETE`.**

---

## 2. Baseline Artifact

`SOC-IQ-FRONTEND-MAX-10-PHASE-2A-HIGHEST-LEVERAGE-HARDENING-FULL.zip`,
as supplied.

- `unzip -t` / extraction: no errors, 814 entries extracted cleanly.
- `docs/audits/SOC-IQ-FRONTEND-MAX-10-FORENSIC-AUDIT.md` and
  `docs/audits/SOC-IQ-FRONTEND-MAX-10-PHASE-2A-HIGHEST-LEVERAGE-CLOSURE.md`
  both present and read in full before any change was made.

---

## 3. MAX-10 Audit Direction

Unchanged from Phase 2A: `MAX10-F-01`, column sort on `DataTable`. The
audit's own recommendation text (forensic audit, §"Recommended
direction") explicitly scoped the *initial* implementation to the
Investigations list while noting sort is opt-in per column so other
`DataTable` consumers are unaffected until they choose to adopt it —
leaving the door open, by design, for later columns to opt in without
reopening the audit.

---

## 4. Phase 2A Capability

`DataTable` owns generic, reusable sort state and a stable comparator
(`compareSortValues` / `compareNonNullSortValues`) with direction-
independent null-last ordering, exposed to any consumer via two
optional column fields: `sortable: true` and a `sortValue` accessor.
Phase 2A opted the Investigations page's Status, Risk, and Analyzed
columns into this mechanism. No other `DataTable` consumer (Reports,
Dashboard's Recent Investigations widget, IOC Explorer, Threat Intel)
had opted in.

---

## 5. Phase 2B Gap

`ReportsPage` renders a Status column and an Analyzed column whose
values are the exact same `row.status` / `row.analyzedAt` fields as
`InvestigationsPage`'s sortable Status/Analyzed columns — both pages
consume the same `useInvestigationsList()` hook and the same
backend-sourced `InvestigationSummary` shape (`reportsViewModel.ts`'s
own doc comment: Reports is explicitly "the same real
`list_investigations` data `InvestigationsPage` already fetches").
Before this phase, an analyst could sort by status or date on
Investigations but not on Reports, despite looking at the same values
— an interaction-consistency gap directly caused by Phase 2A landing
on only one of two pages that share this data, not a new, unrelated
finding.

Two other `DataTable` consumers were inspected and **not** changed,
because neither shares Phase 2A's evidence bar:

- **Dashboard's "Recent Investigations" widget**
  (`DashboardRecentInvestigations.tsx`) — a small, fixed-length
  preview list whose whole purpose is showing the most-recently
  analyzed items in recency order; adding sort would work against the
  widget's own intent and its row count is too small for reordering
  to carry analyst value. Left unchanged.
- **IOC Explorer / Threat Intel indicator tables**
  (`InvestigationIocWorkspace.tsx`, `InvestigationThreatIntel.tsx`) —
  a genuinely different data domain (IOC type/confidence/verdict, not
  status/date), not the same fields Phase 2A already sorts elsewhere.
  Adding sort there would be a new, freestanding decision each with
  its own evidence case, not a deepening of the one direction Phase 2A
  established. Deferred, not addressed.

---

## 6. Primary Analyst Workflow

"Sort a list of investigation-derived data by status or date" — now
consistent whether the analyst is looking at that data from the
Investigations page or the Reports page, instead of being possible on
one and not the other.

---

## 7. Affected Surfaces

- `frontend/src/pages/ReportsPage.tsx`
- `frontend/src/pages/ReportsPage.test.tsx`

No other surface met the Phase 2B evidence bar (see §5).

---

## 8. Required Changes

1. Mark `ReportsPage`'s `status` column `sortable: true` with
   `sortValue: (row) => row.status` — identical accessor shape to
   `InvestigationsPage`'s Status column.
2. Mark `ReportsPage`'s `analyzed` column `sortable: true` with
   `sortValue: (row) => row.analyzedAt` — identical accessor shape to
   `InvestigationsPage`'s Analyzed column (same ISO 8601 string field,
   same reason plain string comparison is correct without Date
   parsing).
3. Add a mirrored `describe("ReportsPage column sort (Phase 2B)", ...)`
   test block, adapted from `InvestigationsPage.test.tsx`'s sort
   block, covering: sortable-header rendering with initial
   `aria-sort="none"`, non-sortable headers (Report/Export) staying
   plain, ascending sort, descending toggle, chronological sort,
   sort-state reset when switching columns, and composition with the
   active search filter.

No change to `DataTable.tsx` itself — the sort mechanism Phase 2A
built already supports this without modification, which is itself
evidence that Phase 2A's design was sound: opting in a second consumer
required zero changes to the shared component.

---

## 9. Explicitly Deferred

- Sort on Dashboard's Recent Investigations widget — see §5.
- Sort on IOC Explorer / Threat Intel tables — see §5.
- `MAX9-F-01` (stale `package.json` description, P3) — untouched,
  carried forward unchanged, no new evidence bears on it this phase
  either.
- The live browser/visual verification gap — still an environment
  limitation, not something a Phase 2B engineering pass can close (see
  §15, §16, §25).

---

## 10. Expected Improvement

An analyst who has learned "click Status/Analyzed to sort" on the
Investigations page gets the same behavior on Reports without having
to discover a second, inconsistent interaction model for the same
underlying data — a small but real reduction in the "which page
behaves how" tax data-grid users pay when only one of two similar
tables is sortable.

---

## 11. Implementation Details

`ReportsPage`'s column array already used `DataTableColumn<ReportsListRow>`
— the same generic type `InvestigationsPage` uses — so the change is
two added fields per column, no new types, no new state, no new
component. `DataTable`'s existing `useMemo`-based sort continues to
operate on whatever `rows` it's given, which for `ReportsPage` is
already `filteredRows` (the post-search/status-filter set), so sort
composes with the existing toolbar exactly as it does on
Investigations — verified by test (§13, last case).

Diff, in full:

```diff
   {
     key: "status",
     header: "Status",
     render: (row) => <StatusBadge label={row.status} tone={row.statusTone} />,
+    sortable: true,
+    sortValue: (row) => row.status,
   },
-  { key: "analyzed", header: "Analyzed", render: (row) => row.analyzedAt },
+  {
+    key: "analyzed",
+    header: "Analyzed",
+    render: (row) => row.analyzedAt,
+    sortable: true,
+    sortValue: (row) => row.analyzedAt,
+  },
```

(Doc comments explaining the mirrored-field rationale are inline in
the source; omitted here for brevity.)

---

## 12. Analyst Workflow Impact

Reports' Status and Analyzed columns now behave identically to
Investigations' — ascending on first click, descending on second,
`aria-sort` reflecting state, composes with the existing search box.
Report (name) and Export remain plain, non-interactive headers,
matching Investigations' own scope decision to leave the name column
unsorted.

---

## 13. Cross-Surface Integration

Only Reports and Investigations are affected by this phase; they now
present the same two data points with the same interaction. Dashboard,
Analyze, Investigation Workspace, and Settings were inspected (per the
task brief's cross-surface-integration instruction) and found to have
no demonstrable relationship to this direction — none of them render a
Status/Analyzed pair backed by this same data through `DataTable`, so
none were touched.

---

## 14. State Preservation

No new state to preserve across navigation — sort state lives inside
each page's own `DataTable` instance exactly as it did for
Investigations in Phase 2A (component-local `useState`, reset on
remount), and that was an intentional, unchanged design choice: sort
is a view preference for the current page visit, not identity a
returning analyst needs restored. Nothing in this phase alters that.

---

## 15. Error/Empty/Recovery Behavior

Not applicable, unchanged from Phase 2A's own §16 finding for the same
reason: sort operates only on already-loaded, already-filtered rows.
`ReportsPage`'s existing loading/error/empty/filtered-empty states were
re-run under the full suite (§18) and are untouched — no new fetch, no
new async state, no new error surface was introduced.

---

## 16. Accessibility

- **Semantics:** identical native `<button>`-inside-`<th scope="col">`
  pattern Phase 2A already established; no new ARIA reimplementation.
- **`aria-sort`:** `"ascending"`/`"descending"` on the active column,
  `"none"` on the other sortable column, entirely omitted on Report
  and Export — matching Phase 2A's own rule and verified by test.
- **Keyboard:** native `<button>` Enter/Space activation, unchanged.
- **Focus:** relies on the existing global `:focus-visible` rule; no
  local override added.

Status: **STATIC VERIFIED** (source/markup-level; no browser or
screen-reader session was available in this environment — see §25).

---

## 17. Responsive

No layout structure changed. The sort button reuses the exact same
`DataTable.css` rules Phase 2A added — no new CSS was written for this
phase, since Reports uses the same `DataTable` component instance
type. `ReportsPage.css` was not touched.

Status: **STATIC VERIFIED** at the source/CSS level for both `1440×900`
and `1280×720`; **ENVIRONMENT-BLOCKED** for an actual rendered check —
the same standing limitation restated (not newly discovered) in every
prior MAX phase and Phase 2A itself.

---

## 18. Motion

None. No animation, transition, or motion token touched. The sort icon
swap (⇅ → ▲/▼) is the same discrete, non-animated state change Phase
2A already established; not applicable rather than a gap.

---

## 19. Design-System Consistency

Zero new tokens, zero new CSS, zero new dependency. This phase reuses
`DataTable.tsx`/`DataTable.css` exactly as Phase 2A left them — the
strongest possible design-system-consistency outcome, since there was
nothing new to keep consistent.

---

## 20. Performance Considerations

No new re-render surface: `sortedRows` is computed by `DataTable`'s
existing `useMemo` keyed on `[rows, sortState, columns]`, unchanged
from Phase 2A. `ReportsPage`'s own `columns` array is a module-level
constant (as it was before), so no new unstable dependency was
introduced by adding the two fields. No memoization, virtualization,
or other optimization mechanism was added — none was needed.

---

## 21. Test Results

```text
$ npx tsc --noEmit
(no output — clean)

$ npx vitest run
Test Files  82 passed (82)
     Tests  1187 passed (1187)
  Duration  93.86s

$ npx vite build
✓ 201 modules transformed.
✓ built in 4.59s
```

1180 baseline (Phase 2A's own re-run total) + 7 new `ReportsPage`
sort tests = 1187, all passing, all re-run fresh in this phase. Module
count (201) is identical to Phase 2A's own build — no new module was
introduced, consistent with reusing `DataTable` unchanged.

New tests cover: sortable-header rendering with initial `aria-sort`
state, non-sortable headers (Report/Export) staying plain, ascending
sort with verified row order, descending toggle, chronological
Analyzed sort, sort-state reset when switching the active column, and
composition with an active search filter.

---

## 22. TypeScript Result

**Clean. 0 errors.**

---

## 23. Production Build Result

**Succeeded.** 201 modules transformed — unchanged from Phase 2A's own
build, confirming no new module was pulled in by this change.

---

## 24. Regression Review

Diff-audited the full working tree against a fresh, untouched
extraction of the Phase 2A baseline ZIP:

```text
Files pristine/frontend/src/pages/ReportsPage.tsx and extracted/frontend/src/pages/ReportsPage.tsx differ
Files pristine/frontend/src/pages/ReportsPage.test.tsx and extracted/frontend/src/pages/ReportsPage.test.tsx differ
```

Exactly the 2 files listed in §7/§8 differ. No backend Python, no Rust
(`sidecar-core`, `keystore-core`, `src-tauri`), no packaging script, no
`DataTable.tsx`/`.css`, no `InvestigationsPage.tsx`, no other frontend
page or component, and no dependency manifest changed.

- **MAX-6 (design system):** no token, no component API change beyond
  the two optional fields Phase 2A already added. No regression.
- **MAX-7 (analyst workflow):** Reports' existing search/filter/export/
  row-activation behavior re-verified passing, unchanged. No
  regression.
- **MAX-8 (production readiness):** build succeeds, module count
  unchanged. No regression.
- **MAX-9 (analyst UX/navigation/recovery):** no navigation, loading,
  error, or recovery path touched. No regression.
- **MAX-10 Phase 2A (sort on Investigations):** `InvestigationsPage.tsx`,
  `InvestigationsPage.test.tsx`, `DataTable.tsx`, and `DataTable.css`
  are byte-identical to the supplied baseline per the diff above. No
  regression.

**Scope compliance: PASS.**

---

## 25. Environment Limitations

Unchanged from every prior MAX phase, Phase 2A included:

- No browser or dev server available in this environment — all
  accessibility/responsive/motion conclusions above are
  **STATIC VERIFIED**, never an observed rendering.
- No Rust toolchain available — not relevant to this phase (no Rust
  file was touched).

---

## 26. Remaining Conditions

1. `MAX9-F-01` (stale `package.json` description, P3) remains open,
   unchanged.
2. The live browser/visual verification gap remains unperformed, as it
   has across every MAX cycle including Phase 2A — a standing
   infrastructure recommendation, not a defect introduced or left by
   this phase's work.
3. Sort on the Dashboard "Recent Investigations" widget and on the IOC
   Explorer / Threat Intel tables was considered and explicitly not
   implemented (§5, §9) — either because it works against the
   surface's own intent (Dashboard) or because it would be a new,
   freestanding direction rather than a deepening of `MAX10-F-01`
   (IOC/Threat Intel). Not a gap in this phase; a scope boundary.

---

## 27. Final Verdict

The one demonstrable Phase 2B gap in the Phase 2A direction —
identical sortable data inconsistently sortable across two pages — was
closed with a minimal, evidence-backed, two-file change. No
architecture changed, no unrelated surface was touched, and the diff
against the untouched Phase 2A baseline proves it. All automated
verification was re-run fresh in this phase and passed cleanly.

```text
MAX-10 PHASE 2B — COMPLETE
```

---

## Hard Stop

Phase 2B is complete. Per the task brief's own rule, this phase does
not automatically continue to Phase 2C or any further MAX-10 work.
Awaiting explicit direction before any further work on this project.
