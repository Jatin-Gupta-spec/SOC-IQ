/**
 * Sidecar status indicator — Phase 4G-3 Part 2.
 *
 * Consumes (does not own) the sidecar status established in Part 1:
 * `useSidecarStatus()` (`shared/sidecar/useSidecarStatus.ts`) reads
 * the frozen `sidecarProjection` store, and
 * `projectSidecarStatusView()` (`shared/sidecar/sidecarStatusView.ts`)
 * normalizes that into the closed six-value vocabulary Part 1 already
 * defined (`unknown` / `starting` / `connected` / `disconnected` /
 * `restarting` / `failure`). This component adds no new state, no new
 * vocabulary, and no backend/reconciler calls of its own — it is
 * purely presentational over what Part 1 already exposes (task brief
 * §5/§7).
 *
 * # Location (task brief §4)
 *
 * Rendered at the bottom of the sidebar by `NavigationRegion`
 * (`app/shell/NavigationRegion.tsx`) — a single, stable, always-
 * visible location, not a second global status architecture. This
 * file itself has no opinion on where it's mounted; it is a self-
 * contained component precisely so `NavigationRegion` can place it
 * without either file needing to know about the other's internals
 * beyond a normal import.
 *
 * # Design tokens (task brief §8)
 *
 * Reuses the existing semantic `--color-status-*` tokens
 * (`styles/tokens.css`) exactly as `StatusBadge`
 * (`pages/components/StatusBadge.tsx`) already does for other status
 * surfaces in this codebase — success/warning/error/info map
 * one-to-one onto connected/restarting/failure/starting, with
 * `--color-text-muted` (already used for muted/secondary text
 * elsewhere) for the two non-alarming neutral states, `unknown` and
 * `disconnected`. No new token was needed or added.
 *
 * # Accessibility (task brief §6)
 *
 * The status is never color-only: the tone dot is purely decorative
 * (`aria-hidden`) and every piece of meaning lives in the visible text
 * label, which doubles as the element's accessible name (no redundant
 * `aria-label` duplicating visible text). The wrapper uses
 * `role="status"` + `aria-live="polite"` — the one piece of ARIA this
 * component actually needs, since a transition here (e.g. connected
 * -> restarting) is exactly the kind of out-of-band update assistive
 * tech should be told about without the user needing to go looking
 * for it; nothing else here adds ARIA beyond that.
 */

import type { ReactElement } from "react";
import { useSidecarStatus } from "../sidecar/useSidecarStatus";
import type { SidecarProjectionStore } from "../sidecar/projectionStore";
import {
  projectSidecarStatusView,
  type SidecarStatusView,
} from "../sidecar/sidecarStatusView";
import "./SidecarStatusIndicator.css";

const STATUS_VIEW_LABEL: Record<SidecarStatusView, string> = {
  unknown: "Sidecar status unknown",
  starting: "Sidecar starting",
  connected: "Sidecar connected",
  disconnected: "Sidecar disconnected",
  restarting: "Sidecar restarting",
  failure: "Sidecar unavailable",
};

export interface SidecarStatusIndicatorProps {
  /**
   * Test-injection points only, mirroring `useSidecarStatus`'s own
   * `store` parameter — production callers never pass either. `view`
   * bypasses the consumer entirely for pure presentational tests
   * (`SidecarStatusIndicator.test.tsx`); `store` instead wires a real
   * (but test-local, non-singleton) `SidecarProjectionStore` through
   * to `useSidecarStatus()` for live state-transition/subscription
   * tests (`SidecarStatusIndicator.live.test.tsx`). If both are
   * given, `view` wins.
   */
  readonly view?: SidecarStatusView;
  readonly store?: SidecarProjectionStore;
}

/**
 * Renders the current sidecar status as a small tone dot (decorative)
 * plus a readable text label (the actual, and only required, carrier
 * of meaning — task brief §6). Presentational: reads the Part 1
 * consumer via `useSidecarStatus()` unless a `view` is supplied
 * directly for testing, and owns no lifecycle logic of its own.
 */
export function SidecarStatusIndicator({
  view,
  store,
}: SidecarStatusIndicatorProps): ReactElement {
  const projectedState = useSidecarStatus(store);
  const resolvedView = view ?? projectSidecarStatusView(projectedState);
  const label = STATUS_VIEW_LABEL[resolvedView];

  return (
    <div
      className="sidecar-status"
      role="status"
      aria-live="polite"
      data-sidecar-status-view={resolvedView}
    >
      <span
        className={`sidecar-status__dot sidecar-status__dot--${resolvedView}`}
        aria-hidden="true"
      />
      <span className="sidecar-status__label">{label}</span>
    </div>
  );
}
