# SOC-IQ Frontend MAX-12 — Forensic Audit (Audit Only)

## 1. Audit Metadata

- Phase: MAX-12, Phase 1 (forensic audit only — no implementation performed).
- Session continuity note: **no new project ZIP was uploaded for this
  phase.** The authoritative baseline used is the exact full-project state
  this same session most recently produced and delivered as
  `SOC-IQ-FRONTEND-MAX-11-CLOSURE-FULL.zip` (SHA-256
  `8aa0586c46512ba86f1be01a22d8d02754eeea4d14e4bd2ea9f8e36c4dcb3590`, 824
  entries, `unzip -t` clean, verified in the prior turn). The on-disk working
  tree used for this audit is that exact content (minus `frontend/
  node_modules`/`frontend/dist`, which are excluded from the delivered
  archive by convention and are build artifacts, not source). This is
  recorded explicitly per §0's requirement to report the baseline rather
  than silently substitute one — there was no ambiguity to resolve since
  only one full-project archive exists in this session, but the absence of
  a fresh upload this turn is itself worth stating plainly.

## 2. ZIP Integrity Verification

Re-confirmed this phase, not assumed from the prior turn:

- `docs/audits/SOC-IQ-FRONTEND-MAX-11-CLOSURE.md` present and internally
  consistent with the working tree (its own §6 diff-forensics claims —
  exactly 4 files changed under `frontend/src/pages/settings/` — were
  spot-re-verified against the current tree's file listing and match).
- `docs/audits/SOC-IQ-FRONTEND-MAX-11-FORENSIC-AUDIT.md` present.
- No `.git` directory (unchanged since MAX-3) — filesystem/mtime-based
  provenance used throughout, same standing constraint as every prior MAX
  phase.

## 3. Project Structure

```
app/            — Python backend (api, application, database, gui legacy,
                  reporting, scoring, secrets, services, settings,
                  threat_intel, timeline)
database/       — SQLite artifacts
docs/           — adr, architecture, audits, contracts, migration, phase4,
                  security, testing
frontend/       — React + TypeScript, Tauri desktop shell (audit focus)
keystore-core/  — Rust keystore crate
packaging/      — pyinstaller, scripts
samples/        — sample report fixtures
sidecar-core/   — Rust sidecar crate
src-tauri/      — Tauri shell, capabilities, icons
tests/          — architecture, fixtures, gui (Python-side)
```

Frontend structure (`frontend/src/`):

```
app/            — router, navigation, shell, command palette, providers
mock/           — remaining mock data (settings/investigations/reports)
pages/          — page shells + one folder per feature (analyze, dashboard,
                  investigation, investigations, reports, settings,
                  components [shared primitives])
shared/         — api client, commands, events (SSE), hooks, notifications,
                  sidecar status
styles/         — global CSS + design tokens
```

MAX-11 baseline verified present and unmodified outside its own declared
scope (§2). Task brief's frontend-first scope followed; `app/` (Python
backend) and `src-tauri/` (Rust) were inspected only where they bear
directly on frontend correctness (capability manifest, IPC contract shape),
per §3's "inspect only where materially relevant" instruction — no backend
implementation defect was searched for exhaustively, consistent with this
audit series' established method (see MAX-11 audit §3).

## 4. MAX-11 Baseline Verification

- MAX11-F-01 (native Export Directory browse picker): re-confirmed present
  and correctly implemented (`exportDirectoryBrowse.ts`,
  `ExportDirectoryControl.tsx`) — consistent with the MAX-11 closure
  document's own findings, independently re-derived last phase.
- `src-tauri/capabilities/default.json`: unchanged, no new grant.
- Two P3 items were carried forward from MAX-11 as explicitly unselected:
  Reports `DataTable` column sort, and `MAX9-F-01` (stale `package.json`
  description).

## 5. Scope

Frontend-first, full-project-aware. Backend/Rust inspected only where they
bear on frontend correctness (§3). No implementation performed this phase
(§11 rule).

## 6. Methodology

- Full `find`/`grep` sweep of `frontend/src` for `TODO`/`FIXME`/`XXX`/`HACK`
  markers (none found) and leftover `console.log`/`console.debug` calls
  (none found).
- Enumerated every `.ts`/`.tsx` file without a co-located `.test.ts(x)` and
  cross-checked each against the project's established integration-test
  convention (documented in the MAX-11 audit §6) rather than assuming a
  gap; spot-checked several (`useVirustotalKeySave.ts`,
  `pages/components/DataTable.tsx`) against their actual covering suites.
