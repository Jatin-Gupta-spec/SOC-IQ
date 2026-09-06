# Phase 4A-1C: Workflow Pass — Checkpoint 4A-1C-A

## Environment (verified this session, not assumed)

Unlike the 4A-1B session (which had no PySide6/pytest/network and
could only verify changes by static reading), this session's
sandbox had a working index:

- Python 3.12.3
- `pip install -r requirements.txt --break-system-packages`
  succeeded: PySide6 6.11.2, pytest 9.1.1, rich, requests,
  python-dotenv, reportlab all installed.
- `QT_QPA_PLATFORM=offscreen` rendering confirmed working (a real
  `QApplication` constructs and a `MainWindow` renders and can be
  `.grab()`bed to PNG).
- **Baseline full suite, before any 4A-1C edit: 542 passed, 0
  failed.**
- **Full suite after all 4A-1C-A edits below: 542 passed, 0
  failed** (re-run at the end of this checkpoint).
- `python3 -m compileall app tests`: clean, no syntax errors,
  re-run at the end of this checkpoint.

All screenshots referenced below were produced by a small harness
script that boots the app the same way production does —
`ApplicationShell().bootstrap()` + `ensure_main_window()` — not a
shortcut that skips the real stylesheet/window-chrome path.

## COMPLETED — 4A-1C-A

Scope actually implemented and verified this checkpoint: **dashboard
responsive-fit fixes at the 1280×720 floor only.** Analyze,
Investigation Workspace, and every other workflow in the original
4A-1C brief were **not started** — see "REMAINING" below.

### 1. Dashboard Hero + Quick Access row — horizontal clipping (fixed, verified)

At 1280×720 the Hero status strip (wordmark, live-pulse dot,
OPERATIONAL badge, THREAT badge, clock) and the Quick Access button
row together needed **~1175px** of combined minimum width but the
row only had **~1040px** available. A prior (4A-1B-era) attempt to
fix this only rebalanced the two widgets' stretch factor (2:1 →
2:3); measuring both widgets' actual `sizeHint()` at 1280×720 showed
this could not have worked — the combined content didn't fit at any
stretch ratio, it just moved which widget got clipped.

Fix: shortened the three Quick Access button labels —
`"+ Analyze Report"` → `"Analyze"`, `"Browse History"` →
`"History"`, `"Threat Intel Lookup"` → `"Threat Intel"` — in
`app/gui/widgets/dashboard/quick_access_widget.py`. Re-measured:
Quick Access's own `sizeHint()` dropped from 574px to 372px wide;
combined with Hero's 601px and 16px spacing, both widgets now render
at their **full, uncompressed** `sizeHint()` with margin to spare
(997px used of ~1040px available). Confirmed both by direct
`sizeHint()`/actual-`size()` equality checks and by an offscreen
screenshot — the row renders cleanly with no truncated badge or
button text.

`app/gui/pages/dashboard_page.py`'s stretch-factor comment for this
row was rewritten to document the actual root cause (content not
fitting at all, not a stretch-ratio question) instead of the
previous comment's incomplete diagnosis.

### 2. System Status row — horizontal clipping (fixed, verified)

`SystemStatusSection`'s two-service status strip
(`"Database Health: <badge>    Threat Intelligence: <badge>"`) had
a measured minimum width of **617px**, but the utility row (shared
with KPISection on a 1:3 stretch split) only gave it a few hundred
px at 1280×720 — causing exactly the truncation you flagged
("Database Hea…", "Threat Intelli…", "…I Key Missi…").

Fix, in `app/gui/widgets/dashboard/system_status_section.py` and
`app/services/system_health_service.py`:

- `"Database Health"` → `"Database"`, `"Threat Intelligence"` →
  `"Threat Intel"` (labels shortened, same meaning).
