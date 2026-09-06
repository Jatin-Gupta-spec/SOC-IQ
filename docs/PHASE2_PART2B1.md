# Phase 2 Part 2B-1 — Investigation-Level Analyst Context

Baseline: `SOC-IQ-Phase2-Part2A-COMPLETED.zip`.
This document covers only what changed in Part 2B-1. Phase 0,
Phase 1, Phase 2 Part 1, and Phase 2 Part 2A remain frozen and
were not reopened.

## What Part 2B-1 found

Part 2A built the "select an IOC -> see everything about it"
experience. Stepping back to the investigation as a whole, two
gaps stood out:

- The Investigation Summary already surfaced ID, report name,
  timestamp, status, severity, IOC count, risk score, and
  confidence -- but nothing about the investigation's overall
  threat-intelligence state. An analyst could see "12 IOCs" but
  not "were they even checked, and if not, why not" without
  opening the Threat Intelligence tab and interpreting a bare
  table (or its absence) themselves.
- Three widgets had no real empty state: `IOCSummaryWidget` showed
  every category at "0" instead of communicating "no evidence
  found"; `ThreatIntelligenceWidget` showed a bare 0-row table with
  no explanation of *why* (no hash indicators? no API key? a
  provider error?); and `InvestigationWorkspacePage` had no
  "no investigation selected" state at all -- `ApplicationState`
  already exposes `clear_current_investigation()` (used by
  `tests/gui/test_application_state_selected_ioc.py`), and the
  workspace already subscribes to the resulting
  `investigation_selected` signal via `refresh()`, but the reset
  path just blanked every field to "Waiting..." rather than
  telling the analyst anything was actually cleared.

## What was implemented

**Investigation Summary -> Evidence -> Threat Intelligence -> Risk
posture**, answerable at a glance, entirely within the existing
Investigation Workspace and existing architecture:

- `app/services/ioc_detail_context.py` gained
  `build_investigation_threat_intel_overview()`, the
  investigation-level counterpart to Part 2A's per-IOC
  `build_ioc_detail_context()`. It reads the same
  `ThreatIntelService` coverage output
  (`Investigation.threat_intelligence["coverage"]`/`["status"]`)
  and reuses the same `TI_STATE_*` vocabulary, so both views agree
  on what "enriched" / "no API key" / "provider error" /
  "incomplete check" mean. It performs no network calls and
  fabricates nothing -- an investigation with no coverage data at
  all is reported as "not enriched", not silently ignored.
- `InvestigationHeaderCard` gained a "Threat Intelligence" row
  (compact label, e.g. "Enriched (8/8)", "No API Key Configured",
  "Partial (3/5)", with the full sentence as a tooltip), completing
  the four analyst questions from the task brief -- identity,
  evidence, threat-intel state, and risk -- in one place.
  `load_investigation()` takes the overview as an optional second
  argument so existing/other callers are unaffected.
- `ThreatIntelligenceWidget` gained a summary line above the table
  when there is enrichment data, and an `EmptyState` (from the
  existing, previously-unused `app/gui/components/feedback` design
  system) in place of the table when there is none -- explaining
  *why* (no hash indicators extracted, no API key, provider
  rejected the key, rate limited) instead of leaving a bare 0-row
  table.
- `IOCSummaryWidget` gained the same `EmptyState` treatment for the
  genuinely-no-IOCs case, instead of a table of all-zero rows.
- `InvestigationWorkspacePage` gained a top-level `EmptyState`
  ("No Investigation Selected"), shown instead of the header card
  and tabs whenever `ApplicationState.get_current_investigation()`
  is `None` -- both before any investigation has ever been opened
  and if `clear_current_investigation()` is ever called while the
  workspace is on screen. `load_investigation()` now also reads
  whether a VirusTotal API key is configured (the same local
  settings read already used by `_on_ioc_detail_requested`) and
  builds the overview once per load, passing it to both the header
  card and the Threat Intelligence tab so they never disagree.

