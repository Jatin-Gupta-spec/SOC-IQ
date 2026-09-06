import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { DataTable, type DataTableColumn } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import type { DashboardRecentInvestigationRow } from "./dashboardViewModel";
import "./DashboardRecentInvestigations.css";

const columns: DataTableColumn<DashboardRecentInvestigationRow>[] = [
  { key: "name", header: "Investigation", render: (row) => row.name },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusBadge label={row.status} tone={row.statusTone} />,
  },
  {
    key: "severity",
    header: "Severity",
    render: (row) => <StatusBadge label={row.severity} tone={row.severityTone} />,
  },
  { key: "updated", header: "Analyzed", render: (row) => row.updatedLabel },
];

export interface DashboardRecentInvestigationsProps {
  readonly investigations: readonly DashboardRecentInvestigationRow[];
}

/**
 * Rows with a real, persisted `investigationId` navigate to the
 * existing Investigation Workspace route (`/investigations/:id`,
 * `app/router.tsx`) when activated. Navigation goes through the
 * `HashRouter`'s own `location.hash` convention (matching
 * `InvestigationsPage`'s `#/investigations/{id}` links) rather than
 * `useNavigate()`, so this component keeps rendering standalone
 * outside a `<Router>` exactly as the existing test harness
 * (`dashboard.test.tsx`'s `renderToStaticMarkup`) already exercises
 * it. Rows without a real ID (`investigationId === null`) are left
 * non-interactive -- there's no real destination to send them to.
 */
export function DashboardRecentInvestigations({
  investigations,
}: DashboardRecentInvestigationsProps): ReactElement {
  const hasNavigableRow = investigations.some((row) => row.investigationId !== null);

  function activateRow(row: DashboardRecentInvestigationRow): void {
    if (row.investigationId === null) {
      return;
    }
    window.location.hash = `/investigations/${row.investigationId}`;
  }

  return (
    <Card title="Recent Investigations" className="dashboard-page__recent">
      {investigations.length === 0 ? (
        <p className="dashboard-page__empty">No recent investigations.</p>
      ) : (
        <div className="dashboard-recent-investigations__table-wrap">
          <DataTable
            caption="Recent investigations"
            columns={columns}
            rows={investigations}
            getRowId={(row) => row.id}
            {...(hasNavigableRow ? { onRowActivate: activateRow } : {})}
            getRowAriaLabel={(row) =>
              row.investigationId !== null
                ? `Open investigation ${row.name}, analyzed ${row.updatedLabel}`
                : `${row.name}, no workspace available`
            }
          />
        </div>
      )}
    </Card>
  );
}
