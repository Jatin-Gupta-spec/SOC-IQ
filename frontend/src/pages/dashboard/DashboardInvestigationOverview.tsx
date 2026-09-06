import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import type { DashboardInvestigationWorkloadCount } from "./dashboardViewModel";
import "./DashboardInvestigationOverview.css";

export interface DashboardInvestigationOverviewProps {
  readonly workload: readonly DashboardInvestigationWorkloadCount[];
}

export function DashboardInvestigationOverview({
  workload,
}: DashboardInvestigationOverviewProps): ReactElement {
  const total = workload.reduce((sum, entry) => sum + entry.count, 0);
  const maxCount = workload.length > 0 ? Math.max(...workload.map((entry) => entry.count)) : 0;

  return (
    <Card title="Investigation Overview" className="dashboard-page__investigation-overview">
      {workload.length === 0 ? (
        <p className="dashboard-page__empty">No investigation status data available.</p>
      ) : (
        <div>
          <div className="dashboard-investigation-overview__summary">
            <span className="dashboard-investigation-overview__total">{total.toLocaleString("en-US")}</span>
            <span className="dashboard-investigation-overview__summary-label">investigations</span>
          </div>
          <ul className="dashboard-investigation-overview__list" aria-label="Investigation status distribution">
            {workload.map((entry) => {
              const percentage = total > 0 ? (entry.count / total) * 100 : 0;
              const relativeWidth = maxCount > 0 ? (entry.count / maxCount) * 100 : 0;
              return (
                <li key={entry.status} className="dashboard-investigation-overview__row">
                  <div className="dashboard-investigation-overview__row-header">
                    <StatusBadge label={entry.label} tone={entry.tone} />
                    <span className="dashboard-investigation-overview__count">
                      {entry.count.toLocaleString("en-US")}
                      <span className="dashboard-investigation-overview__percentage">
                        {Math.round(percentage)}%
                      </span>
                    </span>
                  </div>
                  <div
                    className="dashboard-investigation-overview__bar-track"
                    role="progressbar"
                    aria-label={`${entry.label} investigations`}
                    aria-valuemin={0}
                    aria-valuemax={total}
                    aria-valuenow={entry.count}
                  >
                    <span
                      className="dashboard-investigation-overview__bar"
                      style={{ width: `${relativeWidth}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}
