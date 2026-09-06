/**
 * Analysis execution error mapping — Phase 4I-1B, §9.
 *
 * Maps the real errors `runCommand()` (`shared/api/client.ts`) can
 * throw for `analyze_report` onto a small, closed, user-facing
 * taxonomy. Every case below corresponds to an error type that
 * actually exists in the codebase today (confirmed by reading
 * `client.ts` directly) — no invented category is added to satisfy
 * a checklist (§9's own instruction).
 *
 * `message` on every variant is a fixed, safe, non-technical string
 * — never the raw `Error.message` from a `CommandFailedError` /
 * `CommandNetworkError` / etc., which can carry backend detail
 * (a file path, an exception's `str()`) that §9 says must not reach
 * the UI verbatim. The original error is preserved on `cause` for
 * diagnostics only (mirrors `analysisInput.ts`'s own
 * `AnalysisInputRejection["read-failed"].cause` pattern) — logged via
 * `console.error`, never rendered.
 */

import {
  CommandFailedError,
  CommandHttpError,
  CommandMalformedResponseError,
  CommandNetworkError,
  SidecarNotConnectedError,
} from "../../shared/api/client";

export type AnalysisExecutionErrorKind =
  | "invalid_input"
  | "sidecar_unavailable"
  | "application_failure"
  | "network_failure"
  | "unexpected";

export interface AnalysisExecutionError {
  readonly kind: AnalysisExecutionErrorKind;
  readonly message: string;
  /** The backend error code, when one exists (`CommandFailedError.code`). Diagnostics only. */
  readonly code?: string;
  /** The original thrown value. Diagnostics only — never rendered. */
  readonly cause: unknown;
}

/** `CommandFailedError.code`s that mean "the input itself was the problem". */
const INVALID_INPUT_CODES = new Set(["REPORT_NOT_FOUND", "INVALID_COMMAND_PAYLOAD"]);

export function mapExecutionError(error: unknown): AnalysisExecutionError {
  if (error instanceof CommandFailedError) {
    const kind: AnalysisExecutionErrorKind = INVALID_INPUT_CODES.has(error.code)
      ? "invalid_input"
      : "application_failure";
    return { kind, message: describeExecutionError({ kind }), code: error.code, cause: error };
  }

  if (error instanceof SidecarNotConnectedError) {
    const kind: AnalysisExecutionErrorKind = "sidecar_unavailable";
    return { kind, message: describeExecutionError({ kind }), cause: error };
  }

  if (error instanceof CommandNetworkError || error instanceof CommandHttpError) {
    const kind: AnalysisExecutionErrorKind = "network_failure";
    return { kind, message: describeExecutionError({ kind }), cause: error };
  }

  if (error instanceof CommandMalformedResponseError) {
    const kind: AnalysisExecutionErrorKind = "unexpected";
    return { kind, message: describeExecutionError({ kind }), cause: error };
  }

  const kind: AnalysisExecutionErrorKind = "unexpected";
  return { kind, message: describeExecutionError({ kind }), cause: error };
}

export function describeExecutionError(error: Pick<AnalysisExecutionError, "kind">): string {
  switch (error.kind) {
    case "invalid_input":
      return "This report couldn't be analyzed. Check that the file is still available and try again.";
    case "sidecar_unavailable":
      return "The analysis service isn't available right now. Check the sidecar status and try again.";
    case "application_failure":
      return "Analysis failed while processing this report.";
    case "network_failure":
      return "Couldn't reach the analysis service. Check your connection and try again.";
    case "unexpected":
      return "Something went wrong while starting analysis.";
  }
}
