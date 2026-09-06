# SOC-IQ — Phase 4 Next-Generation Architecture Master Plan

**Status:** Proposed / Approved-pending-review
**Baseline:** SOC-IQ-Phase4A-1C-B-A-CHECKPOINT.zip (~39,300 LOC Python, 206 files, 542/542 tests passing)
**Scope of this document:** Architecture and migration design only. No implementation, no file modification.

---

## 0. Method Note

Every claim below is labeled:

- **CONFIRMED** — verified directly against source in this checkpoint.
- **LIKELY** — strongly implied by source/tests but not exhaustively traced.
- **UNKNOWN** — not yet verifiable from the checkpoint; needs a follow-up read before Phase 4B begins.

Prior phase docs (`PHASE4_PART4A1B.md`, `PHASE4_PART4A1C.md`) were treated as **hypotheses**, not fact, and re-checked against `app/` source. All 17 baseline "problems" listed in your brief were re-verified directly in source during this pass (see §1.7).

---

## 1. CURRENT STATE

### 1.1 Layering (CONFIRMED, from directory structure + imports)

```
app/
├── cli.py                     Thin CLI entrypoint (76 LOC) — CONFIRMED
├── main.py, initializer.py    App bootstrap
├── extractor.py, analyzer.py  IOC extraction / report analysis
├── scoring/                   Weighted, explainable risk scoring engine
├── threat_intel/              VirusTotal client + orchration service
├── database/                  connection.py, models.py, repository.py, service.py
├── settings/                  models.py, repository.py, service.py
├── reporting/                 builder/service + json/csv/markdown/html/pdf exporters
├── services/                  dashboard, correlation, risk-explanation, system-health services
├── exceptions.py, exporters.py, display.py, logger.py, config.py
└── gui/                       PySide6 presentation layer (controllers, pages, widgets,
                                components, design tokens, events, workers, models)
```

CLI and GUI both import the same `app.*` domain modules (extractor, scoring, threat_intel,
database, reporting) — **CONFIRMED**: this is a genuine shared-core architecture, not a
GUI-only app with a CLI bolted on. This is the single most valuable existing asset and the
thing Phase 4 must not break.

### 1.2 Domain ownership (CONFIRMED)

| Concern | Owner today |
|---|---|
| IOC extraction | `app/extractor.py`, `app/analyzer.py` |
| Risk scoring | `app/scoring/engine.py`, `app/scoring/models.py` |
| Threat intel | `app/threat_intel/service.py` → `app/threat_intel/virustotal.py` (1,189 LOC) |
| Persistence | `app/database/repository.py` (613 LOC), `connection.py`, `models.py`, `service.py` |
| Reporting | `app/reporting/{builder,service}.py` + 5 format exporters |
| Settings/secrets | `app/settings/{models,repository,service}.py` |
| Correlation, dashboards | `app/services/*` (6 dashboard-adjacent services + correlation service) |

### 1.3 GUI/event/state architecture (CONFIRMED — this is the messiest layer)

Two independent Qt signal buses exist simultaneously:

- `app/gui/events/application_events.py` → `events` singleton. Its own docstring states its
  scope: settings changes, per-page refresh requests, generic status/error messages, **and**
  a signal called `investigation_deleted` that its own docstring flags as dead/unused-in-practice.
- `app/gui/events/event_bus.py` → `event_bus` singleton. Its docstring states its scope:
  investigation lifecycle (`investigation_selected/created/updated/removed`) plus
  `application_state_changed`.

**CONFIRMED** (read directly from source, not inferred from docs): the two files' own
docstrings already admit the split is confusing and warn engineers not to confuse
`events.investigation_deleted` with `event_bus.investigation_removed` — i.e. the project's
own authors already diagnosed this as a defect and left a guard-rail comment rather than
fixing it. This is exactly problem #2/#3 from your baseline, confirmed at the source level,
not just at the doc level.

Threading: `app/gui/workers/analysis_worker.py` — **LIKELY** a QThread/QRunnable-style worker
that runs extraction + enrichment + persistence off the UI thread; analyze_page.py comments
confirm ("does not poll... a slow/rate-limited enrichment call...") that analysis is
synchronous-per-worker, not step-wise cancellable. **CONFIRMED** via source comment in
`analyze_page.py`.

### 1.4 Analyze-page pipeline defect (CONFIRMED at source)

`app/gui/pages/analyze_page.py` contains three pipeline checkboxes (extraction / TI
enrichment / scoring). Source comments in the file **state outright** that none of the three
checkboxes currently gate what the backend pipeline executes — the enrichment checkbox was
always checked/enabled regardless of whether a VirusTotal key was configured, with no real
connection between checkbox state and pipeline behavior. This is a UI-truthfulness bug, not
a cosmetic one: analysts can believe they disabled TI enrichment and be wrong.

### 1.5 Threat intelligence architecture (CONFIRMED — single-provider, not abstracted)

`ThreatIntelService.__init__` takes an **optional `VirusTotalClient`** as its only injectable
dependency — there is no `ThreatIntelProvider` protocol, no provider registry, no normalized
cross-provider verdict type. `_format_verdict` computes verdict/detection-ratio directly from
VirusTotal's raw response shape (`malicious`/`suspicious`/`harmless`/`undetected` counts).
Adding AbuseIPDB or OTX today would mean writing verdict-shape-specific logic inside (or
beside) this class, not implementing an interface. This confirms problems #6 and #7 from your
baseline exactly.

### 1.6 Secrets/config (CONFIRMED)

`app/settings/models.py::ApplicationSettings.virustotal_api_key` is a plain `str` field.
A custom `__repr__` redacts it from logs/tracebacks (`<redacted>`) — a real, working
mitigation for *accidental* leakage via logging — but the underlying persisted value is
still plaintext JSON on disk (settings repository writes the dataclass to JSON; nothing in
`settings/repository.py` encrypts it). So: log-safe, disk-unsafe. This is a more precise
statement than "no secret protection at all" — the redaction work already done should be
preserved, not thrown away.

### 1.7 Other confirmed baseline facts

- `app/reporting/html_exporter.py` = **1,861 LOC** — CONFIRMED, largest single file in the
  codebase by a wide margin (next-largest is `virustotal.py` at 1,189).
- `app/database/repository.py` = 613 LOC, parameterized SQL — CONFIRMED via prior audit and
  spot-check; no migration/versioning table observed in `connection.py`/`models.py` — LIKELY
  no schema-version tracking exists (worth a direct confirm in Phase 4B before writing
  migration code).
