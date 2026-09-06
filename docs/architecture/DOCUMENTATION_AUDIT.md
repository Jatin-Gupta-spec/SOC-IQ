# SOC-IQ — Documentation Audit

Produced at the end of the "create the authoritative project architecture bible" task.
Documentation-only session — no files under `app/`, `tests/`, `config/`, `database/`, or
`samples/` were created, deleted, or modified. Only `docs/architecture/` gained new files.

## Method

1. Unzipped and directly inspected the full repository (276 files).
2. Read `README.md` (empty — 0 lines), confirmed no `.git` directory exists in this archive.
3. Read the existing architecture bible
   (`PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md`, 946 lines) in full — sections 0–1
   (method + current state), 2–4 (target architecture, data model, domain mapping), and
   24–30 (packaging, directory structure, migration plan, preserve/adapt matrix, ADR index,
   recruiter impact, final verdict, final summary outputs) were read verbatim; sections 5–23
   were located and indexed but not re-transcribed here, since they already exist as the
   authoritative source and this task's own instruction (§3) says to consolidate rather than
   duplicate an existing authoritative document.
4. Read `docs/migration/PHASE4B_EXIT_CRITERIA.md` in full to establish Phase 4B's completion
   status and deliverables index.
5. Read `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` and
   `PHASE4D_API_EVENT_ARCHITECTURE.md` headers/status blocks to establish Phase 4C/4D status.
6. Read `app/api/app.py` and `app/application/handlers.py` in full (source, not docs) to
   verify what Phase 4D actually implemented vs. designed.
7. Ran `python3 -m pytest -q --ignore=tests/gui` — **399 passed**. `tests/gui/` could not be
   collected (`ModuleNotFoundError: No module named 'PySide6'`), a sandbox limitation, not a
   code defect — documented as such rather than silently omitted or silently assumed passing.
8. Confirmed no `frontend/`, `src-tauri/`, or `backend/` directories exist at the repo root.

## Documents created this session

All under `docs/architecture/`:

- `README.md` — index and reading order.
- `PROJECT_CONSTITUTION.md` — the "read first" file.
- `NON_NEGOTIABLE_RULES.md`
- `CURRENT_STATE.md`
- `TARGET_STATE.md`
- `FILE_STRUCTURE.md`
- `CURRENT_TO_TARGET_MAPPING.md`
- `IMPLEMENTATION_STATUS.md`
- `UNKNOWN_AND_ASSUMPTIONS.md`
- `CLAUDE_BOOTSTRAP.md`
- `project-manifest.yaml`
- `DOCUMENTATION_AUDIT.md` (this file)

## Documents intentionally NOT created

The task brief's proposed structure lists roughly 90 files (backend/, frontend/, tauri/,
contracts/, security/, testing/, adr/ subdirectories with one file per concern). The large
majority of that structure **already exists** in this repository under different names and
was verified to cover the same ground:

