# Phase 4D — Reconciliation & Adversarial Audit

**Status:** Audit only. No source, test, or documentation file outside this
report was modified during this pass.
**Starting checkpoint:** archive uploaded as `SOC-IQ-Phase4C-FINAL-FROZEN.zip`.
**Finding of the prior session (unchanged, re-confirmed here):** this archive is
not a clean Phase 4C freeze — it already contains a working Phase 4C provider
abstraction and a partial Phase 4D application/API layer, with no
`PHASE4C_FREEZE.md` anywhere in the archive to explain why.

---

## 1. Executive verdict

- **Phase 4C: COMPLETE in source**, not merely designed. `ThreatIntelProvider`
  and `VirusTotalProvider` exist and `ThreatIntelService` is migrated onto the
  abstraction (§12). This directly contradicts `PROJECT_CONSTITUTION.md` §4/§16
  and `NON_NEGOTIABLE_RULES.md` rule 16, both of which state the abstraction is
  "design-only" / "not yet implemented in source."
- **Phase 4D: PARTIAL, IMPLEMENTED / VERIFIED for the slice it covers.** 3 of the
  ~9 commands named across the design docs are implemented, tested, and pass
  fresh execution (§3, §9). The remaining commands are genuinely absent — no
  code, no stubs — which matches what the docs say on that one specific point.
- **The archive's own documentation is internally inconsistent and in places
  contradicts the source it describes.** `PROJECT_CONSTITUTION.md` is dated
  2026-08-22 against a *different* snapshot name
  (`SOC-IQ-Phase4D-COMPLETE-PROJECT.zip`) than the one actually uploaded here.
  Three different test-count baselines appear across the docs, none matching a
  fresh run (§10).
- **No architectural defects were found in the code itself.** Every coupling
  check in §8 came back clean. The problems found are entirely in
  documentation/process (stale claims, missing freeze report), not in the
  `app/application` / `app/api` implementation.
- **Recommended next action:** treat the existing `app/application`/`app/api`
  work as real, keep it, and correct the documentation drift before adding new
  commands — see §16.

---

## 2. Starting checkpoint

| Item | Result |
|---|---|
| Archive name | `SOC-IQ-Phase4C-FINAL-FROZEN.zip` |
| `PHASE4C_FREEZE.md` or equivalent | **Absent** (only `PHASE2_FREEZE.md`, `PHASE3_PART3C_FREEZE.md` exist) |
| `.git` history | Absent — flat snapshot, consistent with every prior phase per `docs/migration/PHASE4B_GIT_BASELINE_NOTE.md` |
| `app/application/`, `app/api/` present | Yes — unexpected for a "Phase 4C FINAL FROZEN" label |
| `PROJECT_CONSTITUTION.md` snapshot reference | `SOC-IQ-Phase4D-COMPLETE-PROJECT.zip` (a name that does not match this upload) |

---

## 3. Actual source inventory — `app/application/`

| File | Lines | Contents |
|---|---|---|
| `dto.py` | 123 | `AnalyzeReportRequest`, `GetInvestigationRequest`, `ListInvestigationsRequest` (request DTOs, frozen dataclasses with `__post_init__` validation); `InvestigationSummaryDTO` (response DTO, explicit `from_domain`/`to_dict`, never passes a domain object through raw) |
| `errors.py` | 71 | Error-code catalog; `code_for_exception()` walks the MRO so unmapped subclasses fall back to their nearest mapped ancestor, not straight to `INTERNAL_ERROR` |
| `events.py` | 67 | `Event` (frozen dataclass), `EventCollector` (in-process, not a live transport), `new_correlation_id()` |
| `handlers.py` | 221 | 3 command handlers + `dispatch()` + `COMMAND_HANDLERS` dict |
| `responses.py` | 42 | `Envelope`/`ErrorPayload` dataclasses, `ok()`/`fail()` |

## 4. Actual source inventory — `app/api/`

| File | Contents |
|---|---|
| `app.py` | FastAPI `app` object: `GET /health`, `POST /commands/{name}`, `GET /events` (returns a translated 501, not a raw exception) |
| `entrypoint.py` | Runnable sidecar process (loopback bind, ephemeral port handshake) — added in a later phase (4E Part 1) per its own docstring, present in this snapshot |

---

## 5. Command matrix