- Read every Settings-page control (`ThemeControl.tsx`,
  `ExportDirectoryControl.tsx`, `VirustotalControl.tsx`) and their backing
  hooks end to end, plus `SettingsPage.tsx` itself, since Settings was the
  most recently touched surface and the one most likely to have drifted.
- Read `app/providers/ThemeProvider.tsx` and grepped
  `styles/tokens/color.ts` / `styles/tokens.css` / `styles/globals.css` for
  any contrast/theme-variant implementation, to test the Theme control's
  own claims against the actual styling system rather than trusting its
  doc comment.
- Read `pages/components/DataTable.tsx` (sort/keyboard/ARIA semantics) and
  cross-referenced its own in-file comments against actual current
  consumers (`ReportsPage.tsx`, `InvestigationsPage.tsx`) — this is what
  surfaced the documentation/implementation discrepancy in §16.
- Read `shared/events/eventSourceManager.ts` in full (connection
  lifecycle, ref-counting, stale-promise guarding via `connectToken`) for
  race conditions and reconnect-storm risk — none found.
- Read `app/commandPalette/CommandPaletteContainer.tsx` and confirmed its
  test coverage (280 + 128 + 150 lines across three suites) is
  substantive, not padding.
- Read `pages/reports/reportExportPath.ts` (save-dialog/export-format
  derivation pattern) for security-boundary consistency with the
  MAX-10/MAX-11-hardened export flow.
- Cross-referenced `docs/architecture/IMPLEMENTATION_STATUS.md` and
  `docs/architecture/CURRENT_TO_TARGET_MAPPING.md` against the Theme
  control's actual behavior to determine whether "persistence only, no
  live-apply" is a documented architectural decision or an unflagged gap
  (§16 — it is the former at the architecture-doc level, but the
  end-user-facing UI itself discloses none of this).
- Did not re-walk areas with no plausible drift since their last dedicated
  pass (motion, most of Investigation Workspace's tab internals, Analyze's
  core execution path) absent a specific reason to suspect regression,
  consistent with this series' established method.

## 7. Architecture Findings

No architectural regression. Structure unchanged: one router, one typed
command client, one SSE connection manager (ref-counted singleton,
re-verified this phase — no duplicate-connection or leak risk found), one
sidecar-status model. No duplicate state machines, no direct DB access from
the frontend. **No new finding.**

## 8. UX Findings

**MAX12-F-01 (High).** See §16 for full evidence. Summary: the Settings
page's "Theme" control offers two options ("Dark Mode (SOC-IQ Standard)"
and "High Contrast Dark"), persists whichever is chosen through
`save_settings`, and shows a plain "Theme saved." success message — with
no indication anywhere in the rendered UI that selecting "High Contrast
Dark" has no visible effect on the running application. `ThemeProvider.tsx`
implements exactly one static token set; there is no second theme, high-
contrast or otherwise, anywhere in `styles/`. The gap between what the
control implies (a working accessibility-oriented display mode) and what
it does (writes a string to a settings row) is currently disclosed only in
a source-code comment an analyst will never see.

No other new UX finding. Analyze, Investigations, Reports, Investigation
Workspace, and Dashboard all match or exceed their previously-documented
state.

## 9. Accessibility Findings

