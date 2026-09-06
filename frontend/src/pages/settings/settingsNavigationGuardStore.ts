/**
 * `SettingsNavigationGuardStore` -- SOC-IQ MAX-18 Phase 2A-3
 * (MAX18-F-01, in-app SPA navigation guard).
 *
 * Phase 2A-2 (`useSettingsPageDirty.ts`) produced a correct, tested
 * `settingsDirty` aggregate, but scoped entirely inside one
 * `SettingsPage` instance's own local `useState` -- nothing outside
 * that component tree (the sidebar in `NavigationRegion`, the command
 * palette in `CommandPaletteContainer`, both siblings of the routed
 * page under `AppShell`, not descendants of it) could read it. This
 * store is the one small bridge that closes that gap: a
 * Settings-specific singleton, not a generic cross-page
 * unsaved-changes framework -- it knows nothing about any page other
 * than Settings, and its entire public surface is the two questions a
 * navigation trigger and a confirmation dialog actually need
 * answered: "is Settings currently dirty" and "has the person decided
 * to leave anyway".
 *
 * Deliberately class-based and singleton-exported, mirroring
 * `RestartExhaustedNotificationStore`
 * (`shared/notifications/restartExhaustedNotificationStore.ts`)'s own
 * reasoning: production call sites (`NavigationGroup`,
 * `CommandPaletteContainer`, `SettingsNavigationGuardDialog`) share
 * the one `settingsNavigationGuard` instance below, while tests
 * construct their own isolated instance instead of needing a reset
 * hatch on shared module state.
 *
 * # Why a store, not React context (task brief's "no generic global
 * unsaved-changes framework" boundary)
 *
 * A context provider would need to wrap both the sidebar and the
 * routed content above their nearest common ancestor (`AppShell`),
 * which -- unlike this narrow, purpose-built store -- reads as
 * exactly the "global navigation architecture" the brief says not to
 * build. This module exports a plain object with four methods and no
 * dependency on where in the tree it is read from; `NavigationGroup`
 * and `CommandPaletteContainer` import it directly, the same way
 * `RestartExhaustedNotification.tsx` imports its own store directly
 * rather than threading it through props from `App.tsx`.
 *
 * # Decision-before-commit (task brief's core requirement)
 *
 * `requestNavigation()` is the single point every navigation trigger
 * must call *before* performing the actual route change. It never
 * navigates itself -- it only returns `"allowed"` (the caller may
 * proceed exactly as it would have with no guard at all) or
 * `"blocked"` (the caller must not navigate; a confirmation is now
 * pending). This is what keeps the destination from ever being
 * committed before the decision: the guard is consulted first, and
 * the two real call sites (`NavigationGroup`'s `NavLink` `onClick`,
 * `CommandPaletteContainer`'s `handleNavigate`) both structurally
 * cannot reach their own `navigate()`/default-link-follow step when
 * this returns `"blocked"`.
 *
 * # Stale dirty state (task brief's explicit "must not use stale
 * dirty state")
 *
 * `dirty` is written only by `useSettingsNavigationGuardSync`
 * (`useSettingsNavigationGuardSync.ts`), which sets it on every
 * `settingsDirty` change *and* clears it unconditionally on
 * `SettingsPage` unmount -- for any reason, guarded or not. That is
 * what guarantees `dirty` can never outlive the `SettingsPage`
 * instance it describes: there is no code path that leaves it `true`
 * while no `SettingsPage` is mounted, so a later, unrelated
 * navigation from a different page can never be spuriously blocked.
 * `confirmLeave()` (below) additionally clears it itself, ahead of
 * the unmount effect that is about to run anyway, so the guard is
 * inert immediately once "Leave" is chosen -- not just eventually.
 *
 * # No navigate-then-undo (task brief's explicit prohibition)
 *
 * This store never calls `history.back()`/`pushState()`/any
 * navigation API itself, and never inspects or reacts to a
 * `popstate`/`hashchange` event. It only ever answers "allowed" or
 * "blocked" for a navigation a caller has not yet performed. Browser
 * back/forward and direct hash edits fire `popstate` only *after* the
 * URL and history stack have already changed -- there is no
 * synchronous, cancellable hook into that under the current
 * `HashRouter`/declarative-router architecture (`App.tsx`) short of
 * committing the navigation and then reverting it, which this
 * checkpoint's brief explicitly forbids and which this module does
 * not attempt. See `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-3.md`'s
 * "Known limitations" for the full accounting of what this does and
 * does not cover.
 */

export const SETTINGS_NAVIGATION_PATH = "/settings";

/**
 * `pending: false` -- no confirmation currently owed to the person;
 * `pending: true` -- a blocked navigation is awaiting Stay/Leave,
 * carrying the destination that was attempted so `confirmLeave()`
 * knows where to send the caller.
 */
export type SettingsNavigationGuardState =
  | { readonly pending: false }
  | { readonly pending: true; readonly targetPath: string };

export type SettingsNavigationGuardListener = (
  state: SettingsNavigationGuardState,
) => void;

