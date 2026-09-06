import { describe, expect, it } from "vitest";
import type { DashboardSummaryResult } from "../../shared/api/types";
import {
  summarizeInvestigationWorkload,
  toDashboardMetrics,
  toDashboardViewModel,
  toInvestigationActivityTrend,
  toIocDistribution,
  toRecentInvestigations,
  toRiskDistribution,
} from "./dashboardViewModel";

const BASE: DashboardSummaryResult = {
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
      investigation_id: 42,
      report_name: "malware-report.txt",
      risk_score: 91,
      severity: "CRITICAL",
      confidence: 0.94,
      status: "COMPLETED",
      analyzed_at: "2026-08-28T10:15:00",
    },
  ],
};

describe("Dashboard view model", () => {
  it("maps real metrics without inventing trend values", () => {
    expect(toDashboardMetrics(BASE)).toEqual([
      { id: "total-reports", label: "Total Reports", value: "12", iconKey: "reports", accent: "neutral" },
      { id: "total-iocs", label: "Total IOCs", value: "340", iconKey: "iocs", accent: "neutral" },
      {
        id: "high-risk-count",
        label: "High Risk Findings",
        value: "3",
        iconKey: "highRisk",
        accent: "severity",
      },
      {
        id: "threat-intel-coverage",
        label: "Threat Intel Coverage",
        value: "87.5%",
        iconKey: "coverage",
        accent: "neutral",
      },
    ]);
  });

  it("gives High Risk Findings a neutral accent when the real count is zero", () => {
    const result = { ...BASE, metrics: { ...BASE.metrics, high_risk_count: 0 } };
    expect(toDashboardMetrics(result)[2]).toEqual({
      id: "high-risk-count",
      label: "High Risk Findings",
      value: "0",
      iconKey: "highRisk",
      accent: "neutral",
    });
  });

  it("preserves null TI coverage as No data instead of 0%", () => {
    const result = { ...BASE, metrics: { ...BASE.metrics, threat_intel_coverage_percent: null } };
    expect(toDashboardMetrics(result)[3]!.value).toBe("No data");
  });

  it("maps the real status vocabulary exactly", () => {
    expect(summarizeInvestigationWorkload({ COMPLETED: 12, FAILED: 2 })).toEqual([
      { status: "COMPLETED", label: "Completed", tone: "success", count: 12 },
      { status: "FAILED", label: "Failed", tone: "error", count: 2 },
    ]);
    expect(summarizeInvestigationWorkload({})).toEqual([]);
  });

  it("maps risk distribution in severity order and keeps zero counts", () => {
    expect(toRiskDistribution({ HIGH: 2, LOW: 0, CRITICAL: 1, MEDIUM: 3 })).toEqual([
      { severity: "low", label: "Low", count: 0 },
      { severity: "medium", label: "Medium", count: 3 },
      { severity: "high", label: "High", count: 2 },
      { severity: "critical", label: "Critical", count: 1 },
    ]);
  });

  it("maps IOC distribution without recomputing it", () => {
    expect(toIocDistribution(BASE.ioc_distribution)).toEqual([
      { iocType: "domains", label: "Domains", count: 80 },
      { iocType: "ipv4", label: "Ipv4", count: 120 },
      { iocType: "sha256", label: "Sha256", count: 140 },
    ]);
  });

  it("maps recent investigations with real status/severity and a formatted analyzed_at", () => {
    expect(toRecentInvestigations(BASE.recent_investigations)).toEqual([
      {
        id: "42",
        investigationId: 42,
        name: "malware-report.txt",
        status: "COMPLETED",
        statusTone: "success",
        severity: "CRITICAL",
        severityTone: "critical",
        updatedLabel: "Aug 28, 2026, 10:15 AM",
      },
    ]);
  });

  it("handles an unscored investigation without presenting its zero sentinel as real risk", () => {
    const investigation = {
      ...BASE.recent_investigations[0]!,
      severity: "NOT_SCORED",
      risk_score: 0,
      confidence: 0,
    };
    const [row] = toRecentInvestigations([investigation]);
    expect(row!.severity).toBe("Not scored");
    expect(row!.severityTone).toBe("neutral");
  });

  it("maps empty arrays honestly and keeps zero metric counts as real values", () => {
    const result: DashboardSummaryResult = {
      metrics: { total_reports: 0, total_iocs: 0, high_risk_count: 0, threat_intel_coverage_percent: null },
      investigation_status_counts: {},
      risk_distribution: {},
      ioc_distribution: {},
      recent_investigations: [],
    };
    expect(toDashboardViewModel(result)).toEqual({
      metrics: [
        { id: "total-reports", label: "Total Reports", value: "0", iconKey: "reports", accent: "neutral" },
        { id: "total-iocs", label: "Total IOCs", value: "0", iconKey: "iocs", accent: "neutral" },
        {
          id: "high-risk-count",
          label: "High Risk Findings",
          value: "0",
          iconKey: "highRisk",
          accent: "neutral",
        },
        {
          id: "threat-intel-coverage",
          label: "Threat Intel Coverage",
          value: "No data",
          iconKey: "coverage",
          accent: "neutral",
        },
      ],
      investigationWorkload: [],
      recentInvestigations: [],
      riskDistribution: [],
      iocDistribution: [],
    });
  });

  it("sorts investigation activity chronologically without fabricating gap dates", () => {
    expect(
      toInvestigationActivityTrend({ "2026-08-30": 2, "2026-08-28": 1, "2026-08-29": 0 }),
    ).toEqual([
      { date: "2026-08-28", label: "Aug 28", count: 1 },
      { date: "2026-08-29", label: "Aug 29", count: 0 },
      { date: "2026-08-30", label: "Aug 30", count: 2 },
    ]);
  });

  it("maps an empty investigation activity record to an empty trend, not a fabricated series", () => {
    expect(toInvestigationActivityTrend({})).toEqual([]);
  });
});
