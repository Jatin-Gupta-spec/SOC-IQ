// @vitest-environment jsdom
/**
 * `InvestigationHeaderCard` tests — Phase 4J-6 Part 1B.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * this checkpoint already uses (`InvestigationWorkspacePage.test.tsx`,
 * `AnalyzePage.execution.test.tsx`) — no `@testing-library/react` is
 * introduced. Builds `InvestigationWorkspaceData` fixtures directly
 * (the component's actual prop type) rather than going through
 * `normalizeInvestigationWorkspace()`, since normalization itself is
 * already covered by `investigationWorkspaceModel.test.ts`.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvestigationHeaderCard } from "./InvestigationHeaderCard";
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
    root.render(<InvestigationHeaderCard data={data} />);
  });
}

describe("InvestigationHeaderCard", () => {
  describe("identity", () => {
    it("renders the real investigation ID and report name", () => {
      render(makeData({ investigationId: 123, reportName: "report4.txt" }));

      expect(container.textContent).toContain("Investigation #123");
      expect(container.textContent).toContain("report4.txt");
    });

    it("never hardcodes an investigation ID -- a different real ID renders differently", () => {
      render(makeData({ investigationId: 999 }));

      expect(container.textContent).toContain("Investigation #999");
      expect(container.textContent).not.toContain("Investigation #7");
      expect(container.textContent).not.toContain("Investigation #123");
    });

    it("handles a null investigation ID honestly instead of fabricating a number", () => {
      render(makeData({ investigationId: null }));

      expect(container.textContent).toContain("Investigation ID unavailable");
      expect(container.textContent).not.toMatch(/Investigation #\d/);
    });
  });

  describe("risk / severity", () => {
    it("renders the real severity and real risk score when scored", () => {
      render(makeData({ severity: "critical", riskScore: 97 }));

      expect(container.textContent).toContain("critical");
      expect(container.textContent).toContain("97");
    });

    it("keeps NOT_SCORED distinct from a real severity value", () => {
      render(makeData({ severity: "NOT_SCORED", riskScore: 0, confidence: 0 }));

      expect(container.textContent).toContain("Not scored");
      expect(container.textContent).not.toContain("NOT_SCORED");
    });

    it("does not convert a NOT_SCORED investigation's placeholder risk score into a real-looking 0", () => {
      render(makeData({ severity: "NOT_SCORED", riskScore: 0, confidence: 0 }));

      // The risk stat renders "Not scored", not a bare "0" standing in
      // for a real score.
      const statValues = Array.from(container.querySelectorAll(".investigation-header-card__stat-value"));
      const riskValue = statValues.find((el) => el.textContent === "Not scored");
      expect(riskValue).toBeDefined();
    });

    it("displays the real risk score as-is without recalculating it", () => {
      render(makeData({ severity: "medium", riskScore: 55 }));

      expect(container.textContent).toContain("55");
    });
  });

  describe("analysis status", () => {
    it("renders the real analysis status", () => {
      render(makeData({ status: "completed" }));

      expect(container.textContent).toContain("completed");
    });

    it("presents an unrecognized status honestly rather than guessing", () => {
      render(makeData({ status: "archived" }));

      expect(container.textContent).toContain("archived");
    });
  });

  describe("confidence", () => {
    it("formats a real confidence fraction as a percentage", () => {
      render(makeData({ severity: "high", confidence: 0.82 }));

      expect(container.textContent).toContain("82%");
    });

    it("does not fabricate a confidence percentage when not scored", () => {
      render(makeData({ severity: "NOT_SCORED", riskScore: 0, confidence: 0 }));

      expect(container.textContent).not.toContain("0%");
    });
  });

  describe("partial data", () => {
    it("still renders identity and status when IOC/TI data is unavailable", () => {
      render(makeData({ iocsByType: null, rawThreatIntelligence: null }));

      expect(container.textContent).toContain("Investigation #7");
      expect(container.textContent).toContain("malware_report.txt");
    });
  });

  describe("accessibility", () => {
    it("uses a real heading for the investigation identity", () => {
      render(makeData({}));

      const heading = container.querySelector("h2");
      expect(heading).not.toBeNull();
      expect(heading?.textContent).toBe("Investigation #7");
    });

    it("labels each status stat rather than relying on layout alone", () => {
      render(makeData({}));

      const labels = Array.from(container.querySelectorAll(".investigation-header-card__stat-label")).map(
        (el) => el.textContent,
      );
      expect(labels).toEqual(["Analysis status", "Severity", "Risk", "Confidence"]);
    });
  });
});
