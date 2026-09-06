/**
 * App integration test (composition-root smoke test).
 *
 * Extended for Phase 4G-2 Part 2: `App.tsx` now wraps everything in
 * `HashRouter`, which touches `window`/`document` — unavailable under
 * this project's default (node) test environment (see
 * `navigation.live.test.tsx`'s header for the full explanation of
 * why one file in this checkpoint genuinely needs jsdom instead).
 * Rather than moving this whole file to jsdom too, `HashRouter` is
 * mocked to `MemoryRouter` (initialized at `/dashboard`, sidestepping
 * the "/" -> "/dashboard" redirect, which itself needs a live DOM to
 * resolve — also covered in `navigation.live.test.tsx`) purely so
 * `react-dom/server`'s `renderToStaticMarkup` keeps working here, per
 * Part 1's original approach. Real router behavior (redirects,
 * clicking, active state) is verified for real in
 * `navigation.live.test.tsx`; this file's job stays narrow — prove
 * the composition root still renders without throwing.
 *
 * `useEffect` (which owns the sidecar lifecycle start/stop) does not
 * run under `renderToStaticMarkup`, so this intentionally does not
 * exercise `startSidecarLifecycle` — that ownership chain is already
 * covered directly by `sidecarLifecycle.test.ts`.
 */

import { renderToStaticMarkup } from "react-dom/server";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    HashRouter: ({ children }: { children: ReactNode }) => (
      <actual.MemoryRouter initialEntries={["/dashboard"]}>
        {children}
      </actual.MemoryRouter>
    ),
  };
});

const { App } = await import("./App");

describe("App", () => {
  it("mounts without throwing with the AppShell and router composed in", () => {
    expect(() => renderToStaticMarkup(<App />)).not.toThrow();
  });

  it("renders the shell's navigation and content regions", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain("app-shell__navigation-region");
    expect(html).toContain("app-shell__content-region");
  });

  it("renders the routed page inside the shell's content region", () => {
    const html = renderToStaticMarkup(<App />);

    // Updated for Phase 4G-2 Part 3: the "/dashboard" route (this
    // test's fixed MemoryRouter entry, see the mock above) now
    // renders the real DashboardPage instead of the Part 2
    // RoutePlaceholder.
    expect(html).toContain('aria-label="Dashboard page"');
    expect(html).toContain(">Dashboard<");
  });

  it("introduces no competing <main> landmark from AppShell/ContentRegion — the routed page's own <main> is the only one", () => {
    // Phase 4G-2 Part 4-2, §3: PageLayout owns the page's <main>
    // landmark; AppShell and ContentRegion must never add a second
    // one. pages.test.tsx already proves this for each page in
    // isolation; this proves it holds once actually mounted inside
    // the full shell too.
    const html = renderToStaticMarkup(<App />);

    expect((html.match(/<main/g) ?? []).length).toBe(1);
  });

  it("renders the sidebar's navigation items alongside the routed content", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain("nav-sidebar");
    expect(html).toContain("SOC-IQ");
  });
});
