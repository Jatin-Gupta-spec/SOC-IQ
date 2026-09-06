# SOC-IQ — Phase 4D Part 8 — `get_threat_intelligence`

**Status: CLASS A — real existing contract found and implemented, as
a deliberately narrower slice than the richer GUI overview.**
This is **not** a Phase 4D freeze. `GET /events` SSE remains an
honest 501 and is explicitly out of scope for this Part.

## 0. Reconciliation addendum (independent re-audit)

This document was produced in an earlier run. A later run was asked to
treat this archive as a checkpoint arriving *ahead* of the brief it was
given (the brief expected a pre-`get_threat_intelligence` Part 7 state;
the archive already contained this implementation, this document, and
three Phase 4E Part 1 docs beyond Phase 4D). Rather than re-implement or
roll anything back, that run independently re-verified every claim below
against the actual source and tests, without trusting this document's
word for any of it. Result: **VERIFIED — no factual errors found**, with
one caveat this document could not honestly claim on its own:

- Every source claim in §2–§7 below (contract path, handler body, DTO
  validation, dispatch/`COMMAND_HANDLERS` registration count, absence of
  Qt/FastAPI/Tauri/`VirusTotalClient`/`app.gui` imports in
  `app/application/`, error-code reuse, envelope shape, the four
  `GetThreatIntelligenceCommandHandlerTests` plus the one
  `DispatchErrorTranslationTests` case) was independently re-read from
  source this run and matches exactly.
- `python -m unittest tests.test_application_layer -v` was independently
  re-run this run: **67/67 passed**, reproducing the number claimed in
  §6/§9 exactly.
- `python -m unittest discover -s tests -p "test_*.py"` was additionally
  run for the broadest available regression signal: **94 tests
  discovered, 67 passed, 27 errors** — every one of the 27 is a
  `ModuleNotFoundError` for `pytest`/`fastapi`/`PySide6` at import time
  (confirmed individually), not an assertion failure. This matches the
  environment-blocked state this document already declared and surfaces
  no regression.
- **One claim below could not be independently reproduced**: §4's "no
  other file was touched — confirmed by `diff -rq --exclude=__pycache__`
  against the fresh Part 7 extraction." The Part 7 archive was not
  available to this later run for a direct diff, so that specific claim
  is carried forward as inherited/unverified rather than re-confirmed.
  Everything else in this document was independently checked against the
  present source tree directly, which is sufficient to confirm the
  *current* implementation is correct and boundary-clean regardless of
  the historical diff.

No source files were changed by this reconciliation. Only this addendum
was added.

## 1. Checkpoint verification

`SOC-IQ-Phase4D-Part7-Command-Slice.zip` was extracted fresh into a
clean directory before any edit:

| Item | Result |
|---|---|
| Phase 4C provider abstraction | Present |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| Nine implemented commands (incl. `enrich_ioc`) | Present — confirmed by direct read of `handlers.py`'s `COMMAND_HANDLERS` dict (9 keys) |
| `docs/phase4/PHASE4D_PART7_IMPLEMENTATION.md` | Present |
| Baseline tests (`python -m unittest tests.test_application_layer -v`) | **62 passed**, reproduced fresh before this slice touched anything, matching the brief's expected number |
| pytest/FastAPI/Pydantic/httpx/uvicorn/PySide6 | Confirmed absent, no network |

No discrepancy found between the brief's description and the actual
archive.

## 2. Current-source contract audit

Traced `get_threat_intelligence` through the current repository rather
than trusting any prior document, per the brief's explicit instruction
(and Part 7's own precedent — a prior audit had already turned out to
be stale once).

### What exists

- **`Investigation.threat_intelligence`** (`app/database/models.py`) —
  a persisted field on the domain model, populated at analyze-time by
  `ThreatIntelService.enrich_results()` and written/read by
  `app/database/repository.py`. Not GUI-coupled in any way — it is a
  plain domain-model field, already round-tripped through SQLite.
- **`InvestigationSummaryDTO`'s own docstring** (`app/application/dto.py`,
  written in an earlier Part) states outright: *"Deliberately omits
  `iocs` / `threat_intelligence` ... Full IOC/TI detail belongs to the
  not-yet-implemented `get_iocs` / `get_threat_intelligence`
  commands."* This is source-verified, first-party confirmation of
  the command's minimal intended shape — the same reservation that
  was already honored for `get_iocs` in Part 4.
