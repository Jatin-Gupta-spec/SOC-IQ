/**
 * `SidecarEventSubscription` → `SidecarProjectionStore` integration —
 * Phase 4E-P3 Part 2D-3B.
 *
 * This is the one place that calls both Part 2D-2's `onEvent()` seam
 * (`eventSubscription.ts`) and Part 2D-3A's `applyProjectedState()`
 * seam (`projectionStore.ts`), using the pure mapping in
 * `eventProjection.ts`. It owns exactly one thing: its own
 * registration with a `SidecarEventSubscription`. It does not call
 * Tauri's `listen()` itself (task brief §4/§5 — that remains
 * `SidecarEventSubscription`'s sole responsibility) and it does not
 * hold projected state itself (that remains `SidecarProjectionStore`'s
 * sole responsibility) — this class is pure wiring plus its own
 * start/stop lifecycle.
 *
 * # Ownership boundary (task brief §15)
 *
 * ```text
 * Application
 *     owns
 *       ↓
 * the global SidecarEventSubscription (sidecarEvents) and the global
 * SidecarProjectionStore (sidecarProjection) — both already existed
 * before this checkpoint (Part 2D-2 / Part 2D-3A) and are unowned by
 * this class.
 *
 * SidecarProjectionConnector
 *     owns
 *       ↓
 * its own one `onEvent()` consumer callback — nothing more.
 * ```
 *
 * `dispose()` therefore only calls the unsubscribe function
 * `onEvent()` itself returned. It never calls `sidecarEvents.stop()`
 * and never calls `sidecarProjection.dispose()` — either of those
 * would tear down application-wide infrastructure this one connector
 * does not own (task brief §15/§17), exactly the mistake the task
 * brief's own architecture note warns against.
 *
 * # Registration lifecycle (task brief §16/§17)
 *
 * Unlike `SidecarProjectionStore.dispose()` (Part 2D-3A, terminal —
 * once disposed, always disposed) and `SidecarEventSubscription.stop()`
 * (Part 2D-2, restartable via `start()`), this connector's own
 * lifecycle is restartable: `initialize()` → `dispose()` →
 * `initialize()` again is a supported, defined sequence — the second
 * `initialize()` re-registers a fresh `onEvent()` subscription and
 * resumes projecting events, since this class owns nothing but that
 * one registration (no terminal internal state to have been lost).
 * `initialize()` while already initialized is a deterministic no-op
 * (task brief §16: "repeated initialization must be deterministic" —
 * exactly one active store-to-event-source connection at a time, never
 * three callbacks for three calls). `dispose()` is safe to call any
 * number of times, including when never initialized.
 *
 * # Error isolation (task brief §19)
 *
 * `SidecarEventSubscription.onEvent()`'s own dispatch loop
 * (`handleIncoming`, `eventSubscription.ts`) does not wrap individual
 * listener calls in try/catch — a throwing listener would stop
 * delivery to every other listener registered on that same
 * subscription instance, which this connector must not risk being the
 * cause of. `handleEvent` below is therefore wrapped in its own
 * try/catch, matching this codebase's established "log via
 * `console.error`, never throw across a dispatch boundary" convention
 * (`projectionStore.ts`'s own `notify()` uses the identical pattern
 * for the same reason, one layer down). State is only ever mutated by
 * calling `SidecarProjectionStore.applyProjectedState()`, which is
 * itself atomic (assigns, then notifies) — so a thrown error here,
 * before or during projection, can never leave the store holding a
 * partial/corrupt value (task brief §19's "must not corrupt the
 * store's internal state").
 */

import {
  sidecarEvents,
  type SidecarEventSubscription,
} from "./eventSubscription";
import { projectSidecarEvent } from "./eventProjection";
import {
  sidecarProjection,
  type SidecarProjectionStore,
} from "./projectionStore";

