/**
 * Reports page view-model — Reports page real backend wiring
 * (Phase 4L-P3).
 *
 * There is no persisted "generated report" entity anywhere in the
 * backend (no report id, no export status, no created-at for an
 * export) -- `app/reporting/export_manager.py` only ever produces a
 * file on demand for `export_report`; it never records that the
 * export happened. `ReportsPage`'s previous mock (`mock/reports.ts`)
 * depicted a report-history table that has no real counterpart to
 * wire up.
 *
 * What *does* exist, and is genuinely "the reports" from a real SOC
 * analyst's point of view, is the set of already-analyzed
 * investigations -- each one *is* a report (the source report that
 * was analyzed), and each one is something `export_report` can turn
 * into a real HTML/PDF/JSON/Markdown file right now. So this page
 * reuses the same real `list_investigations` data
 * `InvestigationsPage` already fetches (`useInvestigationsList()`,
 * `shared/api/types.ts::InvestigationSummary`) and repurposes it as
 * "the reports available to export" -- honest data, just a different
 * lens on it, per the task's own instruction to wire the page to
 * "whatever real data exists today".
 *
 * # Reused, not reinvented
 *
 * `statusTone` is imported from
 * `pages/investigation/InvestigationHeaderCard.tsx` (the same
 * function `investigationsViewModel.ts` already reuses for
 * `InvestigationsPage`) rather than redefined here, so the two pages
 * are guaranteed to agree on what "completed"/"failed" mean.
 *
 * Severity/risk/confidence are intentionally NOT carried onto this
 * row shape -- they're triage signals, not report metadata, and
 * `InvestigationsPage` already owns that view. Repeating them here
 * would just duplicate that page rather than adding anything Reports
 * specific.
 */

import { statusTone } from "../investigation/InvestigationHeaderCard";
import type { StatusTone } from "../components/StatusBadge";
import type { InvestigationSummary, ListInvestigationsResult } from "../../shared/api/types";

export interface ReportsListRow {
  /** Stable key for `DataTable`'s `getRowId`. Derived from
   * `investigationId` when available; falls back to a
   * position-qualified key for the rare case the backend DTO's
   * `investigation_id: number | null` is actually null (mirrors
   * `investigationsViewModel.ts::toRow`'s same handling). */
  readonly rowId: string;
  readonly investigationId: number | null;
  readonly reportName: string;
  readonly status: string;
  readonly statusTone: StatusTone;
  readonly analyzedAt: string;
  /** Hash-router link target for the source investigation, e.g.
   * `"#/investigations/42"` -- `null` when `investigationId` is
   * null. Mirrors `InvestigationsPage.tsx`'s own plain-hash-link
   * convention (see its doc comment for why this isn't
   * `useNavigate()`). */
  readonly href: string | null;
}

function toRow(investigation: InvestigationSummary, index: number): ReportsListRow {
  const investigationId = investigation.investigation_id;

  return {
    rowId: investigationId !== null ? String(investigationId) : `unidentified-${index}`,
    investigationId,
    reportName: investigation.report_name,
    status: investigation.status,
    statusTone: statusTone(investigation.status),
    analyzedAt: investigation.analyzed_at,
    href: investigationId !== null ? `#/investigations/${investigationId}` : null,
  };
}

/**
 * Pure mapping, no fetching/state -- `list_investigations`'s real
 * response in, `ReportsPage`'s row shape out. An empty input array
 * returns an empty output array; this function never substitutes
 * placeholder rows for a genuinely empty result.
 */
export function normalizeReportsList(investigations: ListInvestigationsResult): ReportsListRow[] {
  return investigations.map(toRow);
}
