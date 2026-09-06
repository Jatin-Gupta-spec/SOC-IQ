/**
 * Sidecar snapshot integration, reconciliation, and event/snapshot
 * race handling — Phase 4E-P3 Part 2D-3C.
 *
 * This is the one place `get_sidecar_status` (`shared/api/client.ts`'s
 * `getSidecarStatus()`) is ever called from the sidecar projection
 * pipeline, and the one place a `SidecarStatus` snapshot is ever
 * compared against the projection store's live, event-derived state.
 * Frozen layers this module depends on but never modifies:
 *
 * - `eventSubscription.ts` (Part 2D-2) — real Tauri `listen()`.
 * - `projectionConnector.ts` (Part 2D-3B) — event -> store wiring.
 * - `projectionStore.ts` (Part 2D-3A) — the authoritative container.
 *
 * # The central requirement
 *
 * A stale snapshot must never overwrite newer accepted event state,
 * including when events arrive while the snapshot request is in
 * flight. This module's entire design exists to satisfy that one
 * sentence.
 *
 * # Why no redundant event queue (task brief §14)
 *
 * `SidecarProjectionConnector` (frozen, Part 2D-3B) already applies
 * every accepted event to `SidecarProjectionStore` the moment it
 * arrives, completely independently of whether a snapshot request is
 * in flight — it has no notion of "pause while a snapshot is
 * pending". That means the store's `getState()?.sequence` at the
 * moment a snapshot promise *resolves* already reflects every event
 * that arrived during the request, with no buffering needed here.
 * Reconciliation therefore only has to compare the snapshot's own
 * `sequence` against whatever `getState()` returns *at that instant*
 * — a redundant queue that re-buffers events already durably applied
 * to the store would duplicate state the store already owns.
 *
 * # Snapshot contract (task brief §3, verified against
 * `src-tauri/src/events.rs`'s `SidecarStatus` and `lib.rs`'s
 * `get_sidecar_status`)
 *
 * - Return type: `SidecarStatus` (`events.rs`), not a `Result` — the
 *   Rust command itself is infallible (it only *reads* four existing
 *   authorities, never fails a precondition). "Failure" on the
 *   frontend side is therefore only ever a transport-level problem:
 *   `invoke()` rejecting, or a structurally malformed response —
 *   both already turned into `SidecarStatusUnavailableError` by
 *   `getSidecarStatus()` (`shared/api/client.ts`), which this module
 *   treats uniformly as "no usable snapshot this attempt".
 * - `sequence: u64` — "the latest already-allocated event sequence
 *   ... never a newly allocated one" (`events.rs`'s own doc on the
 *   field). It is the exact same opaque, monotonically-increasing,
 *   single-global-counter value `eventSubscription.ts` already
 *   tracks per event — not a second, incompatible ordering scheme.
 * - State completeness: `SidecarStatus` has no `Option<T>` field
 *   left unaccounted for except `restart_pending_attempt` (`Option<u32>`,
 *   already `T | null` in `types.ts`/already validated by
 *   `isSidecarStatus`) — every other field is required. The snapshot
 *   is therefore the *complete* `SidecarStatus` shape, not a partial
 *   patch (task brief §3.C/§22): reconciliation always replaces the
 *   store's entire projected value with the snapshot's, in one atomic
 *   `applyProjectedState()` call, never a field-by-field merge.
 * - Atomicity (task brief §3.F): `get_sidecar_status`'s own doc
 *   comment documents that it reads four *independent* locks
 *   (`process`, `scheduler`, `restart_tracker`, `events`), each held
 *   only long enough for its own field, with no combined lock — so an
 *   event can in principle land between two of those reads on the
 *   Rust side. This module cannot close that window (task brief §4:
 *   the backend is frozen/authoritative) — it only guarantees that
 *   *whatever* `SidecarStatus` value arrives is applied to the store
 *   atomically (assign, then notify), via the already-atomic
 *   `SidecarProjectionStore.applyProjectedState()` (Part 2D-3A,
 *   unmodified).
 *
 * # Reconciliation algorithm (task brief §12/§13/§15)
 *
 *     accept the snapshot as authoritative
 *         iff current === null (nothing projected yet)
 *         OR  snapshot.sequence >= current.sequence
 *     otherwise: reject (stale), never applied, never notified
 *
 * This single rule, applied against the store's *live* sequence at
 * the moment the snapshot resolves (not a value captured before the
 * request started), is what makes every race in task brief §8-§11
 * resolve correctly with zero additional bookkeeping:
 *
 * | scenario (task brief §25) | store seq when snapshot resolves | rule result |
 * |---|---|---|
 * | event 11 -> snapshot 10 | 11 | `10 < 11` -> reject; final stays 11 |
 * | snapshot 10 -> event 11 | snapshot applied first (seq 10), then event 11 applied normally by the connector | final 11 |
 * | event 10 -> snapshot 11 | 10 | `11 >= 10` -> apply; final 11 |
 * | event 10 -> snapshot 10 | 10 | `10 >= 10` -> apply (see equal-sequence rule below); final stays 10 |
 * | event 11 -> event 12 -> snapshot 10 | 12 | `10 < 12` -> reject; final stays 12 |
 * | snapshot 10 -> event 11 -> event 12 -> snapshot 9 | first snapshot applied (10), then 11, then 12 (store seq 12); second snapshot: `9 < 12` -> reject | final stays 12 |
 * | snapshot pending -> event 11 -> snapshot 11 | 11 | `11 >= 11` -> apply (equal-sequence rule); final 11 |
 * | snapshot pending -> event 11,12,13 -> snapshot 10 | 13 | `10 < 13` -> reject; final stays 13 |
 *
 * The rule never generates, increments, decrements, resets, or
 * reinterprets a sequence (task brief §13) — `reconcileSnapshot()`
 * only ever compares two backend-issued `u64` values with `>=`/`<`.
 *
 * # Equal-sequence rule (task brief §12/§26, documented decision)
 *
 * Chosen behavior: **the snapshot is authoritative at equal
 * sequence** (applied, replacing the store's current value). Why this
 * is the correct, safest choice rather than an arbitrary one:
 *
 * 1. It cannot roll the store backwards — `sequence` itself is
 *    unchanged (`snapshot.sequence === current.sequence`), so the
 *    ordering invariant this whole module exists to protect is
 *    trivially preserved either way; the only thing an equal-sequence
 *    snapshot can change is the four restart-accounting fields.
 * 2. `eventProjection.ts`'s own module doc (Part 2D-3B, frozen)
 *    documents a *known, accepted* limitation: `restart_pending` can
 *    read stale between a scheduled restart actually firing and the
 *    next event, because no single event payload carries that
 *    cross-stream correlation. That same doc explicitly names
 *    `get_sidecar_status`-backed reconciliation (this checkpoint) as
 *    the thing that closes that gap. An equal-sequence snapshot is
 *    exactly the case where event-derived `state`/`sequence` are
 *    already correct but the restart-accounting fields might not be —
 *    rejecting the snapshot here would mean this known gap can never
 *    actually be closed for a sidecar that is otherwise idle (no new
 *    events arriving to trigger a newer-sequence snapshot).
 * 3. `SidecarProjectionStore.applyProjectedState()` (frozen, Part
 *    2D-3A) already performs a full field-by-field equality check and
 *    skips notification when nothing actually changed — so applying
 *    an equal-sequence snapshot that happens to be byte-identical to
 *    the current state is a correctly silent no-op (task brief §24),
 *    not a spurious re-render.
 *
 * # State preservation (task brief §22)
 *
 * Because the snapshot is the complete `SidecarStatus` shape (see
 * above), "apply" always means "replace the store's entire value with
 * the snapshot's", never a partial merge — there is no stale field to
 * accidentally retain and no valid field to accidentally erase, since
 * the snapshot owns every field the store's shape has.
 *
 * # Initialization flow (task brief §7/§19/§20/§21)
 *
 *     initialize()
 *         -> connector.initialize()            (sync: register the
 *                                                  event -> store wiring)
 *         -> await subscription.start()         (establish real Tauri
 *                                                  listen() registrations
 *                                                  BEFORE requesting a
 *                                                  snapshot -- the
 *                                                  unsafe order task
 *                                                  brief §7 explicitly
 *                                                  forbids is reversed)
 *         -> await fetchStatus()                (get_sidecar_status)
 *         -> reconcileSnapshot(store.getState(), status)
 *         -> apply via store.applyProjectedState() if authoritative
 *
 * `connector.initialize()` runs first and is synchronous — by the
 * time `subscription.start()`'s `await` yields control back to the
 * event loop, the connector's `onEvent()` callback is already
 * registered, so no event delivered once real listening begins can
 * ever be missed (task brief §7's exact requirement).
 *
 * Repeated `initialize()` (task brief §19): while a previous
 * `initialize()` is still in flight (`"initializing"`) or has already
 * completed (`"active"`), a further call returns the *same* promise
 * rather than launching a second `connector.initialize()` (itself
 * already idempotent) or a second concurrent snapshot request —
 * deterministic, no duplicate registrations, no uncontrolled
 * concurrent `get_sidecar_status` calls.
 *
 * Disposal / reinitialization / stale async results (task brief
 * §20/§21): every `initialize()` call captures a private, monotonic
 * `generation` number; `dispose()` bumps it. The one asynchronous gap
 * in the whole sequence (`await fetchStatus()`) is followed by a
 * generation check *before* touching the store — a snapshot that
 * resolves after `dispose()` (or after a newer `initialize()` has
 * already started) is discarded as `"superseded"`, never applied,
 * exactly the `initialize A -> snapshot A pending -> dispose ->
 * initialize B -> snapshot B resolves -> snapshot A resolves later`
 * race task brief §20 names explicitly. `dispose()` itself calls
 * `connector.dispose()` (tearing down the wiring this coordinator
 * turned on) but never `subscription.stop()` or `store.dispose()` —
 * neither belongs to this coordinator, the same ownership discipline
 * `projectionConnector.ts`'s own module doc already established one
 * layer down.
 *
 * # Snapshot failure / initialization failure (task brief §17/§18)
 *
 * `initialize()` never rejects — every failure path resolves with an
 * explicit `{ kind: "failed", error }` (or `"superseded"`) outcome
 * instead, matching this codebase's established "log/report, never
 * throw across an async lifecycle boundary" convention
 * (`projectionStore.ts`/`projectionConnector.ts`'s own `notify()`/
 * `handleEvent()`). A failed or superseded snapshot never touches the
 * store — whatever valid event-derived state the store already holds
 * (or `null`, if none yet) is left completely untouched, and the
 * coordinator's own lifecycle still reaches `"active"` rather than
 * getting stuck in `"initializing"` forever, since
 * `connector.initialize()` already ran and events continue projecting
 * normally regardless of snapshot outcome.
 *
 * # Notification (task brief §24)
 *
 * Never notifies for: a fetch failure, a malformed response (both
 * already rejected before this module ever sees a value), a stale
 * (rejected-by-sequence) snapshot, or an accepted snapshot that
 * doesn't actually change any field — all four fall out of composing
 * two already-correct behaviors (`reconcileSnapshot()` returning
 * `null` for stale, `applyProjectedState()`'s own equality check) with
 * no new special-casing needed here.
 */

