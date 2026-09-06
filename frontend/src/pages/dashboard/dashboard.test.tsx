// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DashboardSummaryResult, InvestigationAggregateSummaryResult } from "../../shared/api/types";
import type { DashboardRecentInvestigationRow } from "./dashboardViewModel";

const dashboardState = vi.hoisted(() => ({
  value: null as DashboardSummaryResult | null,
  state: "success" as "loading" | "success" | "error",
  error: null as unknown,
  retry: vi.fn(),
}));

const activityState = vi.hoisted(() => ({
  value: null as InvestigationAggregateSummaryResult | null,
  state: "success" as "loading" | "success" | "error",
  error: null as unknown,
  retry: vi.fn(),
}));

vi.mock("./useDashboard", () => ({
  useDashboard: () => ({
    state: dashboardState.state,
    dashboard: dashboardState.value,
    error: dashboardState.error,
    retry: dashboardState.retry,
  }),
}));

vi.mock("./useInvestigationActivity", () => ({
  useInvestigationActivity: () => ({
    state: activityState.state,
    activity: activityState.value,
    error: activityState.error,
    retry: activityState.retry,
  }),
}));

import { DashboardPage } from "../DashboardPage";
import { DashboardMetrics } from "./DashboardMetrics";
import { DashboardInvestigationOverview } from "./DashboardInvestigationOverview";
import { DashboardRecentInvestigations } from "./DashboardRecentInvestigations";
import { DashboardRiskOverview } from "./DashboardRiskOverview";
import { DashboardIocOverview } from "./DashboardIocOverview";
import { DashboardQuickActions } from "./DashboardQuickActions";
import { DashboardInvestigationActivity } from "./DashboardInvestigationActivity";
import { buildDashboardQuickActions } from "./dashboardViewModel";
import { NAVIGATION_ITEMS } from "../../app/navigation/navigationModel";

const SUMMARY: DashboardSummaryResult = {
  metrics: {
    total_reports: 12,
    total_iocs: 340,
    high_risk_count: 3,
    threat_intel_coverage_percent: 87.5,
  },
  investigation_status_counts: { COMPLETED: 12 },
  risk_distribution: { LOW: 6, MEDIUM: 3, HIGH: 2, CRITICAL: 1 },
  ioc_distribution: { ipv4: 120, domains: 80, sha256: 140 },
  recent_investigations: [
    {
      investigation_id: 7,
      report_name: "malware-report.txt",
      risk_score: 91,
      severity: "CRITICAL",
      confidence: 0.94,
      status: "COMPLETED",
      analyzed_at: "2026-08-28T10:15:00",
    },
  ],
};

const ACTIVITY_SUMMARY: InvestigationAggregateSummaryResult = {
  total_investigations: 12,
  status_counts: { COMPLETED: 12 },
  severity_distribution: { LOW: 6, MEDIUM: 3, HIGH: 2, CRITICAL: 1 },
  ioc_distribution: { ipv4: 120, domains: 80, sha256: 140 },
  threat_intel_coverage_percent: 87.5,
  investigations_by_date: { "2026-08-27": 4, "2026-08-28": 8 },
};

