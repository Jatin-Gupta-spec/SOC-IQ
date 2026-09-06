# SOC-IQ — PD-05: Retire Top-Level IOC Explorer + Threat Intel

## Entry checkpoint

`SOC-IQ-OPTION1-ANALYZEPAGE-FINAL-VERIFIED-FROZEN.zip`

## Decision

**PD-05 — Top-level IOC/TI destination strategy: OPTION B — retire both
top-level mock destinations from primary navigation.**

This decision applies only to the two top-level mock destinations,
`IOC Explorer` (`/ioc-explorer`) and `Threat Intel` (`/threat-intel`).
It does not implement cross-investigation aggregation (PD-04), an
investigation picker (PD-02/PD-03), or any new backend capability —
those remain separately deferred.

## Rationale

- The current architecture is investigation-centric; real IOC/TI views
  already exist inside the Investigation Workspace
  (`InvestigationIocWorkspace.tsx`, `InvestigationThreatIntel.tsx`),
  reached via `Investigations` → an investigation → its `IOCs`/`Threat
  Intel` tabs.
- The two top-level pages were mock-driven (`mock/iocs.ts`,
  `mock/threatIntel.ts`) with no `investigation_id` to pass to
  `get_iocs`/`get_threat_intelligence`, so they could never become real
  without one of PD-02/PD-03 (an investigation picker) or PD-04
  (new aggregate backend commands) — see
  `POST_FREEZE_PART1_PRODUCT_DECISION_GATE.md` for that original
  analysis.
- Retaining them as permanent placeholders would expose misleading
  top-level destinations that can never be wired up under the existing
  architecture without a separate, still-undecided product decision.
- No new backend capability is required to retire them — this is a
  frontend navigation/page change only.
- Cross-investigation aggregation (PD-04) remains a separate future
  decision, unaffected by this one.

## What changed

- `frontend/src/app/navigation/navigationModel.ts` — removed the
  `ioc-explorer` and `threat-intel` entries from `NAVIGATION_ITEMS`
  (now 6 destinations: Dashboard, Analyze, Investigations, Risk,
  Reports, Settings). The router (`app/router.tsx`), sidebar, dashboard
  quick actions, and command palette (`shared/commands/commandRegistry.ts`)
  all derive from this single source of truth, so removing the two
  entries there automatically removed their routes, sidebar links,
  quick-action links, and palette commands — no second navigation
  configuration was created or hand-edited.
- `frontend/src/app/router.tsx` — removed the two page imports and
  `PAGE_BY_NAVIGATION_ID` mappings. A direct or bookmarked navigation to
  `#/ioc-explorer` or `#/threat-intel` now falls through to the
  pre-existing catch-all route, which redirects to
  `DEFAULT_NAVIGATION_PATH` (`/dashboard`) — the project's established
  `HashRouter` unknown-path behavior. No bespoke redirect was added.
- Deleted `frontend/src/pages/IocExplorerPage.{tsx,css}` and
  `ThreatIntelPage.{tsx,css}`, and their exports from `pages/index.ts`
  — confirmed zero remaining production consumers before deletion.
- Deleted `frontend/src/mock/iocs.ts` and `mock/threatIntel.ts`, and
  removed their re-exports from `mock/index.ts` — confirmed these had
  no consumers other than the two deleted pages (the Investigation
  Workspace's real IOC/TI components import types directly from
  `shared/api/types`, not from these mock modules).
- Updated user-facing copy that referenced the two pages as
  future/top-level destinations
  (`pages/analyze/AnalysisResultSummary.tsx`, `pages/AnalyzePage.tsx`)
  to instead point at the Investigation Workspace's IOCs/Threat Intel
  tabs, which is where that functionality actually lives.
- Updated `frontend/package.json`'s description to drop IOC
  Explorer/Threat Intel from the placeholder-pages list and note the
  retirement.
- Updated tests that hard-coded the old 8-destination navigation/command
  list (`navigationModel.test.ts`, `commandRegistry.test.ts`,
  `pages.test.tsx`, `mock/mock.test.ts`,
  `CommandPaletteContainer.live.test.tsx`,
  `AnalysisResultSummary.test.tsx`) and added explicit PD-05 regression
  assertions that the retired ids/paths/labels are absent from
  `NAVIGATION_ITEMS`, `COMMANDS`, and the live command palette.