/**
 * `"allowed"` -- the caller may navigate immediately, exactly as it
 * would with no guard. `"blocked"` -- the caller must not navigate;
 * `getState()` now reflects the pending confirmation instead.
 */
export type SettingsNavigationGuardDecision = "allowed" | "blocked";

const CLEAN_STATE: SettingsNavigationGuardState = { pending: false };

export class SettingsNavigationGuardStore {
  private dirty = false;
  private state: SettingsNavigationGuardState = CLEAN_STATE;
  private readonly listeners = new Set<SettingsNavigationGuardListener>();

  // -----------------------------------------------------------------
  // Read API
  // -----------------------------------------------------------------

  getState(): SettingsNavigationGuardState {
    return this.state;
  }

  /** Exposed for tests/diagnostics only -- production decisions all
   * go through `requestNavigation()`, never a direct read of this. */
  isDirty(): boolean {
    return this.dirty;
  }

  // -----------------------------------------------------------------
  // Subscription (mirrors `RestartExhaustedNotificationStore`)
  // -----------------------------------------------------------------

  subscribe(listener: SettingsNavigationGuardListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  // -----------------------------------------------------------------
  // Write API -- dirty-state sync (called only by
  // `useSettingsNavigationGuardSync`)
  // -----------------------------------------------------------------

  /**
   * Records whether the currently-mounted `SettingsPage` instance (if
   * any) is dirty. Never touches `state` -- an in-flight pending
   * confirmation is not invalidated just because a control's dirty
   * flag ticked (e.g. a second field going dirty while the dialog is
   * already open); that confirmation still refers to the same
   * attempted navigation either way.
   */
  setDirty(dirty: boolean): void {
    this.dirty = dirty;
  }

  // -----------------------------------------------------------------
  // Write API -- the navigation decision itself
  // -----------------------------------------------------------------

  /**
   * The one method every navigation trigger calls before committing a
   * route change. Returns `"allowed"` -- with no other effect -- when
   * Settings is clean, or when `targetPath` is Settings itself (not
   * actually leaving, so nothing to protect against; also what makes
   * repeatedly clicking the already-active Settings sidebar link a
   * no-op rather than a pointless confirmation). Otherwise opens (or
   * re-targets, if one was already pending -- see doc below) the
   * pending confirmation and returns `"blocked"`.
   */
  requestNavigation(targetPath: string): SettingsNavigationGuardDecision {
    if (!this.dirty || targetPath === SETTINGS_NAVIGATION_PATH) {
      return "allowed";
    }

    // Repeated/rapid navigation attempts (task brief tests 5/6) land
    // here on every call while already pending: this simply
    // overwrites `targetPath` with the latest attempt and re-notifies
    // with an equivalent-shape state (still `pending: true`) rather
    // than opening a second, stacked confirmation -- there is only
    // ever one `state` object, so there is nothing to duplicate.
    this.state = { pending: true, targetPath };
    this.notify();
    return "blocked";
  }

  /** Stay: dismiss the pending confirmation. Local edits are
   * untouched -- this never clears `dirty` -- so the person remains
   * on Settings with their in-progress changes exactly as they left
   * them. A no-op (no notify) if nothing is pending. */
  cancel(): void {
    if (!this.state.pending) {
      return;
    }
    this.state = CLEAN_STATE;
    this.notify();
  }

  /**
   * Leave: resolves the pending confirmation. Returns the destination
   * the caller should now navigate to, or `null` if nothing was
   * pending (defensive only -- every real caller already gates this
   * behind `state.pending`). Clears both the pending confirmation and
   * `dirty` immediately, ahead of `useSettingsNavigationGuardSync`'s
   * own unmount cleanup: the caller is about to navigate away, which
   * unmounts `SettingsPage` and, with it, every control's local edit
   * buffer -- "discard local edits" is therefore a natural
   * consequence of the navigation this return value triggers, not a
   * second thing this store has to separately erase.
   */
  confirmLeave(): string | null {
    if (!this.state.pending) {
      return null;
    }
    const targetPath = this.state.targetPath;
    this.state = CLEAN_STATE;
    this.dirty = false;
    this.notify();
    return targetPath;
  }

  // -----------------------------------------------------------------
  // Internals
  // -----------------------------------------------------------------

  private notify(): void {
    const state = this.state;
    for (const listener of this.listeners) {
      try {
        listener(state);
      } catch (error) {
        // One subscriber's exception must not stop delivery to the
        // rest and must not corrupt store state -- mirrors
        // `RestartExhaustedNotificationStore.notify()`'s identical,
        // already-established convention.
        // eslint-disable-next-line no-console
        console.error(
          "SOC-IQ: settings navigation guard subscriber threw",
          error,
        );
      }
    }
  }
}

/**
 * The one application-wide instance real call sites use. Not
 * initialized/disposed the way the sidecar-derived stores are -- this
 * store has no external source to subscribe to and no lifecycle of
 * its own; it is simply always ready to answer `requestNavigation()`,
 * starting from a clean, non-dirty, non-pending state.
 */
export const settingsNavigationGuard = new SettingsNavigationGuardStore();
