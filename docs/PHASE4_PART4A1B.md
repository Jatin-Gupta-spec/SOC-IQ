# Phase 4A-1B: Continuation Checkpoint

## Environment constraint (read this first)

This session ran in a sandbox with **no network access** and
**PySide6 / pytest not installed and not installable**
(`pip install` fails with "No matching distribution found" for
every package, since there is no index to reach). As a result:

- The GUI could not be launched.
- The test suite (`tests/`, including all of `tests/gui/`) could
  not be run.
- No offscreen Qt rendering or responsive validation (1280x720 /
  1440x900 / 1920x1080) was performed.

Every change in this checkpoint is therefore verified only by
**static reading and `python3 -m compileall`** (confirms the whole
`app/` and `tests/` tree is free of syntax errors), never by
executing the app or the test suite. Baseline and post-change test
counts in the Final Report below are marked "not executed" rather
than fabricated pass/fail numbers. The next session, in an
environment with PySide6 and pytest available, should run the full
suite before trusting this checkpoint's changes are behaviorally
safe, and should specifically re-run:

- `tests/gui/test_phase3e_acceptance.py`
- `tests/gui/test_investigation_workspace_threat_intel.py`
- `tests/gui/test_threat_intel_page_url.py`
- `tests/gui/test_ioc_summary_risk_relevance.py`
- `tests/gui/test_ioc_summary_url.py`

since those are the files closest to what changed here.

## Session 2 addendum — Design System / Accessibility audit

This session used the enabled **Design** plugin's design-system and
accessibility-review disciplines (audit for token consistency,
contrast, and component drift) as the working method, applied
directly to source since the plugin's own skill content isn't
mounted as readable files in this sandbox. Same environment
constraint as above still applies: no PySide6, no rendering, no
test execution. Everything below is either (a) a mechanical,
zero-behavior-change token substitution verified by exact numeric
match, or (b) a numeric/color-math finding that does not touch
code, reported for a human (or a future session with a renderer)
to act on.

### 4. Magic-number spacing/typography -> design tokens (zero behavior change)

Design-token consistency audit found five hardcoded pixel values in
widget code that already had an exact-matching named token in
`app/gui/design/tokens/`. Every substitution below is a like-for-
like numeric swap (e.g. `16` -> `Spacing.LG` where
`Spacing.LG == 16`), so nothing renders differently -- this is
purely "reference the constant instead of the literal" for future
maintainability, not a redesign:

- `app/gui/pages/investigation_workspace.py`: all four tab layouts
  (`overview_layout`, `iocs_layout`, `intel_layout`,
  `correlations_layout`) used raw `setContentsMargins(0, 16, 0, 0)`
  / `setSpacing(16)`. Now `Spacing.LG`.
- `app/gui/widgets/ioc_summary_widget.py`: significance-badge cell
  used raw `setContentsMargins(4, 2, 4, 2)`. Now
  `Spacing.XS, Spacing.XXS, Spacing.XS, Spacing.XXS`.
- `app/gui/widgets/sidebar.py`: the "NAVIGATION" section-eyebrow
  label used raw `font-size: 11px; font-weight: 600;` and
  `padding: 0 12px ...px 12px` -- these exactly match
  `FontSize.LABEL` (11), `FontWeight.SEMIBOLD` (600), and
  `Spacing.MD` (12), so all three are now token references. The
  "SOC-IQ" wordmark's `font-weight: 700` and `padding-bottom: 4px`
  were likewise swapped for `FontWeight.BOLD` and `Spacing.XS`
  (exact matches). Its `font-size: 20px` was **deliberately left as
  a literal** -- no token in the `FontSize` scale
  (12/16/18/22/28...) equals 20, and rounding it to the nearest
  token (18 or 22) would be a real, unverified visual size change
  to the brand wordmark, not a token-consistency fix. Flagging this
  for a human/future-session call: either add a `FontSize.WORDMARK
  = 20` token (if 20px is intentional and should stay named) or
  confirm it should actually be `TITLE` (18) / `HEADING` (22).

Verified via `python3 -m py_compile` + full `compileall` after each
edit; no other magic-number spacing/typography values were found
that had an exact token match (a broader sweep found further raw
pixel values, but each either had no matching token or appeared in
contexts -- e.g. hairline `1px` borders, `999px` circular radius
already expressed via `Radius.CIRCLE` elsewhere -- where forcing a
token match would be guessing, not verifying).

### 5. Accessibility contrast audit (WCAG 2.1 AA) -- findings only, no code changed

