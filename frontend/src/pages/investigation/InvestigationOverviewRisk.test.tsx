// @vitest-environment jsdom
/**
 * `InvestigationOverviewRisk` tests — Phase 4J-6 Part 1C.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationHeaderCard.test.tsx`, `InvestigationWorkspacePage.test.tsx`)
 * -- no `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvestigationOverviewRisk } from "./InvestigationOverviewRisk";
import type {
  InvestigationWorkspaceData,
  InvestigationWorkspaceRiskExplanation,
} from "./investigationWorkspaceModel";

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
    root.render(<InvestigationOverviewRisk data={data} />);
  });
}

describe("InvestigationOverviewRisk", () => {
  it("renders the real risk score and real severity when scored", () => {
    render(makeData({ severity: "critical", riskScore: 97 }));

    expect(container.textContent).toContain("97");
    expect(container.textContent).toContain("critical");
  });

  it("displays the real risk score as-is without recalculating it", () => {
    render(makeData({ severity: "medium", riskScore: 55 }));

    expect(container.textContent).toContain("55");
  });

  it("keeps NOT_SCORED honest instead of showing a fabricated zero", () => {
    render(makeData({ severity: "NOT_SCORED", riskScore: 0, confidence: 0 }));

    expect(container.textContent).toContain("Not scored");
    expect(container.textContent).toContain("Risk scoring was disabled");
    expect(container.textContent).not.toContain("NOT_SCORED");
  });

  it("does not render a bare '0' risk score for a not-scored investigation", () => {
    render(makeData({ severity: "NOT_SCORED", riskScore: 0, confidence: 0 }));

    const metricValues = Array.from(container.querySelectorAll(".metric-card__value")).map((el) => el.textContent);
    expect(metricValues).not.toContain("0");
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

  describe("accessibility", () => {
    it("uses a real heading for the card", () => {
      render(makeData({}));

      const heading = Array.from(container.querySelectorAll("h2")).find(
        (el) => el.textContent === "Risk Overview",
      );
      expect(heading).toBeDefined();
    });
  });

  describe("risk explanation (PD-08-P2)", () => {
    const RISK_EXPLANATION: InvestigationWorkspaceRiskExplanation = {
      investigationId: 7,
      reportName: "malware_report.txt",
      score: 82,
      severity: "high",
      confidence: 0.9,
      iocScore: 60,
      threatIntelScore: 20,
      cveScore: 2,
      iocCategories: [
        {
          iocType: "ipv4",
          iocTypeTitle: "IP Addresses",
          count: 2,
          weight: 30,
          significance: "high",
          points: 60,
        },
      ],
      iocBreakdownVerified: true,
      threatIntelState: "enriched",
      threatIntelMessage: "Threat intelligence was checked for available indicators.",
      threatIntelShortLabel: "Enriched",
      threatIntelRequested: 2,
      threatIntelSucceeded: 2,
      threatIntelMaliciousHashCount: 0,
      threatIntelSuspiciousHashCount: 0,
      correlationEvaluated: true,
      correlationRelationshipCount: 0,
      correlationSummary: "No explicit correlations were found.",
      engineReasons: [],
      narrative: ["This investigation scored 82 (high) based on 2 IP address indicators."],
      warnings: [],
    };

    it("renders the backend's narrative when the investigation is scored and an explanation is available", () => {
      render(makeData({ severity: "high", riskScore: 82, riskExplanation: RISK_EXPLANATION }));

      expect(container.textContent).toContain(
        "This investigation scored 82 (high) based on 2 IP address indicators.",
      );
    });

    it("renders the IOC category breakdown table with the backend's own values, uncalculated", () => {
      render(makeData({ severity: "high", riskExplanation: RISK_EXPLANATION }));

      const rows = Array.from(container.querySelectorAll("tbody tr"));
      expect(rows).toHaveLength(1);
      expect(rows[0]?.textContent).toContain("IP Addresses");
      expect(rows[0]?.textContent).toContain("60");
    });

    it("does not render an unverified-breakdown caveat when the breakdown is verified", () => {
      render(makeData({ severity: "high", riskExplanation: RISK_EXPLANATION }));

      expect(container.textContent).not.toContain("could not be verified");
    });

    it("renders an honest caveat when the category breakdown could not be verified against the stored score", () => {
      render(
        makeData({
          severity: "high",
          riskExplanation: { ...RISK_EXPLANATION, iocBreakdownVerified: false },
        }),
      );

      expect(container.textContent).toContain("could not be verified");
    });

    it("renders explanation warnings as status badges", () => {
      render(
        makeData({
          severity: "high",
          riskExplanation: {
            ...RISK_EXPLANATION,
            warnings: ["Threat intelligence coverage was incomplete."],
          },
        }),
      );

      expect(container.textContent).toContain("Threat intelligence coverage was incomplete.");
    });

    it("does not render a Risk Explanation section when no explanation has been fetched yet", () => {
      render(makeData({ severity: "high", riskExplanation: null }));

      expect(container.textContent).not.toContain("Why this risk assessment");
    });

    it("does not render a Risk Explanation section for a not-scored investigation, even if one is somehow present", () => {
      render(
        makeData({
          severity: "NOT_SCORED",
          riskScore: 0,
          confidence: 0,
          riskExplanation: RISK_EXPLANATION,
        }),
      );

      expect(container.textContent).not.toContain("Why this risk assessment");
      expect(container.textContent).toContain("Risk scoring was disabled");
    });

    it("never invents a narrative or breakdown when riskExplanation is absent", () => {
      render(makeData({ severity: "high" }));

      expect(container.querySelector(".investigation-overview-risk__breakdown")).toBeNull();
      expect(container.querySelector(".investigation-overview-risk__narrative")).toBeNull();
    });
  });
});
