# SOC-IQ — File Structure (current + target)

This document answers "where should new code go?" It does not repeat every line of the
master plan — see `PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` §4.1, §25, §27 for
the source material this is built from.

## Current tree, annotated with target classification

Classification key: **PRESERVE** (move/keep as-is) · **ADAPT** (keep logic, change shape) ·
**REFACTOR** (behavior-preserving internal redesign) · **REDESIGN** (same responsibility,
new implementation) · **NEW** (does not exist yet) · **REMOVE** (retired, no target home).

```
app/
├── cli.py                        PRESERVE  → backend/app/cli.py, re-pointed at application/
├── main.py, initializer.py       PRESERVE (bootstrap) — target home not yet finalized; confirm in source before moving
├── extractor.py                  PRESERVE  → backend/app/domain/extraction/
├── analyzer.py                   PRESERVE  → backend/app/domain/extraction/ (or domain/analysis/ — verify boundary before moving; not finalized in master plan)
├── scoring/                      PRESERVE  → backend/app/domain/scoring/
├── threat_intel/
│   ├── service.py                REFACTOR  → backend/app/application/threat_intel_orchestrator.py (depends on ThreatIntelProvider protocol, NOT YET IMPLEMENTED)
│   └── virustotal.py             ADAPT     → backend/app/providers/virustotal_provider.py (internal HTTP logic preserved)
├── database/
│   ├── repository.py             PRESERVE + ADAPT → backend/app/repositories/sqlite/ (+ introduce migration runner, NOT YET IMPLEMENTED)
│   ├── connection.py, models.py, service.py   same target, same classification
├── reporting/
│   ├── json/csv/markdown/pdf exporters, builder.py, service.py   PRESERVE → backend/app/reporting/*
│   └── html_exporter.py (1,861 LOC)   REDESIGN → template-driven internals, SAME OUTPUT CONTENT (rule #21)
├── settings/                     ADAPT → backend/app/settings/* (+ secret-store-backed key storage, NOT YET IMPLEMENTED; keep existing redacted __repr__)
├── services/                     PRESERVE (logic) → backend/app/application/*_service.py, exposed via command handlers instead of called directly by Qt controllers
├── application/  (NEW, Phase 4D) handlers.py/dto.py/events.py/responses.py/errors.py — ALREADY THE TARGET SHAPE, just not yet under backend/
├── api/          (NEW, Phase 4D) app.py (FastAPI) — ALREADY THE TARGET SHAPE, just not yet under backend/
├── exceptions.py, exporters.py, display.py, logger.py, config.py   PRESERVE (target subpackage not finalized — confirm before moving)
└── gui/                           REMOVE (all PySide6) — see breakdown below
    ├── controllers/*.py           REFACTOR → backend/app/application/* (command handlers) — these already separate intent from Qt painting, per master plan §4.1
    ├── services/*.py              REFACTOR → same as controllers
    ├── events/application_events.py, event_bus.py   REMOVE → superseded by unified event model (docs/contracts/event-model.md), NOT a rename/merge
    ├── models/ (Qt table/proxy models)   REMOVE (Qt-specific)
    ├── pages/*.py                  REMOVE → replaced by React features (frontend/src/features/*)
    ├── widgets/*.py                REMOVE (Qt code) — concepts carry forward as React components (dashboard KPIs, risk gauge, IOC distribution, etc.)
    ├── components/*.py             REMOVE (Qt code); note the panel.py/section_header.py duplicate pair under components/layout/ vs widgets/ — REMOVE BOTH, no need to pick a winner between two retiring implementations (master plan §27)
    ├── design/tokens/*             PRESERVE (VALUES only) → ported to frontend/src/styles/tokens/ as TS/CSS; PySide6 token-loading code itself is REMOVE
    ├── styles/theme.py              REMOVE (Qt-specific) — dark SOC theme concept carries forward via design tokens
    └── workers/analysis_worker.py  REMOVE (Qt-specific) — equivalent async execution lives in the FastAPI command handler

tests/                             PRESERVE — must stay green through every phase (rule #22)
docs/                              PRESERVE + this bible layer added on top
samples/                           PRESERVE — manual testing / demo fixtures
```

## Target tree (new directories, not yet created — master plan §25)

```
frontend/                NEW
├── src/
│   ├── app/              App.tsx, router.tsx, providers/ — owns bootstrap only, no business logic, no direct persistence/network beyond the sidecar origin
│   ├── features/         one folder per feature (dashboard, analyze, investigations, ioc-explorer, threat-intel, risk, history, reports, settings)
│   │   └── <feature>/    components/, hooks/, models/, view-models/, index.ts — owns UI + view-model shaping only; may import shared/*; must NOT import another feature's internals directly
│   ├── shared/            api/ (typed command client), events/ (SSE subscriber), state/ (client store), components/, hooks/, utilities/, types/
│   └── styles/             tokens/ (ported values from app/gui/design/tokens), globals.css, motion.css
└── (build config — not specified yet; confirm before assuming a bundler choice)

src-tauri/                NEW — Rust shell: window lifecycle, capability manifest, sidecar process supervision (spawn/health-check/kill), secret-store glue, native file dialogs/notifications. Owns NO business logic (rule #2).

backend/                  target home for current app/ (see tree above); tests/ moves alongside it
scripts/                  NEW — build/package/lockfile-refresh scripts, none exist yet
```

## Import-direction rule (applies to both current and target code)

```
frontend  →  Tauri capability boundary  →  Python API/application  →  domain services  →  repositories  →  SQLite
Python domain  →  provider interfaces  →  provider adapters
```

Never the reverse, and never a layer skip in the wrong direction — see the forbidden list in
`PROJECT_CONSTITUTION.md` §7 and `NON_NEGOTIABLE_RULES.md`.

**Note on completeness:** this document maps every top-level module and every `app/gui/*`
subpackage, matching the master plan's own "representative, not exhaustive" file-level
mapping (§4.1). It does not enumerate every individual `.py` file inside
`app/gui/widgets/`, `app/gui/pages/`, etc. — those are uniformly REMOVE/REDESIGN-as-React-
component per the rule already stated for their parent directory. If you need a specific
file's disposition and it isn't listed here, check `docs/migration/PHASE4B_CONTROLLER_SERVICE_INVENTORY.md`
and `PHASE4B_LOGIC_PRESERVATION_MATRIX.md` before guessing.
