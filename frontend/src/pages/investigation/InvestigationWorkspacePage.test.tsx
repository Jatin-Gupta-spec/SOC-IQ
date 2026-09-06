// @vitest-environment jsdom
/**
 * `InvestigationWorkspacePage` tests — Phase 4J-6 Part 1A.
 *
 * `useInvestigation` (Phase 4J-4) is mocked at its own module boundary
 * so each `InvestigationLoadState` can be driven directly and
 * deterministically -- this file tests the workspace page's own
 * rendering/state-handling logic, not the fetch hook's behavior
 * (already covered by `useInvestigation.test.tsx`) or the
 * normalization logic (already covered by
 * `investigationWorkspaceModel.test.ts`). Mirrors the established
 * `vi.mock` + `act`/`createRoot` conventions this checkpoint already
 * uses (`AnalyzePage.execution.test.tsx`, `useInvestigation.test.tsx`)
 * -- no `@testing-library/react` is introduced.
 */

import { act, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";

const useInvestigationMock = vi.fn();

vi.mock("./useInvestigation", () => ({
  useInvestigation: (...args: unknown[]) => useInvestigationMock(...args),
}));

import { InvestigationWorkspacePage } from "./InvestigationWorkspacePage";
import type { UseInvestigationResult } from "./useInvestigation";
import type { GetInvestigationResult, TimelineEvent } from "../../shared/api/types";

const INVESTIGATION: GetInvestigationResult = {
  investigation_id: 7,
  report_name: "report.txt",
  risk_score: 42,
  severity: "high",
  confidence: 0.9,
  status: "complete",
  analyzed_at: "2026-08-26T00:00:00",
  correlations: [],
};

const TIMELINE_EVENT: TimelineEvent = {
  event_id: "evt-1",
  investigation_id: 7,
  event_type: "analysis_started",
  timestamp: "2026-08-26T00:00:00",
  source: "analyzer",
  summary: "Analysis started",
  metadata: {},
  semantics: "lifecycle",
};

function makeResult(overrides: Partial<UseInvestigationResult>): UseInvestigationResult {
  return {
    state: "loading",
    data: {
      investigation: null,
      iocs: null,
      threatIntelligence: null,
      timeline: null,
      riskExplanation: null,
    },
    investigationError: null,
    iocsError: null,
    threatIntelligenceError: null,
    timelineError: null,
    riskExplanationError: null,
    retry: vi.fn(),
    ...overrides,
  };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  useInvestigationMock.mockReset();
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(): void {
  act(() => {
    root = createRoot(container);
    root.render(
      <MemoryRouter initialEntries={["/investigations/7"]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationWorkspacePage investigationId={7} />} />
          <Route path="/investigations" element={<div data-testid="investigations-stub">Investigations</div>} />
        </Routes>
      </MemoryRouter>,
    );
  });
}

/** Exposes the router's current `pathname + search` into the DOM (via
 * `data-testid="location-probe"`) so MAX7-F-02 tests can assert on
 * the real URL a `setSearchParams()` call produces, the same way a
 * reload/shared-link/back-button scenario would observe it -- without
 * reaching into `MemoryRouter`'s internal history object. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <div data-testid="location-probe">{`${location.pathname}${location.search}`}</div>;
}

function renderWithLocationProbe(initialEntries: readonly string[]): void {
  act(() => {
    root = createRoot(container);
    root.render(
      <MemoryRouter initialEntries={[...initialEntries]}>
        <LocationProbe />
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationWorkspacePage investigationId={7} />} />
          <Route path="/investigations" element={<div data-testid="investigations-stub">Investigations</div>} />
        </Routes>
      </MemoryRouter>,
    );
  });
}

function locationProbeText(): string {
  return container.querySelector('[data-testid="location-probe"]')!.textContent ?? "";
}

describe("InvestigationWorkspacePage", () => {
  describe("loading", () => {
    it("renders a loading state with no fake investigation information", () => {
      useInvestigationMock.mockReturnValue(makeResult({ state: "loading" }));
      render();

      expect(container.textContent).toContain("Loading investigation");
      // No fake risk score / IOC counts / investigation ID leak into the
      // loading shell.
      expect(container.textContent).not.toContain("42");
      expect(container.textContent).not.toContain("report.txt");
    });
  });

  describe("not found", () => {
    it("renders a dedicated not-found state with the ID and a back action", () => {
      useInvestigationMock.mockReturnValue(makeResult({ state: "notFound" }));
      render();

      expect(container.textContent).toContain("Investigation not found");
      expect(container.textContent).toContain("Investigation ID: 7");

      const backButton = Array.from(container.querySelectorAll("button")).find(
        (button) => button.textContent === "Back to Investigations",
      );
      expect(backButton).toBeDefined();
    });

    it("navigates to /investigations from the back action", () => {
      useInvestigationMock.mockReturnValue(makeResult({ state: "notFound" }));
      render();

      const backButton = Array.from(container.querySelectorAll("button")).find(
        (button) => button.textContent === "Back to Investigations",
      )!;

      act(() => {
        backButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      expect(container.querySelector('[data-testid="investigations-stub"]')).not.toBeNull();
    });

    it("does not treat not-found as an empty/zero-data investigation", () => {
      useInvestigationMock.mockReturnValue(makeResult({ state: "notFound" }));
      render();

      expect(container.textContent).not.toContain("0 IOCs");
      expect(container.textContent).not.toContain("No threat intelligence");
    });
  });

  describe("error", () => {
    it("renders the real error message, a retry action, and a back action", () => {
      const retry = vi.fn();
      useInvestigationMock.mockReturnValue(
        makeResult({ state: "error", investigationError: new Error("boom: sidecar unreachable"), retry }),
      );
      render();

      expect(container.textContent).toContain("boom: sidecar unreachable");

      const retryButton = Array.from(container.querySelectorAll("button")).find(
        (button) => button.textContent === "Retry",
      )!;
      expect(retryButton).toBeDefined();

      act(() => {
        retryButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
      expect(retry).toHaveBeenCalledTimes(1);

      const backButton = Array.from(container.querySelectorAll("button")).find(
        (button) => button.textContent === "Back to Investigations",
      );
      expect(backButton).toBeDefined();
    });

    it("falls back to a generic message when no error message is available", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({ state: "error", investigationError: "not an Error instance" }),
      );
      render();

      expect(container.textContent).toContain("An unknown error occurred");
    });
  });

  describe("partial", () => {
    it("keeps the workspace mounted and distinguishes IOC vs TI failures without fabricating empty data", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: null, threatIntelligence: null },
          iocsError: new Error("iocs failed"),
          threatIntelligenceError: new Error("ti failed"),
        }),
      );
      render();

      expect(container.textContent).toContain("Investigation #7");
      expect(container.textContent).toContain("report.txt");
      expect(container.textContent).toContain("IOC data unavailable");
      expect(container.textContent).toContain("Threat Intelligence data unavailable");

      // The header card itself must still render even though IOC/TI
      // data is unavailable (task brief §10).
      expect(container.querySelector(".investigation-header-card")).not.toBeNull();
    });

    it("only shows a warning for the section that actually failed", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: null, threatIntelligence: { raw: {}, states: {} } },
          iocsError: new Error("iocs failed"),
          threatIntelligenceError: null,
        }),
      );
      render();

      expect(container.textContent).toContain("IOC data unavailable");
      expect(container.textContent).not.toContain("Threat Intelligence data unavailable");
    });

    it("shows the Overview's honest IOC-unavailable state, not a fabricated zero, when IOCs failed", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: null, threatIntelligence: { raw: {}, states: {} } },
          iocsError: new Error("iocs failed"),
          threatIntelligenceError: null,
        }),
      );
      render();

      // Risk information (from the investigation itself, not IOCs)
      // remains fully visible.
      expect(container.querySelector(".investigation-overview-risk")).not.toBeNull();
      expect(container.textContent).toContain("42");

      const summary = container.querySelector(".investigation-overview-summary")!;
      expect(summary.textContent).toContain("IOC data is unavailable");
      expect(summary.querySelectorAll(".metric-card")).toHaveLength(0);
    });

    it("keeps the Part 1D IOC summary honest and lets the Threat Intelligence summary render independently", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: null, threatIntelligence: { raw: {}, states: {} } },
          iocsError: new Error("iocs failed"),
          threatIntelligenceError: null,
        }),
      );
      render();

      const ioc = container.querySelector(".investigation-overview-ioc")!;
      expect(ioc.textContent).toContain("IOC data unavailable");
      expect(ioc.querySelectorAll(".metric-card")).toHaveLength(0);

      // TI succeeded even though IOCs failed -- it must still render,
      // with an honest note rather than a fabricated breakdown, since
      // its per-indicator breakdown depends on the now-missing IOC data.
      const ti = container.querySelector(".investigation-overview-ti")!;
      expect(ti.textContent).toContain("Threat Intelligence data was received");
    });

    it("keeps the Threat Intelligence summary honest when TI failed but IOCs succeeded", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: { ipv4: ["1.2.3.4"] }, threatIntelligence: null },
          iocsError: null,
          threatIntelligenceError: new Error("ti failed"),
        }),
      );
      render();

      const ti = container.querySelector(".investigation-overview-ti")!;
      expect(ti.textContent).toContain("Threat Intelligence data unavailable");

      const ioc = container.querySelector(".investigation-overview-ioc")!;
      expect(ioc.textContent).toContain("IPs");
    });
  });

  describe("success", () => {
    it("passes real, normalized investigation data into the workspace foundation with Overview active", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: {}, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      expect(container.textContent).toContain("Investigation #7");
      expect(container.textContent).toContain("report.txt");

      const overviewTab = Array.from(container.querySelectorAll('[role="tab"]')).find(
        (tab) => tab.textContent?.includes("Overview"),
      )!;
      expect(overviewTab.getAttribute("aria-selected")).toBe("true");

      // No warnings for a clean success.
      expect(container.textContent).not.toContain("data unavailable");
    });

    it("renders the Part 1B Investigation Header Card with real risk/status/confidence", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: {}, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      expect(container.querySelector(".investigation-header-card")).not.toBeNull();
      expect(container.textContent).toContain("42");
      expect(container.textContent).toContain("high");
      expect(container.textContent).toContain("90%");
    });

    it("renders the Part 1C Overview (Risk Overview + Investigation Summary) with real data", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"], domains: [] },
            threatIntelligence: { raw: {}, states: {} },
          },
        }),
      );
      render();

      expect(container.querySelector(".investigation-overview-risk")).not.toBeNull();
      expect(container.querySelector(".investigation-overview-summary")).not.toBeNull();

      // Real, genuine IOC counts from the actual normalized data --
      // one real ipv4 indicator, a real empty domains list.
      const summary = container.querySelector(".investigation-overview-summary")!;
      expect(summary.textContent).toContain("Total IOCs");
      expect(summary.textContent).toContain("1");
    });

    it("renders the Part 1D IOC summary, Threat Intelligence summary, and Timeline with real data", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"] },
            threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
          },
        }),
      );
      render();

      expect(container.querySelector(".investigation-overview-ioc")).not.toBeNull();
      expect(container.querySelector(".investigation-overview-ti")).not.toBeNull();
      expect(container.querySelector(".investigation-overview-timeline")).not.toBeNull();

      const ioc = container.querySelector(".investigation-overview-ioc")!;
      expect(ioc.textContent).toContain("IPs");

      const ti = container.querySelector(".investigation-overview-ti")!;
      expect(ti.textContent).toContain("Enriched");

      const timeline = container.querySelector(".investigation-overview-timeline")!;
      expect(timeline.textContent).toContain("2026-08-26T00:00:00");
    });
  });

  describe("Timeline model/page integration (A4-P2-P3 Part 5B)", () => {
    it("threads a successfully-loaded timeline into the workspace model/presentation data path", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: {},
            threatIntelligence: { raw: {}, states: {} },
            timeline: [TIMELINE_EVENT],
          },
        }),
      );
      render();

      // No warning: the timeline fetch succeeded.
      expect(container.textContent).not.toContain("Timeline data unavailable");
      expect(container.querySelector(".investigation-overview-timeline")).not.toBeNull();
    });

    it("does not break the workspace when timeline is null (unavailable)", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: {},
            threatIntelligence: { raw: {}, states: {} },
            timeline: null,
          },
        }),
      );
      render();

      // The workspace still mounts and renders the Overview normally --
      // an unavailable timeline is not a workspace-breaking condition.
      expect(container.querySelector(".investigation-overview-timeline")).not.toBeNull();
      expect(container.textContent).toContain("Investigation #7");
    });

    it("keeps an empty timeline ([]) distinct from a null (missing) timeline", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: {},
            threatIntelligence: { raw: {}, states: {} },
            timeline: [],
          },
        }),
      );
      render();

      // A genuinely empty timeline is not an error -- no warning, and
      // the workspace mounts exactly as it does for a null timeline
      // (Part 5C owns turning the distinction into different
      // presentation copy).
      expect(container.textContent).not.toContain("Timeline data unavailable");
      expect(container.querySelector(".investigation-overview-timeline")).not.toBeNull();
    });

    it("surfaces timelineError through the existing partial-data warning mechanism", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: {
            investigation: INVESTIGATION,
            iocs: {},
            threatIntelligence: { raw: {}, states: {} },
            timeline: null,
          },
          timelineError: new Error("timeline failed"),
        }),
      );
      render();

      expect(container.textContent).toContain("Timeline data unavailable");
      // The rest of the investigation still renders successfully -- a
      // timeline failure is a partial-data warning, never a total
      // investigation failure.
      expect(container.textContent).toContain("Investigation #7");
      expect(container.textContent).toContain("report.txt");
      expect(container.querySelector(".investigation-header-card")).not.toBeNull();
    });

    it("only shows the timeline warning for a genuine timeline failure, not alongside an unrelated IOC failure", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: {
            investigation: INVESTIGATION,
            iocs: null,
            threatIntelligence: { raw: {}, states: {} },
            timeline: [TIMELINE_EVENT],
          },
          iocsError: new Error("iocs failed"),
          timelineError: null,
        }),
      );
      render();

      expect(container.textContent).toContain("IOC data unavailable");
      expect(container.textContent).not.toContain("Timeline data unavailable");
    });
  });

  describe("risk explanation warning (PD-08-P2)", () => {
    it("surfaces riskExplanationError through the existing partial-data warning mechanism", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: {
            investigation: INVESTIGATION,
            iocs: {},
            threatIntelligence: { raw: {}, states: {} },
            timeline: null,
            riskExplanation: null,
          },
          riskExplanationError: new Error("risk explanation failed"),
        }),
      );
      render();

      expect(container.textContent).toContain("Risk explanation unavailable");
      // The rest of the investigation still renders successfully -- a
      // risk-explanation failure is a partial-data warning, never a
      // total investigation failure.
      expect(container.textContent).toContain("Investigation #7");
      expect(container.textContent).toContain("report.txt");
      expect(container.querySelector(".investigation-header-card")).not.toBeNull();
    });

    it("does not show the risk explanation warning when riskExplanationError is null", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: {},
            threatIntelligence: { raw: {}, states: {} },
            timeline: null,
            riskExplanation: null,
          },
        }),
      );
      render();

      expect(container.textContent).not.toContain("Risk explanation unavailable");
    });

    it("only shows the risk explanation warning for a genuine failure, not alongside an unrelated IOC failure", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: {
            investigation: INVESTIGATION,
            iocs: null,
            threatIntelligence: { raw: {}, states: {} },
            timeline: null,
            riskExplanation: null,
          },
          iocsError: new Error("iocs failed"),
          riskExplanationError: null,
        }),
      );
      render();

      expect(container.textContent).toContain("IOC data unavailable");
      expect(container.textContent).not.toContain("Risk explanation unavailable");
    });
  });

  describe("navigation", () => {
    it("enables all four tabs and never links to another top-level page", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: {}, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      const tabs = Array.from(container.querySelectorAll('[role="tab"]'));
      const iocsTab = tabs.find((tab) => tab.textContent?.includes("IOCs")) as HTMLButtonElement;
      const tiTab = tabs.find((tab) => tab.textContent?.includes("Threat Intel")) as HTMLButtonElement;
      const correlationsTab = tabs.find((tab) => tab.textContent?.includes("Correlations")) as HTMLButtonElement;

      expect(iocsTab.disabled).toBe(false);
      expect(tiTab.disabled).toBe(false);
      expect(correlationsTab.disabled).toBe(false);

      const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
      expect(
        hrefs.every(
          (href) => href !== "#/ioc-explorer" && href !== "#/threat-intel" && href !== "#/correlations",
        ),
      ).toBe(true);
    });
  });

  describe("IOCs tab (Part 2A)", () => {
    it("selects the IOCs tab and renders the real IOC workspace, replacing the Overview content", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"], domains: ["evil.example"] },
            threatIntelligence: { raw: {}, states: {} },
          },
        }),
      );
      render();

      const iocsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("IOCs"),
      ) as HTMLButtonElement;

      act(() => {
        iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      expect(iocsTab.getAttribute("aria-selected")).toBe("true");
      expect(container.querySelector(".investigation-ioc-workspace")).not.toBeNull();
      expect(container.querySelector(".investigation-overview-risk")).toBeNull();

      const workspace = container.querySelector(".investigation-ioc-workspace")!;
      expect(workspace.textContent).toContain("1.2.3.4");
      expect(workspace.textContent).toContain("evil.example");
    });

    it("stays inside the investigation workspace and never navigates to /ioc-explorer", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: { ipv4: ["1.2.3.4"] }, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      const iocsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("IOCs"),
      ) as HTMLButtonElement;

      act(() => {
        iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      expect(container.querySelector('[data-testid="investigations-stub"]')).toBeNull();
      const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
      expect(hrefs.every((href) => href !== "#/ioc-explorer")).toBe(true);
    });

    it("shows the honest unavailable state on the IOCs tab when IOC data failed to load", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: null, threatIntelligence: { raw: {}, states: {} } },
          iocsError: new Error("iocs failed"),
        }),
      );
      render();

      const iocsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("IOCs"),
      ) as HTMLButtonElement;

      act(() => {
        iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      const workspace = container.querySelector(".investigation-ioc-workspace")!;
      expect(workspace.textContent).toContain("IOC data unavailable");
      expect(workspace.querySelectorAll(".metric-card")).toHaveLength(0);
    });
  });

  describe("Threat Intel tab (Part 3A)", () => {
    function clickTiTab(): void {
      const tiTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("Threat Intel"),
      ) as HTMLButtonElement;
      act(() => {
        tiTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }

    it("selects the Threat Intel tab and renders the real TI foundation, replacing the Overview content", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"] },
            threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
          },
        }),
      );
      render();

      const tabs = Array.from(container.querySelectorAll('[role="tab"]'));
      const tiTab = tabs.find((tab) => tab.textContent?.includes("Threat Intel")) as HTMLButtonElement;

      clickTiTab();

      expect(tiTab.getAttribute("aria-selected")).toBe("true");
      expect(container.querySelector(".investigation-threat-intel")).not.toBeNull();
      expect(container.querySelector(".investigation-overview-risk")).toBeNull();

      const workspace = container.querySelector(".investigation-threat-intel")!;
      expect(workspace.textContent).toContain("Enriched");
    });

    it("stays inside the investigation workspace and never navigates to /threat-intel", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: {}, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      clickTiTab();

      expect(container.querySelector('[data-testid="investigations-stub"]')).toBeNull();
      const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
      expect(hrefs.every((href) => href !== "#/threat-intel")).toBe(true);
    });

    it("shows the honest unavailable state on the Threat Intel tab when TI data failed to load", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: { ipv4: ["1.2.3.4"] }, threatIntelligence: null },
          threatIntelligenceError: new Error("ti failed"),
        }),
      );
      render();

      clickTiTab();

      const workspace = container.querySelector(".investigation-threat-intel")!;
      expect(workspace.textContent).toContain("Threat Intelligence data unavailable");
    });

    it("never calls useInvestigation with a different argument when switching Overview → Threat Intel → IOCs → Threat Intel", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"] },
            threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
          },
        }),
      );
      render();

      clickTiTab();
      const iocsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("IOCs"),
      ) as HTMLButtonElement;
      act(() => {
        iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
      clickTiTab();

      // Tab selection is local component state (task brief §23) --
      // `useInvestigation()` is re-invoked on every render (as any
      // hook is), but it must always be called with the same
      // investigation ID; switching tabs never causes it to be called
      // with a different one, i.e. never triggers a distinct fetch.
      expect(useInvestigationMock.mock.calls.every((call) => call[0] === 7)).toBe(true);
      expect(container.querySelector(".investigation-threat-intel")).not.toBeNull();
    });

    it("keeps the IOC workspace independent when TI data is unavailable", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: { ipv4: ["1.2.3.4"] }, threatIntelligence: null },
          threatIntelligenceError: new Error("ti failed"),
        }),
      );
      render();

      const iocsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("IOCs"),
      ) as HTMLButtonElement;
      act(() => {
        iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      const workspace = container.querySelector(".investigation-ioc-workspace")!;
      expect(workspace.textContent).toContain("1.2.3.4");
    });
  });

  describe("Correlations tab (Part 4A)", () => {
    function clickCorrelationsTab(): void {
      const correlationsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("Correlations"),
      ) as HTMLButtonElement;
      act(() => {
        correlationsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }

    it("selects the Correlations tab and renders the honest foundation, replacing the Overview content", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"] },
            threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
          },
        }),
      );
      render();

      const tabs = Array.from(container.querySelectorAll('[role="tab"]'));
      const correlationsTab = tabs.find((tab) => tab.textContent?.includes("Correlations")) as HTMLButtonElement;

      clickCorrelationsTab();

      expect(correlationsTab.getAttribute("aria-selected")).toBe("true");
      expect(container.querySelector(".investigation-correlations")).not.toBeNull();
      expect(container.querySelector(".investigation-overview-risk")).toBeNull();

      const workspace = container.querySelector(".investigation-correlations")!;
      expect(workspace.textContent).toContain("No explicit correlations found");
    });

    it("stays inside the investigation workspace and never navigates to /correlations", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: {}, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      clickCorrelationsTab();

      expect(container.querySelector('[data-testid="investigations-stub"]')).toBeNull();
      const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
      expect(hrefs.every((href) => href !== "#/correlations")).toBe(true);
    });

    it("shows the honest unavailable state on the Correlations tab when both IOC and TI data failed to load", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: null, threatIntelligence: null },
          iocsError: new Error("iocs failed"),
          threatIntelligenceError: new Error("ti failed"),
        }),
      );
      render();

      clickCorrelationsTab();

      const workspace = container.querySelector(".investigation-correlations")!;
      expect(workspace.textContent).toContain("Correlation data unavailable");
    });

    it("never calls useInvestigation with a different argument when switching Overview → Correlations → IOCs", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"] },
            threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
          },
        }),
      );
      render();

      clickCorrelationsTab();
      const iocsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("IOCs"),
      ) as HTMLButtonElement;
      act(() => {
        iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
      clickCorrelationsTab();

      expect(useInvestigationMock.mock.calls.every((call) => call[0] === 7)).toBe(true);
      expect(container.querySelector(".investigation-correlations")).not.toBeNull();
    });

    it("keeps the Correlations tab independent when IOC data is unavailable", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: null, threatIntelligence: { raw: {}, states: {} } },
          iocsError: new Error("iocs failed"),
        }),
      );
      render();

      clickCorrelationsTab();

      const workspace = container.querySelector(".investigation-correlations")!;
      expect(workspace.textContent).toContain("No explicit correlations found");
      expect(workspace.querySelectorAll(".investigation-correlations__item")).toHaveLength(0);
    });

    it("keeps the Correlations tab independent when TI data is unavailable", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "partial",
          data: { investigation: INVESTIGATION, iocs: { ipv4: ["1.2.3.4"] }, threatIntelligence: null },
          threatIntelligenceError: new Error("ti failed"),
        }),
      );
      render();

      clickCorrelationsTab();

      const workspace = container.querySelector(".investigation-correlations")!;
      expect(workspace.textContent).toContain("No explicit correlations found");
      expect(workspace.querySelectorAll(".investigation-correlations__item")).toHaveLength(0);
    });
  });

  describe("Correlations tab — integration polish (Part 4C)", () => {
    function clickCorrelationsTab(): void {
      const correlationsTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
        tab.textContent?.includes("Correlations"),
      ) as HTMLButtonElement;
      act(() => {
        correlationsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }

    it("reuses the shared Card primitive rather than a second visual language", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: {}, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      clickCorrelationsTab();

      const workspace = container.querySelector(".investigation-correlations")!;
      // `.investigation-correlations` is the page-specific className
      // passed to `Card` (`InvestigationCorrelations.tsx`), so a real
      // `.card` class alongside it confirms this section is a `Card`
      // instance -- not a bespoke panel with its own border/surface
      // styling (task brief §8's "no new visual language").
      expect(workspace.classList.contains("card")).toBe(true);
    });

    it("keeps the Correlations heading a real, singular h2 alongside the rest of the workspace's heading structure", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: { investigation: INVESTIGATION, iocs: {}, threatIntelligence: { raw: {}, states: {} } },
        }),
      );
      render();

      clickCorrelationsTab();

      const h1s = container.querySelectorAll("h1");
      const h2s = Array.from(container.querySelectorAll("h2"));
      const correlationsHeadings = h2s.filter((heading) => heading.textContent === "Correlations");

      // Exactly one page-level h1 (`PageHeader`), and the Correlations
      // card's own h2 appears exactly once -- no duplicate/competing
      // heading left over from the previously active tab's content
      // (task brief §9/§12: hierarchy stays legible, nothing buried
      // or duplicated).
      expect(h1s).toHaveLength(1);
      expect(correlationsHeadings).toHaveLength(1);
    });

    it("does not leave Overview-tab headings mounted once Correlations is selected", () => {
      useInvestigationMock.mockReturnValue(
        makeResult({
          state: "success",
          data: {
            investigation: INVESTIGATION,
            iocs: { ipv4: ["1.2.3.4"] },
            threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
          },
        }),
      );
      render();

      clickCorrelationsTab();

      const h2Texts = Array.from(container.querySelectorAll("h2")).map((heading) => heading.textContent);
      expect(h2Texts).not.toContain("Risk Overview");
      expect(h2Texts).not.toContain("Investigation Summary");
    });
  });

  describe("Accessibility Foundation (Frontend MAX-1)", () => {
    function successResult(): UseInvestigationResult {
      return makeResult({
        state: "success",
        data: {
          investigation: INVESTIGATION,
          iocs: { ipv4: ["1.2.3.4"] },
          threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
        },
      });
    }

    function getTabs(): HTMLButtonElement[] {
      return Array.from(container.querySelectorAll('[role="tab"]')) as HTMLButtonElement[];
    }

    function getTabByLabel(label: string): HTMLButtonElement {
      const tab = getTabs().find((candidate) => candidate.textContent === label);
      expect(tab).toBeDefined();
      return tab!;
    }

    describe("semantics", () => {
      it("renders a single tablist with the four workspace tabs", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const tablists = container.querySelectorAll('[role="tablist"]');
        expect(tablists).toHaveLength(1);
        expect(getTabs()).toHaveLength(4);
      });

      it("gives every tab a stable id, aria-controls, and correct aria-selected", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        for (const tab of getTabs()) {
          expect(tab.id).toMatch(/^investigation-workspace-tab-/);
          const controls = tab.getAttribute("aria-controls");
          expect(controls).toMatch(/^investigation-workspace-panel-/);
          // Stable/deterministic: the panel suffix matches the tab id suffix.
          expect(controls).toBe(`investigation-workspace-panel-${tab.id.replace("investigation-workspace-tab-", "")}`);
        }

        const overviewTab = getTabByLabel("Overview");
        expect(overviewTab.getAttribute("aria-selected")).toBe("true");
        const iocsTab = getTabByLabel("IOCs");
        expect(iocsTab.getAttribute("aria-selected")).toBe("false");
      });

      it("renders exactly one tabpanel whose id/aria-labelledby match the active tab", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const panels = container.querySelectorAll('[role="tabpanel"]');
        expect(panels).toHaveLength(1);
        const panel = panels[0] as HTMLElement;
        const overviewTab = getTabByLabel("Overview");

        expect(panel.id).toBe(overviewTab.getAttribute("aria-controls"));
        expect(panel.getAttribute("aria-labelledby")).toBe(overviewTab.id);
      });

      it("keeps the tab/panel relationship correct after switching tabs", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const iocsTab = getTabByLabel("IOCs");
        act(() => {
          iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });

        const panel = container.querySelector('[role="tabpanel"]') as HTMLElement;
        expect(panel.id).toBe(iocsTab.getAttribute("aria-controls"));
        expect(panel.getAttribute("aria-labelledby")).toBe(iocsTab.id);
        expect(iocsTab.getAttribute("aria-selected")).toBe("true");
      });
    });

    describe("roving tabindex", () => {
      it("gives the active tab tabIndex 0 and every inactive tab tabIndex -1", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        for (const tab of getTabs()) {
          const expected = tab.getAttribute("aria-selected") === "true" ? "0" : "-1";
          expect(tab.tabIndex.toString()).toBe(expected);
        }
      });

      it("updates roving tabindex after a click selection", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const threatIntelTab = getTabByLabel("Threat Intel");
        act(() => {
          threatIntelTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });

        expect(threatIntelTab.tabIndex).toBe(0);
        for (const tab of getTabs()) {
          if (tab !== threatIntelTab) {
            expect(tab.tabIndex).toBe(-1);
          }
        }
      });
    });

    describe("keyboard navigation", () => {
      function keydown(target: HTMLElement, key: string): void {
        act(() => {
          target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
        });
      }

      it("ArrowRight moves selection and focus to the next tab", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const overviewTab = getTabByLabel("Overview");
        const iocsTab = getTabByLabel("IOCs");
        overviewTab.focus();

        keydown(overviewTab, "ArrowRight");

        expect(iocsTab.getAttribute("aria-selected")).toBe("true");
        expect(document.activeElement).toBe(iocsTab);
      });

      it("ArrowLeft moves selection and focus to the previous tab", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const overviewTab = getTabByLabel("Overview");
        const iocsTab = getTabByLabel("IOCs");
        act(() => {
          iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });
        iocsTab.focus();

        keydown(iocsTab, "ArrowLeft");

        expect(overviewTab.getAttribute("aria-selected")).toBe("true");
        expect(document.activeElement).toBe(overviewTab);
      });

      it("ArrowRight wraps from the last tab to the first", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const correlationsTab = getTabByLabel("Correlations");
        const overviewTab = getTabByLabel("Overview");
        act(() => {
          correlationsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });
        correlationsTab.focus();

        keydown(correlationsTab, "ArrowRight");

        expect(overviewTab.getAttribute("aria-selected")).toBe("true");
        expect(document.activeElement).toBe(overviewTab);
      });

      it("ArrowLeft wraps from the first tab to the last", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const overviewTab = getTabByLabel("Overview");
        const correlationsTab = getTabByLabel("Correlations");
        overviewTab.focus();

        keydown(overviewTab, "ArrowLeft");

        expect(correlationsTab.getAttribute("aria-selected")).toBe("true");
        expect(document.activeElement).toBe(correlationsTab);
      });

      it("Home moves selection and focus to the first tab", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const correlationsTab = getTabByLabel("Correlations");
        const overviewTab = getTabByLabel("Overview");
        act(() => {
          correlationsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });
        correlationsTab.focus();

        keydown(correlationsTab, "Home");

        expect(overviewTab.getAttribute("aria-selected")).toBe("true");
        expect(document.activeElement).toBe(overviewTab);
      });

      it("End moves selection and focus to the last tab", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const overviewTab = getTabByLabel("Overview");
        const correlationsTab = getTabByLabel("Correlations");
        overviewTab.focus();

        keydown(overviewTab, "End");

        expect(correlationsTab.getAttribute("aria-selected")).toBe("true");
        expect(document.activeElement).toBe(correlationsTab);
      });

      it("does not react to unrelated keys", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const overviewTab = getTabByLabel("Overview");
        overviewTab.focus();

        keydown(overviewTab, "a");

        expect(overviewTab.getAttribute("aria-selected")).toBe("true");
        expect(document.activeElement).toBe(overviewTab);
      });
    });

    describe("mouse interaction (regression)", () => {
      it("clicking a tab still selects it, shows the correct panel, and deselects the previous tab", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const overviewTab = getTabByLabel("Overview");
        const iocsTab = getTabByLabel("IOCs");
        act(() => {
          iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });

        expect(iocsTab.getAttribute("aria-selected")).toBe("true");
        expect(overviewTab.getAttribute("aria-selected")).toBe("false");
        expect(container.querySelector(".investigation-ioc-workspace")).not.toBeNull();
      });

      it("never calls useInvestigation with a different investigation id from a tab click", () => {
        // Mirrors the established pattern used by the other tab
        // describe blocks above (e.g. Correlations tab §"never calls
        // useInvestigation with a different argument..."): tab
        // selection is local render state, so every call the mocked
        // hook does receive (including React's normal re-render call)
        // must still be for the same investigation id -- never a
        // fresh fetch for a different investigation.
        useInvestigationMock.mockReturnValue(successResult());
        render();

        const iocsTab = getTabByLabel("IOCs");
        act(() => {
          iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });

        expect(useInvestigationMock.mock.calls.every((call) => call[0] === 7)).toBe(true);
      });
    });

    describe("regression", () => {
      it("still renders existing tab content and investigation data unchanged", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        expect(container.textContent).toContain("Investigation #7");
        expect(container.textContent).toContain("report.txt");
      });

      it("preserves focus-visible styling by not overriding the shared global rule with inline styles", () => {
        useInvestigationMock.mockReturnValue(successResult());
        render();

        for (const tab of getTabs()) {
          expect(tab.getAttribute("style")).toBeNull();
        }
      });
    });
  });

  describe("URL-represented tab state (MAX7-F-02)", () => {
    function successResult(): UseInvestigationResult {
      return makeResult({
        state: "success",
        data: {
          investigation: INVESTIGATION,
          iocs: { ipv4: ["1.2.3.4"] },
          threatIntelligence: { raw: {}, states: { ipv4: { "1.2.3.4": "enriched" } } },
        },
      });
    }

    function getTabs(): HTMLButtonElement[] {
      return Array.from(container.querySelectorAll('[role="tab"]')) as HTMLButtonElement[];
    }

    function getTabByLabel(label: string): HTMLButtonElement {
      const tab = getTabs().find((candidate) => candidate.textContent === label);
      expect(tab).toBeDefined();
      return tab!;
    }

    it("defaults to the Overview tab when the URL has no ?tab= parameter", () => {
      useInvestigationMock.mockReturnValue(successResult());
      renderWithLocationProbe(["/investigations/7"]);

      expect(getTabByLabel("Overview").getAttribute("aria-selected")).toBe("true");
      expect(locationProbeText()).toBe("/investigations/7");
    });

    it("selects the tab named by an existing ?tab= URL parameter on first render (deep link / reload)", () => {
      useInvestigationMock.mockReturnValue(successResult());
      renderWithLocationProbe(["/investigations/7?tab=threat-intel"]);

      const threatIntelTab = getTabByLabel("Threat Intel");
      expect(threatIntelTab.getAttribute("aria-selected")).toBe("true");
      expect(container.querySelector(".investigation-overview-risk")).toBeNull();
    });

    it("falls back to Overview, without throwing, for an unrecognized ?tab= value", () => {
      useInvestigationMock.mockReturnValue(successResult());
      expect(() => renderWithLocationProbe(["/investigations/7?tab=not-a-real-tab"])).not.toThrow();

      expect(getTabByLabel("Overview").getAttribute("aria-selected")).toBe("true");
    });

    it("writes the selected tab into the URL's ?tab= parameter when a tab is clicked", () => {
      useInvestigationMock.mockReturnValue(successResult());
      renderWithLocationProbe(["/investigations/7"]);

      const iocsTab = getTabByLabel("IOCs");
      act(() => {
        iocsTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      expect(locationProbeText()).toBe("/investigations/7?tab=iocs");
    });

    it("removes the ?tab= parameter again when navigating back to Overview, rather than writing ?tab=overview", () => {
      useInvestigationMock.mockReturnValue(successResult());
      renderWithLocationProbe(["/investigations/7?tab=correlations"]);

      const overviewTab = getTabByLabel("Overview");
      act(() => {
        overviewTab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      expect(locationProbeText()).toBe("/investigations/7");
    });

    it("keeps ArrowRight keyboard selection (MAX-1) in sync with the URL", () => {
      useInvestigationMock.mockReturnValue(successResult());
      renderWithLocationProbe(["/investigations/7"]);

      const overviewTab = getTabByLabel("Overview");
      overviewTab.focus();
      act(() => {
        overviewTab.dispatchEvent(
          new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }),
        );
      });

      expect(locationProbeText()).toBe("/investigations/7?tab=iocs");
    });

    it("supports switching between several tabs in a row, each write reflecting only the latest selection", () => {
      useInvestigationMock.mockReturnValue(successResult());
      renderWithLocationProbe(["/investigations/7"]);

      act(() => {
        getTabByLabel("IOCs").dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
      expect(locationProbeText()).toBe("/investigations/7?tab=iocs");

      act(() => {
        getTabByLabel("Threat Intel").dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
      expect(locationProbeText()).toBe("/investigations/7?tab=threat-intel");
      expect(getTabByLabel("IOCs").getAttribute("aria-selected")).toBe("false");
    });
  });
});
