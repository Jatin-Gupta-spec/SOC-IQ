import { useMemo, useState, type ReactElement } from "react";
import { PageLayout } from "./components/PageLayout";
import { PageHeader } from "./components/PageHeader";
import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { InfoNote } from "./components/InfoNote";
import { StatusBadge } from "./components/StatusBadge";
import { DataTable, type DataTableColumn } from "./components/DataTable";
import { SkeletonBlock } from "./components/SkeletonBlock";
import { useInvestigationsList } from "./investigations/useInvestigationsList";
import { normalizeReportsList, type ReportsListRow } from "./reports/reportsViewModel";
import { ReportExportAction } from "./reports/ReportExportAction";
import { useReducedMotion } from "../shared/hooks/useReducedMotion";
import "./ReportsPage.css";

/**
 * Renders the raw rejection `useInvestigationsList()` exposes as
 * `error` into one human-readable line, mirroring
 * `InvestigationsPage.tsx::describeInvestigationsListError` exactly
 * (same hook, same error shapes -- a second, page-local re-derivation
 * of this would just drift from that one).
 */
function describeReportsListError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while loading reports.";
}

/**
 * Structural loading skeleton -- same table-shaped convention as
 * `InvestigationsPage.tsx::InvestigationsTableSkeleton` (MAX-2, Part
 * 3), since Reports renders the same `DataTable` shape from the same
 * underlying data source.
 */
function ReportsTableSkeleton({ reducedMotion }: { readonly reducedMotion: boolean }): ReactElement {
  return (
    <div className="reports-page__skeleton" aria-hidden="true">
      <SkeletonBlock className="reports-page__skeleton-header" reducedMotion={reducedMotion} />
      {[0, 1, 2, 3, 4].map((row) => (
        <SkeletonBlock key={row} className="reports-page__skeleton-row" reducedMotion={reducedMotion} />
      ))}
    </div>
  );
}

/**
 * MAX7-F-05: whole-row activation, mirroring
 * `InvestigationsPage.tsx::activateRow` exactly (same row shape's
 * `href`/`investigationId` fields, same plain-`location.hash`
 * navigation, same non-interactive fallback when there's no real
 * destination).
 */
function activateRow(row: ReportsListRow): void {
  if (row.href === null) {
    return;
  }
  window.location.hash = row.href.slice(1);
}

/**
 * MAX7-F-03: client-side search/filter, mirroring
 * `InvestigationsPage.tsx`'s identical addition (same underlying
 * `useInvestigationsList()` data, same IOC-workspace-derived toolbar
 * pattern) -- see that file's doc comment for the full rationale.
 * Reports' row shape has no `severity` field (`reportsViewModel.ts`'s
 * own doc comment: severity/risk/confidence are intentionally not
 * carried onto this page), so search here covers name/status only.
 */
const STATUS_FILTER_ALL = "__all__";
type StatusFilterValue = typeof STATUS_FILTER_ALL | string;

function matchesSearch(row: ReportsListRow, normalizedQuery: string): boolean {
  if (normalizedQuery === "") {
    return true;
  }
  return row.reportName.toLowerCase().includes(normalizedQuery) || row.status.toLowerCase().includes(normalizedQuery);
}

function matchesStatus(row: ReportsListRow, statusFilter: StatusFilterValue): boolean {
  return statusFilter === STATUS_FILTER_ALL || row.status === statusFilter;
}

function availableStatuses(rows: readonly ReportsListRow[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const row of rows) {
    if (!seen.has(row.status)) {
      seen.add(row.status);
      ordered.push(row.status);
    }
  }
  return ordered;
}

const columns: DataTableColumn<ReportsListRow>[] = [
  {
    key: "report",
    header: "Report",
    render: (row) =>
      row.href !== null ? (
        <a className="reports-page__row-link" href={row.href}>
          {row.reportName}
        </a>
      ) : (
        row.reportName
      ),
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusBadge label={row.status} tone={row.statusTone} />,
    // MAX10-F-01 / Phase 2B: same field, same sort semantics as
    // `InvestigationsPage.tsx`'s Status column -- this page already
    // mirrors that page's row shape and loading/error/filter
    // conventions exactly (see the file doc comment above), so
    // leaving sort out here would be the one interaction that
    // doesn't carry over, despite the data being identical.
    sortable: true,
    sortValue: (row) => row.status,
  },
  {
    key: "analyzed",
    header: "Analyzed",
    render: (row) => row.analyzedAt,
    // `analyzedAt` is the same ISO 8601 string as
    // `InvestigationsPage.tsx`'s Analyzed column (both derive from
    // `InvestigationSummary.analyzed_at`), so it sorts correctly as
    // a plain string -- see that column's own comment for why no
    // Date parsing is needed.
    sortable: true,
    sortValue: (row) => row.analyzedAt,
  },
  {
    key: "actions",
    header: "Export",
    // MAX7-F-05: the Export button's own click/keyboard activation is
    // its own distinct action (save-file dialog), never "also open
    // this investigation" -- stopping propagation here keeps it from
    // bubbling into the row's own onRowActivate/keydown handling
    // below, the same way the row's real Enter/Space handling already
    // stops it from also scrolling the page (DataTable.tsx).
    render: (row) => (
      <span onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
        <ReportExportAction investigationId={row.investigationId} reportName={row.reportName} />
      </span>
    ),
  },
];

