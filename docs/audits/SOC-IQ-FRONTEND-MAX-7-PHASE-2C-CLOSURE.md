# SOC-IQ Frontend MAX-7 — Phase 2C

## Error + Empty + Search/Filter/Table + Recovery Hardening — Implementation Closure

---

### 1. Executive Summary

This phase implemented the subset of `docs/audits/SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT.md`
(Phase 1, audit-only) that the Phase 2C brief scoped in: findings involving error
recovery, retry behavior, empty states, search, filtering, sorting, table interaction,
selection, and actionable feedback. Re-reading the audit against that scope (§4 below)
found exactly **one** accepted, unimplemented finding inside it:

- **MAX7-F-03 (P2)** — neither the Investigations table nor the Reports table exposed
  a search box, column filter, or sort control, so the only way to reach a specific
  investigation by name/status/severity was to visually scan the full table.

Two categories inside this phase's scope were checked and found to already be in good
shape by the audit itself, with **no finding** attached to them, so nothing was
implemented for them:

- **Error & Recovery (audit §13):** every page's error state already prefers the
  backend's own real error message, offers a `retry()` that re-runs the same request
  without losing the analyst's place, and uses the shared `Button` primitive
  (MAX-6). The audit explicitly recorded "No P0/P1 recovery finding" here — re-verified
  unchanged in this phase's own source read (§4).
- **Empty States (audit §14):** every empty state read explains why the section is
  empty and surfaces a next action inline where one exists. The audit explicitly
  recorded "No finding" here — re-verified unchanged.

**Selection** and **actionable feedback**, also named in this phase's scope, have no
standalone audit finding either: row selection already exists where the audit found it
warranted (`InvestigationIocWorkspace.tsx`, pre-existing), and MAX7-F-05 (whole-row
activation, the audit's own "interaction problem" finding for Investigations/Reports)
was already resolved in Phase 2B. Implementing selection on the Investigations/Reports
list tables themselves would have been inventing a MAX7-F-06 this audit never raised —
explicitly out of scope per this project's own established discipline (see Phase
2B closure §4, which drew the identical line for a different unraised finding).

**MAX7-F-04** (Reports/Investigations purpose overlap) remains explicitly out of scope:
it is a product-direction decision (merge vs. differentiate), not an error/empty/
search/filter/table/selection/feedback finding, and Phase 2B's closure already
documented why implementing it without a decision would be scope invention.

**Implementation result:** MAX7-F-03 was resolved on both `InvestigationsPage.tsx` and
`ReportsPage.tsx` by adding a client-side search input plus a status filter above each
table — mirroring the audit's own recommended direction ("reusing the IOC workspace's
own already-proven search/filter UI pattern") — while leaving `DataTable` itself,
every backend filtering contract, and Phase 2A/2B/MAX-1–MAX-6 untouched. No sort
capability was added: `DataTable` has none today, and both this phase's brief and the
audit's own §22 dependency note treat extending it as a separate, unauthorized
decision, not something this finding's fix requires. TypeScript and the full Vitest
suite both pass clean. A source/diff audit against a pristine second extraction of the
Phase 2B baseline confirms changes are confined to exactly six files, all inside
`frontend/src/pages/` — zero changes to `app/` (backend), `src-tauri/`, `database/`,
`packaging/`, `DataTable.tsx` itself, or any frontend system outside the one in-scope
finding's own call sites.

```text
FRONTEND MAX-7 PHASE 2C — PASS
```

---

### 2. Baseline

