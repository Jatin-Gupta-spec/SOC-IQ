# Phase 4O — Final Closure Audit (Part 5)

**Verdict: OPTION B — COMPLETE WITH INTENTIONAL RETAINED LEGACY.**
No further technically safe retirement of `app/gui`/`tests/gui` is
possible in this session without either implementing missing modern
functionality or getting a product "no, drop it" answer on three
named behaviors. Both are explicitly out of scope for Phase 4O
(Part 9 of the master instructions). This is the correct, honest
result, not a shortfall.

---

## 1. Phase 4O Objective

Retire the legacy PySide6 GUI (`app/gui/**`, `tests/gui/**`) wherever
it is provably redundant with the modern React/Tauri stack, while
never deleting behavior that has no modern equivalent, no modern test
coverage, or is still needed by retained legacy tests — and without
making any product decisions on the audit's behalf.

## 2. Part 3 Baseline (parity audit, prior session)

Per `PHASE4O_PART3_LEGACY_GUI_PARITY_AUDIT.md`: 108 original
`app/gui/**` files (97 production modules + 11 `__init__.py`), 12
`tests/gui/**` suites, zero deletions made. It flagged
`design/icons/` as one of three "empty" packages — an
inventory error corrected in Part 4 (§B.1 below).

## 3. Part 4 Baseline (retirement, prior session) — Revalidated

This session independently re-verified every quantitative claim in
`PHASE4O_PART4_LEGACY_GUI_RETIREMENT.md` against the actual
filesystem and a fresh test run, rather than trusting the report:

| Claim | Verified |
|---|---|
| 42 production files (including the sole occupant of `app/gui/styles/`) retired | **Confirmed** — all 42 listed files, and the 8 emptied subdirectories, are absent from disk. See `PHASE4O_CLOSURE_REMEDIATION_AND_FREEZE.md` §5 for the correction of this session's original "41 files + 1 directory" phrasing, which double-counted one file as also a directory. |
| 66 production files retained | **Confirmed** — `find app/gui -name '*.py'` returns exactly 66. |
| 4 `__init__.py` files edited to drop dangling exports | **Confirmed** — `components/__init__.py`, `components/buttons/__init__.py`, `components/feedback/__init__.py`, `components/layout/__init__.py` all match the documented export lists exactly. |
| 5 of 12 GUI test suites retired | **Confirmed** — `tests/gui/` contains exactly 7 `test_*.py` files, matching the "retained" list in Part 4 §E. |
| GUI tests 142 → 104 | **Confirmed** — fresh `pytest tests/gui -q` under `QT_QPA_PLATFORM=offscreen`: **104 passed, 0 failed.** |
| Backend 780 passing | **Confirmed** — fresh `pytest tests/ --ignore=tests/gui -q`: **780 passed.** |
| Frontend 965 tests / 70 files | **Confirmed** — fresh `npx vitest run`: **965 passed (70 files).** |
| TypeScript 0 errors | **Confirmed** — fresh `npx tsc --noEmit`: clean. |
| Build succeeds, 193 modules | **Confirmed** — fresh `npm run build`: 193 modules transformed, build succeeds. |
| Rust environment-blocked | **Confirmed** — no `cargo`/`rustc` binary present in this container. |

No discrepancy was found between the Part 4 report and the actual
state of the repository.

## 4. Final Legacy GUI Inventory

- **66 production files** under `app/gui/**` (unchanged from Part 4 —
  this session retired none further; see §17).
- **7 test suites** under `tests/gui/**`.
- No runtime entrypoint currently wires these pages together —
  `app/gui/app.py` and `app/gui/main_window.py` (the last two
  launchers) were already deleted in Part 4 as confirmed-dead code;
  neither `app/main.py` nor `app/cli.py` reference `app.gui` at all.
  The retained 66 files exist purely as (a) definitions of behavior
  that has no modern equivalent yet, and (b) the tests that pin that
  behavior — not as a runnable application. This was already true the
  moment Part 4 removed the last launcher, and is not a new or
  concerning finding.

## 5. Complete Retirement History

- **Part 4** (prior session): 42 production files retired (one of
  which was the sole occupant of `app/gui/styles/`, so that directory
  was also removed as a consequence — not a 43rd item), 5 test
  suites retired, 4 `__init__.py` files trimmed. See §3 above for
  fresh verification.
