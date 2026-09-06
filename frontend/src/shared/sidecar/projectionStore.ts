/**
 * Sidecar projection-store foundation — Phase 4E-P3 Part 2D-3A.
 *
 * This is the store *foundation* only: it owns state, exposes a
 * read/subscribe API, and gives a future projection layer exactly one
 * internal seam to push confirmed state into. It does not yet listen
 * to anything — it is not wired to Part 2D-2's
 * `SidecarEventSubscription.onEvent()` (task brief §10) and it does
 * not call `get_sidecar_status` (task brief §11). Both are explicitly
 * later sub-checkpoints (2D-3B / 2D-3C); nothing here anticipates
 * either beyond leaving `applyProjectedState()` available for 2D-3B to
 * call.
 *
 * # State model (task brief §5)
 *
 * Reuses the frozen `SidecarStatus` (`types.ts`, Part 2D-1) verbatim —
 * no second/competing definition of backend sidecar status is
 * introduced here. `SidecarStatus` itself has no representation for
 * "the frontend has not received a status yet" (every field is
 * required, and inventing a fake `LifecycleState` member such as
 * `"UNKNOWN"` would mean modifying the frozen backend contract, which
 * task brief §5 forbids). This store therefore uses an explicit
 * store-level initialization representation instead: `null` means
 * "not yet projected anything", and is never itself a valid
 * `SidecarStatus` value — the public state type is
 * `SidecarProjectionState = SidecarStatus | null`, so `getState()`'s
 * return type makes the distinction visible to every caller at
 * compile time rather than hiding it behind a sentinel string.
 *
 * # Immutability (task brief §6)
 *
 * `SidecarStatus` is a flat record of primitives (`string`/`boolean`/
 * `number`/`number | null`) — no nested objects, no arrays. A shallow
 * `Object.freeze()` on the object handed to `applyProjectedState()` is
 * therefore already full immutability for this shape; a deep-clone or
 * deep-freeze dependency would protect against a mutation surface that
 * does not exist. `getState()` returns that same frozen reference
 * (not a defensive copy) on every call between updates, so identity
 * (`===`) is stable for consumers that want to skip re-render work —
 * a plain object copy would needlessly break that.
 *
 * # Equality / notification policy (task brief §14)
 *
 * `applyProjectedState()` compares every field of the incoming
 * `SidecarStatus` against the currently held one with a flat,
 * hand-written field-by-field comparison (`sidecarStatusEquals`) —
 * not a generic deep-equality library (task brief §6/§14: no new
 * dependency), and sufficient because the shape is flat. An update
 * whose fields are all equal to the current state produces no
 * notification at all — this is what lets a future projection layer
 * (2D-3B) call `applyProjectedState()` freely (e.g. once per delivered
 * domain event) without redundant re-renders for events that don't
 * actually change the projected snapshot.
 *
 * # Subscriber identity / duplicate registration (task brief §8)
 *
 * Listeners are held in a `Set`, exactly mirroring Part 2D-2's
 * `SidecarEventSubscription`'s `onEvent()`/`onDiagnostic()` (see
 * `eventSubscription.ts`). Consequence, chosen deliberately for
 * consistency with that established precedent rather than
 * reinvented here: registering the *same* function reference twice
 * is deduplicated to one active subscription (a `Set` add of an
 * already-present value is a no-op), so it is notified once per
 * change, not twice; the unsubscribe function returned by *either*
 * `subscribe()` call removes that one shared entry. Two distinct
 * closures (even if functionally identical) are two independent
 * subscriptions, since a `Set` compares by reference.
 *
 * # Subscribe-after-dispose (task brief §12)
 *
 * Chosen behavior: `subscribe()` after `dispose()` returns a working,
 * safe-to-call no-op unsubscribe function rather than throwing, and
 * never adds the listener to internal storage (so nothing is retained
 * to leak). This matches this codebase's existing preference for
 * "safe no-op over exception for an expected lifecycle state" already
 * established by Part 2D-1's validators (return `false`, never throw)
 * and Part 2D-2's sequence filtering (silently drop stale events
 * rather than raise) — a disposed store being subscribed to again is
 * an expected end-of-life condition, not a programmer error that
 * should crash the caller.
 *
 * # Error isolation (task brief §15)
 *
 * One subscriber throwing must not stop delivery to the remaining
 * subscribers and must not corrupt store state. State is applied
 * (`this.state = frozen`) *before* any listener runs, so a throwing
 * listener can never leave `getState()` returning a stale or partial
 * value; each listener invocation is individually wrapped in
 * try/catch inside `notify()`, and a caught error is logged with
 * `console.error` (mirroring `eventSourceManager.ts`'s existing
 * `console.warn` + `eslint-disable-next-line no-console` convention
 * for this codebase's "expected, logged, not thrown" pattern) rather
 * than inventing a new global error-reporting mechanism.
 */

import type { SidecarStatus } from "./types";

/**
 * `null` = the store has never had a state applied to it yet (task
 * brief §5's store-level initialization representation). Once a real
 * `SidecarStatus` has been applied, the store never reverts to
 * `null` — there is no `reset()`/`clear()` operation, only
 * `dispose()`, which ends the store's lifecycle entirely rather than
 * blanking its last known state.
 */
export type SidecarProjectionState = SidecarStatus | null;

