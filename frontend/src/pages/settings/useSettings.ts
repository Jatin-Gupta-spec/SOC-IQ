/**
 * Settings data-fetch layer -- SOC-IQ Part 2B-1.
 *
 * Consumes the existing `get_settings` command (Part 2A backend read
 * contract) through the canonical `runCommand()` transport, mirroring
 * `useDashboard.ts`'s own request-lifecycle shape (loading/success/error
 * states, a cancellation flag plus a monotonic generation token so a
 * superseded/unmounted request can never publish stale data, and a
 * `retry()` that starts a fresh cycle).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand } from "../../shared/api/client";
import type { GetSettingsResult } from "../../shared/api/types";

export type SettingsLoadState = "loading" | "success" | "error";

export interface UseSettingsResult {
  readonly state: SettingsLoadState;
  /** `null` until a successful request is applied. */
  readonly settings: GetSettingsResult | null;
  /** The raw command/client error from the failed request. */
  readonly error: unknown | null;
  /** Starts a fresh request cycle and clears the previous result/error. */
  readonly retry: () => void;
}

interface InternalState {
  readonly state: SettingsLoadState;
  readonly settings: GetSettingsResult | null;
  readonly error: unknown | null;
}

function loadingState(): InternalState {
  return { state: "loading", settings: null, error: null };
}

export function useSettings(): UseSettingsResult {
  const [internal, setInternal] = useState<InternalState>(loadingState);
  const generationRef = useRef(0);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const generation = ++generationRef.current;

    setInternal(loadingState());

    void runCommand("get_settings", {}).then(
      (result) => {
        if (cancelled || generation !== generationRef.current) {
          return;
        }
        setInternal({ state: "success", settings: result, error: null });
      },
      (error: unknown) => {
        if (cancelled || generation !== generationRef.current) {
          return;
        }
        setInternal({ state: "error", settings: null, error });
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
    settings: internal.settings,
    error: internal.error,
    retry,
  };
}
