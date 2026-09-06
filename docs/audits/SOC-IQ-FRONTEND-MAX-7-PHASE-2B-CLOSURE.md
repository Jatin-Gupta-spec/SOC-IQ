# SOC-IQ Frontend MAX-7 — Phase 2B

## Navigation + Analyst Workflow Continuity — Implementation Closure

---

### 1. Executive Summary

This phase implemented the subset of `docs/audits/SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT.md`
that the Phase 2B brief scoped in: cross-page navigation, workflow continuity,
Analyze → Investigation, Investigation → Workspace, Workspace → Report, return paths,
action discoverability, and unnecessary navigation friction. MAX7-F-01 and MAX7-F-02
were already resolved in Phase 2A (deep-linking and URL-represented tab state,
respectively) and are unchanged here. Of the three findings that remained open after
Phase 2A (F-03, F-04, F-05), exactly one falls inside this phase's scope as an
*implementable, accepted* finding:

- **MAX7-F-05 (P3)** — `DataTable` already had a real, working whole-row-activation
  capability (`onRowActivate`/`isRowSelected`/`getRowAriaLabel`) that
  `DashboardRecentInvestigations.tsx` already used, but neither `InvestigationsPage.tsx`
  nor `ReportsPage.tsx` passed it — only the investigation-name link text inside each
  row was clickable/keyboard-reachable, not the row itself. This is squarely "action
  discoverability": a dense, scan-heavy SOC table where the expected affordance
  ("click anywhere on the row") existed as a built capability but wasn't wired up at
  either of its two real call sites.

**Findings deliberately not implemented, with the specific scope reasoning:**

- **MAX7-F-03 (P2)** — the audit files this under `Workflow: Investigate (discovery)`
  (§10, §18 of the audit) — it is about the *absence of search/filter/sort at the list
  level*, i.e. discovering which investigations exist, not about navigating between
  pages or workflow stages. Phase 2B's brief scopes in cross-page navigation, workflow
  continuity, and the named Analyze/Investigation/Workspace/Report transitions — it
  does not scope in list-level search, filter, or sort. This is the same category
  distinction Phase 2A's own closure already drew when it filed F-03 as "list-level
  discovery" and left it out of that phase's navigation/context-preservation scope;
  nothing in the Phase 2B brief revises that distinction, so F-03 remains unimplemented
  and untouched.
- **MAX7-F-04 (P2)** — the audit explicitly declines to prescribe a fix for this one:
  "not prescribed in detail per the audit-only mandate... Either is a real option; this
  audit does not pick one" (§8). Resolving the Reports/Investigations purpose overlap
  requires choosing between two materially different product directions (fold Export
  into Investigations and retire Reports, vs. keep both and differentiate Reports'
  copy/columns) — a product decision, not an engineering one the audit or this brief
  authorizes picking unilaterally. Implementing either direction without that decision
  being made first would be scope invention, not scope execution, so F-04 remains
  unimplemented and untouched.
- **No new findings were invented.** The Phase 2B brief's category list (return paths,
  Workspace → Report, etc.) was checked directly against the audit's own findings
  table (§18) and against a fresh read of the relevant source (`BackToInvestigationsButton`,
  `InvestigationWorkspacePage.tsx`'s not-found/error states, `ReportsPage.tsx`,
  `router.tsx`) rather than assumed to imply additional, undocumented defects. The
  audit found no finding in any of those categories beyond F-01/F-02/F-03/F-04/F-05 (all
  five are accounted for above), and this phase does not manufacture one to fill the
  brief's category list. See §4 for the specific re-verification performed.

**Implementation result:** the one accepted finding (F-05) was resolved by wiring
`DataTable`'s existing, unmodified `onRowActivate` capability at its two real call
sites (`InvestigationsPage.tsx`, `ReportsPage.tsx`), reusing the exact pattern already
proven by `DashboardRecentInvestigations.tsx` (plain `location.hash` navigation, not
`useNavigate()`, to preserve standalone rendering outside a `<Router>`). The existing
name-cell `<a href>` was left in place unchanged (middle-click / "open in new tab"
still works), and Reports' Export button was shielded with `stopPropagation` so
exporting a report never also navigates away from the page. `DataTable.tsx` itself —
the one "soft dependency" the audit flagged (§22) — was not modified; this is a
call-site-only change exactly as the audit's own recommended direction describes.
TypeScript and the full Vitest suite both pass clean. A source/diff audit against a
pristine second extraction of the Phase 2A baseline confirms changes are confined to
exactly four files, all inside `frontend/src/pages/` — zero changes to `app/`
(backend), `src-tauri/`, `database/`, `packaging/`, `router.tsx`, `DataTable.tsx`, or
any frontend system outside F-05's own two call sites.

