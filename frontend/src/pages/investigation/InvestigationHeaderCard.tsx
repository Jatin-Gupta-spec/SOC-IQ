/**
 * Investigation Header Card — Phase 4J-6 Part 1B.
 *
 * The identity + high-level status surface for one investigation:
 * who/what it is (investigation ID, report name, analyzed-at), and
 * its risk/severity, analysis status, and confidence, exactly as
 * `normalizeInvestigationWorkspace()` (Phase 4J-5) already shaped
 * them. Deliberately does NOT implement the detailed Overview (IOC
 * counts, TI counts, timeline, correlations) — that is a later part's
 * scope per the task brief §2/§3.
 *
 * Presentation-only, per the task brief §4: no fetching, no routing,
 * no normalization, no `runCommand()`, no re-deriving anything the
 * backend/normalization layer already decided. Reuses the existing
 * `StatusBadge` component and design tokens exclusively — no second
 * color/status system (§6).
 *
 * # The `NOT_SCORED` sentinel
 *
 * `app/analyzer.py` writes `severity = "NOT_SCORED"` (with
 * `risk_score = 0` and `confidence = 0.0` alongside it) when risk
 * scoring was disabled for a run — an honest "we did not calculate
 * this" sentinel, not a real zero/low score (see that module's own
 * comment, and `investigationWorkspaceModel.ts`'s doc comment on the
 * same sentinel). This component treats `severity === "NOT_SCORED"`
 * as the single source of truth for that state and, when it holds,
 * presents Severity/Risk/Confidence as "Not scored" together rather
 * than showing the backend's placeholder `0`/`0%` values as if they
 * were real (task brief §6).
 */

import type { ReactElement } from "react";
import { StatusBadge } from "../components/StatusBadge";
import type { StatusTone } from "../components/StatusBadge";
import "../components/Card.css";
import type { InvestigationWorkspaceData } from "./investigationWorkspaceModel";
import "./InvestigationHeaderCard.css";

export interface InvestigationHeaderCardProps {
  readonly data: InvestigationWorkspaceData;
}

const NOT_SCORED_SENTINEL = "NOT_SCORED";

/** Whether an investigation's risk stage actually ran, per the
 * backend's own `NOT_SCORED` sentinel (`app/analyzer.py`, see this
 * module's doc comment) — not re-derived from `riskScore`/
 * `confidence` themselves, since those are `0`/`0.0` placeholders
 * (not real values) exactly when this is `false`. Exported so other
 * Investigation Workspace surfaces (e.g. the Part 1C Overview) can
 * apply the same scored/not-scored distinction without redefining it. */
export function isInvestigationScored(severity: string): boolean {
  return severity.trim().toUpperCase() !== NOT_SCORED_SENTINEL;
}

/** Real LOW/MEDIUM/HIGH/CRITICAL classifications only
 * (`app/scoring/engine.py::_determine_severity`) — matched
 * case-insensitively for the same reason `AnalysisResultSummary`'s
 * `severityTone` already is (`severity` is a plain backend string,
 * not a constrained enum). Anything else, including a value this
 * component doesn't recognize, renders with a neutral tone via its
 * own real label text rather than being hidden or guessed at.
 * Exported for reuse by other Investigation Workspace surfaces (e.g.
 * the Part 1C Overview) so the tone mapping isn't redefined per
 * component. */
export function severityTone(severity: string): StatusTone {
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

/** The recognized analysis-status vocabulary the task brief §7 names
 * (`COMPLETED`/`FAILED`/`PENDING`), matched case-insensitively since
 * `status` is a plain backend string. An unrecognized status still
 * renders its own real text, with a neutral tone rather than an
 * invented backend state. */
export function statusTone(status: string): StatusTone {
  switch (status.trim().toLowerCase()) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "pending":
      return "info";
    default:
      return "neutral";
  }
}

/** `0.82 -> "82%"` — presentation formatting only (task brief §8), on
 * the real `confidence` fraction already produced by the backend.
 * Never meaningful when severity is the `NOT_SCORED` sentinel (see
 * `isInvestigationScored`). Exported for reuse by other Investigation
 * Workspace surfaces (e.g. the Part 1C Overview). */
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Renders the identity + high-level status header for one already-
 * normalized investigation. Callers only render this once
 * `InvestigationWorkspaceData` actually exists (`useInvestigation()`'s
 * `"success"`/`"partial"` states) — this component has no loading
 * state of its own, matching `InvestigationWorkspacePage`'s existing
 * skeleton-vs-content split (task brief §12).
 */
export function InvestigationHeaderCard({ data }: InvestigationHeaderCardProps): ReactElement {
  const scored = isInvestigationScored(data.severity);

  return (
    <section className="card investigation-header-card">
      <div className="investigation-header-card__identity">
        <h2 className="investigation-header-card__title">
          {data.investigationId !== null ? `Investigation #${data.investigationId}` : "Investigation"}
        </h2>
        <p className="investigation-header-card__meta">
          {data.reportName}
          {data.analyzedAt ? (
            <>
              <span className="investigation-header-card__meta-sep" aria-hidden="true">
                {" "}
                &middot;{" "}
              </span>
              {data.analyzedAt}
            </>
          ) : null}
        </p>
        {data.investigationId === null ? (
          <p className="investigation-header-card__meta investigation-header-card__meta--muted">
            Investigation ID unavailable
          </p>
        ) : null}
      </div>

      <dl className="investigation-header-card__stats">
        <div className="investigation-header-card__stat">
          <dt className="investigation-header-card__stat-label">Analysis status</dt>
          <dd className="investigation-header-card__stat-value">
            <StatusBadge label={data.status} tone={statusTone(data.status)} />
          </dd>
        </div>

        <div className="investigation-header-card__stat">
          <dt className="investigation-header-card__stat-label">Severity</dt>
          <dd className="investigation-header-card__stat-value">
            {scored ? (
              <StatusBadge label={data.severity} tone={severityTone(data.severity)} />
            ) : (
              <StatusBadge label="Not scored" tone="neutral" />
            )}
          </dd>
        </div>

        <div className="investigation-header-card__stat">
          <dt className="investigation-header-card__stat-label">Risk</dt>
          <dd className="investigation-header-card__stat-value">
            {scored ? (
              <span className="investigation-header-card__stat-number">{data.riskScore}</span>
            ) : (
              <span className="investigation-header-card__stat-number investigation-header-card__stat-number--muted">
                Not scored
              </span>
            )}
          </dd>
        </div>

        <div className="investigation-header-card__stat">
          <dt className="investigation-header-card__stat-label">Confidence</dt>
          <dd className="investigation-header-card__stat-value">
            {scored ? (
              <span className="investigation-header-card__stat-number">{formatConfidence(data.confidence)}</span>
            ) : (
              <span className="investigation-header-card__stat-number investigation-header-card__stat-number--muted">
                Not scored
              </span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}
