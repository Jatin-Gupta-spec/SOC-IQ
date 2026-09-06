# Phase 2 Part 1 — Investigation-Centric Workflow

Baseline: `SOC-IQ-Phase1-FINAL-FROZEN.zip` (commit `2f724d1`, frozen).
This document covers only what changed in Part 1. Phase 0 and
Phase 1 remain frozen and were not reopened.

## What Part 1 found

Inspection of the frozen baseline showed most of the Part 1
objective was already in place:

- Investigation identity/context (`InvestigationHeaderCard`), risk
  context (`RiskSummaryWidget`), and history/dashboard → workspace
  navigation (`ApplicationState` + `event_bus`) were already
  implemented cleanly and needed no changes.
- The one real gap: the Investigation Workspace showed IOCs and
  Threat Intelligence as two disconnected tables. An analyst
  looking at a SHA256 hash in "Extracted IOCs" had no way to tell
  whether it had been enriched, or to jump to that record.

## What was implemented

**Investigation → IOC → Threat Intelligence drill-down**, entirely
within the existing Investigation Workspace, reusing the existing
`ThreatIntelService` enrichment data already stored on
`Investigation.threat_intelligence` — no new service, no duplicated
enrichment logic, no schema change.

- `IOCDetailsWidget` gained an optional "Threat Intel" column,
  shown only for the `sha256` category, color-coded by verdict
  (Malicious / Suspicious / Clean / Not Enriched). Double-clicking
  an enriched cell requests navigation to that record; all other
  double-click behavior (copy) is unchanged.
- `ThreatIntelligenceWidget` gained `select_hash()` to focus a
  specific hash's row.
- `InvestigationWorkspacePage` builds a hash → enrichment lookup on
  `load_investigation()`, passes it to the IOC Details view only for
  the `sha256` category, and wires the drill-down request to switch
  to the Threat Intelligence tab and select the matching row. If the
  investigation was reloaded and the hash is no longer present, a
  status message says so instead of navigating to nothing.

## Defect fixed (found during validation, not part of the plan)

`IOCViewerPage.refresh()` compared `investigation.id`, which does
not exist on `Investigation` (the field is `investigation_id`).
This raised an `AttributeError` inside the
`event_bus.investigation_selected` slot on every investigation
selection — i.e. every time History, the Dashboard, or a completed
analysis opened the workspace, which is the exact path Part 1
strengthens. Fixed as a one-line attribute correction; a regression
test (`tests/gui/test_ioc_viewer_page_defect_fix.py`) pins it.

## Testing

- Full pre-existing suite: 199/199 passing, unchanged.
- New: `tests/gui/` (14 tests) — real PySide6 widgets under an
  offscreen `QApplication`, covering the drill-down wiring end to
  end and the `IOCViewerPage` regression.
- Total: 214/214 passing.
- `python -m compileall .`: clean.
- Manual smoke test: instantiated the real `MainWindow`, selected an
  investigation, confirmed the workspace opens, IOC selection shows
  the Threat Intel column, drill-down switches tabs and selects the
  right row, and re-selecting a different investigation still works
  cleanly.

PySide6 and pytest were both installable in this environment, so
this was real execution, not a static read of the code.

## Left for Part 2

- Threat-intelligence linkage for IOC types beyond SHA256, if/when
  enrichment is extended to them.
- Any deeper investigation-timeline or evidence-review work.
- Frotexa integration boundary work (explicitly out of scope here).
