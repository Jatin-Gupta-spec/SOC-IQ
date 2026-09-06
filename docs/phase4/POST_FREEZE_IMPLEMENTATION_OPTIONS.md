# SOC-IQ — Post-Freeze Implementation Options (Part 3 Readiness Audit)

Read-only analysis. Nothing in this document was implemented; no source in
this checkpoint differs from Part 2. Source evidence cited below is from
`app/application/dto.py`, `app/application/handlers.py`,
`app/database/models.py`, the live `database/soc_iq.db` schema, and the
frontend page/hook files named.

## Current Product Reality

| Feature | Current State | Real Backend Integration | Mock/Placeholder | Known Gap |
|---|---|---|---|---|
| Dashboard | Real | `useDashboard()` → `get_dashboard_summary`, no mock imports | None | None found |
| Investigations | Real | `useInvestigationsList()` → `list_investigations`/`search_investigations` | None (comments note it replaced a prior mock collection) | None found |
| Investigation Workspace | Real (mostly) | `useInvestigation()` → `get_investigation`/`get_iocs`; `InvestigationIocWorkspace`/`InvestigationThreatIntel` sub-panels call real data via the same hook, no `runCommand` of their own | `InvestigationOverviewThreatIntel.tsx` still borrows `ThreatIntelPage`'s mock vocabulary in its labels/copy, even though the data it renders is real | Sub-panel copy/vocabulary cleanup |
| Reports | Real | Wired to `export_report` + investigation list data | None (comments note it replaced the prior mock's disabled download path) | None found |
| Analyze | Real, with one leftover mock widget | `useAnalysisExecution()` drives a real `ready → analyzing → completed/failed` flow against `analyze_report` | `mockRecentAnalysisRuns` still renders a static "recent runs" list; one branch of the page's own `InfoNote` still contains stale copy claiming execution "is not implemented" | Recent-runs list has no backing command; stale InfoNote copy |
| IOC Explorer | Mock | None | `mockIocCategories`, `mockIocRecords` | No investigation context to call `get_iocs` with (see Option 2) |
| Threat Intel | Mock | None | `mockThreatIntelProviders`, `mockThreatIntelEnrichments` | Same investigation-context gap as IOC Explorer |
| Risk | Mock | None | `mockOverallRiskScore`, `mockRiskSeverityDistribution`, `mockRiskCategories` | No `get_risk` command exists in `dispatch()` at all — out of this Part 3's scope, noted for completeness |
| Settings | Mock | None (`save_settings` exists; no read command) | `mockSettingsSections` | No `get_settings` command exists in `dispatch()` — same out-of-scope note as Risk |

## Option 1 — AnalyzePage

```
OPTION 1 IMPLEMENTATION SCOPE:
Replace the static mockRecentAnalysisRuns list and correct the one stale
InfoNote branch. No new user-facing capability is added — the real
analyze/execute/retry flow already exists and is unaffected.

ARCHITECTURAL CHANGE:
NONE

BACKEND CHANGE:
NONE — no command exists today for "recent analysis runs across
investigations" and none is required if the list is simply removed or
replaced with a real call to list_investigations (already implemented)
filtered/sorted client-side.

FRONTEND CHANGE:
Remove `mockRecentAnalysisRuns` import and its render block, or replace it
with data already available from list_investigations; correct the stale
InfoNote copy.

TEST CHANGE:
Update/remove the existing AnalyzePage test(s) that assert on the mock
recent-runs content; add a regression test asserting no mock import
remains, mirroring the pattern already used for Dashboard/Investigations/
Reports.
```

This is the only one of the three options with no open product question —
it doesn't require picking a UX direction, only removing a leftover.

## Option 2 — IOC Explorer + Threat Intel Investigation Context

### IOC Explorer
- Current data source: `mock/iocs.ts`, static.
- Current investigation context: none — the page is a top-level nav route
  (`/ioc-explorer`), not investigation-scoped.
- Existing API support: `get_iocs` exists but its request DTO
  (`GetIocsRequest`, `app/application/dto.py`) requires `investigation_id:
  int`. There is no variant that returns IOCs across all investigations.
- Existing database support: `iocs` is a `TEXT` column on the single
  `investigations` table (confirmed from the live schema), one JSON blob
  per investigation row — there is no separate, queryable IOC table.
- UI navigation implication: making this page real means either scoping it
  under an investigation route (losing its current "cross-cutting explorer"
  identity) or adding a picker/selector to a page that currently has none.

### Threat Intel
- Current data source: `mock/threatIntel.ts`, static.
- Current investigation context: none, same top-level-route situation as
  IOC Explorer (`/threat-intel`).
- Existing API support: `get_threat_intelligence` / `GetThreatIntelligenceRequest`
  has the identical `investigation_id: int` requirement.
- Existing persistence: `threat_intelligence` is likewise a single `TEXT`
  column on `investigations`, not a separate table.
- UI/navigation implication: identical shape of problem to IOC Explorer.

### Shared picker model?
The two pages have materially the same requirement (an investigation
selector feeding an otherwise-unchanged per-investigation command), so a
shared picker component is technically appropriate if this direction is
chosen — this is a UX/product call, not an engineering constraint, since
the alternative (Option 3) avoids needing a picker at all by changing what
the backend returns instead of what the frontend asks for.

## Option 3 — Aggregate Backend Commands

Both `iocs` and `threat_intelligence` live as per-row JSON columns on the
single `investigations` table (verified directly against
`database/soc_iq.db`'s schema). An aggregate command is possible but is a
genuine new command, not a variant of an existing one:

```
Potential command: get_all_iocs
Purpose: Return IOCs across every investigation, for a cross-cutting
  IOC Explorer view.
Inputs: none, or an optional filter (type, date range) — a product
  decision, not an engineering one.
Outputs: a list of (investigation_id, ioc_type, value) tuples or similar —
  shape not yet specified pending the product decision on what the
  Explorer should actually group/filter by.
Repository impact: new repository method to scan all investigation rows
  and flatten their iocs JSON blobs; no schema change required since the
  data already exists, but a full-table scan replaces what is currently a
  single indexed lookup by investigation_id.
Database/query impact: none to the schema; a new query pattern (full-table
  JSON flatten) that doesn't exist anywhere else in the codebase today.
Frontend impact: IocExplorerPage rewritten to consume this instead of
  needing a picker at all.
Test impact: new handler test, new repository test, new frontend
  regression test.
Performance considerations: fine at current data volumes; would need
  revisiting if investigation count grows large, since every call
  currently means a full-table scan and in-memory JSON parse.
Security considerations: no new IPC surface beyond a normal read command;
  same authorization model as every other existing command (none of the
  existing commands currently enforce per-user investigation access
  control, so this doesn't introduce a new class of exposure).

Potential command: get_all_threat_intelligence
Purpose / Inputs / Outputs / Repository / DB / Frontend / Test / Perf /
Security: identical shape and considerations to get_all_iocs above,
substituting the threat_intelligence column.
```

Only these two commands are justified by the product reality above — no
other new aggregate command has a corresponding mock page waiting for it.

## Comparison

| Option | Scope | Risk | Architecture Impact | Backend Impact | Frontend Impact | Test Impact |
|---|---|---|---|---|---|---|
| AnalyzePage | Small | Low — removes a leftover, doesn't add capability | None | None | One file, remove/replace one list + fix stale copy | One test file updated |
| IOC/TI investigation context (picker) | Medium | Medium — new UX pattern (picker) applied to two pages; no backend change | None — reuses existing per-investigation commands | None | Two pages + a shared picker component | New tests for the picker and both pages |
| Aggregate backend commands | Medium–Large | Medium — new backend query pattern (full-table JSON scan) not used elsewhere in the codebase | None — fits the existing application/repository layering, but introduces a query shape with no precedent | Two new commands, DTOs, handlers, repository methods | Two pages rewritten around the new commands instead of a picker | New handler, repository, and frontend tests for both commands |

No option is recommended over another here — the deciding factor is a
product question (should IOC Explorer/Threat Intel stay cross-cutting
views, or become investigation-scoped?), not an engineering one; both
Option 2 and Option 3 are architecturally sound ways of answering that
question differently.

## Architecture Readiness

```
Option 1 — AnalyzePage
Existing architecture sufficient: YES
New architectural decision required: NO
Reason: No new command, DTO, or route needed; the real execution path
already exists.

Option 2 — Investigation-context picker
Existing architecture sufficient: YES
New architectural decision required: NO
Reason: Reuses get_iocs/get_threat_intelligence exactly as they exist
today; only adds a new frontend component (a picker), which is a UI
pattern decision, not an architectural one.

Option 3 — Aggregate backend commands
Existing architecture sufficient: YES
New architectural decision required: NO
Reason: New commands fit the existing DTO/handler/repository layering
without bypassing it; the only genuinely new element is a full-table-scan
query pattern, which is a performance/design consideration within the
existing architecture, not a departure from it.
```

## Security Readiness

```
Option 1: No new IPC/backend surface. No security consideration beyond
what already exists.

Option 2: No new backend surface at all — same commands, same DTOs. The
only new frontend surface is a picker reading from data the user already
has access to (list_investigations). No new security consideration
identified.

Option 3: Two new read-only backend commands. Same authorization model as
every existing command (none of the existing commands enforce per-user
investigation access control today, so this doesn't create a new class of
exposure, but it does mean these two new commands inherit that same
existing, already-accepted model rather than introducing a regression).
No export, capability-manifest, or keystore surface touched by any option.
```

No vulnerability is claimed or invented for any option — these are
considerations to be aware of if a direction is approved, not findings of
an existing defect.
