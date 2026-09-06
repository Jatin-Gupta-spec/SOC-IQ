# Phase 4O — Part 4: Legacy GUI Retirement

**Status:** PARTIAL RETIREMENT COMPLETE. This part deleted a proven-safe
subset of `app/gui/**` and `tests/gui/**` production/test files based on
the Part 3 evidence base plus this part's own file-by-file re-confirmation
at deletion time (per the master instructions). It did **not** achieve
"legacy GUI fully retired" — a real majority of `app/gui` remains, for
concrete, evidenced reasons documented below. This is not a partial
failure; it is the correct outcome given what still lacks a modern
equivalent or modern test coverage.

---

## A. Baseline

- Part 3 checkpoint: `docs/phase4/PHASE4O_PART3_LEGACY_GUI_PARITY_AUDIT.md`
  (`SOC-IQ-Phase4O-MIGRATION-P3-PARITY-AUDIT-CHECKPOINT.zip`).
- 108 original `app/gui/**` Python files (97 production modules + 11
  `__init__.py` package markers).
- 12 original `tests/gui/**` test-suite files (+ `conftest.py`,
  `__init__.py`).
- Part 3 made no deletions; this part is the first to touch these
  directories.

## B. Dependency Analysis (Part 1 of this part's own work)

Before any deletion, this part built a real AST-parsed import graph over
all 108 `app/gui/**` files (not a text grep) and cross-referenced it
against the actual imports in all 12 `tests/gui/**` files. This caught
two things Part 3's file-by-file table did not surface at the
whole-graph level:

1. **`app/gui/design/icons/__init__.py` is not empty and is not dead.**
   Part 3's inventory (§2) described `design/icons/` as one of three
   "empty" packages alongside `animations/` and `effects/`. In fact it
   contains a real ~200-line vector icon-rendering module (`Icon` enum,
   `icon_pixmap()`, `icon()`), and it has five real internal importers
   still being retained in this part: `components/cards/metric_card.py`,
   `components/feedback/file_dropzone.py` (retiring, see below),
   `components/timeline/timeline_widget.py` (retiring), `widgets/dashboard/kpi_section.py`
   (retiring), and `widgets/progress_dialog.py` (retiring). It survives
   this part only because `metric_card.py` — a retained component — still
   needs it. This correction is noted for any future retirement pass:
   `design/icons/` is real, load-bearing code, not dead weight.
   `design/animations/__init__.py` and `design/effects/__init__.py`,
   by contrast, really are unreferenced anywhere in `app/gui` (verified:
   zero incoming references in the reverse import graph) — Part 3 was
   right about those two.
2. **A test outside `tests/gui` depends on `app/gui`.**
   `tests/test_threat_intel_state.py::TestGuiCompatibilityReExport`
   (part of the 780-test backend/non-GUI suite, not `tests/gui`) imports
   `app.gui.services.ioc_detail_context` directly to assert the
   compatibility shim re-exports the same objects as the canonical
   `app.services.ioc_detail_context`. Part 3's own dependency table (§3)
   had already found this reference, but this part's first deletion pass
   removed the shim anyway on the reasoning that nothing *inside*
   `app/gui`/`tests/gui` needed it — which broke that backend test. It
   was restored unchanged before the checkpoint was finalized. Lesson
   applied: "internal dependency graph" per the master instructions'
   Part 1 scope (`app/gui/**` and `tests/gui/**`) is necessary but not
   sufficient — a full-project residue search (Part 8, below) is what
   actually catches this class of miss, and should be run *before*
   deleting, not only after.
