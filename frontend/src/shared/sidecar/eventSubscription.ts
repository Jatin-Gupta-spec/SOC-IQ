/**
 * Real Tauri `listen()` integration for the sidecar lifecycle event
 * contract — Phase 4E-P3 Part 2D-2.
 *
 * Part 2D-1 (frozen — `types.ts`/`validation.ts`) defined the wire
 * shapes and the runtime validators. This module is the one place
 * that actually calls `@tauri-apps/api/event`'s `listen()` for the
 * three canonical sidecar events (`types.ts`'s `SIDECAR_EVENT_NAMES`)
 * and turns raw, untrusted Tauri `Event<unknown>` deliveries into
 * validated, sequence-filtered, domain-facing `SidecarDomainEvent`s.
 *
 * # Architecture
 *
 * Mirrors `shared/events/eventSourceManager.ts`'s own shape (a single
 * owner of the underlying transport, ref-counting handled by an
 * explicit start/stop lifecycle instead of subscriber-count teardown,
 * since — unlike the SSE manager — there is exactly one fixed set of
 * three event names to own, not an open set of per-feature channels).
 * A dedicated class rather than bare module state, specifically so
 * tests can construct an isolated instance per test (task brief §14's
 * "testability without requiring the full GUI") instead of needing a
 * `__resetForTests` escape hatch on shared module state. The default
 * export `sidecarEvents` is the one application-wide instance real
 * call sites use; nothing here prevents constructing another instance
 * for a test.
 *
 * This module does not decide anything about sidecar lifecycle and
 * does not hold a projection of current status — it only subscribes,
 * validates, filters, and forwards. The projection store / reducer
 * that turns a stream of `SidecarDomainEvent`s into a `useSidecarStatus()`-
 * style view-model is explicitly Part 2D-3's job (architecture doc
 * §13/§14) — `onEvent()` below is the domain-facing seam that future
 * work plugs into; nothing beyond that seam is implemented here.
 *
 * # Sequence semantics (architecture doc §12.2, re-confirmed against
 * `src-tauri/src/events.rs`'s `EventSequencer`/`sequence_is_unique_and_
 * strictly_increasing_across_every_event_kind` test this checkpoint)
 *
 * `sequence` is allocated from **one** global `AtomicU64` shared by
 * every event kind (`state_changed`/`restart_scheduled`/
 * `restart_exhausted` alike) — there are not three independent
 * per-event-type sequence streams. This module therefore tracks a
 * single `lastAppliedSequence` across all three event names, exactly
 * mirroring the backend's own single counter, and applies the
 * architecture's one drop rule uniformly:
 *
 *     accept an incoming payload's sequence only if it is strictly
 *     greater than the highest sequence already accepted; otherwise
 *     drop it (duplicate or stale) without forwarding to any listener.
 *
 * `sequence` itself is never regenerated, reinterpreted, converted to
 * a timestamp, or used as an array index anywhere in this file — it
 * is read once (`payload.sequence`), compared, stored verbatim in
 * `lastAppliedSequence`, and forwarded unchanged as part of the
 * validated payload object.
 */

import { listen, type Event as TauriEvent, type UnlistenFn } from "@tauri-apps/api/event";

import {
  EVENT_RESTART_EXHAUSTED,
  EVENT_RESTART_SCHEDULED,
  EVENT_STATE_CHANGED,
  type RestartExhaustedPayload,
  type RestartScheduledPayload,
  type SidecarEventName,
  type StateChangedPayload,
} from "./types";
import {
  isRestartExhaustedPayload,
  isRestartScheduledPayload,
  isStateChangedPayload,
} from "./validation";

// ---------------------------------------------------------------------------
// Domain-facing dispatch shape
// ---------------------------------------------------------------------------

/**
 * The one thing this module ever hands a listener: a validated,
 * sequence-accepted payload tagged with which of the three events it
 * came from. Deliberately a discriminated union over the exact
 * Part 2D-1 payload types — no new fields, no merged/flattened shape.
 */
export type SidecarDomainEvent =
  | { readonly kind: "state_changed"; readonly payload: StateChangedPayload }
  | { readonly kind: "restart_scheduled"; readonly payload: RestartScheduledPayload }
  | { readonly kind: "restart_exhausted"; readonly payload: RestartExhaustedPayload };

export type SidecarEventListener = (event: SidecarDomainEvent) => void;

/**
 * Diagnostic-only channel (task brief §6/§12: "optionally record/log
 * diagnostic information" for a rejected payload; §12 of this
 * checkpoint's own brief for subscription failures). Never delivered
 * to `onEvent()` listeners — a rejected/failed item is, by
 * definition, not a valid domain event.
 */