- **`app.gui.services.ioc_detail_context.build_investigation_threat_intel_overview(investigation, api_key_configured)`**
  — a richer, GUI-consumed summary (TI_STATE_*/message/short_label)
  built on top of the same `investigation.threat_intelligence` field.
  Re-read directly this Part: it is genuinely Qt-free (imports only
  `app.database.models.Investigation` at the point it's called; the
  sibling function `build_ioc_detail_context` in the same module also
  imports `app.gui.utils.ioc_significance`, which is itself Qt-free —
  it imports only `app.scoring.engine.RiskScoringEngine`). Prior Parts'
  claim that this dependency chain is "GUI-coupled" was about Qt
  specifically and does not hold up under a fresh read: nothing in
  either module touches PySide6/Qt.
- **`docs/contracts/PHASE4B_QUERY_INVENTORY.md`** independently
  classifies `build_investigation_threat_intel_overview` as *"application
  query, currently mis-located"* — i.e., the codebase's own prior
  audit already recognized this function conceptually belongs in the
  application layer, just physically sits under `app/gui/`.

### The real blocker (re-confirmed, not just re-asserted)

Even though `build_investigation_threat_intel_overview` has no Qt
dependency, importing it into `app/application/handlers.py` would
still be a literal `from app.gui... import ...` statement in that
file. That specific line is not hypothetical: `handlers.py` already
states this as a live, deliberate architectural rule, not a
speculative one —
`SearchInvestigationsCommandHandler`'s own docstring (written in an
earlier Part, unrelated to this one): *"This handler calls
InvestigationService directly rather than importing
HistoryController, so app.application never depends on app.gui — the
same dependency-direction rule every other handler in this file
already follows."* Grepping `app/application/` for `^from app\.gui`
confirms zero existing import statements today. Adding one here would
be the first violation of an invariant this file has held everywhere
else, not merely following a stale worry from an old document.

So the choice is not "Qt-coupled vs not" — it's "does exposing the
richer overview require a first-ever `app.gui` import into
`app.application`, or reimplementing that function's logic verbatim
(duplicating an implementation that already exists, which Part 5
already rejected as invented behavior for this exact function)." Both
options are excluded by this brief's own rules (§6, §"Do not
redesign").

### A. Existing service-level operation for "get threat intelligence"?

Yes, in the minimal sense `InvestigationSummaryDTO`'s docstring
already reserved: `InvestigationService.get_by_id()` (already used by
five other handlers in this file) returns an `Investigation` whose
`.threat_intelligence` field is exactly the TI result the command
needs to expose. No, in the richer sense of the GUI's computed
overview — that operation exists, but not at an importable boundary
this command can reach without violating an existing, deliberate rule.

### B. What does the GUI actually consume?

Traced: GUI page → (not directly relevant here, since no GUI worker
performs this fetch — the GUI reads `investigation.threat_intelligence`
directly off the domain object it already has in memory after
`analyze_report`/`get_investigation`, then calls
`build_investigation_threat_intel_overview` locally to render it).
There is no GUI *worker* backing this command the way
`_VirusTotalLookupWorker` backed `enrich_ioc` — this is a stored-field
read, not a live network call, so "the GUI worker" framing in §6 of
this brief doesn't apply the same way it did for `enrich_ioc`.

### C. Investigation-level or IOC-level?

Investigation-level, and distinct from the already-implemented
`enrich_ioc`: `enrich_ioc` performs a new, live, single-IOC lookup;
`get_threat_intelligence` fetches the already-persisted TI results for
a whole investigation. The persisted dict returned here already
contains per-IOC-type breakdowns (`hashes`/`ips`/`domains`/`urls`,
each a list of per-indicator VT-shaped records) nested inside it —
satisfying "for an investigation/IOC" from `command-model.md` without
requiring a second, separate per-IOC query path to be invented.

### D. Does a persisted model already exist?

Yes — `Investigation.threat_intelligence`, confirmed directly in
`app/database/models.py` and `app/database/repository.py`. No new
persistence was created.

