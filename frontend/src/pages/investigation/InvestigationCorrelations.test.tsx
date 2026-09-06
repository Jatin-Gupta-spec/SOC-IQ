// @vitest-environment jsdom
/**
 * `InvestigationCorrelations` tests — Phase 4J-6 Part 4A.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationOverviewThreatIntel.test.tsx`) -- no
 * `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { CorrelationItem, InvestigationCorrelations } from "./InvestigationCorrelations";
import type { InvestigationCorrelation } from "./investigationCorrelationsModel";
import type { InvestigationWorkspaceData } from "./investigationWorkspaceModel";

const BASE_DATA: InvestigationWorkspaceData = {
  investigationId: 7,
  reportName: "malware_report.txt",
  analyzedAt: "2026-08-26T00:00:00",
  status: "completed",
  riskScore: 82,
  severity: "high",
  confidence: 0.9,
  iocsByType: {},
  rawThreatIntelligence: {},
  correlations: [],
};

function makeData(overrides: Partial<InvestigationWorkspaceData>): InvestigationWorkspaceData {
  return { ...BASE_DATA, ...overrides };
}

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

function render(data: InvestigationWorkspaceData): void {
  act(() => {
    root = createRoot(container);
    root.render(<InvestigationCorrelations data={data} />);
  });
}

describe("InvestigationCorrelations", () => {
  describe("unavailable", () => {
    it("shows an honest unavailable state when both IOC and TI data failed to load", () => {
      render(makeData({ iocsByType: null, rawThreatIntelligence: null }));

      expect(container.textContent).toContain("Correlation data unavailable");
    });

    it("never converts unavailable data into an empty success message", () => {
      render(makeData({ iocsByType: null, rawThreatIntelligence: null }));

      expect(container.textContent).not.toContain("No explicit correlations found");
    });
  });

  describe("empty", () => {
    it("shows an honest empty state, distinct from unavailable, when there is real data but no relationship", () => {
      render(
        makeData({
          iocsByType: {
            ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
            domains: [{ value: "evil.example", tiState: "enriched", typedVerdict: null }],
          },
          rawThreatIntelligence: { "1.2.3.4": { vendor: "vt" } },
        }),
      );

      expect(container.textContent).toContain("No explicit correlations found");
      expect(container.textContent).not.toContain("unavailable");
    });

    it("never implies the investigation is clean or free of threats in the empty state", () => {
      render(makeData({}));

      expect(container.textContent).not.toContain("No threats found");
      expect(container.textContent).not.toContain("Investigation is clean");
    });

    it("does not fabricate a relationship from two IOCs of the same type", () => {
      render(
        makeData({
          iocsByType: {
            ipv4: [
              { value: "1.1.1.1", tiState: "enriched", typedVerdict: null },
              { value: "2.2.2.2", tiState: "enriched", typedVerdict: null },
            ],
          },
        }),
      );

      expect(container.querySelectorAll(".investigation-correlations__item")).toHaveLength(0);
      expect(container.textContent).toContain("No explicit correlations found");
    });
  });

  describe("available", () => {
    it("renders a real, non-fabricated correlation end to end when data.correlations is populated (Phase 4J-6)", () => {
      render(
        makeData({
          iocsByType: {
            domains: [{ value: "evil.com", tiState: null, typedVerdict: null }],
            urls: [{ value: "https://evil.com/payload.exe", tiState: null, typedVerdict: null }],
          },
          correlations: [
            {
              relationshipType: "domain_url_host",
              source: "evil.com",
              target: "https://evil.com/payload.exe",
              context: "URL host matches extracted domain 'evil.com' exactly.",
            },
          ],
        }),
      );

      expect(container.querySelectorAll(".investigation-correlations__item")).toHaveLength(1);
      expect(container.textContent).toContain("domain_url_host");
      expect(container.textContent).toContain("evil.com");
      expect(container.textContent).toContain("https://evil.com/payload.exe");
      expect(container.textContent).not.toContain("No explicit correlations found");
      expect(container.textContent).not.toContain("Correlation data unavailable");

      const toggle = container.querySelector<HTMLButtonElement>(".investigation-correlations__toggle");
      expect(toggle).not.toBeNull();
      act(() => {
        toggle?.click();
      });
      expect(container.textContent).toContain("URL host matches extracted domain 'evil.com' exactly.");
    });
  });

  describe("partial investigation", () => {
    it("shows an honest correlations state without fabricating one when IOC data is unavailable", () => {
      render(makeData({ iocsByType: null, rawThreatIntelligence: {} }));

      expect(container.querySelectorAll(".investigation-correlations__item")).toHaveLength(0);
      expect(container.textContent).not.toContain("Correlation data unavailable");
    });

    it("shows an honest correlations state without fabricating one when TI data is unavailable", () => {
      render(makeData({ iocsByType: { ipv4: [{ value: "1.2.3.4", tiState: null, typedVerdict: null }] }, rawThreatIntelligence: null }));

      expect(container.querySelectorAll(".investigation-correlations__item")).toHaveLength(0);
      expect(container.textContent).not.toContain("Correlation data unavailable");
    });
  });

  describe("interaction", () => {
    // These construct an `InvestigationCorrelation` directly -- a
    // type-correct fixture for the presentational `CorrelationItem`
    // component, not a fabricated investigation. This is not the
    // "manufactured test fixture" the task brief warns against (§19):
    // that warning is about forcing `deriveInvestigationCorrelations`
    // into its `"available"` branch through fake investigation data,
    // which would misrepresent what today's real pipeline can
    // produce. Unit-testing this component's own disclosure behavior
    // against its own prop type is ordinary component testing.
    const WITH_CONTEXT: InvestigationCorrelation = {
      relationshipType: "linked",
      source: "1.2.3.4",
      target: "evil.example",
      context: "Both values were reported together by the same relationship field.",
    };

    const WITHOUT_CONTEXT: InvestigationCorrelation = {
      relationshipType: "linked",
      source: "1.2.3.4",
      target: "evil.example",
    };

    function renderItem(correlation: InvestigationCorrelation): void {
      act(() => {
        root = createRoot(container);
        root.render(
          <ul>
            <CorrelationItem correlation={correlation} index={0} />
          </ul>,
        );
      });
    }

    it("does not render a toggle when there is no context to disclose", () => {
      renderItem(WITHOUT_CONTEXT);

      expect(container.querySelector(".investigation-correlations__toggle")).toBeNull();
    });

    it("renders a collapsed, keyboard-accessible toggle when context is present", () => {
      renderItem(WITH_CONTEXT);

      const toggle = container.querySelector(".investigation-correlations__toggle");
      expect(toggle).not.toBeNull();
      expect(toggle?.tagName).toBe("BUTTON");
      expect(toggle?.getAttribute("aria-expanded")).toBe("false");
    });

    it("hides the context content while collapsed", () => {
      renderItem(WITH_CONTEXT);

      expect(container.textContent).not.toContain("Both values were reported together");
    });

    it("reveals the context and flips aria-expanded when activated", () => {
      renderItem(WITH_CONTEXT);

      const toggle = container.querySelector<HTMLButtonElement>(".investigation-correlations__toggle");
      act(() => {
        toggle?.click();
      });

      expect(toggle?.getAttribute("aria-expanded")).toBe("true");
      expect(container.textContent).toContain("Both values were reported together");
      expect(toggle?.getAttribute("aria-controls")).toBe(
        container.querySelector(".investigation-correlations__context")?.id,
      );
    });

    it("collapses the context again when activated a second time", () => {
      renderItem(WITH_CONTEXT);

      const toggle = container.querySelector<HTMLButtonElement>(".investigation-correlations__toggle");
      act(() => {
        toggle?.click();
      });
      act(() => {
        toggle?.click();
      });

      expect(toggle?.getAttribute("aria-expanded")).toBe("false");
      expect(container.textContent).not.toContain("Both values were reported together");
    });

    it("has an accessible name describing the action, not just an icon or color", () => {
      renderItem(WITH_CONTEXT);

      const toggle = container.querySelector(".investigation-correlations__toggle");
      expect(toggle?.textContent).toBe("View context");
    });
  });

  describe("cross-investigation state leak (MAX-21B-4C-F1)", () => {
    // These deliberately reuse the SAME `root`/mounted component
    // instance across an investigation switch (via `root.render(...)`
    // again, not a fresh `createRoot()`) -- the production defect only
    // reproduces when `InvestigationCorrelations`/`CorrelationItem` are
    // reused across the switch, matching how `WorkspaceTabs` keeps this
    // component mounted in the same tree position across investigations
    // in production. Remounting via a new root each time would make
    // this pass regardless of whether the leak was actually fixed.
    const CORRELATION_A: InvestigationCorrelation = {
      relationshipType: "linked",
      source: "1.1.1.1",
      target: "a.example",
      context: "Investigation A's own explicit relationship context.",
    };

    const CORRELATION_B: InvestigationCorrelation = {
      relationshipType: "linked",
      source: "2.2.2.2",
      target: "b.example",
      context: "Investigation B's own explicit relationship context.",
    };

    function rerenderSameInstance(data: InvestigationWorkspaceData): void {
      act(() => {
        root.render(<InvestigationCorrelations data={data} />);
      });
    }

    it("does not carry investigation A's expanded disclosure into investigation B at the same list position", () => {
      act(() => {
        root = createRoot(container);
        root.render(<InvestigationCorrelations data={makeData({ investigationId: 1, correlations: [CORRELATION_A] })} />);
      });

      const toggleA = container.querySelector<HTMLButtonElement>(".investigation-correlations__toggle");
      expect(toggleA?.getAttribute("aria-expanded")).toBe("false");
      act(() => {
        toggleA?.click();
      });
      expect(toggleA?.getAttribute("aria-expanded")).toBe("true");
      expect(container.textContent).toContain("Investigation A's own explicit relationship context.");

      rerenderSameInstance(makeData({ investigationId: 2, correlations: [CORRELATION_B] }));

      const toggleB = container.querySelector<HTMLButtonElement>(".investigation-correlations__toggle");
      expect(toggleB).not.toBeNull();
      // Without the fix, React reuses the same `CorrelationItem`
      // instance (same array index) across the switch and its local
      // `expanded` state survives, so B's item would already render
      // expanded and its context would already be visible here.
      expect(toggleB?.getAttribute("aria-expanded")).toBe("false");
      expect(container.textContent).not.toContain("Investigation B's own explicit relationship context.");
      expect(container.textContent).toContain("2.2.2.2");
    });

    it("still allows investigation B's own correlation to be expanded normally after the reset", () => {
      act(() => {
        root = createRoot(container);
        root.render(<InvestigationCorrelations data={makeData({ investigationId: 1, correlations: [CORRELATION_A] })} />);
      });
      act(() => {
        container.querySelector<HTMLButtonElement>(".investigation-correlations__toggle")?.click();
      });

      rerenderSameInstance(makeData({ investigationId: 2, correlations: [CORRELATION_B] }));

      const toggleB = container.querySelector<HTMLButtonElement>(".investigation-correlations__toggle");
      act(() => {
        toggleB?.click();
      });

      expect(toggleB?.getAttribute("aria-expanded")).toBe("true");
      expect(container.textContent).toContain("Investigation B's own explicit relationship context.");
    });
  });

  describe("accessibility", () => {
    it("uses a real heading for the card", () => {
      render(makeData({}));

      const heading = container.querySelector("h2");
      expect(heading?.textContent).toBe("Correlations");
    });

    it("carries status as real text, not color alone", () => {
      render(makeData({ iocsByType: null, rawThreatIntelligence: null }));

      const note = container.querySelector('[role="note"]');
      expect(note?.textContent).toContain("Correlation data unavailable");
    });
  });
});