## Unchanged (verified, not assumed)

```
Backend (app/, tests/):        UNCHANGED — byte-identical to checkpoint
Database schema:                UNCHANGED
Tauri / Rust (src-tauri/,
  keystore-core/, sidecar-core/): UNCHANGED — byte-identical to checkpoint
Investigation Workspace:        UNCHANGED (InvestigationIocWorkspace.tsx,
                                 InvestigationThreatIntel.tsx,
                                 useInvestigation.ts, get_iocs,
                                 get_threat_intelligence all untouched)
IOC / Threat Intelligence
  data models:                  UNCHANGED
Security (§20 controls,
  capability manifest, export
  traversal protection,
  keystore, credential handling): UNCHANGED
```

Investigation-scoped IOC and Threat Intel functionality **remains fully
available** via `Investigations` → an investigation → its `IOCs` /
`Threat Intel` tabs. Only the two top-level, never-wireable mock
destinations were retired.

## Verification (this session)

```
Frontend tests (vitest run):   70 files / 949 tests passed, 0 failed
TypeScript (tsc --noEmit):     clean, 0 errors
Frontend production build:     PASS — 186 modules, no warnings
Backend (pytest tests/):       952 passed, 2 skipped (matches the
                                checkpoint's own historical baseline
                                exactly, confirming no backend drift)
Database artifact:             restored to documented MD5
                                d4c1cb7c175ec4e176f6ffb549394994
                                after the backend suite's known
                                mutation side effect
Rust:                          ENVIRONMENT BLOCKED — rustc/cargo were
                                not preinstalled; the apt-available
                                rustc (1.75.0) is below this project's
                                declared minimum (Cargo.toml
                                `rust-version = "1.77"`), and a full
                                Tauri build additionally requires
                                system GTK/WebKit development headers
                                not present in this sandbox. No Rust
                                source or Cargo.toml was modified to
                                work around this.
```

Full recursive diff against the entry checkpoint confirms every changed
file is explainable by this PD-05 retirement (navigation/router/pages/
mock disposition, the directly-affected tests, and the necessary
user-facing copy/documentation correction) — no unrelated files differ,
and `app/`, `database/soc_iq.db`, `src-tauri/`, `keystore-core/`, and
`sidecar-core/` are byte-identical to the entry checkpoint.

## Product-Decision Register

This table is the project's current, authoritative product-decision
register. Earlier point-in-time snapshots of this register (e.g.
`POST_FREEZE_PART1_PRODUCT_DECISION_GATE.md`,
`POST_FREEZE_FINAL_STATUS.md`) are preserved as historical records of
what was decided at that checkpoint and are not updated retroactively.

| ID | Decision | Status |
|---|---|---|
| PD-01 | AnalyzePage completion (remove leftover mock recent-runs list) | RESOLVED — Option 1 implemented |
| PD-02 | IOC Explorer investigation context/picker | **MOOT — superseded by PD-05.** The top-level IOC Explorer this picker would have served was retired; an investigation picker for a destination that no longer exists is not an active product requirement. |
| PD-03 | Threat Intel investigation context/picker | **MOOT — superseded by PD-05.** The top-level Threat Intel destination this picker would have served was retired; an investigation picker for a destination that no longer exists is not an active product requirement. |
| PD-04 | Cross-investigation aggregate backend commands | DEFERRED — remains a separate architectural/product decision, unaffected by PD-05/PD-06/PD-07 |
| PD-05 | Top-level IOC/TI destination strategy | RESOLVED — Option B: retire both from primary navigation |
| PD-06 | Standalone Risk page | **RETIRE** (decision recorded; not yet implemented) — see `PD06_STANDALONE_RISK_RETIREMENT.md` |
| PD-07 | Settings | **PARTIAL BUILD**: theme + export directory only (decision recorded; not yet implemented) — see `PD07_SETTINGS_PARTIAL_BUILD.md`. VirusTotal credential write path separately DEFERRED (ADR-008 / Part 1B-3). |

## Next Action

None required by PD-05 itself. PD-04 remains deferred and unaffected;
PD-02 and PD-03 are moot and require no further action unless the
underlying top-level destinations are reintroduced by a future
decision. PD-06 and PD-07 are decision records only — implementing
Risk retirement or the approved Settings scope requires its own
implementation part; see each linked document's "Next Action".
