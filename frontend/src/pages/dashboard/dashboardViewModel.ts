/**
 * Dashboard view-model boundary — Phase 4H Part 2.
 *
 * Maps the real `DashboardSummaryResult` from `get_dashboard_summary`
 * into presentation-ready shapes consumed by the existing Dashboard
 * widgets. No React, network, database, or aggregation side effects live
 * here. Backend aggregation is never repeated in TypeScript.
 */
import type { NavigationItem } from "../../app/navigation/types";
import type { SidecarStatusView } from "../../shared/sidecar/sidecarStatusView";
import type {
  DashboardSummaryResult,
  InvestigationSummary,
} from "../../shared/api/types";
import type { StatusTone } from "../components/StatusBadge";
import {
  isInvestigationScored,
  severityTone,
  statusTone,
} from "../investigation/InvestigationHeaderCard";

// ---------------------------------------------------------------------------
// Dashboard presentation shapes
// ---------------------------------------------------------------------------

/**
 * Presentation-only key identifying which existing icon a KPI card
 * should render. The actual icon component lookup lives in
 * `DashboardMetrics.tsx` (the view layer) — this file stays
 * presentation-agnostic of React/JSX per its own boundary rules above.
 */
export type DashboardMetricIconKey = "reports" | "iocs" | "highRisk" | "coverage";

/**
 * Icon-badge accent tier. "neutral" is category identity only.
 * "severity" is reserved for High Risk Findings, and only when its
 * real count is greater than zero — see `toDashboardMetrics`.
 */
export type DashboardMetricAccent = "neutral" | "severity";

export interface DashboardMetric {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly iconKey: DashboardMetricIconKey;
  readonly accent: DashboardMetricAccent;
}

export interface DashboardRiskDistributionSlice {
  readonly severity: string;
  readonly label: string;
  readonly count: number;
}

export interface DashboardRecentInvestigationRow {
  readonly id: string;
  /**
   * The real persisted investigation ID, or `null` when the backend
   * summary row has none. Kept separate from `id` (which is always a
   * unique string, falling back to `unidentified-N` for React's key
   * prop) so the presentation layer can tell a genuinely navigable
   * row apart from one with no real Investigation Workspace target.
   */
  readonly investigationId: number | null;
  readonly name: string;
  readonly status: string;
  readonly statusTone: StatusTone;
  readonly severity: string;
  readonly severityTone: StatusTone;
  readonly updatedLabel: string;
}

export interface DashboardInvestigationWorkloadCount {
  readonly status: string;
  readonly label: string;
  readonly tone: StatusTone;
  readonly count: number;
}

export interface DashboardIocDistributionSlice {
  readonly iocType: string;
  readonly label: string;
  readonly count: number;
}

export interface DashboardViewModel {
  readonly metrics: DashboardMetric[];
  readonly investigationWorkload: DashboardInvestigationWorkloadCount[];
  readonly recentInvestigations: DashboardRecentInvestigationRow[];
  readonly riskDistribution: DashboardRiskDistributionSlice[];
  readonly iocDistribution: DashboardIocDistributionSlice[];
}

function humanize(value: string): string {
  return value
    .trim()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

function formatCoverage(value: number | null): string {
  return value === null ? "No data" : `${value}%`;
}

export function toDashboardMetrics(result: DashboardSummaryResult): DashboardMetric[] {
  return [
    {
      id: "total-reports",
      label: "Total Reports",
      value: formatCount(result.metrics.total_reports),
      iconKey: "reports",
      accent: "neutral",
    },
    {
      id: "total-iocs",
      label: "Total IOCs",
      value: formatCount(result.metrics.total_iocs),
      iconKey: "iocs",
      accent: "neutral",
    },
    {
      id: "high-risk-count",
      label: "High Risk Findings",
      value: formatCount(result.metrics.high_risk_count),
      iconKey: "highRisk",
      // A "0 High Risk Findings" card must not visually communicate
      // danger — only accent as severity when the real count is > 0.
      accent: result.metrics.high_risk_count > 0 ? "severity" : "neutral",
    },
    {
      id: "threat-intel-coverage",
      label: "Threat Intel Coverage",
      value: formatCoverage(result.metrics.threat_intel_coverage_percent),
      iconKey: "coverage",
      accent: "neutral",
    },
  ];
}

/**
 * Preserves the backend's actual investigation-status vocabulary. No
 * open/in-progress/closed workflow states are synthesized here.
 */
export function summarizeInvestigationWorkload(
  statusCounts: Readonly<Record<string, number>>,
): DashboardInvestigationWorkloadCount[] {
  return Object.entries(statusCounts)
    .map(([status, count]) => ({
      status,
      label: humanize(status),
      tone: statusTone(status),
      count,
    }))
    .sort((left, right) => left.status.localeCompare(right.status));
}

/**
 * Formats `analyzed_at` into a readable absolute date/time using the
 * existing `en-US` locale convention already used elsewhere in this
 * file (`formatCount`). Presentation-only: the underlying value and
 * its meaning are unchanged, and no relative ("2 hours ago") or
 * invented timezone semantics are introduced -- an unparseable value
 * falls back to the original raw string rather than fabricating one.
 */
function formatAnalyzedAt(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

function toRecentRow(investigation: InvestigationSummary, index: number): DashboardRecentInvestigationRow {
  const scored = isInvestigationScored(investigation.severity);
  const id = investigation.investigation_id !== null
    ? String(investigation.investigation_id)
    : `unidentified-${index}`;

  return {
    id,
    investigationId: investigation.investigation_id,
    name: investigation.report_name,
    status: investigation.status,
    statusTone: statusTone(investigation.status),
    severity: scored ? investigation.severity : "Not scored",
    severityTone: scored ? severityTone(investigation.severity) : "neutral",
    // The backend summary exposes analyzed_at, not a fabricated "updated"
    // field. Format it to a readable absolute date/time (presentation
    // only) instead of inventing a relative time or silently changing
    // its meaning.
    updatedLabel: formatAnalyzedAt(investigation.analyzed_at),
  };
}

export function toRecentInvestigations(
  investigations: readonly InvestigationSummary[],
): DashboardRecentInvestigationRow[] {
  return investigations.map(toRecentRow);
}

const RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;

export function toRiskDistribution(
  distribution: Readonly<Record<string, number>>,
): DashboardRiskDistributionSlice[] {
  const entries = Object.entries(distribution);
  return entries
    .sort(([left], [right]) => {
      const leftIndex = RISK_ORDER.indexOf(left.trim().toUpperCase() as (typeof RISK_ORDER)[number]);
      const rightIndex = RISK_ORDER.indexOf(right.trim().toUpperCase() as (typeof RISK_ORDER)[number]);
      if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right);
      if (leftIndex === -1) return 1;
      if (rightIndex === -1) return -1;
      return leftIndex - rightIndex;
    })
    .map(([severity, count]) => ({
      severity: severity.trim().toLowerCase(),
      label: humanize(severity),
      count,
    }));
}

export function toIocDistribution(
  distribution: Readonly<Record<string, number>>,
): DashboardIocDistributionSlice[] {
  return Object.entries(distribution)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([iocType, count]) => ({
      iocType,
      label: humanize(iocType),
      count,
    }));
}