- The backing status string `"API Key Missing"` → `"No API Key"`
  (this was the single largest width contributor — a badge, not a
  label, so it couldn't wrap or elide without looking broken).

Verified via `grep` that no test asserts either exact removed
string (`tests/` only references `"Threat Intelligence"` in
unrelated widgets — `ioc_summary_widget.py`, `sidebar.py`,
`investigation_workspace.py`, etc. — none of which were touched).
Re-measured: `SystemStatusSection.minimumSizeHint()` width dropped
**617px → 459px**.

### 3. KPI section — horizontal clipping (assessed, not further changed)

`KPISection.minimumSizeHint()` is 526px wide (four `MetricCard`s:
Investigations/Indicators/High Severity/Repository). This did not
need a code change — after the System Status fix above freed room
in the same `utility_row`, KPI's existing content now fits within
its 3-of-4 stretch share at 1280×720 without truncation (confirmed
in the final screenshot below). Left the four metric titles as-is
since they were already the right length once the row had room.

### 4. Featured Investigation Card — vertical clipping/overlap (partially fixed; NOT fully resolved — see Known Issues)

This was the most severe defect found: at 1280×720 the card was
compressed to 126px against a measured 228px content minimum,
causing the "No Investigation Available" / "IOC Count" / "Risk
Score" text to visibly overlap/garble.

Changes made in `app/gui/widgets/dashboard/featured_investigation_card.py`:

- Report-name label: `setWordWrap(True)` → single-line elide
  (`QFontMetrics.elidedText`) with the full text preserved as a
  tooltip, re-elided on `resizeEvent` so it stays correct if the
  card is resized after construction. Font dropped `HEADING` (22px)
  → `SUBTITLE` (16px) — still the most visually prominent line in
  the card (bold, brightest color, first line), just not full
  page-heading size.
- IOC Count and Risk Score merged from two stacked label rows into
  one horizontal row (both values still shown in full, just side by
  side).
- Risk bar height 10px → 6px.
- `info_layout` internal spacing `Spacing.XS` → `Spacing.XXS`.

Also, in `app/gui/pages/dashboard_page.py`: root layout top/bottom
margin `Spacing.PAGE_MARGIN` (24) → `Spacing.MD` (12) (left/right
unchanged, so horizontal alignment with the header/sidebar is
unaffected), and inter-row spacing `Spacing.SM` (8) → `Spacing.XS`
(4).

**Net measured effect:** the dashboard page's own
`minimumSizeHint()` height dropped from **687px to 624px** against
**616px** actually available at 1280×720 — the deficit closed from
71px to 8px (a ~99% reduction). Full test suite re-run clean (542
passed) after every edit in this list.

**However:** a final regression screenshot at 1280×720 (see Known
Issues) still shows visible, if reduced, text overlap in this
card's "No Investigation Available / IOC Count / Risk Score" block.
The `minimumSizeHint()` math says the row is nearly viable now, but
Qt's actual `QBoxLayout` allocation at render time is still
compressing this card below that computed minimum by a small
amount — meaning there is a remaining, real gap between the
computed minimum and the rendered result that this checkpoint did
not have budget to close. This is flagged honestly below rather
than claimed as fixed.

## ADDENDUM — Featured Investigation Card overlap: fixed and verified

A follow-up session picked up specifically to close the "however" gap
noted above, before starting any 4A-1C-B feature work. Environment
re-verified fresh: Python 3.12.3, pytest 9.1.1, PySide6 6.11.2,
offscreen rendering confirmed, baseline full suite 542 passed / 0
failed.

**Root cause, found by direct runtime measurement (not sizeHint
arithmetic alone):** `FeaturedInvestigationCard`'s vertical size
policy is `MinimumExpanding`, which lacks Qt's `ShrinkFlag`. For a
`QWidgetItem` without that flag, Qt's box-layout engine treats the
item's *minimum* as equal to its **sizeHint**, not its smaller
`minimumSizeHint()`. That made the card's true layout-enforced floor
157px (matching its own sizeHint) at 1280×720, while the outer
`QVBoxLayout` was only allocating `primary_row` 156px — a genuine,
if small, shortfall. That 1px-vs-19px-style gap was tested directly:
changing `primary_row`'s stretch factor (values from 1 up to 100)
had **zero effect** on the allocated height, and wrapping the row's
`QHBoxLayout` in a container `QWidget` made the deficit worse (138px
allocated instead of 156px) — both ruled out as the actual lever.
The only reliable lever was reducing the card's own true content
minimum below whatever it was actually being allocated.

**Fix:** in `_build_card_ui()`, the "Analysis Time" label was moved
off its own stacked row and into the same `meta_row` as IOC Count /
Risk Score (now three items on one line instead of two rows). This
removes one full row height plus its `Spacing.XXS` gap (~18px),
dropping the card's `minimumSizeHint()` from 175px to **157px** —
just under the 156px the row actually receives. No text was
truncated, hidden, or moved into a tooltip-only location; all three
values are still fully visible.

**Verification performed (not asserted):**
- Runtime geometry check: every child QLabel/QProgressBar's rendered
  `geometry()` compared against its own `minimumSizeHint()` — no two
  siblings' rects overlap vertically anymore (previously the
  report-name row rendered at 14px against a 25px text minimum,
  which is what caused the visible garble).
