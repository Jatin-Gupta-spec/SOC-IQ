# SOC-IQ — System Architecture Overview

**Status:** Documentation Foundation (Phase 4A) — describes approved target architecture, not yet implemented.
**Authoritative source:** `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` (the Master Plan). This document is a focused entry point into it — where this document and the Master Plan appear to disagree, the Master Plan governs.
**Audience:** future implementation sessions (human or agent), architecture review, portfolio/interview walkthrough.

## Purpose

This document orients a reader (or a future Claude/agent session picking up Phase 4B or later)
to the overall shape of SOC-IQ before they open any single subsystem document. It does not
repeat the Master Plan's reasoning — see the Master Plan for *why* each decision was made
(§2.2 for the IPC choice, §26 for phase sequencing, §30 for the final verdict). This document
is *what the pieces are and where to read more about each one*.

## CURRENT STATE

SOC-IQ today is a single-process Python + PySide6 desktop application (~39,300 LOC, 206
files, 542/542 tests passing at last audit) with a CLI sharing the same domain core. Full
detail: Master Plan §1.

## TARGET STATE

A four-layer desktop application:

```
React + TypeScript (frontend)
   ↕ Tauri IPC
Tauri / Rust (desktop shell + capability boundary)
   ↕ local loopback HTTP + SSE
Python (domain core, unchanged in responsibility, restructured in packaging)
   ↕
SQLite (persistence)
```

Full diagram and reasoning: Master Plan §2.

## Document Map

| Concern | Document |
|---|---|
| Python backend structure | `02-python-backend-architecture.md` |
| Frontend structure | `03-frontend-architecture.md` |
| Tauri/Rust structure | `04-tauri-rust-architecture.md` |
| IPC mechanism | `05-ipc-architecture.md`, and `docs/contracts/` |
| Event system | `06-event-architecture.md`, and `docs/contracts/event-model.md` |
| Client-side state | `07-state-architecture.md` |
| Threat intelligence | `08-threat-intelligence-architecture.md` |
| Database | `09-database-architecture.md` |
| Security (overview) | `10-security-architecture.md`, full detail in `docs/security/` |
| Design system | `11-design-system-architecture.md` |
| Motion/animation | `12-motion-animation-architecture.md` |
| Frontend navigation | `13-frontend-information-architecture.md` |
| Investigation workspace | `14-investigation-workspace-architecture.md` |
| Analysis pipeline | `15-analysis-pipeline-architecture.md` |
| Reporting | `16-reporting-architecture.md` |
| Secrets/configuration | `17-secrets-configuration-architecture.md` |
| Packaging/release | `18-packaging-release-architecture.md` |
| Observability | `19-observability-architecture.md` |
| Testing | `docs/testing/testing-architecture.md` |
| Decisions and rationale | `docs/adr/ADR-001` through `ADR-010` |

## MIGRATION NOTES

No migration has begun. Phase 4B (source-level verification of the current GUI
controllers/services and the items marked UNKNOWN in Master Plan §1.8) is the next step and
is explicitly out of scope for this documentation set. See Master Plan §26 for the full phase
sequence and §30.E for the exact first task.

## UNKNOWN / REQUIRES VERIFICATION

Everything Master Plan §1.8 marks UNKNOWN remains UNKNOWN here too:
worker concurrency model (`app/gui/workers/analysis_worker.py`), whether
`app/database/connection.py` does any pragma/journaling configuration relevant to
multi-process access, full return shapes of `app/services/*`, and whether any existing test
exercises the two-event-bus interaction. These are **UNKNOWN — VERIFY IN PHASE 4B**, not
assumed one way or the other by any document in this set.