```text
FRONTEND MAX-7 PHASE 2B — PASS
```

---

### 2. Baseline

- **Baseline checkpoint:** `SOC-IQ-FRONTEND-MAX-7-PHASE-2A-FULL.zip` (the verified
  Phase 2A implementation checkpoint — MAX7-F-01/F-02 resolved, all other systems
  frozen).
- **Baseline archive entries:** 797
- **`.git`:** absent from the baseline, consistent with every prior MAX phase in this
  project. As with every prior phase, all change-tracking in this phase was done by
  diffing the working tree against a second, untouched extraction of the same
  baseline ZIP, not by any Git mechanism.
- Read directly from the supplied baseline for this phase: the MAX-7 audit
  (`docs/audits/SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT.md`), the Phase 2A closure
  (`docs/audits/SOC-IQ-FRONTEND-MAX-7-PHASE-2A-CLOSURE.md`), and the MAX-6 closure
  (`docs/audits/SOC-IQ-FRONTEND-MAX-6-DESIGN-SYSTEM-CLOSURE.md`), per this phase's own
  process instructions — each confirmed present and byte-consistent with the
  standalone copies supplied alongside the baseline ZIP for this phase.

---

### 3. Scope

**In scope (per the Phase 2B brief):**

- Cross-page navigation
- Workflow continuity
- Analyze → Investigation
- Investigation → Workspace
- Workspace → Report
- Return paths
- Action discoverability
- Unnecessary navigation friction

**Findings resolved under that scope:** MAX7-F-05 (full write-up: audit §12).
MAX7-F-01/F-02 were already resolved in Phase 2A and are unchanged.

**Explicitly considered and left unimplemented, with reasoning:** MAX7-F-03
(list-level discovery, not navigation — see §1), MAX7-F-04 (product-direction decision,
not implementable without one being made — see §1). Backend/Python (`app/`),
Rust/Tauri (`src-tauri/`), database, packaging, `DataTable.tsx` itself, `router.tsx`,
and every other frontend system not directly implicated by F-05's own two call sites
were out of scope and confirmed untouched (§8). MAX-1 accessibility, MAX-2 loading,
MAX-3 responsive, MAX-4 motion, MAX-5 dashboard/data, MAX-6 design-system, and Phase
2A's own F-01/F-02 work were all preserved as frozen systems.

---

### 4. Findings Re-Verified Before Implementation (and Scope Boundary Checked)

**F-05, re-confirmed against this phase's actual source (not assumed from the audit's
own text):**

- `DataTable.tsx` (`frontend/src/pages/components/DataTable.tsx`) still exposes
  `onRowActivate`/`isRowSelected`/`getRowAriaLabel` exactly as documented — full read
  performed; **zero changes needed or made to this file**.
- `DashboardRecentInvestigations.tsx` was re-read in full and confirmed to be the one
  real, already-working consumer of `onRowActivate` in the codebase — its
  `activateRow`/`hasNavigableRow`/`getRowAriaLabel` pattern (plain
  `window.location.hash = \`/investigations/${id}\`` navigation, conditional
  `onRowActivate` inclusion, `getRowAriaLabel` always supplied) is the pattern this
  phase's F-05 implementation reuses verbatim at its two new call sites.
- Confirmed by direct `grep` that neither `InvestigationsPage.tsx` nor
  `ReportsPage.tsx` passed `onRowActivate` before this phase's change — exactly as the
  audit describes.

