import type { ReactElement } from "react";
import { Card } from "../components/Card";
import type { DashboardRiskDistributionSlice } from "./dashboardViewModel";
import "./DashboardRiskOverview.css";

export interface DashboardRiskOverviewProps {
  readonly distribution: readonly DashboardRiskDistributionSlice[];
}

export function DashboardRiskOverview({ distribution }: DashboardRiskOverviewProps): ReactElement {
  const total = distribution.reduce((sum, slice) => sum + slice.count, 0);
  const maxCount = distribution.length > 0 ? Math.max(...distribution.map((slice) => slice.count)) : 0;

  return (
    <Card title="Risk Distribution" className="dashboard-page__risk">
      {distribution.length === 0 || maxCount === 0 ? (
        <p className="dashboard-page__empty">No risk data available.</p>
      ) : (
        <ul className="dashboard-risk-overview__list" aria-label="Risk distribution">
          {distribution.map((slice) => {
            const percentage = total > 0 ? Math.round((slice.count / total) * 100) : 0;
            const relativeWidth = (slice.count / maxCount) * 100;
            return (
              <li key={slice.severity} className="dashboard-risk-overview__row">
                <span className="dashboard-risk-overview__label">{slice.label}</span>
                <span
                  className="dashboard-risk-overview__bar-track"
                  role="progressbar"
                  aria-label={`${slice.label} risk findings`}
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={slice.count}
                >
                  <span
                    className={`dashboard-risk-overview__bar dashboard-risk-overview__bar--${slice.severity}`}
                    style={{ width: `${relativeWidth}%` }}
                  />
                </span>
                <span className="dashboard-risk-overview__count">
                  {slice.count.toLocaleString("en-US")}
                  <span className="dashboard-risk-overview__percentage">{percentage}%</span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
