/**
 * SOC-IQ Design System — Radius Tokens
 * Ported 1:1 from `app/gui/design/tokens/radius.py` (values in px).
 */

const none = 0;
const xs = 2;
const sm = 4;
const md = 6;
const lg = 8;
const xl = 12;
const xxl = 16;
const circle = 999;

export const Radius = {
  none,
  xs,
  sm,
  md,
  lg,
  xl,
  xxl,
  circle,

  // Semantic aliases (mirrors the Python class attributes)
  button: md,
  input: md,
  badge: sm,
  chip: xl,
  card: lg,
  panel: lg,
  dialog: xl,
  tooltip: sm,
} as const;

export type RadiusToken = typeof Radius;