/**
 * Reports page -- real backend wiring (Phase 4L-P3).
 *
 * There is no persisted report-history entity in the backend (see
 * `reports/reportsViewModel.ts`'s doc comment for the full
 * explanation), so this page is wired to the same real
 * `list_investigations` data `InvestigationsPage` already fetches
 * (`useInvestigationsList()`, unchanged and reused as-is -- no second
 * fetch hook) and presents it as "the reports available to export".
 * Every row's Export action calls the real `export_report` command
 * (`reports/useReportExport.ts`) against a real, user-chosen save
 * path -- the previous mock page's permanently-disabled Download
 * button is now genuinely functional instead of removed.
 *
 * Loading/error/empty states mirror `InvestigationsPage.tsx` exactly:
 * no fake rows while loading, no silent fallback to mock data on a
 * failed fetch, and an explicit "no reports" message for a real empty
 * result.
 *
 * MAX7-F-05: every row with a real investigation ID is also whole-row
 * activatable (`activateRow` above, mirroring
 * `InvestigationsPage.tsx`'s identical addition) -- the Export cell's
 * own click/keyboard handling is shielded from it (see the `actions`
 * column above) so exporting a report never also navigates away from
 * this page.
 *
 * MAX7-F-03: a search box (name/status) plus a status filter sit
 * above the table once real rows exist, mirroring
 * `InvestigationsPage.tsx`'s identical addition -- see that file's
 * doc comment for the full empty/unavailable/filtered-empty
 * rationale, reused here unchanged.
 */
export function ReportsPage(): ReactElement {
  const { state, investigations, error, retry } = useInvestigationsList();
  const reducedMotion = useReducedMotion();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>(STATUS_FILTER_ALL);

  const allRows = useMemo(
    () => (investigations !== null ? normalizeReportsList(investigations) : []),
    [investigations],
  );

  const filteredRows = useMemo(() => {
    const normalizedQuery = search.trim().toLowerCase();
    return allRows.filter((row) => matchesStatus(row, statusFilter) && matchesSearch(row, normalizedQuery));
  }, [allRows, statusFilter, search]);

  const statusOptions = useMemo(() => availableStatuses(allRows), [allRows]);
  const hasActiveFilter = search.trim() !== "" || statusFilter !== STATUS_FILTER_ALL;

  function resetFilters(): void {
    setSearch("");
    setStatusFilter(STATUS_FILTER_ALL);
  }

  return (
    <PageLayout label="Reports page">
      <PageHeader
        title="Reports"
        description="Analyzed reports available to export as HTML, PDF, JSON, or Markdown."
      />

      <section className="page-layout__section">
        <Card title="All Reports">
          {state === "loading" ? (
            <>
              <p className="skeleton-status" role="status" aria-live="polite">
                Loading reports…
              </p>
              <ReportsTableSkeleton reducedMotion={reducedMotion} />
            </>
          ) : null}

          {state === "error" ? (
            <>
              <p className="reports-page__message" role="alert">
                {describeReportsListError(error)}
              </p>
              <div className="reports-page__actions">
                <Button onClick={retry}>Retry</Button>
              </div>
            </>
          ) : null}

          {state === "success" && investigations !== null && investigations.length === 0 ? (
            <p className="reports-page__message reports-page__message--muted">
              No reports available. Analyze a report from the Analyze page to see it here.
            </p>
          ) : null}

          {state === "success" && investigations !== null && investigations.length > 0 ? (
            <>
              <div className="reports-page__toolbar">
                <div className="reports-page__field">
                  <label htmlFor="reports-search" className="reports-page__field-label">
                    Search
                  </label>
                  <input
                    id="reports-search"
                    type="search"
                    className="reports-page__search-input"
                    placeholder="Search reports..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </div>
                <div className="reports-page__field">
                  <label htmlFor="reports-status-filter" className="reports-page__field-label">
                    Status
                  </label>
                  <select
                    id="reports-status-filter"
                    className="reports-page__status-filter"
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                  >
                    <option value={STATUS_FILTER_ALL}>All statuses</option>
                    {statusOptions.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </div>
                {hasActiveFilter ? (
                  <button type="button" className="reports-page__reset" onClick={resetFilters}>
                    Clear filters
                  </button>
                ) : null}
                <span className="reports-page__count">
                  Showing {filteredRows.length} of {allRows.length} reports
                </span>
              </div>
              {filteredRows.length === 0 ? (
                <div className="reports-page__no-matches">
                  <InfoNote>No reports match your filters.</InfoNote>
                  <button type="button" className="reports-page__reset" onClick={resetFilters}>
                    Clear filters
                  </button>
                </div>
              ) : (
                (() => {
                  const hasNavigableRow = filteredRows.some((row) => row.investigationId !== null);
                  return (
                    <DataTable
                      caption="Reports"
                      columns={columns}
                      rows={filteredRows}
                      getRowId={(row) => row.rowId}
                      {...(hasNavigableRow ? { onRowActivate: activateRow } : {})}
                      getRowAriaLabel={(row) =>
                        row.investigationId !== null
                          ? `Open investigation ${row.reportName}, status ${row.status}`
                          : `${row.reportName}, no workspace available`
                      }
                    />
                  );
                })()
              )}
            </>
          ) : null}
        </Card>
      </section>
    </PageLayout>
  );
}
