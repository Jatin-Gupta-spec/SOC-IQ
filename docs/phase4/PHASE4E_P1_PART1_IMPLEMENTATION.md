# Phase 4E-P1, Part 1 — Typed Frontend Command Client — Implementation

**Status:** Part 1 of 2. Client implemented, real `npm run typecheck` /
`npm run build` / focused unit tests executed in this session. Phase 4E
is **NOT frozen** by this document.

Builds on: frozen Phase 4D (`docs/phase4/PHASE4D_FREEZE.md`),
`docs/phase4/PHASE4E_ARCHITECTURE.md` §4/§7/§10 (slice "4E-P1 — Typed
frontend command client"), `docs/phase4/PHASE4E_FULL_STATUS_AUDIT.md`.

---

## 1. Checkpoint verification (before any change)

| Check | Result |
|---|---|
| Phase 4D frozen/documented | Yes — `docs/phase4/PHASE4D_FREEZE.md` present, CLASS B freeze |
| All 10 application commands implemented | Yes — `app/application/handlers.py::COMMAND_HANDLERS` has exactly 10 entries |
| `EventBroker` present | Yes — `app/application/broker.py`, unchanged |
| `GET /events` a real SSE endpoint | Yes — `app/api/app.py::events_stream`, unchanged |
| Frontend `EventSource` infrastructure present | Yes — `frontend/src/shared/events/`, unchanged |
| Tauri `get_sidecar_origin` bridge present | Yes — `src-tauri/src/lib.rs`, unchanged |
| `runCommand<T>()` stub present, unimplemented | Yes — `Promise.reject(new SidecarNotConnectedError(...))`, no transport |
| No previous Phase 4E-P1 command-client implementation exists | Confirmed. A file named `docs/phase4/PHASE4E_PART1_IMPLEMENTATION.md` *does* exist, but it documents a **different, earlier** Phase 4E slice — the sidecar runtime foundation (`app/api/entrypoint.py`, `GET /health`) — not the typed command client. `PHASE4E_ARCHITECTURE.md` §10 independently names the client as slice `4E-P1` and confirms its "Current state: explicit stub". No naming collision resolution was needed beyond noting this once, here. |

**Not a stop condition.** The checkpoint matched the expected state; proceeded to implementation.

## 2. Source contract audited before implementing

- `app/api/app.py::run_command` — `POST /commands/{name}`, JSON body,
  looks up `COMMAND_HANDLERS`, returns `fail(UNKNOWN_COMMAND, ...)` for
  an unknown name, otherwise `handler(payload)`.
- `app/application/responses.py::Envelope` — the real envelope:
  `{success, data, error}`, where `error` is `{code, message}` or
  `null`. `frontend/src/shared/api/types.ts`'s existing
  `ApiResponse<T>` already matched this exactly (`success`/`data`/`error`,
  not the task brief's simplified `ok`-keyed example) — used as-is, no
  second envelope introduced.
- `app/application/errors.py` — error-code catalog; codes are opaque
  strings (`INVESTIGATION_NOT_FOUND`, `TI_RATE_LIMITED`, etc.), preserved
  verbatim, not re-typed as a TS enum (that would need updating in two
  places every time a code is added — deliberately avoided).
- `app/application/dto.py` — all 10 request DTOs' fields and
  `__post_init__` validation rules, transcribed field-for-field into
  `CommandContracts` in `types.ts`.
- `app/application/handlers.py` — every handler's `ok(...)` call site,
  read directly to derive each command's actual response `data` shape
  (see §4 below for the two fields left as `Record<string, unknown>`
  rather than invented).

## 3. Previous stub state

```ts
export function runCommand<T>(_name: string, _payload: unknown): Promise<ApiResponse<T>> {
  return Promise.reject(new SidecarNotConnectedError(
    "runCommand() has no transport yet; only getSidecarOrigin() is wired as of Phase 4D SSE Part 4B",
  ));
}
```

No transport, no envelope handling, no error model. `getSidecarOrigin()`
(unchanged by this Part) was already fully implemented.

## 4. Implementation

### 4.1 `runCommand<K>()` design

```ts
export async function runCommand<K extends CommandName>(
  name: K,
  payload: CommandPayload<K>,
): Promise<CommandResult<K>>
```

Rather than the free `<T>` generic the stub declared, `name` is
constrained to the literal union `CommandName` (the 10 real command
names) and `payload`/the resolved value are both derived from one
central `CommandContracts` map in `types.ts` — per
`PHASE4E_ARCHITECTURE.md` §7's explicit invitation ("If a
command-name-to-request/response mapping can be safely typed without
overengineering, use it"). This means:

```ts
await runCommand("get_investigation", { investigation_id: 1 });
// payload shape checked at compile time; resolved value is InvestigationSummary
```

with no caller needing to pass an explicit `<T>`, no risk of a
command-name typo compiling, and no risk of a mismatched payload
compiling. No large generated-code system was introduced — the map is
one hand-written interface (`CommandContracts`) mirroring the 10
existing DTOs.

**Behavior**, in order:
1. `getSidecarOrigin()` is awaited first — its rejection
   (`SidecarNotConnectedError`) propagates unchanged; origin resolution
   is never re-implemented or duplicated here.
2. `fetch(`${origin}/commands/${name}`, { method: "POST", ... })` —
   the existing route, exactly. A `fetch` throw (offline, connection
   refused) is caught and re-thrown as `CommandNetworkError`.
3. A non-`response.ok` status throws `CommandHttpError` (status +
   statusText preserved) — this only exists as an escape hatch;
   `run_command` itself always returns 200 with a `fail()` envelope for
   application errors.
4. The body is parsed as JSON; a parse failure throws
   `CommandMalformedResponseError`.
5. The parsed body is structurally validated against the
   `{success, data, error}` shape (`isApiResponseShape`) — anything
   that doesn't match (wrong types, missing keys) throws
   `CommandMalformedResponseError` rather than being treated as a
   success.
6. `success: false` throws `CommandFailedError`, carrying the backend's
   `code` and `message` verbatim.
7. `success: true` resolves to `data` directly, typed as
   `CommandResult<K>`.

### 4.2 Response envelope

Reused `ApiResponse<T>` from `types.ts` unchanged — no second envelope.
`isApiResponseShape()` is the one new piece: a structural type guard
that only checks the envelope's own shape (`success`/`data`/`error`),
not the inner `data` shape (that remains the backend DTO/handler's
contract, already tested server-side).

### 4.3 Error model

Four concrete error classes, one abstract base (`CommandClientError`)
so a caller can catch broadly or narrowly:

| Class | When |
|---|---|
| `CommandNetworkError` | `fetch()` itself threw (no response received) |
| `CommandHttpError` | Non-2xx HTTP status |
| `CommandMalformedResponseError` | Body isn't valid JSON, or doesn't match the envelope shape |
| `CommandFailedError` | Well-formed `fail()` envelope — carries the backend `code`/`message` verbatim |

`SidecarNotConnectedError` (pre-existing, from `getSidecarOrigin()`) is
left as its own separate type rather than folded into
`CommandClientError` — it is a precondition failure (no origin to even
attempt a request against), not a failure of the request itself, and
`eventSourceManager.ts` already depends on catching it by its own name.

No generic catch-all: every failure path throws a distinct, typed
class; nothing is silently converted to a fake success; no stack trace
or internal detail beyond `message`/`code`/`status` crosses the
boundary.

### 4.4 Typed command definitions

Added to `frontend/src/shared/api/types.ts` (not `client.ts` —
`client.ts` only consumes them):
- `CommandName` — the 10-name literal union.
- One request-payload interface per command (`GetInvestigationPayload`,
  `SaveSettingsPayload` (discriminated union mirroring the DTO's
  exactly-one-of-three-fields rule), etc.), each a field-for-field
  mirror of its `app/application/dto.py` request DTO.
- One response-data type per command, mirroring each handler's `ok(...)`
  call site. Two fields (`Investigation.iocs`,
  `Investigation.threat_intelligence`) and one command's full result
  (`enrich_ioc`, wrapping `ThreatIntelService.lookup_indicator`'s
  `dict[str, Any]`) are typed as `Record<string, unknown>` rather than
  guessed at — none of the three has a backend DTO or fixed schema to
  derive a real type from.
- `CommandContracts` — the name → `{payload, result}` map `runCommand`
  is generic over.

## 5. Sidecar-origin integration

Unchanged. `runCommand` calls `getSidecarOrigin()` exactly once per
invocation and does not re-implement port discovery, Tauri `invoke`,
lifecycle checks, or sidecar startup logic. Verified by the "never calls
Tauri invoke directly for command transport" test (§6) — exactly one
`invoke("get_sidecar_origin")` call per `runCommand()` call, everything
after that is plain `fetch`.

## 6. Tests actually executed (this session)

Added `frontend/src/shared/api/client.test.ts` (new — no prior frontend
test file or configured test runner existed; `vitest` was added as the
one new dev dependency, matching Vite's own standard test runner rather
than introducing an unrelated framework). `package.json` gained one
script: `"test": "vitest run"`.

`npx vitest run` — **10 passed, 0 failed**:

1. origin resolved through `getSidecarOrigin()`/`invoke`, request hits `${origin}/commands/{name}` — no hardcoded port
2. request constructed correctly; body serialized as JSON
3. successful envelope resolves to typed `data` directly
4. backend `fail()` envelope becomes a typed `CommandFailedError` with code/message preserved
5. non-2xx HTTP status is not treated as success (`CommandHttpError`)
6. a `fetch` throw is represented as `CommandNetworkError`
7. a non-`ApiResponse`-shaped JSON body is rejected as malformed, not success
8. a non-JSON body is rejected as malformed, not success
9. `SidecarNotConnectedError` from `getSidecarOrigin()` propagates without calling `fetch`
10. exactly one `invoke` call per `runCommand()` call (`get_sidecar_origin` only) — no direct Tauri command-transport call

## 7. Typecheck / build status

Both executed for real in this session, not assumed:

- `npm install` — succeeded (73 packages; network access to the npm
  registry is allowed in this sandbox).
- `npm run typecheck` (`tsc --noEmit`) — **0 errors.** One real defect
  was found and fixed during this: `CommandNetworkError`'s constructor
  originally declared a `public readonly cause: unknown` parameter
  property, which conflicts with `Error.cause` (ES2022,
  `tsconfig.json`'s `target: "ES2022"`) under this project's
  `noImplicitOverride: true` — renamed to `originalError` rather than
  adding an `override` modifier, since it isn't actually overriding
  `Error.cause`'s semantics, just colliding with the name.
- `npm run build` (`tsc --noEmit && vite build`) — **succeeded**, 44
  modules transformed, `dist/` regenerated (`index.html` + one JS/CSS
  bundle, 144.79 kB / 46.97 kB gzip).

## 8. Environment

Node v22.22.2, npm 10.9.7. Unlike prior Phase 4 sessions, this sandbox
*did* have network access to the npm registry, so `npm install` and
`npm install -D vitest` both succeeded — no environment blocker to
report for the frontend toolchain this session. No Rust toolchain was
touched or needed (`src-tauri`/`sidecar-core` are out of this Part's
scope). No `.git` exists in the extracted project (consistent with
every prior session's finding) — no `git status`/`diff` could be run;
file-change verification instead comes from a direct `diff -rq` against
a second, untouched extraction of the same uploaded zip (§10).

## 9. Adversarial audit

| Check | Result |
|---|---|
| Hardcoded ports | None — origin comes from `getSidecarOrigin()` alone |
| Duplicate fetch wrappers | None — one `fetch` call site |
| Silent error swallowing | None — every failure path throws a typed error |
| Fake success responses | None — malformed/HTTP-failed/network-failed all reject |
| Malformed JSON treated as success | Rejected (`CommandMalformedResponseError`) |
| Backend error code loss | `CommandFailedError.code` carries it verbatim |
| Accidental/recursive retry loops | None — `runCommand` makes exactly one request, no retry logic |
| Direct Tauri calls from UI | None — `runCommand`/`getSidecarOrigin` are the only `invoke` call sites, both inside `client.ts` |
| Direct sidecar lifecycle management from UI | None — out of scope, untouched |
| Command-name typos | Structurally impossible for typed callers — `name` is `CommandName`, a closed literal union matching `COMMAND_HANDLERS`'s 10 keys |
| Inconsistent endpoint paths | One template, `${origin}/commands/${name}` |
| Duplicated request types | None — `CommandContracts` is the one source |
| Unsafe casts / `any` abuse | Zero occurrences of `any` in `client.ts`/`types.ts` (grep-confirmed). Two `as` casts exist, both narrowing an already-validated `unknown` at the generic boundary (`body.data as CommandResult<K>` after `isApiResponseShape` confirms `success: true`; `body as ApiFailure` after confirming `!body.success`) — not unsafe, since the shape is checked immediately before each cast |
| Unnecessary architecture | None added beyond the error classes and type map the contract explicitly calls for |
| Breaking existing SSE/EventSource behavior | `frontend/src/shared/events/**` untouched; `GET /events` route untouched |

## 10. Files changed

Diffed against a second, independent extraction of the same uploaded
zip:

- `frontend/src/shared/api/client.ts` — `runCommand<T>()` implemented; four error classes added
- `frontend/src/shared/api/types.ts` — `CommandName`/`CommandContracts`/per-command payload+result types added
- `frontend/src/shared/api/client.test.ts` — new, 10 focused tests
- `frontend/package.json` / `frontend/package-lock.json` — added `vitest` as a dev dependency and a `test` script
- `docs/phase4/PHASE4E_P1_PART1_IMPLEMENTATION.md` — this document

Nothing under `app/application/`, `app/api/`, `app/threat_intel/`,
`sidecar-core/`, or `src-tauri/` was touched — none was necessary; no
backend contract defect was found.

## 11. Remaining Phase 4E-P1 work (Part 2)

Per the task brief, Part 2 is out of scope for this session and was not
started:
- final caller migration (currently `runCommand`/`getSidecarOrigin` have
  no consumer beyond `client.ts` itself and this Part's tests — no page
  or hook calls a command yet, consistent with `PHASE4E_ARCHITECTURE.md`
  §7's "Pages/components: intentionally absent" for this stage)
- verification/hardening pass
- preparing the client for the next Phase 4E slice (4E-P3, frontend
  origin-retry loop, is the next dependency-free slice per the
  architecture doc's ordering)

## 12. Phase 4E freeze status

**Phase 4E is NOT frozen.** This Part closes exactly one of the six
slices named in `PHASE4E_ARCHITECTURE.md` §10 (`4E-P1`), and even that
slice's own completion criteria ("every one of the 10 commands callable
... no `any` at the call-site boundary") is met only for the client
itself — no live sidecar call has been exercised (that's `4E-P6`, which
explicitly depends on this slice plus `4E-P5`). `4E-P2` through `4E-P6`
are all still open, per the architecture document's own §11 checklist.