## 3. Classification

**CLASS A**, scoped narrowly: the raw, already-persisted
`Investigation.threat_intelligence` field is a real, existing,
extractable operation, reachable without violating any existing
architectural rule and without inventing new business semantics.

The richer GUI-computed overview is explicitly **not** part of this
slice — exposing it would require either the first `app.gui` import
into `app/application` (forbidden by this brief and by the file's own
stated invariant) or reimplementing its state-computation logic
(forbidden as invented/duplicated behavior). That remains a real,
open architectural question (properly a relocation decision — move
`build_investigation_threat_intel_overview` out of `app/gui/services/`
into an application-layer module — which is out of this Part's scope
to decide unilaterally) and is recorded under Known Limitations
rather than silently solved.

## 4. Implementation

### Files changed

- `app/application/dto.py` — added `GetThreatIntelligenceRequest`
  (frozen dataclass, identical validation shape to `GetIocsRequest`).
- `app/application/handlers.py` — added `GetThreatIntelligenceRequest`
  import, `GetThreatIntelligenceCommandHandler`, one `dispatch()`
  branch, one `COMMAND_HANDLERS` entry.
- `tests/test_application_layer.py` — added
  `GetThreatIntelligenceCommandHandlerTests` and one dispatch-level
  error-translation test.

No other file was touched — confirmed by `diff -rq --exclude=__pycache__`
against the fresh Part 7 extraction (§7).

### `GetThreatIntelligenceRequest`

```python
@dataclass(frozen=True)
class GetThreatIntelligenceRequest:
    investigation_id: int
```

Validation is byte-for-byte identical to `GetIocsRequest`/
`GetInvestigationRequest` — same positive-int constraint, same
`Investigation` row being looked up.

### `GetThreatIntelligenceCommandHandler`

```python
class GetThreatIntelligenceCommandHandler:
    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: GetThreatIntelligenceRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        return ok(
            {
                "investigation_id": investigation.investigation_id,
                "threat_intelligence": investigation.threat_intelligence,
            }
        )
```

Structurally identical to `GetIocsCommandHandler` — same lookup, same
not-found handling, same envelope shape — with `threat_intelligence`
in place of `iocs`.

### Dispatch / registration

One new `dispatch()` branch (`if name == "get_threat_intelligence":`)
and one new `COMMAND_HANDLERS` entry. `COMMAND_HANDLERS` now has 10
keys, confirmed by `ast`-parsing the assignment:

```
['get_investigation', 'get_iocs', 'get_threat_intelligence',
 'save_settings', 'list_investigations', 'delete_investigation',
 'search_investigations', 'analyze_report', 'export_report',
 'enrich_ioc']
```

## 5. Error handling

No new error path introduced. `InvestigationService.get_by_id` is the
same call `GetInvestigationCommandHandler`/`GetIocsCommandHandler`
already make; the not-found case reuses `INVESTIGATION_NOT_FOUND`
exactly, and any unexpected service exception (e.g. `DatabaseError`)
is translated by `dispatch()`'s existing generic boundary via
`code_for_exception`, the same as every other handler with no local
`try`/`except` of its own. No provider-level TI error states
(no-api-key, rate-limited, etc.) apply here — those belong to
`enrich_ioc`'s live-lookup path, not this stored-field read.

## 6. Tests

`GetThreatIntelligenceCommandHandlerTests` (mirrors
`GetIocsCommandHandlerTests` exactly):
- returns the stored `threat_intelligence` dict for an existing
  investigation, unmodified.
- returns `INVESTIGATION_NOT_FOUND` for a missing investigation.
- request DTO rejects a non-positive `investigation_id`.
- dispatched via command name.

`DispatchErrorTranslationTests` — added
`test_get_threat_intelligence_translates_unexpected_service_exception`,
mirroring the existing `get_iocs` case.

### Tests actually executed

```
python -m unittest tests.test_application_layer -v
```
→ **67/67 passed** (62 baseline + 5 new), reproduced fresh, no
failures or errors.

### Environment-blocked tests

pytest/FastAPI/httpx/uvicorn/PySide6 remain absent and there is no
network access — `tests/gui/*` and any `app/api/*` HTTP-level test
remain unexecuted, exactly as every prior Part has documented. No
dependency declaration was modified to work around this.