3. **A retained file (`app/gui/pages/component_showcase_page.py`, at
   the time still undecided) imports four components this part had
   already deleted** (`icon_button.py`, `loading_skeleton.py`,
   `toast_notification.py`, `timeline/timeline_widget.py`), and the
   package `__init__.py` re-export chains
   (`components/__init__.py` → `components/buttons/__init__.py` /
   `components/feedback/__init__.py` / `components/layout/__init__.py`)
   unconditionally imported all of them, breaking every GUI test's
   collection (6 of 7 retained suites failed to import at all, since
   they all transitively import `app.gui.pages.*` → `app.gui.widgets`
   → `app.gui.components`). Resolved by (a) retiring
   `component_showcase_page.py` itself (see §F/§G — an internal
   dev-tooling page with zero other consumers anywhere in the project,
   one of Part 3 §9's two explicit "needs a decision" items, resolved
   here as retire) and (b) trimming the now-dead re-exports out of the
   four `__init__.py` files rather than un-deleting the components.

For every file initially proposed for deletion, this part additionally
re-ran a full-project text search (not limited to `app/gui`) for its
dotted module path before the final checkpoint, per Recommended Next
Step 3 of the Part 3 audit. That search is reported in §I.

## C. Retirement Rules Applied

A production file was deleted only when **all** of the following held,
verified for that specific file (not inferred from its group):

- It has zero incoming references from any file in the "retained set"
  (see §D) — computed as the transitive closure, over the real AST
  import graph, of every `app/gui` module that a retained test
  (§E) or a retained-but-untested real-behavior file (`csv_exporter.py`
  / `history_page.py`, see §E) actually imports.
- It has zero references anywhere else in the project outside a
  docstring/comment (verified in §I).
- Its corresponding test coverage, if any, is also being retired for a
  documented reason (§E), not silently dropped.
- Deleting it does not empty a package directory that still has to
  serve retained siblings — package `__init__.py` files were only
  deleted when the whole directory emptied (`components/navigation/`,
  `components/timeline/`, `components/charts/`, `design/animations/`,
  `design/effects/`, `widgets/dashboard/`, `workers/`, `styles/`);
  otherwise the `__init__.py` was kept and, where it re-exported a
  deleted sibling, edited to drop just that export (§B item 3).

## D. Retained Closure (why the bulk of `app/gui` survives)

The retained closure was computed by taking every `app.gui` import
actually made by the 7 GUI test suites this part keeps (§E) — not by
guessing which files "look important" — and following the real forward
import graph outward. Two consequences fall directly out of this, and
they explain most of what did **not** get deleted:

- **`pages/investigation_workspace.py` is a single, large composition
  root.** It is imported by 5 of the 7 retained test suites
  (`test_investigation_workspace_risk_explanation.py`,
  `test_investigation_workspace_threat_intel.py`,
  `test_ioc_detail_experience.py`,
  `test_ioc_summary_risk_relevance.py`, `test_phase3e_acceptance.py`),
  and it directly imports 13 other `app/gui` modules
  (`correlation_widget.py`, `detail_section.py`,
  `investigation_header_card.py`, `investigation_metrics_widget.py`,
  `investigation_timeline_widget.py`, `ioc_detail_dialog.py`,
  `ioc_details_widget.py`, `ioc_summary_widget.py`, `page_container.py`,
  `risk_explanation_widget.py`, `risk_summary_widget.py`,
  `threat_intelligence_widget.py`, plus `application_state.py` and
  `event_bus.py`). Every one of those 13 is therefore retained too,
  regardless of whether Part 3's per-file table called it a "safe
  candidate" in isolation — in the real graph, they are not isolated.
- **The `design/tokens/*` and `design/theme/{palette,font_factory,theme_manager}.py`
  token system is retained wholesale**, because every retained widget
  (`ioc_summary_widget.py`, `risk_explanation_widget.py`, etc.) imports
  `design/tokens/__init__.py`, which re-exports every individual token
  module. Only the *unused* half of `design/theme/` —
  `stylesheet.py` and `stylesheet_builder.py`, which fed the dead
  `MainWindow`/`ApplicationShell` chain, not the retained widgets —
  was safe to remove. This directly answers Part 3 §9's open question
  ("which stylesheet system does the runtime actually use") — the
  retained widgets use `theme_manager.py`/`palette.py`/`font_factory.py`
  directly; `stylesheet_builder.py` was only ever reached through
  `styles/theme.py` → `main_window.py`/`application_shell.py`, all
  three of which are now gone together.

