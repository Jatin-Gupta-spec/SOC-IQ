# SOC-IQ — Phase 4D Part 7 — `enrich_ioc`

**Status: CLASS A — real existing contract found and implemented.**
This is **not** a Phase 4D freeze. `get_threat_intelligence` remains
unimplemented and `GET /events` SSE remains an honest 501.

## 1. Checkpoint verification

`SOC-IQ-Phase4D-Part6-Command-Slice.zip` was extracted fresh into a
clean directory (not trusted from the brief's description) and
verified directly before any edit:

| Item | Result |
|---|---|
| Phase 4C provider abstraction (`app/threat_intel/provider.py`, `virustotal_provider.py`) | Present |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| Eight completed commands (`get_investigation`, `list_investigations`, `analyze_report`, `delete_investigation`, `search_investigations`, `get_iocs`, `save_settings`, `export_report`) | Present — confirmed by direct read of `handlers.py`'s `COMMAND_HANDLERS` dict (8 keys) |
| `docs/phase4/PHASE4D_PART6_IMPLEMENTATION.md` | Present |
| Part 4/5/6 "remaining Phase 4D commands" sections | Present, all three list `enrich_ioc` and `get_threat_intelligence` as unimplemented |
| Baseline tests (`python -m unittest tests.test_application_layer -v`) | **54 passed**, reproduced fresh before this slice touched anything |
| pytest/FastAPI/Pydantic/httpx/uvicorn/PySide6 | Confirmed absent, no network — full pytest/API/GUI verification environment-blocked, exactly as the brief states |

No discrepancy between the supplied checkpoint summary and the actual
archive contents.

## 2. Contract audit — and a discrepancy found in the prior audits

Part 4, Part 5, and Part 6's "remaining commands" sections all state
`enrich_ioc` has **no standalone per-IOC enrichment call site**, citing
`docs/contracts/PHASE4B_COMMAND_INVENTORY.md`'s original Phase-4B-era
finding verbatim. That inventory document is itself explicitly dated
before Phase 4C:

> `enrich_ioc` — no standalone "re-enrich a single IOC" call site was
> found; TI enrichment currently only happens as one step inside
> `analyze_report`...

**This is stale.** Re-auditing the actual current source tree (not the
Phase 4B document) found:

- `ThreatIntelService.lookup_indicator(ioc_type: str, value: str) -> dict[str, Any]`
  (`app/threat_intel/service.py`), added in **Phase 4C, Stage 2**
  (per that method's own docstring and `ThreatIntelService`'s module
  docstring) — a single-IOC lookup method, structurally and
  semantically distinct from the whole-investigation
  `enrich_results`.
- A real, wired GUI caller:
  `app.gui.pages.threat_intel_page._VirusTotalLookupWorker.run` calls
  `self._service.lookup_indicator(self._query_type, self._query)` on a
  background thread for the Threat Intelligence page's interactive
  ad-hoc lookup box — confirmed by direct read of
  `app/gui/pages/threat_intel_page.py`.
- Dedicated, passing tests already exercising this exact method
  end-to-end: `tests/test_threat_intel.py`
  (`test_lookup_indicator_returns_legacy_shape_for_each_type`,
  `..._not_found_is_not_clean`, `..._invalid_type_raises_value_error`,
  `..._propagates_errors_unlike_enrich_results`) and
  `tests/gui/test_threat_intel_page_url.py` (worker-dispatch tests).
- An existing, already-correct entry in `errors.py`'s exception-code
  map for every exception `lookup_indicator` can raise
  (`TI_INVALID_IOC`, `TI_INVALID_API_KEY`, `TI_RATE_LIMITED`,
  `TI_PROVIDER_UNAVAILABLE`, `TI_PROVIDER_ERROR`).

Part 4/5/6 evaluated `enrich_ioc` against the wrong artifact (a
pre-Phase-4C document) instead of the post-Phase-4C source tree their
own checkpoint already contained. This slice does not rewrite those
prior documents (their reasoning was sound *given* the document they
cited); this section records the correction going forward.

### A. Existing service method?

Yes: `ThreatIntelService.lookup_indicator`.

- **Inputs:** `ioc_type: str` (one of `"sha256"`, `"ipv4"`, `"domain"`,
  `"url"` — the same four categories `enrich_results` enriches, per
  `_QUERY_TYPE_TO_IOC_TYPE`), `value: str`.
- **Outputs:** the same VT-shaped, verdict-annotated dict
  `enrich_results` produces per item (e.g. `sha256`/`found`/
  `malicious`/`suspicious`/`harmless`/`undetected`/`verdict`/
  `detection_ratio`/... — shape varies by IOC type, matching
  `VirusTotalClient.lookup_*`'s original per-type shapes exactly).
- **Errors:** raises directly rather than catching (unlike
  `enrich_results`) — `ValueError` for an unsupported `ioc_type`,
  and every `ThreatIntelError` subclass the provider can raise
  (`InvalidHashError`/`InvalidIPError`/`InvalidDomainError`/
  `InvalidURLError`/`InvalidAPIKeyError`/`RateLimitExceededError`/
  `ThreatIntelConnectionError`/`ThreatIntelTimeoutError`/
  `UnexpectedAPIResponseError`).
- **Existing caller:** `_VirusTotalLookupWorker.run`
  (`app/gui/pages/threat_intel_page.py`).

### B. IOC types actually supported

Verified against `_QUERY_TYPE_TO_IOC_TYPE`
(`app/threat_intel/service.py`): exactly `sha256`, `ipv4`, `domain`,
`url` — the same four `VirusTotalProvider._SUPPORTED_IOC_TYPES`
supports. Not inferred from the command's name.

### C. Synchronous or asynchronous?

Synchronous from the caller's point of view.
`ThreatIntelService.lookup_indicator` is a plain sync method (it
internally bridges the provider's `async lookup_raw()` via
`asyncio.run(...)`, exactly as `enrich_results` already does for its
own per-item calls) — no new async system introduced; the command
handler calls it exactly like every other synchronous handler in this
file.

### D. What does the existing caller expect?

Traced `_VirusTotalLookupWorker.run`: it calls
`service.lookup_indicator(query_type, query)` and either emits the
returned dict on success or the stringified exception message on
failure — nothing more elaborate. The command handler mirrors this
exactly: pass `(ioc_type, value)` through, return the dict on success,
let `dispatch()`'s existing generic exception boundary translate a
raised exception. No hypothetical future frontend need was designed
around.

## 3. Decision gate

**CLASS A** — a real existing service operation
(`ThreatIntelService.lookup_indicator`) with a confirmed existing
caller, confirmed inputs/outputs/errors, and confirmed IOC-type
support. Exposing it through the application layer requires no new
business semantics.

## 4. Implementation

### Files changed

- `app/application/dto.py` — added `VALID_IOC_TYPES` constant and
  `EnrichIocRequest` (frozen dataclass, `__post_init__` validation).
- `app/application/handlers.py` — added `ThreatIntelService` import,
  `EnrichIocCommandHandler`, one `dispatch()` branch, one
  `COMMAND_HANDLERS` entry.
- `tests/test_application_layer.py` — added
  `EnrichIocCommandHandlerTests` and
  `EnrichIocDispatchErrorTranslationTests`, plus a minimal local
  `_FakeVirusTotalClient` for dependency injection (same
  `ThreatIntelService(virustotal=...)` pattern
  `tests/test_threat_intel.py` already establishes).

No other file was touched — confirmed by `diff -rq --exclude=__pycache__`
against the fresh Part 6 extraction (§7).

### `EnrichIocRequest`

```python
VALID_IOC_TYPES = ("sha256", "ipv4", "domain", "url")

@dataclass(frozen=True)
class EnrichIocRequest:
    ioc_type: str
    value: str
```

`ioc_type` is restricted to `VALID_IOC_TYPES` at the DTO boundary —
the same validate-at-the-DTO pattern `ExportReportRequest.export_format`
already uses. `lookup_indicator` itself raises a bare `ValueError` for
an unsupported type; catching the bad type here instead means the
failure surfaces as the same `INVALID_COMMAND_PAYLOAD` shape every
other malformed-input rejection uses, rather than a one-off
untranslated `ValueError`. `value` is checked only for being a
non-empty string — per-type format validation (hash shape, IP shape,
etc.) is not duplicated from `threat_intel_page.py`'s regexes; it
already exists once, inside the provider, and is already mapped to
`TI_INVALID_IOC`.

### `EnrichIocCommandHandler`

```python
class EnrichIocCommandHandler:
    def __init__(self, service: ThreatIntelService | None = None) -> None:
        self._service = service if service is not None else ThreatIntelService()

    def handle(self, request: EnrichIocRequest) -> dict[str, Any]:
        result = self._service.lookup_indicator(request.ioc_type, request.value)
        return ok(result)
```

Follows the exact constructor-injection / thin-translation shape every
other handler in this file uses. Unlike most other handlers, it has no
local `try`/`except`: `lookup_indicator` deliberately propagates every
failure as a raised exception (its own docstring: "Unlike
`enrich_results`, this does not catch and count errors ... meant for
interactive, single-indicator callers"), so translation is left to
`dispatch()`'s existing generic exception boundary — the same
boundary `GetInvestigationCommandHandler`/`ListInvestigationsCommandHandler`/etc.
already rely on for their own untranslated domain exceptions.

### Dispatch / registration

One new `dispatch()` branch (`if name == "enrich_ioc":`) and one new
`COMMAND_HANDLERS` entry, matching the pattern of every prior command
exactly. `COMMAND_HANDLERS` now has 9 keys (confirmed directly by
`ast`-parsing the assignment, not by eyeballing).

## 5. Error translation

No new error category introduced. Every exception
`ThreatIntelService.lookup_indicator` can raise already has an entry
in `errors.py`'s `_EXCEPTION_CODE_MAP`:

| Exception | Code |
|---|---|
| `InvalidHashError` / `InvalidIPError` / `InvalidDomainError` / `InvalidURLError` | `TI_INVALID_IOC` |
| `InvalidAPIKeyError` | `TI_INVALID_API_KEY` |
| `RateLimitExceededError` | `TI_RATE_LIMITED` |
| `ThreatIntelConnectionError` / `ThreatIntelTimeoutError` | `TI_PROVIDER_UNAVAILABLE` |
| `UnexpectedAPIResponseError` | `TI_PROVIDER_ERROR` |

A bare `ValueError` for an unsupported `ioc_type` cannot reach
`lookup_indicator` in practice, since `EnrichIocRequest.__post_init__`
already rejects any `ioc_type` outside `VALID_IOC_TYPES` before the
handler is ever called — mirroring `ExportReportRequest`'s own
unreachable-`else`-branch precedent for `export_format`.

## 6. Tests

`EnrichIocCommandHandlerTests` (handler-level, `_FakeVirusTotalClient`
injection):
- valid sha256 enrichment returns the expected `ok()` envelope and
  verdict/detection_ratio.
- request DTO rejects an unsupported `ioc_type`.
- request DTO rejects a blank `value`.
- dispatched via command name (`dispatch("enrich_ioc", ...)`).

`EnrichIocDispatchErrorTranslationTests` (dispatch-level, exercising
`lookup_indicator`'s real raise-don't-catch behavior through the fake
client):
- `InvalidHashError` → `TI_INVALID_IOC`.
- `RateLimitExceededError` → `TI_RATE_LIMITED`.
- `InvalidAPIKeyError` → `TI_INVALID_API_KEY`.

### Tests actually executed

```
python -m unittest tests.test_application_layer -v
```
→ **62/62 passed** (54 baseline + 8 new), reproduced fresh, no
failures or errors.

### Environment-blocked tests

pytest/FastAPI/httpx/uvicorn/PySide6 remain absent and there is no
network access in this sandbox — `tests/test_threat_intel.py` (uses
pytest), `tests/gui/*` (needs PySide6), and any `app/api/*` HTTP-level
test all remain unexecuted, exactly as every prior Part in this
sequence has documented. No dependency declaration was modified to
work around this.

## 7. Adversarial audit

| Check | Result |
|---|---|
| Direct `VirusTotalClient` import in `app/application/` | None — grepped, zero hits |
| Qt/PySide6 imports in `app/application/` (new) | None — only the pre-existing, untouched docstring mention in `__init__.py` |
| FastAPI imports in handlers/DTOs | None |
| Tauri/Rust imports | None |
| Duplicated threat-intelligence logic | None — handler calls `lookup_indicator` as-is, no reimplementation |
| Bypassing `ThreatIntelProvider` | No — `EnrichIocCommandHandler` only calls `ThreatIntelService`, which is already the sole caller of the provider abstraction |
| Duplicated dispatch registration | No — exactly one `if name ==` branch, one `COMMAND_HANDLERS` entry |
| Business logic in `app/api/app.py` | Untouched — confirmed by diff (§ below) |
| New global state | None |
| Changed semantics of existing commands | None — `diff -rq --exclude=__pycache__` against the fresh Part 6 extraction shows exactly three files changed: `app/application/dto.py`, `app/application/handlers.py`, `tests/test_application_layer.py`; all other files (including `app/api/app.py`, `app/threat_intel/*`, `src-tauri/`, `frontend/src/`, `app/reporting/`, `app/database/`, `app/settings/`, `app/gui/`, `app/application/errors.py`, `app/application/events.py`, `app/application/responses.py`) byte-identical |
| Secret/API-key leakage | None — `lookup_indicator`'s response never includes the API key itself; unchanged from before |
| Accidental change to Phase 4C | None — `app/threat_intel/*` byte-identical |
| Accidental change to previous commands | None — the 8 previously-completed command handlers/dispatch branches/registrations are textually unchanged; their test classes still pass unmodified |

**PASS.**

## 8. Documentation

Created `docs/phase4/PHASE4D_PART7_IMPLEMENTATION.md` (this file). No
freeze document created. Phase 4D not claimed complete. No historical
document (Part 4/5/6 docs) rewritten — the stale-audit discrepancy is
recorded here going forward rather than silently corrected in place.

## 9. Full regression (where possible)

```
python -m unittest tests.test_application_layer -v
```
→ 62/62 passed.

Syntax/compile check:

```
python -m py_compile app/application/dto.py app/application/handlers.py tests/test_application_layer.py
```
→ clean, no errors.

pytest/FastAPI/PySide6-dependent suites remain environment-blocked, as
stated in §6.

## 10. Phase status

**PHASE 4D NOT FROZEN.**

Remaining, verified from the repository:

- `get_threat_intelligence` — still real but still blocked exactly as
  Part 4/5/6 documented: its natural backing
  (`app.gui.services.ioc_detail_context.build_investigation_threat_intel_overview`)
  still lives under `app/gui/`, still takes GUI-adjacent inputs
  (`api_key_configured`), and still depends on
  `app.gui.utils.ioc_significance`. Confirmed unchanged by this
  slice's diff (§7) — not re-audited further here, since this Part's
  scope was `enrich_ioc` only.
- `GET /events` SSE — remains an honest 501, untouched by this slice.

## 11. Known limitations

- `EnrichIocCommandHandler` returns whatever shape
  `lookup_indicator` returns for the given `ioc_type` — that shape is
  not uniform across types (e.g. the key is `sha256` for a hash lookup,
  `ip` for an IPv4 lookup, per `VirusTotalClient`'s original per-type
  dict shapes). This is not a new inconsistency introduced by this
  slice; it is `lookup_indicator`'s existing, tested, GUI-relied-upon
  contract, preserved unchanged rather than normalized into a new
  uniform shape (which would be inventing behavior, not extracting
  it).
- Like the GUI's own worker, this command does not call
  `ThreatIntelService.is_configured()` before attempting a lookup — an
  unconfigured provider surfaces as `InvalidAPIKeyError` →
  `TI_INVALID_API_KEY` from the lookup attempt itself, exactly
  matching `_VirusTotalLookupWorker.run`'s existing behavior (it also
  does not pre-check `is_configured()`; `ThreatIntelPage._init_vt_client`
  only uses it for a GUI-level enable/disable decision, not a
  pre-flight guard around the lookup call itself).
