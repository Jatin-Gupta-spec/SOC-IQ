/**
 * SOC-IQ Design System — Elevation Tokens
 * Ported 1:1 from `app/gui/design/tokens/elevation.py`.
 *
 * Elevation describes visual hierarchy (a level), not a specific
 * box-shadow implementation — the shadow values themselves live in
 * `shadow` (see `color.ts`) and are composed at the component layer,
 * same as the Python source's own stated intent.
 */

export const Elevation = {
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
  dialog: 4,
  overlay: 5,
} as const;

export const ZIndex = {
  background: 0,
  content: 100,
  sidebar: 200,
  header: 300,
  dropdown: 500,
  tooltip: 700,
  dialog: 900,
  notification: 1000,
} as const;

export type ElevationToken = typeof Elevation;
export type ZIndexToken = typeof ZIndex;
