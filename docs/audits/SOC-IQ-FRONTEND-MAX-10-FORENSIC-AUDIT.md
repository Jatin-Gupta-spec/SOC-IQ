# SOC-IQ Frontend MAX-10 — Phase 1

## Post-MAX Product Evolution Forensic Audit

---

## 1. Executive Summary

SOC-IQ's frontend, nine MAX cycles in, is stable, lean, and honest about its
own data. This audit found **zero P0 findings and zero P1 findings**. It
found **one P2 finding** (Investigations list has no column sort — a
long-noted, previously-deferred gap that this audit is the first to treat
as a proper evidence-backed finding rather than a permanently-accepted
boundary) and **two INFO observations** (a workspace information-architecture
note about where Timeline lives, and a terminology mismatch between this
audit program's generic template language and the product's actual tab
names). `MAX9-F-01` (stale `package.json` description) remains open,
unchanged, carried forward from MAX-9.

The single largest standing gap is not a code defect: it is that **no MAX
phase since MAX-3 has ever rendered this application in an actual browser**.
Every accessibility/responsive/motion conclusion across seven phases
(MAX-3 through MAX-9) has been static/source-level. That fact is restated
here, not because it is new, but because a "highest-value next investment"
analysis has to be honest that it is auditing a product that has never
actually been watched running.

**Recommended MAX-10 direction:** implement column sorting on the
Investigations `DataTable` (§26–27) — the one area where accumulated,
repeated deferral has left a genuine, evidence-backed analyst-efficiency
gap in a primary discovery surface, with low regression risk and no
architectural change required.

**Verdict: `MAX-10 AUDIT COMPLETE WITH CONDITIONS`.**

---

## 2. Authoritative Baseline

- Started from `SOC-IQ-FRONTEND-MAX-9-ANALYST-UX-FINAL-FULL.zip`.
- ZIP integrity verified (`unzip -t`: no errors detected).
- SHA-256 of the input baseline archive: `9d3ace50b055d92c994d9fade9a271ecfe5ab8dac6b2b007d43344b12dc3eb5f`
  — recorded here for traceability; this is the *baseline's* hash, not
  this phase's output archive (that hash is computed fresh in §28, after
  finalization, per the ZIP-verification rule).
- Extracted cleanly. `docs/audits/SOC-IQ-FRONTEND-MAX-9-FINAL-CLOSURE.md`
  present, confirmed, states verdict `FRONTEND MAX-9 — PASS WITH DOCUMENTED
  CONDITIONS`.
- Read: MAX-9 final closure, MAX-9 Phase 1 forensic audit and Phases
  2A/2B/2C closures, MAX-8 production-readiness audit, MAX-7 analyst UX
  closure, MAX-6 design-system closure.
- **Git provenance unavailable; filesystem/static verification performed.**
  No `.git` directory found. Unchanged since MAX-3.

MAX-9 is confirmed closed on defensible terms. Proceeding.

---

## 3. Audit Method

