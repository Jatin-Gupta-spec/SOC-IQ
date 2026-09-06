# Report Ingestion Security Model

**Status:** Documentation Foundation (Phase 4A).
**Related:** `threat-model.md`, `docs/architecture/15-analysis-pipeline-architecture.md`.

## CURRENT STATE (CONFIRMED)

No `subprocess`/`eval`/`exec`/`pickle`/`shell=True` usage exists anywhere in `app/`
(CONFIRMED, prior audit + this pass) — ingested report content is never used to construct
executable code or shell commands under the current architecture. This is a real, existing
mitigation, preserved unchanged going forward. Whether current extraction/scoring code
enforces explicit size limits or has been audited for regex catastrophic-backtracking risk
was not independently re-verified in this pass.

## TARGET STATE (PROPOSED)

- Report ingestion (`docs/architecture/15-analysis-pipeline-architecture.md`) treats all
  uploaded report content, and every IOC value extracted from it, as untrusted data
  end-to-end — never executed, never used to construct a shell command, never rendered as
  auto-clickable without user intent.
- Explicit input size limits are enforced at the API command-validation boundary
  (`docs/contracts/command-model.md`) before a report reaches the extraction pipeline.
- Extraction/scoring regular expressions are reviewed for catastrophic-backtracking risk as
  part of Phase 4B hardening — this review has not yet occurred (see UNKNOWN below) and is
  not assumed complete by any other document in this set.
- The no-`shell=True`/no-`eval`/no-`exec` discipline confirmed in current Python code is
  treated as a hard, cross-language rule extended to Rust as well (`threat-model.md`) — no
  new code path introduced during migration may use ingested content to construct a shell
  command in any language.

## MIGRATION NOTES

The regex-DoS review is explicitly scheduled as Phase 4B hardening work (Master Plan §6),
not deferred indefinitely — it is one of the concrete outputs expected from that phase,
alongside the controller/service inventory.

## UNKNOWN / REQUIRES VERIFICATION

Whether current extraction/scoring regexes have already been reviewed for catastrophic
backtracking, and whether any current size cap exists on report ingestion: **UNKNOWN —
VERIFY IN PHASE 4B.**
