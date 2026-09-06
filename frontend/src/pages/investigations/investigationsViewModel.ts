/**
 * Investigations page view-model — Investigations page real backend
 * wiring.
 *
 * Maps the real `list_investigations` response
 * (`ListInvestigationsResult`, `shared/api/types.ts` --
 * `InvestigationSummaryDTO.to_dict()` on the backend) onto the flat
 * row shape `InvestigationsPage`'s table renders.
 *
 * # Reused, not reinvented
 *
 * Severity tone, "analysis status" tone, the `NOT_SCORED` sentinel
 * handling, and confidence formatting are NOT redefined here --
 * they're imported from `pages/investigation/InvestigationHeaderCard.tsx`,
 * which already implements and exports them
 * (`severityTone`/`statusTone`/`isInvestigationScored`/
 * `formatConfidence`) for exactly this "plain backend string, matched
 * case-insensitively" contract. A second, page-local copy of that
 * mapping would drift from the Workspace's own the first time either
 * one changed -- reusing the existing functions is both less code and
 * the only way the two surfaces are guaranteed to agree on what
 * "high severity" or "not scored" means.
 *
 * # Fields the mock UI had that the real backend does not provide
 *
 * `InvestigationSummaryDTO` (`app/application/dto.py`) has no
 * `owner` or `iocCount` field -- `mock/investigations.ts`'s shape
 * was never a backend contract, just isolated mock/adaptor data
 * (its own doc comment: "Isolated from any production
 * repository/database shape"). Inventing values for either field
 * here would be exactly the kind of fabricated data this checkpoint's
 * other real-data surfaces (`useInvestigation.ts`,
 * `InvestigationHeaderCard.tsx`) explicitly refuse to do -- so the
 * Investigations table simply does not have Owner/IOCs columns
 * anymore. This is the "existing structure literally prevents real
 * data from being displayed" case the task's design rule allows for.
 */

import { formatConfidence, isInvestigationScored, severityTone, statusTone } from "../investigation/InvestigationHeaderCard";
import type { StatusTone } from "../components/StatusBadge";
import type { InvestigationSummary, ListInvestigationsResult } from "../../shared/api/types";

export interface InvestigationsListRow {
  /** Stable key for `DataTable`'s `getRowId`. Derived from
   * `investigationId` when available; falls back to a
   * position-qualified key for the rare case the backend DTO's
   * `investigation_id: number | null` is actually null (never
   * expected in practice -- persisted investigations always have a
   * database id -- but the type allows it, so this stays honest
   * rather than assuming). */
  readonly rowId: string;
  readonly investigationId: number | null;
  readonly reportName: string;
  readonly status: string;
  readonly statusTone: StatusTone;
  /** Whether this investigation's risk stage actually ran (the
   * `NOT_SCORED` sentinel check, `isInvestigationScored`). When
   * `false`, `severity`/`riskScore`/`confidenceLabel` are all
   * presentation placeholders ("Not scored" / `null`), never the
   * backend's raw `0`/`0.0` sentinel values shown as if real. */
  readonly scored: boolean;
  readonly severity: string;
  readonly severityTone: StatusTone;
  readonly riskScore: number | null;
  readonly confidenceLabel: string | null;
  readonly analyzedAt: string;
  /** Hash-router link target for this row, e.g. `"#/investigations/42"`
   * -- `null` when `investigationId` is null (nothing to link to).
   * A plain hash-link, not `useNavigate()`, for the same
   * standalone-render reason `AnalyzePage`/`AnalysisResultSummary`
   * already established (see `InvestigationsPage.tsx`'s own doc
   * comment). */
  readonly href: string | null;
}

function toRow(investigation: InvestigationSummary, index: number): InvestigationsListRow {
  const scored = isInvestigationScored(investigation.severity);
  const investigationId = investigation.investigation_id;

  return {
    rowId: investigationId !== null ? String(investigationId) : `unidentified-${index}`,
    investigationId,
    reportName: investigation.report_name,
    status: investigation.status,
    statusTone: statusTone(investigation.status),
    scored,
    severity: scored ? investigation.severity : "Not scored",
    severityTone: scored ? severityTone(investigation.severity) : "neutral",
    riskScore: scored ? investigation.risk_score : null,
    confidenceLabel: scored ? formatConfidence(investigation.confidence) : null,
    analyzedAt: investigation.analyzed_at,
    href: investigationId !== null ? `#/investigations/${investigationId}` : null,
  };
}

/**
 * Pure mapping, no fetching/state -- `list_investigations`'s real
 * response in, `InvestigationsPage`'s row shape out. An empty input
 * array returns an empty output array (the page's own empty-state
 * handling decides what to render for that case; this function never
 * substitutes placeholder rows).
 */
export function normalizeInvestigationsList(
  investigations: ListInvestigationsResult,
): InvestigationsListRow[] {
  return investigations.map(toRow);
}
