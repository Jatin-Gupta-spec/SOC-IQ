# SOC-IQ Frontend MAX-7 — Analyst UX + Workflow Hardening — Audit

## PHASE 1 — FORENSIC AUDIT ONLY (no source changes made)

**This is the single authoritative MAX-7 Phase 1 audit document.**
No prior MAX-7 audit Markdown existed before this pass — a full search of the
project's `docs/audits/` directory before writing found MAX-1 through MAX-6
closures/audits only, plus release/security audits unrelated to MAX-7 (§3). This
document therefore supersedes nothing and merges nothing from an earlier MAX-7
draft; it is the first and only MAX-7 audit, produced directly from the project
source. This consolidation pass re-verified that fact (§19) rather than assuming it
from the prior session.

---

## 1. Executive Summary

This audit inspected SOC-IQ's frontend as a real analyst tool rather than a generic
React application, focused on the four core workflows (Analyze, Investigate,
Analysis → Investigation, Reporting) and the Investigation Workspace as the highest-
priority surface. It is static/code-level only — no dev server or browser was
available in this environment, so every finding below is derived from direct reading
of the actual TSX/CSS source and its own doc comments, not from inference about how
it "probably" behaves.

**Headline result:** the individual pieces of SOC-IQ are well-built — every page
handles loading/error/empty states honestly, IOC search/filter is real, tab semantics
are properly accessible (MAX-1), and the design system is consistent (MAX-6). The
problems found are almost entirely at the *seams between* workflows, not inside any
single page:

- The single most important cross-workflow path in the product — **Analyze → open the
  investigation you just created** — does not deep-link to that investigation. It sends
  the analyst to the general Investigations list instead, even though the exact
  investigation ID is already known to the component (F-01, P0).
- The Investigation Workspace's tab selection is pure local React state with no URL
  representation, so a reload, a shared link, or the browser back button cannot return
  an analyst to the IOC/Threat Intel/Correlations tab they were just looking at — every
  such action silently drops them back to Overview (F-02, P1).
- There is no way to jump directly to a specific investigation from anywhere in the
  app except by scrolling/scanning the Investigations table — the command palette only
  knows about the five static top-level pages, and neither Investigations nor Reports
  has a search, filter, or sort control of its own (F-03, P2).
- "Reports" and "Investigations" render the same underlying list from the same
  `useInvestigationsList()` hook and differ by exactly one column (Export vs. nothing),
  with no distinct report artifact, preview, or review step — which is workable but
  gives an analyst two nearly-identical destinations for the same data with no signal
  for which one to use for which task (F-04, P2).
- `DataTable` already supports whole-row activation (`onRowActivate`) but Investigations
  and Reports don't use it — only the investigation-name text itself is clickable, so a
  click anywhere else on a row (the status badge, the risk cell) does nothing (F-05,
  P3).

No P0-severity finding blocks a workflow outright — an analyst *can* complete every
workflow — but F-01 forces an unnecessary re-search after every single analysis run,
which is exactly the kind of "seriously obstructs an important, frequent task" pattern
P0 is meant to capture.

```text
Findings: 5 total — P0: 1 · P1: 1 · P2: 2 · P3: 1
```

---

## 2. Audit Scope

Frontend-only, workflow/UX-focused, audit-only (no implementation). In scope: the five
top-level pages (Dashboard, Analyze, Investigations, Reports, Settings), the
Investigation Workspace and its four tabs, cross-page navigation, the command palette,
`DataTable`/`Button`/`Card`/`PageHeader`/token layer as they affect workflow (not as a
second design-system audit), error/recovery/empty-state UX, and search/filter/sort UX.
Out of scope, per the brief: backend/Python, Rust/Tauri, database, packaging, and any
change to MAX-1–MAX-6 frozen systems except where a MAX-7 finding is directly caused by
one (no such dependency was found beyond the narrow, explicitly-flagged items in §22).

**Correction to the page inventory named in the task brief:** "Provider Detail" is not
a standalone routed page. `ProviderDetail.tsx` is a collapsed-by-default panel embedded
inside the Investigation Workspace's Threat Intel tab (rendered up to three times per
investigation, once per raw-payload context) — there is no `/provider/:id`-style route
and no sidebar entry for it. This audit treats it as part of the Threat Intel tab
audit (§9) rather than scoring it as a seventh independent page, since scoring a
non-existent page would misstate the actual page inventory. Its scorecard row (§21) is
retained per the brief's requested table shape but marked accordingly.

---

## 3. Previous Phase Boundaries

Read directly from `docs/audits/` before any MAX-7 inspection began. The directory
contains MAX-1 through MAX-6 closures, a MAX-6 audit, and a set of unrelated R2–R4
release/persistence/packaging/CORS audits — no earlier MAX-7 document of any kind was
found, so §4/§19's merge instruction has nothing to merge against; this is recorded
here as a verified fact, not an assumption.