- `npm install` (159 packages, clean), `npx tsc --noEmit` (clean),
  `npx vitest run` (82/82 files, 1172/1172 tests), `npx vite build`
  (clean, chunk-for-chunk identical to every MAX-9 phase's build) — all
  re-run directly in this phase, not assumed from MAX-9's record.
- Source-level review of every page (`DashboardPage`, `AnalyzePage`,
  `InvestigationsPage`, `InvestigationWorkspacePage` and its seven
  sub-components, `ReportsPage`, `SettingsPage`), the command palette and
  search-command module, the design-token/CSS layer, and the dependency
  manifest.
- Targeted greps for: fabricated/random data, mock imports outside
  Settings, TODO/FIXME, console.log, hardcoded colors, sort logic,
  dependency usage per import.
- **No application source, test, config, or dependency file was
  modified.** This audit document and its own working artifacts are the
  only additions.
- **No application source code was modified in this phase — audit only**,
  per this phase's own rule. Nothing below §26 constitutes an
  implementation; it is ranked candidates for a future, separately-scoped
  phase.
- **Environment limitation, unchanged since MAX-3:** no browser or dev
  server is available here. All accessibility/responsive/motion/visual
  conclusions in this document are **STATIC-VERIFIED** (source/CSS/test-
  based) unless explicitly marked otherwise, and are never reported as an
  observed rendering.

---

## 4. Product Maturity (Q3)

**No evidence of student-project or prototype behavior.** Concrete
indicators checked:
- Dependency footprint is deliberately lean: 6 runtime dependencies
  (`@tauri-apps/api`, `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-fs`,
  `react`, `react-dom`, `react-router-dom`), 8 dev dependencies. All three
  Tauri packages have confirmed in-source usage (15, 6, and 2 importing
  files respectively) — no unused heavy dependency.
- Zero `TODO`/`FIXME` markers, zero `console.log`, zero hardcoded colors
  outside the token file (re-confirmed this phase, same as MAX-9).
- No fabricated dashboard data: `DashboardPage.tsx` contains an explicit
  in-source comment disclaiming "No fake values, labels, percentages,
  names, or chart data," and no `mock` import — re-confirmed by direct
  read, not merely by trusting the comment.
- Terminology is internally consistent within the product itself (the
  workspace's own tab labels — "Overview," "IOCs," "Threat Intel,"
  "Correlations" — are used consistently across component names, test
  names, and CSS class prefixes).

**One notable stylistic trait, recorded as INFO not a finding:** source
files carry unusually extensive prose-style header comments (e.g.
`InvestigationWorkspacePage.tsx`'s header narrates its own build history
across "Part 1D," "Part 2A," "Part 3A," "Part 4A"). This is a heavier
in-source documentation style than is typical, but it is consistently
applied, doesn't block readability, and is not a maintainability defect —
recorded as a stylistic observation only.

**Score basis:** 8/10 — see §25.

---

## 5. Analyst Efficiency (Q2)

Traced the conceptual step count for each brief-specified task by reading
the actual component/hook wiring (not by clicking through, which is
environment-blocked):

| Task | Steps (source-traced) | Friction found |
|---|---|---|
| Find an investigation | Navigate → Investigations → (optional search/filter) → select row | None found; single list surface, no redundant intermediate screen |
| Understand investigation status | Status is visible directly in the Investigations row and again in the workspace header (`InvestigationHeaderCard`) | None — status isn't buried |
| Open investigation context | One click/activation on a row → workspace loads with URL-addressable identity | None |
| Review IOCs | Compact summary in Overview tab, full detail in dedicated IOCs tab | None — appropriately layered (summary→detail) |
| Review evidence/timeline | **Timeline is a card within the Overview tab, not a dedicated tab** (see §7, §22 finding INFO-1) | Real but currently INFO-level, not confirmed as analyst-impacting without volume data |
| Understand risk | `InvestigationOverviewRisk` renders directly in Overview, no extra navigation | None |
| Generate a report | Reporting flow reachable from workspace; `reportsViewModel` covers report state/export separately from workspace state | None found structurally |
| Export a report | Explicit export action with failure-state handling covered by `reportsViewModel.test.ts` | None found structurally |
| Recover from failure | Error/retry/stale-response handling independently re-validated by MAX-9 Phase 2C, unchanged since | None found; already hardened |
| **Sort an Investigations list by any column** | **Not possible — `DataTable` has no sort implementation** | **Genuine, evidence-backed friction (§26 candidate)** |

**Score basis:** 7/10 — one concrete, repeatedly-deferred friction point
(sorting) keeps this from a higher score; everything else traced clean.

---

## 6. Information Density

- Overview tab combines: header identity/status, risk, summary, a compact
  IOC distribution, a Threat Intel summary, and the timeline card — six
  regions on one tab. Each individually is compact (`InvestigationOverviewIOC`
  is 152 lines, `InvestigationOverviewTimeline` is 140 lines — both small,
  focused components), but six regions stacked on one tab is the densest
  single surface in the product.
- IOCs and Threat Intel each get their own dedicated, larger tab
  (`InvestigationIocWorkspace` at 665 lines, `InvestigationThreatIntel` at
  466 lines) — appropriately given more room than their Overview
  summaries.
- Dashboard sections are each independently labeled with `aria-label`
  (Key metrics, Operational status, Investigation overview, Recent
  investigations, Risk distribution, IOC distribution, Quick actions,
  Investigation activity) — eight distinct labeled regions, suggesting a
  deliberately segmented rather than monolithic layout.

**No evidence of either an overly sparse or an overly dense surface**
beyond the Overview tab's six-region stack, which is a genuine but modest
density concentration — recorded as INFO (§22, INFO-1), tied to the same
Timeline-placement observation, not a separate finding, since fixing one
plausibly addresses the other.

---

## 7. Investigation Workspace (Area 4)

Re-audited independently, not assumed healthy from MAX-9.

- Four real, selectable tabs confirmed by direct source read: **Overview,
  IOCs, Threat Intel, Correlations** — all real, none stubbed (`grep` for
  `mock` across all seven workspace sub-components: zero matches).
- Active tab is URL-persisted via a validated query param
  (`isWorkspaceTabId` guards against an invalid raw `?tab=` value before
  trusting it) — re-confirmed present, matches MAX-7's `MAX7-F-02` fix
  description exactly.
- Timeline data is real (`get_timeline`-backed) and honestly distinguishes
  three states — populated, genuinely empty, and unavailable — with the
  unavailable case explicitly never presented as if it were a real event
  history (`__fallback-note`, confirmed by direct read of
  `InvestigationOverviewTimeline.tsx`). This is a materially honest
  data-handling pattern, not a superficial label.
- **Finding INFO-1:** Timeline lives inside the Overview tab as one of six
  stacked regions rather than as its own top-level tab alongside IOCs/
  Threat Intel/Correlations, despite being backed by real, potentially
  large, ordered event data. For an investigation with a long real event
  history, this could mean scrolling past risk/summary/IOC/Threat-Intel
  summaries to reach timeline detail. This is plausible, not confirmed —
  no data-volume evidence (e.g., typical event counts per investigation)
  was available to this audit to say whether it is actually a problem in
  practice. Recorded as INFO, not P2, because the evidence bar for "real
  friction" isn't met yet — but noted as worth revisiting with real usage
  data.

**Determination: this is a genuine investigation cockpit**, not a shell —
four real tabs, real cross-tab identity, real timeline/IOC/threat-intel
data, honest empty/error handling. MAX-9's characterization is not
overturned; no evidence of it being "assumed perfect" without basis, and
no evidence found to reopen it.

---

## 8. Dashboard (Area 5)

Re-confirmed: no `mock` import, explicit in-source no-fabrication
disclaimer, eight independently `aria-label`ed sections, no `Math.random`
or synthetic-data pattern found anywhere in `DashboardPage.tsx`.

**No regression from MAX-5. No new finding.**

---

## 9. Analyze (Area 6)

309 lines; distinct configuration → run → progress → result states exist
as named component states (confirmed by the same pattern MAX-9's forensic
audit already verified — zero `mock` imports, real `useAnalysisExecution`
hook). No new finding; nothing in this phase's review contradicts MAX-9's
conclusion that Analyze is real and workflow-complete.

---

## 10. Reporting (Area 7)

`ReportsPage.tsx` (298 lines) and `reportsViewModel.ts`/test (6 passing
tests) separate report *state* from report *export*, which is the correct
split for "was the report generated" vs. "did the export actually
succeed" — consistent with MAX-9's explicit rule that export success must
never be claimed unless the application itself reports it. No evidence
this rule is violated in current source.

**No new finding.**

---

## 11. Search / Discovery (Area 8)

Two distinct search surfaces exist, and they serve different purposes:
- `searchCommands.ts` — deterministic substring search over the **command
  palette's** command/navigation list (not investigation records). Its
  own header comment explains it deliberately avoids fuzzy-matching and
  relevance scoring, since no such dependency exists in the project and
  none was authorized.
- The Investigations page's own search/filter (independently re-validated
  by MAX-9 Phase 2C).

