/**
 * SOC-IQ Design System — Opacity Tokens
 * Ported 1:1 from `app/gui/design/tokens/opacity.py`.
 */

export const Opacity = {
  transparent: 0.0,
  subtle: 0.1,
  hover: 0.15,
  selected: 0.2,
  disabled: 0.4,
  muted: 0.6,
  overlay: 0.75,
  opaque: 1.0,
} as const;

export type OpacityToken = typeof Opacity;
