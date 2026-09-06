# SOC-IQ FRONTEND MAX-14 — FULL-PROJECT FORENSIC AUDIT

## 1. Audit Metadata

- Phase: MAX-14 Phase 1 (Forensic Audit — AUDIT ONLY)
- Date: 2026-09-05
- Scope: `frontend/` and directly relevant integration boundaries
- No source files were modified during this audit.

## 2. Authoritative ZIP

```text
Input ZIP: SOC-IQ-FRONTEND-MAX-13-FINAL-CLOSURE-FULL-PROJECT.zip
SHA-256: 691e9afbb2f661a97567d12c461ac3345d1a9fb5bf502310f81648f925ef4d93
Entry count: 830
Archive integrity: OK (unzip -l / -q extraction clean, no CRC errors)
Fresh extraction: performed to a clean directory
Project structure: complete (app/, database/, docs/, frontend/, keystore-core/,
  packaging/, samples/, sidecar-core/, src-tauri/, tests/)
MAX-13 closure documentation: present
  - docs/audits/SOC-IQ-FRONTEND-MAX-13-FORENSIC-AUDIT.md
  - docs/audits/SOC-IQ-FRONTEND-MAX-13-PHASE-2B-CLOSURE.md
```

## 3. MAX-13 Closure Verification

MAX-13's selected direction was **MAX13-F-01 — Error Boundary Recovery**: the
foundation-level `ErrorBoundary` previously left the fallback UI permanent for
the rest of the session; the closure added a "Try again" action that clears
the caught error and lets React re-attempt rendering the subtree.