describe("DashboardPage real-data boundary", () => {
  beforeEach(() => {
    activityState.state = "success";
    activityState.value = ACTIVITY_SUMMARY;
    activityState.error = null;
  });

  it("renders real summary values through the view-model boundary", () => {
    dashboardState.state = "success";
    dashboardState.value = SUMMARY;
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("Total Reports");
    expect(html).toContain(">12<");
    expect(html).toContain(">340<");
    expect(html).toContain("87.5%");
    expect(html).toContain("50%");
    expect(html).toContain("33%");
    expect(html).toContain("Completed");
    expect(html).toContain("malware-report.txt");
    expect(html).toContain("CRITICAL");
    expect(html).not.toContain("Active Investigations");
    expect(html).not.toContain("+2 this week");
  });

  it("renders the real investigation activity trend from its own independent aggregate", () => {
    dashboardState.state = "success";
    dashboardState.value = SUMMARY;
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("Investigation Activity");
    expect(html).toContain("Aug 27");
    expect(html).toContain("Aug 28");
    expect(html).toContain('role="progressbar"');
  });

  it("shows the activity widget's own loading state independently of the main dashboard", () => {
    dashboardState.state = "success";
    dashboardState.value = SUMMARY;
    activityState.state = "loading";
    activityState.value = null;
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("Loading investigation activity");
    expect(html).not.toContain("Aug 27");
  });

  it("shows the activity widget's own error state independently of the main dashboard", () => {
    dashboardState.state = "success";
    dashboardState.value = SUMMARY;
    activityState.state = "error";
    activityState.value = null;
    activityState.error = new Error("aggregate command failed");
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("aggregate command failed");
    expect(html).toContain("Total Reports");
  });

  it("shows an honest loading state without dashboard data", () => {
    dashboardState.state = "loading";
    dashboardState.value = null;
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("Loading dashboard data");
    expect(html).not.toContain("Total Reports");
    expect(html).not.toContain("malware-report.txt");
  });

  it("shows the real error and a retry action", () => {
    dashboardState.state = "error";
    dashboardState.value = null;
    dashboardState.error = new Error("sidecar unavailable");
    dashboardState.retry.mockClear();
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("sidecar unavailable");
    expect(html).toContain(">Retry<");
  });

  it("uses the P3 dashboard composition grid without changing data boundaries", () => {
    dashboardState.state = "success";
    dashboardState.value = SUMMARY;
    const html = renderToStaticMarkup(<DashboardPage />);

    expect(html).toContain('class="dashboard-page__grid"');
    expect(html).toContain('class="dashboard-page__metrics"');
    expect(html).toContain('class="dashboard-page__operational"');
    expect(html).toContain('class="dashboard-page__investigations"');
    expect(html).toContain('class="dashboard-page__recent"');
    expect(html).toContain('class="dashboard-page__risk"');
    expect(html).toContain('class="dashboard-page__ioc"');
    expect(html).toContain('class="dashboard-page__quick-actions"');
    expect(html).toContain('class="dashboard-page__activity"');
    expect(html).not.toContain("dashboard-page__overview-row");
    expect(html).not.toContain("dashboard-page__lower");
  });

  it("keeps operational status and quick actions on their existing boundaries", () => {
    dashboardState.state = "success";
    dashboardState.value = SUMMARY;
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("Operational Status");
    for (const item of NAVIGATION_ITEMS) {
      if (item.group === "primary" && item.id !== "dashboard") {
        expect(html).toContain(`href="#${item.path}"`);
      }
    }
  });
});

