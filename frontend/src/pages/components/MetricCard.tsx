import type { ReactElement, ReactNode } from "react";
import "./Card.css";
import "./MetricCard.css";

/**
 * Restrained icon-badge accent tiers.
 *
 * "neutral" is a category-identity tint only, never implying a
 * security signal. "severity" is reserved for metrics that genuinely
 * represent a severity-tier signal (e.g. High Risk Findings when its
 * count is greater than zero) — callers gate this themselves rather
 * than MetricCard guessing at meaning from a raw value.
 */
export type MetricCardAccent = "neutral" | "severity";

export interface MetricCardProps {
  readonly label: string;
  readonly value: string;
  /** Short supporting context, e.g. "+3 since yesterday". Optional. */
  readonly trend?: string;
  /** Optional restrained icon badge. Rendered next to the label, not as a full-card treatment. */
  readonly icon?: ReactNode;
  /** Optional accent tier for the icon badge. Defaults to "neutral" when an icon is present. */
  readonly accent?: MetricCardAccent;
}

/**
 * A single labeled metric (Phase 4G-2 Part 3, §7/§12).
 *
 * Used by Dashboard and Risk for their KPI rows. `value` is a string,
 * not a number, on purpose: it keeps this component from doing any
 * formatting decisions — the mock-data layer already produced a
 * display-ready string (see §16, "mock data must ... use realistic
 * structure").
 *
 * `icon`/`accent` are optional and additive (Flagship Dashboard pass,
 * Step 2): omitting them leaves existing behavior/markup for `label`,
 * `value`, and `trend` completely unchanged.
 */
export function MetricCard({ label, value, trend, icon, accent }: MetricCardProps): ReactElement {
  const resolvedAccent = accent ?? "neutral";
  return (
    <div className="card metric-card">
      <div className="metric-card__header">
        <span className="metric-card__label">{label}</span>
        {icon ? (
          <span
            className={`metric-card__icon-badge metric-card__icon-badge--${resolvedAccent}`}
            aria-hidden="true"
          >
            {icon}
          </span>
        ) : null}
      </div>
      <span className="metric-card__value">{value}</span>
      {trend ? <span className="metric-card__trend">{trend}</span> : null}
    </div>
  );
}
