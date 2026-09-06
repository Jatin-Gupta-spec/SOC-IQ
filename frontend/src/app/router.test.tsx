/**
 * AppRoutes tests.
 *
 * As with `navigation/NavigationRegion.test.tsx`, this exercises each
 * canonical path directly via `MemoryRouter`'s `initialEntries`
 * rather than the "/" redirect (which needs a live DOM — see
 * `navigation.live.test.tsx`). That's sufficient to prove §21's
 * requirement that every navigation destination renders its real
 * Part 3 page, without duplicating the redirect coverage that
 * already exists elsewhere.
 *
 * Updated for Phase 4G-2 Part 3: routes now render real pages
 * (`../pages`) instead of the Part 2 `RoutePlaceholder`, so this
 * asserts each page's own `<main aria-label="... page">` landmark
 * (set by the shared `PageLayout`) and its `PageHeader` title,
 * rather than the retired `"... page placeholder"` text.
 *
 * Updated again for MAX-8 Phase 2A (MAX8-F-01): every route element
 * is now a lazily-loaded component behind its own `<Suspense>`
 * boundary. `renderToStaticMarkup` cannot wait for a dynamic
 * `import()` to resolve (there is no async step in a synchronous
 * render), so it now deterministically renders each `<Suspense>`
 * boundary's fallback (`RouteLoadingFallback`) instead of the real
 * page's own content -- that is the correct, expected static-render
 * outcome for a lazy route, not a regression, and this file now
 * asserts exactly that: the landmark (`<main aria-label="... page">`)
 * still resolves to the right destination immediately (proving
 * `RouteLoadingFallback` carries the right label per route), while
 * the resolved real-page content is proven separately, live, in
 * `router.live.test.tsx` -- matching this project's existing
 * static-test/`.live.test`-file split for anything that needs a real
 * async step to observe.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { AppRoutes } from "./router";
import { NAVIGATION_ITEMS } from "./navigation/navigationModel";

describe("AppRoutes", () => {
  it.each(NAVIGATION_ITEMS.map((item) => [item.label, item.path] as const))(
    "renders the %s page's route-loading fallback (Suspense, MAX8-F-01) at %s",
    (label, path) => {
      const html = renderToStaticMarkup(
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>,
      );

      // The lazily-loaded page component itself is proven live, in
      // router.live.test.tsx -- this only proves the right Suspense
      // fallback, carrying the right destination's landmark and
      // accessible loading announcement, is what a static render
      // (matching a real first-paint before the route's JS chunk
      // arrives) produces.
      expect(html).toContain(`aria-label="${label} page"`);
      expect(html).toContain(`Loading ${label}…`);
    },
  );

  it("redirects an unknown path to the default navigation path's page", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/does-not-exist"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    // A live DOM is needed to observe the <Navigate> redirect actually
    // occur (see navigation.live.test.tsx); under static rendering the
    // <Navigate> element itself renders no output, so this only proves
    // the catch-all route doesn't throw. Real redirect behavior is
    // covered live in navigation.live.test.tsx.
    expect(html).toBe("");
  });

  // Phase 4J-3: dynamic /investigations/:investigationId route.
  // Phase 4J-6 Part 1A: a valid ID now hands off to the real
  // InvestigationWorkspacePage (see InvestigationRoute.tsx's updated
  // doc comment) instead of the old placeholder text.
  // MAX-8 Phase 2A (MAX8-F-01): InvestigationWorkspacePage is now
  // also lazy (it's the single largest page in the project -- see
  // InvestigationRoute.tsx), so a static render now deterministically
  // shows its own Suspense fallback here too, same as the five
  // navigation-item routes above. The real, post-load "Loading
  // investigation..." state (from `useInvestigation()`'s own
  // synchronous initial state once the page chunk has resolved) is
  // proven live, in router.live.test.tsx.
  describe("the dynamic investigation route", () => {
    it("reaches the investigation route for a valid numeric ID", () => {
      const html = renderToStaticMarkup(
        <MemoryRouter initialEntries={["/investigations/123"]}>
          <AppRoutes />
        </MemoryRouter>,
      );

      expect(html).toContain('aria-label="Investigation Workspace page"');
      expect(html).toContain("Loading Investigation Workspace…");
    });

    it("does not enter the valid investigation route for a non-numeric ID", () => {
      const html = renderToStaticMarkup(
        <MemoryRouter initialEntries={["/investigations/not-a-number"]}>
          <AppRoutes />
        </MemoryRouter>,
      );

      // The route itself still matches (it's a string param, not a
      // numeric route constraint) -- what must NOT happen is the
      // component treating "not-a-number" as a valid investigation ID.
      expect(html).toContain('aria-label="Investigation page"');
      expect(html).not.toContain("Investigation #");
      expect(html).toContain("not a valid investigation ID");
    });

    it("does not shadow the existing static /investigations route", () => {
      const html = renderToStaticMarkup(
        <MemoryRouter initialEntries={["/investigations"]}>
          <AppRoutes />
        </MemoryRouter>,
      );

      expect(html).toContain('aria-label="Investigations page"');
    });
  });
});