| Phase | What it closed | Frozen for MAX-7 |
|---|---|---|
| MAX-1 | WAI-ARIA tab pattern for the Investigation Workspace tabs (roving tabindex, arrow/Home/End keys, single `tabpanel`) | Tab *semantics* — not touched by any finding below |
| MAX-2 | Table-shaped loading skeletons on Investigations/Reports/Settings, matching Dashboard/Workspace's existing pattern | Skeleton components |
| MAX-3 | `DataTable` horizontal-scroll wrapper, `PageHeader`/workspace-tabs `flex-wrap` — three CSS-only overflow fixes at 1280/1440 | Breakpoint tokens, overflow strategy |
| MAX-4 | Hover/focus transitions on previously-instant controls, tokenized durations, Command Palette entrance motion, global `prefers-reduced-motion` floor | Motion tokens/utilities |
| MAX-5 | Real `get_investigation_aggregate_summary` wiring into a new Dashboard "Investigation Activity" trend chart — the only temporal visualization in the product; no risk/IOC trend exists (no backend aggregate for either) | Dashboard data contracts |
| MAX-6 | Shared `Button` primitive; migrated six retry-button contexts + two export-button contexts onto it; converged Analyze's deviant focus-outline color onto the global MAX-1 standard; `MetricCard`/`InvestigationHeaderCard` compose `.card` instead of duplicating it | `Button`/`Card`/`DataTable`/`PageHeader` architecture — see §22 boundary below |

MAX-6's own "Remaining Work" section explicitly deferred, unresolved as of this audit:
viewport/rendered verification at both required breakpoints, badge classification, a
Provider Detail visual audit, and `BackToInvestigationsButton`'s un-migrated third
button style. None of these are reopened here; where they intersect a MAX-7 finding
(F-02), that intersection is called out explicitly rather than treated as new MAX-7
scope.

---

## 4. Analyst Workflow Map

```text
Dashboard ──(Recent Investigations row, real ID)──────────┐
                                                            ▼
Analyze ──(Open Investigation link, GENERIC LIST PATH)──▶ Investigations ──(name link, real ID)──▶ Investigation Workspace
                                                                                                          │
                                                                                                    Overview / IOCs /
                                                                                                    Threat Intel /
                                                                                                    Correlations
                                                                                                    (local state only,
                                                                                                     no URL — F-02)
Reports ──(name link, real ID; same list as Investigations)──▶ Investigation Workspace
Reports ──(Export column)──▶ native save dialog (no in-app preview)
```

Three of the four entry points into the Investigation Workspace (Dashboard, the
Investigations list itself, the Reports list) use the specific investigation's real
ID. The fourth — the one immediately after an analyst finishes an analysis, arguably
the highest-frequency handoff in the whole product — does not. This asymmetry is the
basis for F-01 and is evidenced directly in §5/§7 below, not inferred.

---

## 5. Analyze Workflow

`AnalyzePage.tsx` (309 lines) + `analyze/AnalysisResultSummary.tsx` (181 lines) were
read in full.

**Orientation / priority:** clear. A single-purpose page: pick or drop a report,
configure three toggles (extract IOCs / enrich TI / score risk), start. No competing
secondary actions.

**Progress/feedback:** the execution state machine (`analysisWorkflowState.ts`) is
honest — it renders which stages the backend actually ran (`result.options`, echoed
back from the backend, not merely what was requested), and explicitly does not
fabricate a risk score when `score_risk` was disabled (renders `NOT_SCORED` as an
`InfoNote`, not a "0"). No feedback issues found.

**F-01 — the handoff itself:**