export type SidecarDiagnostic =
  | {
      readonly kind: "invalid_payload";
      readonly eventName: SidecarEventName;
      readonly rawPayload: unknown;
    }
  | {
      readonly kind: "stale_sequence";
      readonly eventName: SidecarEventName;
      readonly sequence: number;
      readonly lastAppliedSequence: number;
    }
  | {
      readonly kind: "subscription_failed";
      readonly eventName: SidecarEventName;
      readonly error: unknown;
    };

export type SidecarDiagnosticListener = (diagnostic: SidecarDiagnostic) => void;

// ---------------------------------------------------------------------------
// listen() injection point (task brief §14: "mock the Tauri event API
// at the infrastructure boundary. Do not mock your own subscription
// service.")
// ---------------------------------------------------------------------------

type ListenFn = typeof listen;

interface SidecarEventSubscriptionOptions {
  /**
   * Defaults to the real `@tauri-apps/api/event`'s `listen`. Tests
   * inject a controlled fake here instead of mocking anything on this
   * class itself.
   */
  readonly listenFn?: ListenFn;
}

type SidecarEventDescriptor<TPayload> = {
  readonly eventName: SidecarEventName;
  readonly kind: SidecarDomainEvent["kind"];
  readonly validate: (value: unknown) => value is TPayload;
  readonly sequenceOf: (payload: TPayload) => number;
};

const EVENT_DESCRIPTORS: readonly SidecarEventDescriptor<
  StateChangedPayload | RestartScheduledPayload | RestartExhaustedPayload
>[] = [
  {
    eventName: EVENT_STATE_CHANGED,
    kind: "state_changed",
    validate: isStateChangedPayload,
    sequenceOf: (payload) => payload.sequence,
  },
  {
    eventName: EVENT_RESTART_SCHEDULED,
    kind: "restart_scheduled",
    validate: isRestartScheduledPayload,
    sequenceOf: (payload) => payload.sequence,
  },
  {
    eventName: EVENT_RESTART_EXHAUSTED,
    kind: "restart_exhausted",
    validate: isRestartExhaustedPayload,
    sequenceOf: (payload) => payload.sequence,
  },
];

type SubscriptionStatus = "stopped" | "starting" | "started";

/**
 * Owns the real Tauri listeners for the three sidecar lifecycle
 * events. One instance owns, at most, one active listener per event
 * name at any time (task brief §8's duplicate-subscription
 * protection) and exposes an explicit `start()`/`stop()` lifecycle
 * (task brief §9) that is safe under repeated and/or overlapping
 * calls, including across the async gap `listen()` itself introduces
 * (task brief §10).
 */
export class SidecarEventSubscription {
  private readonly listenFn: ListenFn;
  private readonly listeners = new Set<SidecarEventListener>();
  private readonly diagnosticListeners = new Set<SidecarDiagnosticListener>();

  private status: SubscriptionStatus = "stopped";
  private startPromise: Promise<void> | null = null;
  /**
   * Bumped by every `start()`/`stop()` call. A `registerListener()`
   * in flight compares the token it captured against this value once
   * its `listen()` promise resolves; a mismatch means a newer
   * start/stop cycle has already superseded it, so the just-resolved
   * listener is torn down immediately instead of being kept (task
   * brief §10's race).
   */
  private generation = 0;
  private unlistenFns: UnlistenFn[] = [];

  /**
   * One global ordering boundary (module doc above) — every event
   * kind shares this single counter, matching the backend's one
   * `EventSequencer`. `0` before any event has ever been accepted,
   * matching the backend's own "no event yet" sentinel
   * (`EventSequencer::current_sequence`'s doc comment).
   */
  private lastAppliedSequence = 0;

  constructor(options: SidecarEventSubscriptionOptions = {}) {
    this.listenFn = options.listenFn ?? listen;
  }

  // -------------------------------------------------------------------
  // Domain-facing subscription (the Part 2D-3 seam)
  // -------------------------------------------------------------------

