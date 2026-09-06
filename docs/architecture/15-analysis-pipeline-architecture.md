# Analysis Pipeline Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §14, §1.4 (current-state defect), `docs/contracts/command-model.md`.

## CURRENT STATE (CONFIRMED from source)

`app/gui/pages/analyze_page.py` presents three pipeline checkboxes (extraction / TI
enrichment / scoring). Source comments in the file **state outright** that none of the three
checkboxes currently gate what the backend pipeline actually executes — the enrichment
checkbox was always checked and enabled regardless of whether a VirusTotal key was
configured, with no real connection between checkbox state and pipeline behavior (CONFIRMED
by direct source read, Master Plan §1.4, matching baseline problem #1). This is a
UI-truthfulness defect: an analyst can believe they disabled TI enrichment and be wrong.

## TARGET STATE (PROPOSED)

```
Report ingestion → validation → extraction → normalization
   → [TI enrichment]   ← gated by analyze_report.options.enrich_ti  (server-enforced)
   → [risk scoring]    ← gated by analyze_report.options.score_risk (server-enforced)
   → correlation → persistence → events (analysis.progress ×N → analysis.completed)
   → frontend updates (via event stream, not a return value the UI must poll)
```

The three "checkboxes" become three boolean fields on the `analyze_report` command payload
(see `docs/contracts/command-model.md`), validated and enforced inside the Python
application-layer handler. There is no code path by which the UI can display
"enrichment off" while the backend enriches anyway, because the backend — not the UI — is the
only thing that decides whether enrichment runs. This is the direct architectural fix for the
current-state defect above, not a cosmetic UI change.

## MIGRATION NOTES

This fix ships as part of Phase 4I (Master Plan §26), with the exit criterion stated
explicitly: "backend enforces options, verified by test." The three current checkbox widgets
are retired along with the rest of `app/gui/pages/analyze_page.py` in Phase 4O.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding for the defect itself — confirmed directly at source. The exact current
worker-thread mechanics that execute the (currently un-gated) pipeline
(`app/gui/workers/analysis_worker.py`) remain **UNKNOWN — VERIFY IN PHASE 4B.**