interface SidecarProjectionConnectorOptions {
  /** Defaults to the one application-wide `sidecarEvents` instance. Tests inject an isolated instance instead. */
  readonly subscription?: SidecarEventSubscription;
  /** Defaults to the one application-wide `sidecarProjection` instance. Tests inject an isolated instance instead. */
  readonly store?: SidecarProjectionStore;
}

type ConnectorLifecycle = "uninitialized" | "active" | "disposed";

/**
 * Feeds `SidecarEventSubscription.onEvent()` into
 * `SidecarProjectionStore.applyProjectedState()` via the pure
 * `projectSidecarEvent` mapping. One instance owns, at most, one
 * active `onEvent()` registration at a time.
 */
export class SidecarProjectionConnector {
  private readonly subscription: SidecarEventSubscription;
  private readonly store: SidecarProjectionStore;

  private lifecycle: ConnectorLifecycle = "uninitialized";
  private unsubscribe: (() => void) | null = null;

  constructor(options: SidecarProjectionConnectorOptions = {}) {
    this.subscription = options.subscription ?? sidecarEvents;
    this.store = options.store ?? sidecarProjection;
    // Bound once so the same function reference is reused across
    // every initialize() call — `SidecarEventSubscription.onEvent()`
    // stores listeners in a `Set`, so reusing one reference (rather
    // than a fresh closure per call) keeps duplicate-registration
    // protection meaningful and keeps `dispose()`'s captured
    // unsubscribe function paired with the exact listener it added.
    this.handleEvent = this.handleEvent.bind(this);
  }

  /** `"uninitialized"` before the first `initialize()`, `"active"` while registered, `"disposed"` after `dispose()` (task brief §17). */
  getLifecycle(): ConnectorLifecycle {
    return this.lifecycle;
  }

  // -------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------

  /**
   * Register this connector's one `onEvent()` callback with the
   * underlying `SidecarEventSubscription`. Idempotent: a second call
   * while already `"active"` is a no-op (task brief §16) — it does
   * not re-register, and does not affect the existing registration.
   * Safe to call again after `dispose()` (task brief §17's own
   * defined re-initialization sequence).
   */
  initialize(): void {
    if (this.lifecycle === "active") return;

    this.unsubscribe = this.subscription.onEvent(this.handleEvent);
    this.lifecycle = "active";
  }

  /**
   * Remove this connector's `onEvent()` registration. Safe to call
   * repeatedly (task brief §17's "repeated dispose() must be safe")
   * and safe to call before `initialize()` has ever run. Does not
   * touch the underlying `SidecarEventSubscription`'s own
   * start/stop lifecycle or the `SidecarProjectionStore`'s own
   * dispose lifecycle — see the module doc's ownership boundary.
   */
  dispose(): void {
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
    this.lifecycle = "disposed";
  }

  // -------------------------------------------------------------------
  // Internals
  // -------------------------------------------------------------------

  private handleEvent(event: Parameters<typeof projectSidecarEvent>[1]): void {
    try {
      const next = projectSidecarEvent(this.store.getState(), event);
      if (next !== null) {
        this.store.applyProjectedState(next);
      }
      // `next === null`: no baseline to project a restart event onto
      // yet (`eventProjection.ts`'s own doc) — a deliberate no-op, not
      // an error condition, so nothing is logged.
    } catch (error) {
      // Never let a projection failure propagate back into
      // `SidecarEventSubscription`'s own dispatch loop (module doc's
      // error-isolation section) — logged, not thrown, matching
      // `projectionStore.ts`'s own established convention.
      // eslint-disable-next-line no-console
      console.error("SOC-IQ: sidecar event projection failed", error);
    }
  }
}

/**
 * The one application-wide instance real call sites use, wiring the
 * one application-wide `sidecarEvents` to the one application-wide
 * `sidecarProjection`. Not initialized here — a future UI-integration
 * checkpoint calls `sidecarProjectionConnector.initialize()` once at
 * application startup, alongside `sidecarEvents.start()` (out of scope
 * for this checkpoint — task brief §23: "No UI").
 */
export const sidecarProjectionConnector = new SidecarProjectionConnector();
