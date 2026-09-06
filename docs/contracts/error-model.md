# Error Model

**Status:** Documentation Foundation (Phase 4A).
**Related:** `response-model.md`, `event-model.md` (`analysis.failed`,
`ti.enrichment.failed`), `docs/architecture/08-threat-intelligence-architecture.md`
(provider error states).

## CURRENT STATE

`app/threat_intel/exceptions.py` (CONFIRMED, 76 LOC) already defines a set of specific
exception types: `InvalidAPIKeyError`, `InvalidDomainError`, `InvalidHashError`,
`InvalidIPError`, `InvalidURLError`, `RateLimitExceededError`, `ThreatIntelConnectionError`,
`ThreatIntelTimeoutError`, `UnexpectedAPIResponseError` (CONFIRMED by import list in
`app/threat_intel/service.py`). This is a real, existing precedent for specific,
named error types rather than generic exceptions — the target error model extends this
pattern to the command/event boundary rather than introducing a new philosophy.

## TARGET STATE (PROPOSED)

- Every command failure returns `{ "success": false, "error": { "code": "...", "message":
  "..." } }` (see `response-model.md`) with a stable, documented `code` string
  (e.g. `INVESTIGATION_NOT_FOUND`, `INVALID_COMMAND_PAYLOAD`, `TI_PROVIDER_UNAVAILABLE`) —
  the frontend branches on `code`, never on parsing `message` text.
- The existing `app/threat_intel/exceptions.py` types map directly onto TI-specific error
  codes surfaced through this model (e.g. `RateLimitExceededError` → `TI_RATE_LIMITED`),
  preserving the existing exception granularity rather than collapsing it into a single
  generic "TI failed" code.
- Long-running command failures are additionally reported via a `*.failed` event
  (`analysis.failed`, `ti.enrichment.failed`) carrying the same `code`/`message` shape, so a
  frontend that's mid-operation learns of failure through the event stream it's already
  subscribed to, not by polling the original command's response again.
- Validation failures (malformed command payload) are rejected before touching domain logic,
  with a distinct `INVALID_COMMAND_PAYLOAD` code — this is the enforcement point referenced
  in `docs/security/ipc-security-model.md`.

## MIGRATION NOTES

The exact, exhaustive error-code catalog is Phase 4D implementation work, built by mapping
the existing exception types (`app/threat_intel/exceptions.py`, and any equivalent in
`app/database/`, `app/reporting/`) to codes — not invented independently of what already
exists.

## UNKNOWN / REQUIRES VERIFICATION

Whether `app/database/*` or `app/reporting/*` define their own specific exception hierarchies
comparable to `app/threat_intel/exceptions.py` — **UNKNOWN — VERIFY IN PHASE 4B** (not
independently confirmed for those modules during this pass).
