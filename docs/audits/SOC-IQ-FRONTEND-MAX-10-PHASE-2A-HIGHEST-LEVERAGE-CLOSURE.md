# SOC-IQ Frontend MAX-10 — Phase 2A

## Highest-Leverage Product Direction Hardening — Closure

---

## 1. Executive Summary

Phase 2A implemented the single direction the MAX-10 Phase 1 forensic
audit identified as highest-leverage: **column sort on the Investigations
`DataTable`** (`MAX10-F-01`). Nothing else was touched. The change is
additive, opt-in per column, and reuses `DataTable`'s existing
delegated-state ownership pattern rather than introducing a second state
mechanism. All automated verification re-run fresh this phase: TypeScript
clean, 1180/1180 tests passing (1172 baseline + 8 new), production build
succeeds with an unchanged module count (201).

**Verdict: `MAX-10 PHASE 2A — COMPLETE`.**

---

## 2. Baseline Artifact

`SOC-IQ-FRONTEND-MAX-10-FORENSIC-AUDIT-FULL.zip`, as supplied.

- `unzip -t`: no errors detected.
- Extracted cleanly.
- **Note:** the archive's internal top-level directory is named
  `SOC-IQ-FRONTEND-MAX-5-DASHBOARD-FULL`, not MAX-10. This is a
  labeling inconsistency in the upload, not a content problem — the
  correct MAX-10 forensic audit document was present and complete at
  `docs/audits/SOC-IQ-FRONTEND-MAX-10-FORENSIC-AUDIT.md`, dated after
  and referencing every MAX-9 artifact as its own baseline. Recorded
  here for traceability; not treated as a scope or provenance defect.

---

## 3. MAX-10 Audit Recommendation

Read in full: `docs/audits/SOC-IQ-FRONTEND-MAX-10-FORENSIC-AUDIT.md`.

The audit found **zero P0 and zero P1 findings**. Its one P2 finding,
`MAX10-F-01`, was explicitly named the recommended MAX-10 direction
(§26–27 of the audit): add column sort to `DataTable`, scoped to the
Investigations list's Status/Risk/Analyzed columns — a gap
twice-deferred across MAX-8 and MAX-9 purely on scope-authorization
grounds, not on merit.

Two other candidates were ranked and explicitly **not** selected by the
audit itself:
- Live browser/visual verification — not a coding task; an environment
  gap, not something a MAX-10 engineering phase can close.
- Moving Timeline to its own workspace tab — INFO-level only, no
  usage-volume evidence meeting the audit's own evidence bar.

Phase 2A followed the audit's selection exactly.

---

## 4. Selected Product Direction

Implement ascending/descending column sort on `DataTable`, applied to
the Investigations list's **Status**, **Risk**, and **Analyzed**
columns only — the exact scope the audit named. Investigation
(name), Severity, and Confidence remain unsorted, matching
`MAX10-F-01`'s own scope statement.

---

## 5. Problem Being Solved

An analyst viewing the Investigations list could not reorder it by
status, date, or risk from the UI. For a list-based triage surface,
column sort is a conventional expectation of any professional data
grid; its absence was a genuine, if modest, recurring efficiency cost.

---

## 6. Evidence Supporting the Direction

Direct source read of `DataTable.tsx` (pre-change): no sort state, no
sort handler, no header sort affordance existed anywhere in the
component. The gap was independently noted and explicitly deferred in
MAX-9 Phase 2C's own closure document before this audit treated it as
a first-class, evidence-backed finding.

---

## 7. Scope

- `frontend/src/pages/components/DataTable.tsx` — sort capability.
- `frontend/src/pages/components/DataTable.css` — sort-button styling.
- `frontend/src/pages/InvestigationsPage.tsx` — Status/Risk/Analyzed
  marked sortable.
- `frontend/src/pages/InvestigationsPage.test.tsx` — 8 new tests.

---

## 8. Explicit Non-Scope

- `MAX9-F-01` (stale `package.json` description, P3) — left open,
  carried forward unchanged, per the audit's own note that nothing new
  bears on it.
- Live browser/visual verification gap — outside this phase's control;
  restated, not addressed, per §26 of the audit.
- Timeline tab placement (INFO-1) — no evidence bar met; not
  actionable, not touched.
- Every other page, component, backend module, Rust crate, and
  packaging script — untouched. See §21 (Regression Review) for the
  diff proof.
- No new sort capability was added to any other `DataTable` consumer
  (Dashboard, IOC Explorer, Reports, Risk) — the audit scoped the
  finding to the Investigations list specifically, and those pages'
  columns were left exactly as they were.

---

## 9. Files/Components Changed

