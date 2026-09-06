import { useEffect, type ReactElement } from "react";
import { HashRouter } from "react-router-dom";
import { ErrorBoundary } from "./providers/ErrorBoundary";
import { ThemeProvider } from "./providers/ThemeProvider";
import { AppRoutes } from "./router";
import { AppShell } from "./shell/AppShell";
import { startSidecarLifecycle } from "./sidecarLifecycle";
import { restartExhaustedNotification } from "../shared/notifications/restartExhaustedNotificationStore";

/**
 * Application composition root.
 *
 * Composes the architectural foundations established across this
 * project (error boundary, theme/token provider, sole ownership of
 * the sidecar lifecycle's startup/shutdown per
 * `docs/phase4/PHASE4G_IMPLEMENTATION_READINESS.md` §D/§E, and the
 * `AppShell` layout foundation from Part 1), plus — new in Phase
 * 4G-2 Part 2 — `HashRouter`, wrapped around `AppShell` so both the
 * sidebar (inside `AppShell`) and the routed content (`AppRoutes`,
 * `AppShell`'s child) share one router instance and one source of
 * truth for the current route. This is the only structural change
 * this checkpoint makes to `App.tsx`; Part 3 (mock pages) only needs
 * to fill in what `AppRoutes` already renders, not touch this file.
 * No feature-page functionality.
 *
 * # Restart-exhausted notification (4G-4 Part 2)
 *
 * A second, independent effect starts/stops
 * `restartExhaustedNotification`, mirroring the sidecar-lifecycle
 * effect above exactly — one composition-root-owned start/stop pair,
 * nothing else. It is a separate effect (not folded into the one
 * above) because the two have separate ownership: this store
 * subscribes to the already-running sidecar projection, it does not
 * start or stop it (see `restartExhaustedNotification.ts`'s own
 * ownership-boundary doc) — collapsing them into one effect would
 * blur that only-`startSidecarLifecycle`-owns-the-sidecar boundary
 * for no benefit. `AppShell` (mounted below) only ever reads this
 * store through `RestartExhaustedNotification`/
 * `useRestartExhaustedNotification`; it never calls
 * `initialize()`/`dispose()` itself.
 */
export function App(): ReactElement {
  useEffect(() => {
    const sidecarLifecycle = startSidecarLifecycle();
    return () => {
      sidecarLifecycle.stop();
    };
  }, []);

  useEffect(() => {
    restartExhaustedNotification.initialize();
    return () => {
      restartExhaustedNotification.dispose();
    };
  }, []);

  return (
    <ErrorBoundary>
      <ThemeProvider>
        <HashRouter>
          <AppShell>
            <AppRoutes />
          </AppShell>
        </HashRouter>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
