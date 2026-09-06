// @vitest-environment jsdom
/**
 * `InvestigationOverviewSummary` tests — Phase 4J-6 Part 1C.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationHeaderCard.test.tsx`, `InvestigationWorkspacePage.test.tsx`)
 * -- no `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvestigationOverviewSummary } from "./InvestigationOverviewSummary";
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
    root.render(<InvestigationOverviewSummary data={data} />);
  });
}

function metricValue(label: string): string | null {
  const cards = Array.from(container.querySelectorAll(".metric-card"));
  const card = cards.find((el) => el.querySelector(".metric-card__label")?.textContent === label);
  return card?.querySelector(".metric-card__value")?.textContent ?? null;
}

function indicator(value: string): { value: string; tiState: null; typedVerdict: null } {
  return { value, tiState: null, typedVerdict: null };
}

describe("InvestigationOverviewSummary", () => {
  it("renders genuine available IOC counts grouped by real type", () => {
    render(
      makeData({
        iocsByType: {
          ipv4: [indicator("1.2.3.4"), indicator("5.6.7.8")],
          domains: [indicator("evil.example")],
          sha256: [indicator("a".repeat(64))],
          md5: [indicator("b".repeat(32))],
        },
      }),
    );

    expect(metricValue("IPs")).toBe("2");
    expect(metricValue("Domains")).toBe("1");
    expect(metricValue("Hashes")).toBe("2");
    expect(metricValue("Total IOCs")).toBe("5");
  });

  it("keeps genuine zero counts as real zeroes, not hidden or converted", () => {
    render(makeData({ iocsByType: {} }));

    expect(metricValue("Total IOCs")).toBe("0");
    expect(metricValue("IPs")).toBe("0");
    expect(metricValue("CVEs")).toBe("0");
  });

  it("treats a type key absent from a real response the same as a real empty array", () => {
    render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

    expect(metricValue("IPs")).toBe("1");
    // "domains" was never a key in this response at all -- still a
    // real, honest 0 (no indicators of that type in this response),
    // not omitted or fabricated as something else.
    expect(metricValue("Domains")).toBe("0");
    expect(metricValue("Total IOCs")).toBe("1");
  });

  it("shows an honest unavailable state instead of fabricating zero counts when IOC data failed", () => {
    render(makeData({ iocsByType: null }));

    expect(container.textContent).toContain("IOC data is unavailable");
    expect(metricValue("Total IOCs")).toBeNull();
    expect(container.querySelectorAll(".metric-card")).toHaveLength(0);
  });

  describe("accessibility", () => {
    it("uses a real heading for the card", () => {
      render(makeData({}));

      const heading = Array.from(container.querySelectorAll("h2")).find(
        (el) => el.textContent === "Investigation Summary",
      );
      expect(heading).toBeDefined();
    });
  });
});
