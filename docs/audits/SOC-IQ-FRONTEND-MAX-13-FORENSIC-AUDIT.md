# SOC-IQ Frontend MAX-13 — Forensic Audit (Audit Only)

## 1. Audit Metadata

- Phase: MAX-13, audit-only. No implementation performed.
- Authoritative input: `SOC-IQ-FRONTEND-MAX-12-FINAL-CLOSURE-FULL-PROJECT.zip`,
  SHA-256 `a9685930f7e675cf1db2eec01fc590b0e82500cc0cdf84b30896094a91075532`,
  827 entries, delivered at the end of the MAX-12 Phase 2B closure phase in
  this same session.

## 2. Authoritative Full-Project ZIP

Same archive as above — re-verified this phase, not assumed from the prior
turn (§3).

## 3. ZIP Integrity

- `unzip -t`: clean, no errors, re-run fresh this phase.
- Independently re-extracted to a fresh directory (not reused from the
  Phase 2B working tree) before any inspection.
- No `node_modules/` or `frontend/dist/` present in the archive itself
  (correctly excluded — build artifacts, not source).

**Baseline integrity: VALID.**

## 4. Project Structure

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

Frontend (`frontend/src/`): `app/` (router, navigation, shell, command
palette, providers), `mock/`, `pages/` (page shells + one folder per
feature), `shared/` (api, commands, events/SSE, hooks, notifications,
sidecar status), `styles/`. 127 non-test `.ts`/`.tsx` files, 84 test
files, 1208 tests.

## 5. MAX-12 Baseline Verification

- `docs/audits/SOC-IQ-FRONTEND-MAX-12-FORENSIC-AUDIT.md`,
  `docs/audits/SOC-IQ-FRONTEND-MAX-12-PHASE-2A-CLOSURE.md`, and
  `docs/audits/SOC-IQ-FRONTEND-MAX-12-CLOSURE.md` are all present.
- `docs/audits/SOC-IQ-FRONTEND-MAX-12-CLOSURE.md` §15 states a final
  verdict of `MAX-12 CLOSED`.

## 6. MAX-12 Closure Verification

Re-checked against the current source, not taken on the closure
document's word:

- `frontend/src/pages/settings/ThemeControl.tsx` was re-read: the
  unconditional `role="note"` disclosure described in the closure
  document is present, unchanged, and matches the described behavior.