## E. Test-Suite Disposition (all 12 original files)

| Test | Disposition | Reason |
|---|---|---|
| `test_export_continuity.py` | **RETIRED** | Part 3: YES. Sole subject `app/gui/main_window.py` confirmed dead entrypoint (§F). |
| `test_investigation_analyst_context.py` | **RETIRED** | Part 3: YES. Every module it imports (`application_state`, `investigation_workspace`, `investigation_header_card`, `ioc_summary_widget`, `threat_intelligence_widget`) is independently retained via other tests (§D), so retiring this test file loses no production-file coverage — those modules keep their other test coverage. |
| `test_investigation_workspace_url.py` | **RETIRED** | Part 3: YES. Same reasoning — `investigation_workspace.py`/`ioc_details_widget.py` remain covered by other retained suites. |
| `test_ioc_summary_url.py` | **RETIRED** | Part 3: YES. `ioc_summary_widget.py` remains covered by `test_ioc_summary_risk_relevance.py`. |
| `test_ioc_viewer_page_defect_fix.py` | **RETIRED** | Part 3: YES, with documented rationale difference — this pins a historical Qt attribute-name typo (`investigation.id` vs `investigation_id`) that cannot recur in the modern TypeScript stack (typed field, not a Python attribute lookup). `ioc_viewer_page.py` itself remains, covered by `test_ioc_summary_risk_relevance.py`; only this defect-class regression test is retired. |
| `test_application_state_selected_ioc.py` | **RETAINED** | Part 3: UNCERTAIN — the outcome (selecting an IOC shows detail; switching investigation clears it) has a React equivalent, but the specific invariant this suite pins is `ApplicationState`-singleton semantics with no 1:1 React analog to verify against. Not re-resolved in this part; carried forward. |
| `test_investigation_workspace_risk_explanation.py` | **RETAINED** | Part 3: NOT SAFE. Confirmed still true — `InvestigationOverviewRisk.tsx` (checked again this part) renders score/severity/confidence only; no component reads `RiskExplanationService` output. |
| `test_investigation_workspace_threat_intel.py` | **RETAINED** | Part 3: UNCERTAIN. This part specifically re-checked the named gap (does the modern tab model support click-to-navigate from an enriched TI cell) by searching `InvestigationIocWorkspace.tsx` and `InvestigationThreatIntel.tsx` for any double-click/navigate handler — found none. The gap is confirmed real, not just unconfirmed; retained. |
| `test_ioc_detail_experience.py` | **RETAINED** | Part 3: UNCERTAIN. This part re-checked the named gap (dialog-specific "only offer view-full-record when enriched" conditional) against `InvestigationIocWorkspace.tsx`'s `IocDetail` panel — found `enriched`/`not_enriched` state labels but no confirmed 1:1 conditional-action match. Not resolved; retained pending a closer look in a future part. |
| `test_ioc_summary_risk_relevance.py` | **RETAINED** | Part 3: NOT SAFE (mixed suite) — TI-coverage-label assertions are redundant with modern tests, but the per-category Risk Significance badge assertions protect behavior with zero frontend equivalent (`grep -i significance frontend/src` → zero non-test hits, re-confirmed this part). |
| `test_phase3e_acceptance.py` | **RETAINED** | Part 3: PARTIAL/UNCERTAIN for the GUI-specific assertion (`test_d_gui_workspace_ti_section_displays_non_hash_records`), which has no frontend counterpart. The backend 3/4 of this suite is redundant with existing backend tests but the file was not split apart in this part — that would be its own retirement decision, deferred. |
| `test_threat_intel_page_url.py` | **RETAINED** | Part 3: UNCERTAIN for the Qt-threading-specific worker-construction/callback assertions (no 1:1 frontend test, though rendered outcomes are covered); YES only for the already-ported detection-logic assertions. Since the file mixes both, the whole file is retained. |