| File | Nature of change |
|---|---|
| `frontend/src/pages/components/DataTable.tsx` | New optional `sortable`/`sortValue` fields on `DataTableColumn`; internal sort state; stable comparator with direction-independent null-last ordering; native `<button>` sortable headers with `aria-sort`. |
| `frontend/src/pages/components/DataTable.css` | Minimal button-reset + icon styling, existing design tokens only. |
| `frontend/src/pages/InvestigationsPage.tsx` | Status/Risk/Analyzed columns marked `sortable` with a `sortValue` accessor; one stale doc comment corrected. |
| `frontend/src/pages/InvestigationsPage.test.tsx` | 8 new tests; one new fixture row (`INVESTIGATION_3`, unscored) added to exercise null-ordering and multi-row chronological sort. |

4 files changed. 0 files added or removed outside this set (the
closure document itself is the only addition to `docs/`).

---

## 10. Implementation Summary

`DataTable` now owns sort state (`{ key, direction } | null`) via
`useState`, matching the pattern MAX-9 Phase 2C already established for
this component (delegated state ownership, not a second mechanism per
page). A column opts in with `sortable: true` plus a `sortValue`
accessor returning a plain, comparable `string | number | null` — the
column's `render` output (a `ReactNode`) is not itself comparable, so
this is a separate, required field rather than reusing `render`.

Sorting is computed in a `useMemo` over `rows`; when no sort is active,
the memo returns the exact same array reference passed in, so every
consumer that doesn't opt in (Dashboard, IOC Explorer, Reports, Risk)
renders identically to before. Sorting is stable (`Array.prototype.sort`
is spec-guaranteed stable since ES2019), so tied values keep their
original relative order.

