# SOC-IQ — Target State (summary)

Full detail: `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` §2–§25.
This file is a navigation summary, not a replacement — read the linked sections for anything
you plan to act on.

## Layer diagram (master plan §2.1)

React+TypeScript (presentation, view models, motion)
  ↕ typed IPC commands/events
Tauri/Rust (desktop shell, capability boundary, sidecar supervision, native OS calls)
  ↕ local-loopback HTTP + SSE (`127.0.0.1`, ephemeral port, chosen at startup — ADR-006)
Python FastAPI sidecar — application boundary (command handlers, event publisher, DTOs)
  ↕
Python domain services (extraction · scoring · TI orchestration · correlation · reporting · investigation lifecycle)
  ↕
SQLite (repository pattern, migrations)

Rust also owns, beside this stack, without a Python round-trip: native file dialogs/fs
access under explicit capability scopes, OS notifications, OS credential store, and (future,
not yet authorized — rule #15/#16 in `NON_NEGOTIABLE_RULES.md`) YARA/hashing/PE-metadata
native workers.

## Target directory tree (master plan §25)

```
soc-iq/
├── frontend/          NEW — React + TypeScript
├── src-tauri/          NEW — Rust shell
├── backend/            FROM current app/ — domain core preserved
│   ├── app/
│   └── tests/          FROM current tests/, baseline preserved
├── docs/                FROM current docs/ + this bible + new ADRs
├── scripts/             NEW — build/package/lockfile-refresh scripts
└── samples/              FROM current samples/
```

`app/gui/**` has no target directory — retired, superseded by `frontend/` + `src-tauri/`.
See `FILE_STRUCTURE.md` for the deeper breakdown and `CURRENT_TO_TARGET_MAPPING.md` for the
file-by-file mapping.

## IPC decision (ADR-006, master plan §2.2)

Local HTTP/JSON-RPC(-ish)/SSE service on `127.0.0.1`, launched and supervised by Tauri as a
sidecar process (FastAPI/uvicorn). Rejected alternatives: Rust→Python FFI, stdio subprocess
protocol, named pipes. Reasoning: reuses a mature, independently testable/debuggable Python
web stack; same server can back CLI/automation later; natural home for an SSE event channel;
keeps Rust free of any domain-logic code path by construction.

## Data / Command / Event / State model (master plan §3)

| Category | Owner |
|---|---|
| Data | Python domain + SQLite |
| Commands | Python application boundary (FastAPI handlers) |
| Events | Python publishes; Tauri relays; React subscribes |
| State | React client store, never persisted server-side |

This is the fix for the current "pipeline checkboxes don't actually gate anything" defect
(master plan §1.4): pipeline options become fields on the `analyze_report` command payload,
not GUI-local booleans.

## Threat intelligence target (master plan §5, PHASE4C doc)

`ThreatIntelProvider` protocol + adapters (VirusTotal first, AbuseIPDB/OTX later — not
before the abstraction is proven, rule #16). Canonical verdict enum:
`MALICIOUS / SUSPICIOUS / CLEAN / NOT_FOUND / UNSUPPORTED / NO_API_KEY / UNAVAILABLE /
RATE_LIMITED / ERROR`. Critical rule: `NOT_FOUND != CLEAN` (rule #9).

## Security target (master plan §6, `docs/security/*`)

Explicit trust boundaries between React / Tauri-Rust / Python / SQLite / external TI
providers / report files / filesystem / OS credential store. Least-privilege Tauri
capability manifest (no `shell:*`, no unrestricted `fs:*`). Loopback-only backend. OS-backed
secret storage for API keys, handed to the sidecar at process start.

## Migration roadmap (master plan §26)

4A architecture reset (done) → 4B domain boundary hardening (done) → 4C TI provider
abstraction design (done; implementation pending) → 4D unified command/event contract
(in progress) → 4E Rust/Tauri foundation → 4F React design system → 4G application shell →
4H dashboard → 4I analysis workflow → 4J investigation workspace → 4K TI/risk views →
4L reporting → 4M security hardening → 4N integration → 4O PySide6 retirement →
4P final audit. Full per-phase objective/deliverables/exit-criteria table: master plan §26.

## What target-state work is explicitly NOT authorized yet

YARA/Sigma/sandbox integration, a second TI provider implementation, the Tauri OS updater —
see master plan §30.F and `NON_NEGOTIABLE_RULES.md` #15–#16.
