# Command Model

**Status:** Documentation Foundation (Phase 4A). Architectural contract only — no API is
implemented yet.
**Related:** Master Plan §3 (command ownership), §16 (representative examples),
`docs/architecture/05-ipc-architecture.md`, ADR-006.

## CURRENT STATE

No command model exists today. The current GUI issues in-process Python method calls
directly from Qt controllers/services to domain modules (CONFIRMED, Master Plan §1.1) — there
is no serialized command boundary to document as "current state" here.

## TARGET STATE (PROPOSED)

A command is an imperative request from the frontend to the Python backend, sent as
`POST /commands/{name}` with a JSON body, validated against an explicit schema before
touching any domain logic (this validation step is a hard requirement — see
`docs/security/ipc-security-model.md`).

**Representative commands** (Master Plan §16; full, exhaustive schema set is implementation
work for Phase 4D, not defined here):

| Command | Purpose |
|---|---|
| `analyze_report` | Ingest and process a report; carries the pipeline-option gating described in `docs/architecture/15-analysis-pipeline-architecture.md` |
| `get_investigation` | Fetch a single investigation by id |
| `list_investigations` | Fetch a page of investigations |
| `get_iocs` | Fetch IOCs for an investigation |
| `get_threat_intelligence` | Fetch TI results for an investigation/IOC |
| `get_risk` | Fetch the risk-score breakdown for an investigation |
| `export_report` | Trigger a report export (see `docs/architecture/16-reporting-architecture.md`) |
| `export_investigations_csv` | Bulk investigation-history CSV export (see `docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md`); distinct from `export_report` |
| `delete_investigation` | Delete an investigation |
| `search_investigations` | Search investigations |
| `enrich_ioc` | Request TI enrichment for a specific IOC |

**Example payload** (`analyze_report`):

```json
{
  "report_source": { "type": "file", "path": "..." },
  "options": { "extract_iocs": true, "enrich_ti": true, "score_risk": true }
}
```

**Rule:** every command has a corresponding response model (`response-model.md`) and, where
long-running, a corresponding set of events (`event-model.md`) that report progress and
completion — a command's HTTP response acknowledges receipt/validation, not necessarily
final completion, for long-running operations.

## MIGRATION NOTES

The full, exhaustive command schema set (every field, every validation rule) is Phase 4D
implementation work. This document defines the *model* of what a command is and the
representative catalog; it is not the final OpenAPI/Pydantic schema.

## UNKNOWN / REQUIRES VERIFICATION

Exact current parameter shapes accepted by the underlying domain functions this command
model will wrap (e.g. what `app/gui/controllers/analyze_controller.py` currently passes into
the analysis pipeline) are **UNKNOWN — VERIFY IN PHASE 4B**, and will inform the exact
Pydantic model fields at implementation time.