- `app/gui/components/layout/panel.py::Panel` alongside `app/gui/widgets/panel.py` and
  `app/gui/components/layout/section_header.py` alongside `app/gui/widgets/section_header.py`
  — CONFIRMED duplicate/legacy-vs-new component pairs exist on disk simultaneously.
- Design-token system is real and non-trivial: `app/gui/design/tokens/{colors, spacing,
  radius, typography, elevation, duration, easing, opacity}.py` — eight distinct token
  categories — CONFIRMED. This is genuine design-system groundwork worth porting forward,
  not rebuilding from nothing.
- CLI is intentionally thin (76 LOC) — CONFIRMED — meaning the CLI is already a second,
  working "headless client" proof that the domain core is UI-agnostic. This is direct
  evidence for how a future Python-domain/Tauri-frontend split should work.

### 1.8 UNKNOWN (flag for Phase 4B, do not guess)

- Exact concurrency model of `analysis_worker.py` (QThread vs QThreadPool vs QRunnable) —
  needs a direct read.
- Whether `database/connection.py` does any pragma/journaling configuration relevant to a
  future multi-process (Tauri sidecar) access pattern.
- Full shape of `app/services/*` dashboard services' return types (needed to design the
  IPC/API response schemas precisely, not just approximately).
- Whether any test currently exercises the two-event-bus interaction (if not, that itself is
  a testing gap to fix in Phase 4B before touching the event system).

---

## 2. TARGET ARCHITECTURE

### 2.1 Layer diagram

```
┌─────────────────────────────────────────────────────────────┐
│  React + TypeScript (Frontend)                                │
│  presentation, view models, client-side cache, motion         │
└───────────────────────────▲─────────────────────────────────┘
                             │ typed IPC commands / events
┌───────────────────────────┴─────────────────────────────────┐
│  Tauri (Rust) — desktop shell + capability boundary            │
│  window lifecycle, packaging, permissions, native OS calls,    │
│  process supervision of the Python sidecar, secret-store glue  │
└───────────────────────────▲─────────────────────────────────┘
                             │ local, loopback-only JSON-RPC/HTTP
┌───────────────────────────┴─────────────────────────────────┐
│  Python domain/application boundary (FastAPI/uvicorn sidecar)  │
│  command handlers, event publisher, DTO ↔ domain mapping        │
├─────────────────────────────────────────────────────────────┤
│  Python domain services                                        │
│  extraction · normalization · scoring · TI orchestration ·     │
│  correlation · reporting · investigation lifecycle              │
├─────────────────────────────────────────────────────────────┤
│  Persistence — SQLite (repository pattern, migrations)         │
└─────────────────────────────────────────────────────────────┘
```

Rust/native capabilities sit **beside** this stack, not inside the Python boundary:

```
Tauri (Rust) also owns, directly, with no Python round-trip:
  - native file dialogs / filesystem access under explicit capability scopes
  - OS notifications
  - OS credential store (Windows Credential Manager / keychain) read-write
  - (future) YARA scanning, file hashing, PE metadata — isolated native workers
```

### 2.2 IPC mechanism decision

**Options evaluated:**

| Option | Verdict | Why |
|---|---|---|
| Tauri `invoke` calling into Rust which calls Python via FFI | Rejected | Forces Rust to own a Python runtime binding; couples the native/security boundary to a scripting runtime; makes Python packaging Rust's problem too. |
| Subprocess protocol over stdio (line-delimited JSON) | Rejected as primary | Works, but no free tooling for typed schemas, harder to support concurrent long-running streaming (progress events) cleanly, harder to debug/test independently of Tauri. |
| Named pipes | Rejected | Platform-divergent implementation (Windows named pipes vs Unix domain sockets) adds real complexity for no benefit over loopback TCP on a desktop app that already only targets one machine. |
| **Local HTTP/JSON-RPC service on `127.0.0.1`, launched and supervised by Tauri as a sidecar process** | **Chosen** | Reuses a mature, testable, independently-runnable Python web stack (FastAPI). Same server underlies both the GUI IPC layer *and* can be reused for CLI/automation later. Debuggable with ordinary HTTP tools during development. Natural home for a WebSocket/SSE channel for the event stream (§3, §16). Trivially portable if a browser-based mode is ever wanted. |

**Concrete shape:**

- Tauri launches `soc-iq-backend` (a PyInstaller/py-build-standalone sidecar binary — see §24)
  bound to `127.0.0.1:<ephemeral-port>`, chosen at startup and passed to the frontend via a
  Tauri command, never hard-coded.
- The port binds to loopback only; Tauri's capability config denies the frontend any network
  capability except calling that single origin (see §6, §7).
- Commands = `POST /commands/{name}` with a JSON body and JSON response (§16).
- Events = a single `GET /events` Server-Sent-Events (or WebSocket) stream the React app
  subscribes to once, so backend event publication is push-based, not polled.
- Rust never calls Python directly; Rust only supervises the process (spawn/health-check/kill)
  and passes the port to the frontend. This keeps "Tauri must not become the business logic
  layer" true by construction — there is no code path in Rust that contains domain logic.

This is a **PROPOSED** decision (ADR-006) — not yet implemented.

---

## 3. DATA / COMMAND / EVENT / STATE MODEL

| Category | Owner | Notes |
|---|---|---|
| **Data** (investigations, IOCs, TI results, risk scores, reports, settings) | Python domain + SQLite | Single source of truth. Frontend never persists domain data locally beyond a short-lived cache (§9). |
| **Commands** (imperative requests: analyze_report, create/delete_investigation, enrich_ioc, export_report, search_investigations) | Python application boundary (FastAPI handlers) | Frontend issues commands; Tauri only relays filesystem/native commands it owns itself (open file dialog, save export). |
| **Events** (analysis.started/progress/completed/failed, investigation.created/updated/deleted, ti.enrichment.*) | Python publishes; Tauri relays unmodified; React subscribes | One schema, one publisher, versioned (§15). |
| **State** (current page, selected investigation/IOC, active analysis, UI-only flags) | React (client-side state store, e.g. Zustand/Redux-lite) | Never persisted server-side. Derived from the last-known event/command responses. |

This directly fixes problem #1 (checkboxes not controlling the pipeline): pipeline options
become **fields on the `analyze_report` command payload**, not GUI-local booleans, so the
backend is the single place that decides what actually ran, and the frontend just reflects
the command it sent plus the events it gets back.

