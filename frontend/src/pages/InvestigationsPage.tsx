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
import { normalizeInvestigationsList, type InvestigationsListRow } from "./investigations/investigationsViewModel";
import { InvestigationsCsvExportAction } from "./investigations/InvestigationsCsvExportAction";
import { useReducedMotion } from "../shared/hooks/useReducedMotion";
import "./InvestigationsPage.css";

/**
 * Renders the raw rejection `useInvestigationsList()` exposes as
 * `error` into one human-readable line -- preferring the backend's
 * own message (`CommandFailedError`/`CommandClientError`/
 * `SidecarNotConnectedError` are all real `Error` subclasses) over an
 * invented one, mirroring
 * `InvestigationWorkspacePage.tsx::describeInvestigationError`'s
 * established convention exactly.
 */
function describeInvestigationsListError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while loading investigations.";
}

/**
 * Structural loading skeleton -- mirrors the real `DataTable`'s shape
 * (a header row plus a handful of row-height blocks) so the loading
 * state resembles the table about to appear, following the same
 * unlabeled-block convention `DashboardPage.tsx`'s `DashboardSkeleton`
 * and `InvestigationWorkspacePage.tsx`'s `WorkspaceSkeleton` already
 * established (MAX-2, Part 2). A fixed five-row count is a reasonable
 * approximation of "a table's worth of rows" -- not a claim about how
 * many investigations actually exist, which is unknown while loading.
 */
function InvestigationsTableSkeleton({ reducedMotion }: { readonly reducedMotion: boolean }): ReactElement {
  return (
    <div className="investigations-page__skeleton" aria-hidden="true">
      <SkeletonBlock className="investigations-page__skeleton-header" reducedMotion={reducedMotion} />
      {[0, 1, 2, 3, 4].map((row) => (
        <SkeletonBlock key={row} className="investigations-page__skeleton-row" reducedMotion={reducedMotion} />
      ))}
    </div>
  );
}

/**
 * MAX7-F-05: whole-row activation. `DataTable`'s `onRowActivate`
 * capability already exists and is already used by
 * `DashboardRecentInvestigations.tsx` for this exact table shape --
 * this reuses it rather than inventing a second interaction pattern.
 * Navigates via `location.hash` (matching this page's own existing
 * name-link convention, see the component doc comment below for why
 * this isn't `useNavigate()`), not a new navigation mechanism.
 * Rows without a real, persisted `investigationId` (`href === null`)
 * are left non-interactive -- there's no real destination to send
 * them to.
 */
function activateRow(row: InvestigationsListRow): void {
  if (row.href === null) {
    return;
  }
  window.location.hash = row.href.slice(1);
}

/**
 * MAX7-F-03: client-side search/filter, mirroring the IOC workspace's
 * own already-proven pattern (`InvestigationIocWorkspace.tsx`'s
 * search input + type-`<select>` + "Clear filters" + "Showing X of Y"
 * toolbar) rather than inventing a second UI convention -- see the
 * audit's own "Recommended direction" (§10).
 *
 * MAX10-F-01: `DataTable`'s previously-absent sort capability (noted
 * and explicitly deferred here as recently as MAX-9 Phase 2C) is now
 * implemented and used by the Status/Risk/Analyzed columns below --
 * see `DataTable.tsx`'s own doc comment for the sort model itself.
 * Sorting composes with the search/filter state above unchanged: the
 * table always receives `filteredRows` and sorts whatever that
 * currently is.
 *
 * The status filter's own options are derived from the statuses
 * actually present in the loaded rows (never a hard-coded vocabulary
 * that could offer a guaranteed-empty option), matching the IOC
 * workspace's identical "derive filter options from real data" rule.
 */
const STATUS_FILTER_ALL = "__all__";
type StatusFilterValue = typeof STATUS_FILTER_ALL | string;

function matchesSearch(row: InvestigationsListRow, normalizedQuery: string): boolean {
  if (normalizedQuery === "") {
    return true;
  }
  return (
    row.reportName.toLowerCase().includes(normalizedQuery) ||
    row.status.toLowerCase().includes(normalizedQuery) ||
    row.severity.toLowerCase().includes(normalizedQuery)
  );
}

