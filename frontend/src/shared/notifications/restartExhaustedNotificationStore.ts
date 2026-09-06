/**
 * Restart-exhausted notification foundation — Phase 4G-4 Part 1.
 *
 * Consumes (does not own) the frozen 4G-3 sidecar projection
 * (`sidecarProjection`, `shared/sidecar/projectionStore.ts`). This
 * module adds no lifecycle ownership, no second sidecar-state
 * authority, and no backend/reconciler calls of its own — per task
 * brief §1's architecture diagram, it sits strictly *after* the 4G-3
 * consumer, reading only what that layer already exposes.
 *
 * # Why a transition detector, not a raw event consumer (task brief §6)
 *
 * `SidecarProjectionState` (`projectionStore.ts`) is a point-in-time
 * *snapshot* (`SidecarStatus | null`), not a discrete event stream —
 * the frozen 4G-3 store never replays `EVENT_RESTART_EXHAUSTED`
 * (`shared/sidecar/types.ts`) as a standalone event to its
 * subscribers, only the resulting snapshot's `restart_exhausted`
 * boolean. Reusing that exact frozen field (not inventing a
 * competing "exhausted" concept) and detecting its `false -> true`
 * edge across successive snapshots is the thin frontend transition
 * detector task brief §6 asks for when only a state transition (not
 * a first-class event) is exposed at this layer.
 *
 * # Duplicate-notification avoidance (task brief §5)
 *
 * `lastObservedExhausted` is this store's own edge-detection memory,
 * independent of the "visible"/dismissed notification state below.
 * Consequences of keeping the two separate:
 *   - A snapshot update that changes some other field (e.g. `sequence`
 *     ticks while `restart_exhausted` stays `true`) updates
 *     `lastObservedExhausted` to the same `true` it already was, so
 *     no second notification fires — satisfies "unchanged state" and
 *     "repeated identical state" from task brief §5/§12.
 *   - Dismissing the notification (`dismiss()`) clears *visibility*
 *     only; it does not touch `lastObservedExhausted`, so a later,
 *     unrelated snapshot while still exhausted cannot resurrect a
 *     dismissed notification — but a genuine new exhaustion cycle
 *     (a later `true -> false -> true`, e.g. the sidecar recovered
 *     and later exhausted its restarts again) still notifies, since
 *     that really is a new transition.
 *   - This store is a singleton (`restartExhaustedNotification`
 *     below, mirroring `sidecarProjection`'s own singleton pattern),
 *     not per-component state — so navigating between pages (which
 *     mounts/unmounts consuming components, not this store) can
 *     never reset `lastObservedExhausted` and cause a re-notification
 *     task brief §5 explicitly calls out to avoid.
 *   - React Strict Mode's double-invocation of effects only calls
 *     this store's own idempotent `initialize()` twice (see below);
 *     it never re-runs `handleSidecarState()` on its own.
 *
 * # Subscription lifecycle (mirrors `SidecarProjectionConnector`,
 * `shared/sidecar/projectionConnector.ts`)
 *
 * `initialize()` is idempotent (a second call while already
 * `"active"` is a no-op) and safely re-runnable after `dispose()`,
 * exactly like that connector's own documented lifecycle. It also
 * seeds from the source's *current* snapshot once, so a sidecar that
 * is already exhausted at the moment this store starts still
 * produces a notification — a real "the sidecar's restarts are
 * exhausted" condition should not go unreported merely because it was
 * already true before this store subscribed.
 *
 * # No sidecar lifecycle ownership (task brief §1/§3)
 *
 * This store only ever calls `source.subscribe()` / `source.getState()`
 * — it never calls `startSidecarLifecycle()`,
 * `SidecarSnapshotReconciler.initialize()/.dispose()`, or any other
 * lifecycle-owning API. `dispose()` here only removes this store's own
 * subscription to `source`; it never disposes `source` itself, the
 * same ownership boundary `SidecarProjectionConnector.dispose()`
 * already documents.
 */

import {
  sidecarProjection,
  type SidecarProjectionState,
  type SidecarProjectionStore,
} from "../sidecar/projectionStore";

/**
 * Closed notification vocabulary (task brief §7's "notification
 * state"). Deliberately not carrying a redundant "dismissed" branch —
 * dismissed and never-yet-shown are the same externally observable
 * state (`{ visible: false }`); only this store's private
 * `lastObservedExhausted` needs to remember which one it was, and
 * only to decide whether a *future* transition should re-notify.
 */
export type RestartExhaustedNotificationState =
  | { readonly visible: false }
  | {
      readonly visible: true;
      /** `SidecarStatus.restart_attempts` at the moment exhaustion was observed — reused verbatim, not recomputed. */
      readonly attempts: number;
      /** `SidecarStatus.sequence` at the moment exhaustion was observed — an opaque ordering value, never reinterpreted. */
      readonly sequence: number;
    };

export type RestartExhaustedNotificationListener = (
  state: RestartExhaustedNotificationState,
) => void;

type StoreLifecycle = "uninitialized" | "active" | "disposed";

interface RestartExhaustedNotificationStoreOptions {
  /** Defaults to the one application-wide `sidecarProjection` instance. Tests inject an isolated instance instead. */
  readonly source?: SidecarProjectionStore;
}

/**
 * The restart-exhausted notification foundation. One instance tracks,
 * at most, one active notification derived from `source`'s
 * `restart_exhausted` transitions. Deliberately a class, mirroring
 * every other frozen sidecar module's own reasoning
 * (`projectionStore.ts`, `projectionConnector.ts`): tests construct
 * their own instance against an isolated source rather than needing a
 * reset hatch on shared module state.
 */