| Command | DTO | Handler | Response | Validation | API endpoint | Tests | Status |
|---|---|---|---|---|---|---|---|
| `get_investigation` | ✅ `GetInvestigationRequest` | ✅ `GetInvestigationCommandHandler` | ✅ summary or `INVESTIGATION_NOT_FOUND` | ✅ positive-int check | ✅ via `POST /commands/get_investigation` | ✅ `test_application_layer.py`, `test_api_layer.py` | **IMPLEMENTED / VERIFIED** |
| `list_investigations` | ✅ `ListInvestigationsRequest` (no params) | ✅ `ListInvestigationsCommandHandler` | ✅ list of summaries | n/a (no params) | ✅ | ✅ | **IMPLEMENTED / VERIFIED** |
| `analyze_report` | ✅ `AnalyzeReportRequest` | ✅ `AnalyzeReportCommandHandler` | ✅ result + `correlation_id` | ✅ non-empty path string | ✅ (though see §6 — sync only) | ✅ including full event-sequence assertion | **IMPLEMENTED / VERIFIED** |
| `delete_investigation` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT STARTED** — named in `PHASE4B_COMMAND_INVENTORY.md` |
| `save_settings` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT STARTED** — inventory itself calls the name "inferred," never confirmed |
| `export_report` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT STARTED** — inventory explicitly flags this as referenced-but-unwired |
| `enrich_ioc` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT STARTED** — inventory explicitly flags this as referenced-but-unwired |
| `get_iocs` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT STARTED** — explicitly deferred in `dto.py`'s own docstring |
| `get_threat_intelligence` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT STARTED** — explicitly deferred in `dto.py`'s own docstring |
| `search_investigations` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT STARTED** |

No stub, TODO, or partial implementation was found for any of the 7 unimplemented
commands — they are genuinely absent from source, matching what
`PHASE4D_PART2_IMPLEMENTATION.md` §3 claims on this specific point.

---

## 6. Event matrix

| Event | Payload | Producer | Consumer | Serializable | Dispatch | Tests | Live/dead |
|---|---|---|---|---|---|---|---|
| `analysis.started` | `{report_path}` | `AnalyzeReportCommandHandler` | `EventCollector` (in-process only) | ✅ `to_dict()`/`asdict` | In-process append, no transport | ✅ | **Live** — asserted in `test_analyzes_real_sample_report_and_emits_correct_event_sequence` |
| `analysis.progress` | `{percent, message}` | same, via `on_progress` callback forwarded from `app.analyzer.analyze_report` | same | ✅ | same | ✅ | **Live** |
| `analysis.completed` | `{existing, investigation}` | same | same | ✅ | same | ✅ | **Live** |
| `analysis.failed` | `{code, message}` | same (two call sites: invalid path, and the broad `except Exception`) | same | ✅ | same | ✅ (`AnalyzeReportErrorTranslationTests`) | **Live** |

No decorative or dead event definitions were found — `events.py` defines the
generic `Event`/`EventCollector` machinery only; the four event *names* above
are the only ones actually published anywhere in source. `GET /events` does not
yet consume `EventCollector` over a live stream — this is a documented gap
(§7), not a second, competing event system.

---

## 7. Error model audit

`code_for_exception()` (errors.py) maps 11 concrete exception types plus a
`SOCIQError` base-class fallback, walking the MRO. Traced against actual call
sites:

| Exception | Where raised | Translated by | Verified |
|---|---|---|---|
| `CommandValidationError` (bad payload shape) | DTO `__post_init__` | `dispatch()`'s own `except CommandValidationError` | ✅ test |
| `TypeError` (missing/unexpected dataclass field) | dataclass `__init__` | `dispatch()`'s own `except TypeError` → `INVALID_COMMAND_PAYLOAD` | ✅ test |
| `DatabaseError` | `InvestigationService.get_by_id` / `.list_all()` (reproduced directly in tests via a raising fake) | `dispatch()`'s catch-all `except Exception` → `code_for_exception()` → `DATABASE_ERROR` | ✅ `DispatchErrorTranslationTests` |
| Generic/unmapped domain exception | anywhere | catch-all → `INTERNAL_ERROR` | ✅ `test_unmapped_exception_falls_back_to_internal_error` |
| `FileNotFoundError` from `analyze_report`'s own domain path | `app.analyzer.analyze_report` | `AnalyzeReportCommandHandler`'s own internal `except Exception` → `REPORT_NOT_FOUND` mapping | ✅ |
| Provider errors (`InvalidAPIKeyError`, `RateLimitExceededError`, `ThreatIntelConnectionError`, etc.) | `app/threat_intel/exceptions.py` | mapped in the catalog | Mapping present; **no test drives a TI exception through the command boundary specifically** — coverage is at the catalog-unit level (`ErrorTranslationUnitTests`), not an end-to-end `analyze_report`-triggers-a-TI-exception path |