**No evidence of a meaningful discovery gap.** Per this audit's own
instruction not to assume global search is necessary absent evidence: none
was found. The command palette already provides fast cross-page
navigation; investigation-record search is scoped correctly to the
Investigations list itself, which is where an analyst would expect it.

---

## 12. Design System (Area 9)

Re-ran the hardcoded-color grep independently this phase: zero hits
outside `tokens.css`. Single `DataTable`, single `Button`, single `Card`
confirmed by directory listing — no shadow/duplicate implementation
found anywhere in `pages/components/`.

**No systemic inconsistency found. No new finding.**

---

## 13. Accessibility (Area 10)

Re-ran the same static checks MAX-9 used, independently: `aria-*` present
across 55 `.tsx` files (identical count to MAX-9's re-check), MAX8-F-06's
focus-suppression pattern still absent.

**STATIC-VERIFIED only** — no live keyboard/focus/screen-reader
observation was newly performed, consistent with every phase since MAX-3.
No regression evidence found.

---

## 14. Responsive / Desktop Viewports (Area 11)

Breakpoints at 640px/900px/1280px re-confirmed present in CSS (identical
to MAX-9's finding). **NOT VERIFIED — ENVIRONMENT-BLOCKED** for actual
rendering at 1280×720 or 1440×900. Unscored (`N/A`), consistent with every
phase since MAX-3 — not newly discovered, not treated as a defect.

---

## 15. Motion (Area 12)

`prefers-reduced-motion` handling present in 11 CSS files (identical count
to MAX-9). No decorative/looping animation found in source. No source
changed since MAX-9, so nothing could have newly regressed.

**STATIC-VERIFIED. No new finding.**

---

## 16. Performance (Area 13)

Build output is chunk-for-chunk identical to MAX-9's build (same file
names, same byte sizes, e.g. `InvestigationWorkspacePage` chunk at 37.36
kB / 9.07 kB gzip). No evidence of new render loops, duplicate requests,
or memory growth was found in source — but this audit did not (and could
not, environment-blocked) load-test with a realistic large investigation
list or dense IOC/timeline dataset, which the brief specifically calls
out as the relevant test. **This is recorded as an evidentiary gap, not a
finding of a problem** — there is no evidence of a performance defect, but
there is also no evidence that performance holds up under realistic
analyst-scale data, because no such environment or dataset was available
to this audit.

---

## 17. Build / Dependency Health (Area 14)

- 6 runtime + 8 dev dependencies. All runtime dependencies confirmed used
  by direct import grep. No duplicate packages found in the lockfile
  (single `package-lock.json`, no `pnpm-lock`/`yarn.lock` coexisting).
  No accidental heavy dependency (no charting library, no date library,
  no lodash-class utility belt) — the product does its own thin
  view-model layer instead (`investigationsViewModel.ts`,
  `reportsViewModel.ts`, etc.), which keeps the dependency surface small.
- No upgrades performed or recommended in this phase, per this phase's
  own rule.

**No finding. Healthy.**

---

## 18. Runtime Reliability (Area 15)

Covered indirectly through the same passing automated suite MAX-9
independently re-validated for recovery/retry/stale-response protection
(generation-counter-based, per Phase 2C). No live failure-injection
session was newly performed in this phase (environment-blocked, same as
every prior phase).

**STATIC-VERIFIED via test suite. No new finding.**

---

## 19. Data Credibility (Area 16)

Checked specifically for the failure mode the brief calls out — UI
assumptions distorting backend truth — across Dashboard and the
Investigation Timeline component, the two places most likely to invent
data:
- Dashboard: no fabrication found (§8).
- Timeline: explicitly, three-way honest state handling (populated /
  genuinely-empty / unavailable) with the fallback state visibly labeled
  as a fallback, never presented as real history (§7).

**No evidence of the frontend distorting backend truth anywhere sampled.
No new finding.**

---

## 20. Codebase Evolution (Area 17)

Checked specifically for signs of nine-cycle accumulation:
- **Duplicate abstractions:** the closest candidate is the
  Overview-summary vs. dedicated-tab pairs (`InvestigationOverviewIOC` +
  `InvestigationIocWorkspace`; `InvestigationOverviewThreatIntel` +
  `InvestigationThreatIntel`). On direct read, these are not duplicates —
  the Overview versions are compact summaries (152/155 lines) and the tab
  versions are the full detail views (665/466 lines), a deliberate
  summary/detail split, not redundant reimplementation. Not a finding.
- **Dead components:** none found — every component file located has a
  corresponding import site and a corresponding test file.
- **Stale comments:** the extensive "Part 1D / Part 2A / Part 3A" header
  narration (§4) is historical but internally consistent with what the
  code actually does on direct read — not found to be inaccurate,
  therefore not "stale" in the sense of misleading.
- **CSS/token fragmentation:** zero hardcoded-color violations found
  (§12); one CSS file per component, consistently, no found evidence of
  a second competing styling approach.

**No material maintainability complexity found. No new finding.**

---

## 21. Test Health (Area 18)

```text
$ npx tsc --noEmit
(no output — clean)

$ npx vitest run
Test Files  82 passed (82)
     Tests  1172 passed (1172)
  Duration  58.85s

$ npx vite build
✓ 201 modules transformed.
✓ built in 2.96s
```

Identical counts to MAX-9. Spot-checked test specificity (not just count):
`investigationRouteParams.test.ts` (16 tests, identity/route-param
correctness), `investigationsCsvExportPath.test.ts` (6 tests, export path
correctness) — both behaviorally specific, not shallow snapshot coverage.

---

## 22. Realistic User Journeys (Area 19)

All five scenarios traced via source (not click-through, environment-
blocked):

- **A — New Analysis:** file selection → configure → run → progress →
  result — all real states confirmed present in `AnalyzePage.tsx`
  (§9). No missing step found.
- **B — Investigation Review:** Investigations → open → risk → evidence/
  IOCs → timeline — all reachable; timeline reachable but nested inside
  Overview rather than a dedicated tab (INFO-1, §7).
- **C — Reporting:** workspace → report → review → export → return —
  state/export split confirmed (§10); no missing step found.
- **D — Failure Recovery:** covered by MAX-9 Phase 2C's independently
  re-validated error/retry/stale-response handling; no regression
  evidence found.
- **E — Search/Filter:** Investigations search/filter re-validated by
  MAX-9 Phase 2C; **sorting is the one step in this journey the analyst
  cannot do** (§5, §26).

---

## 23. MAX-1 → MAX-9 Regression Review

| Foundation | Status | Regression? | Evidence |
|---|---|---|---|
| MAX-1 Accessibility | Static-healthy | No | 55 files with `aria-*`, MAX8-F-06 pattern absent, re-confirmed this phase |
| MAX-2 Loading | Healthy | No | Loading states present per page, covered by passing tests |
| MAX-3 Responsive | Unverified (not regressed) | N/A | ENVIRONMENT-BLOCKED, unchanged since MAX-3 |
| MAX-4 Motion | Static-healthy | No | 11 files with reduced-motion handling, no new animation, no source changed |
| MAX-5 Dashboard/Data | Healthy | No | No mock import, no fabrication, re-confirmed §8 |
| MAX-6 Design System | Healthy | No | Zero hardcoded-color violations, re-confirmed §12 |
| MAX-7 Analyst UX | Healthy | No | MAX7-F-02 URL-tab-validation pattern re-confirmed present §7 |
| MAX-8 Production Readiness | Healthy | No | Build/chunk output identical to MAX-9 baseline |
| MAX-9 Analyst Hardening | Healthy | No | Zero source changes since MAX-9; identical test/build results |

No foundation reopened without evidence. None found to have regressed.

---

## 24. Full Finding Register

```text
ID: MAX10-F-01
Priority: P2
Area: Analyst Efficiency / Search-Discovery / Design System
Location: frontend/src/pages/components/DataTable.tsx; consumed by
  frontend/src/pages/InvestigationsPage.tsx
Observed: DataTable has no column-sort capability. An analyst viewing the
  Investigations list cannot reorder it by status, date, or risk from the
  UI itself.
Evidence: Direct source read of DataTable.tsx — no sort state, no
  sort handler, no clickable-header-sort affordance found. This absence
  was first noted (and explicitly deferred, not fixed) in MAX-9 Phase 2C's
  closure ("DataTable's absence of a sort capability is noted as a known,
  already-accepted dependency... not implemented here because doing so
  would extend DataTable's contract without a specific finding
  authorizing that scope expansion").
Impact: Medium. For a list-based triage surface, column sort is a
  conventional expectation of any professional data-grid; its absence is
  a genuine, if modest, efficiency cost every time an analyst wants
  the list ordered by something other than its default order.
Why it matters: This gap has now been carried, unexamined as an actual
  finding, across at least two MAX cycles (MAX-8 → MAX-9 → this audit)
  purely because no phase's narrow scope authorized raising it as one.
  MAX-10's explicit purpose is to ask what genuinely matters next rather
  than continue that pattern.
Recommended direction: Add column sort to DataTable (ascending/descending
  toggle on sortable columns), scoped first to the Investigations list's
  status/date/risk columns. Should reuse existing DataTable
  state-ownership patterns (per MAX-9 2C's finding that DataTable already
  owns delegated state cleanly) rather than introducing a second state
  mechanism.
Regression risk: Low-medium. Additive to an existing, well-tested
  component; existing DataTable consumers with no sort config should be
  unaffected if sort is opt-in per column.
Confidence: High (the absence itself); Medium (the size of the resulting
  analyst-efficiency benefit, since no volume/usage data was available to
  this audit).
```

No P0 or P1 finding exists anywhere in this audit. `MAX10-F-01` is the
only registered P2. `MAX9-F-01` (P3, `package.json` description) remains
open, unchanged, carried forward from MAX-9 — not re-litigated here since
nothing new bears on it.

---

## 25. Scorecard

| Area | Score /10 | Basis |
|---|---:|---|
| Product Maturity | 8 | Lean deps, no fabricated data, consistent terminology; heavier-than-typical comment style noted as INFO only |
| Analyst Efficiency | 7 | Every traced task clean except sorting (MAX10-F-01) |
| Information Density | 7 | Mostly well-segmented; Overview tab's six-region stack is the one dense concentration (INFO-1) |
| Investigation Workspace | 8 | Four real tabs, honest timeline data handling; INFO-1 on Timeline placement |
| Dashboard | 9 | No fabrication, well-labeled regions, re-confirmed healthy |
| Analyze Workflow | 8 | Real, complete states; no new finding |
| Reporting | 8 | State/export correctly separated; no new finding |
| Search/Discovery | 8 | Two appropriately-scoped search surfaces; no evidence of a gap |
| Design System | 9 | Zero token-discipline violations |
| Accessibility | 7 | Structurally sound (static); live behavior still never observed since MAX-3 |
| Responsive | N/A | ENVIRONMENT-BLOCKED, unchanged |
| Motion | 8 | Structural coverage confirmed; live motion never observed |
| Performance | 6 | No defect evidence, but no realistic-scale load test possible in this environment — genuine evidentiary gap |
| Runtime Reliability | 7 | Covered by tests; no live failure-injection session |
| Data Credibility | 9 | No fabrication found anywhere sampled |
| Architecture | 9 | Stable, no drift, no rewrite indicated |
| Maintainability | 8 | No dead code, no duplicate abstractions found; heavy comment style is a style choice, not a defect |
| Test Health | 10 | 82/82, 1172/1172, directly re-run |
| Production Readiness | 8 | Zero P0/P1; one new P2, one carried P3; environment gaps disclosed, not hidden |

---

## 26. Ranked Next-Investment Candidates

```text
Candidate: Investigations DataTable column sort
Problem: Analyst cannot reorder the primary discovery list by status/date/risk.
Evidence: MAX10-F-01 (§24); independently noted (and deferred) in MAX-9 2C.
Expected analyst impact: Medium — real, recurring, conventional-expectation gap on a primary surface.
Engineering complexity: Medium — additive to existing DataTable/state pattern.
Regression risk: Low-medium.
Why now: Twice-deferred purely on scope-authorization grounds, not on merit; MAX-10 exists to make exactly this call.
Why not: No usage-volume data confirms how often analysts would actually reorder the list; benefit size is somewhat assumed.
Priority: P2
```

```text
Candidate: Live browser/visual verification pass (accessibility, responsive, motion)
Problem: Every a11y/responsive/motion conclusion since MAX-3 is static-only; nothing has ever been watched rendering.
Evidence: Every MAX phase 3 through 10 states ENVIRONMENT-BLOCKED for this exact gap.
Expected analyst impact: Unknown until performed — that is precisely the risk: seven phases of unverified assumption.
Engineering complexity: Not a coding task — requires a browser-capable verification environment, not application changes.
Regression risk: None (verification only).
Why now: The gap is now old enough (7 phases) that its absence is itself the most notable pattern in this entire audit history.
Why not: Outside this audit's and this phase's control — no application-code phase can close it; it needs an environment change, not a MAX-10 engineering phase.
Priority: P1 in importance, but not schedulable as a MAX-10 coding phase — recorded as a standing infrastructure recommendation rather than the chosen direction.
```

```text
Candidate: Move Timeline to its own workspace tab (INFO-1)
Problem: Real, potentially large timeline data lives inside a six-region Overview tab rather than getting dedicated space.
Evidence: §6, §7 — structural observation only, no usage-volume evidence.
Expected analyst impact: Unknown — plausible but unconfirmed.
Engineering complexity: Medium (new tab, routing/test updates).
Regression risk: Low-medium (touches the workspace tab model MAX-7 hardened).
Why now: Architecture is stable enough to support it if evidence later confirms the need.
Why not: Doesn't yet meet this program's own evidence bar (§ audit evidence standard) — recorded as INFO, not promoted to a finding, and not recommended for immediate action.
Priority: INFO — revisit if usage data becomes available.
```

## RECOMMENDED MAX-10 DIRECTION

**Implement DataTable column sort on the Investigations list (`MAX10-F-01`).**
It is the only candidate that is simultaneously evidence-backed (not
speculative), scoped to a specific and bounded change (not a redesign),
low-to-medium regression risk, and additive to an already-hardened
component rather than requiring new architecture. The live-browser-
verification gap is arguably higher-importance in the abstract, but it
is not something a MAX-10 *engineering* phase can implement — it is a
standing recommendation for whoever controls this project's execution
environment, not a coding deliverable, and is recorded as such rather
than forced into this phase's direction to make the ranking look tidier
than the evidence supports.

---

## 27. Explicit Non-Findings

```text
No evidence of architecture instability.
No evidence of fabricated dashboard data.
No evidence of MAX-1 tab accessibility regression (focus-suppression pattern absent, re-confirmed).
No evidence of generic page-level scrolling being required anywhere in source.
No evidence of duplicate component systems (single DataTable, single Button, single Card).
No evidence of a meaningful search/discovery gap beyond sorting.
No evidence of hardcoded colors or design-token violations.
No evidence of dead components or unused dependencies.
No evidence of test weakening, deletion, or skipping since MAX-9.
No evidence that MAX-9's zero-source-change record was inaccurate — independently re-confirmed by identical build/test output.
```

---

## 28. ZIP Verification

(Recorded after packaging; see final message for the computed values —
entry count, file count, byte size, SHA-256, extraction check, nested-zip
check, and audit-document presence check, all performed after
finalization per this phase's own rule that the archive's own hash cannot
be written inside itself.)

---

## 29. Final Verdict

```text
MAX-10 AUDIT COMPLETE WITH CONDITIONS
```

Conditions:
1. `MAX9-F-01` (stale `package.json` description, P3) remains open,
   carried forward unchanged.
2. `MAX10-F-01` (Investigations DataTable has no column sort, P2) is a new,
   evidence-backed finding, recommended as the MAX-10 direction, **not
   implemented in this phase** — this phase is audit-only per its own
   hard-stop rule.
3. Live browser/visual verification (accessibility, responsive at
   1280×720/1440×900, motion, keyboard, screen-reader) remains
   unperformed across all ten MAX cycles to date. This closure's
   Accessibility/Responsive/Motion scores are static-only and should not
   be read as an observed QA pass.
4. Two INFO-level observations (Overview-tab density / Timeline placement;
   heavier-than-typical inline comment style) are recorded for awareness,
   not as findings requiring action.

---

## Hard Stop

This is MAX-10 Phase 1 only. No finding was implemented. No frontend
source was modified. No redesign was proposed. No dependency was
upgraded. Phase 2 does not begin automatically. Awaiting explicit approval
before any further MAX-10 work.