**Result: 5 of 12 suites retired, matching Part 3's own "4 clean YES + 1
YES-with-rationale" count exactly. All 7 retained suites collect and
pass cleanly (104/104) after the fixes in §B item 3.**

## F. Exact Deletion List (42 files)

Production files:

```
app/gui/app.py
app/gui/main_window.py
app/gui/styles/theme.py
app/gui/widgets/application_shell.py
app/gui/design/theme/stylesheet.py
app/gui/design/theme/stylesheet_builder.py
app/gui/pages/analyze_page.py
app/gui/pages/dashboard_page.py
app/gui/pages/risk_dashboard_page.py
app/gui/pages/component_showcase_page.py
app/gui/controllers/analyze_controller.py
app/gui/controllers/dashboard_controller.py
app/gui/services/analysis_service.py
app/gui/workers/analysis_worker.py
app/gui/workers/__init__.py
app/gui/models/investigation_proxy_model.py
app/gui/widgets/sidebar.py
app/gui/widgets/progress_dialog.py
app/gui/widgets/dashboard/__init__.py
app/gui/widgets/dashboard/cyber_status_pulse.py
app/gui/widgets/dashboard/dashboard_hero_widget.py
app/gui/widgets/dashboard/featured_investigation_card.py
app/gui/widgets/dashboard/investigation_queue_widget.py
app/gui/widgets/dashboard/ioc_distribution_widget.py
app/gui/widgets/dashboard/kpi_section.py
app/gui/widgets/dashboard/live_security_events_widget.py
app/gui/widgets/dashboard/quick_access_widget.py
app/gui/widgets/dashboard/system_status_section.py
app/gui/components/buttons/icon_button.py
app/gui/components/feedback/file_dropzone.py
app/gui/components/feedback/loading_skeleton.py
app/gui/components/feedback/toast_notification.py
app/gui/components/layout/page_header.py
app/gui/components/layout/panel.py
app/gui/components/navigation/__init__.py
app/gui/components/navigation/search_bar.py
app/gui/components/navigation/sidebar_item.py
app/gui/components/timeline/__init__.py
app/gui/components/timeline/timeline_widget.py
app/gui/components/charts/__init__.py
app/gui/design/animations/__init__.py
app/gui/design/effects/__init__.py
```

(41 files + the now-empty `app/gui/styles/` directory removed as a
whole = matches the 42-file/directory count tracked during this part.)

Test files:

```
tests/gui/test_export_continuity.py
tests/gui/test_investigation_analyst_context.py
tests/gui/test_investigation_workspace_url.py
tests/gui/test_ioc_summary_url.py
tests/gui/test_ioc_viewer_page_defect_fix.py
```

Directories removed once genuinely empty:
`app/gui/components/charts/`, `app/gui/components/navigation/`,
`app/gui/components/timeline/`, `app/gui/design/animations/`,
`app/gui/design/effects/`, `app/gui/styles/`, `app/gui/widgets/dashboard/`,
`app/gui/workers/`.

Files edited (not deleted) to remove now-dangling re-exports of deleted
siblings:

```
app/gui/components/__init__.py       (dropped IconButton, LoadingSkeleton,
                                       ToastNotification, ToastType,
                                       FileDropzoneWidget, Panel,
                                       SearchBar, TimelineWidget,
                                       TimelineEvent re-exports)
app/gui/components/buttons/__init__.py   (dropped IconButton)
app/gui/components/feedback/__init__.py  (dropped FileDropzoneWidget,
                                           LoadingSkeleton,
                                           ToastNotification, ToastType)
app/gui/components/layout/__init__.py    (dropped Panel)
```

No other files were modified. `app/gui/services/ioc_detail_context.py`
was deleted and then restored unchanged within this same part (see §B
item 2) — net effect on that file is zero change from baseline.

## G. Exact Retained List (66 production files, 7 test files)

Retained in full, unmodified: everything not listed in §F. This
includes, notably:

- All of `design/tokens/*` (8 files) and
  `design/theme/{__init__,palette,font_factory,theme_manager}.py`.