import { getSidecarStatus } from "../api/client";
import {
  sidecarEvents,
  type SidecarEventSubscription,
} from "./eventSubscription";
import {
  sidecarProjectionConnector,
  type SidecarProjectionConnector,
} from "./projectionConnector";
import {
  sidecarProjection,
  type SidecarProjectionState,
  type SidecarProjectionStore,
} from "./projectionStore";
import type { SidecarStatus } from "./types";

// ---------------------------------------------------------------------------
// Pure reconciliation rule (task brief §11: kept separate and testable
// in isolation, mirroring eventProjection.ts's own separation from its
// connector).
// ---------------------------------------------------------------------------

/**
 * Decide whether `snapshot` is authoritative against the store's
 * current projected state. Returns the `SidecarStatus` to apply
 * (always `snapshot` itself, verbatim — never merged, never mutated)
 * when authoritative, or `null` when the snapshot must be rejected as
 * stale. See this module's doc comment for the full algorithm and the
 * documented equal-sequence decision. Never generates, increments,
 * decrements, or reinterprets a sequence — the comparison is the only
 * thing this function does.
 */
export function reconcileSnapshot(
  current: SidecarProjectionState,
  snapshot: SidecarStatus,
): SidecarStatus | null {
  if (current === null) return snapshot;
  if (snapshot.sequence < current.sequence) return null;
  return snapshot;
}

