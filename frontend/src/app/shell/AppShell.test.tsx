/**
 * AppShell foundation tests.
 *
 * Still uses `react-dom/server`'s `renderToStaticMarkup` (no
 * `@testing-library/react`/jsdom) per Part 1's original approach —
 * see `../navigation.live.test.tsx` for the one file in this project
 * that genuinely needs a live DOM instead, and why.
 *
 * Updated for Phase 4G-2 Part 2: `AppShell` always renders the real
 * `NavigationRegion` internally now (not a bare placeholder), and
 * `NavigationRegion`'s links use `react-router-dom`'s `NavLink`,
 * which requires a `Router` in context to render at all. These tests
 * wrap `AppShell` in a `MemoryRouter` for that reason — `AppShell`
 * itself still takes no router prop and knows nothing about routing.
 *
 * Extended for Phase 4G-4 Part 2: `AppShell` now also mounts
 * `RestartExhaustedNotification` (see `AppShell.tsx`). These tests
 * never drive the notification's default store into an exhausted
 * state, so they only assert the not-visible case here (the
 * component renders `null`, i.e. no `role="alert"`); the visible
 * case, real transitions, dismissal, and no-duplicate-on-rerender are
 * covered against a live DOM in `AppShell.live.test.tsx` instead,
 * matching `RestartExhaustedNotification`'s own
 * static/live test split.
 *
 * Extended for Phase 4G-5 Part 1: `AppShell` now also mounts
 * `CommandPaletteContainer`. Same split applies — closed-by-default
 * is asserted here; Ctrl+K invocation, search, keyboard navigation,
 * and selection are covered in `commandPalette/*.live.test.tsx`
 * instead.
 */

import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { AppShell } from "./AppShell";

function renderShell(children: ReactNode): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <AppShell>{children}</AppShell>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  it("mounts without throwing", () => {
    expect(() => renderShell(<div />)).not.toThrow();
  });

  it("renders a navigation region landmark", () => {
    const html = renderShell(<div />);

    expect(html).toContain("app-shell__navigation-region");
    expect(html).toContain('aria-label="Primary navigation"');
  });

  it("renders a content region", () => {
    const html = renderShell(<div />);

    expect(html).toContain("app-shell__content-region");
  });

  it("renders its children inside the content outlet", () => {
    const html = renderShell(<p>shell-content-outlet-probe</p>);

    expect(html).toContain("shell-content-outlet-probe");
  });

  it("places the navigation region before the content region in document order", () => {
    const html = renderShell(<div />);

    const navIndex = html.indexOf("app-shell__navigation-region");
    const contentIndex = html.indexOf("app-shell__content-region");

    expect(navIndex).toBeGreaterThan(-1);
    expect(contentIndex).toBeGreaterThan(-1);
    expect(navIndex).toBeLessThan(contentIndex);
  });

  it("wraps the navigation and content regions in their own row below the notification slot", () => {
    const html = renderShell(<div />);

    expect(html).toContain("app-shell__regions");
  });

  it("renders no restart-exhausted alert when the sidecar has not reported exhaustion", () => {
    const html = renderShell(<div />);

    expect(html).not.toContain('role="alert"');
    expect(html).not.toContain("restart-exhausted-notification");
  });

  it("renders no command palette dialog by default (closed until Ctrl+K)", () => {
    const html = renderShell(<div />);

    expect(html).not.toContain('role="dialog"');
    expect(html).not.toContain("command-palette-backdrop");
  });
});