**Scope-boundary re-verification (the specific check behind the "no new findings
invented" claim in §1):**

- `InvestigationWorkspacePage.tsx`'s not-found/error states' `BackToInvestigationsButton`
  was re-read: it always returns to the generic `/investigations` list rather than
  wherever the analyst actually came from (Dashboard, Investigations, or Reports).
  The audit read this same code and explicitly recorded "No finding" against it (§9:
  "each with a Retry (error only) and a Back-to-Investigations action. No finding.").
  Phase 2B's brief lists "return paths" as an in-scope *category*, but implementing a
  fix here would mean inventing a new MAX7-F-06 finding this audit never raised, not
  implementing an *accepted* finding — outside this phase's "implement only accepted
  findings" instruction. Left untouched.
- `ReportsPage.tsx` was checked for any existing or missing Workspace → Report
  navigation affordance beyond what F-04 already covers (the Export column itself,
  and F-05's row-activation gap, now resolved). No additional, audit-documented defect
  was found in this transition.
- `router.tsx`'s catch-all redirect and the retired-route handling (audit §10, "Dead
  ends / duplicated navigation: none found") were re-read and confirmed unchanged and
  still correct — no new dead end introduced by this phase's own change.

---

### 5. Implementation

#### 5.1 MAX7-F-05 — Whole-row activation on Investigations and Reports

**Files:** `frontend/src/pages/InvestigationsPage.tsx`,
`frontend/src/pages/ReportsPage.tsx`

Both pages now pass `onRowActivate` (conditionally, only when at least one row has a
real `investigationId` — mirroring `DashboardRecentInvestigations.tsx`'s own
`hasNavigableRow` guard) and `getRowAriaLabel` to their `DataTable`. Activation
navigates via `window.location.hash = row.href.slice(1)` — the same plain
`location.hash` mechanism the existing name-cell link and
`DashboardRecentInvestigations.tsx` already use, not `useNavigate()`, preserving both
pages' existing ability to render standalone outside a `<Router>` (the documented
reason both pages already avoid `useNavigate()` for their name links).

```diff
  <DataTable
    caption="Investigations"
    columns={columns}
-   rows={normalizeInvestigationsList(investigations)}
+   rows={rows}
    getRowId={(row) => row.rowId}
+   {...(hasNavigableRow ? { onRowActivate: activateRow } : {})}
+   getRowAriaLabel={(row) => /* ... */}
  />
```

(and the equivalent change to `ReportsPage.tsx`'s own `DataTable` usage.)

The name cell's existing `<a href="#/investigations/{id}">` was left completely
unchanged in both pages — per the audit's own recommended direction ("keeping the
existing name `<a href>` inside the row... the two are not mutually exclusive"), it
still provides native middle-click / "open in new tab" behavior that a bare
`onRowActivate` alone would not.

**Reports' Export cell — the one interaction the audit's F-05 write-up didn't have to
address (Investigations has no equivalent):** `ReportsPage.tsx`'s Export column
contains a real `<Button>` (`ReportExportAction`), which — once the row itself became
click/Enter/Space-activatable — would otherwise have its click and keydown events
bubble up to the row's own `onRowActivate`/keyboard handling, causing "export this
report" to also silently navigate away from Reports mid-export. The Export cell is now
wrapped in a `<span>` that stops propagation of both `onClick` and `onKeyDown`, so the
Export button's own activation is fully shielded from the row's activation — the two
actions stay independent, exactly as they were before F-05 was wired up, with only the
new row-wide activation added on top.

```diff
  {
    key: "actions",
    header: "Export",
-   render: (row) => <ReportExportAction investigationId={row.investigationId} reportName={row.reportName} />,
+   render: (row) => (
+     <span onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
+       <ReportExportAction investigationId={row.investigationId} reportName={row.reportName} />
+     </span>
+   ),
  },
```

**What this deliberately did not change:**

- **`DataTable.tsx`:** zero edits. `onRowActivate`/`isRowSelected`/`getRowAriaLabel`,
  the interactive-row CSS class, `tabIndex`, `aria-selected`, and the existing
  Enter/Space keydown handling (with its own `preventDefault()`) are all exactly as
  MAX-6 confirmed them ("the strongest-documented shared component found") — this
  phase only adds two new call sites for an existing, unmodified capability.
- **`DashboardRecentInvestigations.tsx`:** read (for its established pattern), not
  modified.
- **MAX-1 keyboard semantics elsewhere in the app** (the Investigation Workspace's own
  `WorkspaceTabs`): entirely unrelated surface, not touched.
- **Phase 2A's F-01/F-02 work:** `AnalysisResultSummary.tsx`'s deep-link and
  `InvestigationWorkspacePage.tsx`'s URL-represented `activeTab` are untouched — see
  §8's diff confirming neither file appears in this phase's change set.

---

### 6. Preserved Systems

Confirmed untouched by this phase, by direct diff (§8) and by inspection:

- MAX-1 accessibility architecture (tab semantics, roving tabindex, keyboard handling)
- MAX-2 loading skeletons
- MAX-3 responsive/overflow CSS
- MAX-4 motion tokens/utilities
- MAX-5 Dashboard data contracts, including `DashboardRecentInvestigations.tsx` (read
  for its pattern, not modified)
- MAX-6 `Button`/`Card`/`DataTable`/`PageHeader` architecture — `DataTable.tsx` itself
  received zero edits (§5.1)
- Phase 2A's MAX7-F-01 (`AnalysisResultSummary.tsx`) and MAX7-F-02
  (`InvestigationWorkspacePage.tsx`)
- MAX7-F-03/F-04 (out of this phase's scope; not implemented — §1/§3)
- Backend/Python (`app/`), Rust/Tauri (`src-tauri/`), database, packaging, `router.tsx`

---

### 7. Tests

**Updated (2 files)** — both now opt into `@vitest-environment jsdom` (previously
plain-Node, `renderToStaticMarkup`-only) so real click/keydown events can be
dispatched; every pre-existing `renderToStaticMarkup`-based test in each file is
unaffected by this environment change and continues to pass unmodified:

- `frontend/src/pages/InvestigationsPage.test.tsx` — new `describe("InvestigationsPage
  row activation (MAX7-F-05)", ...)` block, mirroring `dashboard.test.tsx`'s
  established `act` + `createRoot` + native `dispatchEvent` convention:
  - opens the investigation on a click anywhere in a row (specifically a
    non-name-link cell, to prove whole-row activation), asserting on the *second*
    row's real investigation ID (not just the first) to prove the correct row's data
    is used
  - opens the correct row's investigation on Enter
  - opens an investigation on Space
  - still finds the name cell's real `<a href>` in the DOM (middle-click/open-in-new-tab
    preserved)
- `frontend/src/pages/ReportsPage.test.tsx` — new `describe("ReportsPage row
  activation (MAX7-F-05)", ...)` block, same conventions, plus the Export-shielding
  cases this page specifically needs:
  - opens the investigation on a click anywhere in a row
  - opens an investigation on Enter
  - **does NOT navigate when the row's Export button is clicked**
  - **does NOT navigate when Enter is pressed while the Export button is focused**
  - still finds the name cell's real `<a href>` in the DOM
  - the `ReportExportAction` mock itself was changed from a plain `<span>` to a real
    `<button>` so these tests can dispatch a genuine click/keydown on it and observe
    that propagation is actually stopped, not merely assume it.

All pre-existing tests in both files' original `describe("InvestigationsPage", ...)`
/ `describe("ReportsPage", ...)` blocks (loading/success/empty/error/page-structure/
CSV-export coverage) were run unmodified and continue to pass.

**Run results:**

```text
npx tsc --noEmit     → PASS (clean, zero errors)
npx vitest run       → PASS — 81 test files, 1152 tests, 0 failures
```

(1152 = Phase 2A's verified 1143 baseline tests + 9 new tests added by this phase: 4
in `InvestigationsPage.test.tsx`, 5 in `ReportsPage.test.tsx`.)

---

### 8. Phase 2A Regression Check

Re-ran the full Vitest suite (§7) against this phase's working tree, which includes
every Phase 2A test file unmodified:

- `frontend/src/pages/analyze/AnalysisResultSummary.test.tsx` (MAX7-F-01 coverage) —
  **passes unmodified**.
- `frontend/src/pages/AnalyzePage.execution.test.tsx` (MAX7-F-01 composed-page
  coverage) — **passes unmodified**.
- `frontend/src/pages/investigation/InvestigationWorkspacePage.test.tsx` (MAX7-F-02's
  full `"URL-represented tab state (MAX7-F-02)"` describe block, plus all pre-existing
  MAX-1 accessibility tests) — **passes unmodified**.

The diff audit below (§9) independently confirms `AnalysisResultSummary.tsx` and
`InvestigationWorkspacePage.tsx` are byte-identical to the Phase 2A baseline — Phase
2A's own source changes were not touched, let alone reverted, by this phase.

```text
Phase 2A regression: PASS
```

---

### 9. Source / Diff Audit

Diffed the full working tree against a second, untouched extraction of the baseline
ZIP (`SOC-IQ-FRONTEND-MAX-7-PHASE-2A-FULL.zip`). Excluding `frontend/node_modules`
(created by this phase's own `npm install`, required to run `tsc`/`vitest`, and
excluded from the delivered ZIP per §10), exactly four files differ, all under
`frontend/src/pages/`:

```text
frontend/src/pages/InvestigationsPage.tsx
frontend/src/pages/InvestigationsPage.test.tsx
frontend/src/pages/ReportsPage.tsx
frontend/src/pages/ReportsPage.test.tsx
```

No changes anywhere under `app/`, `src-tauri/`, `database/`, `packaging/`,
`keystore-core/`, `sidecar-core/`, `tests/`, or any other `frontend/src/` path —
including `router.tsx`, `DataTable.tsx`, `DashboardRecentInvestigations.tsx`,
`AnalysisResultSummary.tsx`, `InvestigationWorkspacePage.tsx`, and every other
MAX-1–MAX-6 and Phase-2A file — confirming no scope leakage beyond F-05's own two
call sites.

```text
Source integrity: PASS
```

---

### 10. Full Project ZIP

- **Filename:** `SOC-IQ-FRONTEND-MAX-7-PHASE-2B-FULL.zip`
- **Contents:** complete Phase 2B project state, excluding only
  `node_modules/`, `dist/`, `target/`, `__pycache__/`, `.pytest_cache/`, `coverage/`,
  `.vscode/`, `.idea/`, and any prior ZIP checkpoint (none were present in the working
  tree at any point in this phase — confirmed by search, §9).
- **No nested ZIP:** confirmed by search of the working tree before packaging (§9) —
  the Phase 2A ZIP was extracted to build this phase's baseline, not copied into it.
- Exact entry count, size, and SHA-256 are recorded in the final response accompanying
  this closure document (computed after archive creation, per this project's own
  established convention — see the identical hash-timing reasoning in the MAX-6 and
  MAX-7 Phase 1 closures) rather than duplicated here to avoid two sources of truth
  for the same figures.

---

### 11. Remaining Work

- MAX7-F-03 (list-level search/filter/sort) and MAX7-F-04 (Reports/Investigations
  purpose overlap) remain open, unimplemented, and out of this phase's scope — F-03
  is a discovery/list-level concern rather than a navigation/workflow-continuity one;
  F-04 requires a product-direction decision (merge vs. differentiate) this phase is
  not authorized to make unilaterally. Both remain available for a future phase once
  that scope or decision is explicitly extended/made.
- MAX-6's own carried-forward gap (rendered/viewport verification at 1280×720 and
  1440×900) was not re-attempted here; no dev server or browser was available in this
  environment, consistent with every prior phase in this project.

---

### 12. Final Verdict

The one accepted, in-scope MAX-7 finding remaining after Phase 2A (F-05) is
implemented with the smallest correct change — two call-site additions reusing an
existing, unmodified `DataTable` capability and an already-proven pattern from
`DashboardRecentInvestigations.tsx` — verified against real source before and after,
covered by new focused tests (including negative tests proving the Export action is
shielded from row activation), and confirmed via diff to touch nothing outside its own
two call sites. F-03 and F-04 were deliberately left unimplemented with documented
scope reasoning rather than assumed into scope to fill out the brief's category list.
Phase 2A's F-01/F-02 work is confirmed byte-identical and regression-free.
TypeScript and the full test suite pass clean.

```text
FRONTEND MAX-7 PHASE 2B — PASS
```

**Do not begin Phase 2C.**