// ---------------------------------------------------------------------------
// Diagnostics (task brief §17/§18: expose/record failure per this
// codebase's existing convention -- eventSubscription.ts's onDiagnostic()
// shape, reused rather than reinvented)
// ---------------------------------------------------------------------------

export type SidecarSnapshotDiagnostic =
  | { readonly kind: "snapshot_fetch_failed"; readonly error: unknown }
  | {
      readonly kind: "snapshot_rejected_stale";
      readonly snapshot: SidecarStatus;
      readonly currentSequence: number;
    }
  | { readonly kind: "snapshot_applied"; readonly snapshot: SidecarStatus }
  | { readonly kind: "snapshot_superseded"; readonly snapshot: SidecarStatus | null };

export type SidecarSnapshotDiagnosticListener = (
  diagnostic: SidecarSnapshotDiagnostic,
) => void;

/**
 * The outcome of one `initialize()` call's reconciliation attempt.
 * Never a rejection (task brief §18's documented decision) — every
 * path, including failure, is represented here.
 */
export type SidecarReconciliationOutcome =
  | { readonly kind: "applied"; readonly status: SidecarStatus }
  | { readonly kind: "stale"; readonly status: SidecarStatus }
  | { readonly kind: "failed"; readonly error: unknown }
  | { readonly kind: "superseded" };

