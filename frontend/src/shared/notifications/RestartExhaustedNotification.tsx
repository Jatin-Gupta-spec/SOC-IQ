/**
 * Restart-exhausted notification — presentational foundation, Phase
 * 4G-4 Part 1.
 *
 * Consumes (does not own) the notification state established in this
 * checkpoint: `useRestartExhaustedNotification()`
 * (`useRestartExhaustedNotification.ts`) reads the frozen
 * `restartExhaustedNotification` store. This component adds no new
 * state and no sidecar-reading logic of its own — purely
 * presentational over what the store already exposes.
 *
 * # Scope (task brief §11)
 *
 * This is the Part 1 foundation surface only, not the final visual
 * treatment — no final placement in `AppShell`/`NavigationRegion`,
 * no dismiss-button styling pass, no toast-stack positioning. Part 2
 * ("Final Notification UI + Motion Integration") mounts and finishes
 * this. What's established here — the accessible markup, the motion
 * behavior, the dismiss wiring — does not need to be redone there.
 *
 * # Accessibility (task brief §8)
 *
 * A restart-exhausted condition is a hard failure the person actively
 * needs to know about right away (the sidecar has stopped trying to
 * recover on its own) — the "least disruptive correct semantic" for
 * that is `role="alert"` (an assertive live region), not the ambient
 * `role="status"` `SidecarStatusIndicator` already uses for routine
 * state ("§8: do not make every notification an alert" — this one
 * specific case warrants it; a future, lower-urgency notification
 * built on this same foundation would use `role="status"` instead).
 * The message text is the sole carrier of meaning — no color-only
 * signal — and the dismiss control has a real accessible name, not an
 * icon-only affordance.
 *
 * # Motion (task brief §9/§10)
 *
 * Reuses the existing `.transition-fade` utility class
 * (`styles/motion.css`, established Phase 4F/pre-existing to this
 * checkpoint) for its enter/exit opacity transition rather than
 * defining a second duration/easing pairing of its own — that utility
 * already consumes `--duration-fast`/`--easing-out` and already
 * degrades to `--duration-instant` under
 * `prefers-reduced-motion: reduce` (`motion.css`'s own existing
 * global rule). This component adds no motion logic of its own; it
 * only needs to render conditionally, which CSS opacity plus
 * `visible ? ... : null` already achieves without JS-driven animation
 * that would itself need a separate reduced-motion branch.
 *
 * # Post-dismiss focus restoration (MAX16-F-01)
 *
 * Dismissing this notification removes its own `Dismiss` button from
 * the DOM. Without help, a keyboard user who just activated that
 * button is left with `document.activeElement === document.body` —
 * their position in the page silently lost. This is a local,
 * component-scoped fix (no new global focus-management
 * infrastructure): a single ref remembers where focus meaningfully
 * was *before* the notification became visible, captured the moment
 * it appears (i.e. before the person has had a chance to tab onto
 * the `Dismiss` button itself, so that button can never end up as the
 * remembered target). When the notification's `visible` state flips
 * back to `false` — whether via the default `dismiss()` path or a
 * caller-supplied `onDismiss` override that also clears visibility —
 * an effect restores focus to that remembered element, provided it is
 * still connected to the document (`document.contains`); if it is
 * not (or none was ever captured, e.g. nothing had focus), focus
 * falls back to the first primary navigation link in
 * `NavigationRegion` (`.nav-sidebar__link`) — an existing, always
 * mounted, always keyboard-reachable control, chosen deliberately
 * over letting focus fall to `<body>` by accident. Every target is
 * revalidated with `document.contains` immediately before
 * `.focus()` is called, so a detached node is never focused.
 */

import { type ReactElement, useEffect, useRef } from "react";
import { useRestartExhaustedNotification } from "./useRestartExhaustedNotification";
import {
  restartExhaustedNotification,
  type RestartExhaustedNotificationStore,
} from "./restartExhaustedNotificationStore";
import "./RestartExhaustedNotification.css";