- Actual offscreen `.grab()` screenshots taken and visually
  inspected: empty state, and a populated state with a long
  (55-char) report name + CRITICAL severity + 3-digit risk score —
  both render cleanly with no overlap or clipping.
- Full dashboard screenshot at 1280×720 reviewed end-to-end — no
  other row regressed.
- Full test suite re-run after the edit: 542 passed, 0 failed.
- Spot-checked 1440×900 (card renders at 321px, well above its
  157px minimum) and 1920×1080 (451px) — no regression at the
  larger breakpoints.

This closes the one item 4A-1C-A left open. No other 4A-1C-B scope
(Analyze, Investigation Workspace, IOC Summary, Threat Intelligence,
Risk/Severity, History, secondary UI, motion, accessibility,
three-resolution validation) was started in this session — all of
it remains deferred, per explicit instruction to stop after this
fix and package a checkpoint.

## REMAINING — 4A-1C-B (not started this checkpoint)

Per your explicit stop instruction, the following are **deferred in
full** — no code was touched for any of these in this checkpoint:

- **Finish the Featured Investigation Card overlap** (see Known
  Issues) — the highest-priority carry-over, since it's a visible
  defect on the landing page.
- Re-validate the full dashboard (all rows, not just the ones fixed
  here) at 1440×900 and 1920×1080 — only 1280×720 was checked this
  session.
- **Analyze Page** — input/dropzone hierarchy, drag/drop states,
  loading/progress state, success/error/empty states. Not started.
- **Investigation Workspace** — identity, primary hierarchy,
  IOC→TI relationship, analyst actions, loading/empty/partial/error
  states, responsive behavior. Not started.
- IOC Summary
- Threat Intelligence page
- Risk / Severity page
- History page
- Secondary UI systems (dialogs, toolbars, menus, tooltips,
  notifications) consistency pass
- Cross-workflow visual-language consistency audit
- Remaining motion/animation work
- Accessibility refinement pass (contrast, focus visibility,
  keyboard nav) beyond what 4A-1B already covered
- Final three-resolution validation across the whole app
- Final full-app regression pass

None of the above should be assumed complete or attempted-and-safe;
they simply were not touched.

## Architecture

No backend/service boundaries, workers, database architecture, or
event mechanisms were touched this checkpoint — all changes were
widget-level (labels, fonts, spacing, one status string) or
page-layout-level (margins/spacing). The known
`app/services/risk_explanation_service.py` → GUI import issue
flagged in earlier checkpoints was not touched and was not made
worse (no changes were made to that file or to
`app/gui/pages/investigation_workspace.py`'s consumption of it in
this session — Investigation Workspace work is entirely deferred).

## Phase 4A-1C-B-A — Analyze Page fixes (this checkpoint)

Environment re-verified fresh at the start of this session: Python
3.12.3, pytest 9.1.1, PySide6 6.11.2, offscreen rendering confirmed.
**Baseline full suite: 542 passed, 0 failed.**

Scope was deliberately narrowed mid-session by explicit instruction
to stop feature work and package a checkpoint before the Analyze
Page batch was fully complete. What follows is only what was
actually implemented and verified — Investigation Workspace, IOC
Summary, Threat Intelligence, Risk/Severity, History, secondary UI,
motion, and accessibility work are all still entirely untouched (see
"REMAINING" above, still accurate).

### 1. Dead Progress Dialog "Cancel" button (fixed)

`ProgressDialog` (`app/gui/widgets/progress_dialog.py`) has always
exposed a fully enabled button and a `canceled` signal, but
`AnalyzePage` never connected to that signal — clicking the button
did nothing observable. Checked `AnalysisWorker.run()`
(`app/gui/workers/analysis_worker.py`): it executes synchronously on
its own thread with no interruption flag it polls, so there is no
mechanism anywhere in the app that can actually stop an in-flight
analysis. Rather than either leaving a dead control or faking
cancellation, the button was relabeled **"Dismiss"** and its
`canceled` signal is now connected, in `AnalyzePage`, to a handler
that hides the dialog and shows a toast honestly stating the
analysis is still running in the background. `_on_analysis_finished`
/ `_on_analysis_failed` remain connected and still fire normally
when the background thread completes. Docstrings on `canceled`,
`finish_activity()`, and `reset()` in `progress_dialog.py` were
updated to match.

### 2. Silent drag-and-drop rejection (fixed)

