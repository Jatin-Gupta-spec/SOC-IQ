# Phase 4E-P1, Part 2 — Typed Frontend Command Client — Caller Migration, Hardening, Final Verification

**Status:** Part 2 of 2. Verification-and-hardening session performed
against the real, extracted Part 1 checkpoint. Real `npm run typecheck`,
`npm run build`, `npx vitest run`, and the backend regression suites were
executed in this session, not assumed. Phase 4E is **NOT frozen** by this
document.

Builds on: `docs/phase4/PHASE4E_ARCHITECTURE.md`,
`docs/phase4/PHASE4E_FULL_STATUS_AUDIT.md`,
`docs/phase4/PHASE4D_FREEZE.md`,
`docs/phase4/PHASE4E_P1_PART1_IMPLEMENTATION.md`.

---

## 1. Mandatory checkpoint verification

The uploaded `SOC-IQ-Phase4E-P1-Part1-CommandClient.zip` was extracted
fresh and inspected directly (not assumed from the Part 1 document).

| Check | Result |
|---|---|
| `runCommand<T>()` exists | Yes — `frontend/src/shared/api/client.ts`, real `fetch()` transport |
| Uses `getSidecarOrigin()` | Yes — awaited first, unchanged, never re-implemented |
| No hardcoded sidecar port | Confirmed — the only `127.0.0.1` occurrences are a doc-comment example and a test fixture constant (`client.test.ts`) |
| Response envelopes handled centrally | Yes — one `isApiResponseShape()` structural guard, one call site |
| Backend error codes preserved | Yes — `CommandFailedError.code`/`.message` carry the `fail()` envelope verbatim |
| Malformed responses rejected | Yes — non-JSON and shape-mismatched bodies both throw `CommandMalformedResponseError`, never treated as success |
| No direct Tauri `invoke()` calls in UI command callers | Vacuously true — no UI command callers exist yet (see §3) |
| Phase 4D SSE intact | Yes — `frontend/src/shared/events/**` untouched; `GET /events` untouched; verified by direct diff and by re-running the backend event-broker suite (§8) |
| Phase 4D remains frozen | Yes — `docs/phase4/PHASE4D_FREEZE.md` unchanged, no `app/` file it covers was touched |
| Phase 4E remains unfrozen | Yes — this document says so explicitly (§14) |

**Not a stop condition.** Part 1 is present and matches its own
implementation document exactly — same `runCommand<K>()` signature, same
four error classes, same `CommandContracts` map, same 10 command names.
Every field in `frontend/src/shared/api/types.ts` was re-checked
field-for-field against the live `app/application/dto.py` request DTOs
and `app/application/handlers.py`'s `ok(...)` call sites (§9) — no drift
found. Proceeded to Part 2 work.

---

## 2. Objective

Per the task brief: complete the typed command-client boundary and
migrate the appropriate existing frontend command callers, then harden
and finally verify Phase 4E-P1 as a whole.

## 3. Full caller audit (§3 of the brief)

Searched the entire `frontend/src` tree for every pattern named in the
brief: `fetch(`, `axios`, `XMLHttpRequest`, `invoke(`, hardcoded API
URLs, hardcoded `127.0.0.1`/`localhost`, direct `/command` paths,
command names, `TODO` placeholders, and duplicated request/response
parsing.

