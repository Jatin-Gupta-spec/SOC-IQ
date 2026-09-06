// @vitest-environment jsdom
/**
 * MAX-8 Phase 2A (MAX8-F-01) — live route-resolution tests.
 *
 * `router.test.tsx` proves each route's `<Suspense>` fallback
 * (`RouteLoadingFallback`) via `renderToStaticMarkup`, since a
 * synchronous static render can never observe a dynamic `import()`
 * resolving. This file is the live-DOM counterpart, following the
 * same `react-dom/client` + `act` + jsdom approach
 * `navigation.live.test.tsx` and this project's other `.live.test`
 * files already established (no `@testing-library/react` added —
 * native DOM query/`act` is enough for these assertions, matching
 * the project's existing precedent of not adding a test dependency
 * for convenience). It proves the thing that actually matters for
 * MAX8-F-01: that code-splitting is purely a loading-sequence change,
 * and every route's real, previously-eager page content still
 * renders exactly as before once its chunk resolves.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "./router";
import { NAVIGATION_ITEMS } from "./navigation/navigationModel";

/**
 * SOC-IQ GATE 2 STEP 5 — forensic finding.
 *
 * A clean-Windows CI run (`npm ci` + `vitest run` in a fresh
 * environment, no warmed Vite/Vitest transform cache) failed the
 * first three of this file's five `it.each` cases (Dashboard,
 * Analyze, Investigations) plus the Investigation Workspace case,
 * while the identical suite passed 1376/1376 with zero flakiness in
 * this project's own reference environment (verified as part of this
 * investigation, `npm ci` + three consecutive full `vitest run`
 * passes). Instrumented timing of `renderAt()`'s per-attempt polling
 * loop showed the *first* time any given lazy route module is
 * dynamically imported in a freshly-spawned Vitest worker, the
 * on-demand transform (Vite/esbuild, cold — no `.vite` cache yet)
 * costs measurably more real wall-clock time than every subsequent
 * import in that same worker (observed: Dashboard, the first route
 * touched, at ~3x the cost of Reports/Settings, the last two touched,
 * in the very same file); the Investigation Workspace's own lazy
 * chunk (this project's two largest non-test source files) shows the
 * same first-touch cost independently. The 40-attempt / 100ms
 * (4000ms) budget below was only ever validated against that fast,
 * already-warm reference environment and leaves too little headroom
 * for a colder, slower-disk first import elsewhere (a clean Windows
 * checkout being the concrete case that surfaced it) -- it is a test
 * synchronization defect, not a routing/lazy-loading defect: the
 * production `React.lazy`/`Suspense` wiring in `router.tsx` and
 * `InvestigationRoute.tsx` is unchanged and, per the above, resolves
 * correctly every time once given enough wall-clock time.
 *
 * Fix: widen this file's own polling budget (loop iteration count
 * only -- the 100ms poll interval, and everything the loop actually
 * checks for, are untouched) and this file's Vitest test timeout to
 * match, scoped to this file alone via `vi.setConfig`. A fast
 * environment is completely unaffected (the loop still returns the
 * instant its condition is met); a slow first-import environment now
 * gets real headroom instead of a tight one calibrated for a single
 * reference machine.
 */
vi.setConfig({ testTimeout: 15_000 });

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

async function renderAt(path: string): Promise<void> {
  await act(async () => {
    root = createRoot(container);
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>,
    );
  });

  // The initial `act` above only flushes the render that *triggers*
  // each lazy `import()` (Suspense's fallback commit); the import
  // itself resolves once its module has actually been transformed by
  // Vite/Vitest's on-demand pipeline, which -- the first time a given
  // page module is requested -- can take real wall-clock time (well
  // beyond a single microtask or timer tick), not just scheduling
  // latency. Poll with a real per-attempt budget and stop as soon as
  // the fallback's own status text is gone, rather than either a
  // single fixed wait (flaky under cold-transform latency) or a fixed
  // number of short ticks (same problem, just retried).
  //
  // 120 attempts (12s) rather than the original 40 (4s) -- see the
  // GATE 2 STEP 5 forensic note above `vi.setConfig` at the top of
  // this file for why. The 100ms interval is unchanged.
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (!container.textContent?.includes("Loading ")) {
      return;
    }
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 100));
    });
  }
}

describe("AppRoutes (live DOM, lazy resolution)", () => {
  it.each(NAVIGATION_ITEMS.map((item) => [item.label, item.path] as const))(
    "resolves the %s page's real content at %s once its chunk loads",
    async (label, path) => {
      await renderAt(path);

      const main = container.querySelector(`[aria-label="${label} page"]`);
      expect(main).not.toBeNull();
      // The route-loading fallback's own status text must be gone --
      // proves this is the real page, not the still-pending
      // `RouteLoadingFallback`.
      expect(main?.textContent).not.toContain(`Loading ${label}…`);
      expect(main?.querySelector("h1, h2")?.textContent).toBe(label);
    },
  );

  it("resolves the real Investigation Workspace page for a valid numeric ID", async () => {
    await renderAt("/investigations/123");

    const main = container.querySelector('[aria-label="Investigation Workspace page"]');
    expect(main).not.toBeNull();
    // Proves this is the real, lazily-loaded InvestigationWorkspacePage
    // -- not the still-pending RouteLoadingFallback -- by its own
    // heading, present in every one of that page's states (loading,
    // error, or success; see InvestigationWorkspacePage.tsx).
    expect(main?.querySelector("h1")?.textContent).toBe("Investigation Workspace");
    expect(main?.textContent).not.toContain("Loading Investigation Workspace…");
    // No Tauri runtime is present in this jsdom test environment (by
    // design -- see FileDropzone.live.test.tsx/client.ts's own doc
    // comments), so useInvestigation()'s real fetch attempt fails
    // fast; this proves the real page's own error state renders
    // end-to-end post-lazy-load, not that a network call ever
    // succeeds here.
    expect(main?.textContent).toContain("Something went wrong loading this investigation");
  });
});