- **Baseline checkpoint:** `SOC-IQ-FRONTEND-MAX-7-PHASE-2B-FULL.zip` (the Phase 2B
  implementation checkpoint — MAX7-F-01/F-02/F-05 resolved, F-03/F-04 unimplemented
  with documented reasoning, all other systems frozen and confirmed untouched by
  Phase 2B's own closure).
- **`.git`:** absent from the baseline, consistent with every prior MAX phase in this
  project. As with Phase 2A/2B, all change-tracking in this phase was done by diffing
  the working tree against a second, untouched extraction of the same baseline ZIP,
  not by any Git mechanism.

---

### 3. Scope

**In scope (per the Phase 2C brief):**

- Error recovery
- Retry behavior
- Empty states
- Search
- Filtering
- Sorting
- Table interaction
- Selection
- Actionable feedback

**Findings resolved under that scope:** MAX7-F-03 (full write-up: audit §10/§12).

**Explicitly considered and left unimplemented, with reasoning:**

- **Error & Recovery / Empty States** — the audit found no finding in either category
  (§13/§14, re-verified §4 below); there is nothing to implement.
- **Selection / actionable feedback** — no audit finding names either as a gap on
  Investigations/Reports; row selection already exists where audited as warranted
  (`InvestigationIocWorkspace.tsx`), and adding it to the list tables would be
  inventing new scope this audit never raised.
- **Sorting** — explicitly named in this phase's scope, but the audit's own MAX7-F-03
  write-up and its §22 dependency note both treat `DataTable` sort capability as a
  separate, not-pre-authorized extension; this phase's brief also explicitly forbids
  redesigning `DataTable`. No sort was added.
- **MAX7-F-04** — a product-direction decision (merge vs. differentiate Reports and
  Investigations), not an error/search/table finding; remains open per Phase 2B's own
  documented reasoning, unchanged here.

MAX-1 accessibility, MAX-2 loading, MAX-3 responsive, MAX-4 motion, MAX-5 dashboard/
data, MAX-6 design-system work, and Phase 2A's/2B's own F-01/F-02/F-05 work were all
preserved as frozen systems (§6 below).

---

### 4. Findings Re-Verified Before Implementation (and Scope Boundary Checked)

**F-03, re-confirmed against this phase's actual source (not assumed from the audit's
own text):** grepped `InvestigationsPage.tsx` and `ReportsPage.tsx` and confirmed
neither had any search/filter local state, any `<input type="search">`, or any
`<select>` before this phase's change — matching the audit's "no search box, a column
filter, or a sortable header" description exactly. Confirmed `DataTable.tsx` still has
no sort-related prop of any kind (`DataTableColumn` has only `key`/`header`/`render`),
matching the audit's and Phase 2B's own re-confirmation.

**Error & Recovery, re-checked for a Phase 2C-relevant regression or newly-visible
gap:** re-read `InvestigationsPage.tsx`'s and `ReportsPage.tsx`'s `state === "error"`
branches — both still call the shared `Button` primitive's `retry`, still prefer the
backend's own `Error.message` via their respective `describe*ListError()` helpers, and
neither was touched by Phase 2A's or 2B's own changes. No new gap found; this phase's
own F-03 addition does not touch either branch (the search/filter toolbar only renders
inside the `state === "success"` branch, confirmed in the implementation below).

