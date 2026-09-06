# Phase 3 — Part 3A Record

## Investigation Intelligence Experience

```
Phase 3A
Status: COMPLETED
```

## Baseline

Started from `SOC-IQ-Phase2-FINAL-FROZEN.zip`. Phase 0, Phase 1, and
Phase 2 remain unmodified and frozen.

## Inspection findings

Before making any change, the areas listed in the Phase 3A brief
(Investigation model/service, `ApplicationState`, Investigation
Workspace, IOC models/extraction/widgets, Threat Intelligence
models/widgets, risk/severity display, existing tests, existing
design tokens/components) were read in full.

The finding: Phase 2 Part 2A and Part 2B-1 already implemented the
great majority of what Phase 3A describes.

  * `ApplicationState` already holds one authoritative selected
    investigation *and* a selected IOC (`SelectedIOC`), both
    thread-safe, both notified via the existing `event_bus` -- no
    second state manager needed.
  * `InvestigationWorkspacePage` already is the central analyst
    workbench: a persistent header (identity + risk/severity +
    threat-intel overview) plus three tabs (Overview & Metrics,
    Extracted IOCs, Threat Intelligence), already wired
    Investigation -> IOC -> Threat Intelligence -> Risk.
  * `app/services/ioc_detail_context.py` already builds a
    single-IOC investigation/threat-intel context with an honest,
    non-fabricating state vocabulary (`TI_STATE_ENRICHED`,
    `TI_STATE_NOT_ENRICHED`, `TI_STATE_NO_API_KEY`,
    `TI_STATE_PROVIDER_ERROR`, `TI_STATE_INCOMPLETE_CHECK`,
    `TI_STATE_UNSUPPORTED_TYPE`) and an investigation-level
    equivalent (`build_investigation_threat_intel_overview()`).
  * `IOCDetailDialog` already shows risk significance
    (`ioc_type_significance()`, reusing
    `RiskScoringEngine.IOC_WEIGHTS` as the sole source of truth) and
    a "jump to Threat Intelligence" drill-down for enriched hashes.
  * Empty/invalid states (no investigation, no IOCs, no threat-intel
    records, unsupported IOC type, no API key, provider error) were
    already handled cleanly, with no raw tracebacks reaching the UI.

Given this, Part 3A avoided an unnecessary rewrite and instead
closed the one genuine gap found during inspection.

## The gap

The **IOC Summary table** -- the first, category-level view of an
investigation's evidence (`IOC Type` / `Count`) -- showed neither
risk relevance nor threat-intelligence coverage. Both already
existed one click away, in `IOCDetailDialog`, but only for a single
selected value. An analyst scanning the summary table had to open
every category, then every IOC, to learn which categories actually
mattered -- the opposite of "make existing intelligence
understandable... without unnecessary scrolling" (or clicking).

## Implemented (Part 3A-2 / Part 3A-3)

**`app/gui/widgets/ioc_summary_widget.py`**

  * Added a **Risk Significance** column: one `Badge` per IOC
    category, driven entirely by the existing
    `ioc_type_significance()` helper (`app/gui/utils/
    ioc_significance.py`), which in turn reads
    `RiskScoringEngine.IOC_WEIGHTS`. No new scoring, no new
    thresholds, no engine change -- purely surfacing a value that
    already existed and was already shown one click deeper.
  * Added a **Threat Intelligence** column:
      - the SHA256 row shows the real
        `build_investigation_threat_intel_overview()` result
        (`short_label`, e.g. `"Partial (1/2)"`,
        `"No API Key Configured"`) when the caller supplies one;
      - every other category always shows `"Not Supported"` --
        the exact vocabulary `IOCDetailDialog` already uses for the
        same state, since only SHA256 hashes are enriched by the
        current provider integration;
      - if no overview was supplied at all, the SHA256 row shows an
        explicit `"\u2014"` placeholder rather than a fabricated
        figure.
  * `load_investigation()` gained one new, optional,
    backward-compatible parameter (`threat_intel_overview: dict |
    None = None`); every existing call site with one argument
    continues to work unchanged.
  * `reset()` now also clears the stored overview.

**`app/gui/pages/investigation_workspace.py`**

  * The already-computed `threat_intel_overview` (used for the
    header card and the Threat Intelligence tab) is now also passed
    to `_ioc_summary_widget.load_investigation()` -- one extra
    argument, no new computation, no duplicate logic.

**`app/gui/pages/ioc_viewer_page.py`**

  * This page previously called `IOCSummaryWidget.load_investigation
    (investigation)` with no threat-intel context at all. It now
    builds the same overview the workspace does (`SettingsService`
    + `build_investigation_threat_intel_overview()`, both already
    existing, read-only, no new provider calls) so the cross-
    investigation IOC Explorer gets the same honest coverage
    information, for consistency across every IOC-related page in
    scope.