---

## 4. PYTHON DOMAIN ARCHITECTURE (target)

Preserving, not rewriting, the modules identified in §1.2. Target package shape:

```
backend/
├── app/
│   ├── domain/            # pure models + business rules (scoring, verdict normalization)
│   ├── application/       # command handlers, use-cases, event publisher
│   ├── providers/         # threat_intel provider adapters (NEW abstraction, see §5)
│   ├── repositories/      # persistence interfaces + SQLite implementation
│   ├── reporting/         # exporters (existing, HTML split up — see §18)
│   ├── api/                # FastAPI app: command routes + SSE/WS event route (NEW, thin)
│   ├── cli.py              # existing thin CLI, now calls application/ layer directly (kept)
│   └── settings/           # existing, + secret-store adapter (see §22)
└── tests/
```

### 4.1 File-level mapping (representative, not exhaustive)

| CURRENT FILE | TARGET LOCATION | ACTION |
|---|---|---|
| `app/extractor.py`, `app/analyzer.py` | `backend/app/domain/extraction/` | **PRESERVE** logic, **ADAPT** module boundary |
| `app/scoring/engine.py`, `scoring/models.py` | `backend/app/domain/scoring/` | **PRESERVE** |
| `app/threat_intel/service.py` | `backend/app/application/threat_intel_orchestrator.py` | **REFACTOR** to depend on `ThreatIntelProvider` protocol instead of `VirusTotalClient` directly |
| `app/threat_intel/virustotal.py` | `backend/app/providers/virustotal_provider.py` | **ADAPT** — wrap existing client behind the new interface; internal HTTP logic **PRESERVED** |
| `app/database/repository.py`, `connection.py`, `models.py`, `service.py` | `backend/app/repositories/sqlite/` | **PRESERVE** + **INTRODUCE** migration runner |
| `app/reporting/*` | `backend/app/reporting/*` | **PRESERVE** service/builder/json/csv/markdown/pdf; **REDESIGN** html_exporter internals only (§18) |
| `app/settings/*` | `backend/app/settings/*` | **ADAPT** — add secret-store-backed key storage, keep existing redacted-repr model |
| `app/services/*` (dashboard/correlation/risk-explanation) | `backend/app/application/*_service.py` | **PRESERVE** logic; exposed via new command handlers instead of being called directly by Qt controllers |
| `app/gui/**` (all PySide6) | *(none — retired)* | **REMOVE**, replaced by React frontend; **PRESERVE** the design-token *values* (ported, see §10), not the Qt widget code |
| `app/gui/controllers/*_controller.py`, `app/gui/services/*` | `backend/app/application/*` (command handlers) | **REFACTOR** — these already separate "what to do" from "how to paint it"; that separation is exactly what a command handler needs |
| `app/cli.py` | `backend/app/cli.py` | **PRESERVE**, re-pointed at `application/` layer |

The controllers/services under `app/gui/controllers` and `app/gui/services` are the most
important discovery here: they **already** express intent (analyze, list, delete) somewhat
separately from Qt painting code, so they migrate into command handlers with logic changes,
not logic invention.

---

## 5. THREAT INTELLIGENCE ARCHITECTURE (priority)

### 5.1 Provider interface (PROPOSED)

```python
class ThreatIntelProvider(Protocol):
    name: str  # "virustotal", "abuseipdb", "otx"
    supported_ioc_types: set[IOCType]

    async def lookup(self, ioc: IOC) -> ProviderResult: ...
    def is_configured(self) -> bool: ...
```

### 5.2 Canonical verdict model (PROPOSED — the missing piece from §1.5)

```python
class Verdict(str, Enum):
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    CLEAN = "clean"
    NOT_FOUND = "not_found"        # provider has no record — explicitly NOT "clean"
    UNSUPPORTED = "unsupported"    # provider doesn't support this IOC type
    NO_API_KEY = "no_api_key"
    UNAVAILABLE = "unavailable"    # timeout / connection error
    RATE_LIMITED = "rate_limited"
    ERROR = "error"

@dataclass(frozen=True)
class ProviderResult:
    provider: str
    ioc: IOC
    verdict: Verdict
    confidence: float | None       # 0-1, None where provider gives no confidence signal
    raw_detection_ratio: str | None  # e.g. "12/94", provider-specific, display-only
    source_url: str | None
    queried_at: datetime
    error_detail: str | None = None
```

`NOT_FOUND != CLEAN` is enforced by construction: a provider adapter that returns "no record"
must return `Verdict.NOT_FOUND`, never `Verdict.CLEAN`. `Verdict.CLEAN` is reserved for a
provider explicitly asserting "checked, zero detections."

### 5.3 Aggregation across providers

