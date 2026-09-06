/**
 * Analysis execution lifecycle hook — Phase 4I-1B, §6/§7/§10/§11.
 *
 * The one place that composes: the state machine transitions
 * (`analysisWorkflowState.ts`), the real execution adapter
 * (`analysisExecution.ts`), real progress consumed over the existing
 * SSE transport (`shared/events/useEventStream.ts`, §7: "if real
 * progress percentages exist: consume them" — this is that
 * consumption), and the report-path boundary (`analysisReportPath.ts`,
 * §3/§4).
 *
 * # Progress correlation (§7, §11)
 *
 * `AnalyzeReportCommandHandler` generates its `correlation_id`
 * server-side and only exposes it via the `analysis.started` event's
 * top-level `correlation_id` field (or the command's own response,
 * which arrives only at completion) — the frontend cannot know it in
 * advance. This hook adopts the id from the first `analysis.started`
 * event received while a run with no id yet is active, then filters
 * every subsequent `analysis.progress` event against it. This is a
 * best-effort correlation, not a guarantee: `EventBroker`
 * (`app/application/broker.py`) is a single shared stream with no
 * per-client scoping, so a *second, concurrent* `analyze_report` call
 * from a different client while this one is in flight cannot be
 * fully disambiguated by this contract alone. Documented here rather
 * than silently assumed away — §3's "do not invent backend
 * semantics" — because a client-scoped subscription does not exist
 * to invent from. Duplicate submission from *this* page is already
 * prevented structurally (`canStart` is only true from `ready`; see
 * below), which is the case this checkpoint's own UI can guarantee.
 *
 * # Stale-run protection (§11)
 *
 * `runId` is generated fresh per attempt and captured by both the
 * event listeners (via `activeRunId`) and the `executeAnalysis()`
 * continuation. Every state update — event-driven or promise-driven
 * — first checks "is this still the active run" before applying, so:
 *   - a component unmount stops applying updates (`mountedRef`)
 *   - a late-resolving promise from an abandoned run cannot overwrite
 *     a newer run's state (`runId` comparison)
 *   - `useEventStream`'s own effect cleanup (already ref-counted,
 *     Strict-Mode-safe — see its doc comment) handles subscription
 *     disposal; this hook adds no subscription bookkeeping of its own
 *     on top of that (§10: "Do NOT create another sidecar/event
 *     store").
 */

import { useCallback, useEffect, useRef } from "react";
import { useEventStream } from "../../shared/events/useEventStream";
import { executeAnalysis } from "./analysisExecution";
import { resolveReportPath, describeReportPathBlockedReason } from "./analysisReportPath";
import {
  adoptCorrelationId,
  beginExecuting,
  markExecutionCompleted,
  markExecutionFailed,
  retryFailed,
  updateProgress,
} from "./analysisWorkflowState";
import type { AnalysisReadyState, AnalysisWorkflowState } from "./analysisWorkflowState";

function generateRunId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Fallback for a test/JSDOM environment without `crypto.randomUUID` —
  // still unique enough for this hook's own equality checks, which
  // never leave the current page session.
  return `run-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export interface UseAnalysisExecutionResult {
  /** Whether the execution control should be enabled right now. */
  readonly canStart: boolean;
  /** Why `canStart` is false due to the report-path boundary
   * specifically (as opposed to simply not being in `ready`) —
   * shown by the UI so the control's disabled state isn't
   * unexplained (§15: "disabled/busy controls communicate their
   * state"). `null` when not applicable. */
  readonly blockedReason: string | null;
  readonly start: () => void;
  /** Whether the retry control should be enabled right now — only
   * ever true from `failed`, and only when the same report-path
   * boundary that gates `start` resolves successfully (Phase 4I-2
   * §10). */
  readonly canRetry: boolean;
  /** Re-runs a failed analysis against the same input, per
   * `retryFailed`'s doc comment. A no-op outside `failed`. */
  readonly retry: () => void;
}

export interface UseAnalysisExecutionDeps {
  /** Overridable only for tests — production code always uses the
   * real, honestly-always-blocked `resolveReportPath` (§3/§4). This
   * lets the hook's own state-machine/event-wiring logic be exercised
   * with deterministic fixtures (§18: "test the adapter contract and
   * state transitions honestly") without that orthogonal, documented
   * gap making this hook's own logic untestable. */
  readonly resolvePath?: typeof resolveReportPath;
}

export function useAnalysisExecution(
  state: AnalysisWorkflowState,
  setState: (updater: (current: AnalysisWorkflowState) => AnalysisWorkflowState) => void,
  deps: UseAnalysisExecutionDeps = {},
): UseAnalysisExecutionResult {
  const resolvePath = deps.resolvePath ?? resolveReportPath;
  const activeRunId = useRef<string | null>(state.status === "analyzing" ? state.runId : null);
  const mountedRef = useRef(true);

  useEffect(() => {
    activeRunId.current = state.status === "analyzing" ? state.runId : null;
  }, [state]);

  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  useEventStream<{ report_path: string }>("analysis.started", (event) => {
    setState((current) => {
      if (current.status !== "analyzing") return current;
      if (current.runId !== activeRunId.current) return current;
      return adoptCorrelationId(current, event.correlation_id);
    });
  });

  useEventStream<{ percent: number; message: string }>("analysis.progress", (event) => {
    setState((current) => {
      if (current.status !== "analyzing") return current;
      if (current.runId !== activeRunId.current) return current;
      if (current.correlationId !== null && current.correlationId !== event.correlation_id) {
        return current;
      }
      return updateProgress(current, { percent: event.payload.percent, message: event.payload.message });
    });
  });

  // Shared by `start` (from `ready`) and `retry` (from `failed`, via
  // `retryFailed`) so the two controls can never drift into two
  // slightly different execution paths — §10's "retry must not ...
  // create duplicate requests accidentally" is satisfied structurally
  // here, by there being exactly one place that calls
  // `executeAnalysis()` and mints a `runId` for it, not by each
  // caller separately promising not to.
  const beginRun = useCallback(
    (readyState: AnalysisReadyState) => {
      const resolved = resolvePath(readyState.input);
      if (!resolved.ok) {
        // Defensive only — the UI's `canStart`/`canRetry` already
        // keep this unreachable via user interaction.
        return;
      }

      const runId = generateRunId();
      setState(() => beginExecuting(readyState, runId));

      void executeAnalysis(resolved.reportPath, readyState.options).then((outcome) => {
        if (!mountedRef.current) {
          return;
        }
        setState((current) => {
          if (current.status !== "analyzing" || current.runId !== runId) {
            // Superseded by a reset, a newer run, or navigation away
            // and back — this outcome is stale.
            return current;
          }
          return outcome.ok
            ? markExecutionCompleted(current, outcome.result)
            : markExecutionFailed(current, outcome.error);
        });
      });
    },
    [setState, resolvePath],
  );

  const resolution =
    state.status === "ready" || state.status === "failed" ? resolvePath(state.input) : null;

  const start = useCallback(() => {
    if (state.status !== "ready") {
      return;
    }
    beginRun(state);
  }, [state, beginRun]);

  const retry = useCallback(() => {
    if (state.status !== "failed") {
      return;
    }
    beginRun(retryFailed(state));
  }, [state, beginRun]);

  return {
    canStart: state.status === "ready" && resolution !== null && resolution.ok,
    blockedReason: resolution !== null && !resolution.ok ? describeReportPathBlockedReason(resolution.reason) : null,
    start,
    canRetry: state.status === "failed" && resolution !== null && resolution.ok,
    retry,
  };
}
