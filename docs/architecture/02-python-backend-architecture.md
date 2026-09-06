# Python Backend Architecture

**Status:** Documentation Foundation (Phase 4A). Describes target packaging of the existing,
unmodified domain logic. No source files referenced here have been changed.
**Related:** Master Plan §4 (full mapping table), §1.1–1.2 (current state), ADR-001.

## CURRENT STATE (CONFIRMED from source)

The domain core lives under `app/` and is already shared by two clients — the PySide6 GUI and
a 76-line CLI (`app/cli.py`) — both importing the same extraction, scoring, threat-intel,
database, and reporting modules. This dual-client reuse is the strongest piece of existing
evidence that a third client (a future HTTP API) can reuse the same core without rewriting it.

Confirmed module ownership (Master Plan §1.2):

| Concern | Current module |
|---|---|
| IOC extraction | `app/extractor.py`, `app/analyzer.py` |
| Risk scoring | `app/scoring/engine.py`, `app/scoring/models.py` |
| Threat intel | `app/threat_intel/service.py`, `app/threat_intel/virustotal.py` |
| Persistence | `app/database/{connection,models,repository,service}.py` |
| Reporting | `app/reporting/{builder,service}.py` + 5 exporters |
| Settings | `app/settings/{models,repository,service}.py` |
| Correlation / dashboards | `app/services/*` |

## TARGET STATE (PROPOSED)

```
backend/
├── app/
│   ├── domain/            pure models + business rules (scoring, verdict normalization)
│   ├── application/       command handlers, use-cases, event publisher
│   ├── providers/         threat-intel provider adapters
│   ├── repositories/       persistence interfaces + SQLite implementation
│   ├── reporting/          exporters (existing, HTML internals redesigned — see 16-reporting-architecture.md)
│   ├── api/                 FastAPI app: command routes + SSE/WS event route (thin)
│   ├── cli.py                existing thin CLI, re-pointed at application/ layer
│   └── settings/             existing model, + secret-store adapter
└── tests/
```

This restructures **packaging**, not **logic**. Every module in the CURRENT STATE table above
maps to a target location per Master Plan §4.1's file-level table; that table is the
authoritative migration map and is not duplicated here to avoid drift between two copies.

The most consequential target addition is the `api/` package: a thin FastAPI layer whose
handlers translate validated HTTP requests into calls against `application/` use-cases, and
whose only job is DTO-in/DTO-out translation — no business logic is permitted to live in
`api/`. This mirrors the existing GUI controllers, which already separate "what to do" from
"how to paint it" (Master Plan §4.1) — the handlers are structurally the controllers' closest
target-architecture cousin.

## MIGRATION NOTES

- `app/gui/controllers/*` and `app/gui/services/*` are the two directories whose logic must be
  most carefully inventoried before extraction, because they currently mix Qt-specific
  plumbing with genuine application logic. Phase 4B's first task (Master Plan §30.E) is
  exactly this inventory — it has not been performed yet.
- `app/threat_intel/service.py` is **refactored**, not just moved — see
  `08-threat-intelligence-architecture.md` and ADR-007.
- `app/reporting/html_exporter.py` (1,861 LOC) is **redesigned internally** — output content
  preserved, implementation shape changed. See `16-reporting-architecture.md`.
- `app/database/*` and `app/settings/*` are preserved with additive changes only (migration
  runner; secret-store adapter). See `09-database-architecture.md` and
  `17-secrets-configuration-architecture.md`.

## UNKNOWN / REQUIRES VERIFICATION

- Full return-type shapes of `app/services/dashboard_*.py`, `correlation_service.py`,
  `risk_explanation_service.py`, `system_health_service.py` — needed to write precise DTO
  schemas in `docs/contracts/`. **UNKNOWN — VERIFY IN PHASE 4B.**
- Exact extent of Qt-coupling inside `app/gui/controllers/*` and `app/gui/services/*` —
  **UNKNOWN — VERIFY IN PHASE 4B** (Master Plan §1.8, risk #6 in §26/Top-10-risks).