No raw exception was found able to escape either `dispatch()` or the FastAPI
route (`run_command` has no unhandled path — `dispatch()` never re-raises).
`GET /events` was rewritten in "Part 2" to return a translated `NOT_IMPLEMENTED`
501 instead of a bare `NotImplementedError`; confirmed in source (§4) and
covered by `test_events_stream_returns_translated_not_implemented_error`.

**Gap found (minor):** the TI-exception → command-boundary path is mapped but
not exercised end-to-end by a test. Documented as a gap, not fixed here per the
audit-only scope.

---

## 8. API audit

| Endpoint | Transport | Command/Handler | Response | Error mapping | Tests | Status |
|---|---|---|---|---|---|---|
| `GET /health` | FastAPI | none — no domain/service dependency, by design | `{"status": "ok"}` via `ok()` | n/a | ✅ | Correct, matches its own docstring's stated invariant (cheap, no domain state) |
| `POST /commands/{name}` | FastAPI | `COMMAND_HANDLERS.get(name)` → `dispatch()` | `ok()`/`fail()` envelope | Delegated entirely to `dispatch()` — the route itself adds no logic | ✅ | Correct — a genuine thin adapter, not a place where business logic leaked |
| `GET /events` | FastAPI | none (SSE not implemented) | `JSONResponse(501, fail(NOT_IMPLEMENTED, ...))` | Explicit, documented | ✅ | Correct given documented scope — real gap, honestly represented, not silently stubbed |

No application/business logic was found living in `app/api/app.py` — every
route either has zero domain dependency (`/health`) or immediately delegates to
`app.application.handlers` (`/commands/{name}`).

---

## 9. Architectural coupling audit

