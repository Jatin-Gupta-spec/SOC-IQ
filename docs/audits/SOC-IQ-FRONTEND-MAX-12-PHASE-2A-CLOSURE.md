# SOC-IQ Frontend MAX-12 Phase 2A — Implementation Closure

## 1. Baseline

Working tree corresponds to `SOC-IQ-FRONTEND-MAX-12-FORENSIC-AUDIT-CHECKPOINT-FULL.zip`
(SHA-256 `d3dba3d463311f0bcab5f1c3d2aad29bcdae405cd4c1ef60700298ae2143a2be`,
825 entries), the exact checkpoint delivered at the end of the MAX-12
audit-only phase. No new ZIP was uploaded for this phase; per the task
brief's own instruction to report rather than silently substitute a
baseline, this is stated explicitly. This phase's own audit
(`docs/audits/SOC-IQ-FRONTEND-MAX-12-FORENSIC-AUDIT.md`) was read in full
before any edit was made.

## 2. Selected Direction (Restated)

**MAX12-F-01**: make the Settings "Theme" control honestly disclose, in the
rendered UI itself, that a selected/persisted theme value is saved but not
applied to the running interface — closing the gap between what the
component's own source comment already admitted and what an analyst using
the actual app could see. No other MAX-12 audit finding was implemented;
no rejected alternative (Reports sort — already invalidated as a real gap;
`package.json` description) was touched.

## 3. Root Cause Addressed

Before: `ThemeControl.tsx`'s doc comment stated the limitation ("this
control only ever claims to persist the chosen value, never to apply it
live") but the rendered component never told the analyst this. An analyst
selecting "High Contrast Dark" and saving it saw only "Theme saved." — a
plain success message indistinguishable from a save that actually changed
anything.

After: the component now always renders a `role="note"` disclosure — the
same convention `VirustotalControl`'s own restart-required note already
established in this exact Settings page — stating plainly that the
selection is saved but not yet applied, regardless of which value is
selected, persisted, dirty, or just-saved. This is not a symptom patch (an
error message that appears only in one state); it addresses the actual
root cause (the UI's `Success ≠ Applied` gap existed in every state the
control can be in, including on initial page load before any interaction),
so the disclosure is unconditional rather than conditioned on any one
`saveStatus`.

## 4. Scope

**Directly required, implemented:**
- `frontend/src/pages/settings/ThemeControl.tsx`: added an always-visible
  `<p className="settings-page__field-note" role="note">` disclosure,
  reusing the exact CSS class and ARIA role already in the same file for
  the pre-existing unsupported-persisted-value note. Updated the
  component's doc comment to record MAX12-F-01 and explain why the note is
  unconditional rather than state-gated. Zero new CSS, zero new component,
  zero new dependency.
- `frontend/src/pages/settings/ThemeControl.live.test.tsx`: added a new
  `describe("MAX12-F-01: not-yet-applied disclosure", …)` block (5 tests)
  proving the disclosure is present for both supported theme values, for
  an unsupported/legacy persisted value (alongside the pre-existing note,
  not replacing it), before and after a save, and that it renders with
  `role="note"` rather than as a status/alert.

