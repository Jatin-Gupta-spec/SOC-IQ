import type { ReactElement } from "react";
import "./RouteLoadingFallback.css";
import { PageLayout } from "../pages/components/PageLayout";
import { SkeletonBlock } from "../pages/components/SkeletonBlock";
import { useReducedMotion } from "../shared/hooks/useReducedMotion";

export interface RouteLoadingFallbackProps {
  /** The destination's own accessible page name, e.g. "Reports" —
   * matches the `label` each page's own `PageLayout` call uses, so
   * the `<main aria-label="...">` landmark an assistive-tech user
   * sees does not change identity between the loading placeholder and
   * the real page once its chunk finishes loading. */
  readonly label: string;
}

/**
 * `Suspense` fallback for route-level code-splitting (MAX-8 Phase 2A,
 * MAX8-F-01).
 *
 * Each lazily-loaded route in `router.tsx` gets its own `<Suspense>`
 * boundary using this component as `fallback`, parameterized with
 * that route's own navigation label. This keeps the same `PageLayout`
 * landmark contract every real page already honors (MAX-1) intact
 * during the brief window a route's JS chunk is still being fetched,
 * rather than leaving the `<main>` landmark missing or mislabeled
 * while the network request is in flight. Content itself is a single
 * unlabeled `SkeletonBlock` (MAX-2's existing shared loading-block
 * idiom, already reduced-motion aware) — this is a route-transition
 * placeholder, not a content-shaped skeleton, so it does not attempt
 * to mimic any specific page's layout.
 */
export function RouteLoadingFallback({ label }: RouteLoadingFallbackProps): ReactElement {
  const reducedMotion = useReducedMotion();

  return (
    <PageLayout label={`${label} page`}>
      <p className="skeleton-status" role="status" aria-live="polite">
        {`Loading ${label}…`}
      </p>
      <SkeletonBlock className="route-loading-fallback__block" reducedMotion={reducedMotion} />
    </PageLayout>
  );
}