type ReconcilerLifecycle = "uninitialized" | "initializing" | "active" | "disposed";

interface SidecarSnapshotReconcilerOptions {
  /** Defaults to the one application-wide `sidecarProjectionConnector` (Part 2D-3B). Tests inject an isolated instance instead. */
  readonly connector?: SidecarProjectionConnector;
  /** Defaults to the one application-wide `sidecarProjection` store (Part 2D-3A). Tests inject an isolated instance instead. */
  readonly store?: SidecarProjectionStore;
  /** Defaults to the one application-wide `sidecarEvents` subscription (Part 2D-2). Tests inject an isolated instance instead. */
  readonly subscription?: SidecarEventSubscription;
  /** Defaults to the real `getSidecarStatus()` (`shared/api/client.ts`). Tests inject a controlled fake instead of mocking Tauri directly. */
  readonly fetchStatus?: () => Promise<SidecarStatus>;
}

/**
 * Orchestrates the deterministic initialization flow described in this
 * module's doc comment: connect event projection, then request and
 * reconcile the sidecar snapshot, then store the authoritative result.
 * One instance owns, at most, one in-flight `initialize()` sequence at
 * a time.
 */
export class SidecarSnapshotReconciler {
  private readonly connector: SidecarProjectionConnector;
  private readonly store: SidecarProjectionStore;
  private readonly subscription: SidecarEventSubscription;
  private readonly fetchStatus: () => Promise<SidecarStatus>;
  private readonly diagnosticListeners = new Set<SidecarSnapshotDiagnosticListener>();

  private lifecycle: ReconcilerLifecycle = "uninitialized";
  /** Bumped by every `initialize()` and every `dispose()` call (task brief §20/§21). */
  private generation = 0;
  private initPromise: Promise<SidecarReconciliationOutcome> | null = null;

  constructor(options: SidecarSnapshotReconcilerOptions = {}) {
    this.connector = options.connector ?? sidecarProjectionConnector;
    this.store = options.store ?? sidecarProjection;
    this.subscription = options.subscription ?? sidecarEvents;
    this.fetchStatus = options.fetchStatus ?? getSidecarStatus;
  }

  /** `"uninitialized"` before the first `initialize()`; `"initializing"` while the sequence above is in flight; `"active"` once it has settled (applied, stale, or failed -- all reach `"active"`, task brief §18); `"disposed"` after `dispose()`. */
  getLifecycle(): ReconcilerLifecycle {
    return this.lifecycle;
  }

  /** Subscribe to reconciliation diagnostics (fetch failure, stale rejection, applied, superseded). Returns an unsubscribe function. */
  onDiagnostic(listener: SidecarSnapshotDiagnosticListener): () => void {
    this.diagnosticListeners.add(listener);
    return () => {
      this.diagnosticListeners.delete(listener);
    };
  }