**Empty States, re-checked for the same reason:** the real-empty messages ("No
investigations found." / "No reports available. Analyze a report from the Analyze page
to see it here.") are unchanged by this phase — F-03's new "no matches" state is a
*third*, distinct state (real data present, current filter matches none of it), not a
replacement for either existing one. This mirrors the IOC workspace's own three-way
empty/unavailable/filtered-empty distinction (audit §12) exactly, extended to a second
surface rather than re-invented.

**Command Palette:** the audit's MAX7-F-03 write-up also names
`CommandPaletteContainer.tsx`/`commandRegistry.ts` as a location, but its own
"Recommended direction" is explicit that "the lowest-effort path is a client-side
search/filter box on Investigations... before considering command-palette or
backend-driven search." This phase implements that lowest-effort path only; the
Command Palette itself (`COMMANDS` derived from the five static `NAVIGATION_ITEMS`)
was read, confirmed unrelated to this phase's change, and left untouched.

---

### 5. Implementation

#### 5.1 MAX7-F-03 — Search/filter on Investigations

**Files:** `frontend/src/pages/InvestigationsPage.tsx`, `frontend/src/pages/InvestigationsPage.css`

A search input (matches `reportName`/`status`/`severity`, case-insensitive substring)
and a status `<select>` (options derived from the statuses actually present in the
loaded rows — never a hard-coded vocabulary that could offer a guaranteed-empty
option, mirroring the IOC workspace's identical rule) now sit above the table,
rendered only once real, non-empty investigation data exists — matching the IOC
workspace's own "toolbar only appears once a real dataset exists" convention exactly.

- **Filtering is local, derived state** (`useState` + `useMemo` over the rows
  `normalizeInvestigationsList()` already produces) — no second fetch, no
  `runCommand()`, no mutation of the normalized rows (`.filter()` only, never
  `.sort()` or in-place mutation).
- **"Clear filters"** appears only while a filter is active and resets both fields in
  one action, mirroring the IOC workspace's identical control.
- **A live "Showing X of Y investigations" count** sits in the toolbar.
- **A third, honest empty state** — "No investigations match your filters." (via the
  shared `InfoNote` primitive, the same one the IOC workspace's own filtered-empty
  state already uses) plus its own "Clear filters" action — renders when real rows
  exist but the current search/status combination matches none of them. This is never
  conflated with the pre-existing "No investigations found." real-empty message, which
  is unchanged and still governs the genuinely-empty-result case.
- **MAX7-F-05 (Phase 2B) is preserved exactly**: `onRowActivate`/`getRowAriaLabel` are
  now computed over `filteredRows` instead of the full row set (so whole-row activation
  keeps working correctly on a filtered view), using the identical `activateRow`
  function Phase 2B introduced, unchanged.

#### 5.2 MAX7-F-03 — Search/filter on Reports

**Files:** `frontend/src/pages/ReportsPage.tsx`, `frontend/src/pages/ReportsPage.css`

The identical pattern, applied to `ReportsPage.tsx`'s own row shape. Since
`ReportsListRow` carries no `severity` field (`reportsViewModel.ts`'s own doc comment:
severity/risk/confidence are intentionally not carried onto this page), the search
here matches `reportName`/`status` only — never inventing a field the page's real data
doesn't have. The Export column's own click/keydown-shielding from `onRowActivate`
(Phase 2B, `event.stopPropagation()`) is untouched and re-verified working against a
filtered row set (§7).

**What this deliberately did not change:**

- **`DataTable.tsx`:** zero edits. Both pages' toolbars are call-site-only additions
  built from plain HTML `<input>`/`<select>`/`<button>` elements, the same pattern the
  IOC workspace's own toolbar already established outside `DataTable` — no sort prop,
  no selection prop, no new `DataTable` capability of any kind.
- **Backend filtering contracts:** no change to `list_investigations`, its DTO, or any
  `runCommand()` call — both pages still fetch via the unmodified
  `useInvestigationsList()` hook and filter only the already-fetched, already-normalized
  rows client-side.
- **Phase 2A's F-01/F-02 work:** `AnalysisResultSummary.tsx`'s deep-link and
  `InvestigationWorkspacePage.tsx`'s URL-represented tab state are untouched (confirmed
  by the diff audit, §8).
- **Phase 2B's F-05 work:** `activateRow`, the Export-cell propagation shield, and the
  row-activation test coverage in both pages are all preserved, only re-scoped to
  operate over `filteredRows` rather than the unfiltered row set.
- **MAX-1 accessibility:** neither table's row semantics, `tabIndex`, or keyboard
  handling changed — `DataTable`'s own interactive-row wiring (untouched) still owns
  all of that; the toolbar's own `<input>`/`<select>`/`<button>` elements use native,
  unmodified keyboard behavior (Tab/Enter/Space), with real `<label htmlFor>` pairing
  for both the search input and the status filter on each page.

---

### 6. Preserved Systems

Confirmed untouched by this phase, by direct diff (§8) and by inspection:

- MAX-1 accessibility architecture (tab semantics, roving tabindex, keyboard handling)
- MAX-2 loading skeletons
- MAX-3 responsive/overflow CSS
- MAX-4 motion tokens/utilities
- MAX-5 Dashboard data contracts
- MAX-6 `Button`/`Card`/`DataTable`/`PageHeader` architecture — `DataTable.tsx` itself
  has zero changes this phase
- Phase 2A's MAX7-F-01 (`AnalysisResultSummary.tsx`) and MAX7-F-02
  (`InvestigationWorkspacePage.tsx`)
- Phase 2B's MAX7-F-05 (`activateRow`/Export-cell shielding on both pages, reused
  unchanged)
