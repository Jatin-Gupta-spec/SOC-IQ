# SOC-IQ Frontend MAX-6 — Design System + Visual Consistency
## Forensic Audit Report (Audit Only — No Source Modified)

Status: **AUDIT PHASE COMPLETE — AWAITING REVIEW/AUTHORIZATION FOR IMPLEMENTATION**

---

## 0. Baseline Integrity

```
git branch          : N/A — no .git directory present in the MAX-5 checkpoint archive
git rev-parse HEAD   : N/A
git status --short   : N/A
```

The extracted `SOC-IQ-FRONTEND-MAX-5-DASHBOARD-FULL.zip` does not contain a `.git` directory,
so the git-based provenance commands specified by the workflow cannot produce real output.
This audit instead used the zip contents directly as the baseline. **No source files
(`.tsx`, `.ts`, `.css`, tokens, tests, config) were modified during this phase** — the only
file written is this report, under `docs/audits/`.

Evidence type for this entire audit: **CODE/STYLE INSPECTION**. No dev server was started,
no browser rendering was captured, and no viewport screenshots were taken. Findings below
are derived from static analysis of the CSS/TSX source (grep-based inventory + manual
reading of matched rules), not from rendered visual verification. This should be corrected
with actual browser inspection at 1280×720 and 1440×900 before or during implementation.

---

## 1. Executive Summary

**Token layer verdict: mature, well-adopted, not a source of the findings below.**
`frontend/src/styles/tokens.css` (178 lines) defines a comprehensive semantic token set
(color, spacing, radius, typography, motion, elevation, opacity). Across the 37 non-core
component/page CSS files (~865 `var()` references), a raw-value sweep found:

- 0 raw hex colors outside `tokens.css` itself
- 0 raw `font-size` px values
- 0 raw `border-radius` px values
- 0 raw `gap` px values
- A small number of legitimate component-specific raw `width`/`height`/`min-width` values
  (status dots, sr-only 1px elements, chart-bar sizing, responsive max-widths matching
  known breakpoints) — none of these are findings; see §9 Non-Findings.

**The inconsistency in this codebase is not "missing tokens." It's "the same semantic
control implemented independently, multiple times, each pulling a slightly different
combination of otherwise-valid tokens."** The clearest expression of this is buttons
(§4) and, to a lesser extent, base-surface duplication in cards (§3).

**Confirmed P0 findings: 2** (retry-button fragmentation; Analyze-page focus-outline
deviation — related but distinct).
**Confirmed P1 findings: 1** (no shared Button primitive; button property drift beyond
retry buttons).
**Confirmed P2 findings: 1** (card base-surface rule duplicated instead of composed).
No P3s are called out individually; low-value items are folded into §9.

**Overall assessment:** SOC-IQ's design *token* system is in good shape and should not
be touched. The design *component* system has real gaps at the button/control layer
specifically. Cards, tables, badges, and page headers are in materially better shape
than buttons and should be treated with a much lighter touch.

---

## 2. Token Audit

| Check | Result |
|---|---|
| Token inventory exists (`tokens.css`, `styles/tokens/*.ts`) | Yes, mirrored per file header comment; not independently diffed line-by-line in this pass |
| Raw hex colors outside tokens | None found |
| Raw font-size px | None found |
| Raw border-radius px | None found |
| Raw gap px | None found |
| Raw padding/margin px | 1 instance (`StatusBadge.css:4`, `padding: 2px var(--space-sm)` — the `2px` has no matching space token; low-value, see §9) |
| Raw border-width (px) | Several (`1px solid transparent`, `2px solid transparent`) — legitimate; no `--border-width-*` token exists, and `transparent` colors are an intentional layout-shift-avoidance pattern (reserving space for a border that appears on hover/selected) |
| Unused/underused tokens | Not exhaustively verified this pass — would need a token-by-token grep sweep against both `.css` and `.ts` consumers; flagged as a follow-up, not a finding |

**Verdict: do not run a mechanical tokenization pass. There is essentially nothing left
to tokenize at the raw-value level.**

---

## 3. Component Audit — Cards / Surfaces

Shared primitive: `pages/components/Card.css` (`.card`) —
`background: var(--color-surface-primary)`, `border: 1px solid var(--color-border-default)`,
`border-radius: var(--radius-lg)`, `padding: var(--space-card-padding)`.