## What was deliberately NOT implemented

- No changes to `RiskScoringEngine`, IOC extraction, or
  `ThreatIntelService`/`VirusTotalClient` -- the overview function
  only reads their existing output.
- No new global/singleton state -- the workspace still reads
  `ApplicationState.get_current_investigation()` exactly as before;
  no second selected-investigation mechanism was added.
- No reporting/export changes (left for Part 2B-2), no dashboard
  redesign, no database changes, no Frotexa integration.
- The `IOCDetailDialog` / per-IOC threat-intelligence experience
  from Part 2A is untouched -- this part is about the investigation
  as a whole, not the single-IOC drill-down.

## Testing

- **New pure-logic tests**
  (`tests/test_investigation_threat_intel_overview.py`, 8 tests, no
  Qt dependency): every state
  `build_investigation_threat_intel_overview()` can return --
  enriched, no threat-intelligence data recorded at all, no hash
  indicators extracted, no API key configured (verified to take
  priority over the generic provider-error path even though the
  underlying coverage also carries `invalid_api_key=True`, since
  the client fails fast on the first lookup with no key), rejected
  API key with a key configured, rate limited, and partial/
  incomplete coverage -- plus a sweep asserting every state
  produces a non-empty `short_label` and `message`.
- **New GUI tests**
  (`tests/gui/test_investigation_analyst_context.py`, 13 tests,
  real Qt widgets under an offscreen `QApplication`, matching the
  existing Part 2A GUI test style): the workspace's empty state on
  startup, after loading an investigation, after
  `_reset_workspace()`, and after `ApplicationState
  .clear_current_investigation()` fires while the workspace is
  open; the header card's Threat Intelligence row and its tooltip,
  and that `reset()` clears it; the Threat Intelligence widget's
  table/empty-state toggle with a reason attached; and the IOC
  summary widget's table/empty-state toggle for the zero-IOC case.
- **Existing suite**: unchanged. `InvestigationHeaderCard
  .load_investigation()` and `ThreatIntelligenceWidget
  .load_investigation()` both take their new context argument as
  optional, so every pre-existing call site and test keeps working
  without modification.

### Environment limitation (disclosed per task instructions)

This sandbox has no network access, and neither PySide6 nor pytest
is pre-installed here, so **the real `pytest` suite and the real
GUI smoke test could not be executed in this environment** --
unlike Part 2A, which reported running both. What was actually
done instead:

- `python -m compileall .`: clean, no errors, across the whole
  project including every new/changed file.
- Every pure-Python (no-PySide6) test module -- the pre-existing
  suite and both new test files -- was imported and its test
  functions executed manually (a minimal in-process runner, since
  `pytest` itself isn't available to invoke). All tests that don't
  depend on pytest-specific fixtures (`monkeypatch`, `tmp_path`,
  `capsys`, `parametrize`) passed, including all 14 pre-existing
  `tests/test_ioc_detail_context.py` tests and all 8 new
  `tests/test_investigation_threat_intel_overview.py` tests. Tests
  requiring those fixtures could not be driven by the manual
  runner and were left unexecuted rather than misreported as
  passing; none of them touch the files changed in this part.
- The new Qt-based tests in `tests/gui/test_investigation_analyst_context.py`
  were written to match the existing GUI test suite's style and
  were traced by hand against the final widget code
  (attribute names, method signatures, visibility toggling) but
  were **not actually executed** -- PySide6 is not installed and
  cannot be installed without network access.
- No real `MainWindow` smoke test was performed for the same
  reason.

If PySide6 and pytest are available wherever this ZIP is next
opened, running `pytest` should be the first step of Part 2B-2 to
confirm all of the above before building on it.

## Left for Part 2B-2

- Reporting/export work (explicitly out of scope for 2B-1).
- Confirming the new GUI tests actually pass under a real PySide6
  + pytest environment (see limitation above).
- Any further cross-page surfacing of investigation-level context
  outside the workspace, if desired.
