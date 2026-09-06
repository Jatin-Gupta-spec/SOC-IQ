/**
 * Dashboard mock domain data (Phase 4G-2 Part 3, §7/§15/§16; revised
 * Phase 4H Part 2 §7/§21 defect fix).
 *
 * Isolated from any production API/DTO shape — these types exist
 * only to drive the mock Dashboard page and are not shared with
 * `shared/api`. All values are static (no `Date.now()`, no
 * `Math.random()`) so rendering and tests stay deterministic.
 *
 * # Part 2 audit finding (fixed here)
 *
 * The Part 1 checkpoint redeclared its own `status`/`severity` union
 * types inline on `RecentInvestigationSummary` — an exact duplicate of
 * vocabulary that already existed elsewhere: `InvestigationStatus`/
 * `Severity` in `mock/investigations.ts`. Task brief §7: "Do NOT
 * create a competing Severity/Risk enum if one already exists." This
 * revision imports it instead of redeclaring it, and derives the
 * Dashboard's "recent investigations" from the one canonical
 * `mockInvestigations` list rather than maintaining a second,
 * separately-hand-copied array that could silently drift from it.
 *
 * # PD-06 cleanup (Part 3)
 *
 * `mock/risk.ts` and this file's `mockRiskDistribution` re-export of
 * its `mockRiskSeverityDistribution` were removed: the standalone
 * Risk page that consumed them was retired, and the real Dashboard
 * (`DashboardRiskOverview.tsx`) sources its risk distribution from the
 * backend's `get_dashboard_summary` command, not from mock data.
 */

import type { InvestigationStatus, Severity } from "./investigations";
import { mockInvestigations } from "./investigations";

export type { InvestigationStatus, Severity };

export interface DashboardMetric {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly trend?: string;
}

/** The Dashboard's recent-investigations row shape — a subset of the canonical `InvestigationSummary` fields (`mock/investigations.ts`), not a competing shape. */
export interface RecentInvestigationSummary {
  readonly id: string;
  readonly name: string;
  readonly status: InvestigationStatus;
  readonly severity: Severity;
  readonly updatedLabel: string;
}

export const mockDashboardMetrics: DashboardMetric[] = [
  { id: "active-investigations", label: "Active Investigations", value: "7", trend: "+2 this week" },
  { id: "high-risk-findings", label: "High Risk Findings", value: "12", trend: "+3 since yesterday" },
  { id: "iocs-observed", label: "IOCs Observed", value: "184", trend: "+21 this week" },
  { id: "ti-coverage", label: "Threat Intel Coverage", value: "68%", trend: "of observed IOCs" },
];

/**
 * The 5 most recently updated investigations, derived from the one
 * canonical `mockInvestigations` list (`mock/investigations.ts`) —
 * that list is already ordered most-recent-first (see its own
 * `updatedLabel` values), so this is a straight `slice`, not a
 * re-sort or a hand-maintained duplicate.
 */
export const mockRecentInvestigations: RecentInvestigationSummary[] = mockInvestigations
  .slice(0, 5)
  .map(({ id, name, status, severity, updatedLabel }) => ({ id, name, status, severity, updatedLabel }));
