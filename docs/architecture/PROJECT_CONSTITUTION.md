# SOC-IQ — Project Constitution

**Read this file FIRST in every new Claude session, before touching any code.**

Architecture Version: **Phase 4 Architecture v1.0**
Status: **APPROVED** (master plan) / Phase 4B **COMPLETE** / Phase 4C **COMPLETE (source-implemented)** / Phase 4D **PARTIALLY IMPLEMENTED (representative slice)**
Last Verified: this reconciliation session, against the archive audited in
`docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md`. The prior "Last Verified" line here cited a
`SOC-IQ-Phase4D-COMPLETE-PROJECT.zip` snapshot name that did not match the archive it was
shipped in — flagged, not silently fixed by renaming the archive; see the reconciliation
audit §2/§10/§14 for the full discrepancy.
Verified Against: flat archive snapshot — **no `.git` history was present in the archive**; see `docs/migration/PHASE4B_GIT_BASELINE_NOTE.md`. A local repo may have been initialized in a later phase — check `git log` yourself before trusting this line for long.

This document is a synthesis and index. It does not replace the detailed source documents —
it tells you which ones are authoritative and in what order to read them. Where this
document and a detailed subsystem document disagree, **the subsystem document wins** unless
it is older than a documented correction (see §12, Authority Hierarchy).

---

## 1. Project Identity

SOC-IQ is a desktop application for SOC (Security Operations Center) analysts: it ingests a
threat/incident report, extracts IOCs (IPs, domains, URLs, hashes), enriches them against
threat-intelligence providers, computes an explainable risk score, correlates findings across
investigations, and produces exportable reports (JSON/CSV/Markdown/HTML/PDF).

## 2. Product Purpose

Give an analyst one desktop tool that takes a raw report from "just text" to "scored,
enriched, correlated, exportable investigation" without hand-copying IOCs between five
different tools. The explainability of the risk score and the correctness of TI verdicts
(see §17) are the product's actual value proposition, not the UI chrome around them.

## 3. Core Engineering Philosophy

- **Preserve proven domain logic. Do not rewrite what already works.** Extraction, scoring,
  and the database repository layer are the most valuable existing assets in the codebase —
  see `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` §1.1–§1.2.
- **Verify against source, never against memory of prior chats.** Every phase document in
  this project tags its claims CONFIRMED / LIKELY / UNKNOWN / DEPRECATED for exactly this
  reason. Continue that discipline.
- **Staged migration, not a rewrite.** See §5 and the 4A–4P roadmap in the master plan §26.
- **One source of truth per concern.** Data in Python+SQLite, commands in the Python
  application boundary, events published once, state owned by the frontend — see §8–§11.
- **Documentation-only phases are allowed and have already happened** (4A, 4C) — producing a
  correct design document without touching code is legitimate, first-class work in this
  project, not a stall.

## 4. Current Baseline (CONFIRMED, re-verified this session)

- Single Python codebase under `app/`, PySide6 desktop GUI, sharing the same domain modules
  (`extractor.py`, `analyzer.py`, `scoring/`, `threat_intel/`, `database/`, `reporting/`,
  `services/`) between the GUI and a thin CLI (`app/cli.py`).