**Explicitly out of scope (per the MAX-12 audit's own non-goals, §19):**
- No actual working "High Contrast Dark" theme was implemented — no new
  design-token set, no `ThemeProvider` change, no CSS beyond the one reused
  class.
- No change to `VirustotalControl.tsx`, `ExportDirectoryControl.tsx`, or
  any other Settings control.
- No change to `save_settings`'s contract, `useSettingsFieldSave`, or
  `THEME_OPTIONS`.
- Reports `DataTable` untouched (confirmed not a real gap, MAX-12 audit §16).
- `MAX9-F-01` (`package.json` description) untouched.
- No backend, no `src-tauri/`, no capability manifest change.

## 5. Files Changed

Diff-audited via `find … -newer docs/audits/SOC-IQ-FRONTEND-MAX-12-FORENSIC-AUDIT.md`
against the full working tree (`frontend/`, `app/`, `src-tauri/`,
`database/`, `keystore-core/`, `sidecar-core/`, `packaging/`, `tests/`).
**Exactly 2 files differ**, both under `frontend/src/pages/settings/`:

- **Modified:** `ThemeControl.tsx`
- **Modified:** `ThemeControl.live.test.tsx`

Nothing else changed anywhere in the project.

## 6. Functional Changes

`ThemeControl` now tells the analyst, every time it renders, that the
Theme selection is saved but not applied to the interface. This is true on
initial load (before any interaction), while a different value is selected
but not yet saved, and after a successful or failed save — the disclosure
is orthogonal to `saveStatus`/`dirty`, since the underlying limitation it
describes is unrelated to either. No other functional behavior of the
control changed: the same two options, same `save_settings` call shape,
same unsupported-value handling, same save/error/retry flow.

## 7. UX Changes

The Settings "Appearance" card no longer implies, by omission, that
choosing "High Contrast Dark" changes anything. An analyst who wants real
higher contrast now learns, in the product itself rather than only in
source code, that this option currently does not deliver that — matching
the same honesty standard `VirustotalControl`'s restart-required note
already sets in the same page, rather than papering over the gap.

## 8. Accessibility

- `role="note"` matches the exact convention already used for the
  sibling unsupported-value note in this same component — no new ARIA
  pattern introduced.
- The note is a plain `<p>`, not `aria-live`, since it is not tied to any
  transient state change (unlike the `role="status"`/`aria-live="polite"`
  success message, which remains untouched) — it is static, always-present
  content, and does not need to interrupt or be announced on every render.
- No change to keyboard operation, tab order, or focus — no new
  interactive element was added, only static text.
- `STATIC VERIFIED` (source-level + jsdom-DOM-level via the new tests) —
  `ENVIRONMENT-BLOCKED` for real screen-reader verification, unchanged
  standing condition (no browser automation in this sandbox).

## 9. Responsive

The new note reuses the pre-existing `.settings-page__field-note` rule,
which already renders correctly at every previously-verified breakpoint
for the sibling unsupported-value note and `VirustotalControl`'s own note
— no new CSS, no new layout risk. `STATIC VERIFIED` only, same standing
condition as every prior phase.

## 10. Performance

No new state, effect, subscription, or computation. The note is static
JSX rendered unconditionally alongside content that already renders every
time — zero additional render cost beyond the DOM node itself.

## 11. Security

No filesystem, export, credential, or trust-boundary code was touched.
`save_settings`'s contract, `useSettingsFieldSave`, and the capability
manifest are all unmodified (confirmed in the diff audit, §5).

## 12. Testing

Exact commands and results, all run fresh in this session:

```
npx tsc --noEmit
  → 0 errors

npx vitest run src/pages/settings/ThemeControl.live.test.tsx
  → 1 test file, 14 tests passed (9 pre-existing + 5 new)

npm test -- --run  (full suite)
  → Test Files  84 passed (84)   [MAX-12 audit baseline: 84]
  → Tests       1208 passed (1208)   [MAX-12 audit baseline: 1203]
  → 0 failures, 0 unhandled errors
  → net new: 5 tests, 0 new test files (added to the existing
    ThemeControl.live.test.tsx rather than a new file, since no new
    mocking setup was required, unlike MAX-11's Tauri-mocked addition)

npx vitest run src/pages/settings/   (targeted settings-surface re-run)
  → 8 test files, 70 tests, all passed — confirms no regression in any
    sibling Settings control (VirustotalControl, ExportDirectoryControl,
    useSettings, useSettingsFieldSave)

npm run build
  → tsc --noEmit clean, vite build succeeded
  → 202 modules transformed   [unchanged from MAX-12 audit baseline —
    ThemeControl.tsx is a modified file, not a new module]
  → dist/ produced, no build errors or warnings beyond the pre-existing
    baseline output shape (SettingsPage's own JS chunk grew from
    10.84 kB to 11.06 kB gzip, consistent with the added static text)
```

No test was removed, weakened, or skipped. All 9 pre-existing
`ThemeControl.live.test.tsx` tests pass completely unmodified, proving the
existing save/dirty/error/retry/unsupported-value behavior is unaffected.

## 13. Behavioral Verification

- **Primary workflow:** confirmed — the disclosure is present in every
  state the control can be in (initial load with a supported value,
  initial load with an unsupported value, dirty-but-unsaved, saving,
  post-success, post-error), verified by the 5 new tests plus manual
  re-reading of the component's render output for each branch.
- **States:** loading (N/A — this control receives `persistedTheme` as a
  prop, no independent loading state of its own), success, error, recovery
  all re-verified passing; no empty state applicable (the field always has
  a value or the "Choose a theme…" placeholder, unchanged).
- **Accessibility:** `role="note"` semantics preserved/extended, no
  keyboard/focus change (§8).
- **Responsive:** no new CSS, existing rule reused (§9).
- **Regression:** full 1208-test suite passes; targeted 70-test
  Settings-surface re-run passes; build is clean.

## 14. Complete Diff Audit

- Exactly 2 files changed, both within the declared implementation
  boundary (§5).
- No unrelated file changed, no accidental deletion, no dependency change
  (`package.json`/lockfile untouched — confirmed by their absence from the
  changed-file list), no broken import (`tsc --noEmit` clean), no dead
  code introduced, no unnecessary abstraction (the change is two JSX
  lines plus a doc-comment update), no unrelated styling change (zero CSS
  files touched), no accessibility regression (§8), no security regression
  (§11).
- Every changed file is directly justified: the component implementing
  the fix, and its test file proving it.

## 15. Environment Limitations

- No Rust/Tauri toolchain in this sandbox — unaffected by this phase
  regardless, since no Tauri-side file was touched.
- No browser/screen-reader runtime automation — accessibility/responsive
  claims in §8–§9 remain source/jsdom-level, unchanged standing condition
  from every prior MAX phase.

## 16. Phase 2A Verdict

```
MAX-12 PHASE 2A — PASS, READY FOR PHASE 2B
```

This is implementation, not final closure. Per the task brief's explicit
instruction, MAX-12 is **not** being declared CLOSED in this document — a
future phase must independently re-audit the produced full-project ZIP
before any closure verdict is issued.
