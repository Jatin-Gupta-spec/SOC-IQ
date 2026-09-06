/**
 * Dashboard investigation-activity data-fetch layer — MAX-5 (Dashboard
 * Data + Visualization Foundation).
 *
 * Consumes the existing `get_investigation_aggregate_summary` command
 * (PD-04) through the canonical `runCommand()` transport, the same
 * transport `useDashboard()` already uses. This is the one genuine
 * temporal series SOC-IQ's backend actually exposes today --
 * `investigations_by_date`, a real day-bucketed count of
 * investigations grouped by each investigation's persisted
 * `analyzed_at` (see `InvestigationAggregateSummaryResult`'s own doc
 * comment, `shared/api/types.ts`). No risk-trend or IOC-trend series
 * exists in the backend, so this hook exposes only what is real.
 *
 * Kept as a request independent from `useDashboard()`'s own
 * `get_dashboard_summary` fetch, rather than merged into it, so a
 * failure or slow response fetching the activity trend can never
 * block or fail the rest of the Dashboard's already-real widgets
 * (KPIs, risk/IOC distribution, recent investigations) -- the two
 * commands are already separate, independently-callable backend
 * commands, and this hook does not invent a coupling between them
 * that the backend contract does not have.
 *
 * Mirrors `useDashboard()`'s own request-lifecycle idiom exactly
 * (closure-scoped cancellation flag + monotonically increasing
 * generation token, so a superseded/unmounted retry can never publish
 * stale data) rather than inventing a second pattern for the same
 * problem.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand } from "../../shared/api/client";
import type { InvestigationAggregateSummaryResult } from "../../shared/api/types";

export type InvestigationActivityLoadState = "loading" | "success" | "error";

export interface UseInvestigationActivityResult {
  readonly state: InvestigationActivityLoadState;
  /** `null` until a successful request is applied. A successful empty
   * aggregate is represented by the real DTO's empty `investigations_by_date`,
   * never by fallback data. */
  readonly activity: InvestigationAggregateSummaryResult | null;
  /** The raw command/client error from the failed request. */
  readonly error: unknown | null;
  /** Starts a fresh request cycle and clears the previous result/error. */
  readonly retry: () => void;
}

interface InternalState {
  readonly state: InvestigationActivityLoadState;
  readonly activity: InvestigationAggregateSummaryResult | null;
  readonly error: unknown | null;
}

function loadingState(): InternalState {
  return { state: "loading", activity: null, error: null };
}

export function useInvestigationActivity(): UseInvestigationActivityResult {
  const [internal, setInternal] = useState<InternalState>(loadingState);
  const generationRef = useRef(0);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const generation = ++generationRef.current;

    setInternal(loadingState());

    void runCommand("get_investigation_aggregate_summary", {}).then(
      (result) => {
        if (cancelled || generation !== generationRef.current) {
          return;
        }
        setInternal({ state: "success", activity: result, error: null });
      },
      (error: unknown) => {
        if (cancelled || generation !== generationRef.current) {
          return;
        }
        setInternal({ state: "error", activity: null, error });
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
    activity: internal.activity,
    error: internal.error,
    retry,
  };
}