describe("Dashboard widgets", () => {
  it("render empty metrics without throwing", () => {
    expect(() => renderToStaticMarkup(<DashboardMetrics metrics={[]} />)).not.toThrow();
  });

  it("render an honest empty investigation state", () => {
    const html = renderToStaticMarkup(<DashboardRecentInvestigations investigations={[]} />);
    expect(html).toContain("No recent investigations.");
    expect(html).not.toContain("<table");
  });

  it("render an honest empty risk state", () => {
    const html = renderToStaticMarkup(<DashboardRiskOverview distribution={[]} />);
    expect(html).toContain("No risk data available.");
    const populated = renderToStaticMarkup(
      <DashboardRiskOverview distribution={[
        { severity: "critical", label: "Critical", count: 2 },
        { severity: "low", label: "Low", count: 2 },
      ]} />,
    );
    expect(populated).toContain("50%");
    expect(populated).toContain('role="progressbar"');
  });

  it("render an honest empty IOC state", () => {
    const html = renderToStaticMarkup(<DashboardIocOverview distribution={[]} />);
    expect(html).toContain("No IOC data available.");
    const populated = renderToStaticMarkup(
      <DashboardIocOverview distribution={[
        { iocType: "ipv4", label: "IPv4", count: 3 },
        { iocType: "sha256", label: "SHA256", count: 1 },
      ]} />,
    );
    expect(populated).toContain("75%");
    expect(populated).toContain("25%");
  });

  it("render an honest empty investigation activity state", () => {
    const html = renderToStaticMarkup(<DashboardInvestigationActivity trend={[]} />);
    expect(html).toContain("No investigation activity data available.");
    const populated = renderToStaticMarkup(
      <DashboardInvestigationActivity
        trend={[
          { date: "2026-08-27", label: "Aug 27", count: 4 },
          { date: "2026-08-28", label: "Aug 28", count: 8 },
        ]}
      />,
    );
    expect(populated).toContain("Aug 27");
    expect(populated).toContain("Aug 28");
    expect(populated).toContain('role="progressbar"');
    expect(populated).toContain('aria-valuenow="8"');
  });

  it("treats an all-zero investigation activity trend as an honest empty state", () => {
    const html = renderToStaticMarkup(
      <DashboardInvestigationActivity
        trend={[{ date: "2026-08-27", label: "Aug 27", count: 0 }]}
      />,
    );
    expect(html).toContain("No investigation activity data available.");
  });

  it("render real investigation status counts without invented workflow states", () => {
    const workload = [{ status: "COMPLETED", label: "Completed", tone: "success" as const, count: 12 }];
    const html = renderToStaticMarkup(<DashboardInvestigationOverview workload={workload} />);
    expect(html).toContain("Completed");
    expect(html).toContain(">12<");
    expect(html).toContain('role="progressbar"');
    expect(html).not.toContain("Open");
    expect(html).not.toContain("In progress");
    expect(html).not.toContain("Closed");
  });

  it("keeps quick actions derived from the existing navigation model", () => {
    const actions = buildDashboardQuickActions(NAVIGATION_ITEMS);
    const html = renderToStaticMarkup(<DashboardQuickActions actions={actions} />);
    expect((html.match(/<a /g) ?? []).length).toBe(actions.length);
  });
});

describe("Dashboard Recent Investigations keyboard activation", () => {
  // Mirrors the established `act` + `createRoot` + native `dispatchEvent`
  // convention (InvestigationIocWorkspace.test.tsx's "keyboard
  // accessibility" describe block) rather than introducing
  // @testing-library/react. DataTable's own Enter/Space handling
  // (DataTable.tsx) already has coverage there; this closes the one
  // real gap -- the Dashboard's own interactive-row consumer,
  // DashboardRecentInvestigations, had none (its existing tests above
  // only use renderToStaticMarkup, which cannot dispatch events at
  // all).
  let container: HTMLDivElement;
  let root: Root;

  const ROW: DashboardRecentInvestigationRow = {
    id: "51",
    investigationId: 51,
    name: "malware_report.txt",
    status: "COMPLETED",
    statusTone: "success",
    severity: "CRITICAL",
    severityTone: "critical",
    updatedLabel: "Aug 29, 2026, 5:33 AM",
  };

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    window.location.hash = "";
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    window.location.hash = "";
  });

  function renderRecentInvestigations(): void {
    act(() => {
      root = createRoot(container);
      root.render(<DashboardRecentInvestigations investigations={[ROW]} />);
    });
  }

  function pressKeyOnRow(key: string): void {
    const row = container.querySelector("tbody tr");
    act(() => {
      row?.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
    });
  }

  it("navigates to the Investigation Workspace with the row's real investigation ID on Enter", () => {
    renderRecentInvestigations();

    pressKeyOnRow("Enter");

    expect(window.location.hash).toBe(`#/investigations/${ROW.investigationId}`);
  });

  it("navigates to the Investigation Workspace with the row's real investigation ID on Space", () => {
    renderRecentInvestigations();

    pressKeyOnRow(" ");

    expect(window.location.hash).toBe(`#/investigations/${ROW.investigationId}`);
  });
});
