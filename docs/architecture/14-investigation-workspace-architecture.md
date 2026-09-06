# Investigation Workspace Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §13, `07-state-architecture.md` (selected-IOC persistence).

## CURRENT STATE

`app/gui/pages/investigation_workspace.py` exists (CONFIRMED, file present) alongside a
cluster of supporting widgets (`investigation_header_card.py`,
`investigation_metrics_widget.py`, `investigation_statistics_widget.py`,
`investigation_timeline_widget.py`, `correlation_widget.py`). The exact current tab/section
structure inside this page was not independently re-verified in full during this pass —
treated as **UNKNOWN — VERIFY IN PHASE 4B**.

## TARGET STATE (PROPOSED)

```
Investigation
├── Overview        summary, key metrics, quick actions
├── IOCs             extracted indicators, filterable by type/verdict
├── Threat Intel      per-IOC, per-provider results (NOT_FOUND shown distinctly from CLEAN)
├── Risk               explainable score breakdown (weights visible, not a black-box number)
├── Timeline            chronological event/analysis history for this investigation
├── Correlation          links to related investigations sharing IOCs
├── Evidence              source report(s), extracted artifacts
└── Reports                export history + regenerate
```

A persistent left rail within the workspace (not top tabs that reset scroll position) lets an
analyst move Overview → IOCs → Threat Intel without losing the selected IOC — the
selected-IOC id lives in the frontend state store (`07-state-architecture.md`) and survives
tab switches within a session.

This tab set is treated as the *core SOC experience* by the Master Plan (§13) — it is the
single screen where the value of the multi-provider TI abstraction
(`08-threat-intelligence-architecture.md`) and the explainable risk score
(existing `app/scoring/`, preserved unchanged) are both visible together.

## MIGRATION NOTES

The Overview/IOCs/Evidence tabs ship first (Phase 4J, Master Plan §26); the remaining tabs
(TI/Risk views) follow in Phase 4K once the multi-provider TI display is ready.

## UNKNOWN / REQUIRES VERIFICATION

Current `investigation_workspace.py` section structure and its relationship to
`correlation_widget.py`: **UNKNOWN — VERIFY IN PHASE 4B.**