| Component | Relationship to `.card` | Classification |
|---|---|---|
| `MetricCard.css` (`.metric-card`) | Duplicates the exact same 4 base properties (surface-primary / border-default / radius-lg / card-padding) verbatim, then adds its own header/label/value/trend structure | **B — legitimate specialized component**, but the base-surface rule is copy-pasted rather than composed. See Finding F-03. |
| `InvestigationHeaderCard.css` (`.investigation-header-card`) | Same exact duplication of the 4 base properties | Same as above — Finding F-03 |
| `DashboardPage.css` usage of `.card` | Uses `.card` directly (`.dashboard-page__grid > section > .card`), no duplication | **Exemplary — non-finding** |
| `SettingsPage.css` `.settings-page__skeleton-card` | Not a real card — a skeleton loading placeholder sized to approximate card heights (120px / 96px, unrelated to `.card`) | Not a card-system finding; naming is arguably misleading but out of scope |

No visual divergence was found — every real card renders with identical surface/border/
radius/padding because the values, though duplicated, are identical. This is a
maintainability issue (three places to edit if the base card treatment ever changes),
not a currently-visible inconsistency.

---

## 4. Component Audit — Buttons (expanded beyond retry)

**No shared Button primitive exists anywhere in the codebase** (confirmed: no file
matching `*button*`/`*Button*` other than the per-feature CSS/TSX already covered).
Every interactive button is a hand-rolled, page-scoped class. Inventorying the "filled
primary" and "outlined" families found at least **two different unmanaged specs for
what is visually the same button style**, plus the previously-identified retry-button
fragmentation:

**"Filled primary" family A** (Settings/Investigations/Reports retry buttons):
`radius-sm`, `padding: var(--space-sm) var(--space-lg)`, `font-size-body`, no local
`:disabled` or `:focus-visible` (inherits global).

**"Filled primary" family B** (Investigations export button, Reports action button):
`radius-md`, `padding: var(--space-xs) var(--space-sm)`, `font-size-body-small`,
explicit local `:disabled` (`opacity: 0.7`).

These two families are both "brand-purple filled button," used for comparable actions
(retry / export / act-on-item), but differ in radius, padding scale, and font size —
close enough to look "almost the same" and different enough to look unintentional side
by side.

**"Outlined info" family** (Analyze page only — start button, browse button, retry
button, and the checkbox focus ring in `AnalysisOptionsControls.css`): `radius-md`,
`border: 1px solid var(--color-status-info)`, transparent background, and — notably —
**every one of these four controls overrides `:focus-visible` to use
`--color-status-info` instead of the global `--color-border-focus`** defined once in
`globals.css` (`:focus-visible { outline: 2px solid var(--color-border-focus); }`).

This is not a one-off mistake on the retry button — it's a page-wide, internally
consistent alternate focus treatment scoped to Analyze. That changes the read: it looks
like a deliberate (if undocumented) design choice for that page rather than an accident,
but it still means SOC-IQ currently has **two different focus-indicator colors in
production**, which is a direct, evidence-based MAX-1 deviation regardless of intent.

**Dashboard retry button**: both occurrences (`DashboardPage.css:230`) declare only
`min-height` and `padding` — no color, background, or border. `globals.css` has no
base `<button>` element reset. Confirmed by reading the exact JSX (`DashboardPage.tsx`
lines ~108 and ~174): plain `<button type="button" className="dashboard-page__retry-button">`
with no other class. **This renders as an unstyled native browser button** — the most
severe single finding in this audit, because it's not just inconsistent, it's currently
broken relative to the rest of the product's visual language.

---

## 5. Component Audit — Tables

Shared primitive: `pages/components/DataTable.css` / `DataTable.tsx`, well-documented
(inline comments cite specific phase/part numbers for several non-obvious decisions:
horizontal scroll containment, cell text wrapping to avoid silent clipping, opt-in
interactive rows). This is the strongest-documented shared component found in the audit.

