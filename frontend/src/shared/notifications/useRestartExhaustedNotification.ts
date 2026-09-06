/**
 * React hook consumer for `RestartExhaustedNotificationStore` — Phase
 * 4G-4 Part 1.
 *
 * Same shape and reasoning as `shared/sidecar/useSidecarStatus.ts`:
 * `useSyncExternalStore` over the one already-existing store instance
 * (`restartExhaustedNotification`), so the calling component always
 * reads a synchronously-current value (no stale flash before the
 * first effect) and survives React 18 concurrent rendering / Strict
 * Mode's double-effect invocation without a hand-rolled
 * `useState`/`useEffect` pair tearing. This hook owns no state and no
 * subscription bookkeeping of its own — both remain the store's sole
 * responsibility.
 */

import { useSyncExternalStore } from "react";
import {
  restartExhaustedNotification,
  type RestartExhaustedNotificationState,
  type RestartExhaustedNotificationStore,
} from "./restartExhaustedNotificationStore";

/**
 * Returns the current restart-exhausted notification state and
 * re-renders the calling component whenever it changes. Does not
 * initialize or dispose the store (that remains the composition
 * root's responsibility, mirroring `sidecarLifecycle.ts`'s own
 * pattern) — this hook only ever reads and subscribes.
 *
 * `store` exists only as a test-injection point, mirroring
 * `useSidecarStatus`'s own `store` parameter — production call sites
 * never pass it.
 */
export function useRestartExhaustedNotification(
  store: RestartExhaustedNotificationStore = restartExhaustedNotification,
): RestartExhaustedNotificationState {
  return useSyncExternalStore(
    (onStoreChange) => store.subscribe(() => onStoreChange()),
    () => store.getState(),
    () => store.getState(),
  );
}
