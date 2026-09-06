import type { ReactElement } from "react";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import type { StatusTone } from "../components/StatusBadge";
import { InfoNote } from "../components/InfoNote";
import type { AnalysisExecutionResult } from "./analysisWorkflowState";

/**
 * Completed-analysis result surface — Phase 4I-2 §4/§5/§6/§7/§8.
 *
 * Renders exactly what `AnalysisExecutionResult` carries (§3: "expose
 * only information actually available from the existing backend/
 * application layer") — nothing here is fetched, recomputed, or
 * guessed. Two categories this checkpoint's brief anticipates
 * (§5 IOC summary, §6 TI summary) are deliberately *not* rendered as
 * data: `AnalyzeReportResult` (`shared/api/types.ts`, mirroring
 * `AnalyzeReportCommandHandler.handle()` in `handlers.py`) does not
 * include IOC or TI fields at all, so there is nothing "already
 * exposed" to summarize (§5/§6's own conditional — "if the real
 * result already exposes ..."). Fabricating counts by calling
 * `get_iocs`/`get_threat_intelligence` on the side would also mean
 * duplicating the Investigation Workspace's IOC/Threat Intel tabs'
 * fetching here; instead this shows the honest boundary note §6
 * calls for. Risk *is* rendered, because `riskScore`/`severity` are
 * real fields already on the result (§7: "if only a risk identifier/
 * status exists: display only that information").
 */

export interface AnalysisResultSummaryProps {
  readonly result: AnalysisExecutionResult;
  /** Hash-router path for the Investigations destination (from
   * `NAVIGATION_ITEMS`, not invented here — see this file's caller).
   * MAX7-F-01: the handoff link below appends
   * `result.investigationId` to this base path
   * (`#{investigationsPath}/{id}`) so it deep-links straight into
   * that specific investigation's own workspace route
   * (`/investigations/:investigationId`), matching the pattern
   * already used by `DashboardRecentInvestigations`,
   * `InvestigationsPage`, and `ReportsPage` — never the bare list. */
  readonly investigationsPath: string;
}

/** Backend severity strings observed in `app/scoring/engine.py`
 * (`_determine_severity`) are uppercase ("LOW"/"MEDIUM"/"HIGH"/
 * "CRITICAL"), but `AnalysisExecutionResult.severity` is typed as a
 * plain `string` (mirroring `InvestigationSummaryDTO`, which does not
 * constrain it further) — matched case-insensitively here so a tone
 * is chosen without assuming a stricter contract than the backend
 * actually gives. An unrecognized value still renders (via its own
 * label text, StatusBadge is never color-only) with a neutral tone
 * rather than being hidden or guessed at.
 */
function severityTone(severity: string): StatusTone {
  switch (severity.trim().toLowerCase()) {
    case "low":
      return "success";
    case "medium":
      return "warning";
    case "high":
      return "error";
    case "critical":
      return "critical";
    default:
      return "neutral";
  }
}

function statusTone(status: string): StatusTone {
  switch (status.trim().toLowerCase()) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    default:
      return "neutral";
  }
}

/** The backend's own honest sentinel for a disabled risk stage
 * (`app/analyzer.py`: `score_risk=False` produces `severity =
 * "NOT_SCORED"`, never one of the four real LOW/MEDIUM/HIGH/CRITICAL
 * classifications) — checked case-insensitively for the same reason
 * `severityTone` already is. */
function wasRiskScored(result: AnalysisExecutionResult): boolean {
  return result.severity.trim().toUpperCase() !== "NOT_SCORED";
}

const STAGE_LABELS: ReadonlyArray<{ readonly key: keyof AnalysisExecutionResult["options"]; readonly label: string }> = [
  { key: "extract_iocs", label: "Extract IOCs" },
  { key: "enrich_ti", label: "Enrich Threat Intelligence" },
  { key: "score_risk", label: "Calculate Risk" },
];

export function AnalysisResultSummary({
  result,
  investigationsPath,
}: AnalysisResultSummaryProps): ReactElement {
  const riskScored = wasRiskScored(result);

  return (
    <div className="analysis-result transition-fade">
      <p className="analysis-result__heading">
        Analysis complete for <span className="analysis-result__report-name">&quot;{result.reportName}&quot;</span>
      </p>

      {result.existing ? (
        <InfoNote>
          A report with this file name was already analyzed previously. This is the existing
          investigation, not a new analysis run.
        </InfoNote>
      ) : null}

      {/* §8: which stages the backend actually applied for this run —
          from `result.options`, the value the backend itself echoed
          back, not merely what was requested. */}
      <dl className="analysis-result__badges" aria-label="Analysis stages applied">
        {STAGE_LABELS.map(({ key, label }) => (
          <div className="analysis-result__badge-row" key={key}>
            <dt>{label}</dt>
            <dd>
              <StatusBadge
                label={result.options[key] ? "Ran" : "Skipped"}
                tone={result.options[key] ? "success" : "neutral"}
              />
            </dd>
          </div>
        ))}
      </dl>

      {riskScored ? (
        <div className="analysis-result__metrics">
          <MetricCard label="Risk score" value={String(result.riskScore)} />
        </div>
      ) : (
        <InfoNote>
          Risk scoring was disabled for this run, so no risk score was calculated.
        </InfoNote>
      )}

      <dl className="analysis-result__badges">
        {riskScored ? (
          <div className="analysis-result__badge-row">
            <dt>Severity</dt>
            <dd>
              <StatusBadge label={result.severity} tone={severityTone(result.severity)} />
            </dd>
          </div>
        ) : null}
        <div className="analysis-result__badge-row">
          <dt>Status</dt>
          <dd>
            <StatusBadge label={result.status} tone={statusTone(result.status)} />
          </dd>
        </div>
      </dl>

      {!result.options.extract_iocs || !result.options.enrich_ti ? (
        <InfoNote>
          {!result.options.extract_iocs && !result.options.enrich_ti
            ? "IOC extraction and threat-intelligence enrichment were both disabled for this run."
            : !result.options.extract_iocs
              ? "IOC extraction was disabled for this run."
              : "Threat-intelligence enrichment was disabled for this run."}
        </InfoNote>
      ) : null}

      <InfoNote>
        IOC and threat-intelligence detail views are not shown here — open the investigation
        below to see them in its IOCs and Threat Intel tabs.
      </InfoNote>

      <div className="analysis-result__handoff">
        {result.investigationId !== null ? (
          <a
            className="analysis-result__handoff-link"
            href={`#${investigationsPath}/${result.investigationId}`}
          >
            Open Investigation
          </a>
        ) : (
          <InfoNote>
            No investigation record is available for this run yet, so there&apos;s nothing to open.
          </InfoNote>
        )}
      </div>
    </div>
  );
}
