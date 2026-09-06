/**
 * Analysis execution adapter — Phase 4I-1B, §3/§4/§13.
 *
 * The one real execution boundary this checkpoint uses:
 * `runCommand("analyze_report", ...)` (`shared/api/client.ts`), which
 * is a 1:1 typed wrapper around `POST /commands/analyze_report`
 * (`app/application/handlers.py::AnalyzeReportCommandHandler`). This
 * module does not reimplement extraction, IOC parsing, scoring, or
 * persistence — it only shapes the request/response at the
 * boundary, per §3's explicit prohibition list.
 *
 * `AnalyzeReportCommandHandler.handle()` runs synchronously and
 * returns only once the whole analysis (extraction → enrichment →
 * scoring → persistence) has finished — see its own doc comment in
 * `handlers.py`. That means this function's returned promise
 * settling *is* the real completion/failure signal; it is not a
 * fabricated one. The same handler also publishes real
 * `analysis.started` / `analysis.progress` events through the
 * `EventBroker` while it runs — those are consumed separately, over
 * SSE, by `useAnalysisExecution.ts`, not by this module.
 */

import { runCommand } from "../../shared/api/client";
import type { AnalysisOptions, AnalyzeReportResult } from "../../shared/api/types";
import { mapExecutionError } from "./analysisExecutionError";
import type { AnalysisExecutionError } from "./analysisExecutionError";
import type { AnalysisExecutionResult } from "./analysisWorkflowState";

export type AnalysisExecutionOutcome =
  | { readonly ok: true; readonly result: AnalysisExecutionResult }
  | { readonly ok: false; readonly error: AnalysisExecutionError };

/**
 * Calls the real `analyze_report` command with `reportPath` and the
 * caller's selected `options`, and returns a typed outcome — never
 * throws (every rejection is caught and mapped via
 * `mapExecutionError`, per §9's "map ... into user-facing Analysis
 * errors").
 *
 * `options` is always sent explicitly (Part 3) rather than omitted to
 * rely on the backend's own all-`true` default: the frontend now has
 * a real, user-editable selection (`analysisWorkflowState.ts`'s
 * `ready.options`), and sending it explicitly is what makes changing
 * a checkbox actually change the request instead of being a UI-only
 * effect (§6: "the real runtime payload must contain the selected
 * values").
 */
export async function executeAnalysis(
  reportPath: string,
  options: AnalysisOptions,
): Promise<AnalysisExecutionOutcome> {
  try {
    const data = await runCommand("analyze_report", { report_path: reportPath, options });
    return { ok: true, result: toExecutionResult(data) };
  } catch (error) {
    return { ok: false, error: mapExecutionError(error) };
  }
}

function toExecutionResult(data: AnalyzeReportResult): AnalysisExecutionResult {
  return {
    correlationId: data.correlation_id,
    investigationId: data.investigation.investigation_id,
    reportName: data.investigation.report_name,
    riskScore: data.investigation.risk_score,
    severity: data.investigation.severity,
    status: data.investigation.status,
    existing: data.existing,
    // Echoed back by the backend — the authoritative record of which
    // stages actually ran, not merely what was requested (§8).
    options: data.options,
  };
}