- All of `design/icons/__init__.py` (corrected classification, §B item 1).
- `pages/investigation_workspace.py`, `pages/ioc_viewer_page.py`,
  `pages/threat_intel_page.py`, `pages/history_page.py`,
  `pages/settings_page.py`.
- `services/investigation_correlation_context.py`,
  `services/ioc_detail_context.py` (the compatibility shim).
- `utils/csv_exporter.py`, `utils/badge_mapping.py`.
- `controllers/history_controller.py`.
- `models/investigation_table_model.py`.
- `events/*` (all 3 files).
- `widgets/*` except the 4 explicitly deleted above (~22 files:
  `correlation_widget.py`, `detail_section.py`,
  `investigation_header_card.py`, `investigation_metrics_widget.py`,
  `investigation_statistics_widget.py`, `investigation_timeline_widget.py`,
  `ioc_detail_dialog.py`, `ioc_details_widget.py`, `ioc_summary_widget.py`,
  `key_value_row.py`, `page_container.py`, `panel.py`,
  `risk_explanation_widget.py`, `risk_gauge_widget.py`,
  `risk_summary_widget.py`, `section_header.py`,
  `threat_intelligence_details_dialog.py`, `threat_intelligence_widget.py`).
- `components/base_widget.py`, `components/buttons/animated_button.py`,
  `components/cards/{glass_card,metric_card,modern_card}.py`,
  `components/feedback/{empty_state,status_badge}.py`,
  `components/layout/{component_section,section_header}.py`.

## H. Behavioral Preservation