- MAX7-F-04 (out of this phase's scope; not implemented)
- Backend/Python (`app/`), Rust/Tauri (`src-tauri/`), database, packaging

---

### 7. Tests

**Updated (2 files)** — both files' existing `describe("InvestigationsPage", ...)` /
`describe("ReportsPage", ...)` and MAX7-F-05 row-activation blocks were re-run
unmodified and continue to pass against the new filtered-row-set behavior; no existing
test assertion was changed.

**Added (new `describe` block, 1 per page):**

- `frontend/src/pages/InvestigationsPage.test.tsx`, `"InvestigationsPage search/filter
  (MAX7-F-03)"`, mirroring `InvestigationIocWorkspace.test.tsx`'s established
  native-input-setter + `dispatchEvent` idiom (no testing-library dependency added):
  - renders a search input and status filter once real investigations exist
  - does not render the toolbar for a genuinely empty result
  - narrows the table by search text across name/status/severity
  - narrows the table using the status filter
  - shows the distinct "No investigations match your filters." state (and not the
    real-empty message) when the filter matches nothing
  - "Clear filters" resets both fields and restores every row
  - shows a live "Showing X of Y investigations" count
- `frontend/src/pages/ReportsPage.test.tsx`, `"ReportsPage search/filter
  (MAX7-F-03)"`, the identical set adapted to Reports' name/status-only row shape,
  plus one additional case confirming the Export action still renders correctly
  against a filtered row.

**Run results:**

```text
npx tsc --noEmit     → PASS (clean, zero errors)
npx vitest run       → PASS — 81 test files, 1166 tests, 0 failures
```

(Executed in this environment as `npx tsc --noEmit` / `npx vitest run` after
`npm install`; equivalent to the `npm.cmd` invocations on a Windows dev machine.)

---

### 8. Phase 2A / Phase 2B Regression Check

Re-run in full as part of the single `npx vitest run` above (no separate invocation
needed — both phases' test files are part of the same 81-file/1166-test run):

- `frontend/src/pages/analyze/AnalysisResultSummary.test.tsx` (MAX7-F-01 coverage) —
  unaffected, file not touched this phase.
- `frontend/src/pages/AnalyzePage.execution.test.tsx` (MAX7-F-01 composed-page
  coverage) — unaffected, file not touched this phase.
- `frontend/src/pages/investigation/InvestigationWorkspacePage.test.tsx` (MAX7-F-02's
  `"URL-represented tab state (MAX7-F-02)"` block) — unaffected, file not touched this
  phase.
- `frontend/src/pages/InvestigationsPage.test.tsx` / `ReportsPage.test.tsx`'s existing
  `"...row activation (MAX7-F-05)"` blocks — re-run against this phase's changed files
  and still pass: whole-row activation, keyboard activation, and the Export-cell
  propagation shield all continue to work correctly, now operating over the (by
  default, unfiltered) `filteredRows` set.

```text
Phase 2A regression: PASS
Phase 2B regression: PASS
```

---

### 9. Source / Diff Audit

Diffed the full working tree against a second, untouched extraction of the baseline
ZIP (`SOC-IQ-FRONTEND-MAX-7-PHASE-2B-FULL.zip`). Excluding `frontend/node_modules`
(created by this phase's own `npm install`, required to run `tsc`/`vitest`, and
excluded from the delivered ZIP per §10), exactly six files differ, all under
`frontend/src/pages/`:

```text
frontend/src/pages/InvestigationsPage.css
frontend/src/pages/InvestigationsPage.test.tsx
frontend/src/pages/InvestigationsPage.tsx
frontend/src/pages/ReportsPage.css
frontend/src/pages/ReportsPage.test.tsx
frontend/src/pages/ReportsPage.tsx
```

`frontend/package-lock.json` was diffed separately and confirmed byte-identical
(`npm install` reused the existing lockfile without modification).

No changes anywhere under `app/`, `src-tauri/`, `database/`, `packaging/`,
`keystore-core/`, `sidecar-core/`, `tests/`, `frontend/src/pages/components/DataTable.tsx`,
or any other `frontend/src/` path (including `router.tsx`, every Phase 2A/2B file,
`InvestigationIocWorkspace.tsx`, `commandRegistry.ts`, `CommandPaletteContainer.tsx`,
and every MAX-1–MAX-6 shared component) — confirming no scope leakage beyond the one
in-scope finding's own call sites.

```text
Source integrity: PASS
```

---

### 10. Full Project ZIP

- **Filename:** `SOC-IQ-FRONTEND-MAX-7-PHASE-2C-FULL.zip`
- **Contents:** complete Phase 2C project state, excluding only
  `node_modules/`, `dist/`, `target/`, `__pycache__/`, `.pytest_cache/`, `coverage/`,
  `.vscode/`, `.idea/`, and any prior ZIP checkpoint (none were present in the working
  tree at any point in this phase — confirmed by search, §9). No Phase 2A or Phase 2B
  ZIP is nested inside this archive.
- Exact entry count, size, and SHA-256 are recorded in the final response accompanying
  this closure document (computed after archive creation, per this project's
  established ZIP-verification procedure, identical reasoning to Phase 2A/2B's own
  closures) rather than duplicated here to avoid two sources of truth for the same
  figures.

---

### 11. Remaining Work

- **MAX7-F-04** (Reports/Investigations purpose overlap) remains open, unimplemented,
  and out of this phase's scope — it is a product-direction decision, not an
  error/search/table finding, per Phase 2B's own documented reasoning (unchanged here).
- **`DataTable` sort capability** does not exist and was not added — extending
  `DataTable` to support column sorting remains a real, not-pre-authorized dependency
  (audit §22), explicitly out of scope per this phase's own brief ("Do NOT redesign
  DataTable").
- **Command-palette-driven investigation search** (jumping to a specific investigation
  from anywhere in the app, not just from the Investigations/Reports pages themselves)
  was not implemented — the audit's own recommended direction treats the client-side
  list-level search implemented in this phase as the lower-effort first step, with
  command-palette integration as a later, separate decision.
- MAX-6's own carried-forward gap (rendered/viewport verification at 1280×720 and
  1440×900) was not re-attempted here; no dev server or browser was available in this
  environment, consistent with every prior phase in this project.

---

### 12. Final Verdict

The one accepted, in-scope MAX-7 finding remaining after Phase 2B (F-03) is
implemented on both Investigations and Reports, verified against real source before
and after, covered by new focused tests mirroring the project's own established IOC
workspace search/filter test conventions, and confirmed via diff to touch nothing
outside its own two call sites plus their stylesheets and tests. Error & Recovery and
Empty States were re-checked against this phase's own scope and re-confirmed to have
no outstanding finding, per the audit's own §13/§14. TypeScript and the full test
suite pass clean. Phase 2A's and Phase 2B's own work is confirmed byte-identical and
regression-free.

```text
FRONTEND MAX-7 PHASE 2C — PASS
```

**Do not begin Phase 2D.**
