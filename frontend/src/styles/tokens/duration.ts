/**
 * SOC-IQ Design System — Duration Tokens
 * Ported 1:1 from `app/gui/design/tokens/duration.py` (values in ms).
 *
 * This is the ONE duration-token system for the frontend — see
 * `docs/architecture/12-motion-animation-architecture.md` and
 * `NON_NEGOTIABLE_RULES.md` #23 ("no duplicate sources of truth").
 * The doc's proposed 100/150/250/400ms "micro/small/base/large" scale
 * is NOT used here instead of this ported one; this ported scale is
 * the reconciliation — it already covers the same shape (fastest=100,
 * faster=150, normal=250) plus the semantic aliases the Python side
 * already established.
 */

const instant = 0;
const fastest = 100;
const faster = 150;
const fast = 200;
const normal = 250;
const slow = 350;
const slower = 500;
const slowest = 750;

export const Duration = {
  instant,
  fastest,
  faster,
  fast,
  normal,
  slow,
  slower,
  slowest,

  // Semantic aliases (mirrors the Python class attributes)
  hover: fast,
  buttonPress: faster,
  tooltip: fast,
  sidebar: normal,
  cardLift: normal,
  pageTransition: slow,
  dialog: slow,
  toast: slower,
  loading: slowest,
} as const;

export type DurationToken = typeof Duration;