Directly related to MAX12-F-01: an analyst who genuinely needs higher
contrast and finds a control literally named "High Contrast Dark" has a
reasonable expectation it does something. Selecting it, saving it, and
seeing "Theme saved." with zero visual change is a worse outcome than the
control not existing at all — it actively signals a false success. This is
recorded once, under UX (§8), rather than duplicated as a separate
accessibility finding, since it is the same underlying gap viewed through
two lenses (§7 of the task brief's quality gate — "distinct?").

No other accessibility finding. `DataTable`'s sortable-column headers
correctly use `aria-sort` and native `<button>` semantics (re-verified this
phase); `CommandPalette` and Settings' existing save/error/retry pattern
(`role="alert"`/`role="status"`+`aria-live="polite"`) are consistent and
already covered by MAX-6's dedicated design-system pass.

## 10. Visual System Findings

No new finding. Token/spacing/typography consistency holds; no accidental
one-off styling found in the surfaces read this phase (Settings, Reports,
Command Palette).

## 11. Responsive Findings

No new finding. Nothing read this phase introduced or revealed a new
clipping/overflow/layout-collapse condition. (Scope note: full 1440×900/
1280×720 rendered verification remains `ENVIRONMENT-BLOCKED` — no browser
automation in this sandbox, unchanged standing condition, §24.)

## 12. Performance Findings

No new finding. `eventSourceManager.ts`'s singleton/ref-counting design
(§6) avoids the specific "one connection per render/consumer" failure mode
its own doc comment names. No new unnecessary renders, effects, or timers
found in the surfaces read this phase.

## 13. Reliability Findings

No new finding. `eventSourceManager.ts`'s `connectToken` guard against a
stale async origin-resolution applying itself after a newer connect/
disconnect cycle (§6) is sound — re-traced by hand against the
subscribe/unsubscribe pairing and found to correctly prevent the race it
names. `useVirustotalKeySave.ts`'s `cancelledRef` guard against a
post-unmount state update is present and correctly wired.

## 14. Security Findings

No new finding. `reportExportPath.ts`'s save-dialog pattern is consistent
with `nativeFileSelection.ts`/`exportDirectoryBrowse.ts` — path only ever
comes from the OS-native dialog, never guessed or concatenated; no new
filesystem/export/trust-boundary issue found in the surfaces read this
phase. Capability manifest re-confirmed unchanged.

## 15. Testing Findings

No new coverage gap found beyond the established, deliberate integration-
test convention (MAX-11 audit §6) — re-spot-checked this phase
(`useVirustotalKeySave.ts` is fully exercised through
`VirustotalControl.live.test.tsx`'s "saving" describe block, not
uncovered as a first glance at file-listing alone might suggest).

## 16. Historical Finding Reconciliation — Documentation/Implementation Discrepancy

**The MAX-11 audit's carried-forward P3 item — "Reports page `DataTable`
has no sortable columns, unlike Investigations" — is INVALIDATED against
the current implementation.**

Evidence: `pages/ReportsPage.tsx` lines 109–133 define both its `status`
and `analyzed` columns with `sortable: true` and a `sortValue` accessor,
labeled in their own comment `MAX10-F-01 / Phase 2B`. This code carries the
same baseline mtime (`2026-09-04 11:51:26`) as every other untouched
baseline file — it was **not** introduced by MAX-11 Phase 2A (confirmed
scoped to exactly 4 files under `pages/settings/`, per the MAX-11 closure
doc's own diff forensics, independently re-verified last phase). This means
the MAX-11 forensic audit's own §8 claim was incorrect *at the time it was
written*, against the exact same baseline it was auditing — an audit-error,
not a regression introduced since.

Corroborating evidence: `pages/components/DataTable.tsx`'s own `sortable`
field doc comment (line ~14) still reads "Every existing consumer
(Dashboard, IOC Explorer, Reports, Risk) omits this" — itself stale, since
Reports demonstrably does not omit it, and "IOC Explorer"/"Risk" are pages
already retired from navigation per PD-05/PD-06 (confirmed absent,
`docs/architecture/IMPLEMENTATION_STATUS.md` line 212). This is a second,
independent piece of evidence the same conclusion — an in-source comment
drifted out of sync with its own file's actual usage, predating MAX-11.

Per this task brief's explicit rule (§1: "If documentation conflicts with
implementation, implementation evidence wins, and the discrepancy must be
documented") — implementation wins: **Reports column sort is not a gap.**
It should be struck from any future MAX candidate list. This is a
documentation-correctness note, not itself a MAX-12 direction (there is
nothing to fix in the product; the sort feature already exists and works).

`MAX9-F-01` (`package.json` stale description): re-confirmed still present,
verbatim, unchanged — genuinely still open, still P3, still correctly out
of scope for a MAX-cycle-worthy direction on its own (zero runtime effect).

No regression was found anywhere in the surfaces re-walked this phase.
MAX12-F-01 (§8/§16) is genuinely new — not previously raised in any MAX-1
through MAX-11 audit (grepped `docs/audits/*.md` for `ThemeControl`/
"High Contrast"/theme-application language; only incidental scope
mentions in the MAX-6 design-system closure doc were found, never this
specific gap).

## 17. Finding Severity Matrix

| ID | Severity | Area | Status |
|---|---|---|---|
| MAX12-F-01 | **High** | Settings / Appearance, UX + accessibility-adjacent | **New — selected for MAX-12** |
| (Reports DataTable sort) | — | Reports list | **INVALIDATED** — already implemented; MAX-11 audit's claim was itself incorrect (§16) |
| MAX9-F-01 | P3 | `package.json` metadata | Carried forward, still open, not selected |
| — | — | Architecture, security boundaries, performance, reliability, responsive, most of accessibility | No new finding this cycle |

No Critical finding exists. No new Medium/Low finding beyond the two
carried-forward/reconciled items above.

## 18. Candidate Ranking

1. **MAX12-F-01 — Theme control honesty fix.** Real (verified against both
   the component's own doc comment and the actual absence of any second
   theme in `styles/`), material (every analyst who visits Settings can hit
   this; the specific failure mode — a named accessibility option that
   silently no-ops — is a trust and, secondarily, an accessibility
   concern), actionable (additive-only: surface the same honest disclosure
   the code comment already states, directly in the UI, matching the exact
   pattern `VirustotalControl`'s "restart-required" honesty and
   `ExportDirectoryControl`'s "dialog failed, type it directly" honesty
   already establish elsewhere in this same Settings page), distinct (not
   a duplicate of any prior finding, confirmed §16), current (present in
   this exact baseline, not fixed by MAX-11). Implementation risk: low —
   same shape as MAX-11's own selected direction (a small, additive,
   honesty-oriented UI change reusing an established in-page pattern, no
   backend/contract change).
2. **Reports DataTable sort.** Eliminated — already implemented (§16), not
   a valid candidate.
3. **`package.json` description fix.** Real but trivial, zero runtime
   effect, not MAX-cycle-worthy on its own (unchanged conclusion from
   MAX-11's own ranking).

No other candidate survived the §7 quality gate (real/material/actionable/
distinct/current) with sufficient evidence this phase.

## 19. Selected MAX-12 Direction

### Selected Direction

Make the Settings "Theme" control honestly disclose, in the rendered UI
itself, that a selected/persisted theme value is not currently applied to
the running application — closing the gap between what the control's
source comment already admits and what an analyst using the actual app can
see.

### Why It Wins

It is the only surviving finding that is simultaneously real (independently
verified against both the component and the styling system, not assumed
from a comment), material (100% of analysts who ever open Settings can see
the "Appearance" card; the specific option that no-ops is named after an
accessibility accommodation), and actionable at low risk using a pattern
this exact codebase has already proven twice in the same file family
(`VirustotalControl`, `ExportDirectoryControl`).

### User/Product Impact

An analyst — especially one who specifically wants a higher-contrast
display and reasonably expects "High Contrast Dark" to do something — no
longer gets a silent, misleading "Theme saved." success message with zero
visible effect. The control's real, current behavior (persistence only)
becomes something the product tells the analyst, not something only a
future developer reading source comments would know.

### Affected Surface

`frontend/src/pages/settings/ThemeControl.tsx` (add the disclosure),
possibly its `.css`/shared status-message classes already used by the
Save/error states in the same component. No other page.

### Implementation Boundary (for a future Phase 2A)

- Add a persistent, honest note in `ThemeControl`'s own rendered output
  (not just a source comment) stating that theme selection is saved but
  not yet applied to the interface.
- Reuse the component's existing `settings-page__field-note`/status-message
  CSS classes and `role` conventions already established in this same file
  and its siblings — no new visual language.
- No change to `save_settings`'s contract, no change to `useSettingsFieldSave`,
  no change to `THEME_OPTIONS`.

### Non-Goals

- **Do not implement an actual working "High Contrast Dark" theme.** That
  is a materially larger, riskier, cross-cutting change (a second design-
  token set, `ThemeProvider` rework, every component's CSS) — far beyond
  this audit's "small, additive, low-risk" selection criterion and
  explicitly out of MAX-12 Phase 2A's boundary. Implementing real theme-
  switching is a legitimate future direction but is not this one.
- No change to any other Settings control.
- No architecture rewrite, no new dependency.
- Do not touch Reports `DataTable` (§16 — not a real gap).
- Do not fix `MAX9-F-01` (unrelated surface, deliberately deferred, same
  as MAX-11's own treatment of it).

### Rejected Alternatives

- Reports column sort: not a real gap (§16) — eliminated at the duplicate-
  elimination stage, never reached ranking.
- `package.json` description: real but trivial, no analyst-facing effect,
  not cycle-worthy on its own (unchanged from MAX-11's own conclusion).

## 20. Verification Requirements For A Future Phase 2A

- `npx tsc --noEmit` — 0 errors.
- `npm test -- --run` — 0 regressions against this phase's 1203-test
  baseline; new test(s) for the added disclosure.
- `npm run build` — clean production build.
- Diff-audit against this baseline's untouched extraction — confirm only
  `ThemeControl.tsx` (and its test file) changed.

## 21. Known Environmental Limitations

- No Rust/Tauri toolchain in this sandbox (unchanged, standing condition).
- No browser/Tauri runtime automation — all accessibility/responsive
  observations in this audit are source/static-level.
- No `.git` — mtime-based provenance only.
- Backend (Python)/Rust source was not exhaustively re-audited this phase,
  per §3's frontend-first scope; only surfaces bearing directly on frontend
  correctness were read.

---

**MAX-12 FORENSIC AUDIT COMPLETE — IMPLEMENTATION NOT PERFORMED**