No IOC extraction code, no regex, no scoring formula, no
threat-intelligence provider code, and no database code were
touched. `ApplicationState` was not touched; no new state manager,
singleton, or widget-to-widget state was introduced.

## Tests

Added `tests/gui/test_ioc_summary_risk_relevance.py` (10 new tests):

  * Risk Significance column matches `ioc_type_significance()` for
    every category, including that SHA256 (weight-driven "High")
    differs from a lower-weight category like IPv4.
  * Threat Intelligence column shows the real overview label for
    SHA256 when one is supplied, an explicit unknown placeholder
    when it isn't, and `"Not Supported"` for every other category
    even when an overview *is* supplied.
  * `reset()` clears the stored overview.
  * Both real call sites (`InvestigationWorkspacePage`,
    `IOCViewerPage`) are exercised end-to-end and asserted to pass a
    genuine (non-placeholder) overview through.

No existing test was modified, weakened, or deleted.

## Validation

```
pytest (non-GUI, 11 files, 229 tests): 229 passed, 0 failed, 0 errors
  — real pytest/PySide6 remain uninstallable in this sandbox (no
    network access, confirmed again this session: `pip install
    pytest` and a direct HTTPS request to pypi.org both fail).
    Re-verified and repaired the Phase 2 freeze's pytest-compatible
    shim (fixtures, tmp_path, monkeypatch two- and three-argument
    forms, capsys, parametrize, skipif, raises) before use this
    session: the shim initially mis-handled pytest's two-argument
    `monkeypatch.setattr("module.path.attr", value)` form (treating
    the replacement value as an attribute name) and did not call
    monkeypatch.undo() on a failing test, which together produced
    16 spurious failures/errors in tests/test_virustotal.py and
    tests/test_reporting.py on the first run. Both were shim bugs,
    fixed, and the full non-GUI suite now passes cleanly, including
    every test in the two affected files.
pytest (GUI, 7 files including the new
    test_ioc_summary_risk_relevance.py, ~73 tests): NOT RUN --
    PySide6 unavailable, no network access to install it. Verified
    instead by: (1) `python -m compileall` across the full
    repository -- zero syntax errors; (2) a full AST-level internal-
    import-graph walk of all 151 files under app/ -- zero
    unresolved `app.*` imports; (3) actually importing all 123 non-
    __init__ app submodules under system Python -- 50 import
    cleanly, 71 fail only on the expected missing PySide6, 2
    (app.main, app.display) fail only on the expected missing
    `rich`, 0 unexpected import failures; (4) manual review of every
    changed line in ioc_summary_widget.py, investigation_workspace.py,
    and ioc_viewer_page.py against the existing, already-tested pure-
    Python helpers (`ioc_type_significance()`,
    `build_investigation_threat_intel_overview()`) they call, both of
    which are already covered by the 229 passing non-GUI tests above.
compileall: PASS (zero syntax errors across the full repository,
    re-run after clearing all __pycache__ directories)
import integrity: as above -- 0 unexpected import failures
GUI smoke test: NOT PERFORMED. PySide6 is unavailable in this
    environment and there is no network access to install it. This
    is stated plainly rather than claimed.
```

## Regression check

The Phase 2 freeze's `pytest (non-GUI, 11 files, 229 tests)` figure
is reproduced exactly (229 passed, 0 failed) after this session's
changes, confirming no regression in Dashboard/History/Investigation/
IOC/Threat Intelligence/Risk/Reporting/Export/Database logic that has
non-GUI test coverage. `IOCSummaryWidget`'s two other existing GUI
call sites (`InvestigationWorkspacePage`, `IOCViewerPage`) were
grepped for every `.load_investigation(` call against it; both were
found and updated to the new optional-argument signature, and no
third caller exists.

## Known limitations

  * GUI test suite (`tests/gui/`, including the 10 new tests added
    this session) could not be executed in this environment; PySide6
    is unavailable with no network access to install it -- same
    limitation recorded at the Phase 2 freeze.
  * As at the Phase 2 freeze, the CLI's `rich`-based display layer
    (`app/display.py`) could not be exercised directly for the same
    reason.
  * This session's fixes to the pytest-compatible shim itself are,
    like the shim, sandbox tooling rather than part of the SOC-IQ
    product; they are recorded here for transparency but are not
    included in the "Implemented" section above and are not shipped
    as part of the SOC-IQ codebase.

## Not implemented (explicitly out of scope for Part 3A)

Per the Phase 3A brief: no Phase 3B correlation engine, no evidence
relationship graph, no autonomous SOC agent, no automated response,
no Frotexa integration, no new database architecture, no new threat-
intelligence provider architecture, no new risk engine, and no major
Dashboard redesign. None of these were started.

## Next Baseline

`SOC-IQ-Phase3-Part3A-COMPLETED.zip` is now the authoritative
baseline for **Phase 3B**.