Since actual rendering isn't available, contrast was checked the
only way that's verifiable without Qt: computing WCAG relative
luminance directly from the hex values already defined in
`app/gui/design/tokens/colors.py`, using the standard
sRGB-linearization formula. This is exact math, not a rendering
approximation, for any color pair that is genuinely flat
text-on-background (no alpha blending involved).

**Flat pairs (verified exact):**

| Pair | Ratio | AA normal text (4.5:1) | AA large text/UI (3:1) |
|---|---|---|---|
| text_primary on bg_primary | 17.58:1 | PASS | PASS |
| text_secondary on bg_primary | 12.15:1 | PASS | PASS |
| text_muted on bg_primary | 7.33:1 | PASS | PASS |
| text_disabled on bg_primary | 3.79:1 | FAIL | PASS |
| severity_low on bg_primary | 8.28:1 | PASS | PASS |
| severity_medium on bg_primary | 12.32:1 | PASS | PASS |
| severity_high on bg_primary | 6.73:1 | PASS | PASS |
| **severity_critical on bg_primary** | **3.91:1** | **FAIL** | PASS |
| brand_primary on bg_primary | 4.46:1 | FAIL | PASS |
| status_error on bg_primary | 5.01:1 | PASS | PASS |

`text_disabled` failing AA-normal is expected and not a defect --
WCAG doesn't require disabled controls to meet text contrast.

