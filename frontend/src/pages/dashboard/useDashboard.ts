/**
 * Dashboard data-fetch layer — Phase 4H Part 2.
 *
 * The Dashboard consumes the existing aggregate `get_dashboard_summary`
 * command through the canonical `runCommand()` transport. This hook owns
 * only request lifecycle state; presentation mapping remains in
 * `dashboardViewModel.ts`.
 *
 * Like `useInvestigationsList()`, each request generation has both a
 * closure-scoped cancellation flag and a monotonically increasing
 * generation token. This prevents an unmounted/Strict-Mode-discarded or
 * superseded retry from publishing stale data.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand } from "../../shared/api/client";
import type { DashboardSummaryResult } from "../../shared/api/types";

export type DashboardLoadState = "loading" | "success" | "error";

export interface UseDashboardResult {
  readonly state: DashboardLoadState;
  /** `null` until a successful request is applied. A successful empty
   * aggregate is represented by the real DTO, never by fallback data. */
  readonly dashboard: DashboardSummaryResult | null;
  /** The raw command/client error from the failed request. */
  readonly error: unknown | null;
  /** Starts a fresh request cycle and clears the previous result/error. */
  readonly retry: () => void;
}

interface InternalState {
  readonly state: DashboardLoadState;
  readonly dashboard: DashboardSummaryResult | null;
  readonly error: unknown | null;
}

function loadingState(): InternalState {
  return { state: "loading", dashboard: null, error: null };
}

export function useDashboard(): UseDashboardResult {
  const [internal, setInternal] = useState<InternalState>(loadingState);
  const generationRef = useRef(0);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const generation = ++generationRef.current;

    setInternal(loadingState());

    void runCommand("get_dashboard_summary", {}).then(
      (result) => {
        if (cancelled || generation !== generationRef.current) {
          return;
        }
        setInternal({ state: "success", dashboard: result, error: null });
      },
      (error: unknown) => {
        if (cancelled || generation !== generationRef.current) {
          return;
        }
        setInternal({ state: "error", dashboard: null, error });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [retryNonce]);

  const retry = useCallback(() => {
    setRetryNonce((current) => current + 1);
  }, []);

  return {
    state: internal.state,
    dashboard: internal.dashboard,
    error: internal.error,
    retry,
  };
}
