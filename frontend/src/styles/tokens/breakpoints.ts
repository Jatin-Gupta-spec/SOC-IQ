/**
 * SOC-IQ Design System — Breakpoint Tokens
 *
 * NOT ported from Python (the PySide6 GUI has no CSS-style breakpoint
 * concept). These two values are taken directly from
 * `docs/architecture/13-frontend-information-architecture.md`'s stated
 * target window sizes — not invented — since SOC-IQ is a fixed-window
 * desktop app, not a responsive site: "the dashboard targets 1440x900
 * without vertical scrolling... At 1280x720, the same grid collapses
 * the timeline panel into a secondary tab."
 *
 * `NON_NEGOTIABLE_RULES.md` #19: layout problems are solved by
 * re-composing the grid at these two tiers, never by adding
 * page-level scroll.
 */

export const Breakpoint = {
  /** Minimum supported window width (1280x720 tier). */
  compact: 1280,
  /** Primary target window width (1440x900 tier). */
  standard: 1440,
} as const;

export type BreakpointToken = typeof Breakpoint;