- `npx tsc --noEmit` → 0 errors (re-run fresh this phase).
- `npx vitest run` → 84 test files, 1208 tests, 0 failures (re-run fresh
  this phase — matches the closure document's own figures exactly).
- `npm run build` → 202 modules, clean build, `SettingsPage` chunk still
  11.06 kB gzip (matches).
- `src-tauri/capabilities/default.json` and `app/` (Python backend):
  no discrepancy found between the closure document's "untouched" claim
  and the current tree.

**No discrepancy found between the MAX-12 closure document's claims and
the current ZIP.** MAX-12's closure is corroborated, not merely trusted.

## 7. Scope

Full-project-aware, frontend-first — consistent with every prior MAX
audit in this series. Backend (`app/`) and Rust (`src-tauri/`,
`keystore-core/`, `sidecar-core/`) were inspected only where they bear
directly on frontend correctness (composition-root/error-handling
boundary, capability manifest). No exhaustive backend/Rust audit was
performed; no Rust/Tauri toolchain is available in this sandbox (§25).

## 8. Methodology

- Swept `frontend/src` for `TODO`/`FIXME`/`XXX`/`HACK` markers (none) and
  stray `console.log`/`console.debug` calls (none; the two `console.*`
  hits found are an intentional, commented, ESLint-suppressed
  `console.warn`/`console.error` in `eventSourceManager.ts` and
  `ErrorBoundary.tsx` respectively — both are the established
  diagnostics convention, not leftovers).
- Enumerated every `.ts`/`.tsx` file without a co-located test file and
  cross-checked each against the project's established
  integration-test convention (page-level tests covering feature
  subcomponents) — the large majority are type-only files, token
  definitions, or components already covered by their page's
  integration suite, consistent with prior MAX audits' findings on this
  convention. Two files stood out as not fitting that pattern:
  `app/providers/ErrorBoundary.tsx` and `shared/events/eventSourceManager.ts`
  (the latter is exercised only indirectly through consumers, per the
  MAX-12 audit's own prior read of it — no new finding there this phase).
- Read `App.tsx` (composition root) in full and traced exactly where
  `ErrorBoundary` is mounted in the component tree.
- Read `ErrorBoundary.tsx` in full (catch, fallback render, recovery
  path).
- Read `App.test.tsx` in full to determine what the app's own test suite
  actually proves about the error boundary's behavior.
- Read `router.tsx` to confirm route structure (one boundary for the
  whole app vs. per-route).
- Grepped the full `docs/audits/*.md` history for
  `ErrorBoundary`/"error boundary" to check whether this is a
  previously-raised, previously-rejected, or previously-fixed finding
  (§17).
- Spot-checked `pages/components/DataTable.tsx` for virtualization/
  windowing as a candidate performance finding (§13).
- Re-ran the full automated verification suite (§6) to corroborate
  MAX-12's closure rather than trusting it.
- Did not re-walk areas with no plausible drift since their last
  dedicated pass (Analyze's core execution path, most of Investigation
  Workspace's tab internals, Reports export flow) absent a specific
  reason to suspect regression — consistent with this series'
  established method.

## 9. Architecture Findings

No architectural regression since MAX-12. Structure unchanged: one
router, one typed command client, one SSE connection manager, one
sidecar-status model, one composition root. **New finding this phase:**
the composition root's error-handling boundary is architecturally a
single point of failure for the entire application — see MAX13-F-01
(§10, §16).

## 10. UX Findings

**MAX13-F-01 (High).** See §16 for full evidence. Summary: `App.tsx`
mounts exactly one `ErrorBoundary`, at the outermost level, wrapping
`ThemeProvider` → `HashRouter` → `AppShell` → `AppRoutes`. Its fallback
UI (`role="alert"`, "Something went wrong") has no retry, reset, or
navigation-away affordance — once any single render-time error occurs
anywhere in the entire application (any page, any workflow, any
component), the fallback is permanent for the life of that app session,
and the analyst's only recovery is a full application restart, losing
all in-progress investigation/analysis/report state.

No other new UX finding this phase. Dashboard, Investigations, Reports,
Investigation Workspace, Analyze, and Settings all match or exceed their
previously-documented state.

## 11. Accessibility Findings

No new accessibility finding. `ErrorBoundary`'s fallback correctly uses
`role="alert"`, which is itself accessible — the finding in §10 is a
reliability/recovery gap, not an accessibility defect in the fallback
markup itself.

## 12. Responsive Findings

No new finding. No layout/viewport regression found in the surfaces
re-walked this phase.

## 13. Performance Findings

`DataTable.tsx` (220 lines, shared by Reports/Investigations/Dashboard
consumers) renders its full row set with no virtualization/windowing.
Considered as a candidate finding but **not selected** — the project's
actual data volumes (investigation lists, IOC tables) are not evidenced
in this ZIP to reach a scale where this matters, and no user-facing
symptom (jank, dropped frames) is demonstrable from source alone. Kept
as a documented, low-confidence future candidate rather than promoted
(§20).

No other performance regression or new finding.

## 14. Reliability Findings

MAX13-F-01 (§10) is fundamentally a reliability finding: a single
unhandled render error anywhere in the tree is unrecoverable without a
full process restart. This is the highest-leverage finding this phase
— see §16 for full reliability analysis.

## 15. Security Findings

No new finding. `src-tauri/capabilities/default.json` unchanged since
MAX-12. No filesystem/export/path-handling code was touched since
MAX-12 (confirmed §6). MAX-10's export/filesystem security remediation
remains intact — not re-derived from scratch this phase, but no
evidence of drift was found in the surfaces re-walked.

## 16. Testing Findings

`App.test.tsx` contains 5 tests, all of which assert the composition
root renders correctly on a happy path (shell regions present, one
`<main>` landmark, routed page present, sidebar present). **None of the
5 tests throws an error inside the tree and asserts the `ErrorBoundary`
actually catches it, renders its fallback, or — critically — that any
recovery path exists.** The catch/fallback behavior of the single
application-wide error boundary is therefore both architecturally risky
(§10) and currently untested.

Grepped `docs/audits/*.md` (MAX-1 through MAX-12) for
`ErrorBoundary`/"error boundary": two mentions found.
- MAX-8's Production Readiness audit (§12, Desktop Shell Audit)
  described the composition root's mount order (`ErrorBoundary` →
  `ThemeProvider` → `HashRouter` → `AppShell` → `AppRoutes`) and issued
  `PASS — NO MATERIAL FINDING`, but only evaluated it for
  startup-sequence/loading-flash concerns, never for catch/recovery
  behavior.
- MAX-7's Analyst UX closure document noted, in passing, that "no
  changes made in this phase to error boundaries" — a scope statement,
  not an evaluation of the boundary's own adequacy.

Neither prior mention analyzed the actual failure mode this audit
identifies. **MAX13-F-01 is genuinely new — not previously raised,
evaluated, or rejected in any MAX-1 through MAX-12 audit.**

## 17. Historical Finding Reconciliation

| Prior finding | MAX-12 status | Current status this phase |
|---|---|---|
| MAX12-F-01 (Theme control honesty) | FIXED (MAX-12 Phase 2A) | Re-confirmed fixed (§6) — not re-raised |
| Reports `DataTable` column sort | Invalidated (MAX-12 audit §16 — already implemented) | Re-confirmed not a gap; not re-raised |
| `MAX9-F-01` (`package.json` stale description) | Carried forward, still open, P3, deliberately deferred | Still present, still P3, still not cycle-worthy on its own — carried forward again, not promoted |
| Real "High Contrast Dark" theme | Explicit MAX-12 non-goal | Still not implemented — remains a legitimate but larger future candidate, not selected this phase (materially larger/riskier than MAX13-F-01) |

No regression was found in any previously-fixed area.

## 18. Severity Matrix

| ID | Severity | Confidence | Area | Status |
|---|---|---|---|---|
| MAX13-F-01 | **High** | High | Composition root / reliability, all workflows | **New — selected for MAX-13** |
| DataTable virtualization | — | Low (no demonstrated data-volume symptom) | Reports/Investigations/Dashboard | Documented, not selected |
| `MAX9-F-01` | P3 | High | `package.json` metadata | Carried forward, still open, not selected |
| — | — | — | Architecture (other than §9), accessibility, responsive, security, most of UX | No new finding this cycle |

No Critical finding exists. No other new Medium/Low finding beyond the
items above.

## 19. Candidate Ranking

1. **MAX13-F-01 — Error boundary recovery.** Real (directly observed in
   `App.tsx`/`ErrorBoundary.tsx`, confirmed untested in `App.test.tsx`),
   material (100% of workflows share the one boundary; the failure mode
   is total, not partial), distinct (never previously raised — §16–17),
   current (present in this exact MAX-12 checkpoint), actionable
   (bounded: add a reset affordance to the existing fallback, scoped to
   the existing `ErrorBoundary` component — does not require touching
   any page), high leverage (protects every workflow at once from one
   change, rather than one workflow at a time).
2. **DataTable virtualization.** Real as a structural observation, but
   fails materiality without evidence of actual data volumes that would
   cause a symptom — speculative at this evidence level, so it is
   documented rather than ranked as a live candidate.
3. **`package.json` description fix.** Real but trivial, zero runtime
   effect, not MAX-cycle-worthy on its own — unchanged conclusion from
   MAX-9 through MAX-12's own ranking of the same item.

## 20. Selected MAX-13 Direction

### Selected Direction

Give the application's single top-level `ErrorBoundary` a way for the
analyst to recover from a caught render error — a reset action on its
existing fallback UI — instead of leaving the fallback permanent for
the rest of the session.

### Why It Wins

It is the only surviving finding that is simultaneously real
(independently observed in source, not assumed), material (the entire
application — every workflow, not one page — is one unhandled render
error away from requiring a full restart, for a desktop tool used
during live investigations where in-progress state has real value),
distinct (never raised in MAX-1 through MAX-12, confirmed by direct
grep of the audit history), current, and actionable at low
architectural risk: the fix is scoped entirely to one existing
component (`ErrorBoundary.tsx`) and does not require touching any page,
any route, any backend contract, or any dependency.

### Expected Product Improvement

An analyst who hits an unexpected render error in one workflow (a
malformed IOC payload, an edge case in Investigation Workspace, etc.)
gets a path back into the running application — reset the boundary and
continue — instead of being forced to restart SOC-IQ and lose whatever
was in progress. This converts a currently catastrophic, all-or-nothing
failure mode into a recoverable one, for every workflow at once,
without waiting for each individual page to add its own defensive
handling.

### Affected Surface

`frontend/src/app/providers/ErrorBoundary.tsx` only. No page, no route,
no shared hook, no backend/Rust file.

### Implementation Boundary (for a future Phase 2A)

- Add a reset action (e.g. a button) to `ErrorBoundary`'s existing
  fallback render, calling `this.setState({ error: null })` (or
  equivalent) so the boundary can remount its children.
- Reuse the fallback's existing `role="alert"` container and general
  visual language already established in this same file — no new
  design system component.
- No change to `componentDidCatch`'s logging behavior.
- No change to where `ErrorBoundary` is mounted in `App.tsx`.

### Non-Goals

- **Do not add per-route/per-page error boundaries.** That is a
  materially larger, cross-cutting architectural change (one boundary
  per route, decisions about what state each page-level boundary should
  preserve) — out of this direction's bounded, low-risk scope. It is a
  legitimate larger future direction, not this one.
- Do not wire `componentDidCatch` to a real diagnostics/observability
  sink — out of scope per the component's own existing doc comment
  (`docs/architecture/19-observability-architecture.md` work).
- Do not touch `ThemeControl.tsx`, any Settings control, `DataTable.tsx`,
  or any other page/component.
- Do not touch `package.json`'s stale description (`MAX9-F-01`,
  unrelated surface, deliberately still deferred).
- No new dependency, no architecture rewrite.

### Rejected Alternatives

- DataTable virtualization: no demonstrated materiality at this
  evidence level (§13, §19) — documented as a future candidate, not
  selected.
- `package.json` description fix: real but trivial, no analyst-facing
  effect, not cycle-worthy on its own (unchanged conclusion carried
  since MAX-9).
- Real "High Contrast Dark" theme implementation: a legitimate,
  larger future direction, but explicitly out of scope for a
  small/additive/low-risk MAX-cycle selection (same reasoning MAX-12
  already applied to reject this as a non-goal).

## 21. Verification Requirements For A Future Phase 2A

- `npx tsc --noEmit` — 0 errors.
- `npm test -- --run` — 0 regressions against this phase's 1208-test
  baseline; new test(s) proving the boundary (a) still catches and
  renders its fallback on a thrown error, and (b) the new reset action
  actually remounts children afterward.
- `npm run build` — clean production build.
- Diff-audit against this baseline's untouched extraction — confirm
  only `ErrorBoundary.tsx` (and its new test file, if one is added)
  changed.

## 22. Known Limitations

- No Rust/Tauri toolchain in this sandbox (unchanged, standing
  condition) — `src-tauri/`, `keystore-core/`, `sidecar-core/` were not
  independently compiled or exhaustively audited this phase.
- No browser/Tauri runtime automation — all accessibility/responsive
  observations in this audit are source/static-level.
- No `.git` — mtime-based provenance only.
- Backend (Python) source was not exhaustively re-audited this phase,
  per the established frontend-first scope; only surfaces bearing
  directly on frontend correctness were read.
- The DataTable-virtualization observation (§13) is explicitly
  low-confidence — it reflects a structural absence, not a demonstrated
  symptom, and should not be read as an accepted finding.

---

**MAX-13 FORENSIC AUDIT COMPLETE — IMPLEMENTATION NOT PERFORMED**