| Check | Result | Classification |
|---|---|---|
| `app/application` importing Qt/PySide6 | None found (only a docstring *mentions* "PySide6 GUI" as context) | CORRECT |
| `app/application` importing FastAPI/pydantic | None found (docstring in `dto.py` *mentions* pydantic as a future migration target, no import) | CORRECT |
| `app/application` importing GUI (`app.gui.*`) | None found | CORRECT |
| Handlers constructing infrastructure directly instead of DI | `GetInvestigationCommandHandler`/`ListInvestigationsCommandHandler` accept an optional `service` param defaulting to a real `InvestigationService()` — this is DI-with-a-default, the standard pattern used by this project elsewhere | ACCEPTABLE |
| API layer implementing business logic | None found — see §8 | CORRECT |
| DTOs depending on infrastructure | None — `dto.py` imports only `app.database.models.Investigation` (the domain model it maps, per its own stated contract) and `app.application.errors` | CORRECT |
| Events depending on transport | None — `events.py` has zero FastAPI/HTTP imports | CORRECT |
| Application layer depending on Tauri | None — only comment/docstring mentions in `app/api/*` referring to a future consumer, not an import | CORRECT |
| Duplicate command/event buses | None — `app/application/events.py` is the only event abstraction in the new layer; the two legacy Qt buses (`app/gui/events/*`) still exist but are untouched and undisputedly separate, matching the documented "replace, don't merge" plan | ACCEPTABLE (pre-existing, documented, not this phase's problem to resolve) |
| Circular imports | None found (`app/application` never imports `app/api`; `app/api` imports `app/application` one-directionally) | CORRECT |
| Provider-specific types leaking into application contracts | None — `InvestigationSummaryDTO` deliberately omits nested TI/IOC domain shapes per its own docstring | CORRECT |

**Verdict: zero DEFECT-classified findings.** Every coupling check passed. The
one FUTURE WORK item is the unimplemented SSE stream, already honestly
documented as such in source, not hidden.

---

## 10. Fresh test results (run this session, not carried forward)

```
$ python3 -m pytest tests/ -q --ignore=tests/gui
481 passed, 1 warning in 3.83s

$ QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q
635 passed, 1 warning in 12.17s

$ python3 -m pytest tests/test_application_layer.py tests/test_api_layer.py -q
24 passed, 1 warning in 0.49s
```

PySide6 **is** installed in this sandbox — the GUI suite collected and passed
in full. This contradicts `PROJECT_CONSTITUTION.md`'s claim that GUI tests are
"UNVERIFIED... this session" for whatever session produced that document; that
claim does not hold for the environment this audit actually ran in.

### Discrepancy reconciliation

| Source | Count | Scope | Verified this session? |
|---|---|---|---|
| `IMPLEMENTATION_STATUS.md` | 399 | non-GUI | **No** — stale, does not match fresh run |
| Prior audit turn (this conversation) | 481 | non-GUI | **Yes** — reproduced identically this turn |
| `PHASE4D_PART2_IMPLEMENTATION.md` | 558 | claimed "full suite" | **No** — does not match either non-GUI (481) or combined (635) fresh counts; likely stale or measured against a different, later snapshot than this archive |
| This audit | 481 (non-GUI) / 635 (combined, GUI offscreen) | both | **Yes**, both figures freshly run |

No test was skipped, weakened, or modified to produce these numbers. The
gap between 399/481/558/635 is not explained by any single cause found in this
archive — most plausibly, different documents were written against different,
later snapshots of the same evolving project (consistent with
`PROJECT_CONSTITUTION.md` citing a `SOC-IQ-Phase4D-COMPLETE-PROJECT.zip` name
that isn't this upload) and never reconciled back into this one before it was
packaged and labeled "Phase4C-FINAL-FROZEN."

---

## 11. Design-vs-source matrix

| Area | Design says | Source actually does | Tests prove | Documentation says | Verdict |
|---|---|---|---|---|---|
| DTOs | Frozen dataclasses, 1:1 field match to future pydantic models | Matches exactly | ✅ | Matches | CONFIRMED |
| Commands | 3 commands as a "representative slice"; ~7 more named but deferred | Matches exactly — 3 implemented, 7 absent | ✅ | Matches (Part 2 doc §3) | CONFIRMED |
| Handlers | Thin orchestration, no business logic, DI-friendly | Matches | ✅ | Matches | CONFIRMED |
| Responses | Never a bare domain object, never a raised exception for expected failures | Matches | ✅ | Matches | CONFIRMED |
| Errors | Normalized catalog, MRO-based fallback | Matches | ✅ (catalog-level); gap at TI-exception end-to-end (§7) | Matches | CONFIRMED, with one untested edge |
| Events | Schema + in-process collector only, no live transport this phase | Matches | ✅ | Matches | CONFIRMED |
| API | Thin adapter, `/health`, `/commands/{name}`, `/events` (translated 501) | Matches | ✅ | Matches | CONFIRMED |
| Entrypoint | Added Phase 4E Part 1, loopback + handshake | Present, matches its own docstring's stated origin | Not directly targeted by this audit's test runs (already covered by `tests/test_sidecar_entrypoint.py`, pre-existing) | Matches | CONFIRMED |
| Health endpoint | Zero domain dependency | Matches | ✅ | Matches | CONFIRMED |
| Event endpoint | Documented-gap 501, not a crash | Matches | ✅ | Matches | CONFIRMED |
| Exception handling | No raw exception crosses the boundary | Matches (§7) | ✅ | Matches | CONFIRMED |
| Serialization | All DTOs/events/envelopes are plain-dict serializable | Matches | ✅ | Matches | CONFIRMED |
| Dependency direction | application ← api, never the reverse; application never → GUI/Qt/Tauri | Matches (§9) | ✅ (import grep) | Matches | CONFIRMED |
| **Phase 4C provider abstraction** | `PROJECT_CONSTITUTION.md`/`NON_NEGOTIABLE_RULES.md`: "design-only, not yet in source" | **Fully implemented in source** (`ThreatIntelProvider`, `VirusTotalProvider`, migrated `ThreatIntelService`) | ✅ (`test_threat_intel_provider_contract.py`, `test_virustotal_provider.py`) | **CONTRADICTS** constitution/rules | **DOCUMENTATION DRIFT** — source is ahead of these two governing documents |
| **Phase 4C freeze report** | Implied to exist for any "-FINAL-FROZEN" archive | **Absent** | n/a | n/a | **DEFECT** (process, not code) |
| **Overall test baseline** | Single authoritative number expected | 481 non-GUI / 635 combined, freshly confirmed | ✅ | Three conflicting stale numbers across docs | **DOCUMENTATION DRIFT** |

---

## 12. Phase 4C status

**COMPLETE.** `ThreatIntelProvider` (protocol) and `VirusTotalProvider`
(concrete adapter) both exist in source; `ThreatIntelService` depends on the
protocol type, never a bare client, confirmed by direct read of
`app/threat_intel/service.py` (9 references to `ThreatIntelProvider`/
`VirusTotalProvider`, including the constructor's default provider list).
Backed by two dedicated test files. The only thing actually missing is the
**freeze report** documenting this completion — the code is done, the paperwork
isn't.

## 13. Phase 4D status

**PARTIAL — IMPLEMENTED / VERIFIED for the 3-command slice it covers.**
Not "Complete" (as `PHASE4D_PART2_IMPLEMENTATION.md` claims) and not "3/many
commands wired, SSE not implemented" as a vague in-progress note (as
`IMPLEMENTATION_STATUS.md` says) — both are technically consistent with what's
in source, but neither commits to a verifiable, falsifiable claim the way this
audit's command/event matrices (§5, §6) do. Exit criteria per
`PROJECT_CONSTITUTION.md` §26 ("contract tests passing") **are met for the
implemented slice** — all 24 application+API tests pass fresh — but the phase
as a whole is not exit-criteria-complete while 7 of ~10 named commands and the
SSE stream remain unbuilt.

---

## 14. Defects

1. **Missing `PHASE4C_FREEZE.md`.** Process gap, not a code defect. Phase 4C
   work is real and tested but was never formally frozen/documented as such.
2. **`PROJECT_CONSTITUTION.md` §4/§16 and `NON_NEGOTIABLE_RULES.md` rule 16 are
   factually wrong about Phase 4C's source status** — both currently say the
   `ThreatIntelProvider` abstraction is design-only. This is the highest-authority
   document in the project's own hierarchy (§12 of the constitution itself) and
   it's stale on a load-bearing fact. Since rule 16 gates "do not implement a
   second TI provider before the abstraction is stable" on this same false
   premise, leaving it uncorrected risks a future session either wrongly
   refusing legitimate work or wrongly reintroducing the abstraction from
   scratch.
3. **Three unreconciled test-count baselines** (399 / 558 / actual 481 or 635)
   across `IMPLEMENTATION_STATUS.md` and `PHASE4D_PART2_IMPLEMENTATION.md`.
   Neither older number can be traced to a reproducible run in *this* archive.
4. **Minor test gap:** no test drives a threat-intel exception through the
   command dispatch boundary end-to-end (the mapping exists and is unit-tested
   in isolation, just not integration-tested through `dispatch()`).

## 15. Deferred work (confirmed genuinely not started, not just undocumented)

- Commands: `delete_investigation`, `save_settings`, `export_report`,
  `enrich_ioc`, `get_iocs`, `get_threat_intelligence`, `search_investigations`.
- `GET /events` SSE streaming (currently an honest 501).
- Rust/Tauri shell wiring beyond the existing `entrypoint.py`/`sidecar-core`
  (out of this audit's scope; not re-verified here).
- React frontend integration (out of scope).

---

## 16. Recommended next action

1. Keep `app/application/*` and `app/api/*` exactly as-is — they are real,
   tested, defect-free work, not something to redo.
2. Before any new Phase 4D command work: correct the two stale, high-authority
   documents (`PROJECT_CONSTITUTION.md` §4/§16, `NON_NEGOTIABLE_RULES.md` rule
   16) to state Phase 4C is source-complete, and write the missing
   `PHASE4C_FREEZE.md` so this archive's "FINAL-FROZEN" label is actually true
   retroactively.
3. Then resume Phase 4D by implementing the next command from
   `PHASE4B_COMMAND_INVENTORY.md`/`PHASE4B_QUERY_INVENTORY.md` (this audit
   makes no recommendation on which one — that's a scope decision, not an
   audit finding).
4. Add the one missing integration test identified in §7/§15 (TI exception
   through `dispatch()`) opportunistically when touching that area next, not
   as an emergency fix.

---

## Final report

- **Checkpoint findings:** archive is not a clean Phase 4C freeze; no freeze
  report exists; Phase 4D application/API layer already present.
- **What Phase 4C actually is:** complete in source (provider abstraction +
  migrated service + tests), contradicting two governing documents that say
  otherwise.
- **What Phase 4D actually contains:** 3 of ~10 named commands, fully
  implemented and tested; 4 events, all live; a thin, defect-free FastAPI
  adapter; an honestly-stubbed SSE endpoint.
- **Exact fresh test counts:** 481 passed (non-GUI), 635 passed (combined,
  `QT_QPA_PLATFORM=offscreen`), 24 passed (application+API layer only).
- **Material discrepancies:** three conflicting historical test-count claims;
  `PROJECT_CONSTITUTION.md`/`NON_NEGOTIABLE_RULES.md` factually wrong about
  Phase 4C; constitution references a snapshot name that doesn't match this
  archive.
- **Architectural defects found:** none in code. All coupling checks passed.
- **Genuinely verified:** all 3 commands, all 4 events, the error model (minus
  one integration-test gap), the API layer, dependency direction.
- **Genuinely unverified/deferred:** the 7 remaining commands, SSE streaming,
  Rust/Tauri/React layers (out of scope this pass).
- **Audit document:** `docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md` (this file).
- **Full project zip:** `SOC-IQ-Phase4D-Reconciliation-Audit.zip`.

**PHASE 4D RECONCILIATION COMPLETE — READY FOR IMPLEMENTATION/FIX PASS**