- **Part 5** (this session): **zero additional files retired.** The
  orphan sweep in §15 below found no new provably-dead code; every
  remaining file traces to either a retained test or a retained
  product gap.

## 6. Remaining Legacy Modules

All 66 retained production files, grouped by why they remain (detail
in §7–§13):

- **Product-gap modules** (no modern equivalent exists):
  `risk_explanation_widget.py`, the significance half of
  `ioc_summary_widget.py`, `csv_exporter.py`, `history_page.py`,
  `settings_page.py`.
- **Composition root and its transitive closure**:
  `investigation_workspace.py` plus the 13 modules it directly
  imports (unchanged from Part 4 §D), because 5 of the 7 retained
  test suites import it.
- **Design-system foundation**: all of `design/tokens/*` (8 files),
  `design/theme/{palette,font_factory,theme_manager}.py`, and
  `design/icons/__init__.py` — all load-bearing for the widgets above.
- **Supporting widgets/components/events/models/controllers**: the
  remainder of `widgets/*`, `components/*`, `events/*`,
  `models/investigation_table_model.py`,
  `controllers/history_controller.py`,
  `services/investigation_correlation_context.py`,
  `services/ioc_detail_context.py` (compatibility shim, still imported
  by `tests/test_threat_intel_state.py`).

## 7. Dependency Analysis (this session)

A lightweight full-project reference scan was run over every retained
`app/gui` module this session (grep-based cross-check of Part 4's
AST-graph claims, not a re-derivation from scratch). Two points worth
recording:

- `app/gui/design/icons/__init__.py` now has exactly **one** internal
  importer, `components/cards/metric_card.py` (the other four
  importers named in Part 4 §B.1 were themselves retired in Part 4).
  `metric_card.py` is in turn imported by `pages/threat_intel_page.py`,
  which is retained (covered by `test_threat_intel_page_url.py` and
  `test_investigation_workspace_threat_intel.py`). The icon module is
  still genuinely load-bearing — see §13.
- `services/ioc_detail_context.py` and `pages/history_page.py`
  initially looked reference-free under a naive dotted-path grep, but
  both are real: `ioc_detail_context` is imported by
  `tests/test_threat_intel_state.py::TestGuiCompatibilityReExport`
  (outside `tests/gui`, exactly as Part 4 §B.2 documented), and
  `history_page.py` has no *importer* in the current tree — its
  survival is justified entirely on product-gap grounds (§10), not on
  dependency grounds, and is documented as such rather than miscounted
  as "in use."

## 8. Test Parity Analysis

No test-count regression this session (104/104, 780/780, 965/965 all
unchanged, freshly re-run — see §3). The three UNCERTAIN gaps from
Part 4 §E were individually re-investigated this session (§14); none
were resolved to retirement, so no further test-count change resulted.

## 9. Risk Narrative Decision — `RETAINED_MODERN_GAP`

`risk_explanation_widget.py` renders output from
`app.services.risk_explanation_service.RiskExplanationService`. This
session confirmed:

- Zero non-test, non-legacy references to `RiskExplanation` or
  `risk_explanation` anywhere under `frontend/src`.
- Zero references to it in `app/api` or `src-tauri` — the backend
  service exists but is **not exposed through any command or endpoint**
  the frontend could call, let alone rendered by one.

No frontend implementation was invented to close this gap (out of
scope per Part 9 of the master instructions). Carried forward
unchanged.

## 10. Risk Significance Decision — `RETAINED_MODERN_GAP`

The per-category "Risk Significance" badge in `ioc_summary_widget.py`
is driven by `app.services.ioc_significance.ioc_type_significance()`,
which reads `RiskScoringEngine.IOC_WEIGHTS` to label each IOC category
(e.g. "SHA256 Hash") High/Medium/Low. This session confirmed:

- Zero non-test references to "significance" anywhere in
  `frontend/src`.
- The frontend's actual per-row badges in
  `InvestigationIocWorkspace.tsx` are a neutral "Type" badge (the IOC
  category name) and a threat-intel enrichment-state badge — neither
  encodes the category-weight concept the legacy badge shows. This is
  the specific "visually similar but behaviorally different" trap the
  master instructions warned against; it was checked for directly and
  ruled out.

Carried forward unchanged.

## 11. CSV Export Decision — Option C, still legacy-only, `RETAINED`