```text
ID: MAX7-F-01
Severity: P0
Workflow: Analysis → Investigation
Page: Analyze (analysis-result handoff)
Location: frontend/src/pages/analyze/AnalysisResultSummary.tsx, "Open Investigation" link
Observed behavior: On a successful analysis with a real `result.investigationId`, the
  "Open Investigation" link renders `href={#${investigationsPath}}`, i.e. the generic
  `/investigations` list path — never `/investigations/${result.investigationId}` —
  even though the specific ID is already present on `result` and is of the identical
  shape (`number`) that three other locations in the same codebase already use to
  deep-link correctly (DashboardRecentInvestigations.tsx, InvestigationsPage.tsx's row
  links, ReportsPage.tsx's row links all build `#/investigations/{id}`).
Why it matters: this is the single highest-frequency transition in the "Analyze"
  workflow — it fires after every completed analysis. Instead of landing on the
  investigation just created, the analyst lands on the full list and has to relocate
  it (by name, scanning, or trusting it's sorted to the top) before they can see its
  IOCs or Threat Intel, which the page's own copy just told them to go check
  ("open the investigation below to see them in its IOCs and Threat Intel tabs").
Expected analyst behavior: click "Open Investigation" → land directly in that
  investigation's workspace, Overview tab, ready to continue into IOCs/Threat Intel.
Evidence: AnalysisResultSummary.tsx's handoff renders `href={"#" + investigationsPath}`
  where `investigationsPath` is the static `/investigations` constant passed in from
  AnalyzePage.tsx; `result.investigationId` (typed `number | null` in
  analysisWorkflowState.ts) is read only to decide *whether* to render a link at all,
  never interpolated into its `href`. Contrast: DashboardRecentInvestigations.tsx's own
  doc comment states rows "with a real, persisted `investigationId` navigate to ...
  `/investigations/:id`" — the correct pattern already exists elsewhere in the same
  checkpoint.
Recommended direction: interpolate `result.investigationId` into the handoff href
  (`#/investigations/${result.investigationId}`), matching the pattern already
  established by the Dashboard/Investigations/Reports row links. No new navigation
  mechanism is needed — this is a one-value fix to an existing, working pattern.
Dependencies: none on frozen MAX-1–MAX-6 systems. `InvestigationRoute`/
  `InvestigationWorkspacePage` already handle any valid numeric ID correctly.
```

---

## 6. Investigation Workflow

`InvestigationsPage.tsx` (full read) + `DataTable.tsx` (full read).

**Orientation:** clear — one table, one heading ("All Investigations"), one description
line explaining what the columns mean.

**Discoverability of the primary path (select an investigation):** the investigation
name is a real `<a href="#/investigations/{id}">`, so it's a native, keyboard-reachable
link with correct browser affordances (right-click "open in new tab" works, etc.) —
this is a genuinely good pattern, not a finding.

**F-05 — row activation inconsistency** (full entry in §12, Search/Filter/Table UX).

**F-03 — no search/filter/sort at the list level** (full entry in §10).

**Empty/error states:** both honest — an explicit "No investigations found." for a
real empty result (never confused with a loading or error state) and an error card
with a Retry button that reuses the shared `Button` primitive. No finding.

---

## 7. Analysis → Investigation Workflow

This is where F-01 (§5) lives; it is the only defect found in this transition. Once an
analyst *does* reach the Investigations list (whether via the broken link or by
clicking the sidebar), the rest of the path (list → workspace) is sound, per §6/§9.

---

## 8. Reporting Workflow

`ReportsPage.tsx` + `reports/ReportExportAction.tsx` read in full.

```text
ID: MAX7-F-04
Severity: P2
Workflow: Reporting
Page: Reports
Location: frontend/src/pages/ReportsPage.tsx (whole-page pattern)
Observed behavior: Reports renders the exact same underlying list as Investigations —
  both call `useInvestigationsList()` and both build their rows from the identical
  `investigations` array (`normalizeReportsList` vs. `normalizeInvestigationsList` — a
  same-shape re-derivation, not a different data source). The only structural
  difference is Reports drops the Confidence column and adds one Export column
  (ReportExportAction: opens a native save dialog and calls `export_report` directly —
  no in-app preview, no distinct "report" artifact, no review step of any kind between
  "select" and "export").
Why it matters: an analyst who wants to "review a report" (Investigation → report →
  review → export → return) has no in-app content to review — the closest equivalent is
  opening the same investigation from either page's identical name-link. Having two
  destinations with near-identical tables and no differentiating label or description
  beyond the header text risks analysts defaulting to whichever they land on first and
  not realizing the other exists, or wondering why there are two "investigation lists."
Expected analyst behavior: a single mental model for "where do I see this investigation
  as data" (Investigations) vs. "where do I get an artifact out of it" (Reports/Export)
  — currently both are the same table with an extra button, so the distinction is not
  visually or structurally reinforced.
Evidence: ReportsPage.tsx's columns array and InvestigationsPage.tsx's columns array
  differ by exactly the Confidence key (dropped) and the Export key (added); both call
  the same `useInvestigationsList()` hook (`reports/reportsViewModel.ts` /
  `investigations/investigationsViewModel.ts` are both thin per-page mappers over the
  same `investigations` array, not separate fetches).
Recommended direction: not prescribed in detail per the audit-only mandate — the two
  directions the implementation phase should weigh are (a) fold Export into
  Investigations as a column/row action so Reports is retired, or (b) keep both but
  differentiate Reports' purpose in its own copy/columns (e.g., last-export status)
  so it isn't a visual duplicate. Either is a real option; this audit does not pick one.
Dependencies: none on frozen systems — this is a page-composition question, not a
  DataTable/Button/token issue.
```

No feedback/recovery issues were found in the Export flow itself: it honestly
disables/relabels when there's no investigation ID or no native save dialog available
(`ReportExportAction.tsx`), and cycles through Export → Exporting… → Export
again/Retry export states with real backend calls at every step — not a finding.

---

## 9. Investigation Workspace Deep Audit

`InvestigationWorkspacePage.tsx` read in full (450 lines), including its
`WorkspaceTabs` sub-component.

**Investigation identity / header hierarchy:** the header card renders identity, risk,
and status above the tabs, sourced from the same `useInvestigation()` fetch that
services every tab (single fetch, no per-tab re-fetch — confirmed in the component's own
doc comment: "switching between tabs never triggers a new fetch"). Not-found and error
states are handled as distinct, honestly-labeled states (not folded into a generic
error), each with a Retry (error only) and a Back-to-Investigations action. No finding.

**F-02 — tab selection has no URL representation:**

```text
ID: MAX7-F-02
Severity: P1
Workflow: Investigate
Page: Investigation Workspace
Location: frontend/src/pages/investigation/InvestigationWorkspacePage.tsx —
  `const [activeTab, setActiveTab] = useState<WorkspaceTabId>("overview")`
Observed behavior: which of the four tabs (Overview/IOCs/Threat Intel/Correlations) is
  active lives entirely in local component state, never reflected into the URL
  (route is `/investigations/:investigationId` only — no `?tab=` or `/iocs` segment).
Why it matters (context loss): an analyst deep in the IOCs tab who reloads the page,
  follows a link back into the same investigation from elsewhere in the app (Dashboard,
  Investigations, Reports — all of which link to the bare investigation ID), or uses
  the browser's back button after tabbing around, is always returned to Overview — the
  investigation identity survives (it's in the URL), but the specific working context
  inside it does not. This also means a colleague cannot be sent a link straight to
  "the Threat Intel tab of investigation #42" — only to its Overview.
Expected analyst behavior: reloading, back-navigating, or receiving a shared link
  while working a specific tab should return to that same tab, not silently reset
  investigative context.
Evidence: `WORKSPACE_TABS`'s four ids are local `useState` only; `router.tsx`'s only
  investigation-scoped route is the bare `/investigations/:investigationId` (confirmed
  by reading the full route table — no nested/child routes exist for tabs).
Recommended direction: represent `activeTab` in the URL (a query parameter or path
  segment) so it round-trips through reload/back/forward/share, while leaving the
  existing WAI-ARIA tab keyboard handling (MAX-1) and the single-fetch-per-investigation
  behavior untouched — this is additive URL state, not a rearchitecture of either.
Dependencies: touches `InvestigationWorkspacePage.tsx`, which is also where MAX-1's
  tab semantics live — any implementation must preserve the existing roving-tabindex/
  ArrowRight-Left/Home/End behavior exactly (identify the dependency, don't silently
  modify MAX-1 architecture as a side effect — see §22).
```

**Excessive navigation / duplicated selections:** none observed within the workspace
itself — the IOC search/type-filter state resets cleanly on investigation-id change
(explicitly handled, per `InvestigationIocWorkspace.tsx`'s own doc comment, to avoid a
stale filter surviving a switch to a different investigation), and no modal is used
anywhere in the workspace. No click-count claims are made here — none were
runtime-verified in this environment.

**Detail/evidence exposure (Threat Intel raw payload / "Provider Detail"):** the raw
provider payload is rendered as a collapsed-by-default, generically-walked key/value
hierarchy — never a fabricated field, and sensitive-looking keys (credential-shaped
fields) are withheld by pattern match rather than guessed at. This is a defensible,
conservative choice for detail exposure and is not a finding either way; it was not
independently re-verified against a live payload in this environment (no browser/
backend available), so this audit stops at confirming the source-level contract rather
than inventing backend behavior that does not exist.

**`BackToInvestigationsButton`:** a plain native `<button>`, not the shared `Button`
primitive — this is not a new MAX-7 finding; it is MAX-6's own documented, deliberate
exception ("intentionally left unmigrated because it was never part of a confirmed
finding," MAX-6 closure §12). Noted here only so it isn't mistaken for something this
audit missed.

---

## 10. Cross-Page Navigation

Entry points/destinations traced via `router.tsx`, `navigationModel.ts`, and every
component found to build an `href`/`onRowActivate`/`navigate()` call.

```text
ID: MAX7-F-03
Severity: P2
Workflow: Investigate (discovery)
Page: Investigations / Reports / global (Command Palette)
Location: frontend/src/pages/InvestigationsPage.tsx, ReportsPage.tsx,
  app/commandPalette/CommandPaletteContainer.tsx, shared/commands/commandRegistry.ts
Observed behavior: neither the Investigations table nor the Reports table exposes a
  search box, a column filter, or a sortable header (`DataTable.tsx` itself has no
  sort capability anywhere in the codebase — confirmed by direct read; the IOC
  workspace's own doc comment independently confirms this: "Sorting is intentionally
  not added: DataTable ... has no existing sort capability to reuse"). The Command
  Palette (Ctrl/Cmd+K) is likewise static: `COMMANDS` is derived 1:1 from the five
  `NAVIGATION_ITEMS` sidebar destinations only — it has no awareness of individual
  investigations, IOCs, or reports.
Why it matters: the only way to reach a specific investigation by name/date/severity
  from anywhere in the app is to open the Investigations (or Reports) table and
  visually scan it top-to-bottom — there is no quick-jump, no keyboard-driven search,
  and nothing to reorder the table by severity or date once it's on screen. This scales
  fine for a short list; it becomes real friction as investigation count grows, and it
  is the opposite of the "Raycast-like efficiency" the project's own design direction
  calls for.
Expected analyst behavior: type a few characters of a report name, or a severity, and
  narrow the list — either inline on the page or via the palette that already exists
  and already handles fuzzy text matching for its five static commands.
Evidence: full read of InvestigationsPage.tsx/ReportsPage.tsx (no search/filter state,
  no sort handler passed to columns) and commandRegistry.ts (`COMMANDS` is a pure
  `NAVIGATION_ITEMS.map(...)`, no dynamic/investigation-derived entries).
Recommended direction: lowest-effort path is a client-side search/filter box on
  Investigations (mirroring the IOC workspace's own already-proven search/filter
  pattern, §12) before considering command-palette or backend-driven search.
Dependencies: `DataTable`'s lack of sort is a pre-existing, MAX-6-confirmed-clean-
  system characteristic (MAX-6 closure §5: DataTable was the "strongest-documented
  shared component found," not touched). Adding sort would mean extending DataTable's
  architecture — flagged per §22 as a real dependency on a frozen system, not
  auto-authorized by this finding.
```

**Dead ends / duplicated navigation:** none found. The retirement of the former
top-level IOC Explorer/Threat Intel/Risk destinations (documented PD-05/PD-06 decisions
inside `navigationModel.ts`, predating MAX-7) is intentional and consistently applied —
`router.tsx`'s catch-all redirects any bookmarked old hash to the Dashboard rather than
404ing, and no navigation link anywhere still points at a retired path. Not a finding.

---

## 11. State Preservation

| State | Preserved? | Evidence |
|---|---|---|
| Selected investigation (URL) | **Preserved** | `/investigations/:investigationId` round-trips through reload/back/share |
| Active workspace tab | **Unexpectedly lost** | F-02 (§9) — local `useState` only |
| IOC search/type filter (within a tab) | **Intentionally reset** on investigation-id change; otherwise preserved for the session while viewing that investigation | `InvestigationIocWorkspace.tsx`'s own doc comment, confirmed by reading the reset logic |
| Investigations/Reports list state | **Not applicable** — no search/filter/sort exists yet to preserve (F-03) | — |
| Analysis configuration (Analyze page toggles) | **Unable to verify persistence intent** — no persistence mechanism found, but nothing in the workflow requires it to survive navigation away from Analyze | `AnalyzePage.tsx` read; toggles are local `useState`, page-session only, consistent with a single-shot form |

No other cross-page state-preservation expectation was identified as applicable to
this product's actual workflows.

---

## 12. Search/Filter/Table UX

**List-level (Investigations/Reports):** covered by F-03 (§10) — no search, filter, or
sort exists at all at this level.

**IOC workspace (`InvestigationIocWorkspace.tsx`)** — the one place real search/filter
exists in the product: client-side text search plus a type filter whose *options* are
derived from the types actually present in the loaded data (never offering a filter
option guaranteed to return zero rows — a genuinely good, verified pattern, not a
finding). Three distinct empty states are honestly differentiated: no IOCs at all vs.
IOCs unavailable (fetch failure) vs. real IOCs present but the current search/filter
combination matches none of them (with its own "Clear filters" action) — exactly the
"empty vs. unavailable vs. filtered-empty" distinction a well-built table should make.
This is a model for what F-03 recommends extending to Investigations.

**Reset/clear controls:** present and working in the IOC workspace ("Clear filters");
absent everywhere else because no other filterable surface currently exists (F-03).

**Row activation / interaction:**

```text
ID: MAX7-F-05
Severity: P3
Workflow: Investigate / Reporting
Page: Investigations, Reports
Location: frontend/src/pages/components/DataTable.tsx (capability); InvestigationsPage.tsx
  / ReportsPage.tsx (non-use of it)
Observed behavior: `DataTable` has a real, already-built whole-row activation mode
  (`onRowActivate`/`isRowSelected`/`getRowAriaLabel` props — makes every `<tr>`
  focusable and Enter/Space-activatable, per its own doc comment). Investigations and
  Reports both render `DataTable` *without* passing `onRowActivate`, so only the literal
  investigation-name `<a>` text inside the first cell is clickable/keyboard-reachable as
  a distinct stop; clicking the Status badge, Severity badge, Risk, Confidence, or
  Analyzed cells does nothing.
Why it matters: a dense, scan-heavy SOC table is exactly the case where "click anywhere
  on the row" is the expected affordance (and is the pattern the product's own stated
  Mobbin-quality-interaction-patterns direction calls for) — the current behavior
  requires precise pointer targeting on a short text link inside a wide row.
Expected analyst behavior: click/tap anywhere in a row to open that investigation,
  same as many dense analyst tools already do.
Evidence: DataTable.tsx's `interactive = onRowActivate !== undefined` gate; grep-
  confirmed neither InvestigationsPage.tsx nor ReportsPage.tsx passes `onRowActivate`.
Recommended direction: pass `onRowActivate`/`getRowAriaLabel` on both pages, keeping the
  existing name `<a href>` inside the row for middle-click/"open in new tab" (a real,
  currently-working affordance that a bare `onRowActivate` alone would not preserve) —
  the two are not mutually exclusive.
Dependencies: `DataTable` itself needs no change — this is a call-site (page-level)
  fix using an already-built, MAX-6-confirmed-clean capability. No frozen-system
  reopening required.
```

**Density/scanability/truncation:** not independently flagged — columns are narrow and
single-purpose (name/status/severity/risk/confidence/date), StatusBadge is
color-plus-text (never color-only), and `DataTable`'s MAX-3 horizontal-scroll wrapper
handles overflow locally rather than at the page level. No finding.

**Keyboard behavior:** native `<a>`/`<button>` elements throughout — standard Tab/Enter
behavior applies without any custom keyboard handling to audit, except where
`onRowActivate` is used (Enter/Space explicitly handled, confirmed in `DataTable.tsx`).

---

## 13. Error & Recovery

Consistent, honest pattern across every page audited: `describe*Error()` helpers
prefer the backend's own real `Error.message` over an invented string (repeated
verbatim convention across `InvestigationsPage.tsx`, `ReportsPage.tsx`,
`InvestigationWorkspacePage.tsx`), every error state offers a Retry that calls the same
hook's own `retry()` (not a full page reload), and Retry buttons are now uniformly the
shared `Button` primitive post-MAX-6 (no fragmentation left to find — confirmed, not
just assumed, by re-reading the six migrated call sites listed in the MAX-6 closure).
Context is preserved through retry in every case observed: retrying re-runs the same
hook against the same investigation ID / same list request, never resets to a different
page or loses the analyst's place. No P0/P1 recovery finding; no duplicate actions or
dead ends were found in any failure path read.

The one recovery-adjacent gap already covered above is F-02: an *unintentional*
navigation-triggered "reset" (tab reverting to Overview), which is a state-preservation
defect rather than a genuine error-recovery defect, and is filed there rather than
duplicated here.

---

## 14. Empty States

Every empty state read (Investigations "No investigations found.", Reports' equivalent,
the IOC workspace's three-way empty/unavailable/filtered-empty split, Dashboard's own
existing empty states inspected during MAX-5 and not touched since) explains *why* the
section is empty and, where a next action exists (clear filters, retry), surfaces it
inline. None were found to be purely decorative. No finding.

---

## 15. Keyboard Workflow

MAX-1's tab pattern (`InvestigationWorkspacePage.tsx`) was re-read and confirmed intact:
roving `tabIndex`, `ArrowRight`/`ArrowLeft`/`Home`/`End` all move both selection and
real DOM focus, other keys fall through to native behavior, and only the active
`tabpanel` is mounted. `DataTable`'s opt-in interactive-row mode correctly handles
Enter/Space with `preventDefault()` to stop page scroll on Space. No keyboard regression
or new gap was found in any surface read. This section is a confirmation, not a new
finding — MAX-1's own architecture is explicitly not reopened here.

---

## 16. Responsive Workflow

```text
1280 × 720  — ENVIRONMENT-BLOCKED — browser viewport verification unavailable
1440 × 900  — ENVIRONMENT-BLOCKED — browser viewport verification unavailable
```

No browser or rendering surface was available in this sandbox (identical, carried-
forward constraint to MAX-3's and MAX-6's own audits — see §3 above). Static review
confirms MAX-3's three fixes (DataTable horizontal-scroll wrapper, PageHeader
`flex-wrap`, workspace-tabs `flex-wrap`) remain present and untouched in the current
source, and MAX-6's migration touched no `@media` block in any file it changed
(confirmed by the same static-diff method MAX-6's own closure used). This audit does
not claim a visual pass at either breakpoint — that remains the same open condition
MAX-6 already carried forward, not a new MAX-7 gap. No page-level scrolling was added
or recommended anywhere in this audit.

---

## 17. Motion UX

Not reopened as new scope (MAX-4 is frozen). Spot-check: the Investigation Workspace's
tabpanel still carries `investigation-workspace__content--enter` on every tab switch
(the MAX-4-era transition class), and `Button`'s CSS (confirmed during the MAX-6 read
in §3) uses the same `--duration-fast`/`--easing-out` tokens as every other migrated
control. No motion regression found; no motion was added anywhere in this audit.

---

## 18. Findings

| ID | Severity | Workflow | Page |
|---|---|---|---|
| MAX7-F-01 | **P0** | Analysis → Investigation | Analyze |
| MAX7-F-02 | **P1** | Investigate | Investigation Workspace |
| MAX7-F-03 | **P2** | Investigate (discovery) | Investigations / Reports / Command Palette |
| MAX7-F-04 | **P2** | Reporting | Reports |
| MAX7-F-05 | **P3** | Investigate / Reporting | Investigations, Reports |

(Full write-ups in §5, §9, §10, §8, §12 respectively. No P0 finding beyond F-01 was
identified; severities were not inflated to fill a quota.)

---

## 19. P0/P1/P2/P3 Prioritization

- **P0 (1):** F-01 — broken deep-link on the highest-frequency cross-workflow handoff.
- **P1 (1):** F-02 — silent context loss on the Investigation Workspace's own tab state.
- **P2 (2):** F-03 — no discovery/search at list level; F-04 — Reports/Investigations
  duplication with no distinct reporting artifact.
- **P3 (1):** F-05 — row-activation affordance gap using an already-built capability.

No finding was rated P0 purely because it was inconvenient; each P0/P1 rating above is
tied to a concrete, source-confirmed behavior that either blocks a common path outright
(none did) or forces unnecessary, avoidable rework on a task the analyst just completed
(F-01) or silently discards working context the analyst didn't choose to discard
(F-02).

---

## 20. Workflow Scorecard

| Workflow | Discoverability | Efficiency | Context Preservation | Recovery | Overall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Analyze | 8/10 | 7/10 | 6/10 | 9/10 | 7/10 |
| Investigate | 7/10 | 6/10 | 7/10 | 9/10 | 7/10 |
| Analysis → Investigation | 6/10 | 4/10 | 6/10 | n/a | 5/10 |
| Reporting | 7/10 | 6/10 | 8/10 | 9/10 | 7/10 |

- **Analyze:** the form itself is clean and honest (8/10 discoverability, 9/10
  recovery — real retry, real error messages). Efficiency/context docked for the F-01
  handoff, which is *inside* this workflow's own final step.
- **Investigate:** strong recovery (state-machine driven, Retry preserves context) and
  solid discoverability once inside an investigation; docked on efficiency/context for
  F-02 (tab loss) and F-03 (no list-level search).
- **Analysis → Investigation:** the lowest score, driven entirely by F-01 — the
  transition exists and works, but sends the analyst to the wrong specificity of
  destination every time. "Recovery" is marked n/a — there is no error state in this
  specific transition to recover from, F-01 is a routing defect, not a failure state.
- **Reporting:** functional and honest (real export, real save-dialog integration, no
  fake Download button) but docked on discoverability for F-04's page-purpose overlap.

---

## 21. Page Scorecard

| Page | Orientation | Hierarchy | Interaction | Recovery | Workflow UX |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dashboard | 9/10 | 8/10 | 8/10 | 8/10 | 8/10 |
| Analyze | 8/10 | 8/10 | 7/10 | 9/10 | 6/10 |
| Investigations | 8/10 | 8/10 | 6/10 | 9/10 | 6/10 |
| Workspace | 9/10 | 9/10 | 8/10 | 9/10 | 7/10 |
| Reports | 7/10 | 7/10 | 6/10 | 9/10 | 6/10 |
| Settings | 8/10 | 7/10 | 8/10 | 9/10 | 8/10 |
| Provider Detail | n/a | n/a | n/a | n/a | n/a |

- **Dashboard:** correct deep-linking throughout (Recent Investigations), real temporal
  data (MAX-5), no findings raised against it in this pass.
- **Analyze:** Workflow UX specifically docked for F-01 even though the page's own
  internal UX is strong (hence the gap between its Orientation/Recovery scores and its
  Workflow UX score).
- **Investigations:** Interaction docked for F-05 (row activation) and F-03 (no
  search/filter); everything else about the page is sound.
- **Workspace:** the strongest page audited — highest Orientation/Hierarchy scores of
  any surface; Workflow UX alone docked for F-02.
- **Reports:** the lowest Orientation score, reflecting F-04's page-purpose ambiguity
  relative to Investigations; Interaction shares Investigations' F-05 gap.
- **Settings** was read only lightly (three sub-controls confirmed on the MAX-6 Button
  migration, per §3) — no dedicated deep pass was performed since Settings is not part
  of the four named core workflows; scores here are provisional/lighter-confidence than
  the other five rows, flagged honestly rather than presented as equally verified.
- **Provider Detail** is scored `n/a` throughout — per §2's scope correction, it is not
  a standalone page and scoring it as one would misstate the actual page inventory. Its
  content is covered qualitatively under Investigation Workspace (§9).

---

## 22. Protected Systems

Confirmed untouched, and confirmed **not required to change** for any F-01–F-05 fix:

- Token layer (`tokens.css`) — no finding references a token gap.
- `Button` architecture — F-01/F-02/F-03/F-04 are routing/state/composition issues, not
  button-styling issues; F-05's fix is a call-site prop addition to `DataTable`, not a
  `Button` change.
- `Card`/`PageHeader` architecture — not referenced by any finding.
- `DataTable` architecture — **one soft dependency exists**, flagged transparently
  rather than silently acted on: F-05's recommended direction uses `DataTable`'s
  *existing* `onRowActivate` capability (a call-site change only, zero `DataTable.tsx`
  edits needed) and F-03's recommended direction would, if a future implementation
  phase chooses full column sorting over a simpler search box, require extending
  `DataTable` itself (no sort capability exists anywhere in the component today). This
  is documented as a dependency, not pre-authorized — document it, do not automatically
  modify it.
- MAX-1 accessibility architecture — F-02's recommended direction explicitly requires
  preserving the existing tab keyboard handling; flagged as a dependency in F-02's own
  entry (§9), not silently assumed safe to disturb.

---

## 23. Recommended MAX-7 Implementation Order

Not implemented — recommendation only, ranked by priority (workflow blockers → context
loss → navigation friction → interaction problems → recovery → hierarchy →
table/search/filter → polish):

1. **F-01** (P0) — fix the Analyze → Investigation handoff link. Smallest possible
   change (one interpolated value) with the largest workflow impact found in this
   audit.
2. **F-02** (P1) — give the Investigation Workspace's active tab a URL representation,
   built carefully alongside (not instead of) MAX-1's existing keyboard handling.
3. **F-03** (P2) — add search/filter to the Investigations list, most cheaply by
   reusing the IOC workspace's own already-proven search/filter UI pattern rather than
   inventing a new one; defer any `DataTable` sort-capability extension to its own
   explicit decision.
4. **F-04** (P2) — resolve the Reports/Investigations purpose overlap; this is a
   product-direction decision (merge vs. differentiate) more than an engineering one,
   so it should be decided before it is implemented.
5. **F-05** (P3) — wire `onRowActivate` on Investigations/Reports; trivial, low-risk,
   can be bundled with either F-01 or F-03's implementation pass rather than run as its
   own phase.

No P0 finding beyond F-01 exists to reorder ahead of it; no finding here should be
read as authorization to reopen MAX-1–MAX-6 architecture beyond the specific, narrow
dependencies named in §22.

---

## 24. Audit Limitations

- **No dev server, browser, or rendering surface was available** in this sandbox — every
  finding here is source/static-analysis-derived, consistent with MAX-3's and MAX-6's
  own carried-forward environmental limitation. No pixel-level, hover-state, or
  actual-viewport claim is made anywhere in this document.
- **No test suite was executed** in this pass. Given the audit-only, non-implementation
  mandate and the absence of any source change to verify against, a fresh `npm ci` /
  `vitest run` baseline was judged out of scope for establishing *this* document's
  findings (all of which are read directly from source, not inferred from test
  behavior) and was not run. This is stated plainly rather than a result being
  fabricated.
- **Git provenance unavailable** in the supplied project artifact (no `.git` directory
  present anywhere in the extracted tree) — filesystem/static verification was
  performed instead throughout, consistent with every prior MAX-phase closure's own
  documented limitation (see §25's Source Immutability Check).
- **Settings and Dashboard received a lighter pass** than Analyze/Investigations/
  Investigation Workspace/Reports, since the task brief's four named core workflows
  don't route through them as a primary path; their scorecard entries are flagged as
  lower-confidence in §21 rather than presented as equally exhaustive.
- **No click-count or timing claims** are made anywhere in this document — none were
  runtime-verified in this environment.
- **No earlier MAX-7 audit existed to merge** — verified by directory listing (§3);
  this document is therefore original to this pass, not a consolidation of conflicting
  prior drafts.

---

## 25. Final Verdict

```text
FRONTEND MAX-7 — AUDIT COMPLETE WITH DOCUMENTED CONDITIONS
```

The product's individual surfaces are in good shape — the loading/error/empty-state
discipline established by MAX-2 and the design-system consistency established by MAX-6
both held up under a workflow-focused re-read, and no regression against MAX-1–MAX-6
was found anywhere. The real opportunity for MAX-7 implementation is narrow and
concrete: one broken deep-link (F-01) that undercuts the product's most important
single transition, one piece of missing URL state (F-02) that quietly discards analyst
context, and a small, well-scoped set of discovery/consistency gaps (F-03/F-04/F-05)
that do not block any workflow today but will compound as investigation volume grows.
The "documented conditions" are the same environmental ones every prior MAX phase has
carried: no browser/viewport verification, no test-suite execution this pass, no Git
provenance in the supplied artifact.

**No fixes, components, CSS, tokens, routes, backend, Rust, or dependency changes have
been made.** The next step is a separate MAX-7 implementation/remediation prompt,
scoped against the findings above, once reviewed and authorized.

---

## 26. Artifact Information

| Artifact | Value |
| --- | --- |
| ZIP | `SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT-FULL.zip` |
| Entries | recorded externally — see delivery message (deterministic from final file set, not from the ZIP's own bytes; see hash-timing note below) |
| Size | recorded externally — see delivery message |
| SHA-256 | recorded externally — see delivery message |
| Extraction (fresh temp dir) | recorded externally — see delivery message |
| Source integrity | PASS — verified below |
| Browser verification | BLOCKED — no rendering surface available in this environment (§16) |

**Hash-timing note:** the exact byte size and SHA-256 of the final ZIP cannot be
embedded inside this Markdown file, because this Markdown file is itself one of the
ZIP's entries — writing its own future hash/size into its own content would change
that content, which would change the ZIP's bytes, which would invalidate the
already-written hash. This document's content is finalized as of this line; the ZIP is
built from it unchanged after this point; the size, hash, and extraction result are
computed after packaging and reported only in the delivery message, per this
project's own established convention (MAX-6's closure applied the identical
reasoning to its own archive hash, for the identical reason).

**Source integrity (verified before packaging):** no `.git` directory exists anywhere
in the supplied project artifact — Git provenance is unavailable, consistent with
every MAX-1–MAX-6 closure's own documented limitation. In its place, a full recursive
diff was run between this working tree and a second, pristine extraction of the
originally-supplied baseline ZIP (`SOC-IQ-FRONTEND-MAX-6-DESIGN-SYSTEM-FINAL-FULL.zip`).
Result: **exactly one file differs** — this audit document itself
(`docs/audits/SOC-IQ-FRONTEND-MAX-7-ANALYST-UX-AUDIT.md`), which did not exist in the
baseline and is new. Every other file — all of `app/` (Python/FastAPI), `src-tauri/`
(Rust/Tauri), `database/`, `packaging/`, `frontend/` (React/TypeScript/CSS, including
every MAX-1–MAX-6 change already baked into the supplied checkpoint), and every other
existing `docs/` file — is byte-identical to the baseline. No React, TypeScript, CSS,
token, test, backend, Rust, or dependency file was modified. **Source integrity:
PASS.**
