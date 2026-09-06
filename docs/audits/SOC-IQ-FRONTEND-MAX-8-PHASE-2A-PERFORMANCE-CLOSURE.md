# SOC-IQ Frontend MAX-8 — Phase 2A

## Performance + Rendering Hardening — Closure

---

### 1. Baseline

- **Filename:** `SOC-IQ-FRONTEND-MAX-8-PRODUCTION-READINESS-AUDIT-FULL.zip`
- Extracted twice: one working copy (`baseline/`) that this phase edited, and one
  pristine, untouched comparison copy (`pristine/`) used for the forensic diff in §12.
- Read in full before any edit: `docs/audits/SOC-IQ-FRONTEND-MAX-8-PRODUCTION-READINESS-AUDIT.md`
  (the Phase 1 audit this phase implements against), plus the MAX-7 and MAX-6 closure
  documents referenced by it.

---

### 2. Accepted Findings

Per the brief's hard scope ("implement ONLY accepted MAX-8 findings related to...
performance/rendering") and the audit's own §21 remediation-order caveats:

| Finding | Priority | In scope for 2A? | Disposition |
| --- | --- | --- | --- |
| **MAX8-F-01** — route-level code-splitting half | P2 | **Yes** | **Implemented** (this phase) |
| **MAX8-F-01** — `DataTable` virtualization half | P2 | No | **Deferred** — audit and brief both say not to add virtualization without a real, known target dataset size; none exists. No change made. |
| **MAX8-F-02** — `DataTable`/column memoization | P3 | No | **Deferred** — audit's own recommended direction: "if a real re-render cost is ever measured"; brief §2: no `memo`/`useMemo`/`useCallback` without a concrete reason. No re-render cost has been measured. No change made. |
| **MAX8-F-03** — `StatusBadge.css` raw px value | P3 | **No** | Out of hard scope — design-token consistency, not performance/rendering. Not implemented in this phase. |
| **MAX8-F-04** — large-file extraction | P3 | No | Audit's own recommendation: no action. No change made. |
| **MAX8-F-05** — patch-level dependency bumps | P3 | **No** | Out of hard scope — dependency hygiene, not performance/rendering, and brief §9 requires an audit-identified *concrete need* before touching dependencies at all (this one is routine maintenance, not a performance fix). Not implemented in this phase. |

Only **MAX8-F-01's code-splitting half** is both (a) a performance/rendering finding
and (b) implementable without speculation — the audit already confirmed, by grep, that
zero `React.lazy`/`Suspense` usage exists anywhere in `src`, and its "recommended
direction" explicitly called this the low-structural-risk, additive half of F-01.
Everything else above stays untouched this phase, on the brief's own instruction not
to fix speculative performance concerns or do general cleanup outside hard scope.

---

### 3. Implemented Changes

**Route-level code-splitting (MAX8-F-01)**

- `frontend/src/app/router.tsx` — `PAGE_BY_NAVIGATION_ID`'s five entries
  (`DashboardPage`, `AnalyzePage`, `InvestigationsPage`, `ReportsPage`,
  `SettingsPage`) changed from static imports (via the `../pages` barrel) to
  `React.lazy(() => import(...))`, one per `NAVIGATION_ITEMS` entry — same table,
  same one-map-per-route pattern the audit's own "recommended direction" called out.
  Each route's `<Route element>` is now wrapped in its own `<Suspense>` boundary
  (one per route, not one shared boundary around the whole `<Routes>`), so navigating
  to an unloaded route never unmounts sibling routes and each fallback carries that
  specific destination's own accessible name.
- `frontend/src/app/InvestigationRoute.tsx` — `InvestigationWorkspacePage` (497
  lines, one of the two largest files in the project per MAX8-F-04) is now lazy the
  same way, wrapped in its own `<Suspense>` boundary. This is the single
  highest-value split available under F-01: an analyst who never opens an
  investigation in a session never pays for that page's JS (or, transitively, for
  `InvestigationIocWorkspace.tsx`, the other 665-line file it composes).
