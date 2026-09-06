import type { ReactElement } from "react";
import "./Skeleton.css";

export interface SkeletonBlockProps {
  /** Extra class name for page-specific sizing/placement. */
  readonly className?: string;
  /** From `useReducedMotion()` -- when true, renders the static block
   * with no pulse animation, matching the Dashboard/Investigation
   * Workspace skeletons' existing reduced-motion behavior. */
  readonly reducedMotion: boolean;
}

/**
 * Shared structural loading-skeleton block (MAX-2, Part 5).
 *
 * A single unlabeled, `aria-hidden` placeholder rectangle using the
 * same tokens/pulse idiom Dashboard and Investigation Workspace each
 * already established independently. Intentionally minimal -- it owns
 * no layout, grid, or semantics of its own; callers arrange blocks
 * into their own page-specific skeleton shape via `className`, the
 * same way Dashboard and Workspace already do. This is not a generic
 * "everything skeleton" -- it does not render text, labels, counts,
 * or any content-shaped abstraction, only the shared visual treatment.
 */
export function SkeletonBlock({ className, reducedMotion }: SkeletonBlockProps): ReactElement {
  const classes = reducedMotion
    ? `skeleton-block ${className ?? ""}`.trim()
    : `skeleton-block skeleton-block--pulse ${className ?? ""}`.trim();

  return <div className={classes} aria-hidden="true" />;
}
