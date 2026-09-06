# Phase 3 — Part 3C Freeze Record

## Analyst Risk Explanation

```
Phase 3C
Status: COMPLETE / FROZEN
```

## Baseline

Started from the Phase 3B evidence correlation baseline (`c2da08a`).
Phase 0, Phase 1, Phase 2, Phase 3A, and Phase 3B remain unmodified
and frozen.

## Sub-phases

Phase 3C consisted of two sub-phases:

**Phase 3C-1 — Risk explanation foundation**
`726b613 — feat: establish phase 3c risk explanation foundation`

Added `RiskExplanationService`
(`app/services/risk_explanation_service.py`) and its domain models
(`app/services/risk_explanation_models.py`), answering "why does this
investigation have this risk/severity" by reading an investigation's
already-persisted score, severity, confidence, ioc_score,
threat_intel_score, cve_score, IOCs, and threat intelligence — plus,
optionally, a Phase 3B `CorrelationReport` supplied by the caller.
The service never recalculates score/severity/confidence; every value
in its result is a direct passthrough. Per-IOC-category point
breakdowns reuse the existing `RiskScoringEngine.IOC_WEIGHTS` table
and are only shown numerically once verified to sum to the
investigation's persisted `ioc_score`, otherwise the narrative falls
back to qualitative, significance-only language. Threat-intelligence
context reuses `build_investigation_threat_intel_overview()` as-is.
The service is framework-independent (no PySide6 import), read-only,
and introduces no database changes.

**Phase 3C-2 — Analyst risk context integration**
`e7683dd — feat: integrate phase 3c analyst risk context`

Integrates the Phase 3C-1 `RiskExplanationService` into the
Investigation Workspace as a "Why This Risk?" section on the Overview
tab. Adds `RiskExplanationWidget`, which renders a `RiskExplanation`
as-is (narrative, contributing IOC evidence, warnings, correlation
context, empty/error states). `InvestigationWorkspacePage` builds the
explanation from the existing correlation report and settings-derived
API key state, and does not let a service failure crash the workspace
or leak a raw exception to the analyst. Evidence rows drill into the
IOC tab via the existing `IOCSummaryWidget` selection path; the
correlation summary drills into the Correlations tab — both reuse the
existing `ApplicationState`/tab-index navigation, with no new state
manager introduced.

## Frozen baseline

`e7683dd` is the current Phase 3C implementation baseline (HEAD at
the time of this freeze). Phase 3C is closed. Future work must build
on top of this baseline rather than reopen or rewrite Phase 3C
without a demonstrated bug, regression, correctness/security issue,
test failure, or genuine architectural violation.

## Verification

This freeze was verified directly in this session against the actual
repository state (not carried forward from prior claims):

```
git status:      working tree clean, nothing to commit
git log (HEAD):  e7683dd (feat: integrate phase 3c analyst risk context)
pytest (full suite, offscreen Qt): 362 passed, 0 failed, 0 errors
```

No additional verification (manual GUI smoke test, performance
testing, etc.) was performed beyond the above; none is claimed.

## Known pre-existing items

Recorded here without being fixed, per the freeze rules:

* **Documentation gap.** The repository has formal freeze
  documentation for Phase 1 and Phase 2, and a Part-level record for
  Phase 3A, but had no Phase 3B or Phase 3C freeze documentation
  prior to this file. This document addresses the Phase 3C gap only.
  No Phase 3B content is recorded or invented here — a Phase 3B
  freeze document, if wanted, is a separate task.
* **Existing TODO.**
  `app/gui/widgets/dashboard/featured_investigation_card.py:37`
  contains a TODO noting logic duplicated with
  `ThreatIntelligenceFeedWidget._SEVERITY_BADGE_MAP`. This is a
  pre-existing maintenance item, is not part of Phase 3C, and was not
  modified as part of this freeze.

## Not implemented (explicitly out of scope for Phase 3C)

No Phase 3D work, no new risk-scoring formula, no new
threat-intelligence provider architecture, no new database
architecture, and no Dashboard redesign. None of these were started
as part of Phase 3C.

## Next Baseline

`e7683dd` is now the authoritative frozen baseline for **Phase 3D**
(or whichever phase is designated next). Local `main` is ahead of
`origin/main` and has not been pushed as part of this freeze.