Independent verification performed (not taken on the closure document's word):

- Read `frontend/src/app/providers/ErrorBoundary.tsx` directly. The
  `handleReset` method clears `state.error`, and the render path returns
  `this.props.children` once `state.error` is `null`, matching the claimed
  behavior. No retry counters/backoff were added, matching the documented
  intentional scope limit.
- Read `frontend/src/app/providers/ErrorBoundary.live.test.tsx`. It uses real
  `createRoot`/`act` DOM rendering (not `renderToStaticMarkup`) and proves:
  catch → fallback with `role="alert"`, `componentDidCatch` logging, a real
  enabled `<button>` recovery action, successful recovery when the underlying
  cause is gone, and re-catching when it is not.
- Ran the full frontend suite fresh: `npx vitest run` → **85 test files,
  1214 tests, all passing**, including the above.
- Ran `npx tsc --noEmit` → clean, no errors.

**MAX-13 closure is independently corroborated.** No regression found.

## 4. Methodology

- Fresh extraction and hash of the authoritative ZIP.
- Direct source reading of the frontend tree (`frontend/src/**`), not just
  audit-document review.
- Full test suite and TypeScript project execution rather than relying on
  prior audits' reported results.
- Cross-referenced current source state against every MAX-1…MAX-13 audit and
  closure document's open/deferred items to determine current status.
- Targeted inspection of the specific areas the governing brief calls out by
  name (MAX-10 export/filesystem security, MAX-12 ThemeControl honesty,
  MAX-13 ErrorBoundary, MAX9-F-01, High Contrast Dark, DataTable
  virtualization) plus a scan of adjacent lifecycle code (SSE/sidecar hooks)
  for anything not previously covered.

## 5. Architecture Findings

No new architecture findings. Composition root (`App.tsx`), routing,
provider nesting (`ErrorBoundary` → `ThemeProvider` → `Router`), and the
sidecar/event-projection layer (`shared/sidecar/*`, `shared/events/*`) match
what MAX-8 through MAX-13 already documented: ref-counted SSE subscription
manager, cleanup-on-unmount, handler read through a ref to avoid stale
closures. No duplicated responsibility or new coupling observed.

## 6. UX Findings

One new, narrow finding — see MAX14-F-01 below. No other UX friction beyond
what MAX-1 through MAX-13 already found and either fixed or explicitly
deferred (Analyze/Settings mock-labeling honesty, ThemeControl "no live
re-skin" disclosure, IOC/Threat Intel navigation retirement).

## 7. Accessibility Findings

**MAX14-F-01 (new this phase).** See §16/§18 for the full write-up. Summary:
the app-level `ErrorBoundary` fallback (`role="alert"`) and its "Try again"
recovery button manage no keyboard focus at all — not on catching an error,
and not on successful recovery. This is a real gap distinct from what
MAX13-F-01 fixed (which was the recovery *mechanism*, not focus handling
around it), and inconsistent with an established project convention:
`InvestigationWorkspacePage.tsx`'s tab switching and
`CommandPaletteContainer`/`CommandPalette.tsx` both call `.focus()`
explicitly on state transitions that change what's visible. `ErrorBoundary`
is the one state-changing UI surface in the codebase with zero focus
management.

No other new accessibility findings. Tables (`DataTable.tsx`) still use a
real `<button>` for sortable headers with `aria-sort`, `scope="col"`, and a
`<caption>`; keyboard row activation (`Enter`/`Space`) is implemented and
`event.preventDefault()`'d correctly for Space. Command palette and dialog
patterns are unchanged from MAX-12/MAX-13's verified state.

## 8. Responsive Findings

No new findings at 1280×720 / 1366×768 / 1440×900. `DataTable`'s
horizontal-scroll-scoped-to-the-component pattern (from MAX-3) is unchanged
and still the only responsive accommodation needed in the areas inspected.

## 9. Performance Findings

`DataTable` still has no virtualization (carried forward from MAX-8's
`MAX8-F-01`, repeatedly deferred through MAX-9 – MAX-13). No evidence of
actual investigation/report/IOC row counts in this codebase or its fixtures
that would make this a demonstrated (rather than speculative) user-facing
problem — the deferral calculus is unchanged. Not promoted; see §15.

## 10. Reliability Findings

MAX-13's `ErrorBoundary` recovery is intact and not regressed (§3). No new
reliability findings beyond MAX14-F-01, which is an accessibility/UX gap
adjacent to reliability but not a functional recovery defect — the recovery
itself works; only the focus experience around it is missing.

## 11. Security Findings

No new frontend security findings. Spot-checked that MAX-10's export/
filesystem remediation is present and unchanged (no diffs found against the
security docs' described behavior in `shared/api`/settings export-path
code touched by that closure). No source changes were made to verify this
further, per this phase's audit-only boundary.

## 12. Testing Findings

`ErrorBoundary.live.test.tsx` exercises catch, fallback semantics, logging,
and both recovery outcomes at the narrowest correct level (isolated
component + real DOM), consistent with the repository's established
integration-testing convention — no co-located test-per-token demanded. No
test currently asserts anything about focus, which is consistent with
MAX14-F-01 being a genuine, previously-unexamined gap rather than an
untested-but-known behavior.

## 13. Historical Finding Reconciliation

| Finding | Status this phase | Basis |
|---|---|---|
| MAX-10 export/filesystem security remediation | **FIXED, unchanged** | Spot-checked against `docs/security/*`; no contradicting evidence found |
| MAX-12 ThemeControl honesty fix | **FIXED, unchanged** | Read `ThemeControl.tsx` directly: always-visible disclosure note and unsupported-value handling both present exactly as MAX-12 describes |
| MAX-13 ErrorBoundary recovery | **FIXED, unchanged, independently reverified** | §3 |
| `MAX9-F-01` (stale `package.json` description) | **STILL OPEN, no new evidence** | `package.json`'s description still says "Analyze, Risk, and Settings remain mock/placeholder," but `AnalyzePage.tsx` has zero mock imports and is wired to a real hook, and "Risk" has no top-level nav entry — the exact same mismatch MAX-9 first found. Text is byte-for-byte the pattern carried through MAX-9 – MAX-13. Not promoted (P3, no new evidence, explicitly out-of-cycle-scope policy in every prior phase). |
| High Contrast Dark (real theme) | **STILL OPEN, no new evidence** | `ThemeControl.tsx` confirms no live re-skin architecture exists yet; MAX-12's honesty disclosure is the only mitigation. Same "legitimate but materially larger than one cycle" status as MAX-13 recorded. Not promoted. |
| DataTable virtualization | **STILL OPEN, no new evidence** | No virtualization in `DataTable.tsx`; no evidence of row counts that make this a demonstrated (not speculative) problem. Not promoted. |

No previously-fixed finding was found regressed. No finding was invalidated.

## 14. Severity/Confidence Matrix

| Finding | Severity | Confidence | Affected surface |
|---|---|---|---|
| MAX14-F-01 — ErrorBoundary fallback/recovery has no focus management | P2 | High | `frontend/src/app/providers/ErrorBoundary.tsx` (app-wide) |

## 15. Candidate Ranking

1. **MAX14-F-01 — ErrorBoundary focus management** (selected). Material
   impact: this boundary sits at the root of the app (`App.tsx` wraps
   everything in it), so any caught error unmounts the entire visible
   application for a keyboard user with no focus signal of where they've
   landed. Evidence-backed, current, distinct from MAX-13 (mechanism vs.
   focus), consistent with an existing project convention violated here,
   bounded (one file, additive), low regression risk.
2. `MAX9-F-01` stale description — real but no new evidence, P3, explicitly
   out of scope by five consecutive phases' own policy. Not selected.
3. DataTable virtualization — real but speculative without demonstrated row
   counts; larger blast radius (shared primitive). Not selected.
4. High Contrast Dark real theme — real but explicitly larger than one MAX
   cycle per MAX-12/MAX-13's own assessment, unchanged. Not selected.

MAX14-F-01 outranks all carried-forward candidates on evidence strength,
current relevance, and bounded scope, despite being visually the least
noticeable of the four.

## 16. Selected MAX-14 Direction

### Selected Direction

Add keyboard focus management to the app-level `ErrorBoundary`'s fallback UI
and its recovery action, so a keyboard user is never silently left with
focus on nothing after an error is caught or cleared.

### Why It Wins

It is the only candidate with fresh, direct evidence (no `.focus()` calls
anywhere in `ErrorBoundary.tsx` or its test, against an established
project-wide convention of managing focus on view-replacing state changes),
it sits at the highest-leverage point in the tree (every analyst workflow is
behind this boundary), and it is small and additive — unlike the other three
carried-forward candidates, which are either explicitly out-of-cycle-scope
by prior phases' own policy or lack demonstrated (as opposed to speculative)
impact.

### Expected Product Improvement

When any part of the app throws and this boundary catches it, a keyboard-
only analyst currently has no indication of where their focus went — they
must tab from the top of an otherwise-empty page to find "Try again."
Moving focus to the fallback (and, on recovery, restoring/moving focus into
the recovered content) closes that gap without changing what the boundary
catches or how recovery itself works.

### Affected Surface

- `frontend/src/app/providers/ErrorBoundary.tsx` (add focus management)
- `frontend/src/app/providers/ErrorBoundary.live.test.tsx` (add focus
  assertions to the existing catch/recovery test suites)

No other file is expected to require changes.

### Implementation Boundary

Phase 2A may modify `ErrorBoundary.tsx` and its existing test file only, to
add focus management (e.g. a ref to the fallback heading or the "Try again"
button, focused on catch; focus handling on reset). It may follow the exact
`.focus()` convention already used in `InvestigationWorkspacePage.tsx` /
`CommandPalette.tsx`.

### Non-Goals

- Do not add retry counters, backoff, or any other recovery-mechanism
  changes — MAX13-F-01's recovery behavior is frozen and must not be
  re-raised or altered.
- Do not touch `package.json`'s stale description (`MAX9-F-01`) — carried
  forward, unrelated, still P3.
- Do not implement a real "High Contrast Dark" theme or touch
  `ThemeControl.tsx`/`ThemeProvider.tsx`.
- Do not add `DataTable` virtualization or otherwise touch `DataTable.tsx`.
- Do not touch security, export, Tauri, or Rust code — nothing in this
  direction requires it.
- Do not add new dependencies. Native DOM `.focus()` is sufficient, as it is
  everywhere else in this codebase.

### Rejected Alternatives

- **`MAX9-F-01` package.json description fix** — trivial and real, but P3
  with zero new evidence and explicitly deferred by five straight phases'
  own scope policy; fixing it here would be scope-creep relative to this
  phase's own selection criteria, not a defect in the candidate itself.
- **DataTable virtualization** — legitimate future work, but promoting it
  now would be speculative optimization without a demonstrated row-count
  problem, which §5/§9 of the governing brief explicitly disallows.
- **Real High Contrast Dark theme** — legitimate, but MAX-12 and MAX-13 both
  already assessed it as materially larger than a single MAX cycle
  (new theming architecture, not a single-component change); no new
  evidence this phase changes that assessment.

## 17. Verification Requirements for Phase 2A

- Focused tests: extend `ErrorBoundary.live.test.tsx` to assert focus lands
  on the fallback (or its recovery button) on catch, and is sensibly placed
  after recovery.
- Full test suite: `npx vitest run` must remain fully green (currently 85
  files / 1214 tests).
- `npx tsc --noEmit` must remain clean.
- Production build: `npm run build` should be run to confirm no build
  regression.
- No accessibility regression: confirm `role="alert"` and the existing
  `aria`/semantic structure of the fallback are unchanged aside from the
  added focus behavior.
- No responsive check needed (no layout change).
- No backend/Tauri/Rust verification needed — this direction does not touch
  that boundary.
- Final diff/scope audit: confirm only `ErrorBoundary.tsx` and its test file
  changed.
- Complete full-project ZIP verification per the standard MAX workflow.

## 18. Full Finding Register

```text
Finding ID: MAX14-F-01
Severity: P2
Confidence: High
Affected surface: frontend/src/app/providers/ErrorBoundary.tsx (app-wide —
  wraps the entire application in App.tsx)
Exact file(s): frontend/src/app/providers/ErrorBoundary.tsx,
  frontend/src/app/providers/ErrorBoundary.live.test.tsx
Exact evidence: No `.focus()` call, ref, or other focus-management logic
  exists anywhere in ErrorBoundary.tsx. Its own test file
  (ErrorBoundary.live.test.tsx) asserts DOM content and button
  enabled-state but never asserts document.activeElement. By contrast,
  frontend/src/pages/investigation/InvestigationWorkspacePage.tsx
  (selectAndFocusTab) and frontend/src/app/commandPalette/CommandPalette.tsx
  both explicitly call .focus() on view-changing state transitions,
  establishing this as the codebase's convention for exactly this class
  of UI change.
User/product impact: This is the app's outermost error boundary
  (App.tsx wraps <ErrorBoundary> around <ThemeProvider><Router>...</Router>
  </ThemeProvider>), so any uncaught render error anywhere in the app
  unmounts the entire visible UI in favor of the fallback. A keyboard-only
  analyst's focus reverts to <body> with no signal of where to go; they
  must tab from the document start to reach "Try again." The same gap
  recurs on recovery: nothing moves focus into the re-rendered children.
Why it matters now: MAX13-F-01 fixed the recovery *mechanism* but its own
  scope note says it is "the foundation only," not full recovery UX —
  focus handling was never in scope for that finding and has not been
  addressed since.
Why previous MAX phases did not already resolve it: MAX-13 (the only prior
  phase to touch this file) was scoped specifically to making "Try again"
  functionally clear the error state; no prior MAX phase's accessibility
  audit examined ErrorBoundary's focus behavior specifically, and this is
  the first phase to compare it against the project's own established
  .focus()-on-transition convention.
Actionability: Small, additive, single-file change following an existing
  in-repo pattern.
Scope/risk: Low. No change to catch/recovery logic, no new dependencies,
  no architecture change.
```

## 19. Final Verdict

```text
PASS — VALID MAX-14 DIRECTION SELECTED
```

MAX-14 Phase 1 (forensic audit) is complete. No source implementation was
performed. The next authorized operation is MAX-14 Phase 2A, scoped exactly
as defined in §16.
