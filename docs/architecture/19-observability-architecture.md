# Observability Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §21.

## CURRENT STATE

`app/logger.py` exists (CONFIRMED, file present in the checkpoint) as the current logging
entrypoint. Its exact current structure (formatting, log levels, whether it already does any
redaction beyond the settings `__repr__` override) was not independently re-verified in this
pass — **UNKNOWN — VERIFY IN PHASE 4B**.

## TARGET STATE (PROPOSED)

- **Structured logging** (JSON lines) in the Python backend, with `correlation_id` and
  `investigation_id` attached to every log line touching an analysis — these are the same
  identifiers carried on events (`06-event-architecture.md`,
  `docs/contracts/correlation-ids.md`), so a log line and the event stream can be correlated
  directly.
- **Audit trail:** investigation create/update/delete and export actions are recorded as
  domain events persisted alongside investigations (not just transient bus events) — this
  gives a durable history independent of whether a frontend was even connected when the
  action happened.
- **Debug mode:** a verbose event/command logging toggle, off by default.
- **Explicit redaction at the logging layer:** API keys and full IOC raw report content are
  never logged at INFO level; only IDs/hashes are. This extends the existing settings-level
  redaction discipline (`17-secrets-configuration-architecture.md`) to logging generally,
  rather than leaving it as a settings-only guarantee.

## MIGRATION NOTES

Observability work has no single dedicated phase — correlation IDs are introduced with the
event/command contract in Phase 4D, and audit-trail persistence is verified as part of
security hardening in Phase 4M.

## UNKNOWN / REQUIRES VERIFICATION

Current `app/logger.py` structure and any existing redaction behavior beyond the settings
`__repr__` override: **UNKNOWN — VERIFY IN PHASE 4B.**