- Every deleted production module either (a) had zero incoming
  references anywhere in the project once its sole test dependency was
  also retired (verified in §I), or (b) was a dead entrypoint
  (`app.py`/`main_window.py`/`application_shell.py`) already confirmed
  unreachable from any launcher in Part 3 §3, whose one piece of real
  logic (`MainWindow._export_report`'s format dispatch) is independently
  documented in `app/application/dto.py` as already ported to the
  `export_report` command.
- No module implementing one of Part 3's three named behavioral gaps
  ("Why this risk?" narrative, per-category Risk Significance badge,
  bulk CSV export) was deleted. `risk_explanation_widget.py`,
  `ioc_summary_widget.py`, `csv_exporter.py`, and `history_page.py` are
  all retained, along with their test coverage where it exists.
- `component_showcase_page.py` (an internal dev/QA tool for browsing
  the Qt design system, per Part 3 §9) is the one file this part
  resolved past "needs a decision": it has zero references anywhere
  else in the project (re-verified after every other deletion, §I),
  carries no test, and is not end-user-facing functionality — it was
  retired along with the four Qt-primitive components (`icon_button.py`,
  `loading_skeleton.py`, `toast_notification.py`, `timeline_widget.py`)
  that existed solely to be shown off on that page.
  `settings_page.py`, Part 3 §9's other "needs a decision" item, was
  **not** resolved the same way — it is a real end-user settings
  surface with no located frontend equivalent, which is a product
  question this part is not positioned to answer; it remains retained
  and open.

## I. Regression Results (this session, fresh)

```
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/gui -q
  Before: 142 passed   (re-verified fresh at the start of this part,
                        matching Part 3's own fresh count — not the
                        stale 154 in docs/architecture/IMPLEMENTATION_STATUS.md)
  After:  104 passed, 0 errors, 0 failures

python3 -m pytest tests/ --ignore=tests/gui -q
  Before: 780 passed
  After:  780 passed   (unchanged — confirms the ioc_detail_context.py
                        shim restoration in §B item 2 fully resolved the
                        one regression this part caused)

cd frontend && npx vitest run
  Before: 965 passed (70 files)
  After:  965 passed (70 files)   (unchanged)

cd frontend && npx tsc --noEmit
  0 errors (unchanged)

cd frontend && npm run build
  193 modules, succeeds (unchanged)

cargo check / cargo test (sidecar-core, src-tauri)
  ENVIRONMENT-BLOCKED — no cargo/rustc in this container, consistent
  with every prior Phase 4 session for this project. Not run.
```

Test-count math: 142 − 104 = 38 individual test cases lost with the 5
retired suites, all of them cases whose production module(s) retain
coverage elsewhere per §E — no coverage of currently-supported behavior
was silently dropped.

## J. Frozen-Area Verification

A full recursive diff was run between this checkpoint and the untouched
Part 3 baseline archive (excluding generated artifacts —
`__pycache__`, `node_modules`, `dist`, `.pytest_cache`, and a
`database/soc_iq.db` file created incidentally by running the backend
test suite locally, removed before packaging). The diff contains
**only**:

- The 42 deletions and 5 test-file deletions listed in §F.
- The 4 edited `__init__.py` files listed in §F.
- One new file: this document.

Nothing else changed. In particular, confirmed byte-identical /
untouched:

- Dashboard (Phase 4H): unchanged.
- Reporting (Phase 4L): unchanged.
- Threat Intel architecture: unchanged.
- Integration (Phase 4N): unchanged.
- Investigation Workspace (React): unchanged.
- Analysis workflow (React): unchanged.
- Tauri command/event architecture, `src-tauri/`, `sidecar-core/`: unchanged.
- Database schema (`database/`, excluding the incidental `.db` file): unchanged.
- Frontend design system / React app shell: unchanged.
- API contracts / command handlers: unchanged.
- `requirements.txt`: unchanged — `PySide6>=6.11.2` deliberately left
  in place, since `app/gui` and `tests/gui` still import it directly and
  will continue to for as long as any legacy GUI code remains (see §K).

A final project-wide text search for every deleted module's dotted
path (`app.gui.<name>`) found only historical docstring/comment
references in already-frozen production files
(`app/application/dto.py`, `app/application/handlers.py`,
`app/application/errors.py`, `app/services/dashboard_aggregation.py`)
and in pre-existing architecture/migration documents under `docs/`
— all pre-dating this part, all describing provenance ("this DTO's
behavior was ported from `app/gui/main_window.py`"), none of them a
live import. None were edited, consistent with the narrow-diff
requirement.

## K. Next Phase

Phase 4O is **not** ready to proceed to a final audit. Concrete
remaining work, in priority order:

1. **Three product decisions are still open**, unchanged from Part 3:
   is the "Why this risk?" narrative required in the modern app; is the
   per-category Risk Significance badge required; is bulk CSV export of
   investigation history still a required feature. Until at least one
   of these gets a "no, drop it" answer, `risk_explanation_widget.py`,
   the significance half of `ioc_summary_widget.py`, and
   `csv_exporter.py`/`history_page.py` all stay, along with everything
   `investigation_workspace.py` pulls in transitively (§D) — which is
   most of the remaining `app/gui` file count.
2. **`settings_page.py`** still has no located frontend equivalent and
   needs a direct answer (in scope / deferred / genuinely missing),
   same as Part 3 §9 left it.
3. Three of the five originally-UNCERTAIN test suites still have
   unresolved, specifically-named gaps after this part's targeted
   checks (double-click TI-cell navigation, dialog-conditional parity,
   `ApplicationState`-singleton semantics) — each would need either a
   small frontend implementation task or an explicit "won't implement"
   product call before its legacy test/widget pair could retire.
4. `test_phase3e_acceptance.py` and `test_threat_intel_page_url.py` are
   each internally mixed (part provably redundant with backend/DTO-layer
   tests, part not) — a future part could split them rather than
   keeping the whole file for the sake of one still-real assertion.
5. Only once (1)–(4) are resolved does `PySide6` become removable from
   `requirements.txt`, and only then does a further pass to retire the
   remaining ~66 `app/gui` files and 7 `tests/gui` suites become
   possible.

**Given the above, `app/gui` is not fully retired and this document
does not claim it is.** 66 of the original 108 production files and 7
of the original 12 test suites remain, for the specific, evidenced
reasons in §D–§E, not because this part ran out of time to check them.