- `frontend/`, `src-tauri/`, and `sidecar-core/` **do exist** at the repo root in this
  archive (React/Tauri/Rust foundation and sidecar-core work from a later phase in this
  project's lineage than Phase 4D). This corrects an earlier version of this line, which
  claimed none of the three existed yet — that was true of an earlier snapshot but not of
  the archive this constitution ships alongside; not independently re-audited this session
  (out of Phase 4D Part 2's scope — see `docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md` §15).
  No `backend/` directory exists; the Python domain still lives at `app/`, not
  `backend/app/` — the target directory structure (§25 of the master plan) is still not
  fully in effect.
- A new `app/api/` and `app/application/` layer exists (Phase 4D work): FastAPI route
  (`app/api/app.py`, requires `fastapi`, not installed in this sandbox), command dispatch
  (`app/application/handlers.py`), DTOs, response/error envelopes, and an event collector.
  Only three commands are wired: `get_investigation`, `list_investigations`,
  `analyze_report`. SSE `/events` streaming is explicitly `NotImplementedError` — not a bug,
  documented as deferred (see `app/api/app.py` docstring and
  `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md` §22).
- `app/threat_intel/service.py::ThreatIntelService` is migrated onto a real
  `ThreatIntelProvider` protocol (`app/threat_intel/provider.py`), with `VirusTotalProvider`
  (`app/threat_intel/virustotal_provider.py`) as the sole concrete adapter today. This was
  re-confirmed by direct source read and by `tests/test_threat_intel_provider_contract.py` /
  `tests/test_virustotal_provider.py` passing — see
  `docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md` §3/§12 and `docs/phase4/PHASE4C_FREEZE.md`.
  This corrects an earlier version of this line, which stated the abstraction was
  design-only; that was true when `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` was
  first written, but the source moved ahead of it in a later, undocumented session, and this
  file was not updated to match at the time.
- Test baseline: **399 non-GUI tests pass** in this sandbox (`pytest -q --ignore=tests/gui`,
  re-run this session). The GUI test suite (`tests/gui/`) could not be collected here because
  `PySide6` is not installed in this sandbox — this is a **sandbox environment gap**, not a
  confirmed code regression; do not treat it as evidence the GUI tests are broken. Earlier
  phase docs report a "542 tests passing" baseline including GUI tests — that number was not
  independently re-verified this session for the GUI portion. Re-run the full suite with
  PySide6 installed before trusting either number as current.

## 5. Target Architecture (one paragraph — full detail in §2 of the master plan)

React+TypeScript frontend → Tauri (Rust) desktop shell/capability boundary → local-loopback
HTTP+SSE → Python FastAPI sidecar (application boundary) → Python domain services → SQLite.
Rust owns native OS capabilities (file dialogs, notifications, OS secret store, future
YARA/hashing) directly, beside the Python round-trip, never inside it. See
`docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` §2.1 for the diagram.

## 6. Technology Responsibilities

| Layer | Owns | Never does |
|---|---|---|
| React/TS | UI, view models, motion, client state | persistence, scoring, TI logic, direct SQLite/network access |
| Tauri/Rust | shell, packaging, capabilities, native OS calls, sidecar supervision | business logic |
| Python | domain logic, persistence, TI orchestration, reporting | native OS capability enforcement |
| SQLite | durable storage | — |

## 7. Architectural Boundaries (must never be crossed)

React → SQLite. React → Python internals. React → external TI APIs directly. Rust → scoring.
Rust → TI orchestration. Rust → database business logic. Python domain → Qt. Python domain →
React. Python domain → Tauri implementation details. Frontend → arbitrary filesystem.
Frontend → arbitrary internet. Full list: `NON_NEGOTIABLE_RULES.md`.

## 8. Data Ownership
Python domain + SQLite is the single source of truth for investigations, IOCs, TI results,
risk scores, reports, settings. Frontend never persists domain data beyond a short-lived
client cache.

## 9. Command Ownership
The Python application boundary (`app/application/handlers.py` today; `backend/app/api/` in
the target tree) owns all imperative commands (`analyze_report`, `list_investigations`,
`get_investigation`, and the not-yet-implemented create/delete/enrich/export/search
commands — see `docs/contracts/PHASE4B_COMMAND_INVENTORY.md` and
`PHASE4B_QUERY_INVENTORY.md`). Tauri only relays commands it owns itself (native file
dialogs, save-export).

## 10. Event Ownership
Python publishes; Tauri relays unmodified; React subscribes. One schema, one publisher,
versioned — see `docs/contracts/event-model.md` and `event-versioning.md`. This replaces the
two independent Qt signal buses (`app/gui/events/application_events.py` and
`app/gui/events/event_bus.py`) that exist in the current PySide6 code — both are **REMOVE**,
not merge-by-renaming (master plan §27, §30.H).

## 11. State Ownership
Current page, selected investigation/IOC, active analysis, UI-only flags live in the React
client state store once it exists. Never persisted server-side. In the current PySide6 code,
this role is played by `ApplicationState` — see
`docs/migration/PHASE4B_STATE_INVENTORY.md` for the full existing-state audit.

## 12. Authority Hierarchy

When documents conflict, higher wins:

1. `PROJECT_CONSTITUTION.md` (this file)
2. `NON_NEGOTIABLE_RULES.md`
3. `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` (the Architecture Bible)
4. `docs/adr/ADR-*.md`
5. Phase/subsystem architecture documents (`docs/architecture/0N-*.md`, `docs/phase4/*`, `docs/migration/*`)
6. `docs/contracts/*`
7. Implementation status documents (`IMPLEMENTATION_STATUS.md`)
8. Comments / code

**If code contradicts documentation:** do not silently change either. Flag the contradiction,
determine whether code is stale, documentation is stale, or the architecture decision
genuinely changed, then update the authoritative document deliberately and say so in your
output. This has already happened once, correctly: Phase 4B applied BEFORE/AFTER corrections
directly to `09-database-architecture.md`, `06-event-architecture.md`, and
`07-state-architecture.md` after source review contradicted the original text.

## 13–21. Subsystem Philosophies

Rather than restate them, this section points at the authoritative source per subsystem —
read the linked document, do not re-derive its content from this summary:

| Subsystem | Authoritative document |
|---|---|
| Frontend | `docs/architecture/03-frontend-architecture.md`, master plan §9 |
| Backend | `docs/architecture/02-python-backend-architecture.md`, master plan §4 |
| Rust/Tauri | `docs/architecture/04-tauri-rust-architecture.md`, master plan §7–§8 |
| Database | `docs/architecture/09-database-architecture.md` (BEFORE/AFTER-corrected), master plan §17 |
| Threat intel | `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md`, master plan §5 |
| Design system | `docs/architecture/11-design-system-architecture.md`, master plan §10 |
| Motion | `docs/architecture/12-motion-animation-architecture.md`, master plan §11 |
| Testing | `docs/testing/testing-architecture.md`, master plan §20 |
| Migration | `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` §26 |

## 22. Non-Negotiable Rules
See `NON_NEGOTIABLE_RULES.md` — read it before any implementation task.

## 23. Forbidden Shortcuts
See `NON_NEGOTIABLE_RULES.md` §"Do not do this" and master plan §30 Final Summary #9.

## 24. Current Phase
**Phase 4D, in progress** (a representative command/event slice implemented; SSE streaming
and the remaining commands from the Phase 4B inventories are not yet built). Phase 4C is
**source-implemented** — `ThreatIntelProvider`/`VirusTotalProvider` exist and
`ThreatIntelService` is migrated onto the protocol; see `docs/phase4/PHASE4C_FREEZE.md`. See
`IMPLEMENTATION_STATUS.md` for the full per-component breakdown, though note that document
itself was found stale on this same point during reconciliation and should be re-verified
before being trusted for anything not re-confirmed in
`docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md`.

## 25. Current Implementation Status
Full detail: `IMPLEMENTATION_STATUS.md` (stale in places — see note above).
`docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md` is the freshest verified source. One-line
summary as of reconciliation: Python domain core, PySide6 GUI, and CLI are fully implemented
and tested (481 non-GUI / 635 combined-with-GUI tests green, freshly run). The
`ThreatIntelProvider` abstraction is implemented and tested. The API/application boundary
exists for 3 commands (`get_investigation`, `list_investigations`, `analyze_report`).
`frontend/`, `src-tauri/`, and `sidecar-core/` exist in this archive (see §4) but were not
re-audited this session — out of scope for this Phase 4D command-slice pass.

## 26. Next Implementation Task
Per the master plan §26 (4D row) and `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md`, the
next authorized work is completing Phase 4D: wire the remaining commands from
`docs/contracts/PHASE4B_COMMAND_INVENTORY.md` / `PHASE4B_QUERY_INVENTORY.md`, and implement
the `/events` SSE stream against `app.application.events.EventCollector`. **Do not start
Phase 4E (Rust/Tauri foundation) before Phase 4D's exit criteria — contract tests passing —
are met.** Confirm current status against `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md`
directly before beginning, since this constitution is a snapshot and may already be stale by
the time you read it.

## 27. Known Risks
Top 10 architectural risks and top 10 security risks are enumerated in the master plan,
Final Summary Outputs §6–§7. Do not re-derive these; read them there.

## 28. Known Unknowns
See `UNKNOWN_AND_ASSUMPTIONS.md`. Most Phase 4B-era unknowns were resolved during Phase 4B
(see `docs/architecture/PHASE4B_ARCHITECTURAL_FINDINGS.md` "Remaining unknowns" section for
what's still open: reporting internals, settings internals beyond what 4C touched, scoring
engine internals, extractor internals were explicitly escalated rather than silently
assumed).

## 29. Important Historical Decisions
- The two current Qt event buses were diagnosed as confusing *by the original project's own
  code comments*, not invented as a criticism during migration planning (master plan §1.3).
- `risk_explanation_service.py`'s backend→GUI import was found to be a real architectural
  defect during Phase 4B and was **documented, not fixed** — deferred to 4C/4D per the rule
  that non-trivial fixes are not made silently during a documentation phase (see
  `docs/migration/PHASE4B_EXIT_CRITERIA.md`, "Explicit non-actions").
- No `.git` history shipped with any archive snapshot seen so far. Treat this as a standing
  condition, not a one-time surprise — see `docs/migration/PHASE4B_GIT_BASELINE_NOTE.md`.

## 30. How Claude Must Behave When Modifying This Project
See `CLAUDE_BOOTSTRAP.md` — read it in full before writing or editing any code.
