import type { ReactElement } from "react";
import { Button } from "../components/Button";
import { useInvestigationsCsvExport } from "./useInvestigationsCsvExport";
import { isInvestigationsCsvSaveSupported } from "./investigationsCsvExportPath";

/**
 * The Investigations page's "Export CSV" control (PD-08-P5.3). Lives
 * in `PageHeader`'s `actions` slot rather than inside the `Card`
 * housing the table, so it reads as a page-level action on the whole
 * investigation history rather than a per-row/table affordance --
 * consistent with it exporting every investigation, not the current
 * table selection.
 *
 * Only ever offers to export when there is a real native save dialog
 * to get a path from (`isInvestigationsCsvSaveSupported()`);
 * otherwise it says so honestly rather than rendering a control that
 * cannot work, mirroring `ReportExportAction`'s own "no fake
 * functionality" rule. No `title` tooltip is added -- the project has
 * no existing tooltip convention (confirmed by reading every other
 * page/action component), so this control's accessible name
 * (`aria-label`) and its visible label are the only affordances,
 * exactly as `ReportExportAction`'s own control already establishes.
 */
export function InvestigationsCsvExportAction(): ReactElement {
  const { state, runExport } = useInvestigationsCsvExport();

  if (!isInvestigationsCsvSaveSupported()) {
    return (
      <span
        className="investigations-page__export-disabled"
        aria-label="Exporting investigation history requires the desktop app"
      >
        Desktop app required
      </span>
    );
  }

  const label =
    state.status === "exporting"
      ? "Exporting…"
      : state.status === "success"
        ? "Export CSV again"
        : state.status === "error"
          ? "Retry export CSV"
          : "Export CSV";

  return (
    <div className="investigations-page__export-cell">
      <Button
        size="compact"
        onClick={() => runExport()}
        disabled={state.status === "exporting"}
        aria-busy={state.status === "exporting"}
        aria-label="Export investigation history as CSV"
      >
        {label}
      </Button>
      {state.status === "success" ? (
        <p className="investigations-page__export-note" role="status" aria-live="polite">
          Saved {state.rowCount} {state.rowCount === 1 ? "row" : "rows"} to {state.outputPath}
        </p>
      ) : null}
      {state.status === "error" ? (
        <p
          className="investigations-page__export-note investigations-page__export-note--error"
          role="alert"
        >
          {state.message}
        </p>
      ) : null}
    </div>
  );
}
