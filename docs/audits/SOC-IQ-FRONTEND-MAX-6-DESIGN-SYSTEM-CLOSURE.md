# SOC-IQ Frontend MAX-6

## Design System + Visual Consistency Closure

---

### 1. Executive Summary

MAX-6's intent, per the forensic audit that opened this workstream, was to check
SOC-IQ's frontend for design-system and visual-consistency drift: token usage,
shared-component adoption (cards, tables, badges, page headers, empty/error states),
and button/control consistency across all page contexts.

**Audit result:** the token layer was found mature and not a source of drift. The
component layer was materially clean except at the button/control layer, where four
independent findings were confirmed — two P0 (retry-button fragmentation, including an
unstyled Dashboard occurrence; an Analyze-page focus-outline deviation from the global
MAX-1 standard), one P1 (no shared `Button` primitive), one P2 (card base-surface rule
duplicated instead of composed). Badges and the Provider Detail page were left
explicitly incomplete, and no rendered-viewport verification was performed at either
required breakpoint.

**Implementation result:** all four confirmed findings (F-01–F-04) were resolved. A
minimal shared `Button` primitive was introduced and every affected control across six
page contexts (Dashboard, Analyze, Investigations, Reports, Settings, and — surfaced
during implementation, not in the original audit matrix — Investigation Workspace) was
migrated to it. TypeScript, the full Vitest suite (1136 tests / 81 files, including 8
new `Button` tests), and the production build all pass clean. Diffing against a pristine
second extraction of the baseline confirms changes are confined to `frontend/` and
`docs/audits/` — zero changes to `app/`, `src-tauri/`, `database/`, `packaging/`, or any
other path.

**Final verdict:** rendered/viewport verification at 1280×720 and 1440×900 was **not
performed** in either phase — this remains a genuine, carried-forward environmental gap,
not a skipped step.

```text
FRONTEND MAX-6 — PASS WITH DOCUMENTED CONDITIONS
```

---

### 2. Baseline

