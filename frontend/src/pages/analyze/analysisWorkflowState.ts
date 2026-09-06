/**
 * Analysis workflow state model — Phase 4I-1A §4, extended Phase
 * 4I-1B §5 for the real execution lifecycle.
 *
 * 4I-1A took a person from "no input" to "ready to start analysis".
 * This checkpoint extends the same discriminated union with the
 * states execution actually needs — `analyzing`, `completed`,
 * `failed` — rather than building a second state machine alongside
 * it (§5: "Extend the 4I-1A state model only as necessary").
 *
 * Modeled as a discriminated union (not a handful of independent
 * booleans) so impossible combinations the checkpoint briefs call
 * out by name — `ready` with no input, `analyzing` without a valid
 * input, `completed` without an execution result, a stale completion
 * overwriting a newer run — cannot be constructed. Each state's own
 * shape only carries the data that's actually valid for that state:
 *
 *   idle              -> no input, no error
 *   inputSelected     -> raw AnalysisInput, not yet validated
 *   validating        -> raw AnalysisInput, validation in progress
 *   ready             -> a *validated* input value
 *   invalid           -> the input that failed, plus the reason
 *   analyzing         -> a validated input, a run identity, and the
 *                        latest progress/correlation info for that run
 *   completed         -> the run identity plus a typed execution result
 *   failed            -> the run identity plus a typed execution error
 *
 * `validating` exists as a distinct state (rather than folding
 * directly from `inputSelected` to `ready`/`invalid`) because
 * `analysisInput.ts`'s validation is written as an async boundary
 * (see its own doc comment) — the UI needs a state to be in while
 * that resolves. `analyzing` exists as a distinct state for the same
 * reason, one level up: `analysisExecution.ts`'s `executeAnalysis()`
 * is itself an async boundary.
 *
 * `runId` (on `analyzing`/`completed`/`failed`) is a client-generated
 * identity for *this* execution attempt, not the backend
 * `correlation_id` (which is only known once the first
 * `analysis.started` SSE event or the command's own response
 * arrives — see `useAnalysisExecution.ts`). It exists purely for
 * stale-run protection (§11): a late-resolving promise or event from
 * an earlier run can compare its captured `runId` against the
 * current state's `runId` and discard itself if they don't match,
 * without needing the backend id to exist yet.
 */

import type { AnalysisInput, AnalysisInputRejection } from "./analysisInput";
import type { AnalysisExecutionError } from "./analysisExecutionError";
import type { AnalysisOptions } from "../../shared/api/types";

/**
 * The options a person can select before starting a run — Phase 4I
 * Remediation Part 3, §4/§5/§6. Mirrors the server-side default in
 * `AnalyzeReportPayload`'s own doc comment ("All fields default to
 * `true` server-side when `options` is omitted entirely"): a freshly
 * `ready` input starts with every stage selected, matching what
 * omitting `options` from the payload would already do. This constant
 * is the *client-side* mirror of that default, not a new default the
 * backend doesn't already have.
 */
export const DEFAULT_ANALYSIS_OPTIONS: AnalysisOptions = {
  extract_iocs: true,
  enrich_ti: true,
  score_risk: true,
};

export interface AnalysisIdleState {
  readonly status: "idle";
}

export interface AnalysisInputSelectedState {
  readonly status: "inputSelected";
  readonly input: AnalysisInput;
}

export interface AnalysisValidatingState {
  readonly status: "validating";
  readonly input: AnalysisInput;
}

export interface AnalysisReadyState {
  readonly status: "ready";
  readonly input: AnalysisInput;
  /** The currently selected stage options for this input — editable
   * only from this state (`updateOptions`), per §5: options are a
   * pre-execution choice, not something that changes mid-run. */
  readonly options: AnalysisOptions;
}

export interface AnalysisInvalidState {
  readonly status: "invalid";
  readonly input: AnalysisInput;
  readonly rejection: AnalysisInputRejection;
}

