/**
 * `useSettingsNavigationGuardSync` -- SOC-IQ MAX-18 Phase 2A-3
 * (MAX18-F-01, in-app SPA navigation guard).
 *
 * The one piece of wiring `SettingsPage` needs to add for the
 * navigation guard to work at all: forwarding the page's own
 * `settingsDirty` aggregate (Phase 2A-2, `useSettingsPageDirty`) into
 * `settingsNavigationGuard`, the singleton `NavigationGroup` and
 * `CommandPaletteContainer` actually read from. No new dirty *logic*
 * is introduced here -- this hook only ever forwards a boolean it is
 * given.
 *
 * Two effects, two different jobs:
 *
 *   1. Forward `settingsDirty` to the store on every change, so the
 *      guard's view of "is Settings dirty" never lags behind the
 *      page's own aggregate by more than one render.
 *   2. Unconditionally clear the store's dirty flag on unmount --
 *      regardless of *why* `SettingsPage` unmounted (a guard-confirmed
 *      Leave, which `confirmLeave()` already clears itself; a route
 *      change the guard did not need to intercept because Settings
 *      was clean; or, in principle, any other unmount). This is what
 *      prevents stale dirty state (task brief's explicit
 *      requirement): there is no way for `dirty` to remain `true` in
 *      the store once no `SettingsPage` instance is mounted to back
 *      it, so a later, unrelated navigation from a different page can
 *      never be spuriously blocked by a previous visit's leftover
 *      state.
 *
 * A fresh mount of `SettingsPage` gets a fresh `useSettingsPageDirty`
 * instance (Phase 2A-2's own guarantee) *and* arrives at a guard
 * store already guaranteed clean by the previous instance's unmount
 * cleanup -- so re-entering Settings after leaving it clean is itself
 * never treated as dirty.
 */
import { useEffect } from "react";
import {
  settingsNavigationGuard,
  type SettingsNavigationGuardStore,
} from "./settingsNavigationGuardStore";

export function useSettingsNavigationGuardSync(
  settingsDirty: boolean,
  store: SettingsNavigationGuardStore = settingsNavigationGuard,
): void {
  useEffect(() => {
    store.setDirty(settingsDirty);
  }, [settingsDirty, store]);

  // Deliberately its own effect, with an empty-except-`store`
  // dependency array, so its cleanup runs exactly once -- on this
  // `SettingsPage` instance's real unmount -- rather than on every
  // `settingsDirty` change the effect above already handles.
  useEffect(() => {
    return () => {
      store.setDirty(false);
    };
  }, [store]);
}
