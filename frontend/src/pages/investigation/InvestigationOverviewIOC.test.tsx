// @vitest-environment jsdom
/**
 * `InvestigationOverviewIOC` tests — Phase 4J-6 Part 1D.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationOverviewSummary.test.tsx`) -- no
 * `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvestigationOverviewIOC } from "./InvestigationOverviewIOC";
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

function indicator(value: string): { value: string; tiState: null; typedVerdict: null } {
  return { value, tiState: null, typedVerdict: null };
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
    root.render(<InvestigationOverviewIOC data={data} />);
  });
}

function metricValue(label: string): string | null {
  const cards = Array.from(container.querySelectorAll(".metric-card"));
  const card = cards.find((el) => el.querySelector(".metric-card__label")?.textContent === label);
  return card?.querySelector(".metric-card__value")?.textContent ?? null;
}

describe("InvestigationOverviewIOC", () => {
  it("renders real counts and total from genuinely available IOC data", () => {
    render(
      makeData({
        iocsByType: {
          ipv4: [indicator("1.2.3.4"), indicator("5.6.7.8")],
          domains: [indicator("evil.example")],
          sha256: [indicator("a".repeat(64))],
        },
      }),
    );

    expect(metricValue("Total")).toBe("4");
    expect(metricValue("IPs")).toBe("2");
    expect(metricValue("Domains")).toBe("1");
    expect(metricValue("Hashes")).toBe("1");
  });

  it("shows an honest empty state, distinct from unavailable, when every category is genuinely empty", () => {
    render(makeData({ iocsByType: {} }));

    expect(container.textContent).toContain("No IOCs found");
    expect(container.textContent).not.toContain("unavailable");
    expect(container.querySelectorAll(".metric-card")).toHaveLength(0);
  });

  it("shows an honest unavailable state, never fabricated zero counts, when IOC data failed", () => {
    render(makeData({ iocsByType: null }));

    expect(container.textContent).toContain("IOC data unavailable");
    expect(container.textContent).not.toContain("No IOCs found");
    expect(container.querySelectorAll(".metric-card")).toHaveLength(0);
  });

  it("treats a type key absent from a real response the same as a real empty array", () => {
    render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

    expect(metricValue("IPs")).toBe("1");
    expect(metricValue("Domains")).toBe("0");
    expect(metricValue("Total")).toBe("1");
  });

  it("draws no distribution segment for a genuinely zero category", () => {
    render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")], domains: [] } }));

    const segments = container.querySelectorAll(".investigation-overview-ioc__bar-segment");
    expect(segments).toHaveLength(1);
  });

  describe("accessibility", () => {
    it("uses a real heading for the card", () => {
      render(makeData({}));

      const heading = Array.from(container.querySelectorAll("h2")).find(
        (el) => el.textContent === "IOC Summary",
      );
      expect(heading).toBeDefined();
    });

    it("hides the purely decorative distribution bar from assistive tech", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      const bar = container.querySelector(".investigation-overview-ioc__bar");
      expect(bar?.getAttribute("aria-hidden")).toBe("true");
    });
  });
});
