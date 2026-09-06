/**
 * React hook consumer for `SettingsNavigationGuardStore` -- SOC-IQ
 * MAX-18 Phase 2A-3.
 *
 * Same shape and reasoning as
 * `shared/notifications/useRestartExhaustedNotification.ts`:
 * `useSyncExternalStore` over the one already-existing store instance
 * (`settingsNavigationGuard`), so the calling component (the
 * confirmation dialog) always reads a synchronously-current value and
 * survives React 18 concurrent rendering / Strict Mode's
 * double-effect invocation without a hand-rolled `useState`/`useEffect`
 * pair tearing. This hook owns no state and no subscription
 * bookkeeping of its own -- both remain the store's sole
 * responsibility.
 */

import { useSyncExternalStore } from "react";
import {
  settingsNavigationGuard,
  type SettingsNavigationGuardState,
  type SettingsNavigationGuardStore,
} from "./settingsNavigationGuardStore";

/**
 * Returns the current pending-confirmation state and re-renders the
 * calling component whenever it changes.
 *
 * `store` exists only as a test-injection point, mirroring
 * `useRestartExhaustedNotification`'s own `store` parameter --
 * production call sites never pass it.
 */
export function useSettingsNavigationGuardState(
  store: SettingsNavigationGuardStore = settingsNavigationGuard,
): SettingsNavigationGuardState {
  return useSyncExternalStore(
    (onStoreChange) => store.subscribe(() => onStoreChange()),
    () => store.getState(),
    () => store.getState(),
  );
}