- **Baseline checkpoint:** `SOC-IQ-FRONTEND-MAX-5-DASHBOARD-FULL.zip`
- **Archive size (per implementation phase's own record):** 2,411,384 bytes
- **Entries (per implementation phase's own record):** 790 files
- **SHA-256 (per implementation phase's own record):** `8884c7c26ab1748a7b226d96cfdc8d1f33aa2982261e7aa5999dce4d07e64858`
- **`.git`:** absent from the baseline archive, confirmed independently by both the
  audit phase and the implementation phase. No Git-based provenance commands
  (`git branch`, `git rev-parse HEAD`, `git status --short`, `git diff`) could produce
  real output at any point in this workstream — none were fabricated.
- **Provenance limitation:** because no `.git` directory exists at any point in this
  chain, all change-tracking in both phases was done by diffing a working tree against
  a second, untouched extraction of the same baseline ZIP, not by any Git mechanism.
  This is a standing limitation of the MAX-5 checkpoint, not something introduced by
  MAX-6.

---

### 3. Scope

- **Frontend-only.** All permitted work was confined to `frontend/` (React/TypeScript/
  CSS) plus documentation under `docs/audits/`.
- **Design-system / visual-consistency scope only:** token usage, shared-component
  adoption (buttons, cards, tables, badges, page headers, empty/error states), and
  focus-indicator consistency. No feature work, no data/business-logic changes.
- **Explicitly prohibited:** any change to `app/` (Python/FastAPI backend), `src-tauri/`
  (Rust/Tauri shell), `database/`, `packaging/`, `sidecar-core/`, `keystore-core/`,
  tests outside what's needed to cover the new `Button` component, or any
  infrastructure/build configuration. The diff audit (§11) confirms this boundary held.

---

### 4. Forensic Audit Summary

The audit was **static code/style inspection only** — no dev server was run, no browser
rendering was captured, no viewport screenshots were taken. Findings below are derived
from grep-based inventory plus manual reading of matched CSS/TSX rules.

**Token layer:** mature and well-adopted. Across 37 non-core component/page CSS files
(~865 `var()` references): zero raw hex colors, zero raw `font-size` px values, zero raw
`border-radius` px values, zero raw `gap` px values outside `tokens.css` itself. Two
minor non-findings were noted rather than raised as issues: a single untokenized `2px`
padding value in `StatusBadge.css:4`, and several legitimate `1px`/`2px solid
transparent` border-width declarations (an intentional layout-shift-avoidance pattern;
no `--border-width-*` token exists or is needed for it).

#### F-01 — P0 — Retry-button fragmentation, including unstyled Dashboard occurrence

- **Affected pages (as audited):** Dashboard, Settings, Investigations, Reports
  (Analyze's retry button was scoped separately under F-02).
- **Affected files:** `DashboardPage.css:230`, `SettingsPage.css:64`,
  `InvestigationsPage.css:16`, `ReportsPage.css:16`.
- **Finding:** three independent visual implementations for the same "retry after
  error" action. Settings/Investigations/Reports shared one filled-brand-button spec
  (`radius-sm`, `padding: var(--space-sm) var(--space-lg)`, `font-size-body`, no local
  `:disabled`/`:focus-visible`). Dashboard's two occurrences declared only
  `min-height`/`padding` — no color, background, or border, and `globals.css` had no
  base `<button>` reset to fall back on. Confirmed against the JSX directly: a plain
  `<button type="button" className="dashboard-page__retry-button">` with no other
  class, rendering as an unstyled native browser button next to an otherwise polished
  UI. The audit called this the single most user-visible issue found.
- **Scope dependency noted by audit:** implementation should happen together with F-04
  (the Button primitive decision), not in isolation, to avoid creating a fifth bespoke
  implementation.

#### F-02 — P0 — Analyze-page alternate focus-indicator color

- **Affected controls:** `AnalyzePage.css` — native-browse, start, and retry buttons
  (all three) — plus the checkbox `:focus-visible` override in
  `AnalysisOptionsControls.css`.
- **Finding:** all four controls overrode the global `:focus-visible` rule
  (`outline: 2px solid var(--color-border-focus)`, defined once in `globals.css`) with
  `outline: 2px solid var(--color-status-info)` instead — internally consistent within
  Analyze, inconsistent with every other page. This produced two different
  focus-indicator colors in production, a direct MAX-1 deviation regardless of intent.
- **Why treated as a design decision, not an engineering one:** the override was
  internally consistent across all four Analyze controls, which reads as a deliberate
  (if undocumented) page-scoped choice rather than a one-off accident. The audit
  explicitly declined to pick a side — either (a) document it as an intentional Analyze
  accent and keep it, or (b) treat it as drift and converge on the global token — and
  flagged it for an explicit accept/reject decision rather than a silent fix.
- **Final decision (implementation phase):** the undocumented exception was **rejected**.
  No source evidence was found for an intentional product requirement, so all four
  controls now rely on the global focus rule with no local override anywhere, including
  inside the new `Button` component itself.
- **Resulting implementation:** see §6 "Analyze Focus" below.

#### F-03 — P2 — Card base-rule duplication

- **Affected components:** `MetricCard` (`.metric-card`), `InvestigationHeaderCard`
  (`.investigation-header-card`), both duplicating `.card`'s exact `background-color` /
  `border` / `border-radius` / `padding` declarations verbatim instead of composing it.
- **Finding:** no visible inconsistency (the duplicated values were identical to
  `.card`'s) — a maintainability finding only: three places to edit if the base card
  treatment ever changes, not a currently-visible bug.
- **Status:** fixed, not deferred — see §7.

#### F-04 — P1 — No shared Button primitive (identified as the root cause underlying F-01)

- **Affected components:** `InvestigationsPage.css:53` (`.investigations-page__export-button`)
  and `ReportsPage.css:53` (`.reports-page__action-button`) — a second, distinct
  "filled primary" family (`radius-md`, `padding: var(--space-xs) var(--space-sm)`,
  `font-size-body-small`) alongside F-01's family.
- **Finding:** no shared Button primitive exists anywhere in the codebase — every
  interactive button is a hand-rolled, page-scoped class. Two overlapping,
  internally-consistent-but-mutually-inconsistent "filled primary" specs were confirmed,
  which the audit identified as the underlying reason four independent retry-button
  implementations exist in the first place. Flagged as the prerequisite decision
  blocking F-01's implementation.

---

### 5. Confirmed Clean Systems

Preserved as audited, not touched or redesigned by MAX-6:

- **Token layer** (`tokens.css`, `styles/tokens/*.ts`) — mature; the audit's explicit
  recommendation was *not* to run a mechanical tokenization pass, and none was run.
- **`DataTable`** — the strongest-documented shared component found; every tabular UI
  outside one legitimate specialized exception (`InvestigationOverviewRisk.tsx`'s
  denser in-card risk-breakdown table, explicitly commented in source as reusing an
  established bordered-box treatment) uses it directly.
- **`PageHeader`** — used by all six top-level pages that have a page header; exemplary,
  non-finding.
- **`Card`** (`.card`) — the shared primitive itself was not modified; only its two
  duplicating consumers changed, under F-03.
- **`InfoNote`** — consistent dashed-border, muted-text empty/info-state treatment
  across investigation, settings, and dashboard panels; not exhaustively traced
  per-page, but no distinct finding was raised against it.
- **`CommandPalette`'s** borderless, bottom-border-only search input — an intentional,
  conventional pattern, correctly distinct from standard form inputs.

None of the above were redesigned, rewritten, or "improved" as part of this phase.

---

### 6. Implementation

#### Shared Button

- **Location:** `frontend/src/pages/components/Button.tsx` + `Button.css` (+
  `Button.test.tsx`, 8 new tests).
- **API:** `variant?: "primary" | "secondary"` (default `"primary"`), `size?: "default"
  | "compact"` (default `"default"`), plus every standard `<button>` HTML attribute via
  `ButtonHTMLAttributes<HTMLButtonElement>` — `disabled`, `aria-busy`, `aria-label`,
  `onClick`, etc. all pass through untouched at every call site. `type` defaults to
  `"button"`.
- **Variants:** `"primary"` — filled brand button (the retry/save family); `"secondary"`
  — transparent/outlined (Analyze's browse/start/retry family).
- **Sizes:** `"default"` — from the retry-button family's spec; `"compact"` — from the
  export/action-button family's spec (`InvestigationsCsvExportAction`,
  `ReportExportAction`). Both sizes were drawn directly from the two pre-existing,
  independently-arrived-at specs identified in F-04, not invented.
- **Focus behavior:** intentionally unset at the component level — `Button` declares no
  `:focus-visible` rule of its own and relies entirely on the pre-existing global rule
  in `globals.css`. This is the mechanism by which F-02's resolution is structurally
  enforced going forward: any future consumer gets the correct focus color by default
  and would have to actively add an override to deviate from it. A dedicated test
  asserts `Button.css` contains neither a `:focus-visible` rule nor any reference to
  `--color-status-info`.
- **Disabled behavior:** handled entirely via the native `disabled` attribute passed
  through `ButtonHTMLAttributes` — no bespoke disabled styling logic was added beyond
  what call sites already supplied.
- **Loading behavior:** no `loading` prop was added. Every existing call site already
  manages its own busy state via `disabled` and `aria-busy`, passed straight through;
  a dedicated `loading` prop would have duplicated existing behavior rather than
  replaced anything.
- **Token usage:** every declaration in `Button.css` uses an existing token
  (`--font-family-primary`, `--font-size-body`/`--font-size-body-small`,
  `--font-weight-medium`, `--radius-sm`/`--radius-md`, `--space-*`, `--color-*`,
  `--duration-fast`, `--easing-out`). No new tokens were added; `tokens.css` was not
  modified.

#### Retry Migration

All affected retry buttons now render `<Button>`:

- **Dashboard** (×2) — primary variant; original `min-height`/`padding` sizing intent
  preserved via a small local override layered on top through `className`. This also
  closes the "unstyled Dashboard button" issue, the audit's single most severe finding.
- **Settings** — page-level retry, plus three sub-control Save/Retry buttons
  (`VirustotalControl`, `ExportDirectoryControl`, `ThemeControl` — see "Scope
  correction" below).
- **Investigations** — primary variant.
- **Reports** — primary variant.
- **Analyze** — secondary/accent variant, matching its pre-existing distinct visual
  treatment (see F-02 resolution below for the focus-specific change).
- **Investigation Workspace** — primary variant; not in the original audit matrix (see
  "Scope correction").

No retry logic, event handlers, or copy were changed at any migrated call site.

#### Analyze Focus

The undocumented Analyze-page focus override was rejected in favor of convergence on
the global MAX-1 standard: all four previously-overriding controls (browse, start,
retry, and the analysis-options checkbox) now inherit the shared `Button`/`globals.css`
`:focus-visible` behavior with no local override anywhere. Analyze's buttons **do**
still use `--color-status-info` as their resting **border** color (a
`.analyze-page__accent-button` modifier shared by start/retry) — this was never the
part of F-02 that was flagged, and the border-color choice itself is preserved as a
legitimate, intentional page-specific accent, distinct from the focus-outline issue
that was fixed.

#### Scope correction (discovered during implementation, not present in the original audit matrix)

The audit's cross-page matrix marked Investigation Workspace and the three Settings
sub-controls as not directly audited for buttons (➖, not ✅). Implementation surfaced
two real, in-scope issues that widen F-01's known footprint without changing its
classification:

1. `InvestigationWorkspacePage.tsx` has its own retry button
   (`.investigation-workspace__retry-button`) with the exact same filled-brand-button
   spec as the other five — migrated to `Button` alongside them. Its sibling
   `.investigation-workspace__secondary-button` (`BackToInvestigationsButton`) is a
   third, distinct neutral-outline style that was **not** touched, since it was never
   part of a confirmed finding and forcing it into an existing variant would have been
   speculative (see §12).
2. `VirustotalControl.tsx`, `ExportDirectoryControl.tsx`, and `ThemeControl.tsx`
   (rendered inside `SettingsPage`) reuse the literal class names
   `settings-page__save-button` / `settings-page__retry-button` that
   `SettingsPage.css` defined. Removing those CSS rules as part of the F-01 migration
   would have silently unstyled these three controls' Save/Retry buttons — caught
   before finalizing, not shipped. All three were migrated to `Button` in the same
   pass, preserving the existing class names via `Button`'s `className` prop so
   existing `*.live.test.tsx` `querySelector` calls continue to resolve. Verified by
   the full Vitest run passing.

A third, documentation-only correction: implementation-time re-inspection confirmed the
`AnalysisOptionsControls.css` checkbox `:focus-visible` override (cited in the audit at
"lines 36-37") was real and was fixed as part of F-02. An earlier, non-final draft of
the closure had incorrectly claimed the audit overstated this — the audit's original
finding was correct; that was a documentation error on the implementation side, not a
code error, recorded here for an honest paper trail rather than silently corrected.

---

### 7. F-03 Decision

**Fixed**, not deferred. `MetricCard` and `InvestigationHeaderCard` now compose the
shared `.card` class (`className="card metric-card"` /
`className="card investigation-header-card"`) instead of duplicating its
`background-color`/`border`/`border-radius`/`padding` declarations. Their own CSS files
now contain only their additive, component-specific rules. `Card` itself was not
modified. No visible rendering change, since the duplicated values were already
identical to `.card`'s — this was a maintainability-only finding, and the audit had
rated it low-priority/opportunistic rather than urgent; it was folded into the same
pass as the other three findings rather than deferred to a future phase.

---

### 8. Accessibility

- **Focus-visible:** restored to a single global standard everywhere via F-02's
  resolution — no page or component overrides the global `:focus-visible` rule any
  longer.
- **Keyboard behavior:** unchanged at every call site — `Button` renders a real native
  `<button>` element (verified by test), not a clickable `<div>` or other non-semantic
  substitute, so existing keyboard operability was not altered.
- **Disabled behavior:** passed straight through via native `disabled` attribute
  handling; no custom disabled logic was introduced.
- **Semantic button behavior:** `type` defaults to `"button"`; all native `<button>`
  attributes (`aria-busy`, `aria-label`, etc.) continue to work exactly as before.
- **MAX-1 preservation:** no native `<button>` elements were replaced with non-semantic
  substitutes anywhere in the migration.

---

### 9. Responsive Verification

```text
1280 × 720  — CONDITIONAL — environment did not permit rendered viewport verification
1440 × 900  — CONDITIONAL — environment did not permit rendered viewport verification
```

This condition is carried forward unchanged from the audit phase, not newly introduced
by implementation — the audit itself performed only static code inspection (no dev
server, no rendered screenshots) and explicitly called this out as something that
"should be corrected with actual browser inspection ... before or during
implementation." That correction did not happen in this environment either, for the
same underlying reason: no browser automation is available here. Static inspection
during implementation showed no `@media` blocks were touched by the diff in
`AnalyzePage.css`/`DashboardPage.css`, and breakpoints (`max-width: 1280px`,
`max-width: 900px`) remain used consistently in the files reviewed — but this is a
weaker claim than actual rendering, and is not represented as a visual pass.

---

### 10. Regression Verification

| Check | Result |
|---|---|
| `npx tsc --noEmit` | **PASS** — zero errors |
| `npx vitest run` | **PASS** — 81 test files, 1136 tests, 0 failures (includes 8 new `Button.test.tsx` tests) |
| `npm run build` | **PASS** — `tsc --noEmit && vite build` succeeded; 199 modules transformed, `dist/` produced |
| Rendered/viewport verification (1280×720, 1440×900) | **NOT PERFORMED** — no browser automation available in this environment |

All of the above were independently re-run from a fresh extraction of the final
checkpoint (not just the working tree used during implementation), with a fresh
`npm install` against the existing lockfile.

**Environment limitation noted in the source report:** the workflow specifies
`npm.cmd ci`; this environment ran `npm install` instead after an initial `npm ci`
invocation was interrupted by the environment's own command timeout (network-bound, not
a project issue). `npm install` against the existing lockfile is dependency-equivalent
for this purpose — no lockfile changes were made or needed, and no `npm audit
fix`/`npm update` was run.

**MAX-1–MAX-5 regression spot-check (carried from both phases):**

- **MAX-1 (accessibility):** F-02 was the one genuine MAX-1-adjacent deviation found;
  now resolved (§8). No other MAX-1 regressions were encountered in either phase.
- **MAX-2 (loading):** no loading-state code touched; `aria-busy` plumbing preserved
  verbatim at every migrated call site.
- **MAX-3 (responsive):** no breakpoints, layout, or `@media` rules changed except
  incidental removal of now-empty selectors inside media-free base rules; verified no
  `@media` blocks were touched in `AnalyzePage.css`/`DashboardPage.css`.
- **MAX-4 (motion):** `Button` uses the same `--duration-fast`/`--easing-out` tokens
  every migrated button already used; no new transitions or animations added.
- **MAX-5 (Dashboard data):** no data, mapping, or visualization code touched — only
  the two retry buttons' markup/styling.

---

### 11. Scope / Diff Audit

Change list, verified by diffing the final working tree against a **second, pristine
extraction of the original supplied baseline ZIP** (no `.git` was available to diff
against at any point in this workstream — a filesystem/archive-level comparison was
used instead throughout):

**New files (3 source + 2 documentation):**
- `frontend/src/pages/components/Button.tsx`
- `frontend/src/pages/components/Button.css`
- `frontend/src/pages/components/Button.test.tsx`
- `docs/audits/SOC-IQ-FRONTEND-MAX-6-DESIGN-SYSTEM-AUDIT.md`
- `docs/audits/SOC-IQ-FRONTEND-MAX-6-DESIGN-SYSTEM-CLOSURE.md` (this document)

**Modified files (21):**
```
frontend/src/pages/AnalyzePage.css
frontend/src/pages/AnalyzePage.tsx
frontend/src/pages/DashboardPage.tsx
frontend/src/pages/InvestigationsPage.css
frontend/src/pages/InvestigationsPage.tsx
frontend/src/pages/ReportsPage.css
frontend/src/pages/ReportsPage.tsx
frontend/src/pages/SettingsPage.css
frontend/src/pages/SettingsPage.tsx
frontend/src/pages/analyze/AnalysisOptionsControls.css
frontend/src/pages/components/MetricCard.css
frontend/src/pages/components/MetricCard.tsx
frontend/src/pages/components/index.ts
frontend/src/pages/investigation/InvestigationHeaderCard.css
frontend/src/pages/investigation/InvestigationHeaderCard.tsx
frontend/src/pages/investigation/InvestigationWorkspacePage.css
frontend/src/pages/investigation/InvestigationWorkspacePage.tsx
frontend/src/pages/investigations/InvestigationsCsvExportAction.tsx
frontend/src/pages/reports/ReportExportAction.tsx
frontend/src/pages/settings/ExportDirectoryControl.tsx
frontend/src/pages/settings/ThemeControl.tsx
frontend/src/pages/settings/VirustotalControl.tsx
```

**Scope confirmation:** the same diff shows zero changes anywhere under `app/`
(Python/FastAPI), `src-tauri/` (Rust/Tauri), `database/`, `packaging/`,
`sidecar-core/`, `keystore-core/`, or any other non-frontend path. Every changed file is
under `frontend/` or `docs/audits/`.

**This consolidation pass:** confirmed via inspection that this documentation
consolidation itself changed no source file — only `docs/audits/*.md` content, per the
frozen-implementation constraint governing this pass.

---

### 12. Remaining Work

- **Viewport/rendered verification** at 1280×720 and 1440×900 for all six retry
  contexts and the three Analyze controls (default/hover/keyboard-focus/disabled) —
  genuinely not performed at any point in this workstream, not just deprioritized.
- **Badge classification** — the audit identified badge-like classes in `MetricCard`,
  `InvestigationThreatIntel`, `AnalyzePage`, and three Dashboard panels but did not
  individually classify them (legitimate-wrapper vs. duplicate vs. specialized). Still
  incomplete; out of this phase's F-01–F-04-only mandate.
- **Provider Detail page** — not audited at all in either phase. Implementation only
  confirmed, via the passing full test suite and TypeScript check, that the `Button`
  changes don't break it — not that it is visually consistent.
- **`.investigation-workspace__secondary-button`** (`BackToInvestigationsButton`) — a
  third, distinct neutral-outline button style, intentionally left unmigrated because
  it was never part of a confirmed finding.
- **`StatusBadge.css:4`'s untokenized `2px` padding** — real but trivial; noted by the
  audit as not worth its own finding ID, and not touched by implementation.

No further implementation should proceed on any of the above without a new, explicit
audit/authorization step, per this workstream's own process.

---

### 13. Artifact

```text
SOC-IQ-FRONTEND-MAX-6-DESIGN-SYSTEM-FULL.zip
```

This documentation-consolidation pass required exactly one rebuild of the archive, per
§8 of this pass's governing instructions — the previously-supplied ZIP already
contained both canonical documents individually, but this consolidated closure document
(replacing the prior, less-complete closure) had to be packaged into the checkpoint to
be the authoritative one. Nothing else in the archive changed.

| Property | Value (as originally supplied) | Value (this consolidation's rebuild) |
|---|---|---|
| Entries | 795 files | 795 files |
| Size | 2,472,633 bytes | see delivery message accompanying this archive |
| SHA-256 | `09e4bee9c0e8ebc5a0c5fa361d871a8dfe425d7629d338e78d86f3db8d6960ed` | see delivery message accompanying this archive |
| Fresh-extraction result | PASS | PASS — extracted into a clean directory; `app/`, `src-tauri/`, `database/`, `frontend/`, `docs/audits/` all present with expected contents; zero excluded directories (`node_modules/`, `dist/`, `target/`, `__pycache__/`, `.pytest_cache/`, `coverage/`, `.vscode/`, `.idea/`) present in the archive |
| Integrity | PASS | PASS |

(As with the prior closure document, this archive's own hash cannot be embedded inside
a file that is itself packaged into that archive — hashing necessarily happens after
this document's content is finalized. The size and SHA-256 for this pass's rebuild are
reported in the accompanying message, not chased to a false convergence here.)

**Diff against the originally-supplied ZIP:** a full recursive diff of both fresh
extractions (795 entries each) shows exactly one file differs — this closure document
itself. Every other file, including `Button.tsx`/`Button.css`/`Button.test.tsx`, the
21 modified page/component files from §11, and the archived audit document, is
byte-identical between the two archives. Source immutability for this consolidation
pass is confirmed.

Note on the size figure: the implementation-phase closure's own prior record of the
rebuilt archive's size (2,471,803 bytes) differs slightly from the 2,472,633 bytes
measured directly against the originally-supplied file at the start of this
consolidation pass. Per this pass's conflict-resolution rule (prefer actual
verification output over prior assumptions), the measured value is treated as
authoritative; the small delta is most likely explained by filesystem/zip-metadata
differences between packaging passes rather than a content change, since the entry
count and file contents were otherwise confirmed identical.

---

### 14. Final Verdict

```text
FRONTEND MAX-6 — PASS WITH DOCUMENTED CONDITIONS
```

The one open condition, carried across both phases of this workstream, is
viewport/rendered verification at 1280×720 and 1440×900, which no environment in this
workstream has been able to perform. Everything within reach — static-analysis audit,
TypeScript, the full test suite, the production build, and archive integrity — has been
independently verified, including a fresh extraction of the final checkpoint.

**STOP condition reached.** No further implementation (MAX-7, additional visual
polish, badge/Provider-Detail work, or reopening F-01 through F-04) should begin without
a new, explicit authorization step.