export type SidecarProjectionListener = (
  state: SidecarProjectionState,
) => void;

type StoreLifecycle = "active" | "disposed";

function sidecarStatusEquals(a: SidecarStatus, b: SidecarStatus): boolean {
  return (
    a.state === b.state &&
    a.restart_pending === b.restart_pending &&
    a.restart_pending_attempt === b.restart_pending_attempt &&
    a.restart_attempts === b.restart_attempts &&
    a.restart_exhausted === b.restart_exhausted &&
    a.sequence === b.sequence
  );
}

/**
 * The authoritative frontend projection of sidecar status. One
 * instance owns one current `SidecarProjectionState` and notifies its
 * subscribers exactly once per state change that actually changes a
 * field (task brief §8's "notify each active subscriber exactly
 * once" + §14's "no redundant notifications").
 *
 * Deliberately a class (not bare module state) for the same reason
 * `eventSubscription.ts` gave for its own class-based design
 * (task brief §17's test-isolation requirement): tests construct
 * their own instance rather than needing a `__resetForTests` escape
 * hatch on shared module state. `sidecarProjection` below is the one
 * application-wide instance real call sites (starting with Part
 * 2D-3B) use.
 */
export class SidecarProjectionStore {
  private state: SidecarProjectionState = null;
  private readonly listeners = new Set<SidecarProjectionListener>();
  private lifecycle: StoreLifecycle = "active";

  // -------------------------------------------------------------------
  // Read API
  // -------------------------------------------------------------------

  /** The current projected state, or `null` if nothing has ever been applied. Frozen — see module doc's immutability section. */
  getState(): SidecarProjectionState {
    return this.state;
  }

  /** `"active"` until `dispose()` is called; `"disposed"` forever after (task brief §12). */
  getLifecycle(): StoreLifecycle {
    return this.lifecycle;
  }

  // -------------------------------------------------------------------
  // Subscription
  // -------------------------------------------------------------------

  /**
   * Register a listener for future state changes. Returns an
   * unsubscribe function. Calling `subscribe()` does **not**
   * synchronously replay the current state to the new listener — this
   * store is pull-based for "what is it right now"
   * (`getState()`) and push-based only for "it just changed"
   * (this method); a caller that wants both reads `getState()` once
   * and then subscribes, the same two-step pattern
   * `useEventStreamStatus.ts` already uses for the SSE status hook.
   *
   * After `dispose()`, this is a safe no-op: it returns a working
   * unsubscribe function but never stores the listener (task brief
   * §12's chosen behavior, explained in the module doc above).
   */
  subscribe(listener: SidecarProjectionListener): () => void {
    if (this.lifecycle === "disposed") {
      return () => {};
    }

    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  // -------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------

  /**
   * End this store's lifecycle. Safe to call repeatedly (task brief
   * §12's "repeated dispose() must be safe") — a second/third call is
   * a no-op. Clears every subscriber reference immediately (task
   * brief §13's "explicitly clear internal subscription storage",
   * not a garbage-collection assumption) and, from this point on,
   * `applyProjectedState()` is inert and `subscribe()` returns a
   * no-op.
   */
  dispose(): void {
    if (this.lifecycle === "disposed") return;
    this.lifecycle = "disposed";
    this.listeners.clear();
  }

  // -------------------------------------------------------------------
  // The Part 2D-3B seam (task brief §9/§17)
  // -------------------------------------------------------------------

  /**
   * Apply a new authoritative `SidecarStatus`, notifying subscribers
   * if and only if at least one field actually differs from the
   * currently held state (module doc's equality/notification
   * policy). This is deliberately a genuine, documented internal API
   * — not a test-only shim bolted on afterward (task brief §17: "do
   * not expose a public production mutation API solely for testing")
   * — because it IS the seam a future event-projection layer (Part
   * 2D-3B) needs in order to turn a validated `SidecarDomainEvent`
   * (`eventSubscription.ts`) into an updated projection. This
   * checkpoint's own tests are simply this seam's first caller, ahead
   * of 2D-3B's arrival.
   *
   * No-op once `dispose()` has been called (task brief §12: no
   * notifications after disposal).
   */
  applyProjectedState(next: SidecarStatus): void {
    if (this.lifecycle === "disposed") return;
    if (this.state !== null && sidecarStatusEquals(this.state, next)) {
      return;
    }

    const frozen = Object.freeze({ ...next });
    this.state = frozen;
    this.notify(frozen);
  }

  private notify(state: SidecarProjectionState): void {
    for (const listener of this.listeners) {
      try {
        listener(state);
      } catch (error) {
        // One subscriber's exception must not stop delivery to the
        // rest, and must not corrupt store state -- `this.state` was
        // already assigned above, before this loop started (task
        // brief §15).
        // eslint-disable-next-line no-console
        console.error(
          "SOC-IQ: sidecar projection subscriber threw",
          error,
        );
      }
    }
  }
}

/**
 * The one application-wide instance real call sites use. Nothing in
 * this checkpoint calls `applyProjectedState()` on it — Part 2D-3B is
 * the first intended production caller, via `SidecarEventSubscription
 * .onEvent()` (`eventSubscription.ts`)'s existing seam.
 */
export const sidecarProjection = new SidecarProjectionStore();
