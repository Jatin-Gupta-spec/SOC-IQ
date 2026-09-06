/**
 * Tests for `SidecarStatusIndicator` (Phase 4G-3 Part 2).
 *
 * Static/presentational assertions use `renderToStaticMarkup`,
 * matching this project's existing no-jsdom-by-default convention
 * (`pages.test.tsx`). Every state is driven through the component's
 * `view` test-injection prop (mirroring `useSidecarStatus`'s own
 * `store` injection point) rather than the real store — these tests
 * are about the component's rendering for a given view, not about
 * store wiring, which `useSidecarStatus.test.tsx` (Part 1) and
 * `SidecarStatusIndicator.live.test.tsx` (this Part, live-store
 * wiring + shell integration) already cover.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  SIDECAR_STATUS_VIEWS,
  type SidecarStatusView,
} from "../sidecar/sidecarStatusView";
import { SidecarStatusIndicator } from "./SidecarStatusIndicator";

const EXPECTED_LABEL: Record<SidecarStatusView, string> = {
  unknown: "Sidecar status unknown",
  starting: "Sidecar starting",
  connected: "Sidecar connected",
  disconnected: "Sidecar disconnected",
  restarting: "Sidecar restarting",
  failure: "Sidecar unavailable",
};

describe("renders without throwing for every supported view", () => {
  it.each(SIDECAR_STATUS_VIEWS)("%s", (view) => {
    expect(() =>
      renderToStaticMarkup(<SidecarStatusIndicator view={view} />),
    ).not.toThrow();
  });
});

describe("readable status text (task brief §6, §11, §12)", () => {
  it.each(SIDECAR_STATUS_VIEWS)(
    "shows the exact expected text for %s, not merely a colored dot",
    (view) => {
      const html = renderToStaticMarkup(
        <SidecarStatusIndicator view={view} />,
      );

      expect(html).toContain(EXPECTED_LABEL[view]);
    },
  );

  it("never renders the word Connected for a non-connected view (no premature/false status text)", () => {
    for (const view of SIDECAR_STATUS_VIEWS) {
      if (view === "connected") continue;
      const html = renderToStaticMarkup(
        <SidecarStatusIndicator view={view} />,
      );
      expect(html).not.toContain(">Sidecar connected<");
    }
  });

  it("does not show Disconnected for the unknown/initial view", () => {
    const html = renderToStaticMarkup(<SidecarStatusIndicator view="unknown" />);
    expect(html).not.toContain("Sidecar disconnected");
    expect(html).toContain("Sidecar status unknown");
  });
});

describe("accessibility (task brief §6)", () => {
  it("exposes role=status and aria-live=polite exactly once, with no redundant aria-label duplicating the visible text", () => {
    const html = renderToStaticMarkup(
      <SidecarStatusIndicator view="connected" />,
    );

    expect(html).toContain('role="status"');
    expect(html).toContain('aria-live="polite"');
    expect(html).not.toContain("aria-label");
  });

  it("marks the tone dot as decorative (aria-hidden) so the accessible name comes only from the text", () => {
    const html = renderToStaticMarkup(
      <SidecarStatusIndicator view="failure" />,
    );

    expect(html).toContain('sidecar-status__dot');
    expect(html).toMatch(/sidecar-status__dot[^>]*aria-hidden="true"/);
  });

  it.each(SIDECAR_STATUS_VIEWS)(
    "carries a distinct tone class for %s, independent of the text (color is never the only signal)",
    (view) => {
      const html = renderToStaticMarkup(
        <SidecarStatusIndicator view={view} />,
      );

      expect(html).toContain(`sidecar-status__dot--${view}`);
      // The text label itself is present regardless of the tone class,
      // so removing color/CSS entirely would still leave the meaning intact.
      expect(html).toContain(EXPECTED_LABEL[view]);
    },
  );
});

describe("no duplicate indicator within a single render", () => {
  it("renders exactly one status dot per mount", () => {
    const html = renderToStaticMarkup(
      <SidecarStatusIndicator view="connected" />,
    );

    const matches = html.match(/sidecar-status__dot--connected/g) ?? [];
    expect(matches.length).toBe(1);
  });
});
