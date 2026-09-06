# SOC-IQ Architecture Documentation — START HERE

This `docs/architecture/` tree (plus `docs/adr/`, `docs/contracts/`, `docs/security/`,
`docs/testing/`, `docs/migration/`, `docs/phase4/`) is SOC-IQ's persistent architectural
memory. It exists so a completely fresh Claude session can understand the project without
access to any previous chat's context.

## Recommended reading order

1. `PROJECT_CONSTITUTION.md` — identity, philosophy, current status, next task. Read this
   first, always.
2. `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` — the
   architecture bible: current state, target state, every subsystem, the full migration
   roadmap, ADR index, risk lists. This is the single largest source of truth in the project.
3. `FILE_STRUCTURE.md` — where does new code go.
4. `CURRENT_STATE.md` / `TARGET_STATE.md` — what exists today vs. what's being built toward.
5. `NON_NEGOTIABLE_RULES.md` — what must never happen, regardless of task framing.
6. `CURRENT_TO_TARGET_MAPPING.md` — file-by-file disposition.
7. Relevant subsystem documentation — see the table below.
8. `IMPLEMENTATION_STATUS.md` — current phase, what's DONE vs. NOT STARTED, with evidence.
9. `docs/adr/ADR-*.md` — the individual decision records.
10. `CLAUDE_BOOTSTRAP.md` — behavioral instructions for a fresh session before it writes code.

## Subsystem documentation map

| Area | Where |
|---|---|
| System overview | `01-system-overview.md` |
| Python backend | `02-python-backend-architecture.md` |
| Frontend | `03-frontend-architecture.md`, `13-frontend-information-architecture.md` |
| Tauri/Rust | `04-tauri-rust-architecture.md` |
| IPC | `05-ipc-architecture.md`, `docs/contracts/ipc-rules.md` |
| Events | `06-event-architecture.md`, `docs/contracts/event-model.md` |
| State | `07-state-architecture.md` |
| Threat intel | `08-threat-intelligence-architecture.md`, `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` |
| Database | `09-database-architecture.md` |
| Security | `10-security-architecture.md`, `docs/security/*` |
| Design system | `11-design-system-architecture.md` |
| Motion | `12-motion-animation-architecture.md` |
| Investigation workspace | `14-investigation-workspace-architecture.md` |
| Analysis pipeline | `15-analysis-pipeline-architecture.md` |
| Reporting | `16-reporting-architecture.md` |
| Secrets/config | `17-secrets-configuration-architecture.md` |
| Packaging/release | `18-packaging-release-architecture.md` |
| Observability | `19-observability-architecture.md` |
| Phase 4B findings | `PHASE4B_APPLICATION_BOUNDARY_DESIGN.md`, `PHASE4B_ARCHITECTURAL_FINDINGS.md`, and everything under `docs/migration/` |
| Phase 4D (API/event contract) | `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md` |
| Contracts (commands/DTOs/errors/events) | `docs/contracts/*` |
| Testing strategy | `docs/testing/testing-architecture.md` |
| ADRs | `docs/adr/ADR-001` through `ADR-010` |

## Authoritative when documents conflict

See `PROJECT_CONSTITUTION.md` §12 for the full hierarchy. Short version: this constitution
and `NON_NEGOTIABLE_RULES.md` outrank everything; the master plan outranks individual
subsystem docs; subsystem docs outrank implementation-status snapshots; code/comments are
last. If code and docs disagree, that's a contradiction to flag and resolve deliberately —
see `CLAUDE_BOOTSTRAP.md`.

## What this bible layer is, and isn't

This `README.md`, `PROJECT_CONSTITUTION.md`, `NON_NEGOTIABLE_RULES.md`, `FILE_STRUCTURE.md`,
`CURRENT_STATE.md`, `TARGET_STATE.md`, `CURRENT_TO_TARGET_MAPPING.md`,
`IMPLEMENTATION_STATUS.md`, `UNKNOWN_AND_ASSUMPTIONS.md`, `CLAUDE_BOOTSTRAP.md`, and
`project-manifest.yaml` are a **new consolidation layer**, added on top of the extensive
architecture documentation that already existed in this repository (19 numbered subsystem
docs, 10 ADRs, 10 contract docs, 8 security docs, 7 migration docs, 2 phase docs, 1 testing
doc). They summarize and index that existing material rather than duplicate it. See
`DOCUMENTATION_AUDIT.md` for exactly what was created, what was deliberately not recreated,
and why.