/**
 * Selector for the deliberate fallback focus target used when no
 * connected prior-focus element is available (MAX16-F-01 §5 Case B).
 * `.nav-sidebar__link` (`NavigationGroup.tsx`) is a real, always
 * present, always keyboard-focusable `<a>` — not a container that
 * would need an artificial `tabindex` to accept focus. Reading this
 * selector does not require any change to `AppShell`/
 * `NavigationRegion`/`NavigationGroup` themselves.
 */
const FALLBACK_FOCUS_SELECTOR = ".nav-sidebar__link";

/** True only for a still-connected, genuinely focusable element. */
function isConnectedFocusTarget(
  target: HTMLElement | null,
): target is HTMLElement {
  return target !== null && document.contains(target);
}

/** Resolves the deliberate fallback target (Case B), or null if even that is unavailable. */
function resolveFallbackFocusTarget(): HTMLElement | null {
  const fallback = document.querySelector<HTMLElement>(
    FALLBACK_FOCUS_SELECTOR,
  );
  return isConnectedFocusTarget(fallback) ? fallback : null;
}

export interface RestartExhaustedNotificationProps {
  /**
   * Test-injection point only, mirroring
   * `SidecarStatusIndicator`'s own `store` prop — production callers
   * never pass it.
   */
  readonly store?: RestartExhaustedNotificationStore;
  /**
   * Called when the person dismisses the notification. Defaults to
   * calling `dismiss()` on the resolved store, so a production
   * caller needs no wiring of its own; a test can override it to
   * assert dismissal without a full store round-trip.
   */
  readonly onDismiss?: () => void;
}

const MESSAGE = "Sidecar restart attempts exhausted";
const DESCRIPTION =
  "The sidecar process stopped responding and automatic restart attempts have been exhausted. It will not restart on its own.";

/**
 * Renders the restart-exhausted notification when the store's state
 * is `visible: true`, and renders nothing otherwise — this component
 * never renders an empty/placeholder shell, so it introduces no empty
 * landmark or empty live region into the page when there is nothing
 * to announce.
 */
export function RestartExhaustedNotification({
  store,
  onDismiss,
}: RestartExhaustedNotificationProps): ReactElement | null {
  const notification = useRestartExhaustedNotification(store);

  // Remembers where focus meaningfully was before this notification
  // appeared, so dismissal can return it there instead of stranding
  // it on `<body>`. See the "Post-dismiss focus restoration" doc
  // comment above for the full reasoning.
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const wasVisibleRef = useRef(false);

  useEffect(() => {
    const becameVisible = notification.visible && !wasVisibleRef.current;
    const becameHidden = !notification.visible && wasVisibleRef.current;

    if (becameVisible) {
      // Captured now, before the person has had any chance to tab
      // onto the Dismiss button that is about to render — so this
      // can never resolve to that button itself.
      const active = document.activeElement;
      previousFocusRef.current =
        active instanceof HTMLElement && active !== document.body
          ? active
          : null;
    }

    if (becameHidden) {
      const target = isConnectedFocusTarget(previousFocusRef.current)
        ? previousFocusRef.current
        : resolveFallbackFocusTarget();
      target?.focus();
      previousFocusRef.current = null;
    }

    wasVisibleRef.current = notification.visible;
  }, [notification.visible]);

  if (!notification.visible) {
    return null;
  }

  const handleDismiss = (): void => {
    if (onDismiss) {
      onDismiss();
      return;
    }
    (store ?? restartExhaustedNotification).dismiss();
  };

  return (
    <div
      className="restart-exhausted-notification transition-fade"
      role="alert"
    >
      <div className="restart-exhausted-notification__body">
        <p className="restart-exhausted-notification__title">{MESSAGE}</p>
        <p className="restart-exhausted-notification__description">
          {DESCRIPTION}
        </p>
      </div>
      <button
        type="button"
        className="restart-exhausted-notification__dismiss"
        onClick={handleDismiss}
        aria-label="Dismiss sidecar restart-exhausted notification"
      >
        Dismiss
      </button>
    </div>
  );
}