  // -------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------

  /**
   * Run the deterministic initialization flow. Repeated calls while
   * already `"initializing"` or `"active"` return the same promise
   * (task brief §19) rather than repeating any step. Safe to call
   * again after `dispose()` (task brief §20's restartable sequence).
   */
  initialize(): Promise<SidecarReconciliationOutcome> {
    if (
      (this.lifecycle === "initializing" || this.lifecycle === "active") &&
      this.initPromise
    ) {
      return this.initPromise;
    }

    this.lifecycle = "initializing";
    const generation = ++this.generation;

    // Synchronous: the event -> store wiring is registered before any
    // `await` below yields control back to the event loop (task brief
    // §7's ordering requirement).
    this.connector.initialize();

    const promise = this.runSequence(generation);
    this.initPromise = promise;
    return promise;
  }

  /**
   * Tear down this coordinator's own contribution: invalidates any
   * in-flight snapshot request (task brief §21) and disposes the
   * connector registration this coordinator turned on. Never touches
   * `subscription`'s own start/stop lifecycle or `store`'s own
   * dispose lifecycle -- neither belongs to this coordinator (same
   * ownership boundary `projectionConnector.ts` already established
   * one layer down). Safe to call repeatedly, including before
   * `initialize()` has ever run.
   */
  dispose(): void {
    this.generation += 1;
    if (this.lifecycle !== "uninitialized" && this.lifecycle !== "disposed") {
      this.connector.dispose();
    }
    this.lifecycle = "disposed";
    this.initPromise = null;
  }

  // -------------------------------------------------------------------
  // Internals
  // -------------------------------------------------------------------

  private async runSequence(
    generation: number,
  ): Promise<SidecarReconciliationOutcome> {
    // `SidecarEventSubscription.start()` (Part 2D-2, frozen) never
    // rejects -- a single failed registration is reported via its own
    // onDiagnostic() channel, not thrown (see its module doc). It is
    // also idempotent/safe to call even if some other part of the
    // application already called it. Awaited here so real Tauri
    // listen() registration is confirmed established before the
    // snapshot request below is issued.
    await this.subscription.start();

    let status: SidecarStatus;
    try {
      status = await this.fetchStatus();
    } catch (error) {
      if (generation === this.generation) {
        this.lifecycle = "active";
      }
      this.emitDiagnostic({ kind: "snapshot_fetch_failed", error });
      return { kind: "failed", error };
    }

    if (generation !== this.generation) {
      // A dispose() and/or a newer initialize() has already
      // superseded this in-flight request -- discard without ever
      // touching the store (task brief §20/§21's exact race).
      this.emitDiagnostic({ kind: "snapshot_superseded", snapshot: status });
      return { kind: "superseded" };
    }

    const current = this.store.getState();
    const next = reconcileSnapshot(current, status);

    if (next === null) {
      this.lifecycle = "active";
      this.emitDiagnostic({
        kind: "snapshot_rejected_stale",
        snapshot: status,
        currentSequence: current?.sequence ?? 0,
      });
      return { kind: "stale", status };
    }

    // Atomic from the store's own perspective (assign, then notify --
    // Part 2D-3A, unmodified); a no-op notification if `next` is
    // field-for-field identical to `current` (task brief §24).
    this.store.applyProjectedState(next);
    this.lifecycle = "active";
    this.emitDiagnostic({ kind: "snapshot_applied", snapshot: next });
    return { kind: "applied", status: next };
  }

  private emitDiagnostic(diagnostic: SidecarSnapshotDiagnostic): void {
    for (const listener of this.diagnosticListeners) {
      listener(diagnostic);
    }
  }
}

/**
 * The one application-wide instance real call sites use, wiring the
 * one application-wide `sidecarProjectionConnector`/`sidecarProjection`
 * /`sidecarEvents` together with the real `getSidecarStatus()`. Not
 * initialized here -- a future UI-integration checkpoint calls
 * `sidecarSnapshotReconciler.initialize()` once at application
 * startup (out of scope for this checkpoint -- task brief §29: "No UI
 * work").
 */
export const sidecarSnapshotReconciler = new SidecarSnapshotReconciler();
