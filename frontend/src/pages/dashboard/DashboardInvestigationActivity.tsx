import type { ReactElement } from "react";
import { Card } from "../components/Card";
import type { DashboardActivityTrendPoint } from "./dashboardViewModel";
import "./DashboardInvestigationActivity.css";

export interface DashboardInvestigationActivityProps {
  readonly trend: readonly DashboardActivityTrendPoint[];
}

/**
 * Investigation Activity — MAX-5's one legitimate trend visualization.
 *
 * Sources `investigations_by_date`, the one real, backend-verified
 * temporal series SOC-IQ exposes today (see
 * `toInvestigationActivityTrend`'s own doc comment). This is
 * deliberately investigation *volume* by date, not a risk trend or an
 * IOC trend -- no backend aggregate for either of those exists, so
 * neither is rendered here or anywhere else on the Dashboard.
 *
 * Follows the same accessible bar idiom already established by
 * `DashboardRiskOverview`/`DashboardIocOverview`: every bar carries a
 * `role="progressbar"` with real min/max/now values, and the exact
 * count is always shown as text next to the bar -- an analyst never
 * has to visually estimate a bar's height to get the number.
 */
export function DashboardInvestigationActivity({
  trend,
}: DashboardInvestigationActivityProps): ReactElement {
  const maxCount = trend.length > 0 ? Math.max(...trend.map((point) => point.count)) : 0;

  return (
    <Card title="Investigation Activity" className="dashboard-page__activity">
      {trend.length === 0 || maxCount === 0 ? (
        <p className="dashboard-page__empty">No investigation activity data available.</p>
      ) : (
        <div className="dashboard-activity__chart" aria-label="Investigations analyzed by date">
          {trend.map((point) => {
            const relativeHeight = (point.count / maxCount) * 100;
            return (
              <div key={point.date} className="dashboard-activity__column">
                <span className="dashboard-activity__count">{point.count.toLocaleString("en-US")}</span>
                <span
                  className="dashboard-activity__bar-track"
                  role="progressbar"
                  aria-label={`Investigations analyzed on ${point.label}`}
                  aria-valuemin={0}
                  aria-valuemax={maxCount}
                  aria-valuenow={point.count}
                >
                  <span
                    className="dashboard-activity__bar"
                    style={{ height: `${relativeHeight}%` }}
                  />
                </span>
                <span className="dashboard-activity__label">{point.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