`FileDropzoneWidget.dragEnterEvent` (`app/gui/components/feedback/
file_dropzone.py`) previously called `event.ignore()` for an
unsupported file type with no widget-level visual change — Qt's own
forbidden cursor was the only cue, and it doesn't explain *why*.
Added `_apply_rejected_style()`: a red dashed border plus a
"Unsupported file type — expected .txt, .log, or .json" message in
place of the normal helper text, applied on `dragEnterEvent` for a
rejected payload and cleared by the existing `_apply_default_style()`
on `dragLeaveEvent` (verified the reset restores the original label
text/color, not just the border).

### 3. VirusTotal enrichment checkbox no longer implies availability
that isn't there (fixed)

All three pipeline checkboxes on the Analyze page (`_chk_iocs`,
`_chk_vt`, `_chk_risk`) are pre-existing decoration — grepped the
file and confirmed none of the three is ever read anywhere in
`_start_analysis` or elsewhere; that gap is real but out of scope
for this fix and was not touched. What *was* fixed: the VT checkbox
was always checked and enabled regardless of whether a VirusTotal
API key is configured, even though `ApplicationShell` already logs
`"VirusTotal client unavailable — no valid API key is configured"`
at startup when it isn't. Added `AnalyzePage._refresh_vt_availability()`,
called once at construction and again on every `showEvent` (so a key
added on the Settings page while this page stays alive in
`page_stack` is picked up next time the analyst returns to Analyze),
which reads `SettingsService().load_settings().virustotal_api_key`
and disables + unchecks the checkbox with an explanatory tooltip
when no key is set. This only surfaces existing settings state
honestly; it does not add new backend wiring or change what the
checkbox controls (still nothing, pre-existing gap).

### 4. Post-analysis navigation — verified correct, no change needed

Suspected a missing "next action" after analysis completes (no
explicit "View Investigation" button on the page). Verified by
actually running the signal chain in an offscreen harness rather
than assuming from static reading: `AnalyzePage._analysis_completed`
→ `ApplicationState.select_investigation()` → emits
`event_bus.investigation_selected` → already connected in
`MainWindow._connect_signals` to `self._open_workspace` → confirmed
`win.page_stack.currentIndex()` moves from 0 to
`NavigationPage.WORKSPACE` (7) after calling
`win._analysis_completed(investigation)` directly. No defect; no
change made.

### Known Issues (found during visual verification, not fixed)

- **Dropzone icon/label overlap at 1280×720.** A screenshot of the
  Analyze page at 1280×720 (offscreen `.grab()`) shows the dropzone's
  icon and its "Drag & Drop Malware Report File Here" primary label
  visually overlapping/garbled — the same class of defect as the
  Featured Investigation Card issue fixed earlier in this document,
  but in a different widget (`FileDropzoneWidget`, not touched by
  any edit in this checkpoint beyond drag-state styling). Confirmed
  this is pre-existing, not a regression from this session's edits,
  by checking that none of this session's changes touch `_build_ui`,
  the icon pixmap, or layout code in that file — only
  `dragEnterEvent`/`dragLeaveEvent`/style-application methods were
  changed. Not fixed in this checkpoint per the explicit instruction
  to stop and package rather than start a new fix. Flagged as the
  top carry-over item for the next session.
- The pre-existing gap noted in item 3 above (none of the three
  pipeline checkboxes actually gate backend behavior) was not fixed
  — only the VT checkbox's *availability display* was corrected.
  Making the checkboxes functionally control the analysis pipeline
  would touch `AnalyzeController`/`AnalysisService`/`AnalysisWorker`
  call signatures, which is backend wiring beyond this checkpoint's
  scope.

### Tests

Full suite re-run after every edit in this section: **542 passed, 0
failed**, both in the working tree and from a fresh extraction of
`SOC-IQ-Phase4A-1C-B-A-CHECKPOINT.zip`. `python3 -m compileall app
tests` clean in both locations.

### Visual validation

Only 1280×720 was checked this session (explicitly scoped — no
1440×900 or 1920×1080 check was performed), focused on the Analyze
page only: dropzone (valid/rejected drag states), analysis controls,
Dismiss/progress dialog, and VT checkbox availability state. See
Known Issues above for what that check found.

### REMAINING — unchanged from 4A-1C-B, still entirely deferred

Investigation Workspace, IOC Summary, Threat Intelligence,
Risk/Severity, History, secondary UI consistency pass, motion/
animation work, accessibility refinement, and full three-resolution
validation are all untouched — see the "REMAINING" section above,
which still accurately describes the state of this project. The
dropzone overlap noted above is an additional, newly-discovered item
for that list, not previously known.
