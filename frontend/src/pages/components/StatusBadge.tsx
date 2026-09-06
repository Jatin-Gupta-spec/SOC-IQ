import type { ReactElement } from "react";
import "./StatusBadge.css";

/**
 * The badge's visual tone. Deliberately a small closed set mapped to
 * existing `status`/`severity`/`verdict` color tokens by CSS class,
 * not a free-form color prop — see §17, "do not introduce arbitrary
 * colors".
 */
export type StatusTone =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "error"
  | "critical";

export interface StatusBadgeProps {
  readonly label: string;
  readonly tone: StatusTone;
}

/**
 * Generic status/severity/verdict indicator (Phase 4G-2 Part 3, §17/§20).
 *
 * Shared across Investigations (status), IOC Explorer (verdict),
 * Threat Intel (TI_STATE_*), Risk (severity), and Reports (status) so
 * those five pages don't each invent their own badge markup. Per
 * §20, status is never color-only: the tone sets background/text
 * color, but the label text is what actually carries the meaning, so
 * the badge reads correctly in grayscale or to a screen reader.
 */
export function StatusBadge({ label, tone }: StatusBadgeProps): ReactElement {
  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}
