# Phase 2 Part 2A — IOC Investigation & Threat Intelligence Experience

Baseline: `SOC-IQ-Phase2-Part1-COMPLETED.zip` (commit `0747c92`).
This document covers only what changed in Part 2A. Phase 0, Phase
1, and Phase 2 Part 1 remain frozen and were not reopened.

## What Part 2A found

Part 1 built category-level IOC browsing ("Extracted IOCs" table
per type) plus a one-way drill-down from an enriched SHA256 hash to
its Threat Intelligence record. What was still missing for the
"I found this IOC -- what does it mean?" workflow:

- No way to select a *single* IOC value and see everything known
  about it (value, type, which investigation it came from, its
  threat-intelligence status, its risk significance) in one place.
- No visibility into *why* an indicator shows "Not Enriched" --
  the codebase already distinguishes several real reasons (no API
  key, provider rejected the key, rate limited, check incomplete,
  genuinely never enriched) but none of it reached the GUI.
- `ThreatIntelPage` and `VirusTotalClient` already document, in
  their own code, that only SHA256 hashes are enriched -- IP,
  domain, and URL reputation lookups are not implemented against
  any real provider. Nothing communicated that at the IOC level.

## What was implemented

**Select an IOC -> IOC Details -> Threat Intelligence -> Risk
Significance -> back to the investigation**, entirely within the
existing Investigation Workspace and existing architecture:

- `ApplicationState` gained `SelectedIOC` tracking
  (`set_selected_ioc()` / `get_selected_ioc()` /
  `clear_selected_ioc()`), reusing the same lock-guarded,
  event-bus-integrated pattern as the existing current-investigation
  state rather than a second global state mechanism. Selecting a new
  investigation, or clearing the current one, clears the selected
  IOC automatically -- it can't outlive the investigation it belongs
  to.
- `IOCDetailsWidget` gained a "View Details" button (enabled
  whenever a row is selected -- including the row `_populate_table`
  already auto-selects) and a matching context-menu action, emitting
  a new `ioc_detail_requested(ioc_type, value)` signal. The
  pre-existing double-click-to-copy and Threat-Intel-cell-drilldown
  behavior from Part 1 is untouched.
- `app/services/ioc_detail_context.py` (new, plain Python, no
  Qt) assembles the full context for a single IOC: investigation
  identity, a risk-significance label, and an honest
  threat-intelligence state -- `enriched`, `not_enriched`,
  `no_api_key`, `provider_error`, `incomplete_check`, or
  `unsupported_type`. It reuses `ThreatIntelService`'s existing
  enrichment/coverage output and never fabricates a result.
- `app/services/ioc_significance.py` (new) derives a
  Low/Medium/High/Informational significance label purely by
  reading `RiskScoringEngine.IOC_WEIGHTS` -- the scoring algorithm
  itself is untouched, this is presentation banding only.
- `IOCDetailDialog` (new) renders that context using the existing
  design-system widgets (`DetailSection`, `KeyValueRow`, `Badge`),
  matching the rest of the workspace's look. When the indicator is
  enriched, a "View Full Threat Intelligence Record" button reuses
  the exact Part 1 drill-down (switch to the Threat Intelligence
  tab, select the matching row) instead of opening a second view of
  the same data.
- `InvestigationWorkspacePage._on_ioc_detail_requested()` wires it
  together: records the selection on `ApplicationState`, reads
  whether a VirusTotal API key is configured (a local settings read,
  not a network call), builds the context, and opens the dialog. A
  stale signal arriving with no investigation loaded is reported via
  the existing `status_message` signal instead of raising.

Because the dialog is modal, closing it always returns the analyst
directly to the workspace with the investigation still on screen --
there is no dead-end navigation state to manage.

## What was deliberately NOT implemented

- No new VirusTotal endpoints for IP/domain/URL reputation.
  `VirusTotalClient` only exposes `lookup_sha256()`, and
  `ThreatIntelPage`'s existing code already documents that as
  intentional ("Live lookups currently support SHA256 file hashes
  only"). Adding new provider calls here would mean shipping
  untested network integration code with the associated risk of
  fabricated-looking results; instead, those categories honestly
  report `unsupported_type` in the IOC detail view.
- No change to `RiskScoringEngine` or the score calculation itself.
- No new event-bus signals -- `ApplicationState`'s existing
  lock/event-emit pattern was extended, not replaced.

## Testing

- Full pre-existing suite: 214/214 passing, unchanged.
- New: 32 tests across `tests/test_ioc_detail_context.py` (pure
  logic, no Qt -- significance banding and every threat-intelligence
  state), `tests/gui/test_application_state_selected_ioc.py`
  (selection lifecycle), and `tests/gui/test_ioc_detail_experience.py`
  (real Qt widgets under an offscreen `QApplication`: button
  enablement, signal wiring, dialog contents per state, and the
  workspace's missing-investigation guard).
- Total: 246/246 passing.
- `python -m compileall .`: clean.
- Manual smoke test: instantiated the real `MainWindow`, loaded an
  investigation into the workspace, selected a SHA256 category,
  confirmed "View Details" auto-enables, opened the detail dialog
  for an enriched hash (correct verdict/detection ratio shown),
  confirmed `ApplicationState.get_selected_ioc()` reflects the
  selection, opened the detail dialog for a domain (correctly
  reports threat intelligence as not supported for that type), and
  for a hash with no VirusTotal API key configured (correctly
  reports API key not configured) -- none of these raised.

PySide6 and pytest were both installable in this environment, so
this was real execution, not a static read of the code.

## Left for Part 2B

- Real threat-intelligence coverage for IOC types beyond SHA256, if
  a provider integration for IP/domain/URL is ever added.
- Any deeper cross-page navigation that surfaces
  `ApplicationState.get_selected_ioc()` outside the Investigation
  Workspace (e.g. a dashboard widget for "your last-viewed
  indicator").
- Frotexa integration boundary work (explicitly out of scope here).
