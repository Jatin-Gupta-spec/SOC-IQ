# SOC-IQ — PD-06: Retire Standalone Risk Page

## Entry checkpoint

`SOC-IQ-PD05-IOC-TI-TOPLEVEL-RETIREMENT-FINAL.zip`

## Decision

**PD-06 — Standalone Risk page: RETIRE.**

This document originally recorded a decision only, with implementation
deferred. As of a later implementation part, the retirement described
below has been carried out in source — see "Status" below.

## Rationale

- The standalone Risk page (`frontend/src/pages/RiskPage.tsx`) renders
  exclusively from `mock/risk.ts` (`mockOverallRiskScore`,
  `mockRiskSeverityDistribution`, `mockRiskCategories`,
  `mockHighRiskFindings`) — it has no `investigation_id` and no
  backend call of any kind.
- Real risk functionality already exists, backend-integrated, inside
  the Investigation Workspace:

  ```
  Investigations
      ↓
  Investigation Workspace
      ↓
  Overview
      ↓
  Risk  (InvestigationOverviewRisk.tsx — real score, severity,
          confidence, sourced from InvestigationWorkspaceData)
  ```

- The standalone page therefore duplicates a capability the product
  already has, in investigation-scoped, real form, without adding any
  analyst capability the workspace view lacks. Retaining a top-level
  mock "Risk" destination alongside a real, investigation-scoped one
  risks the same misleading-permanent-placeholder problem PD-05
  addressed for IOC Explorer / Threat Intel.
- This mirrors PD-05's own reasoning: a top-level page backed only by
  mock data, with a real equivalent already living inside the
  Investigation Workspace, is a retirement candidate rather than a
  page to keep wiring up in place.

## Current state (reconciled — see docs/phase4/PD12 documentation
## reconciliation pass)

Retained, real risk functionality:

```
app/scoring/**                        RETAINED — real risk engine
app/services/risk_explanation_service.py RETAINED — RiskExplanationService
app/services/risk_explanation_models.py  RETAINED
frontend/src/pages/investigation/InvestigationOverviewRisk.tsx RETAINED
frontend/src/pages/investigation/InvestigationOverviewRisk.css RETAINED
```

Retired standalone destination:

```
frontend/src/pages/RiskPage.tsx        RETIRED — no longer present in source
frontend/src/mock/risk.ts              RETIRED — no longer present in source
Route / NAVIGATION_ITEMS entry         RETIRED — no standalone /risk route
Command-palette entry                  RETIRED — no standalone Risk entry
```

`RiskExplanationService` and its models remain backend-only services,
also consumed by the legacy GUI
(`app/gui/widgets/risk_explanation_widget.py`,
`app/gui/pages/investigation_workspace.py`) and exercised by
`tests/test_risk_explanation_service.py`; the standalone-page retirement
did not touch them.

## Status

**DECISION RECORDED — IMPLEMENTED.**

`RiskPage.tsx` and `mock/risk.ts` have been removed from source, along
with their route and navigation/command-palette entries, in a later
implementation part than the one that produced this decision record.
Standalone Risk destination: **RETIRED**. Real risk scoring/explanation
(`app/scoring/**`, `RiskExplanationService`): **RETAINED**.
Investigation Workspace risk (`InvestigationOverviewRisk.tsx`):
**RETAINED**. Dashboard risk: **RETAINED**.

## Next Action

None outstanding for this decision — the retirement described above is
complete. Any further Risk-related work is a new product decision, not
a continuation of PD-06.
