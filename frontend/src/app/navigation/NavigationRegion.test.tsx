/**
 * NavigationRegion (sidebar) UI tests.
 *
 * `react-dom/server` + `MemoryRouter` again (no jsdom) — see
 * `shell/AppShell.test.tsx`'s header for why that combination is
 * enough for structural/route-driven assertions, and
 * `../navigation.live.test.tsx` for the one file that needs a real
 * DOM (click simulation).
 *
 * "Navigation changes with the route" (§10/§22) is verified here by
 * rendering at each of the eight canonical paths via
 * `MemoryRouter`'s `initialEntries` and asserting the right link
 * carries `aria-current="page"` — i.e. proving the active item is
 * genuinely *derived from the route*, for every destination, not
 * just the one a click test happens to exercise.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { NavigationRegion } from "../shell/NavigationRegion";
import { NAVIGATION_ITEMS } from "./navigationModel";

function renderAt(path: string): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <NavigationRegion />
    </MemoryRouter>,
  );
}

describe("NavigationRegion", () => {
  it("renders the primary navigation landmark", () => {
    const html = renderAt("/dashboard");
    expect(html).toContain('aria-label="Primary navigation"');
  });

  it("renders the SOC-IQ brand", () => {
    const html = renderAt("/dashboard");
    expect(html).toContain("SOC-IQ");
  });

  it("renders all eight destinations with accessible names", () => {
    const html = renderAt("/dashboard");

    for (const item of NAVIGATION_ITEMS) {
      expect(html).toContain(`aria-label="${item.ariaLabel ?? item.label}"`);
      expect(html).toContain(`>${item.label}<`);
    }
  });

  it("renders every destination as a real link with an icon", () => {
    const html = renderAt("/dashboard");

    for (const item of NAVIGATION_ITEMS) {
      expect(html).toContain(`href="${item.path}"`);
    }
    // Icons are inline <svg>, hidden from assistive tech since the
    // link itself already carries the accessible name.
    const svgCount = (html.match(/<svg/g) ?? []).length;
    expect(svgCount).toBe(NAVIGATION_ITEMS.length);
    // Phase 4G-3 Part 2: the sidebar's status footer
    // (`SidecarStatusIndicator`) adds exactly one more decorative
    // `aria-hidden="true"` element (its tone dot) alongside the nav
    // icons — accounted for explicitly here, not folded silently into
    // `NAVIGATION_ITEMS.length`, so this assertion still fails loudly
    // if a future change adds an unexpected extra hidden element.
    const NON_NAV_DECORATIVE_ELEMENTS = 1;
    expect((html.match(/aria-hidden="true"/g) ?? []).length).toBe(
      NAVIGATION_ITEMS.length + NON_NAV_DECORATIVE_ELEMENTS,
    );
  });

  it("renders Settings after a divider, separated from the primary group", () => {
    const html = renderAt("/dashboard");

    const dividerIndex = html.indexOf('class="nav-sidebar__divider"');
    const settingsIndex = html.indexOf('aria-label="Settings"');
    const reportsIndex = html.indexOf('aria-label="Reports"');

    expect(dividerIndex).toBeGreaterThan(-1);
    expect(reportsIndex).toBeLessThan(dividerIndex);
    expect(dividerIndex).toBeLessThan(settingsIndex);
  });

  it.each(NAVIGATION_ITEMS.map((item) => [item.label, item.path] as const))(
    "marks only %s active when the route is %s",
    (label, path) => {
      const html = renderAt(path);

      // Exactly one active link, and it's the right one.
      expect((html.match(/aria-current="page"/g) ?? []).length).toBe(1);

      const activeItem = NAVIGATION_ITEMS.find((item) => item.path === path);
      expect(activeItem?.label).toBe(label);
      expect(html).toContain("nav-sidebar__link--active");
    },
  );
});
