import type { ReactElement } from "react";
import { MetricCard } from "../components/MetricCard";
import {
  IocExplorerIcon,
  ReportsIcon,
  RiskIcon,
  ThreatIntelIcon,
} from "../../app/navigation/icons";
import type { DashboardMetric, DashboardMetricIconKey } from "./dashboardViewModel";
import "./DashboardMetrics.css";

export interface DashboardMetricsProps {
  readonly metrics: readonly DashboardMetric[];
}

/**
 * Reuses the existing hand-rolled navigation icon set rather than
 * authoring near-duplicate icons — each KPI's icon matches the same
 * icon already used for the related nav destination (Reports, IOC
 * Explorer, Risk, Threat Intel), which keeps the icon vocabulary
 * consistent across the app instead of introducing a second one.
 */
const METRIC_ICONS: Readonly<Record<DashboardMetricIconKey, ReactElement>> = {
  reports: <ReportsIcon />,
  iocs: <IocExplorerIcon />,
  highRisk: <RiskIcon />,
  coverage: <ThreatIntelIcon />,
};

export function DashboardMetrics({ metrics }: DashboardMetricsProps): ReactElement {
  return (
    <div className="dashboard-metrics" role="list">
      {metrics.map((metric) => (
        <div className="dashboard-metrics__item" role="listitem" key={metric.id}>
          <MetricCard
            label={metric.label}
            value={metric.value}
            icon={METRIC_ICONS[metric.iconKey]}
            accent={metric.accent}
          />
        </div>
      ))}
    </div>
  );
}