/** The most recent real progress reported for a run — §7: only ever
 * populated from an actual `analysis.progress` SSE event's
 * `percent`/`message`, never fabricated. */
export interface AnalysisProgress {
  readonly percent: number;
  readonly message: string;
}

export interface AnalysisAnalyzingState {
  readonly status: "analyzing";
  readonly input: AnalysisInput;
  /** The options this run was actually started with — carried
   * forward unchanged from the `ready` state's `options` at the
   * moment `beginExecuting` was called (§5: "Options must survive
   * ready -> analyzing"). This is the *requested* set; the
   * authoritative *applied* set is only known once the backend
   * responds (see `AnalysisExecutionResult.options`). */
  readonly options: AnalysisOptions;
  readonly runId: string;
  /** The backend's own id for this run, adopted from the first
   * matching `analysis.started` SSE event. `null` until then — see
   * `useAnalysisExecution.ts`. */
  readonly correlationId: string | null;
  /** `null` until a real `analysis.progress` event has arrived for
   * this run — the UI shows an indeterminate state until then (§7:
   * "do NOT fabricate fake percentage progress"). */
  readonly progress: AnalysisProgress | null;
}

/** The typed completion boundary this checkpoint produces — §13:
 * only what a later checkpoint's results/handoff needs, not a full
 * results page. */
export interface AnalysisExecutionResult {
  readonly correlationId: string;
  readonly investigationId: number | null;
  readonly reportName: string;
  readonly riskScore: number;
  readonly severity: string;
  readonly status: string;
  readonly existing: boolean;
  /** The options the backend actually applied for this run, echoed
   * back on `AnalyzeReportResult` (`app/application/dto.py`) — the
   * source of truth for which stages really ran, used instead of the
   * `analyzing` state's *requested* options so a completed view can
   * never claim a stage executed that the backend didn't run (§8:
   * "do NOT display fabricated ... output"). */
  readonly options: AnalysisOptions;
}

export interface AnalysisCompletedState {
  readonly status: "completed";
  readonly input: AnalysisInput;
  readonly runId: string;
  readonly result: AnalysisExecutionResult;
}

export interface AnalysisFailedState {
  readonly status: "failed";
  readonly input: AnalysisInput;
  /** The options the failed run was started with — the same value
   * `retryFailed` hands back to `ready` unchanged, which is what
   * makes "retry preserves the selected options" true by
   * construction rather than by a separate copy step. */
  readonly options: AnalysisOptions;
  readonly runId: string;
  readonly error: AnalysisExecutionError;
}

export type AnalysisWorkflowState =
  | AnalysisIdleState
  | AnalysisInputSelectedState
  | AnalysisValidatingState
  | AnalysisReadyState
  | AnalysisInvalidState
  | AnalysisAnalyzingState
  | AnalysisCompletedState
  | AnalysisFailedState;

export const initialAnalysisWorkflowState: AnalysisIdleState = {
  status: "idle",
};

/**
 * The explicit, closed set of transitions this checkpoint supports.
 * Kept as plain functions (not a generic reducer with a string
 * action union) so each transition's inputs are exactly the data
 * that transition needs — e.g. `submitInput` cannot be called
 * without an `AnalysisInput`, so "ready with no input" has no code
 * path that produces it.
 */

/** A person picked or dropped a file. Valid from any state — picking
 * a new file always restarts the workflow at `inputSelected`, even
 * if the previous input was `ready` or `invalid`. */
export function selectInput(input: AnalysisInput): AnalysisInputSelectedState {
  return { status: "inputSelected", input };
}

/** Validation has started for the currently selected input. Only
 * meaningful from `inputSelected` — the caller is expected to have
 * just come from there. */
export function beginValidating(
  state: AnalysisInputSelectedState,
): AnalysisValidatingState {
  return { status: "validating", input: state.input };
}

/** Validation succeeded. A freshly `ready` input starts with every
 * stage selected (`DEFAULT_ANALYSIS_OPTIONS`) — matching the
 * server-side default for an omitted `options` field, per that
 * constant's own doc comment. */
