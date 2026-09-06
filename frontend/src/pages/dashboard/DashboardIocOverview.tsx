import type { ReactElement } from "react";
import { Card } from "../components/Card";
import type { DashboardIocDistributionSlice } from "./dashboardViewModel";
import "./DashboardIocOverview.css";

export interface DashboardIocOverviewProps {
  readonly distribution: readonly DashboardIocDistributionSlice[];
}

/**
 * Deterministic IOC type → chart color modifier mapping.
 *
 * Maps the real, normalized `ioc_type` keys the backend extractor
 * produces (see `app/extractor.py`'s `IOC_PATTERNS`) to a small set of
 * `--color-chart-*` hues. Intentionally avoids the severity register
 * (green/yellow/orange/red) so an IOC-type color is never mistaken for
 * a severity signal. Any type not explicitly listed here (e.g. CVEs,
 * file paths, registry keys) falls back to "other".
 */
const IOC_TYPE_MODIFIERS: Readonly<Record<string, string>> = {
  ipv4: "ipv4",
  domains: "domain",
  urls: "url",
  emails: "email",
  md5: "hash",
  sha1: "hash",
  sha256: "hash",
};

function iocTypeModifier(iocType: string): string {
  return IOC_TYPE_MODIFIERS[iocType.trim().toLowerCase()] ?? "other";
}

export function DashboardIocOverview({ distribution }: DashboardIocOverviewProps): ReactElement {
  const total = distribution.reduce((sum, slice) => sum + slice.count, 0);
  const maxCount = distribution.length > 0 ? Math.max(...distribution.map((slice) => slice.count)) : 0;

  return (
    <Card title="IOC Distribution" className="dashboard-page__ioc">
      {distribution.length === 0 || maxCount === 0 ? (
        <p className="dashboard-page__empty">No IOC data available.</p>
      ) : (
        <ul className="dashboard-ioc-overview__list" aria-label="IOC type distribution">
          {distribution.map((slice) => {
            const percentage = total > 0 ? Math.round((slice.count / total) * 100) : 0;
            const relativeWidth = (slice.count / maxCount) * 100;
            return (
              <li key={slice.iocType} className="dashboard-ioc-overview__row">
                <span className="dashboard-ioc-overview__label">{slice.label}</span>
                <span
                  className="dashboard-ioc-overview__bar-track"
                  role="progressbar"
                  aria-label={`${slice.label} IOCs`}
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={slice.count}
                >
                  <span
                    className={`dashboard-ioc-overview__bar dashboard-ioc-overview__bar--${iocTypeModifier(slice.iocType)}`}
                    style={{ width: `${relativeWidth}%` }}
                  />
                </span>
                <span className="dashboard-ioc-overview__count">
                  {slice.count.toLocaleString("en-US")}
                  <span className="dashboard-ioc-overview__percentage">{percentage}%</span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