**Result: the frontend has exactly one command caller, and it is
`runCommand()` itself.** There are no pages, no components, no hooks,
and no `features/` code in this checkpoint — `frontend/src/features/` is
an empty directory, `frontend/src/app/router.tsx` mounts a static
placeholder (`AppRoutes()` renders one `<p>` with no data fetching), and
`frontend/src/app/App.tsx`'s own doc comment states plainly: "No feature
screens, no sidebar/navigation chrome, no data fetching — those belong to
Phase 4G". `PHASE4E_ARCHITECTURE.md` §7 independently confirms this is
intentional for this stage ("Pages/components: intentionally absent...
Phase 4G+ scope"), and Part 1's own implementation document already
recorded the same fact in its §11 ("no page or hook calls a command
yet").

Full inventory, classified per the brief's A/B/C/D scheme:

| Occurrence | Location | Classification |
|---|---|---|
| `fetch(...)` | `client.ts:214` | B — the one canonical transport itself, not a caller to migrate |
| `invoke("get_sidecar_origin")` | `client.ts` (`getSidecarOrigin`), re-used by `eventSourceManager.ts` | C — origin resolution, not command execution; out of command-client scope by design |
| `127.0.0.1` | `client.ts` doc comment (example origin string in prose) | C — documentation text, not a live value |
| `127.0.0.1:54213` | `client.test.ts:28` | C — test fixture constant, not shipped code |
| `/commands/${name}` template | `client.ts:214` | B — the one canonical endpoint template |

No occurrence of `axios`, `XMLHttpRequest`, a second/duplicated
fetch-and-parse block, a hardcoded non-loopback URL, a raw command-name
string outside `types.ts`'s `CommandName` union, or a `TODO` placeholder
was found anywhere in `frontend/src`.

**Conclusion: there is nothing to migrate in this checkpoint.** §4 of
the brief ("Migrate real command callers") therefore has zero applicable
targets — manufacturing a page or component to migrate would mean
building Phase 4G feature-screen work inside a P1 hardening slice, which
the brief itself prohibits ("Do not redesign the UI", "Do not change
page layout") and which `PHASE4E_ARCHITECTURE.md` explicitly reserves for
a later phase. This is reported as a finding, not silently skipped.

## 4. Migration work performed

None — see §3. No page, component, or hook required migration because
none exists yet. `runCommand<T>()`/`getSidecarOrigin()` remain, as Part 1
left them, called only from `client.ts` itself, `client.test.ts`, and (for
`getSidecarOrigin` only) `eventSourceManager.ts`.

## 5. Command type safety (§5 of the brief)

Re-verified `CommandContracts` in `types.ts` field-for-field against the
live backend source in this session (not re-trusted from Part 1's
document):

- Every one of `app/application/dto.py`'s 10 request dataclasses
  (`AnalyzeReportRequest`, `GetInvestigationRequest`,
  `ListInvestigationsRequest`, `SearchInvestigationsRequest`,
  `GetIocsRequest`, `GetThreatIntelligenceRequest`,
  `SaveSettingsRequest`, `ExportReportRequest`, `EnrichIocRequest`,
  `DeleteInvestigationRequest`) matches its corresponding
  `*Payload` type exactly, including `SaveSettingsRequest`'s
  exactly-one-of-three-fields rule (mirrored as a 3-branch discriminated
  union, not a single interface with optional fields).
- Every handler's `ok(...)` call site in `app/application/handlers.py`
  matches its corresponding `*Result` type exactly, including the three
  fields correctly left as `Record<string, unknown>`
  (`GetIocsResult.iocs`, `GetThreatIntelligenceResult.threat_intelligence`,
  `EnrichIocResult`) because none has a backend DTO to derive a narrower
  type from.
- `CommandName`'s 10-member union matches `COMMAND_HANDLERS`'s 10 keys
  exactly (order-independent set comparison).

No `any` exists in `client.ts` or `types.ts` (grep-confirmed, zero
matches). The two `as` casts in `client.ts` (`body.data as
CommandResult<K>` after `isApiResponseShape` confirms `success: true`;
`body as ApiFailure` after confirming `!body.success`) are narrowing
casts on an already-validated `unknown`, not unsafe escapes — unchanged
from Part 1, re-confirmed here. `runCommand("get_investigation", {})`
(wrong payload) and `runCommand("not_a_command", {...})` (unknown name)
both fail to compile — verified interactively against `tsc`. No
additional abstraction (code generation, a runtime schema validator
library, etc.) was added; the existing hand-written map already meets
the brief's "if TypeScript generic inference is already sufficient, do
not add unnecessary abstraction" instruction.

## 6. Error UX boundary (§6)

No page exists to own presentation-level error handling (see §3), so
there is nothing to audit for duplicated backend-error parsing, silent
catches, or raw stack traces in UI code. `client.ts` itself already owns
the entire transport/application error boundary: four concrete
`CommandClientError` subclasses, no generic catch-all, no fake success
path (re-confirmed by reading every `throw`/`return` site in
`runCommand()` — six is present, all six are typed rejections).

## 7. Loading / request lifecycle (§7)

No caller exists, so there is no loading state, duplicate-submission
path, or unmount-after-response path to audit. `runCommand()` itself is
side-effect-free with respect to lifecycle: it makes exactly one `fetch`
call per invocation, holds no client-side mutable state, and each call is
independent (no request-id tracking is needed at this layer since no two
in-flight calls can race each other's rendering — that concern belongs to
whichever future page owns a `useState`/`useEffect` around a
`runCommand()` call, per the brief's own boundary: "API client: ...
transport/application error normalization. Page: presentation").

## 8. No retry system (§8) — verified absent

Read every line of `runCommand()`: exactly one `fetch()` call, no loop,
no `setTimeout`, no recursion, no retry counter. `getSidecarOrigin()`:
exactly one `invoke()` call, same property. Confirmed by the existing
Part 1 test #10 (exactly one `invoke` call per `runCommand()` call),
re-run in this session (§12).

## 9. Security audit (§9)

| Check | Result |
|---|---|
| Hardcoded port | None — origin comes from `getSidecarOrigin()` alone |
| Secret/key added to frontend requests | None — grepped `frontend/src` for `api_key`/`apiKey`/`API_KEY`; the only match is an unrelated design-token comment (`styles/tokens/color.ts`, a color-naming note, not a secret) |
| API key in events | Out of this Part's file-change scope (`app/application/handlers.py` is unmodified); Phase 4D's own freeze audit already traced this (`ti.enrichment.*` payloads never carry the provider key) and nothing here reopens it |
| Backend stack trace exposed | No — `client.ts` only ever surfaces `code`/`message` from the `fail()` envelope, never a raw exception |
| Arbitrary URL construction from user input | No — the only URL built is `` `${origin}/commands/${encodeURIComponent(name)}` ``, where `origin` comes solely from `getSidecarOrigin()` and `name` is a compile-time-closed `CommandName` literal, not a free string |
| Unsafe HTML insertion | None — grepped for `innerHTML`/`dangerouslySetInnerHTML` in `frontend/src`, zero matches |
| Credentials introduced unnecessarily | None |
| New CORS workaround | None added |
| Tauri capability widening | None — `src-tauri/capabilities/default.json` still grants exactly `core:default` + `get_sidecar_origin`, byte-identical to Part 1 |

No pre-existing accepted finding was expanded in scope; none required
re-documentation beyond what Phase 4D's freeze report already covers.

## 10. SSE regression check (§10)

Explicitly re-verified in this session, by source read (not assumed
unchanged):

- `frontend/src/shared/events/eventSourceManager.ts` still imports
  `getSidecarOrigin` from `../api/client` (one import, unchanged) and
  contains no direct `invoke()` call of its own — origin resolution is
  not duplicated between the SSE path and the command path.
- `GET /events` (`app/api/app.py`) untouched — same route, same
  `StreamingResponse`, confirmed by direct read.
- `EventBroker` (`app/application/broker.py`) untouched.
- Heartbeat framing (`: heartbeat` comment frames) and disconnect
  cleanup (`try/finally` unsubscribe) untouched — confirmed by re-running
  `tests/test_event_broker.py` (37/37 passing, §12) rather than trusting
  a prior session's result.
- No command-client change bypasses SSE: `runCommand()` and
  `eventSourceManager.ts` share exactly one origin-resolution function
  and zero other code.

## 11. Tauri regression check (§11)

- `getSidecarOrigin()` remains the only frontend origin bridge — grepped
  `frontend/src` for `invoke(`, only two call sites exist, both inside
  `client.ts` (`getSidecarOrigin`'s own `invoke("get_sidecar_origin")`
  call, and the doc comment referencing it).
- Exactly one `#[tauri::command]` (`get_sidecar_origin`,
  `src-tauri/src/lib.rs:95`) and exactly one
  `generate_handler![get_sidecar_origin]` registration
  (`src-tauri/src/lib.rs:120`) — grep-confirmed, unchanged from Part 1.
- No new Tauri command was introduced this session.
- `src-tauri/capabilities/default.json` unchanged (§9).
- Browser/dev mode still works without Tauri: `getSidecarOrigin()`'s
  `isTauri()` check and its `SidecarNotConnectedError` fallback are
  unchanged — this is also exactly what makes `npx vitest run` (§12)
  pass without a real Tauri runtime present.

`src-tauri/` was not modified. No regression was found that would have
required it.

## 12. Testing (§12) — actually executed this session

Frontend:

```
npm install            # 114 packages, succeeded (registry reachable this session)
npm run typecheck       # tsc --noEmit -- 0 errors
npm run build            # tsc --noEmit && vite build -- succeeded, 44 modules,
                          # dist/index.html + one JS/CSS bundle (144.79 kB / 46.97 kB gzip)
npx vitest run            # 1 test file, 10 tests, 10 passed, 0 failed
```

No new frontend test framework was installed — `vitest` already exists
as a dev dependency from Part 1; `npm run test` maps to `vitest run`
already.

Backend regression (cross-layer, since the command contract spans both):

```
python3 -m pytest tests/test_application_layer.py tests/test_event_broker.py tests/test_api_layer.py -q
# 143 passed, 1 warning, in 2.01s
```

The one warning is a pre-existing `starlette`/`httpx` deprecation notice
(`Using httpx with starlette.testclient is deprecated; install httpx2
instead`) unrelated to any change in this Part — `fastapi`/`starlette`
themselves were not modified, and neither package is part of this
checkpoint's own dependency pins; it is a property of the installed
tooling versions in this sandbox, not a regression introduced here.

No test was skipped, no result was fabricated, and no environment
blocker was hit this session for either the frontend or backend suites.

## 13. Static contract verification (§13)

- No page directly calls `fetch()` for command execution — no page
  exists (§3); the sole `fetch()` call site is `client.ts` itself.
- No page directly calls Tauri `invoke()` for command execution — same
  reasoning; the sole `invoke()` call sites are inside `client.ts`.
- No hardcoded sidecar port — confirmed (§1, §9).
- No duplicate command-endpoint wrapper — one `runCommand()`, one
  template string.
- No duplicated response-envelope parser — one `isApiResponseShape()`.
- No backend-contract drift — re-verified field-for-field in §5 against
  live `app/application/dto.py`/`handlers.py` source, not against the
  Part 1 document's claims about that source.
- All 10 migrated... (n/a — zero callers migrated, §3-4) — all 10
  *command names typed in `CommandContracts`* are valid against
  `COMMAND_HANDLERS`'s keys, checked directly.
- Request shapes match backend DTOs — confirmed in §5.

## 14. Adversarial audit (§14, all 20 items)

| # | Check | Result |
|---|---|---|
| 1 | Unsafe `any` | None (grep-confirmed, `client.ts`/`types.ts`) |
| 2 | Unsafe `as` casts | Two, both narrowing an already-validated `unknown` immediately after a structural check — not unsafe (§5) |
| 3 | Silent catches | None — every `catch` in `runCommand()` re-throws a typed error |
| 4 | Fake fallback values | None |
| 5 | Swallowed HTTP errors | None — non-2xx throws `CommandHttpError` |
| 6 | Lost backend error codes | None — `CommandFailedError.code` preserves it verbatim |
| 7 | Malformed JSON accepted as success | Rejected (`CommandMalformedResponseError`) |
| 8 | Wrong command names | Impossible for typed callers (`CommandName` closed union); no untyped caller exists |
| 9 | Wrong endpoint path | One template, matches `app/api/app.py`'s route exactly |
| 10 | Wrong HTTP method | `POST`, matches `@app.post("/commands/{name}")` |
| 11 | Hardcoded ports | None |
| 12 | Duplicate origin resolution | None — `runCommand`/`eventSourceManager.ts` share one `getSidecarOrigin()` |
| 13 | Duplicate Tauri invocation | None — one `invoke()` call site pattern, reused |
| 14 | Direct UI transport | N/A — no UI callers exist yet (§3) |
| 15 | Accidental SSE regression | None (§10) |
| 16 | Unnecessary retries | None (§8) |
| 17 | Race conditions in migrated callers | N/A — no callers migrated (§3-4) |
| 18 | Stale loading state | N/A — no caller-owned loading state exists yet |
| 19 | Unhandled promise rejection | None found in `client.ts`/`client.test.ts`; not applicable elsewhere (no async caller code exists) |
| 20 | Accidental API-key exposure | None (§9) |

No concrete P1 defect was found this session. Per §14's own instruction
("Fix only concrete P1 defects"), no source change to `client.ts` or
`types.ts` was made — Part 1's implementation was independently
re-verified, not modified, because nothing wrong was found in it.

## 15. Files changed this session

- `docs/phase4/PHASE4E_P1_PART2_IMPLEMENTATION.md` — this document (new)

Nothing else. `frontend/src/shared/api/client.ts`,
`frontend/src/shared/api/types.ts`, and
`frontend/src/shared/api/client.test.ts` are byte-identical to the
uploaded Part 1 checkpoint — confirmed by `diff -rq` against a second,
independent extraction of the same uploaded zip. No file under
`app/application/`, `app/api/`, `app/threat_intel/`, `sidecar-core/`, or
`src-tauri/` was modified.

## 16. Final P1 acceptance criteria

- [x] `runCommand<T>()` is real, not a stub
- [x] sidecar origin comes from `getSidecarOrigin()`
- [x] no hardcoded sidecar port exists
- [x] command transport is centralized
- [x] command response is typed
- [x] request typing is centralized
- [x] backend error codes survive
- [x] malformed responses are rejected
- [x] network failures are surfaced
- [x] relevant command callers use the typed client — **vacuously true: zero command callers exist in this checkpoint (§3); none was fabricated**
- [x] no page owns raw command transport — no page exists
- [x] no duplicate command wrappers exist
- [x] SSE remains unchanged and functional by source verification
- [x] Tauri origin bridge remains unchanged and functional by source verification
- [x] no Phase 4E-P2/P3/P4/P5/P6 work has been introduced
- [x] typecheck passes (0 errors)
- [x] build passes (`dist/` regenerated)
- [x] relevant backend regression tests pass (143/143)
- [x] adversarial audit completed (20/20 items, §14)
- [x] implementation document created (this file)
- [x] full project ZIP created (§17)
- [x] ZIP freshly extracted and verified (§17)

## 17. Full project ZIP + fresh extraction

A single full project ZIP was created from the checked-out tree
(generated artifacts excluded via path-anchored rules —
`__pycache__/`, `*.pyc`, `node_modules/`, `target/`, `.pytest_cache/`,
`dist/`, `build/`, coverage artifacts, temp files — never a broad
substring exclusion). It was then extracted into a second, fresh
directory and verified:

- All expected top-level project directories present (`app/`,
  `frontend/`, `src-tauri/`, `sidecar-core/`, `docs/`, `tests/`, etc.).
- Both `PHASE4E_P1_PART1_IMPLEMENTATION.md` and
  `PHASE4E_P1_PART2_IMPLEMENTATION.md` present under `docs/phase4/`.
- No `__pycache__/`, `node_modules/`, `dist/`, `.pytest_cache/`, or other
  generated artifact present in the fresh extraction.
- `npm run typecheck`, `npm run build`, and `npx vitest run` re-run
  against the fresh extraction's `frontend/` — same results as §12
  (0 typecheck errors, build succeeds, 10/10 tests pass).
- `python3 -m pytest tests/test_application_layer.py
  tests/test_event_broker.py tests/test_api_layer.py -q` re-run against
  the fresh extraction — same 143/143 result as §12.
- File count/tree compared against the pre-zip audited tree (excluding
  the generated artifacts named above and each side's own
  `node_modules`/`dist`/pycache, which are expected to differ): no file
  lost.

## 18. Remaining Phase 4E work

Per `PHASE4E_ARCHITECTURE.md` §10, five slices remain open beyond this
one (`4E-P1`, now complete in both parts):

- **4E-P2** — Sidecar crash/restart decision + implementation
  (`src-tauri/src/lib.rs`, `sidecar.rs`, `sidecar-core/src/supervisor.rs`)
- **4E-P3** — Frontend origin-retry loop
  (`eventSourceManager.ts`, `useEventStreamStatus.ts`)
- **4E-P4** — CORS posture decision (documented, not necessarily coded)
- **4E-P5** — Environment reconciliation (packaging/working-directory
  resolution for a bundled installer)
- **4E-P6** — Live end-to-end verification against a real running
  sidecar (depends on 4E-P1 + 4E-P5)

None of these was started, implemented, or designed in this session, per
the task brief's explicit prohibitions.

## 19. Phase 4E freeze status

**Phase 4E is NOT frozen.** This document closes both parts of exactly
one of the six slices named in `PHASE4E_ARCHITECTURE.md` §10 (`4E-P1`).
`4E-P2` through `4E-P6` remain open. No freeze document for Phase 4E was
created or implied by this session.

## 20. Full project ZIP path

`/mnt/user-data/outputs/SOC-IQ-Phase4E-P1-COMPLETE-FULL-PROJECT.zip`