`<table>` element usage was traced directly in source (not just CSS class names, to
avoid false positives from `__row` flex-layout classes that aren't tables at all):

- Real `<table>` markup outside `DataTable.tsx`: **exactly one** —
  `InvestigationOverviewRisk.tsx` (`.investigation-overview-risk__breakdown`), a small
  5-column IOC-category risk breakdown embedded in a card.
- Every other tabular UI (Investigations, Reports, Dashboard recent-investigations,
  IOC workspace, threat-intel results) uses the shared `DataTable` component.

The one custom table has a code comment explicitly stating it reuses an established
bordered-box treatment rather than inventing a new one. Its th/td styling is close to
but not identical to `DataTable`'s: `padding: var(--space-xs) var(--space-sm)` (vs.
`DataTable`'s uniform `var(--space-sm)`) and `border-bottom: var(--color-border-default)`
on **both** th and td (vs. `DataTable`'s `border-default` on th / `divider-secondary`
on td). This reads as an intentional, denser variant for an in-card stat table, not a
duplicate implementation — classified **legitimate specialized component**, with the
td-border-color choice noted as a minor (P3) inconsistency, not a finding worth its own ID.

**Verdict: tables are in good shape. Do not touch `DataTable` or the risk-breakdown table.**

---

## 6. Component Audit — Badges

`StatusBadge.css`/`.tsx` is a single, well-built shared component with six semantic
variants (`neutral`/`info`/`success`/`warning`/`error`/`critical`) correctly mapped to
the corresponding status/severity color tokens. Adoption was not exhaustively traced
component-by-component in this pass (unlike buttons and tables, where every user was
individually confirmed) — files with badge-*like* class names (`MetricCard`,
`InvestigationThreatIntel`, `AnalyzePage`, three Dashboard panels) were identified but
not individually classified into legitimate-wrapper vs. duplicate vs. specialized.
**This is the one audit category from the requested scope that is incomplete** — see
§10 Follow-up.

---

## 7. Component Audit — Page Headers

Shared primitive: `pages/components/PageHeader.tsx`/`.css`, with a doc comment stating
its purpose explicitly ("every mock page composes this instead of hand-rolling its own
title/description markup ... so the eight pages share one consistent heading structure").
Confirmed used by all six top-level pages that have a page header (Analyze, Investigation
Workspace, Settings, Investigations, Reports, Dashboard). This is exemplary — a clean
non-finding.

---

## 8. Component Audit — Empty / Info States

`InfoNote.css`/`.tsx` provides a consistent dashed-border, muted-text treatment used
across investigation, settings, and dashboard panels for no-data/informational messaging.
Error states specifically route through the same page-scoped "message + retry button"
pattern already covered in §4 — so the retry-button fragmentation is the dominant
error-state inconsistency; there isn't a separate, distinct empty-state inconsistency
on top of it. Not exhaustively traced per-page (see §10).

---

## 9. Cross-Page Consistency Matrix

Legend: ✅ consistent / verified · ⚠️ inconsistency found (see Finding ID) · ➖ not
directly audited this pass (no claim made either way)

| Category | Dashboard | Analyze | Investigations | Workspace | Reports | Settings | Provider Detail |
|---|---|---|---|---|---|---|---|
| Page header | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ➖ |
| Cards | ✅ (uses `.card` directly) | ➖ | ➖ | ✅ (`InvestigationHeaderCard`, F-03) | ➖ | ➖ | ➖ |
| Tables | ✅ (`DataTable`) | n/a | ✅ (`DataTable`) | ✅ (`DataTable` + 1 custom, §5) | ✅ (`DataTable`) | n/a | ➖ |
| Buttons | ⚠️ F-01 (unstyled) | ⚠️ F-02 (focus color) | ⚠️ F-01 (family A) | ➖ | ⚠️ F-01 (family A) | ⚠️ F-01 (family A) | ➖ |
| Badges | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| Empty/error state | ⚠️ (inherits F-01) | ⚠️ (inherits F-02) | ⚠️ (inherits F-01) | ➖ | ⚠️ (inherits F-01) | ⚠️ (inherits F-01) | ➖ |
| Focus indicator | ✅ (global default) | ⚠️ F-02 | ✅ | ➖ | ✅ | ✅ | ➖ |

Cells marked ➖ were not directly inspected in this pass and should not be read as
"consistent" — only the categories above with ✅/⚠️ were actually traced through source.
Provider Detail was not audited at all this pass.

---

## 10. Findings

### F-01 — Retry-button fragmentation, including unstyled Dashboard occurrence
- **Severity:** P0
- **Category:** Semantic/system inconsistency + accidental browser-default styling
- **Affected pages:** Dashboard, Settings, Investigations, Reports (Analyze has its own
  variant, see F-02)
- **Affected files/classes:** `DashboardPage.css:230` (`.dashboard-page__retry-button`),
  `SettingsPage.css:64` (`.settings-page__retry-button`),
  `InvestigationsPage.css:16` (`.investigations-page__retry-button`),
  `ReportsPage.css:16` (`.reports-page__retry-button`)
- **Observed behavior:** Three different implementations for the same "retry after
  error" action. Settings/Investigations/Reports share one filled-brand-button spec
  (effectively identical). Dashboard's two occurrences declare only `min-height`/
  `padding`, with no color/background/border and no base `<button>` reset anywhere in
  `globals.css` to fall back on — this renders as a plain native browser button.
- **Expected/system behavior:** One retry treatment, used identically everywhere the
  same semantic action occurs.
- **Evidence:** Direct CSS rule comparison (quoted in §4/prior turn) + JSX confirmation
  that Dashboard's button has no other class to inherit styling from.
- **Why it matters:** This is the most user-visible inconsistency in the app — an
  unstyled button next to an otherwise polished dark UI reads as broken, not just
  inconsistent.
- **Potential implementation direction (not to be implemented in this phase):** Once a
  shared Button primitive is decided (see F-04), retire all four page-local classes in
  favor of it. Do not build a bespoke `RetryButton` first — evaluate whether a
  general-purpose primitive with a `variant="primary"` (or similar) already covers this
  before adding a retry-specific abstraction.
- **Scope dependency:** Implementation should happen together with F-04 (Button
  primitive decision), not independently — fixing F-01 in isolation risks creating a
  fifth bespoke implementation.

### F-02 — Analyze page uses a page-wide alternate focus-indicator color
- **Severity:** P0
- **Category:** Accessibility deviation from MAX-1 global standard
- **Affected pages:** Analyze only
- **Affected files/classes:** `AnalyzePage.css` — `.analyze-page__native-browse-button:focus-visible`,
  `.analyze-page__start-button:focus-visible`, `.analyze-page__retry-button:focus-visible`
  (all three, lines 40-41, 76-77, 122-123); `AnalysisOptionsControls.css:36-37`
  (checkbox `:focus-visible`)
- **Observed behavior:** All four interactive controls on the Analyze page override the
  global `:focus-visible` rule (`outline: 2px solid var(--color-border-focus)` from
  `globals.css`) with `outline: 2px solid var(--color-status-info)` instead. This is
  internally consistent within Analyze but inconsistent with every other page in the
  matrix (§9), all of which rely on the global default.
- **Expected/system behavior:** Per MAX-1, one focus-indicator color across the app
  unless there's a documented, deliberate reason for a page-scoped exception.
  No such documentation was found.
- **Evidence:** Direct grep confirming all 4 occurrences share the exact same override.
- **Why it matters:** Focus-indicator consistency is a core accessibility signal for
  keyboard users; a page-scoped exception — intentional or not — should be a documented
  decision, not something discovered by audit.
- **Potential implementation direction (not to implement now):** Either (a) this was
  deliberate and should be documented as an intentional Analyze-page accent, in which
  case leave it and record it as an accepted variation, or (b) it was drift and should
  converge on the global focus token. This audit takes no position — it's a product/
  design decision, not an engineering one.
- **Scope dependency:** MAX-1 regression — flag for explicit accept/reject rather than
  silently "fixing."

### F-03 — Card base-surface rule duplicated instead of composed
- **Severity:** P2
- **Category:** Token/design-system underuse (not a visible inconsistency)
- **Affected files/classes:** `MetricCard.css` (`.metric-card`),
  `InvestigationHeaderCard.css` (`.investigation-header-card`) both duplicate `.card`'s
  exact `background-color` / `border` / `border-radius` / `padding` declarations
  verbatim rather than composing/extending `.card`.
- **Observed behavior:** No visible inconsistency — all three surfaces render
  identically because the duplicated values are identical to `.card`'s.
- **Expected/system behavior:** Base surface treatment defined once, specialized
  components add to it rather than repeat it.
- **Why it matters:** Purely a maintenance-cost finding — if the base card treatment
  changes in the future, three places need updating instead of one. Not urgent.
- **Potential implementation direction:** Low priority; only worth doing opportunistically.

### F-04 — No shared Button primitive; two overlapping "filled primary" specs exist
- **Severity:** P1
- **Category:** Repeated visual inconsistency / missing shared component
- **Affected files/classes:** `InvestigationsPage.css:53` (`.investigations-page__export-button`)
  and `ReportsPage.css:53` (`.reports-page__action-button`) — both `radius-md`,
  `padding: var(--space-xs) var(--space-sm)`, `font-size-body-small` — versus the F-01
  "family A" retry buttons at `radius-sm`, `padding: var(--space-sm) var(--space-lg)`,
  `font-size-body`. Both families are brand-purple filled buttons for comparable-weight
  actions.
- **Observed behavior:** Two different, unmanaged specs for what reads as the same
  button style, each internally consistent but inconsistent with the other.
- **Expected/system behavior:** A single shared primitive with size/variant props,
  covering both use cases deliberately rather than by accident.
- **Why it matters:** This is the root cause underlying F-01 — there's no primitive to
  converge on yet, which is exactly why four independent retry-button implementations
  exist.
- **Potential implementation direction (not to implement now):** This is the
  prerequisite decision for fixing F-01. Needs an explicit design decision on the
  primitive's API (variant/size) before any page is touched.
- **Scope dependency:** Blocks F-01's implementation.

---

## 11. MAX-1 / MAX-2 / MAX-3 / MAX-4 / MAX-5 Regression Findings

- **MAX-1 (accessibility):** F-02 is a genuine MAX-1-adjacent deviation (see above).
  No other MAX-1 regressions were encountered.
- **MAX-2 (loading consistency):** No regressions found in this pass; loading states
  were not separately re-audited beyond noting `Skeleton.css` exists and is used
  (e.g., `DashboardSkeleton` referenced in `DashboardPage.tsx`).
- **MAX-3 (responsive):** Not verified at runtime (no rendered viewport inspection
  performed — see §0). Static inspection shows `@media (max-width: 1280px)` and
  `@media (max-width: 900px)` breakpoints used consistently in the files reviewed
  (`DashboardPage.css`, `DashboardMetrics.css`), matching the two required target
  widths. No breakage evidence found, but this is a weaker claim than actual rendering.
- **MAX-4 (motion):** No regressions found; transition tokens (`--duration-fast`,
  `--easing-out`) used consistently in every button/control reviewed.
- **MAX-5 (dashboard data):** Not touched or re-examined; out of scope for this pass
  beyond the two retry-button occurrences already covered under F-01.

---

## 12. Recommended Fix Order (sequencing only — not authorization to implement)

1. **F-04** — decide the shared Button primitive's shape (this unblocks everything else)
2. **F-01** — retire the four retry-button implementations in favor of the primitive,
   fixing the unstyled Dashboard case first if sequencing needs to be split
3. **F-02** — explicit accept/reject decision on Analyze's focus-outline color (design
   decision, not implementation work)
4. **F-03** — opportunistic, no urgency

---

## 13. Explicit Non-Findings (audited and intentionally left alone)

- **Raw CSS values in general** — the token layer is mature; do not run a mechanical
  tokenization pass (§2).
- **Component-specific raw pixel dimensions** (status dots, sr-only elements, chart-bar
  heights, dashboard breakpoint max-widths) — legitimate, component-specific, not
  duplicates of any token.
- **`StatusBadge.css:4`'s `2px`** vertical padding with no matching space token — real
  but trivial; not worth its own finding ID.
- **`CommandPalette`'s borderless, bottom-border-only search input** — an intentional,
  conventional command-palette pattern, correctly distinct from standard form inputs.
- **`InvestigationOverviewRisk.tsx`'s custom `<table>`** — a legitimate denser variant
  for an in-card stat breakdown, explicitly commented as reusing established treatment;
  do not consolidate into `DataTable`.
- **`DataTable`, `PageHeader`, `Card`, `InfoNote` as shared primitives** — all
  well-built and well-adopted; do not modify, rewrite, or "improve" them as part of
  MAX-6.

---

## 14. Follow-up / Incomplete Audit Areas

Given the scope of this pass, two requested categories were not carried to the same
depth as buttons/tables/cards/page-headers and should not be treated as clean until
explicitly audited:

- **Badges** (§6) — adoption of `StatusBadge` vs. the badge-like classes in
  `MetricCard`, `InvestigationThreatIntel`, `AnalyzePage`, and three Dashboard panels
  was identified but not individually classified.
- **Provider Detail page** — not audited at all this pass (missing from the matrix
  entirely).
- **Runtime/visual verification** — everything above is static code inspection; no
  rendered-viewport confirmation at 1280×720 / 1440×900 has been performed.

---

## Verdict

**AUDIT COMPLETE FOR: tokens, buttons, cards, tables, page headers, empty/info states
(partial), MAX-1/3/4 regression spot-check.**
**INCOMPLETE FOR: badges (partial), Provider Detail (not started), inputs/controls
beyond the samples in §4 (partial), runtime/visual verification (not performed).**

No source code was modified. No implementation has begun. This audit is submitted for
review; MAX-6 implementation should not start until it — and specifically the F-02
design decision — is explicitly accepted.