`severity_critical` (#DC2626) failing AA-normal at 3.91:1 **is** a
real finding worth flagging: it is the *worst*-contrast severity
color of the four, on the single severity level a SOC analyst most
needs to notice immediately. It was traced to a concrete, currently
shipping usage: `app/gui/pages/risk_dashboard_page.py` sets this
color directly as literal `QLabel` text color
(`color: {severity_colors["CRITICAL"]}`) on the card surface, i.e.
exactly the flat text-on-background case this contrast number
describes. Two other call sites
(`app/gui/widgets/risk_gauge_widget.py`,
`app/gui/widgets/dashboard/featured_investigation_card.py`) also
reference `palette.severity_critical`, but were **not** confirmed
to render it as flat body text -- they may use it as a progress-bar
fill or an accent stripe, which have different/no WCAG text
requirements; this needs a follow-up read (or, better, an actual
render) to classify before any color change.

`StatusBadge` (used for most other CRITICAL-severity displays,
e.g. the sidebar dashboard's severity badges) does **not** hit this
exact number -- it renders the same `severity_critical` hex as text
on a *~12%-alpha tinted* version of that same red
(`app/gui/components/feedback/status_badge.py`), not on flat
`bg_primary`. The true composited contrast in that case depends on
what's actually behind the badge at render time (alpha blending),
which cannot be computed correctly without knowing the Qt
compositing result -- so that specific case is explicitly left
unverified rather than estimated.

**No color values were changed.** `Colors.Severity.CRITICAL` is
referenced widely enough (badges, charts, gauges, timeline) that
changing it is a real design decision needing visual sign-off, not
something to do blind. Recommendation for the next session with a
renderer: verify the `risk_dashboard_page.py` flat-text case
visually, and if it's confirmed to read as low-contrast in practice,
either lighten `Colors.Severity.CRITICAL` slightly (e.g. toward
`#E5484D`/`#F04438`-range reds, which land closer to 4.5:1+ against
this same `bg_primary` while staying clearly "red"), or render
Critical-severity flat text at a bolder/larger weight so it
qualifies under the 3:1 large-text/UI-component threshold instead
(it already meets that one).

### Design-system consistency: re-confirmed clean

Re-swept after this session's edits: zero raw hex colors outside
`design/tokens/colors.py` / `design/theme/palette.py`; zero emoji
or Unicode-glyph icons in `app/gui`; the one duplicate badge-color
map from the previous session stays fixed; no new duplicates
introduced.

## What changed this session

All changes are surgical (no redesign, no architecture change, no
widget-type changes) because layout/visual changes could not be
verified without a renderer. Scope was deliberately narrowed to
things verifiable by static reading:

### 1. Consolidated a duplicated severity->badge color mapping

`app/gui/widgets/dashboard/featured_investigation_card.py` carried
its own `_SEVERITY_BADGE_MAP`, explicitly flagged by its own code
comment as "identical to `ThreatIntelligenceFeedWidget`'s map,
hoist to one source of truth." The shared helper already existed
at `app/gui/utils/badge_mapping.severity_to_badge_type()` (used by
`live_security_events_widget.py`) but was missing an `"info"`
entry that the local map had.

- Added `"info": BadgeType.INFO` to the shared map in
  `app/gui/utils/badge_mapping.py`.
- Removed the duplicate map from `featured_investigation_card.py`
  and switched it to call the shared helper.
- This is the only remaining "competing badge system" found in the
  codebase; `system_status_section.py` and
  `component_showcase_page.py` map a *different* input vocabulary
  (system health status strings / demo labels, not IOC/investigation
  severity) to the same `BadgeType` values, which is legitimate
  reuse of the same color semantics, not drift risk, so those were
  left as-is.

### 2. Fixed stale/misleading "SHA256-only" comments and docstrings

Phase 3E (already complete per the checkpoint prompt) made all four
IOC categories (SHA256, IPv4, domains, URLs) carry threat-intel
enrichment identically. The *code* in three files already reflected
this correctly, but leftover pre-Phase-3E prose still asserted
"only SHA256 hashes carry threat-intelligence enrichment," which is
exactly the kind of comment that could mislead a future session
into reintroducing SHA256-only behavior (explicitly forbidden by
this checkpoint's own rules). Fixed in:

- `app/services/ioc_detail_context.py` (module-level comment
  above `_ENRICHABLE_IOC_TYPES`)
- `app/gui/pages/investigation_workspace.py`
  (`_on_ioc_selected` docstring)
- `app/gui/widgets/ioc_summary_widget.py` (module-level comments
  above `_ENRICHABLE_IOC_TYPES` / `_TI_NOT_SUPPORTED_LABEL` /
  `_TI_UNKNOWN_LABEL`, and the `load_investigation()` docstring)

No behavior changed in any of these three files -- confirmed by
reading `_ENRICHABLE_IOC_TYPES = frozenset({"sha256", "ipv4",
"domains", "urls"})` was already correct in both places before this
session touched anything.

Checked and confirmed NOT stale (left unchanged): similar-sounding
comments in `app/reporting/{html,markdown,pdf}_exporter.py` about
"hashes stay first" (this is about preserving *display order* for
backward compatibility, still accurate) and in
`app/scoring/engine.py` about "scored identically to the original
hash-only behavior" (correctly describes the Phase 3E parity fix,
still accurate).

### 3. Removed dead imports

Four unused imports found via a static import-usage scan (each
import name appeared nowhere else in its file):

- `app/gui/components/feedback/file_dropzone.py`: unused
  `QHBoxLayout`
- `app/gui/pages/analyze_page.py`: unused `SectionHeader`
- `app/gui/pages/risk_dashboard_page.py`: unused `GlassCard`,
  `BadgeType`, `StatusBadge`

Removing an unused import cannot change runtime behavior, so this
was judged safe without test execution.

## Investigated and found to be non-issues

- `app/gui/pages/risk_dashboard_page.py` constructs `MetricCard`
  and severity-count labels with hardcoded placeholder values
  ("12 Investigations", "68.4 / 100", etc.) in `__init__`. This
  looked like fabricated/fake data at first read, but
  `self.refresh()` is called at the end of `__init__` and
  immediately overwrites every one of those values from
  `InvestigationService.list_all()`. Not a bug; left as-is.
- `app/services/dashboard_threat_feed_service.py` /
  `DashboardController.get_threat_feed()` are no longer called by
  `DashboardPage` (per its own refresh() comment: "the dashboard no
  longer renders the Threat Intelligence Feed widget"), but
  `tests/test_dashboard_services.py` still exercises them directly.
  Left in place -- removing tested, still-correct code without the
  ability to run the test suite would be an unverifiable risk for
  no behavioral benefit.

## Not attempted this session (and why)

Per the 4A-1B focus list, items 1-8 (Investigation Workspace visual
hierarchy, Threat Intelligence visual polish, IOC presentation,
Dashboard refinement, History table hierarchy, Analyze workflow
polish, loading/error/empty states, animation usage) were **not**
attempted beyond the correctness fixes above. All of those are
layout/visual/animation changes to PySide6 widgets; with no
renderer available in this sandbox there was no way to verify such
a change doesn't clip, overlap, or otherwise regress the UI, and
the checkpoint rules explicitly prohibit claiming visual validation
that wasn't performed. Making blind layout edits to a ~500-line
page like `investigation_workspace.py` was judged higher-risk than
value in an environment where a mistake can't be caught before
handoff.

**Recommended for the next session** (needs PySide6 + pytest):
first run the full suite to get a real baseline, then work through
the 4A-1B focus list in order, validating each screen at
1280x720 / 1440x900 / 1920x1080 as changes are made, per the
original checkpoint instructions.
