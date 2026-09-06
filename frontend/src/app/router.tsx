import { lazy, Suspense, type ComponentType, type ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { DEFAULT_NAVIGATION_PATH, NAVIGATION_ITEMS } from "./navigation/navigationModel";
import { RouteLoadingFallback } from "./RouteLoadingFallback";
import { InvestigationRoute } from "./InvestigationRoute";

/**
 * Routing foundation (Phase 4G-2 Part 2) + real page integration
 * (Phase 4G-2 Part 3) + route-level code-splitting (MAX-8 Phase 2A,
 * MAX8-F-01).
 *
 * `HashRouter` (wired in `App.tsx`) is used rather than
 * `BrowserRouter` because the production build is served from
 * Tauri's custom asset protocol, not a path-aware HTTP server with
 * rewrite rules — hash-based routes need no server cooperation.
 *
 * One `<Route>` per `NAVIGATION_ITEMS` entry, so the sidebar
 * (`NavigationRegion`) and the router share the exact same path
 * list — no second, hand-maintained route table that could drift
 * from the navigation model. `PAGE_BY_NAVIGATION_ID` maps each
 * navigation item's stable `id` (not its label) to its Part 3 page
 * component. A missing mapping throws rather than silently
 * rendering a blank page.
 *
 * # Code-splitting (MAX8-F-01)
 *
 * Each entry is now `React.lazy(...)` instead of a static import, so
 * `vite build` emits one chunk per page instead of bundling all five
 * (plus the Investigation Workspace, below) into the single
 * `index-<hash>.js` the MAX-8 audit flagged. The audit's finding was
 * specifically about the *route table's* eager-import pattern
 * (`router.tsx` imports every page directly, confirmed by grep for
 * `React.lazy`/`Suspense` returning zero matches) — switching each
 * entry to `lazy()` here, in the one place all five/six routes are
 * already enumerated, addresses that directly without touching any
 * individual page's own internals or public props. Each lazy loader
 * re-exports the page's existing named export as `default`, since
 * `React.lazy` requires a default export and none of these page
 * modules use one — no page file itself needed to change.
 *
 * Every `<Route>` element gets its own `<Suspense>` boundary (rather
 * than one boundary wrapping the whole `<Routes>`) so that navigating
 * to a not-yet-loaded route shows only that route's own loading state
 * without ever unmounting/remounting sibling routes, and so each
 * fallback can carry that specific destination's own accessible page
 * name (`RouteLoadingFallback`) instead of one generic label for
 * every destination.
 */

const PAGE_BY_NAVIGATION_ID: Record<string, ComponentType> = {
  dashboard: lazy(() => import("../pages/DashboardPage").then((m) => ({ default: m.DashboardPage }))),
  analyze: lazy(() => import("../pages/AnalyzePage").then((m) => ({ default: m.AnalyzePage }))),
  investigations: lazy(() =>
    import("../pages/InvestigationsPage").then((m) => ({ default: m.InvestigationsPage })),
  ),
  reports: lazy(() => import("../pages/ReportsPage").then((m) => ({ default: m.ReportsPage }))),
  settings: lazy(() => import("../pages/SettingsPage").then((m) => ({ default: m.SettingsPage }))),
};

export function AppRoutes(): ReactElement {
  return (
    <Routes>
      <Route path="/" element={<Navigate to={DEFAULT_NAVIGATION_PATH} replace />} />
      {NAVIGATION_ITEMS.map((item) => {
        const Page = PAGE_BY_NAVIGATION_ID[item.id];
        if (!Page) {
          throw new Error(`SOC-IQ: no Part 3 page mapped for navigation id "${item.id}".`);
        }
        return (
          <Route
            key={item.id}
            path={item.path}
            element={
              <Suspense fallback={<RouteLoadingFallback label={item.label} />}>
                <Page />
              </Suspense>
            }
          />
        );
      })}
      {/*
        Dynamic investigation route (Phase 4J-3). Additive: not part of
        `NAVIGATION_ITEMS`/the sidebar (no static nav entry links here
        directly -- it's reached with a specific ID, e.g. from a future
        investigations list), so it's declared as its own `<Route>`
        rather than folded into `PAGE_BY_NAVIGATION_ID`. Placed after
        the static routes and before the catch-all so it doesn't
        shadow or reorder any existing route.
      */}
      <Route path="/investigations/:investigationId" element={<InvestigationRoute />} />
      {/*
        PD-05: the retired top-level `#/ioc-explorer` and
        `#/threat-intel` destinations no longer have a dedicated
        `<Route>` (removed from `PAGE_BY_NAVIGATION_ID` above along
        with their `NAVIGATION_ITEMS` entries). A direct or bookmarked
        navigation to either hash path now simply falls through to
        this existing catch-all, which redirects to
        `DEFAULT_NAVIGATION_PATH` -- no bespoke redirect was added or
        is needed.

        PD-06 (Part 3): the retired top-level `#/risk` destination
        follows this exact same pattern -- removed from
        `PAGE_BY_NAVIGATION_ID` and `NAVIGATION_ITEMS`, no bespoke
        redirect added. Real risk data remains available inside the
        Investigation Workspace (Overview tab), which this retirement
        does not touch.
      */}
      <Route path="*" element={<Navigate to={DEFAULT_NAVIGATION_PATH} replace />} />
    </Routes>
  );
}
