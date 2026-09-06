import {
  sidecarSnapshotReconciler,
  type SidecarSnapshotReconciler,
} from "../shared/sidecar/snapshotReconciliation";

/**
 * Sidecar lifecycle ownership — Phase 4G Implementation Part 1.
 *
 * This is the *only* place in the application that calls
 * `SidecarSnapshotReconciler.initialize()` / `.dispose()`. It adds no
 * lifecycle state of its own: every idempotency, ordering, and
 * async-race guarantee (repeated `initialize()` while in flight
 * returns the same promise; `dispose()` is safe before `initialize()`
 * has ever run; a stale in-flight snapshot from a superseded
 * generation cannot mutate a newer lifecycle's state) is already
 * established and frozen in `snapshotReconciliation.ts`
 * (Part 2D-3C/3D). This module exists solely to give that already-
 * correct lifecycle exactly one caller, per
 * `docs/phase4/PHASE4G_IMPLEMENTATION_READINESS.md` §D/§E.
 *
 * Deliberately not a React hook/component: the composition root
 * (`App.tsx`) only needs a single mount-time call and a single
 * unmount-time call, which a plain `useEffect` one-liner already
 * expresses without introducing a new abstraction. Keeping this a
 * plain function also means the ownership chain
 * (composition root -> reconciler -> subscription -> connector ->
 * store) can be integration-tested directly, without any React
 * rendering machinery this project does not otherwise use in tests.
 */

export interface SidecarLifecycleOwner {
  /**
   * Disposes the sidecar lifecycle. Idempotent — delegates entirely
   * to the frozen reconciler's own idempotent `dispose()`. Safe to
   * call multiple times, and safe to call while `initialize()` is
   * still in flight (readiness doc §H / §K "shutdown during
   * initialization").
   */
  readonly stop: () => void;
}

/**
 * Starts the sidecar lifecycle exactly once for this owner and
 * returns a handle to stop it. The `reconciler` parameter exists only
 * as a test-injection point (mirroring the same constructor-injection
 * pattern `SidecarSnapshotReconciler` itself already uses for
 * `connector`/`store`/`subscription`/`fetchStatus`); production code
 * always uses the default, the one application-wide
 * `sidecarSnapshotReconciler` singleton — never a second instance.
 *
 * Startup failure handling (readiness doc §H): `initialize()` itself
 * never rejects — every outcome, including a failed snapshot fetch,
 * is represented in its resolved `SidecarReconciliationOutcome` and
 * surfaced through the reconciler's own `onDiagnostic()` channel
 * (`snapshotReconciliation.ts`'s documented decision). Rather than
 * inventing a new error framework, this function uses that existing
 * channel: a `"snapshot_fetch_failed"` diagnostic is logged, not
 * swallowed silently. The reconciler itself already reaches its own
 * `"active"` lifecycle state after such a failure, so the application
 * stays in a coherent, non-crashed state on its own — nothing here
 * needs to retry or fail fast. The `.catch()` below is purely
 * defensive, in case a future change to that contract ever introduces
 * a genuine rejection; it must never propagate uncaught and crash the
 * app.
 */
export function startSidecarLifecycle(
  reconciler: SidecarSnapshotReconciler = sidecarSnapshotReconciler,
): SidecarLifecycleOwner {
  const unsubscribeDiagnostics = reconciler.onDiagnostic((diagnostic) => {
    if (diagnostic.kind === "snapshot_fetch_failed") {
      // eslint-disable-next-line no-console
      console.error(
        "SOC-IQ: sidecar snapshot fetch failed during startup",
        diagnostic.error,
      );
    }
  });

  reconciler.initialize().catch((error: unknown) => {
    // eslint-disable-next-line no-console
    console.error("SOC-IQ: sidecar lifecycle initialization failed", error);
  });

  return {
    stop: () => {
      unsubscribeDiagnostics();
      reconciler.dispose();
    },
  };
}