function matchesStatus(row: InvestigationsListRow, statusFilter: StatusFilterValue): boolean {
  return statusFilter === STATUS_FILTER_ALL || row.status === statusFilter;
}

function availableStatuses(rows: readonly InvestigationsListRow[]): string[] {
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

const columns: DataTableColumn<InvestigationsListRow>[] = [
  {
    key: "name",
    header: "Investigation",
    render: (row) =>
      row.href !== null ? (
        <a className="investigations-page__row-link" href={row.href}>
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
    // MAX10-F-01: status/date/risk are the three columns the audit
    // scoped this finding to (§24, §26) -- name/severity/confidence
    // are left unsorted, matching that scope exactly.
    sortable: true,
    sortValue: (row) => row.status,
  },
  {
    key: "severity",
    header: "Severity",
    render: (row) => <StatusBadge label={row.severity} tone={row.severityTone} />,
  },
  {
    key: "risk",
    header: "Risk",
    render: (row) => (row.scored ? String(row.riskScore) : "Not scored"),
    // `riskScore` is already `number | null` -- an unscored
    // investigation's `null` sorts to the end of the list in either
    // direction (`DataTable`'s `compareSortValues`), never presented
    // as though it were a real 0 risk score.
    sortable: true,
    sortValue: (row) => row.riskScore,
  },
  {
    key: "confidence",
    header: "Confidence",
    render: (row) => row.confidenceLabel ?? "Not scored",
  },
  {
    key: "analyzed",
    header: "Analyzed",
    render: (row) => row.analyzedAt,
    // `analyzedAt` is an ISO 8601 string (`InvestigationSummaryDTO
    // .analyzed_at`, always UTC/naive-ISO from the backend) -- a plain
    // locale string compare already sorts it chronologically, so no
    // `Date` parsing (and its own failure modes) is needed here.
    sortable: true,
    sortValue: (row) => row.analyzedAt,
  },
];

/**
 * Investigations page -- real backend wiring.
 *
 * Replaces the previous static `mockInvestigations` collection with
 * the real `list_investigations` command
 * (`useInvestigationsList()` -> `runCommand("list_investigations", {})`,
 * `shared/api/client.ts`), normalized into this page's row shape by
 * `normalizeInvestigationsList()` (`investigations/investigationsViewModel.ts`).
 * The Investigation Workspace this page hands off to
 * (`/investigations/:investigationId`, Phase 4J/4K) is untouched --
 * this page only supplies it with real navigation targets instead of
 * mock ones.
 *
 * Each investigation with a real, persisted ID links to
 * `#/investigations/{id}` via a plain `<a href>` -- not
 * `useNavigate()`/`onRowActivate` -- for the same reason
 * `AnalyzePage`'s `AnalysisResultSummary` handoff link already uses a
 * plain hash-link: it keeps this page renderable standalone, outside
 * a `<Router>`, exactly as `pages.test.tsx`'s existing
 * `renderToStaticMarkup` harness already exercises it. `HashRouter`
 * (`app/router.tsx`) picks the resulting `location.hash` change up
 * exactly as it would a `<Link>` click.
 *
 * Loading/error/empty states are handled honestly per the task's own
 * rules: no fake rows while loading, no silent fallback to mock data
 * on a failed fetch, and an explicit "no investigations" message for
 * a real empty result -- never a state that implies data exists when
 * it doesn't.
 *
 * PD-08-P5.3: the header's `actions` slot now carries
 * `InvestigationsCsvExportAction`, the real bulk investigation-history
 * CSV export control (`investigations/useInvestigationsCsvExport.ts`
 * -> `export_investigations_csv`). It is independent of this page's
 * own list load/error/empty states above -- exporting works (or fails
 * honestly) on its own regardless of whether the on-screen table is
 * currently loading, showing an error, or empty, since the export
 * always re-fetches the full history server-side rather than
 * exporting whatever this page currently has rendered.
 *
 * MAX7-F-05: every row with a real investigation ID is also whole-row
 * activatable (`DataTable`'s existing `onRowActivate`, see
 * `activateRow` above) -- clicking or Enter/Space-activating anywhere
 * in the row opens that investigation, not only the name cell's own
 * `<a href>`, which is left in place unchanged for middle-click/
 * "open in new tab".
 *
 * MAX7-F-03: a search box (name/status/severity) plus a status filter
 * sit above the table once real rows exist, mirroring the IOC
 * workspace's own toolbar. Three empty states stay honestly
 * distinguished: no investigations at all (existing "No
 * investigations found." message, no toolbar), a fetch failure
 * (existing error state, unchanged), and real investigations present
 * but the current search/status combination matching none of them
 * (a new, separate "No investigations match your filters." state with
 * its own "Clear filters" action, toolbar left visible). Search/filter
 * state is plain local `useState` -- no second fetch, no mutation of
 * the normalized rows.
 */
export function InvestigationsPage(): ReactElement {
  const { state, investigations, error, retry } = useInvestigationsList();
  const reducedMotion = useReducedMotion();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>(STATUS_FILTER_ALL);

  const allRows = useMemo(
    () => (investigations !== null ? normalizeInvestigationsList(investigations) : []),
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
    <PageLayout label="Investigations page">
      <PageHeader
        title="Investigations"
        description="Active and recent investigations across the SOC, with status, severity, and risk at a glance."
        actions={<InvestigationsCsvExportAction />}
      />

      <section className="page-layout__section">
        <Card title="All Investigations">
          {state === "loading" ? (
            <>
              <p className="skeleton-status" role="status" aria-live="polite">
                Loading investigations…
              </p>
              <InvestigationsTableSkeleton reducedMotion={reducedMotion} />
            </>
          ) : null}

          {state === "error" ? (
            <>
              <p className="investigations-page__message" role="alert">
                {describeInvestigationsListError(error)}
              </p>
              <div className="investigations-page__actions">
                <Button onClick={retry}>Retry</Button>
              </div>
            </>
          ) : null}

          {state === "success" && investigations !== null && investigations.length === 0 ? (
            <p className="investigations-page__message investigations-page__message--muted">
              No investigations found.
            </p>
          ) : null}

          {state === "success" && investigations !== null && investigations.length > 0 ? (
            <>
              <div className="investigations-page__toolbar">
                <div className="investigations-page__field">
                  <label htmlFor="investigations-search" className="investigations-page__field-label">
                    Search
                  </label>
                  <input
                    id="investigations-search"
                    type="search"
                    className="investigations-page__search-input"
                    placeholder="Search investigations..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </div>
                <div className="investigations-page__field">
                  <label htmlFor="investigations-status-filter" className="investigations-page__field-label">
                    Status
                  </label>
                  <select
                    id="investigations-status-filter"
                    className="investigations-page__status-filter"
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
                  <button type="button" className="investigations-page__reset" onClick={resetFilters}>
                    Clear filters
                  </button>
                ) : null}
                <span className="investigations-page__count">
                  Showing {filteredRows.length} of {allRows.length} investigations
                </span>
              </div>
              {filteredRows.length === 0 ? (
                <div className="investigations-page__no-matches">
                  <InfoNote>No investigations match your filters.</InfoNote>
                  <button type="button" className="investigations-page__reset" onClick={resetFilters}>
                    Clear filters
                  </button>
                </div>
              ) : (
                (() => {
                  const hasNavigableRow = filteredRows.some((row) => row.investigationId !== null);
                  return (
                    <DataTable
                      caption="Investigations"
                      columns={columns}
                      rows={filteredRows}
                      getRowId={(row) => row.rowId}
                      {...(hasNavigableRow ? { onRowActivate: activateRow } : {})}
                      getRowAriaLabel={(row) =>
                        row.investigationId !== null
                          ? `Open investigation ${row.reportName}, status ${row.status}, severity ${row.severity}`
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