// ---------------------------------------------------------------------------
// Investigation activity trend — the one real temporal series (MAX-5)
// ---------------------------------------------------------------------------

export interface DashboardActivityTrendPoint {
  /** `YYYY-MM-DD`, unchanged from the backend's real date key. */
  readonly date: string;
  /** Short, locale-formatted date label for display (e.g. "Sep 3"). */
  readonly label: string;
  readonly count: number;
}

/**
 * Formats a `YYYY-MM-DD` date key into a short display label. Falls
 * back to the raw key for anything that does not parse as a real
 * calendar date rather than fabricating a label.
 */
function formatActivityDateLabel(dateKey: string): string {
  const parsed = new Date(`${dateKey}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return dateKey;
  }
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(parsed);
}

/**
 * Maps the real, backend-verified `investigations_by_date` day-bucketed
 * counts (`compute_investigation_activity_by_date`,
 * `app/services/dashboard_aggregation.py`) into chronologically-sorted
 * points. Only dates the backend actually returned are included --
 * this deliberately does not zero-fill gaps between them into a
 * continuous "last N days" series, which would imply the backend
 * tracks a fixed reporting window it does not.
 */
export function toInvestigationActivityTrend(
  byDate: Readonly<Record<string, number>>,
): DashboardActivityTrendPoint[] {
  return Object.entries(byDate)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, count]) => ({
      date,
      label: formatActivityDateLabel(date),
      count,
    }));
}

export function toDashboardViewModel(result: DashboardSummaryResult): DashboardViewModel {
  return {
    metrics: toDashboardMetrics(result),
    investigationWorkload: summarizeInvestigationWorkload(result.investigation_status_counts),
    recentInvestigations: toRecentInvestigations(result.recent_investigations),
    riskDistribution: toRiskDistribution(result.risk_distribution),
    iocDistribution: toIocDistribution(result.ioc_distribution),
  };
}

// ---------------------------------------------------------------------------
// Existing real Dashboard boundaries — unchanged in behavior
// ---------------------------------------------------------------------------

const OPERATIONAL_STATUS_LABEL: Record<SidecarStatusView, string> = {
  unknown: "Unknown",
  starting: "Starting",
  connected: "Connected",
  disconnected: "Disconnected",
  restarting: "Restarting",
  failure: "Failure",
};

const OPERATIONAL_STATUS_TONE: Record<SidecarStatusView, StatusTone> = {
  unknown: "neutral",
  starting: "info",
  connected: "success",
  disconnected: "neutral",
  restarting: "warning",
  failure: "error",
};

export interface OperationalStatusViewModel {
  readonly label: string;
  readonly tone: StatusTone;
}

export function toOperationalStatusViewModel(
  status: SidecarStatusView,
): OperationalStatusViewModel {
  return {
    label: OPERATIONAL_STATUS_LABEL[status],
    tone: OPERATIONAL_STATUS_TONE[status],
  };
}

export interface DashboardQuickAction {
  readonly id: string;
  readonly label: string;
  readonly path: string;
  readonly icon: NavigationItem["icon"];
}

export function buildDashboardQuickActions(
  navigationItems: readonly NavigationItem[],
): DashboardQuickAction[] {
  return navigationItems
    .filter((item) => item.group === "primary" && item.id !== "dashboard")
    .map((item) => ({ id: item.id, label: item.label, path: item.path, icon: item.icon }));
}