A single IOC in an investigation accumulates a `list[ProviderResult]`. The domain layer
computes a single **display verdict** via an explicit, testable policy (e.g. "malicious if
any provider says malicious; else suspicious if any provider says suspicious; else clean only
if at least one provider explicitly returned clean; else not_found/unavailable") — this policy
is itself a small, independently unit-testable function, distinct from any one provider's
logic, which is the architectural gap the current single-provider code has no room for.

### 5.4 Migration of VirusTotal

`virustotal.py`'s actual HTTP/parsing logic is **PRESERVED** almost entirely — it becomes the
body of `VirusTotalProvider.lookup()`, translating VT's raw response into a `ProviderResult`.
`ThreatIntelService` is **REFACTORED** into an orchestrator that holds `list[ThreatIntelProvider]`
instead of one concrete client.

---

## 6. SECURITY ARCHITECTURE

### 6.1 Threat model (selected entries)

| Threat | Mitigation / owning layer |
|---|---|
| Malicious report file (crafted to exploit a parser) | Extraction runs in the Python sidecar only; size caps + timeout on parsing; never executed, never shelled out |
| Malicious URL/domain/IP as IOC | Treated as inert data end-to-end; never rendered as clickable-by-default, never used to construct shell commands (matches CONFIRMED existing no-`shell=True`/no-`eval`/no-`exec` posture — this must be preserved as a hard rule for all new code, Rust included) |
| Oversized report / regex DoS | Input size limits at the API boundary; scoring/extraction regexes reviewed for catastrophic backtracking as part of Phase 4B hardening pass |
| Path traversal on export | Export path resolution happens in Rust/Tauri's capability-scoped filesystem API, not by trusting a string the frontend sends |
| API-key theft | Key lives in OS secure storage (§22), never sent to the frontend in plaintext, never logged (existing redacted-repr behavior preserved) |
| Frontend compromise (malicious/compromised JS dependency) | Frontend has **zero** direct filesystem/network capability beyond calling the local backend origin and invoking whitelisted Tauri commands; it cannot reach the internet, read arbitrary files, or spawn processes |
| IPC/command abuse (frontend sends unexpected command) | All commands validated against explicit schemas server-side (Pydantic) before touching domain logic; unknown/malformed commands rejected, not "best-effort" parsed |
| Malicious Tauri command misuse | Tauri capability manifest enumerates the exact allowed commands per window; nothing is "on by default" |
| Dependency/supply-chain | Lockfiles for all three ecosystems + SBOM (§23) |

### 6.2 Trust boundaries

```
UNTRUSTED: report files, IOC values, external TI API responses, frontend-originated input
TRUSTED (within its own boundary, but least-privilege toward its neighbors):
  React        — trusted to render, untrusted to decide filesystem/network access
  Tauri/Rust   — trusted to enforce capabilities, untrusted to contain business logic
  Python core  — trusted to hold domain logic + validated data, untrusted input in = validated first
```

- **React may request:** invoke a fixed, versioned set of Tauri commands; call the local
  backend's documented command endpoints; nothing else.
- **Tauri may execute:** the explicit native operations enumerated in its capability config
  (open/save dialog, notification, credential-store read/write, sidecar lifecycle) and
  nothing dynamically constructed from frontend strings without validation.
- **Rust may access:** filesystem paths returned by native dialogs or explicitly
  user-approved app-data directories; no arbitrary path from the frontend is trusted as-is.
- **Python may access:** its own SQLite file, its own app-data directory, the network only to
  configured TI provider endpoints (allow-listed hosts).

---

## 7. TAURI CAPABILITY ARCHITECTURE

```
Frontend request (invoke("export_report", {investigationId}))
   → Tauri command handler (Rust)
   → permission check against capabilities.json for the calling window
   → native dialog for save location (user-in-the-loop, not a raw path from JS)
   → native filesystem write, scoped to the chosen path only
   → result returned to frontend / "export.completed" event emitted
```

Explicit **least-privilege** capabilities (PROPOSED, illustrative):

- `dialog:allow-open`, `dialog:allow-save` — yes, scoped
- `fs:allow-write` — **not** granted broadly; writes only happen inside the Rust command
  handler after a user-driven dialog, never via a generic "write this path" command exposed
  to JS
- `notification:allow-notify` — yes
- `shell:*` — **denied entirely**, no exceptions (matches the existing Python-side
  no-`shell=True` discipline — this becomes a cross-language rule, not just a Python one)
- `http:*` from the frontend — **denied**; all network access is mediated by the Python
  sidecar

---

## 8. RUST ARCHITECTURE

| Responsibility | Timing |
|---|---|
| Tauri shell, window lifecycle, packaging | **NOW** |
| Sidecar process supervision (spawn Python backend, health-check, restart, clean shutdown) | **NOW** |
| Capability-scoped native filesystem ops (open/save dialogs, export writes) | **NOW** |
| OS notifications | **NOW** |
| OS credential-store read/write for the TI API key | **NOW** |
| File hashing (SHA-256 of an uploaded report, for audit trail) | **LATER** |
| YARA scanning of uploaded reports/attachments | **LATER** |
| PE metadata / malware artifact inspection | **OPTIONAL / Research** |
| Any risk scoring, TI orchestration, or investigation logic | **NEVER** — stays Python |

Rust is deliberately kept to shell + native-capability duties now, with a clear, narrow
runway into security-native features later, so the language is justified by what it's
actually asked to do, not padded.

---

## 9. REACT + TYPESCRIPT FRONTEND ARCHITECTURE

```
src/
├── app/                 shell, routing, providers
├── features/
│   ├── dashboard/
│   ├── analyze/          (pipeline options as real command fields, not local-only state)
│   ├── investigation-workspace/
│   ├── ioc-explorer/
│   ├── threat-intel/
│   ├── risk/
│   ├── history/
│   ├── reports/
│   └── settings/
├── shared/
│   ├── components/       (design-system components, see §10)
│   ├── api/               typed IPC client (generated from the JSON schemas in §16)
│   ├── events/             SSE/WS subscription hook, dispatches into the state store
│   ├── view-models/        map backend DTOs → presentation-ready shapes
│   └── state/              Zustand (or similar) store: UI/session state only
└── styles/                design tokens (ported, §10)
```

Async workflow pattern: command → optimistic local "pending" state → event stream confirms
(`analysis.completed`) or corrects (`analysis.failed`) → view model updates. No client-side
polling; the event stream is the source of truth for anything long-running.

---

## 10. DESIGN SYSTEM (porting the existing token architecture)

The existing 8-category token system (`colors, spacing, radius, typography, elevation,
duration, easing, opacity`) maps directly to CSS custom properties / a TS token module —
this is **PRESERVED as values**, **REDESIGNED as implementation** (Python/Qt objects →
TypeScript constants + CSS variables):

```
tokens/
├── color.ts        base + semantic (bg/surface/border/text) + status (malicious/suspicious/clean/unknown)
├── spacing.ts
├── radius.ts
├── typography.ts
├── elevation.ts     → box-shadow scale
├── duration.ts      → motion timing scale (feeds §11 directly)
├── easing.ts        → cubic-bezier scale
└── opacity.ts
```

Cybersecurity-specific semantic colors (malicious/suspicious/clean/not-found/unavailable)
are defined once here and consumed everywhere a verdict is rendered, so the "NOT_FOUND !=
CLEAN" distinction from §5.2 is visually distinct too, not just data-distinct.

---

## 11. MOTION / ANIMATION SYSTEM

Principles (adapted from Framer Motion / motion.dev conventions, not copied):

- **Duration scale:** micro 100ms, small 150ms, base 250ms, large 400ms — driven by the
  ported `duration` tokens.
- **Easing scale:** standard ease-out for entrances, ease-in for exits, a slightly
  overshot spring reserved for one thing only — the risk-score gauge transition — so it
  reads as a meaningful moment, not decoration.
- **Entrance/exit rules:** page transitions cross-fade + slight vertical slide (8px);
  panels within a page use scale+fade, never full-page slide, to keep spatial continuity
  inside the investigation workspace.
- **IOC discovery / TI status transitions:** verdict badges animate a state change (e.g.
  "pending → malicious") with a color + icon morph, not a full re-render flash.
- **Skeleton shimmer:** used only for data genuinely loading over the wire (investigation
  fetch, TI enrichment in progress) — never used to fake latency.
- **Reduced-motion:** `prefers-reduced-motion` disables all non-essential transitions;
  state-changing animations (verdict updates) degrade to instant color change, never
  disappear entirely (status changes must remain perceivable).
- **When NOT to animate:** dense data tables (IOC lists, history), form inputs, anything
  in the command palette's result list beyond a 100ms fade — SOC analysts scanning many
  rows need stability, not motion.

---

## 12. FRONTEND INFORMATION ARCHITECTURE

- **Primary nav (persistent sidebar):** Dashboard · Analyze · Investigations · IOC Explorer ·
  Threat Intel · Risk · Reports · Settings.
- **Investigation-centric secondary nav:** once inside an investigation, the workspace tabs
  (§13) replace the need to navigate away and back.
- **Global search / command palette** (`Cmd/Ctrl+K`): jump to any investigation, IOC, or
  action (e.g. "export current investigation as PDF") without leaving context.
- **Dashboard** targets 1440×900 without scrolling via a fixed 12-column grid (KPI row +
  queue + IOC distribution + timeline as defined panel sizes, not stacked cards that grow
  unbounded); at 1280×720 the same grid collapses the timeline panel into a secondary tab
  rather than introducing page-level vertical scroll.

---

## 13. INVESTIGATION WORKSPACE

```
Investigation
├── Overview        summary, key metrics, quick actions
├── IOCs             extracted indicators, filterable by type/verdict
├── Threat Intel      per-IOC, per-provider results (NOT_FOUND shown distinctly from CLEAN)
├── Risk               explainable score breakdown (weights visible, not a black-box number)
├── Timeline            chronological event/analysis history for this investigation
├── Correlation          links to related investigations sharing IOCs
├── Evidence              source report(s), extracted artifacts
└── Reports                export history + regenerate
```

A persistent left rail within the workspace (not top tabs that reset scroll position) lets
an analyst jump Overview → IOCs → Threat Intel without losing the selected IOC — the
selected-IOC id lives in the frontend state store (§3) and survives tab switches.

---

## 14. ANALYSIS PIPELINE (fixes problem #1 by construction)

```
Report ingestion → validation → extraction → normalization
   → [TI enrichment]   ← gated by analyze_report.options.enrich_ti (server-enforced)
   → [risk scoring]    ← gated by analyze_report.options.score_risk (server-enforced)
   → correlation → persistence → events (analysis.progress ×N → analysis.completed)
   → frontend updates (via event stream, not a return value the UI must poll)
```

The three "checkboxes" become three boolean fields on the `analyze_report` command payload,
validated and enforced inside the Python application-layer handler. There is no code path by
which the UI can display "enrichment off" while the backend enriches anyway, because the
backend is the only thing that decides whether enrichment runs.

---

## 15. EVENT ARCHITECTURE (replaces the dual Qt bus)

**One** event system, published only by the Python backend, consumed identically by Rust
(pass-through) and React (subscribe):

```json
{
  "event": "analysis.progress",
  "version": 1,
  "correlation_id": "an-8f3c...",
  "investigation_id": "inv-1029",
  "timestamp": "2026-08-20T10:15:32Z",
  "payload": { "stage": "ti_enrichment", "percent": 60 }
}
```

Naming convention `domain.action` (`analysis.*`, `investigation.*`, `ti.enrichment.*`)
prevents the collision problem the current two buses have (`investigation_deleted` vs
`investigation_removed` naming the same real-world event two different ways). `version` is
present on every event from day one so payload evolution never becomes a silent breaking
change.

---

## 16. API / IPC CONTRACT (representative)

**Commands** (`POST /commands/{name}`):

```json
// analyze_report
{
  "report_source": { "type": "file", "path": "..." },
  "options": { "extract_iocs": true, "enrich_ti": true, "score_risk": true }
}

// delete_investigation
{ "investigation_id": "inv-1029" }
```

**Events** (over SSE/WS, schema per §15):
`analysis.started`, `analysis.progress`, `analysis.completed`, `analysis.failed`,
`investigation.created`, `investigation.updated`, `investigation.deleted`,
`ti.enrichment.started`, `ti.enrichment.completed`, `ti.enrichment.failed`.

Every command has a matching Pydantic request/response model in the Python API layer, from
which the TypeScript client types are generated (openapi-typescript or equivalent) — the
contract is defined once, in Python, and the frontend types are derived, not hand-duplicated.

---

## 17. DATABASE ARCHITECTURE

- **Keep SQLite** — no evidence in this checkpoint justifies Postgres; a single-user desktop
  SOC tool has no concurrent-writer requirement Postgres would solve.
- **INTRODUCE** a lightweight migration runner (e.g. a lightweight versioned-SQL-file
  approach) since none was confirmed to exist today (§1.8) — a `schema_version` table plus
  ordered `.sql` migration files is enough; no need for a heavy ORM migration framework.
- **PRESERVE** the existing repository pattern and parameterized-query discipline in
  `repository.py` — this is already correct and should not be touched beyond the migration
  wrapper.
- Provider results (§5) get their own table (`ti_results`), foreign-keyed to `iocs`, storing
  `provider, verdict, confidence, raw_payload_json, queried_at` — so multi-provider results
  compose additively instead of overwriting each other.

---

## 18. REPORTING ARCHITECTURE

- JSON/CSV/Markdown/PDF exporters: **PRESERVED** as-is; they sit behind the same
  `export_report` command regardless of frontend technology.
- HTML exporter (1,861 LOC): **REDESIGN** internals only — extract to a small template-driven
  approach (e.g. Jinja2 templates + a slim Python data-assembly layer) so the exporter's job
  becomes "assemble a context dict" rather than "hand-build a wall of HTML/CSS strings in
  Python." Output format and existing report content are preserved; only the
  implementation's shape changes. This is explicitly **not** a rewrite of what the report
  contains — it is a maintainability refactor of *how* it's built.

---

## 19. SECURITY-NATIVE FUTURE FEATURES

| Feature | Classification |
|---|---|
| Additional TI providers (AbuseIPDB, OTX) | **V1** — the provider abstraction (§5) is the prerequisite; providers themselves are additive after that lands |
| File hashing (SHA-256) on ingested reports | **V1** |
| YARA scanning | **V2** |
| Sigma rule support | **V2** |
| PE/malware metadata extraction | **Research/Future** |
| Sandbox integration | **Research/Future** |
| IOC correlation across investigations | **MVP** — correlation service already exists (`app/services/correlation_service.py`), just needs a workspace tab (§13) |
| Detection-rule authoring | **Research/Future** |

---

## 20. TESTING ARCHITECTURE

- **Python:** existing 542 tests **PRESERVED** and must stay green through every phase;
  new tests added for the provider abstraction, command handlers, and event publisher.
- **Contract tests:** the JSON schemas in §16 get golden-file tests so a backend change that
  breaks the frontend's assumptions fails CI before it reaches the frontend.
- **Rust:** unit tests for capability enforcement (a denied command must actually be denied,
  tested, not just declared).
- **React/TypeScript:** component tests (Vitest/Testing Library) for view models and
  presentation logic; no business logic should exist here to test in the first place.
- **IPC/E2E:** a small number of full-stack tests driving the real Tauri app against the real
  Python sidecar (not mocks) for the critical paths: analyze → view results → export.
- **Security tests:** path-traversal attempts against the export command, malformed-command
  payloads against the API boundary, and a capability-manifest snapshot test so a future PR
  can't silently widen Tauri permissions.

---

## 21. OBSERVABILITY

- Structured logging (JSON lines) in the Python backend, correlation_id + investigation_id
  on every log line touching an analysis.
- Audit trail: investigation create/update/delete and export actions recorded as domain
  events persisted alongside investigations (not just transient bus events).
- Debug mode: verbose event/command logging toggle, off by default.
- Explicit redaction: API keys and full IOC raw report content are never logged at INFO
  level; only IDs/hashes are, extending the existing settings redaction discipline
  (§1.6) to the logging layer generally.

---

## 22. SECRETS / CONFIGURATION

- **PROPOSED:** move `virustotal_api_key` storage from plaintext settings JSON into the OS
  secure store — Windows Credential Manager on Windows (the confirmed primary target,
  matching "Windows desktop packaging" in your brief), with a keychain/libsecret path noted
  for future macOS/Linux support.
- Rust owns the credential-store read/write (native capability, §7, §8); Python receives the
  key at sidecar startup via a local, short-lived handoff (e.g. an env var set only for the
  child process, never written to a Python-owned file) rather than Python touching the OS
  keystore API itself — keeps "who can read the keystore" to one, audited, native layer.
- **Development fallback:** `.env`-style local override for running the Python backend
  standalone during development, clearly excluded from production packaging.
- The existing redacted `__repr__` on `ApplicationSettings` is **PRESERVED** regardless of
  where the value is ultimately sourced from.

---

## 23. DEPENDENCY / SUPPLY-CHAIN SECURITY

- Python: replace the confirmed minimum-version `requirements.txt` with a locked
  `requirements.lock` (pip-tools or uv-generated), matching problem #9.
- Rust: `Cargo.lock` committed (default behavior, just enforced in CI).
- Frontend: `pnpm-lock.yaml` committed and CI-enforced.
- Dependency auditing: `pip-audit`, `cargo audit`, `pnpm audit` in CI on every PR.
- SBOM: generated at release time (e.g. CycloneDX) covering all three ecosystems.
- Reproducible builds / signed artifacts: tracked as a **V1** goal, not MVP — real value once
  the app is distributed beyond the author, not before.

---

## 24. PACKAGING / RELEASE

- **Python runtime problem, solved explicitly:** the Python backend is compiled to a
  standalone sidecar binary (PyInstaller or py-build-standalone) and bundled inside the
  Tauri app — end users never need Python installed. This directly answers "do not assume
  Python is magically available."
- Tauri bundles the sidecar binary + the Rust shell + the built React app into a single
  Windows installer (MSI/NSIS via `tauri-bundler`).
- App-data directory: OS-appropriate (`%APPDATA%/SOC-IQ` on Windows) holds the SQLite DB,
  logs, and exported reports' default location — matching the existing `export_directory`
  setting concept.
- Update strategy: Tauri's built-in updater (signed update manifests) — tracked as **V1**,
  not required for an initial packaged release.
- Logs and DB migrations run automatically on sidecar startup, before the API server accepts
  commands, so a version bump never leaves a half-migrated DB reachable by the frontend.

---

## 25. DIRECTORY STRUCTURE (target, mapped from current)

```
soc-iq/
├── frontend/                  NEW — React + TypeScript app (§9)
├── src-tauri/                 NEW — Rust shell (§8)
├── backend/                   FROM current app/ (§4), domain core preserved
│   ├── app/
│   └── tests/                 FROM current tests/ (542 tests, preserved)
├── docs/                      FROM current docs/, + this document + new ADRs (§28)
├── scripts/                   NEW — build/package/lockfile-refresh scripts
└── samples/                   FROM current samples/ (kept for manual testing/demos)
```

`app/gui/**` has no target directory — it is retired (§4.1), superseded by `frontend/` +
`src-tauri/`.

---

## 26. MIGRATION PLAN

| Phase | Objective | Key modules touched | Deliverables | Exit criteria |
|---|---|---|---|---|
| **4A** (this doc) | Architecture reset | none | This master plan | Reviewed/approved |
| **4B** | Domain boundary hardening | `app/gui/controllers`, `app/gui/services` → extracted logic reviewed against §4.1 mapping; fill §1.8 unknowns | Confirmed answers to UNKNOWNs; controller/service logic inventoried | 542 tests still green; no behavior change |
| **4C** | TI provider abstraction | `threat_intel/*` | `ThreatIntelProvider` protocol + VT adapter + verdict model (§5) | VT still works end-to-end via new interface; new unit tests for verdict policy |
| **4D** | Unified command/event contract | new `backend/app/api/`, `application/` | FastAPI sidecar exposing `analyze_report` + a handful of read commands over HTTP+SSE, still driven by a temporary throwaway test client (no frontend yet) | Contract tests (§20) passing |
| **4E** | Rust/Tauri foundation | new `src-tauri/` | Empty Tauri shell that can launch the 4D sidecar and hit one command | Sidecar lifecycle (spawn/health/kill) proven |
| **4F** | React/TS design system | new `frontend/` | Ported tokens (§10), base component library | Storybook-style component gallery |
| **4G** | Application shell | frontend nav | Sidebar, routing, command palette skeleton | Navigable shell against mock data |
| **4H** | Dashboard | frontend + `dashboard_*` command handlers | Working dashboard against real backend | Fits 1440×900 without scroll (§12) |
| **4I** | Analysis workflow | analyze feature + `analyze_report` command | Working analyze page with real per-option gating (fixes problem #1) | Backend enforces options, verified by test |
| **4J** | Investigation workspace | workspace feature | Overview/IOCs/Evidence tabs working | Selected-IOC state survives tab switches |
| **4K** | TI/Risk views | remaining tabs | Multi-provider display, NOT_FOUND vs CLEAN visibly distinct | Manual + snapshot test |
| **4L** | Reporting | `html_exporter` refactor (§18) + export UI | Template-driven HTML exporter, same output content | Existing report tests still pass |
| **4M** | Security hardening | `src-tauri/capabilities/*`, secret store (§22) | Least-privilege capability manifest, keystore-backed API key | Security tests (§20) passing |
| **4N** | Integration | full stack | End-to-end flows working together | E2E tests green |
| **4O** | Migration completion | remove `app/gui/**` | PySide6 GUI retired | CLI + new frontend are the only clients |
| **4P** | Final audit | whole repo | Updated audit doc, updated recruiter scoring (§29) | Ready for portfolio/interview use |

Each phase keeps the previous phase's tests green — no phase is allowed to leave the 542-test
Python baseline broken, per your rule #7.

---

## 27. PRESERVE / ADAPT / REDESIGN / REMOVE MATRIX

| Subsystem | Classification | Notes |
|---|---|---|
| extractor | PRESERVE | move package, logic unchanged |
| analyzer | PRESERVE | |
| scoring | PRESERVE | explainability is a real strength, keep the shape |
| threat_intel (orchestration) | REFACTOR | becomes provider-agnostic orchestrator |
| VirusTotal client | ADAPT | wrapped as one provider adapter, internals kept |
| database | PRESERVE + ADAPT | add migration runner only |
| settings | ADAPT | add secure-store-backed key, keep redacted repr |
| reporting (json/csv/md/pdf) | PRESERVE | |
| reporting (html) | REDESIGN | template-driven internals, same output |
| CLI | PRESERVE | re-pointed at application layer |
| PySide6 GUI (pages/widgets) | REMOVE | superseded by React frontend |
| ApplicationState / dual event buses | REMOVE | superseded by unified event model (§15) |
| workers (`analysis_worker.py`) | REMOVE (Qt-specific) | equivalent async execution lives in the FastAPI command handler |
| GUI pages | REMOVE | replaced by React features |
| GUI widgets (dashboard_*, ioc_*, risk_*) | REMOVE (Qt code) / REDESIGN (concept) | the *concepts* they render (KPI section, risk gauge, IOC distribution) carry forward as React components |
| components/layout/panel.py + widgets/panel.py duplicate pair | REMOVE both | superseded entirely by React layout primitives — no reason to pick a "winner" between two Qt implementations that are both being retired |
| design tokens | PRESERVE (values) / REDESIGN (implementation) | ported to TS/CSS |
| theme (stylesheet_builder, theme_manager) | REMOVE (Qt-specific) | concept (dark SOC theme) carries forward via tokens |
| tests (542 Python) | PRESERVE | must stay green throughout |

---

## 28. ARCHITECTURE DECISION RECORDS (index)

- **ADR-001** — Python remains the domain core (all business logic stays in `backend/app/`).
- **ADR-002** — React + TypeScript as the presentation layer.
- **ADR-003** — Tauri as the desktop shell and capability boundary.
- **ADR-004** — Rust owns native capabilities only, never domain logic.
- **ADR-005** — SQLite remains the database; no Postgres migration without concrete cause.
- **ADR-006** — Local-loopback HTTP+SSE sidecar as the sole IPC mechanism between Rust and
  Python (rejected alternatives: FFI, stdio, named pipes — see §2.2).
- **ADR-007** — Multi-provider threat-intel abstraction with an explicit `NOT_FOUND != CLEAN`
  verdict model.
- **ADR-008** — API keys stored via OS secure storage, handed to the Python sidecar at
  process start, never persisted in plaintext or exposed to the frontend.
- **ADR-009** — Staged migration (Phases 4B–4P); PySide6 GUI is retired only after the React
  frontend reaches feature parity (Phase 4O), not before.
- **ADR-010** — Least-privilege Tauri capability manifest; frontend has no direct filesystem
  or network access.

(Full ADR text — context/decision/alternatives/consequences/rejected-alternatives — to be
written out as individual documents in `docs/adr/` during Phase 4B, once §1.8 unknowns are
resolved and any assumption here that turns out wrong can be corrected before it's codified.)

---

## 29. RECRUITER / INTERVIEW IMPACT

| Dimension | CURRENT | TARGET | Why it changes |
|---|---|---|---|
| Cybersecurity depth | 6/10 | 8/10 | Real multi-provider TI abstraction + explicit verdict semantics is a genuine SOC-engineering concept, not UI polish |
| Security engineering | 6/10 | 8/10 | Explicit trust boundaries, least-privilege Tauri capabilities, OS-backed secret storage — concrete artifacts to walk through in an interview |
| Architecture | 6/10 | 8-9/10 | Clean layering across three languages with one enforced IPC boundary and no logic duplication is a strong systems-design story |
| Backend | 7/10 | 8/10 | Domain core preserved and *proven* reusable (already powers CLI + GUI, will power API too) |
| Frontend | 6/10 | 8/10 | Modern React/TS with a real design system and motion language |
| Rust/systems engineering | n/a | 6-7/10 | Justified, scoped native-capability layer — defensible under questioning because it's narrow, not padded |
| Threat intelligence | 5/10 | 8/10 | The provider-abstraction work directly targets this weakness |
| Testing | 7/10 | 8/10 | 542 Python tests preserved + contract/E2E/security tests added across the new boundary |
| Production readiness | n/a | 6-7/10 | Real packaging story (no "assumes Python is installed"), lockfiles, SBOM |
| Portfolio differentiation | 6/10 | 8-9/10 | "SOC tool with a genuinely provider-agnostic TI layer and an enforced security boundary between UI and native code" is a defensible, specific claim, not a buzzword list |

**What would still prevent a 9-10/10 across the board:** no real production deployment/users,
no second TI provider actually implemented yet (only the abstraction), no independent
security review, and YARA/Sigma/sandbox features remaining "Future" rather than shipped.
Those are legitimate next milestones beyond this document's scope, not gaps in the
architecture itself.

---

## 30. FINAL ARCHITECTURE VERDICT

**A. Is Python + Rust + Tauri + React + TypeScript justified for SOC-IQ?**
Yes, conditionally: only because each language is given a *narrow, non-overlapping*
responsibility (§2, §8) and the domain core is preserved rather than duplicated. If Rust or
TypeScript were asked to reimplement scoring/TI logic, the answer would be no.

**B. Concrete engineering value per language:**
Python — proven domain core, reused by CLI/GUI/API alike. Rust/Tauri — a real least-privilege
security boundary the current all-Python-desktop-app has no equivalent of today. React/TS —
presentation quality and interaction design the current PySide6 UI cannot match without
substantial custom Qt work.

**C. Parts that should never be rewritten:** extraction, scoring, database repository logic,
the CLI's thin/decoupled shape, the design-token *values*.

**D. Parts that should be redesigned:** the event system (unify), the HTML exporter
(template-driven), the TI service (provider-abstracted), secret storage (OS-backed).

**E. What should be implemented first (after this document is approved):** Phase 4B — resolve
the §1.8 unknowns and formally inventory the `app/gui/controllers` / `app/gui/services` logic
against the §4.1 mapping, *before* touching the event system or writing any Rust/React code.

**F. What should NOT be built yet:** YARA/Sigma/sandbox integration, a second TI provider
implementation (build the abstraction in 4C first, add AbuseIPDB after), the OS updater.

**G. What would make this genuinely impressive to a cybersecurity recruiter:** the
NOT_FOUND-vs-CLEAN verdict model and the explicit Tauri capability manifest are the two most
interview-defensible artifacts — both are specific, correct, security-reasoning decisions a
recruiter can ask "why" about and get a real answer, not "because it's a common stack."

**H. Architecture mistakes to avoid during migration:** letting Rust or TypeScript acquire
domain logic "temporarily"; retiring the PySide6 GUI before the React frontend has real
parity; skipping the migration runner and hand-editing the SQLite schema; treating the two
existing event buses as mergeable-by-renaming rather than replacing with the versioned model
in §15.

---

## Final Summary Outputs

### 1. Final target architecture diagram — see §2.1

### 2. Technology responsibility matrix

| Layer | Owns | Never does |
|---|---|---|
| React/TS | UI, view models, motion, client state | persistence, scoring, TI logic, direct SQLite/network access |
| Tauri/Rust | shell, packaging, capabilities, native OS calls, sidecar supervision | business logic |
| Python | domain logic, persistence, TI orchestration, reporting | native OS capability enforcement |
| SQLite | durable storage | — |

### 3. Current→target migration matrix — see §4.1 and §27

### 4. Phase-by-phase roadmap — see §26

### 5. ADR index — see §28

### 6. Top 10 architectural risks
1. Sidecar process management (crash/zombie process) mishandled by Rust supervision.
2. Event-schema versioning skipped, causing silent frontend/backend drift.
3. HTML exporter refactor accidentally changes report output content.
4. Migration runner introduced late, after schema drift has already occurred manually.
5. Command/DTO validation gaps letting malformed frontend input reach domain logic.
6. Controller/service logic in `app/gui/*` turning out to be more Qt-entangled than §1.8 assumes, requiring more extraction work than planned.
7. Provider abstraction designed too VirusTotal-shaped, requiring rework when adding provider #2.
8. Sidecar startup/migration race allowing the UI to query a half-migrated DB.
9. Frontend caching diverging from server state without the event stream being the sole source of truth.
10. Scope creep: Rust/YARA work starting before the MVP native-capability layer is solid.

### 7. Top 10 security risks
1. Tauri capability manifest over-scoped "to save time" during 4E/4G.
2. API key handoff to the sidecar process leaking via a logged environment dump.
3. Export path trusted from frontend input instead of native dialog result.
4. Local HTTP sidecar accidentally bound to `0.0.0.0` instead of `127.0.0.1`.
5. Regex DoS in extraction/scoring not actually re-audited during migration.
6. Dependency supply-chain issue in a new npm/Rust crate not caught before lockfile adoption.
7. SSE/WS event endpoint left unauthenticated to non-localhost callers if port forwarding is misconfigured on a shared machine.
8. Secret-store fallback (dev `.env`) accidentally shipped in a release build.
9. Report file parsing not sandboxed/size-capped, enabling resource-exhaustion via a crafted upload.
10. Verdict-aggregation policy (§5.3) silently downgrading MALICIOUS to a lower severity due to a provider bug — needs its own test coverage, not just "trust the providers."

### 8. Top 10 recruiter differentiators
1. Real multi-provider TI abstraction with an explicit NOT_FOUND-vs-CLEAN model.
2. Explicit trust-boundary diagram and least-privilege Tauri capability manifest.
3. A domain core proven reusable across three clients (CLI, retired GUI, new API/frontend).
4. Staged, tested migration plan rather than a rewrite — shows engineering judgment.
5. OS-backed secret storage instead of plaintext API keys.
6. Explainable risk scoring preserved and exposed through a modern UI.
7. Correlation across investigations as a first-class workspace tab.
8. Contract-tested IPC boundary (schema-driven, not "hope it matches").
9. 542+ preserved tests plus new contract/security/E2E layers — testing story spans the whole stack.
10. A packaging story that doesn't assume Python is installed on the target machine.

### 9. "Do not do this" architecture rules
- Do not let Rust or TypeScript implement scoring, TI orchestration, or persistence.
- Do not give the frontend direct SQLite or network access.
- Do not treat the two current event buses as a naming fix — replace with the unified model.
- Do not retire the PySide6 GUI before the React frontend has real feature parity.
- Do not add a second TI provider before the abstraction (§5) exists.
- Do not store the API key in plaintext anywhere in the target architecture.
- Do not grant Tauri `shell:*` or unrestricted `fs:*` capabilities.
- Do not skip the SQLite migration runner "for now."
- Do not rewrite the HTML exporter's *content*, only its implementation shape.
- Do not add Rust/YARA scope before the native-capability MVP (§8) is solid.

### 10. Exact first implementation task after this document is approved
**Phase 4B, step one:** directly read `app/gui/workers/analysis_worker.py`,
`app/database/connection.py`, and every file under `app/services/` in full, to resolve the
§1.8 UNKNOWNs and produce a verified, file-by-file inventory of exactly what logic inside
`app/gui/controllers/*` and `app/gui/services/*` must be preserved when it moves into
`backend/app/application/`. No Rust, Tauri, or React code is written until that inventory
exists and is checked against the mapping in §4.1.