  /** Subscribe to validated, sequence-accepted domain events. Returns an unsubscribe function. */
  onEvent(listener: SidecarEventListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Subscribe to rejected/failed items, for logging/diagnostics only. Returns an unsubscribe function. */
  onDiagnostic(listener: SidecarDiagnosticListener): () => void {
    this.diagnosticListeners.add(listener);
    return () => {
      this.diagnosticListeners.delete(listener);
    };
  }

  /** Current lifecycle status, for callers/tests that want to observe it without reaching into internals. */
  getStatus(): SubscriptionStatus {
    return this.status;
  }

  /** The last sequence accepted across all three event streams (`0` if none yet). */
  getLastAppliedSequence(): number {
    return this.lastAppliedSequence;
  }

  // -------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------

  /**
   * Establish the real Tauri listeners for all three events. Safe to
   * call repeatedly and/or concurrently: while a start is already in
   * flight or complete, every call returns the same promise/settled
   * state rather than registering a second set of listeners (task
   * brief §8). Resolves once every registration attempt has settled
   * (success or failure) — a single failed registration does not
   * reject the whole `start()` call (task brief §12: one failed
   * subscription must not leave the others un-registered or the
   * lifecycle state inconsistent); failures are reported via
   * `onDiagnostic()` instead.
   */
  start(): Promise<void> {
    if (this.status !== "stopped" && this.startPromise) {
      return this.startPromise;
    }

    this.status = "starting";
    const generation = ++this.generation;

    this.startPromise = this.registerAll(generation).then(() => {
      // Only claim "started" if this is still the active generation —
      // a stop() (or a newer start()) may have superseded us while
      // registration was in flight.
      if (generation === this.generation) {
        this.status = "started";
      }
    });

    return this.startPromise;
  }

  /**
   * Tear down every active listener. Safe to call repeatedly (a
   * second `stop()` is a no-op) and safe to call before an in-flight
   * `start()` has finished registering — any listener that finishes
   * registering after this `stop()` call is unlistened immediately
   * rather than kept (task brief §9/§10).
   */
  stop(): void {
    this.generation += 1; // invalidates any in-flight registerAll()
    this.status = "stopped";
    this.startPromise = null;

    const fns = this.unlistenFns;
    this.unlistenFns = [];
    for (const unlisten of fns) {
      unlisten();
    }
  }

  // -------------------------------------------------------------------
  // Internals
  // -------------------------------------------------------------------

  private async registerAll(generation: number): Promise<void> {
    await Promise.all(
      EVENT_DESCRIPTORS.map((descriptor) => this.registerOne(descriptor, generation)),
    );
  }

  private async registerOne<TPayload>(
    descriptor: SidecarEventDescriptor<TPayload>,
    generation: number,
  ): Promise<void> {
    let unlisten: UnlistenFn;
    try {
      unlisten = await this.listenFn(descriptor.eventName, (event: TauriEvent<unknown>) => {
        this.handleIncoming(descriptor, event.payload);
      });
    } catch (error) {
      // Subscription failure (task brief §12): reported, never thrown
      // out of start(), never invented as a new backend error code.
      this.emitDiagnostic({
        kind: "subscription_failed",
        eventName: descriptor.eventName,
        error,
      });
      return;
    }

    if (generation !== this.generation) {
      // Superseded by a stop()/newer start() while listen() was
      // in flight — do not keep a listener this instance no longer
      // considers active (task brief §10's async race).
      unlisten();
      return;
    }

    this.unlistenFns.push(unlisten);
  }

  private handleIncoming<TPayload>(
    descriptor: SidecarEventDescriptor<TPayload>,
    rawPayload: unknown,
  ): void {
    // Every incoming payload is untrusted runtime data — the generic
    // type Tauri's `listen<T>()` accepts is not itself validation
    // (task brief §5/§6); the Part 2D-1 validator is the only thing
    // that decides whether this payload is accepted.
    if (!descriptor.validate(rawPayload)) {
      this.emitDiagnostic({
        kind: "invalid_payload",
        eventName: descriptor.eventName,
        rawPayload,
      });
      return;
    }

    const sequence = descriptor.sequenceOf(rawPayload);
    if (sequence <= this.lastAppliedSequence) {
      this.emitDiagnostic({
        kind: "stale_sequence",
        eventName: descriptor.eventName,
        sequence,
        lastAppliedSequence: this.lastAppliedSequence,
      });
      return;
    }

    // sequence is stored and forwarded exactly as received — never
    // regenerated, reinterpreted, or altered.
    this.lastAppliedSequence = sequence;

    const domainEvent = { kind: descriptor.kind, payload: rawPayload } as SidecarDomainEvent;
    for (const listener of this.listeners) {
      listener(domainEvent);
    }
  }

  private emitDiagnostic(diagnostic: SidecarDiagnostic): void {
    for (const listener of this.diagnosticListeners) {
      listener(diagnostic);
    }
  }
}

/**
 * The one application-wide instance real call sites use. A future
 * Part 2D-3 projection store subscribes here via `onEvent()`; nothing
 * else in the frontend should construct its own
 * `SidecarEventSubscription` against the real Tauri runtime (task
 * brief §4: "one authoritative subscription mechanism").
 */
export const sidecarEvents = new SidecarEventSubscription();
