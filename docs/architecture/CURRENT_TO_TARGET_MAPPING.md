# SOC-IQ — Current → Target File Mapping

This is the file-by-file companion to `FILE_STRUCTURE.md`. Source: master plan §4.1 and
§27, cross-checked against the actual repository listing this session. Classifications not
already pinned down by an existing document are marked UNKNOWN rather than guessed.

| Current file/dir | Target location | Action | Confidence |
|---|---|---|---|
| `app/extractor.py` | `backend/app/domain/extraction/` | PRESERVE | CONFIRMED (master plan §4.1) |
| `app/analyzer.py` | `backend/app/domain/extraction/` or `domain/analysis/` | PRESERVE | LIKELY — exact subpackage boundary not pinned down in source docs; confirm before moving |
| `app/scoring/engine.py`, `scoring/models.py` | `backend/app/domain/scoring/` | PRESERVE | CONFIRMED |
| `app/threat_intel/service.py` | `backend/app/application/threat_intel_orchestrator.py` | REFACTOR (depend on `ThreatIntelProvider` protocol) | CONFIRMED design / NOT YET IMPLEMENTED |
| `app/threat_intel/virustotal.py` | `backend/app/providers/virustotal_provider.py` | ADAPT (wrap behind new interface, internals preserved) | CONFIRMED design / NOT YET IMPLEMENTED |
| `app/database/repository.py`, `connection.py`, `models.py`, `service.py` | `backend/app/repositories/sqlite/` | PRESERVE + introduce migration runner | CONFIRMED design / migration runner NOT YET IMPLEMENTED |
| `app/reporting/{json,csv,markdown,pdf}_exporter.py`, `builder.py`, `service.py` | `backend/app/reporting/*` | PRESERVE | CONFIRMED |
| `app/reporting/html_exporter.py` | `backend/app/reporting/html_exporter.py` | REDESIGN internals (template-driven), same output content | CONFIRMED design / NOT YET IMPLEMENTED |
| `app/settings/{models,repository,service}.py` | `backend/app/settings/*` | ADAPT (+ secret-store-backed key) | CONFIRMED design / secret store NOT YET IMPLEMENTED |
| `app/services/*.py` (dashboard/correlation/risk-explanation/system-health) | `backend/app/application/*_service.py` | PRESERVE logic, exposed via command handlers | CONFIRMED, inventoried file-by-file in `docs/migration/PHASE4B_CONTROLLER_SERVICE_INVENTORY.md` |
| `app/gui/controllers/*.py` (3 files) | `backend/app/application/*` (command handlers) | REFACTOR | CONFIRMED, inventoried in Phase 4B docs |
| `app/gui/services/*.py` (3 files) | `backend/app/application/*` | REFACTOR | CONFIRMED, inventoried in Phase 4B docs |
| `app/gui/events/application_events.py`, `event_bus.py` | *(none)* | REMOVE, superseded by `docs/contracts/event-model.md` | CONFIRMED |
| `app/gui/pages/*.py` | `frontend/src/features/*` | REMOVE (Qt) / REDESIGN (concept as React feature) | CONFIRMED at directory level; per-page component breakdown not yet written |
| `app/gui/widgets/*.py` | `frontend/src/features/*/components/` or `shared/components/` | REMOVE (Qt) / REDESIGN (concept) | CONFIRMED at directory level |
| `app/gui/components/layout/panel.py` + `app/gui/widgets/panel.py` (duplicate pair) | *(none)* | REMOVE both | CONFIRMED — explicitly called out as not worth resolving since both are retiring |
| `app/gui/design/tokens/*` | `frontend/src/styles/tokens/` | PRESERVE (values only) / REDESIGN (implementation, Qt → TS/CSS) | CONFIRMED |
| `app/gui/styles/theme.py` | *(none)* | REMOVE — dark SOC theme concept carries forward via tokens | CONFIRMED |
| `app/gui/workers/analysis_worker.py` | *(none)* | REMOVE — equivalent async execution lives in the FastAPI command handler | CONFIRMED |
| `app/cli.py` | `backend/app/cli.py` | PRESERVE, re-pointed at `application/` layer | CONFIRMED |
| `app/application/*` (handlers.py, dto.py, events.py, responses.py, errors.py) | `backend/app/application/*` | ALREADY TARGET SHAPE — just needs to move under `backend/` when that directory is created | CONFIRMED, exists in source today (Phase 4D) |
| `app/api/app.py` | `backend/app/api/app.py` | ALREADY TARGET SHAPE | CONFIRMED, exists in source today (Phase 4D); SSE route incomplete |
| `tests/*.py`, `tests/gui/*.py` | `backend/tests/` (non-GUI) — GUI test suite's target home is UNKNOWN, since the code it tests is being removed | PRESERVE (non-GUI) | Non-GUI: CONFIRMED. `tests/gui/`: UNKNOWN — presumably retired alongside `app/gui/`, but no document states this explicitly; do not delete it without confirming with a human or a future phase document first. |
| `app/main.py`, `app/initializer.py`, `app/config.py`, `app/exceptions.py`, `app/exporters.py`, `app/display.py`, `app/logger.py` | UNKNOWN exact subpackage | PRESERVE (logic) | LIKELY PRESERVE, exact target path not pinned down in any source document reviewed this session — confirm before moving, don't assume a path |

## Explicitly not mapped here

Individual files inside `app/gui/pages/`, `app/gui/widgets/`, `app/gui/components/` beyond
the ones called out above are not enumerated 1:1 against a specific target React component —
no source document goes that granular yet (that level of detail belongs to Phase 4F/4G/4H
when the React frontend is actually built). Treat "a page/widget becomes a React feature
concept, not a 1:1 port" as the rule, and consult
`docs/architecture/13-frontend-information-architecture.md` for the intended information
architecture those concepts should land in.