export class RestartExhaustedNotificationStore {
  private readonly source: SidecarProjectionStore;
  private state: RestartExhaustedNotificationState = { visible: false };
  private readonly listeners = new Set<RestartExhaustedNotificationListener>();
  private lifecycle: StoreLifecycle = "uninitialized";
  private lastObservedExhausted = false;
  private unsubscribeSource: (() => void) | null = null;

  constructor(options: RestartExhaustedNotificationStoreOptions = {}) {
    this.source = options.source ?? sidecarProjection;
    // Bound once so the same function reference is reused across
    // every initialize() call, mirroring
    // `SidecarProjectionConnector`'s identical reasoning for its own
    // `handleEvent`.
    this.handleSidecarState = this.handleSidecarState.bind(this);
  }

  // -------------------------------------------------------------------
  // Read API
  // -------------------------------------------------------------------

  getState(): RestartExhaustedNotificationState {
    return this.state;
  }

  /** `"uninitialized"` before the first `initialize()`, `"active"` while subscribed to `source`, `"disposed"` after `dispose()`. */
  getLifecycle(): StoreLifecycle {
    return this.lifecycle;
  }

  // -------------------------------------------------------------------
  // Subscription (own listeners, not `source`'s)
  // -------------------------------------------------------------------

  /**
   * Register a listener for future notification-state changes.
   *
   * Unlike `SidecarProjectionStore.subscribe()`, this does NOT no-op
   * while `disposed`: this store (per `initialize()`'s own doc) is
   * "safely re-runnable after dispose()", so a consumer (e.g. a React
   * component via `useSyncExternalStore`) can mount while this store
   * is between an old `dispose()` and a later `initialize()` — for
   * instance, `AppShell`'s mount happening before its own startup
   * effect calls `initialize()`. `useSyncExternalStore` only invokes
   * `subscribe` again on a later render, not automatically when the
   * store's own lifecycle changes; refusing the registration here
   * while disposed would silently drop that listener forever, so a
   * genuinely later `dismiss()`/transition would never reach it even
   * after `initialize()` reactivates the store. Registering
   * unconditionally costs nothing while disposed (the listener simply
   * sits unused until the next `initialize()` re-subscribes to
   * `source`), and `dispose()` already clears `listeners` for the
   * "truly torn down" case.
   */
  subscribe(listener: RestartExhaustedNotificationListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  // -------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------

  /**
   * Subscribe to `source` and seed from its current snapshot.
   * Idempotent: a second call while already `"active"` is a no-op.
   * Safe to call again after `dispose()` (re-subscribes fresh).
   */
  initialize(): void {
    if (this.lifecycle === "active") return;
    this.lifecycle = "active";
    this.unsubscribeSource = this.source.subscribe(this.handleSidecarState);
    this.handleSidecarState(this.source.getState());
  }

  /**
   * Remove this store's subscription to `source`. Safe to call
   * repeatedly, including before `initialize()` has ever run. Does
   * not touch `source`'s own lifecycle (see module doc's ownership
   * boundary) and does not clear the currently held notification
   * state — only this store's own listener registry.
   */
  dispose(): void {
    if (this.unsubscribeSource) {
      this.unsubscribeSource();
      this.unsubscribeSource = null;
    }
    this.lifecycle = "disposed";
    this.listeners.clear();
  }

  // -------------------------------------------------------------------
  // Dismissal (task brief §7's "notification dismissal")
  // -------------------------------------------------------------------

  /**
   * Hide the current notification, if any. A no-op if nothing is
   * currently visible (no spurious notify-with-no-change). Does not
   * affect edge detection for a future, genuinely new exhaustion
   * transition (see module doc).
   */
  dismiss(): void {
    if (!this.state.visible) return;
    this.state = { visible: false };
    this.notify();
  }

  // -------------------------------------------------------------------
  // Internals
  // -------------------------------------------------------------------

  private handleSidecarState(next: SidecarProjectionState): void {
    // `next?.restart_exhausted ?? false`: task brief §9's "unknown/
    // unexpected state safety" — `next` is `null` before the frozen
    // reconciler has applied a first snapshot (same representation
    // `useSidecarStatus.ts` already documents), which this store
    // treats as "not exhausted", never as a crash.
    const exhausted = next?.restart_exhausted ?? false;

    if (exhausted && !this.lastObservedExhausted) {
      this.state = {
        visible: true,
        attempts: next!.restart_attempts,
        sequence: next!.sequence,
      };
      this.notify();
    }

    this.lastObservedExhausted = exhausted;
  }

  private notify(): void {
    const state = this.state;
    for (const listener of this.listeners) {
      try {
        listener(state);
      } catch (error) {
        // One subscriber's exception must not stop delivery to the
        // rest and must not corrupt store state — mirrors
        // `SidecarProjectionStore.notify()`'s identical, already-
        // established convention.
        // eslint-disable-next-line no-console
        console.error(
          "SOC-IQ: restart-exhausted notification subscriber threw",
          error,
        );
      }
    }
  }
}

/**
 * The one application-wide instance real call sites use, wired to the
 * one application-wide `sidecarProjection`. Not initialized here —
 * a future integration checkpoint (4G-4 Part 2) calls
 * `restartExhaustedNotification.initialize()` once at application
 * startup, mirroring `sidecarProjectionConnector`'s own
 * not-initialized-at-module-scope precedent.
 */
export const restartExhaustedNotification =
  new RestartExhaustedNotificationStore();
