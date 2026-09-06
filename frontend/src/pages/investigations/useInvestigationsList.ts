/**
 * Investigations list data-fetch layer — Investigations page real
 * backend wiring.
 *
 * The one place `InvestigationsPage` gets its data from. Calls the
 * existing, already-typed `list_investigations` command
 * (`shared/api/types.ts::CommandContracts["list_investigations"]`)
 * through the existing `runCommand<K>()` transport
 * (`shared/api/client.ts`) — no second API client, no direct
 * `fetch()`/`invoke()`, no new backend command.
 *
 * # Fetch behavior
 *
 * Mirrors `pages/investigation/useInvestigation.ts`'s established
 * cancellation/generation discipline exactly, adapted to a single
 * fetch instead of three concurrent ones: each effect invocation gets
 * its own closure-scoped `cancelled` flag (so React 18 Strict Mode's
 * mandatory mount→cleanup→mount double-invocation can never leave a
 * shared ref permanently `false`), and a monotonically increasing
 * `generationRef` additionally guards the retry-while-in-flight race.
 * A settlement only applies if it is both not cancelled *and* still
 * the current generation.
 *
 * # States
 *
 * `"loading"` -> `"success"` | `"error"`. There is no `"idle"` state
 * (unlike `useInvestigation`, which can be handed an invalid id) --
 * `list_investigations` takes no parameters, so a fetch always starts
 * immediately on mount. `"success"` and an empty array are both real,
 * distinct outcomes: an empty array means the backend genuinely
 * returned zero investigations, never a stand-in for "not fetched
 * yet" (that's `"loading"`).
 *
 * # Retry
 *
 * `retry()` starts a fresh request cycle (bumps a `retryNonce` the
 * fetch effect depends on) and resets to `"loading"` with the
 * previous result/error cleared -- same "no stale data next to a new
 * attempt" rule `useInvestigation.ts`'s retry follows.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand } from "../../shared/api/client";
import type { ListInvestigationsResult } from "../../shared/api/types";

export type InvestigationsListLoadState = "loading" | "success" | "error";

export interface UseInvestigationsListResult {
  readonly state: InvestigationsListLoadState;
  /** `null` until a successful `list_investigations` response has
   * been applied. A successful-but-empty response is `[]`, not
   * `null` -- those remain distinguishable (empty-list state vs.
   * not-yet-loaded state). */
  readonly investigations: ListInvestigationsResult | null;
  /** Set only when `state` is `"error"` -- the raw rejection from
   * `list_investigations` (a `CommandClientError` subclass or
   * `SidecarNotConnectedError`), never re-typed or narrowed here, so
   * a caller that needs the backend's exact error code can still get
   * it via `instanceof CommandFailedError`. */
  readonly error: unknown | null;
  /** Starts a fresh request cycle -- see the module doc comment's
   * "Retry" section. Safe to call at any time. */
  readonly retry: () => void;
}

interface InternalState {
  readonly state: InvestigationsListLoadState;
  readonly investigations: ListInvestigationsResult | null;
  readonly error: unknown | null;
}

function loadingState(): InternalState {
  return { state: "loading", investigations: null, error: null };
}

export function useInvestigationsList(): UseInvestigationsListResult {
  const [internal, setInternal] = useState<InternalState>(loadingState);
  const generationRef = useRef(0);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const generation = ++generationRef.current;

    setInternal(loadingState());

    void runCommand("list_investigations", {}).then(
      (result) => {
        if (cancelled || generation !== generationRef.current) {
          // Superseded by unmount, Strict Mode's discarded first
          // invocation, or a retry -- this settlement is stale and
          // must never overwrite newer state.
          return;
        }
        setInternal({ state: "success", investigations: result, error: null });
      },
      (error: unknown) => {
        if (cancelled || generation !== generationRef.current) {
          return;
        }
        setInternal({ state: "error", investigations: null, error });
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
    investigations: internal.investigations,
    error: internal.error,
    retry,
  };
}