export function markReady(state: AnalysisValidatingState): AnalysisReadyState {
  return { status: "ready", input: state.input, options: DEFAULT_ANALYSIS_OPTIONS };
}

/** A person changed one or more of the stage checkboxes while
 * `ready` — Part 3 §5. Only callable from `ready`: options are not
 * editable once a run has started (`analyzing`) or finished
 * (`completed`/`failed`), which a `AnalysisReadyState` type guard at
 * the one call site (`AnalyzePage.tsx`) enforces the same way
 * `beginValidating`'s precondition already is. */
export function updateOptions(
  state: AnalysisReadyState,
  options: AnalysisOptions,
): AnalysisReadyState {
  return { ...state, options };
}

/** Validation failed. */
export function markInvalid(
  state: AnalysisValidatingState,
  rejection: AnalysisInputRejection,
): AnalysisInvalidState {
  return { status: "invalid", input: state.input, rejection };
}

/** Clears the current input (and any error) and returns to `idle`. */
export function reset(): AnalysisIdleState {
  return initialAnalysisWorkflowState;
}

/**
 * Execution starts from `ready` (§6: "Provide the real analysis
 * action from the READY state"). Only callable with an
 * `AnalysisReadyState` — a `ready` type guard at the one call site
 * (`useAnalysisExecution.ts`) is what prevents "analyzing without a
 * valid input" from having a code path, the same pattern
 * `beginValidating` already uses for its own precondition.
 *
 * `runId` is generated by the caller (not here) so the caller — the
 * one place that also starts the async `executeAnalysis()` call —
 * can capture the exact same id in its stale-run check.
 */
export function beginExecuting(
  state: AnalysisReadyState,
  runId: string,
): AnalysisAnalyzingState {
  return {
    status: "analyzing",
    input: state.input,
    options: state.options,
    runId,
    correlationId: null,
    progress: null,
  };
}

/** The backend's own id for this run has been observed for the first
 * time (the first `analysis.started` event matching this run). A
 * second call is a no-op — once adopted, a run's correlation id does
 * not change. */
export function adoptCorrelationId(
  state: AnalysisAnalyzingState,
  correlationId: string,
): AnalysisAnalyzingState {
  if (state.correlationId !== null) {
    return state;
  }
  return { ...state, correlationId };
}

/** A real `analysis.progress` event arrived for this run. */
export function updateProgress(
  state: AnalysisAnalyzingState,
  progress: AnalysisProgress,
): AnalysisAnalyzingState {
  return { ...state, progress };
}

/** The command call resolved successfully. */
export function markExecutionCompleted(
  state: AnalysisAnalyzingState,
  result: AnalysisExecutionResult,
): AnalysisCompletedState {
  return { status: "completed", input: state.input, runId: state.runId, result };
}

/** The command call rejected. */
export function markExecutionFailed(
  state: AnalysisAnalyzingState,
  error: AnalysisExecutionError,
): AnalysisFailedState {
  return { status: "failed", input: state.input, options: state.options, runId: state.runId, error };
}

/**
 * A person chose to retry a failed run — Phase 4I-2 §10.
 *
 * Returns to `ready` carrying the *same* `AnalysisInput` the failed
 * run used. Re-validating is deliberately skipped: `failed` is only
 * reachable via `analyzing`, which is only reachable via `ready`
 * (`beginExecuting`'s own signature requires an `AnalysisReadyState`),
 * so this input was already known-valid — nothing about that fact
 * changed while the run was executing. A fresh `runId` is minted by
 * the caller when it starts the retried run (the same pattern
 * `beginExecuting` already uses), not here, so a stale outcome from
 * the failed attempt can never be mistaken for the retry's outcome.
 */
export function retryFailed(state: AnalysisFailedState): AnalysisReadyState {
  return { status: "ready", input: state.input, options: state.options };
}