`null` values (an unscored investigation's risk score) always sort to
the end of the list, **independent of direction** — a deliberate design
choice, and one that caught a real bug of my own during implementation:
an earlier draft applied the ascending/descending multiplier to the
whole comparator including the null-ordering branch, which would have
let unscored rows jump to the top under descending sort. Fixed by
splitting `compareSortValues` (handles `null`, direction-agnostic) from
`compareNonNullSortValues` (direction-scaled), and covered by a
dedicated test (§17).

Column headers for sortable columns render as real `<button>` elements
rather than a `<div role="button">` reimplementation — native semantics
mean keyboard activation (Enter/Space) and focus come from the browser,
not custom code. Click toggles: unsorted/other-column → ascending →
descending → ascending (no third "unsorted" state once a column has
been activated once, matching the audit's own "ascending/descending
toggle" framing).

---

## 11. Analyst Workflow Impact

The one journey step the audit identified as impossible — "sort an
Investigations list by any column" (§5, §22 Journey E of the audit) —
is now possible for the three columns the audit scoped it to. Every
other traced journey step (find/open/review/report/export/recover) was
already clean per the audit and is unaffected — the search/filter
toolbar composes with sort exactly as before (sort operates on whatever
`filteredRows` currently is, verified by test).

---

## 12. Design-System Impact

Zero new design tokens introduced. The sort button and icon use only
existing tokens (`--space-xs`, `--color-text-primary`,
`--color-text-muted`) already present in `styles/tokens.css`. No new
color, spacing, or typography value was hardcoded. No new dependency
added.

---

## 13. Accessibility Impact

- **Semantics:** native `<button>` inside `<th scope="col">` — no ARIA
  reimplementation of button semantics.
- **`aria-sort`:** set to `"ascending"` / `"descending"` on the active
  sortable column, `"none"` on inactive sortable columns, and entirely
  omitted (not merely `"none"`) on non-sortable columns — matching the
  ARIA spec's guidance that `aria-sort` belongs only on columns that
  are themselves sortable.
- **Keyboard:** Enter/Space activation is native `<button>` behavior,
  not re-implemented — no custom `onKeyDown` was added or needed.
- **Focus:** relies entirely on the existing global `:focus-visible`
  rule (`styles/globals.css`); no local focus override was added, so
  no risk of suppressing or duplicating the existing focus ring.
- **No ARIA added where native semantics already cover the need** —
  per this phase's own accessibility rule (§15 of the task brief).

Status: **STATIC VERIFIED** (source/markup-level; no browser/screen-reader
session was available in this environment — see §19).

---

## 14. Responsive Impact

No layout structure changed. The sort button is `inline-flex` within
the existing `<th>` cell, adding only an icon glyph (~1 extra character
width) next to the existing header text — the header row's existing
`white-space: nowrap` and the table's existing horizontal-scroll
wrapper (`.data-table__scroll`, unchanged) already accommodate this.
No new fixed widths, no new min-widths, no page-level scroll
introduced.

Status: **STATIC VERIFIED** at the source/CSS level for both 1440×900
and 1280×720; **ENVIRONMENT-BLOCKED** for an actual rendered check, the
same standing limitation the MAX-10 audit itself restates (§3, §29) —
not new to this phase.

---

## 15. Motion Impact

None. No animation, transition, or motion token was added or modified.
The sort icon swaps character (⇅ → ▲/▼) on state change with no
transition — a discrete state change, not motion, so
`prefers-reduced-motion` has nothing to interact with here. Not
applicable rather than a gap.

---

## 16. Error/Empty/Recovery Impact

Not applicable to this change. Sort operates purely on already-loaded,
already-filtered rows; it introduces no new fetch, no new async state,
and therefore no new loading/error/retry surface. The existing
loading/error/empty/filtered-empty states on `InvestigationsPage`
(re-verified passing, unchanged) are untouched and unaffected — sort
state simply doesn't exist until `state === "success"` and rows are
being rendered.

---

## 17. Data Credibility Assessment

No data was fabricated. `sortValue` accessors read directly from the
same real, backend-sourced row fields (`row.status`, `row.riskScore`,
`row.analyzedAt`) already rendered by each column's existing `render`
function — no new derived, invented, or placeholder value was
introduced. The `null`-last rule for `riskScore` preserves the existing
"Not scored" honesty convention (`InvestigationsListRow.scored`) rather
than inventing a sortable stand-in value for unscored rows.

---

## 18. Test Results

```text
$ npx tsc --noEmit
(no output — clean)

$ npx vitest run
Test Files  82 passed (82)
     Tests  1180 passed (1180)
  Duration  57.20s

$ npx vite build
✓ 201 modules transformed.
✓ built in 2.71s
```

1172 baseline tests + 8 new tests = 1180, all passing, all re-run
directly in this phase (not assumed from the audit's prior run). Module
count (201) is identical to the MAX-10 audit's own build (§21 of the
audit).

New tests cover: sortable-header rendering with initial `aria-sort`
state, non-sortable columns staying plain, ascending sort with a
verified full row order, descending toggle, numeric sort with
null-last ordering in both directions, chronological sort, sort-state
reset when switching the active column, and composition with an active
search filter (sort applies to filtered rows, not the unfiltered set).
These are behavioral assertions on rendered row order and `aria-sort`
attributes, not shallow snapshots.

---

## 19. TypeScript Result

**Clean. 0 errors.**

---

## 20. Build Result

**Succeeded.** 201 modules transformed, output unchanged in structure
from the MAX-10 audit's own build.

---

## 21. Source Hygiene

Grepped all 4 changed files for `console.`, `TODO`, `FIXME`, `XXX`: **none
found**. No unused imports (confirmed by a clean `tsc --noEmit`, which
would flag them under this project's existing strict config). No dead
branches, no duplicate components, no duplicate CSS selectors
introduced, no new dependency added to `package.json`.

---

## 22. Regression Review

Diff-audited the full working tree against a fresh, untouched
extraction of the original uploaded ZIP:

```text
Only in extracted/.../frontend: dist          (build output, excluded from packaging)
Only in extracted/.../frontend: node_modules  (installed deps, excluded from packaging)
Files differ: frontend/src/pages/InvestigationsPage.test.tsx
Files differ: frontend/src/pages/InvestigationsPage.tsx
Files differ: frontend/src/pages/components/DataTable.css
Files differ: frontend/src/pages/components/DataTable.tsx
```

Exactly the 4 files listed in §9 differ. No backend Python, no Rust
(`sidecar-core`, `keystore-core`, `src-tauri`), no packaging script, no
other frontend page or component, and no dependency manifest changed.
**Scope compliance: PASS.**

---

## 23. Environment Limitations

Unchanged from every prior MAX phase and restated (not newly
discovered) by the MAX-10 audit itself:

- No browser or dev server available in this environment — all
  accessibility/responsive/motion conclusions above are
  **STATIC VERIFIED**, never an observed rendering.
- No Rust toolchain available — not relevant to this phase (no Rust
  file was touched), but noted for completeness since prior MAX phases
  record it consistently.

---

## 24. Remaining Conditions

1. `MAX9-F-01` (stale `package.json` description, P3) remains open,
   unchanged — out of this phase's scope, carried forward as the audit
   itself instructed.
2. The live browser/visual verification gap (accessibility, responsive,
   motion, keyboard, screen-reader) remains unperformed, as it has
   across all ten MAX cycles — not something this or any prior MAX
   *engineering* phase can close; a standing infrastructure
   recommendation, not a defect in this phase's work.
3. The archive's internal top-level directory name
   (`SOC-IQ-FRONTEND-MAX-5-DASHBOARD-FULL`) does not match the upload's
   MAX-10 filename — a labeling inconsistency to flag for whoever
   manages this project's checkpoint naming, not a defect in this
   phase's implementation.

---

## 25. Final Assessment

The single highest-leverage direction the MAX-10 audit identified —
and only that direction — was implemented, tested, and verified. No
architecture was changed, no other surface was touched, and the diff
against the untouched baseline proves it. All automated verification
was re-run fresh in this phase and passed cleanly.

```text
MAX-10 PHASE 2A — COMPLETE
```

---

## Hard Stop

Phase 2A is complete. Per the task brief's own rule, this phase does
not automatically continue to Phase 2B or any further MAX-10 work.
Awaiting explicit direction before any further work on this project.