| Proposed file | Already covered by |
|---|---|
| `SYSTEM_OVERVIEW.md` | `01-system-overview.md` |
| `backend/BACKEND_ARCHITECTURE.md` and most of `backend/*` | `02-python-backend-architecture.md`, `15-analysis-pipeline-architecture.md`, `16-reporting-architecture.md`, `17-secrets-configuration-architecture.md` |
| `backend/THREAT_INTEL_ARCHITECTURE.md` | `08-threat-intelligence-architecture.md` + `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` (the latter is more current and more detailed) |
| `backend/DATABASE_ARCHITECTURE.md`, `MIGRATION_ARCHITECTURE.md` | `09-database-architecture.md` |
| `frontend/*` (most files) | `03-frontend-architecture.md`, `13-frontend-information-architecture.md`, `11-design-system-architecture.md`, `12-motion-animation-architecture.md`, `14-investigation-workspace-architecture.md` |
| `tauri/*` (most files) | `04-tauri-rust-architecture.md` |
| `contracts/*` | `docs/contracts/*` (already exists as its own directory: command-model, response-model, error-model, event-model, event-versioning, correlation-ids, dto-boundaries, ipc-rules, frontend-backend-responsibility-boundaries; plus Phase 4B's `PHASE4B_COMMAND_INVENTORY.md` / `PHASE4B_QUERY_INVENTORY.md`) |
| `security/*` | `docs/security/*` (already exists: threat-model, trust-boundary-model, input validation via `report-ingestion-security-model.md`, `filesystem-security-model.md`, `ipc-security-model.md`, `secret-management-model.md`, `dependency-supply-chain-security-model.md`, `tauri-capability-model.md`) |
| `testing/*` | `docs/testing/testing-architecture.md` + `docs/migration/PHASE4B_TEST_COVERAGE_GAPS.md` |
| `adr/ADR-001..010` | `docs/adr/ADR-001` through `ADR-010` already exist, already matching the task brief's own suggested ADR list by content (titles differ slightly, decisions match) |
| `SECURITY_BOUNDARIES.md`, `TRUST_BOUNDARIES.md` | `docs/security/trust-boundary-model.md` |
| `FAILURE_MODES.md`, `OBSERVABILITY.md` | `19-observability-architecture.md` (failure modes not separately broken out — flagged below as a real gap, not silently assumed covered) |
| `DATA_FLOW.md`, `COMMAND_FLOW.md`, `EVENT_FLOW.md`, `STATE_FLOW.md` | Master plan §3 covers the model; concrete step-by-step flows (analyze/export/TI) are described in master plan §14–§16 narrative form rather than as separate flow diagrams — flagged below as a partial gap |
| `MIGRATION_PLAN.md`, `DEPENDENCY_MAP.md` | master plan §26 (migration plan); no standalone dependency-map document exists — flagged below |

Creating near-duplicate files for all of these would violate the task's own instruction
(§3): "avoid duplicate sources of truth... The final structure must have ONE authoritative
version of each architectural decision." Instead, this session added the consolidation/index
layer (`PROJECT_CONSTITUTION.md`, `FILE_STRUCTURE.md`, `CURRENT_STATE.md`, `TARGET_STATE.md`,
`CURRENT_TO_TARGET_MAPPING.md`, `IMPLEMENTATION_STATUS.md`, `NON_NEGOTIABLE_RULES.md`,
`UNKNOWN_AND_ASSUMPTIONS.md`, `CLAUDE_BOOTSTRAP.md`, `project-manifest.yaml`, `README.md`)
that the task brief itself describes as "the most important file(s)" — these are genuinely
new, since nothing in the existing repository played the "read this first" / "bootstrap a
fresh session" / "file-by-file mapping" role before this session.

## Contradictions found

None between existing documents and source, beyond the ones Phase 4B already found and
corrected in place (`09-database-architecture.md`, `06-event-architecture.md`,
`07-state-architecture.md` — already BEFORE/AFTER-annotated, not re-touched this session).

One discrepancy worth flagging explicitly: `docs/migration/PHASE4B_EXIT_CRITERIA.md` and the
master plan both reference a "542 tests passing" baseline; this session could only
independently verify 399 (non-GUI) passing, because `PySide6` is not installed in this
sandbox. This is not evidence the other ~143 GUI tests are broken — it's a sandbox gap,
recorded honestly in `CURRENT_STATE.md` and `IMPLEMENTATION_STATUS.md` rather than either
repeated as fact or silently dropped.

## Remaining UNKNOWNs

See `UNKNOWN_AND_ASSUMPTIONS.md` for the full list. Headline items: exact target subpackage
for several small `app/*.py` utility modules; exact `extractor.py`/`analyzer.py` domain
subpackage boundary; target home for `tests/gui/`; frontend build tooling choice; exact
database migration runner mechanism.

## Genuine gaps identified (not filled this session — flagged for a future phase, per the
task's own "if uncertain, STOP and document" rule)

- No standalone step-by-step DATA_FLOW/COMMAND_FLOW/EVENT_FLOW/STATE_FLOW diagrams exist yet
  as separate documents — only narrative descriptions inside the master plan and Phase 4D
  doc. Worth creating once Phase 4D's remaining commands are wired, so the flows reflect
  real code rather than being written speculatively now.
- No standalone FAILURE_MODES.md or DEPENDENCY_MAP.md exists. Not created this session
  because writing one accurately would require deeper source tracing than this session's
  scope covered (documentation consolidation, not a fresh audit of every subsystem) — better
  done as part of, or right before, Phase 4E/4M when the sidecar-supervision and security
  hardening work makes failure modes concrete rather than speculative.

## Current implementation phase

Phase 4D, in progress. See `IMPLEMENTATION_STATUS.md` for the full breakdown.

## Exact next authorized implementation task

Per master plan §26 (4D row) and `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md`: wire the
remaining commands from `docs/contracts/PHASE4B_COMMAND_INVENTORY.md` /
`PHASE4B_QUERY_INVENTORY.md`, and implement the `/events` SSE stream. Phase 4E (Rust/Tauri
foundation) is not authorized to begin until Phase 4D's contract tests are passing. No new
implementation was performed this session — this task was documentation only, per its own
explicit instructions.
