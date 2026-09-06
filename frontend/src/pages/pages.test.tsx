/**
 * Page rendering tests (Phase 4G-2 Part 3, §24).
 *
 * Each page renders standalone (no router needed — none of these
 * pages use route params) via `react-dom/server`'s
 * `renderToStaticMarkup`, matching the project's existing
 * no-jsdom-by-default convention. Verifies: renders without
 * throwing, carries its own `<main>` landmark with the expected
 * accessible name, and shows its expected title text.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { DashboardSummaryResult, InvestigationAggregateSummaryResult } from "../shared/api/types";

import {
  AnalyzePage,
  DashboardPage,
  InvestigationsPage,
  ReportsPage,
  SettingsPage,
} from "./index";

const PAGES = [
  { name: "Dashboard", Component: DashboardPage, mainLabel: "Dashboard page", title: "Dashboard" },
  { name: "Analyze", Component: AnalyzePage, mainLabel: "Analyze page", title: "Analyze" },
  { name: "Investigations", Component: InvestigationsPage, mainLabel: "Investigations page", title: "Investigations" },
  { name: "Reports", Component: ReportsPage, mainLabel: "Reports page", title: "Reports" },
  { name: "Settings", Component: SettingsPage, mainLabel: "Settings page", title: "Settings" },
] as const;

describe.each(PAGES)("$name page", ({ Component, mainLabel, title }) => {
  it("renders without throwing", () => {
    expect(() => renderToStaticMarkup(<Component />)).not.toThrow();
  });

  it("renders exactly one <main> landmark with the expected accessible name", () => {
    const html = renderToStaticMarkup(<Component />);
    expect((html.match(/<main/g) ?? []).length).toBe(1);
    expect(html).toContain(`aria-label="${mainLabel}"`);
  });

  it("renders its expected title as a single <h1>", () => {
    const html = renderToStaticMarkup(<Component />);
    expect((html.match(/<h1/g) ?? []).length).toBe(1);
    expect(html).toContain(`>${title}<`);
  });
});

const dashboardContentState = vi.hoisted(() => ({
  value: null as DashboardSummaryResult | null,
  state: "success" as "loading" | "success" | "error",
  error: null as unknown,
  retry: vi.fn(),
}));

vi.mock("./dashboard/useDashboard", () => ({
  useDashboard: () => ({
    state: dashboardContentState.state,
    dashboard: dashboardContentState.value,
    error: dashboardContentState.error,
    retry: dashboardContentState.retry,
  }),
}));

const dashboardActivityContentState = vi.hoisted(() => ({
  value: null as InvestigationAggregateSummaryResult | null,
  state: "success" as "loading" | "success" | "error",
  error: null as unknown,
  retry: vi.fn(),
}));

vi.mock("./dashboard/useInvestigationActivity", () => ({
  useInvestigationActivity: () => ({
    state: dashboardActivityContentState.state,
    activity: dashboardActivityContentState.value,
    error: dashboardActivityContentState.error,
    retry: dashboardActivityContentState.retry,
  }),
}));

describe("DashboardPage content", () => {
  it("renders KPI metrics, recent investigations, and risk distribution", () => {
    dashboardContentState.state = "success";
    dashboardContentState.value = {
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
    dashboardActivityContentState.state = "success";
    dashboardActivityContentState.value = {
      total_investigations: 12,
      status_counts: { COMPLETED: 12 },
      severity_distribution: { LOW: 6, MEDIUM: 3, HIGH: 2, CRITICAL: 1 },
      ioc_distribution: { ipv4: 120, domains: 80, sha256: 140 },
      threat_intel_coverage_percent: 87.5,
      investigations_by_date: { "2026-08-28": 12 },
    };
    const html = renderToStaticMarkup(<DashboardPage />);
    expect(html).toContain("Investigation Overview");
    expect(html).toContain("Recent Investigations");
    expect(html).toContain("Risk Distribution");
    expect(html).toContain("Investigation Activity");
  });
});

describe("AnalyzePage content", () => {
  it("describes the real analysis service via InfoNote, with no stale non-functional claim", () => {
    const html = renderToStaticMarkup(<AnalyzePage />);
    expect(html).toContain('role="note"');
    expect(html).toContain("functional against the real analysis service");
    expect(html).not.toContain("not implemented in this checkpoint");
    expect(html).not.toContain("structural mock only");
  });

  it("renders exactly one FileDropzone file input", () => {
    const html = renderToStaticMarkup(<AnalyzePage />);
    expect((html.match(/type="file"/g) ?? []).length).toBe(1);
  });

  it("starts idle, with no validation-error alert rendered", () => {
    const html = renderToStaticMarkup(<AnalyzePage />);
    expect(html).toContain("No file selected");
    expect(html).not.toContain('role="alert"');
  });

  it("no longer renders the removed mock recent-analyses list", () => {
    const html = renderToStaticMarkup(<AnalyzePage />);
    expect(html).not.toContain("Recent Analyses");
    expect(html).not.toContain("phishing-attachment.eml");
  });
});

describe("SettingsPage content", () => {
  // SOC-IQ Part 2B-1: Theme and Export Directory are now real,
  // backend-backed controls loaded via `get_settings` (see
  // `SettingsPage.test.tsx` for full state coverage with the fetch
  // hook mocked). This top-level render has no router/mocked hook, so
  // it renders exactly `useSettings()`'s real initial state -- loading,
  // since no effect has flushed yet -- rather than the old always-mock
  // content.
  it("renders a real loading state rather than mock settings values", () => {
    const html = renderToStaticMarkup(<SettingsPage />);
    expect(html).toContain("Loading settings");
    expect(html).not.toContain("no changes made here are saved");
  });

  it("renders exactly one <main> Settings page landmark with no thrown error", () => {
    expect(() => renderToStaticMarkup(<SettingsPage />)).not.toThrow();
  });
});

describe("ReportsPage content", () => {
  it("renders a real loading state rather than mock report rows (see ReportsPage.test.tsx for full state coverage)", () => {
    const html = renderToStaticMarkup(<ReportsPage />);
    expect(html).toContain("Loading reports");
    expect(html).not.toContain("<table");
    // The old mock report titles never leak through.
    expect(html).not.toContain("Outbound beacon to unknown domain");
  });
});