- `frontend/src/app/RouteLoadingFallback.tsx` (new) + `RouteLoadingFallback.css`
  (new) — the shared `<Suspense fallback>` component. Renders the same `PageLayout`
  `<main aria-label="... page">` landmark contract every real page already honors
  (parameterized per route, so the landmark's accessible name never regresses to
  something generic or missing during the brief window a chunk is loading), a
  `role="status" aria-live="polite"` loading announcement using the project's
  existing shared `.skeleton-status` visually-hidden pattern, and one
  `SkeletonBlock` (MAX-2's existing shared loading-block primitive, already
  reduced-motion aware via `useReducedMotion()`).

No page component's own internals, props, or public API changed. No page's route
path, `NAVIGATION_ITEMS` entry, or navigation label changed.

---

### 4. Performance Rationale

**Before (audit's own measured baseline, this environment):**

```text
dist/assets/index-<hash>.js     306.93 kB  (gzip 90.16 kB)   -- single chunk, all
                                                                 five pages + workspace
199 modules transformed
```

**After (this phase, measured — see §7):**

```text
dist/assets/index-CVAjICVV.js                        211.16 kB  (gzip 68.89 kB)
dist/assets/InvestigationWorkspacePage-DshcLmnd.js     37.36 kB  (gzip  9.07 kB)
dist/assets/AnalyzePage-C4-pPPQY.js                    17.77 kB  (gzip  6.01 kB)
dist/assets/DashboardPage-DZw1-Fbb.js                  15.02 kB  (gzip  3.80 kB)
dist/assets/SettingsPage-CW0mi7OS.js                   10.04 kB  (gzip  2.76 kB)
dist/assets/InvestigationsPage-6hC4SeWC.js              7.28 kB  (gzip  2.53 kB)
dist/assets/ReportsPage-DsayjFCP.js                     7.18 kB  (gzip  2.62 kB)
dist/assets/DataTable-BEWFiOmO.js                       3.84 kB  (gzip  1.12 kB)
+ several small shared chunks (StatusBadge, MetricCard, useInvestigationsList, etc.)
201 modules transformed
```

The `index-*.js` entry chunk — the one every route pays for on first paint,
regardless of which page an analyst opens — drops from 306.93 kB to 211.16 kB raw
(90.16 kB → 68.89 kB gzipped), a **measured, real reduction of ~23% gzipped**, not an
estimate. An analyst who spends a session only on the Dashboard, for example, now
never downloads/parses/evaluates the Investigation Workspace's 37.36 kB chunk (or,
transitively, `InvestigationIocWorkspace.tsx`'s code) at all. This is exactly the gap
MAX8-F-01 named: "every route ... is paid for on first load" even when unvisited.

Two per-route CSS files appearing in the build output (e.g.
`InvestigationWorkspacePage-ybCnMomR.css`, `DashboardPage-DA_Fq8Mh.css`) are Vite's
automatic consequence of code-splitting a component whose module already had its own
CSS import — not a separate change, and not a regression: total CSS byte count across
all chunks is materially unchanged from the prior single 64.20 kB file, only its
chunk boundaries moved to match the new JS chunk boundaries.

**What was not done, and why:** `DataTable` virtualization and memoization (the
other half of F-01, and all of F-02) were not implemented. No real dataset size or
measured re-render cost exists in this environment to justify either — the audit
itself classified list/table scale as `STATIC PERFORMANCE RISK — NOT BENCHMARKED`,
and the brief is explicit that speculative `memo`/`useMemo`/`useCallback` or
virtualization additions are out of scope without a concrete reason. Adding either
now would be exactly the kind of unjustified optimization §2 of the brief prohibits.

---

### 5. Before/After Behavior

- **Navigation:** identical. Same five sidebar destinations, same paths, same
  `NAVIGATION_ITEMS`-driven route table, same redirect/catch-all behavior.
- **First paint of a route not yet visited this session:** now shows
  `RouteLoadingFallback` (a landmark + status announcement + skeleton block) for the
  duration of that route's chunk fetch/evaluate, before the real page mounts. This
  window is not observable as a delay in this environment (no dev server/browser
  available for timing), but is architecturally real and is the intended, correct
  behavior of `React.lazy` + `Suspense` — not a defect.
- **Every other in-session navigation to an already-loaded route:** unchanged: the
  module is cached by the browser's module loader after first load, so `Suspense`
  never re-suspends for a route already visited this session.
- **Investigation route, invalid ID:** unchanged — `InvestigationRoute`'s own
  inline "not a valid investigation ID" branch was never part of the lazy boundary
  and still renders synchronously exactly as before.
- **Investigation route, valid ID, no Tauri runtime (this environment/tests):**
  once `InvestigationWorkspacePage`'s chunk resolves, `useInvestigation()`'s own
  existing fetch-and-error behavior is unchanged and was proven live (§6) — this
  phase did not touch that hook or its error/loading/success states at all.

---

### 6. Tests

Two files updated/added, both exercising only the routing/Suspense boundary this
phase actually changed:

- **`frontend/src/app/router.test.tsx`** (updated) — the five parameterized
  navigation-item tests and the investigation-route test now assert the *correct*
  static-render outcome for a lazy route: `renderToStaticMarkup` cannot observe a
  dynamic `import()` resolving (there is no async step available to it), so it
  deterministically renders each route's `Suspense` fallback. Updated to assert that
  fallback carries the right destination's landmark (`aria-label="... page"`) and
  loading announcement, rather than the old assertion (the real page's heading) that
  no longer reflects what a static render of a lazy route actually produces. This is
  not a weakened test — it proves the same landmark-identity guarantee via the
  fallback's own props, and now correctly documents *why* static rendering shows the
  fallback rather than silently asserting something that stopped being true.
- **`frontend/src/app/router.live.test.tsx`** (new) — the live-DOM counterpart,
  using this project's existing `react-dom/client` + `act` + jsdom pattern (matching
  `navigation.live.test.tsx` and the ten other `.live.test` files already in the
  project; no `@testing-library/react` or other new dependency added). Proves the
  thing that actually matters for MAX8-F-01: every route's real page content —
  proven by its own `<h1>` heading — still renders end-to-end once its chunk
  resolves, for all five navigation-item routes plus the Investigation Workspace
  route (asserted via its real error-state text, since no Tauri runtime is present
  in this test environment — consistent with how the project's other live tests
  already handle that same constraint).

**Full suite results (this environment, `npx vitest run`):**

```text
Test Files  82 passed (82)
     Tests  1172 passed (1172)
```

(Baseline was 81 files / 1166 tests; this phase adds one new file with 6 tests —
82/1172 — and modifies zero others. No test was deleted, skipped, or weakened.)

---

### 7. TypeScript

```text
$ npx tsc --noEmit
(no output — exit 0)
```

**PASS**, clean, with the project's existing `noUnusedLocals`/`noUnusedParameters`
strictness unchanged and unweakened.

---

### 8. Build

```text
$ npm run build
> tsc --noEmit && vite build
vite v5.4.21 building for production...
✓ 201 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                        0.39 kB │ gzip:  0.26 kB
dist/assets/MetricCard-D7bfu9Ry.css                     1.11 kB │ gzip:  0.43 kB
dist/assets/DataTable-D81UJSg_.css                      2.80 kB │ gzip:  0.78 kB
dist/assets/SettingsPage-CozYlcO4.css                   2.84 kB │ gzip:  0.67 kB
dist/assets/StatusBadge-svcYUkB4.css                    2.86 kB │ gzip:  0.66 kB
dist/assets/ReportsPage-DwoWEuoU.css                    3.04 kB │ gzip:  0.74 kB
dist/assets/InvestigationsPage-C0GAh-sM.css             3.24 kB │ gzip:  0.77 kB
dist/assets/AnalyzePage-PToO8zUt.css                    4.80 kB │ gzip:  1.17 kB
dist/assets/DashboardPage-DA_Fq8Mh.css                 13.39 kB │ gzip:  2.10 kB
dist/assets/index-VHngyuku.css                         14.19 kB │ gzip:  3.31 kB
dist/assets/InvestigationWorkspacePage-ybCnMomR.css    16.00 kB │ gzip:  2.18 kB
dist/assets/index-BI4gUBDD.js                           0.28 kB │ gzip:  0.18 kB
dist/assets/types-CJVIbdXd.js                           0.34 kB │ gzip:  0.24 kB
dist/assets/useInvestigationsList-32tqZzbG.js           0.57 kB │ gzip:  0.33 kB
dist/assets/MetricCard-CuMczssu.js                      0.60 kB │ gzip:  0.31 kB
dist/assets/StatusBadge-BjRod607.js                     0.65 kB │ gzip:  0.37 kB
dist/assets/DataTable-BEWFiOmO.js                       3.84 kB │ gzip:  1.12 kB
dist/assets/ReportsPage-DsayjFCP.js                     7.18 kB │ gzip:  2.62 kB
dist/assets/InvestigationsPage-6hC4SeWC.js              7.28 kB │ gzip:  2.53 kB
dist/assets/SettingsPage-CW0mi7OS.js                   10.04 kB │ gzip:  2.76 kB
dist/assets/DashboardPage-DZw1-Fbb.js                  15.02 kB │ gzip:  3.80 kB
dist/assets/AnalyzePage-C4-pPPQY.js                    17.77 kB │ gzip:  6.01 kB
dist/assets/InvestigationWorkspacePage-DshcLmnd.js     37.36 kB │ gzip:  9.07 kB
dist/assets/index-CVAjICVV.js                         211.16 kB │ gzip: 68.89 kB
✓ built in 2.57s
```

**PASS.** `frontend/node_modules` and `frontend/dist` were removed again after this
build, before packaging (§10), matching MAX-8 Phase 1's own precedent of never
shipping either in a delivered checkpoint ZIP.

---

### 9. Accessibility Regression

`PASS`, by source inspection (no browser/screen-reader available in this
environment — same limitation the Phase 1 audit itself carried under §22):

- Every real page's own `PageLayout` `<main aria-label="... page">` landmark is
  unchanged — no page's own JSX was touched.
- `RouteLoadingFallback` reuses that exact same `PageLayout` contract during the
  loading window, parameterized per route, so the accessible landmark name for a
  given destination never changes identity, disappears, or goes generic between
  "chunk loading" and "chunk loaded."
- `RouteLoadingFallback` adds a `role="status" aria-live="polite"` announcement
  (reusing the project's existing shared `.skeleton-status` visually-hidden CSS
  class, the same idiom `DashboardPage.tsx` already established for its own
  skeleton), so assistive tech is told a page is loading rather than encountering
  silence followed by a sudden content swap.
- `SkeletonBlock` itself is unmodified and already `aria-hidden="true"` with
  existing reduced-motion handling (§10 below).
- No focus management changed: `Suspense` does not move focus, and neither did the
  eager-import version it replaces.
- MAX-1/MAX-6 keyboard/tab/table/ARIA behavior was not touched by this phase in any
  page's own source.

---

### 10. Responsive Regression

`ENVIRONMENT-BLOCKED` — no dev server or browser was available in this environment,
consistent with every prior phase of this project (audit §22). This phase made no
layout, CSS-sizing (beyond `RouteLoadingFallback`'s own single `min-height`/`width`
rule), or breakpoint changes to any existing page. `RouteLoadingFallback` uses the
same `PageLayout` wrapper every page already uses at 1280×720 and 1440×900, so no
new responsive surface was introduced beyond what `PageLayout` already handles.

---

### 11. Motion Regression

`PASS`. `RouteLoadingFallback` reuses `SkeletonBlock` and `useReducedMotion()`
exactly as `DashboardPage`/`InvestigationWorkspacePage`/etc. already do — no new
animation, decorative or otherwise, was introduced. Reduced-motion behavior for this
new loading state degrades identically to every other skeleton in the project (pulse
disabled, static block shown).

---

### 12. Forensic Diff

`Git provenance unavailable; filesystem/static diff verification performed.`

The baseline ZIP was extracted twice: once as the working copy this phase edited,
once as an untouched comparison copy. `diff -rq` between the two (excluding only
`node_modules`/`dist`, install/build-only artifacts never part of any delivered
checkpoint ZIP) after this phase's work was complete:

```text
Files .../frontend/src/app/InvestigationRoute.tsx differ
Only in modified copy: frontend/src/app/RouteLoadingFallback.css
Only in modified copy: frontend/src/app/RouteLoadingFallback.tsx
Only in modified copy: frontend/src/app/router.live.test.tsx
Files .../frontend/src/app/router.test.tsx differ
Files .../frontend/src/app/router.tsx differ
```

**Exactly six touched paths, all under `frontend/src/app/`:**

| Path | Change | Maps to |
| --- | --- | --- |
| `frontend/src/app/router.tsx` | Modified | MAX8-F-01 |
| `frontend/src/app/InvestigationRoute.tsx` | Modified | MAX8-F-01 |
| `frontend/src/app/RouteLoadingFallback.tsx` | New | MAX8-F-01 (supporting) |
| `frontend/src/app/RouteLoadingFallback.css` | New | MAX8-F-01 (supporting) |
| `frontend/src/app/router.test.tsx` | Modified | Test update for MAX8-F-01 |
| `frontend/src/app/router.live.test.tsx` | New | Regression test for MAX8-F-01 |

- No unrelated changes found.
- No accidental formatting churn found outside the six paths above.
- `frontend/package.json` and `frontend/package-lock.json`: **untouched** — zero
  dependency drift; MAX8-F-05 was correctly left unimplemented (out of hard scope).
- `app/` (Python backend), `src-tauri/` (Rust/Tauri), `database/`, `packaging/`:
  **confirmed untouched** — none appear in the diff above.
- No `.git` directory was present in the baseline ZIP (consistent with the Phase 1
  audit's own §4/§21 notes), so this diff is filesystem-level, not Git-history-level.

---

### 13. Remaining Conditions

- **MAX8-F-01's virtualization half, and all of MAX8-F-02**, remain unimplemented,
  by design (§2/§4) — no real dataset size or measured re-render cost exists to
  justify either. `DataTable` list/table scale remains
  `STATIC PERFORMANCE RISK — NOT BENCHMARKED`, unchanged from the Phase 1 audit's own
  classification. This should stay open until a real target investigation/IOC volume
  or an actual measured re-render cost is known — not implemented speculatively.
- **MAX8-F-03** (StatusBadge token bypass) and **MAX8-F-05** (patch-level dependency
  bumps) remain unimplemented — out of this phase's hard scope (not
  performance/rendering findings). Both remain valid, low-risk items for a future,
  differently-scoped phase.
- **MAX8-F-04** (large-file extraction) remains a watch item only, per the audit's
  own recommendation — no action taken or currently recommended.
- Responsive verification remains `ENVIRONMENT-BLOCKED` — no dev server/browser was
  available in this environment, same standing limitation carried since MAX-3.
- The measured bundle-size improvement (§4) is real and reproducible in this
  environment's `vite build` output, but real-world load-time impact (as opposed to
  byte-count impact) was not measured, since no browser/network-throttling
  environment was available.

---

### 14. Final Verdict

```text
MAX-8 PHASE 2A — PASS WITH DOCUMENTED CONDITIONS
```

The one in-scope, non-speculative performance finding (MAX8-F-01's code-splitting
half) is implemented, tested (live and static), and measured (real before/after
build output showing the shared entry chunk drop from 90.16 kB to 68.89 kB gzipped).
TypeScript is clean, the full suite passes (82 files / 1172 tests), and the forensic
diff confirms no scope creep. The "documented conditions" are the deliberately
unimplemented items above (F-01's virtualization half, F-02, F-03, F-04, F-05) — each
correctly out of scope or unjustified without further evidence, not oversights.