`app/gui/utils/csv_exporter.py` exports a *list* of investigations to
CSV; `history_page.py` is its only caller. This session found direct,
explicit evidence in the modern command layer itself:
`app/application/dto.py`'s `ExportReportRequest` docstring states
the modern `export_report` command is deliberately restricted to four
formats (html/pdf/json/markdown) and **explicitly excludes** the CSV
path, because the legacy exporter's list-based signature has no
confirmed single-investigation call site and wrapping it would be
inventing behavior rather than migrating it. `frontend/src` has zero
CSV references. This is a clean **Option C** (still legacy-only), not
obsolete and not already replaced — retained with direct evidence,
no new command was written (per Part 9's explicit prohibition).

## 12. Settings Decision — `RETAINED — MODERN EQUIVALENT INCOMPLETE`

`app/gui/pages/settings_page.py` contains real behavior: saving a
VirusTotal API key, browsing/setting an export directory, and
applying a theme, all via `app.settings.service.SettingsService`.
`frontend/src/pages/SettingsPage.tsx` was read this session; its own
docstring states plainly that it is a mock page whose controls are
"restricted to what the frontend information-architecture doc
actually names" and are all rendered `disabled`, with an explicit
"no changes made here are saved" notice. This is not a matter of
interpretation — the modern page documents its own incompleteness.
No settings architecture was implemented (out of scope per Part 9).
Retained and documented per the master instructions' exact required
label.

## 13. Icon-Module Decision — `RETAINED`

`app/gui/design/icons/__init__.py` (corrected from Part 3's "empty"
misclassification, per Part 4 §B.1) has exactly one remaining internal
importer this session: `components/cards/metric_card.py`, which is
itself used by the retained `pages/threat_intel_page.py`. Real,
load-bearing, single-hop dependency chain — retained.

## 14. UNCERTAIN Test Decisions (this session's re-investigation)

| Test | Named gap | This session's check | Classification |
|---|---|---|---|
| `test_application_state_selected_ioc.py` | `ApplicationState`-singleton semantics (select clears on new investigation, explicit clear) with no 1:1 React analog | Confirmed: the React equivalent (`InvestigationIocWorkspace.tsx`) tracks the selected IOC as local component `useState`, not a global singleton with the same clear/select lifecycle. The state-shape difference is real, not cosmetic. | **RETAIN_TEST** |
| `test_investigation_workspace_threat_intel.py` | Double-click-to-navigate from an enriched TI cell | Searched `InvestigationThreatIntel.tsx` and `InvestigationIocWorkspace.tsx` for any double-click/navigate handler — found none; only single-click selection and copy handlers exist. | **RETAIN_TEST** |
| `test_ioc_detail_experience.py` | Dialog offers "view full record" only when the IOC is enriched | Searched for "View full record"/"ViewFullRecord" and any enrichment-gated action in the investigation pages — found only the `enriched`/`not_enriched` status *labels*, no gated action of any kind. | **RETAIN_TEST** |

None could be safely retired or split off into `MIGRATE_COVERAGE` this
session: in each case the missing frontend behavior itself doesn't
exist yet, so adding a "minimum appropriate test to the modern layer"
would mean testing behavior that isn't implemented — which the master
instructions (Part 2, Part 9) explicitly forbid inventing.

`test_phase3e_acceptance.py` and `test_threat_intel_page_url.py`
remain mixed suites (Part 4 §K.4) — not split this session; that
remains a documented, deferred future task, not a blocker to Option B.

## 15. Final Deletion List

**None.** No file was deleted in this session.

## 16. Final Retained List

Unchanged from Part 4 §G: 66 production files under `app/gui/**`, 7
test suites under `tests/gui/**`. See §6 for the grouped rationale.

## 17. Product Decisions Still Required

Unchanged from Part 4 §K, still open:

1. Is the "Why this risk?" narrative required in the modern app? If
   "no," `risk_explanation_widget.py` and its test can retire.
2. Is the per-category Risk Significance badge required? If "no," the
   significance half of `ioc_summary_widget.py` and the corresponding
   assertions in `test_ioc_summary_risk_relevance.py` can retire.
3. Is bulk CSV export of investigation history still a required
   feature? If "no," `csv_exporter.py`/`history_page.py` retire; if
   "yes," it needs an explicit modern-architecture decision (new
   command + UI) that is out of Phase 4O's scope to make.
4. Is `settings_page.py`'s functionality in scope for the current
   frontend milestone, or deferred? The frontend page's own docstring
   suggests deferred-by-design, but that is a product call, not a
   technical one this audit can make.
5. The double-click TI-navigation and enrichment-gated dialog-action
   gaps (§14) each need either a small, explicitly-scoped frontend
   task or an explicit "won't implement" call.

Until at least one of (1)–(3) gets a "no," `investigation_workspace.py`
and everything it transitively pulls in (§6) — the majority of the
remaining file count — has no path to retirement, regardless of how
many further audit passes are run.

## 18. Regression Results (this session, fresh)

```
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/gui -q
  104 passed

python3 -m pytest tests/ --ignore=tests/gui -q
  780 passed, 4 warnings (unrelated async-mock warnings, pre-existing)

cd frontend && npx vitest run
  965 passed (70 files)

cd frontend && npx tsc --noEmit
  0 errors

cd frontend && npm run build
  193 modules transformed, build succeeds

cargo check / cargo test
  ENVIRONMENT-BLOCKED — no cargo/rustc binary in this container.
```

All figures match the Part 4 baseline exactly. No regressions, no
new failures, no test-count drift.

## 19. Frozen-Area Verification

This session did not have the Part 3 baseline archive available to
re-run Part 4's own byte-level recursive diff. In its place, this
session verified consistency the available way: every file Part 4
claimed retired is absent, every file it claimed retained is present
and matches its documented content (§3–§7), and the full regression
suite (§18) — which would fail immediately if any frozen subsystem
(Dashboard, Reporting, Threat Intel, Integration, Investigation
Workspace, Tauri commands, database schema) had been touched —
reproduces Part 4's exact pass counts. This is strong but indirect
evidence of frozen-area integrity; a true byte-diff against the Part 3
archive was not repeated this session because that archive was not
part of this session's input.

Stray generated artifacts present at the start of this session and
excluded from the final archive: `database/soc_iq.db` (incidental,
created by a prior local test run) and 27 `__pycache__` directories.

## 20. Final Phase 4O Verdict

**OPTION B — COMPLETE WITH INTENTIONAL RETAINED LEGACY.**

Every remaining `app/gui` file and `tests/gui` suite was checked this
session and falls into one of exactly three buckets:

- **TECHNICALLY RETIRED**: 41 files + 1 directory + 5 test suites
  (Part 4, re-confirmed this session — §3).
- **RETAINED BECAUSE MODERN EQUIVALENT IS MISSING**:
  `risk_explanation_widget.py` (§9), the significance half of
  `ioc_summary_widget.py` (§10), `csv_exporter.py`/`history_page.py`
  (§11), `settings_page.py` (§12), and everything the
  `investigation_workspace.py` composition root pulls in transitively
  (§6) because the retained tests covering these gaps still import it.
- **RETAINED BECAUSE PRODUCT DECISION IS REQUIRED**: the same five
  items above, framed the other way — each has a concrete yes/no
  question (§17) whose "no" answer is the only thing that would let
  it retire. No such answer was given to this audit, and this audit
  is explicitly not positioned to invent one (Part 3/4/9 of the master
  instructions).

No file was force-deleted to improve the file count. No frontend
functionality was invented to manufacture false equivalence. No new
backend command, database schema, or settings architecture was built.

## 21. Exact Next Phase Recommendation

Phase 4O cannot make further technical progress without one of:

- A product decision on items (1)–(4) in §17, which would let this
  audit's *next* part immediately retire the corresponding legacy
  module(s) and, once all three of (1)–(3) are resolved "no," retire
  `investigation_workspace.py`'s remaining closure and remove
  `PySide6` from `requirements.txt` entirely; **or**
- A scoped frontend implementation task (outside Phase 4O, per Part 9)
  to close one or more of: the risk-narrative view, the
  risk-significance badge, bulk CSV export, the settings page, TI-cell
  double-click navigation, or the enrichment-gated "view full record"
  action — after which the corresponding legacy widget and test
  retire on the same technical grounds Part 4 already used for the 41
  files it retired.

Recommended immediate next step: route items (1)–(4) in §17 to
whoever owns the product roadmap for a yes/no, rather than opening a
Phase 4P audit pass with no new evidence to act on.