## 7. Adversarial audit

| Check | Result |
|---|---|
| `app.gui` import statements in `app/application/` | None — grepped for `^from app\.gui`, zero hits (only pre-existing docstring mentions, unchanged) |
| Qt/PySide6 imports | None |
| FastAPI imports | None |
| Tauri/Rust imports | None |
| Direct `VirusTotalClient` dependency | None |
| Duplicate TI logic | None — no reimplementation of `build_investigation_threat_intel_overview`'s state-computation logic |
| Duplicate command registration | No — exactly one `if name ==` branch, one `COMMAND_HANDLERS` entry |
| Business logic in `app/api/app.py` | Untouched — confirmed by diff |
| Secret/API-key leakage | None — the persisted `threat_intelligence` dict never contains the API key itself |
| Changes to Phase 4C | None — `app/threat_intel/*` byte-identical |
| Changes to previous commands | None — `diff -rq --exclude=__pycache__` against the fresh Part 7 extraction shows exactly three files changed: `app/application/dto.py`, `app/application/handlers.py`, `tests/test_application_layer.py`; every other file (including `app/api/app.py`, `app/threat_intel/*`, `app/gui/*`, `src-tauri/`, `frontend/src/`, `app/reporting/`, `app/database/`, `app/settings/`, `app/application/errors.py`, `app/application/events.py`, `app/application/responses.py`) byte-identical |
| Changes to Rust/Tauri/frontend | None |
| Changes to unrelated services | None |

**PASS.**

## 8. Documentation

Created `docs/phase4/PHASE4D_PART8_IMPLEMENTATION.md` (this file). No
freeze document created. Phase 4D not claimed complete. Prior Parts'
documents (4/5) are not rewritten — their "GUI-coupled, deferred"
conclusion about the *richer overview* was reasonable and remains true
for that specific function; what changed this Part is scoping the
command to the raw persisted field instead, which those documents
never separately considered.

## 9. Full regression (where possible)

```
python -m unittest tests.test_application_layer -v
```
→ 67/67 passed.

```
python -m py_compile app/application/dto.py app/application/handlers.py tests/test_application_layer.py
```
→ clean, no errors.

pytest/FastAPI/PySide6-dependent suites remain environment-blocked, as
stated in §6.

## 10. Phase status

**PHASE 4D NOT FROZEN.**

Remaining, verified from the repository:

- `GET /events` SSE — remains an honest 501, untouched by this slice,
  as explicitly required.

No other named command remains unimplemented. All ten commands in
`docs/contracts/command-model.md`'s illustrative catalog now have a
`COMMAND_HANDLERS` entry, though `get_threat_intelligence` is
intentionally the minimal raw-field slice described above, not the
GUI's full computed overview.

## 11. Known limitations

- `GetThreatIntelligenceCommandHandler` returns the raw, already-
  persisted `Investigation.threat_intelligence` dict exactly as
  `ThreatIntelService.enrich_results()` produced and `analyze_report`
  stored it (`status`/`coverage`/`hashes`/`ips`/`domains`/`urls`). It
  does **not** return the richer, human-readable TI_STATE_*/message/
  short_label overview that
  `app.gui.services.ioc_detail_context.build_investigation_threat_intel_overview`
  computes for the GUI's Investigation Summary and Threat Intelligence
  tab. Producing that overview through this command would require an
  architectural decision this Part is not scoped to make alone:
  relocating `build_investigation_threat_intel_overview` (and its
  Qt-free dependency `app.gui.utils.ioc_significance`) out of
  `app/gui/` into an application-layer module, exactly as
  `docs/contracts/PHASE4B_QUERY_INVENTORY.md` already flags them as
  "mis-located." Until that relocation happens, a caller wanting the
  friendlier overview must compute it client-side from this command's
  raw data, the same way the current GUI already does.
- No investigation-level "was an IOC key configured" flag is included
  in the response (unlike the GUI overview's `api_key_configured`
  parameter) — that value is not stored on `Investigation` and is a
  settings-layer concern (`save_settings`/`SettingsService`), not part
  of the persisted TI result this command exposes.
