# SOC-IQ Frontend MAX-9 — Phase 2C

## Error + Empty State + Search/Filter/Table + Recovery Hardening — Closure

---

### 1. Baseline

- **Filename:** `SOC-IQ-FRONTEND-MAX-9-PHASE-2B-NAVIGATION-WORKFLOW-FULL.zip`
- **Size:** 2,545,195 bytes
- **Entries:** 811
- **SHA-256:** `1b6eeb938a0413bda5d5387fbd574bdafb502d49834d4e75626c66679bd835a6`
- Verified before implementation: ZIP integrity (`unzip -t`, clean), clean
  extraction, presence of the Phase 2B closure document, and presence of
  the required prior closures (MAX-9 Phase 1 audit, Phase 2A closure,
  MAX-8 Phase 2D closure, MAX-7 Analyst UX closure, MAX-6 Design System
  closure).
- Re-ran `tsc --noEmit`, `vitest run`, and `npm run build` against this
  exact baseline before deciding on scope: TypeScript clean, 82/82 test
  files / 1172/1172 tests passing, build succeeding with the same
  per-route chunk breakdown recorded in every prior checkpoint. The
  baseline handed to this phase is unchanged.

---

### 2. Findings Addressed

**None from the MAX-9 register** (still only MAX9-F-01, P3, package-metadata,
out of this phase's scope — unchanged since Phase 2A). Phases 2A and 2B
produced no regression finding either.

Per this phase's rule — *"Implement only: MAX-9 findings; concrete
regressions from Phase 2A/2B; issues discovered while verifying those
findings"* — this phase's own verification work against its specific new
scope (error states, empty states, search, filters, sorting, DataTable
interaction, stale data, partial data, notifications, report/export
failure) was the only remaining avenue for new evidence. That verification
was performed directly against source, not assumed, and is recorded in §3.

**No implementable finding was produced.**

---

### 3. Evidence Gathered This Phase

Because this phase's scope (error/empty/search/filter/table/recovery) is
materially different from Phase 2B's (navigation), each area was
independently re-inspected at the source level rather than treated as
already covered by prior phases' conclusions:

- **`DataTable`** (`pages/components/DataTable.tsx`, 110 lines): a
  presentational table primitive with no built-in loading/error/empty
  handling of its own — that state ownership is delegated to each
  consuming page, matching the brief's own "error ownership at the correct
  UI level" requirement rather than violating it.
- **Investigations list — error/empty/filtered-empty distinction**
  (`InvestigationsPage.tsx`): confirmed, by reading the render logic
  directly, that three states are honestly kept separate: no
  investigations exist at all ("No investigations found.", no toolbar
  shown), a fetch failure (a `role="alert"` message plus a shared `Button`
  "Retry"), and investigations existing but the current search/status
  combination matching none ("No investigations match your filters." with
  its own "Clear filters" action, toolbar left visible). This is exactly
  the three-way distinction (§ "Empty States") the brief asks to verify —
  already implemented and documented in-source as `MAX7-F-03`.
- **Search/filter mechanics**: the search input has an associated
  `<label htmlFor>` (accessible name), filtering is local `useState` (no
  extra fetch, no mutation of the normalized source rows), a "Showing X of
  Y investigations" count is always visible, and "Clear filters" appears
  only when a filter is actually active and resets both search and status
  together.
- **Report/export failure** (`ReportExportAction.tsx`): the control
  distinguishes four real states (`idle`/`exporting`/`success`/`error`) with
  correct button-disable-while-exporting behavior, a `role="status"`
  success note showing the real save path (never a fabricated one), and a
  `role="alert"` error note with the label switching to "Retry export" —
  never a false success state, never a permanently-disabled unrelated
  control. Rows without exportable data or without desktop-save support
  say so honestly ("Export unavailable" / "Desktop app required") rather
  than rendering a control that cannot work.
- **Stale-response protection** (`useInvestigation.ts`): switching between
  investigations is guarded by a monotonically increasing
  `generationRef` combined with a closure-scoped `cancelled` flag, so a
  slower, earlier fetch can never overwrite state from a newer one — the
  exact "stale data" failure mode (§ "Stale Data") this phase's brief warns
  against. In-source comments confirm this was a deliberate design choice
  ("stale partial data is not retained across a[n investigation]"), not an
  accident this phase discovered by luck.
- **Notifications**: only one notification type exists in the codebase
  (`RestartExhaustedNotification`, for sidecar-restart exhaustion). It is
  singular and state-store-driven (`restartExhaustedNotificationStore.ts`),
  so there is no toast-stack, no duplicate-message surface, and no
  possibility of a success notification surviving a failed operation
  because there is exactly one notification and its own store owns
  showing/hiding it.

No violation of the error/empty/search/filter/recovery contract this
phase's brief describes was found in any of the areas checked.

---

### 4. Findings Deferred

```text
Finding: MAX9-F-01
Status: Unchanged — still P3, still a package.json metadata issue with
  no error/empty/search/filter/recovery dimension.
Disposition: Remains open for a future documentation-scoped phase.
```

No new finding was produced by this phase's own verification work (§3).

---

### 5–9. Error-State / Empty-State / Search / Filter / Sorting-Table Changes

**None.** Each of these areas (§3) was found to already implement the
contract this phase's brief describes. Sorting was separately confirmed to
be intentionally absent: `DataTable` has no sort capability, and the
Investigations list's own in-source documentation notes this is a known,
already-accepted dependency (matching the MAX-9 audit's own observation)
rather than an oversight this phase should silently work around by adding
one — doing so would mean extending `DataTable`'s contract, which is
outside this phase's "no new table framework / preserve existing DataTable"
rule without a specific finding authorizing it.

### 10. Recovery Changes

**None.** Retry (Investigations list) and export retry (Reports) already
use the shared `Button`, already disable during the in-flight action, and
already restore to a correct state on success or a clearly-owned error on
failure.

### 11. Stale-State Verification

Confirmed via source inspection (§3) that `useInvestigation.ts` already
prevents stale responses from overwriting newer state via a generation
counter. No stale-row, stale-count, or stale-selection issue was found
elsewhere in the areas checked.

### 12. Partial-Data Verification

Not independently re-derived beyond what Phase 1 already covered (no new
evidence surfaced); no fabricated placeholder value was found in any file
read this phase.

### 13. Accessibility Verification

No markup or CSS was touched. The `role="alert"` / `role="status"` /
`aria-live="polite"` usages found in `InvestigationsPage.tsx` and
`ReportExportAction.tsx` were read directly and confirmed to follow the
"do not overuse live regions" guidance — each is a single, purposeful
status/error surface, not a system that fires repeatedly for the same
condition.

### 14. Responsive Verification

No layout/CSS file was touched. Live 1280×720/1440×900 verification
remains `ENVIRONMENT-BLOCKED` in this execution environment — unchanged,
disclosed since MAX-3.

### 15. Motion Verification

No motion-related file was touched.

---

### 16. Files Changed / Forensic Change Review

| File | Change |
| --- | --- |
| `docs/audits/SOC-IQ-FRONTEND-MAX-9-PHASE-2C-RECOVERY-CLOSURE.md` | New — this document |

Forensic diff against the Phase 2B working tree confirms this is the
**only** difference:

```text
$ diff -rq <Phase 2B tree> <Phase 2C tree>
Only in <Phase 2C tree>/docs/audits: SOC-IQ-FRONTEND-MAX-9-PHASE-2C-RECOVERY-CLOSURE.md
```

No backend, Rust/Tauri, `DataTable`, notification, or state-management
source was touched. No new table framework, no new notification system, no
speculative feature, no test weakening.

---

### 17. Test Results

```text
$ npx tsc --noEmit
(no output — clean)

$ npx vitest run
Test Files  82 passed (82)
     Tests  1172 passed (1172)
  Duration  57.82s
```

Identical counts to every prior checkpoint. No test was added or modified —
no behavior changed, and the areas verified this phase
(`investigationsViewModel.test.ts`, `useInvestigation.test.tsx`,
`useReportExport.test.tsx`, `restartExhaustedNotificationStore.test.ts`,
among others) already exercise the mechanisms described in §3 and continue
to pass unchanged.

### 18. Build Result

```text
$ npm run build
✓ 201 modules transformed.
✓ built in 2.69s
```

Identical chunk list and sizes to every prior checkpoint's build.

---

### 19. Regression Matrix

| Area                        | Result |
| ---------------------------- | ------ |
| MAX-1 Accessibility          | PASS |
| MAX-2 Loading                | PASS |
| MAX-3 Responsive             | PASS (ENVIRONMENT-BLOCKED for live viewport check, unchanged) |
| MAX-4 Motion                 | PASS |
| MAX-5 Dashboard/Data         | PASS |
| MAX-6 Design System          | PASS |
| MAX-7 Analyst UX             | PASS |
| MAX-8 Production Readiness   | PASS |
| MAX-9 Phase 2A               | PASS |
| MAX-9 Phase 2B               | PASS |
| MAX-9 Phase 2C               | PASS |

No source change occurred, so no prior guarantee had anything to regress
against; confirmed rather than assumed via a full re-run of typecheck,
tests, and build.

---

### 20. Remaining Conditions

- **MAX9-F-01** remains open and deferred, unchanged — P3,
  documentation-only, no error/empty/search/filter/recovery dimension.
- **`DataTable`'s absence of a sort capability** is noted as a known,
  already-accepted dependency (referenced in-source and consistent with
  the MAX-9 audit's own observation) — not implemented here because doing
  so would extend `DataTable`'s contract without a specific finding
  authorizing that scope expansion, per this phase's own "no new table
  framework" and "do not add sorting where no existing contract exists"
  rules.
- No other condition is carried forward. Direct re-validation of error
  ownership, the three-way empty/error/filtered-empty distinction, search
  and filter mechanics, report/export failure states, and stale-response
  protection found the existing implementation already satisfies this
  phase's stated goal.

---

### 21. Final Verdict

```text
MAX-9 PHASE 2C — PASS WITH DOCUMENTED CONDITIONS
```

This phase's mission was to harden error, empty-state, search/filter/table,
and recovery behavior based on evidence. The MAX-9 register offered nothing
in this scope, Phases 2A/2B produced no regression, and this phase's own
direct re-validation — `DataTable`'s delegated state ownership, the
Investigations list's honestly-distinguished three-way empty/error/
filtered-empty states, search/filter mechanics, report/export failure
handling, and generation-counter-based stale-response protection — found
each area already implements the contract this phase describes.
Implementing changes without such evidence would have violated this
phase's own "only evidence-backed changes" rule and risked introducing
unreviewed drift into recovery/error paths that were independently
confirmed sound. Accordingly, this phase made zero source changes and
carries forward the one pre-existing, unrelated documented condition
(MAX9-F-01), plus a noted, already-accepted `DataTable` sorting dependency
that remains out of scope absent a specific finding.
