// @vitest-environment jsdom
/**
 * `InvestigationOverviewThreatIntel` tests — Phase 4J-6 Part 1D.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationOverviewSummary.test.tsx`) -- no
 * `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvestigationOverviewThreatIntel } from "./InvestigationOverviewThreatIntel";
import type { InvestigationWorkspaceData, InvestigationWorkspaceIndicator } from "./investigationWorkspaceModel";
import type { TiState } from "../../shared/api/types";

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

function indicator(value: string, tiState: TiState | null): InvestigationWorkspaceIndicator {
  return { value, tiState, typedVerdict: null };
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
    root.render(<InvestigationOverviewThreatIntel data={data} />);
  });
}

function rowCount(label: string): string | null {
  const rows = Array.from(container.querySelectorAll(".investigation-overview-ti__row"));
  const row = rows.find((el) => el.textContent?.includes(label));
  return row?.querySelector(".investigation-overview-ti__row-count")?.textContent ?? null;
}

describe("InvestigationOverviewThreatIntel", () => {
  it("shows an honest unavailable state when the TI fetch failed", () => {
    render(makeData({ rawThreatIntelligence: null, iocsByType: { ipv4: [indicator("1.2.3.4", "enriched")] } }));

    expect(container.textContent).toContain("Threat Intelligence data unavailable");
  });

  it("never converts a TI fetch failure into a 'Not enriched' state", () => {
    render(makeData({ rawThreatIntelligence: null }));

    expect(container.textContent).not.toContain("Not enriched");
  });

  it("shows an honest note when TI succeeded but IOC data (needed for the breakdown) failed", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: null }));

    expect(container.textContent).toContain("Threat Intelligence data was received");
    expect(container.textContent).toContain("IOC data for this investigation failed to load");
  });

  it("shows an honest empty state, distinct from unavailable, when there are no indicators to enrich", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: {} }));

    expect(container.textContent).toContain("No indicators to enrich");
    expect(container.textContent).not.toContain("unavailable");
  });

  it("distinguishes every canonical TI state by real count", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: {
          ipv4: [
            indicator("1.1.1.1", "enriched"),
            indicator("2.2.2.2", "enriched"),
            indicator("3.3.3.3", "no_api_key"),
          ],
          domains: [indicator("evil.example", "provider_error")],
          urls: [indicator("http://bad.example", "incomplete_check")],
          cves: [indicator("CVE-2024-0001", "unsupported_type")],
          emails: [indicator("a@b.com", "not_enriched")],
        },
      }),
    );

    expect(rowCount("Enriched")).toBe("2");
    expect(rowCount("No API key")).toBe("1");
    expect(rowCount("Provider error")).toBe("1");
    expect(rowCount("Incomplete check")).toBe("1");
    expect(rowCount("Unsupported type")).toBe("1");
    expect(rowCount("Not enriched")).toBe("1");
  });

  it("keeps a real provider error visible and distinguishable, never disguised as success", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: { ipv4: [indicator("1.1.1.1", "provider_error")] },
      }),
    );

    const badge = Array.from(container.querySelectorAll(".status-badge")).find(
      (el) => el.textContent === "Provider error",
    );
    expect(badge?.className).toContain("status-badge--error");
  });

  it("reports indicators with no TI classification separately from 'not_enriched'", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: { ipv4: [indicator("1.1.1.1", null)] },
      }),
    );

    expect(rowCount("Not yet classified")).toBe("1");
    expect(container.textContent).not.toContain("Not enriched");
  });

  describe("accessibility", () => {
    it("uses a real heading for the card", () => {
      render(makeData({}));

      const heading = Array.from(container.querySelectorAll("h2")).find(
        (el) => el.textContent === "Threat Intelligence Summary",
      );
      expect(heading).toBeDefined();
    });
  });
});
