/**
 * React hook consumer for the frozen sidecar projection store —
 * Phase 4G-3 Part 1.
 *
 * This is the *first* React-facing read of the sidecar state chain
 * (`SidecarSnapshotReconciler` -> `SidecarEventSubscription` ->
 * event/snapshot projection -> `SidecarProjectionStore`, all frozen
 * as of 4G-2). Nothing about that chain changes here: this hook only
 * subscribes to the one already-existing application-wide store
 * instance, `sidecarProjection` (`projectionStore.ts`), and re-renders
 * the calling component when it changes.
 *
 * # Why `useSyncExternalStore`
 *
 * `sidecarProjection` is exactly the kind of external, mutable,
 * subscribe/getSnapshot store this hook exists for — the same store
 * already used by `sidecarLifecycle.ts`'s non-React callers. A plain
 * `useState` + `useEffect(() => store.subscribe(setState), [])` (the
 * pattern `useEventStreamStatus.ts` uses for the SSE connection
 * status) would work for the common case, but `useSyncExternalStore`
 * is the correct primitive for this exact situation: it reads
 * `getState()` synchronously during render (so no stale value can
 * ever flash before the first effect runs), and it de-dupes/repairs
 * itself correctly across React 18 concurrent rendering and Strict
 * Mode's deliberate double-invocation of effects — both of which a
 * hand-rolled `useState`/`useEffect` pair can tear under. No new
 * dependency: `useSyncExternalStore` ships with React 18
 * (`react` is already `^18.3.1`, `App.tsx` already exercises Strict
 * Mode's double-effect behavior via `navigation.live.test.tsx`'s live
 * DOM tests).
 *
 * # Initial state (task brief §6)
 *
 * `sidecarProjection.getState()` already returns `null` until the
 * frozen reconciler has applied a first real `SidecarStatus` — this
 * hook does not invent a second "unknown" representation on top of
 * that; it hands back exactly what the store holds, including `null`,
 * unchanged. A caller that wants a normalized display vocabulary
 * (`"unknown"` / `"starting"` / `"connected"` / ...) uses
 * `sidecarStatusView.ts`'s `projectSidecarStatusView()` on this hook's
 * return value — kept as a separate, pure, non-hook module so the
 * subscription concern here stays independent of the display-mapping
 * concern there (task brief §4's "smallest appropriate abstraction").
 *
 * # Subscription lifecycle (task brief §7)
 *
 * `subscribe` below is called by React itself (on mount, and again on
 * every Strict Mode double-invocation) and always delegates straight
 * to `sidecarProjection.subscribe()`, which already de-dupes same-
 * reference listeners and safely unsubscribes (`projectionStore.ts`'s
 * own documented guarantees) — this hook adds no subscription
 * bookkeeping of its own to duplicate that.
 *
 * # Error/unknown-state safety (task brief §8)
 *
 * This hook does not interpret `SidecarStatus.state` at all — it is a
 * plain passthrough of whatever `sidecarProjection` holds, so an
 * unrecognized *future* lifecycle string can never throw here; that
 * interpretation (and its safe-fallback handling) belongs entirely to
 * `sidecarStatusView.ts`, which is the one place in this checkpoint
 * that reads `.state`.
 */

import { useSyncExternalStore } from "react";
import {
  sidecarProjection,
  type SidecarProjectionStore,
  type SidecarProjectionState,
} from "./projectionStore";

/**
 * Returns the current sidecar projection state — `null` until the
 * frozen reconciler has applied a first snapshot/event, the most
 * recently applied `SidecarStatus` after that — and re-renders the
 * calling component whenever it changes. Does not own, start, or stop
 * the sidecar lifecycle (that remains `sidecarLifecycle.ts`'s sole
 * responsibility, per `App.tsx`); this hook only ever reads.
 *
 * `store` exists only as a test-injection point, mirroring the same
 * constructor-injection pattern already established elsewhere in this
 * chain (`startSidecarLifecycle`'s `reconciler` parameter,
 * `SidecarSnapshotReconciler`'s own `connector`/`store`/`subscription`
 * parameters) — production call sites never pass it, and always get
 * the one application-wide `sidecarProjection` singleton every other
 * production caller already shares.
 */
export function useSidecarStatus(
  store: SidecarProjectionStore = sidecarProjection,
): SidecarProjectionState {
  return useSyncExternalStore(
    (onStoreChange) => store.subscribe(() => onStoreChange()),
    () => store.getState(),
    () => store.getState(),
  );
}
