import type { ReactElement } from "react";
import { Button } from "../components/Button";
import { useReportExport } from "./useReportExport";
import { isReportSaveSupported } from "./reportExportPath";

export interface ReportExportActionProps {
  readonly investigationId: number | null;
  readonly reportName: string;
}

/**
 * One row's real "Export" control (Phase 4L-P3). Unlike the previous
 * mock page's permanently-`disabled` Download button, this actually
 * calls `export_report` -- but only ever offers to when there is a
 * real investigation id to export (`investigationId !== null`) and a
 * real native save dialog to get a path from
 * (`isReportSaveSupported()`); otherwise it says so honestly rather
 * than rendering a control that cannot work, matching the task's "no
 * fake functionality" rule the original mock page's doc comment
 * already followed.
 */
export function ReportExportAction({ investigationId, reportName }: ReportExportActionProps): ReactElement {
  const { state, runExport } = useReportExport();

  if (investigationId === null) {
    return (
      <span className="reports-page__action-disabled" aria-label={`Export unavailable for ${reportName}`}>
        Export unavailable
      </span>
    );
  }

  if (!isReportSaveSupported()) {
    return (
      <span className="reports-page__action-disabled" aria-label={`Export ${reportName} requires the desktop app`}>
        Desktop app required
      </span>
    );
  }

  const label =
    state.status === "exporting" ? "Exporting…" : state.status === "success" ? "Export again" : state.status === "error" ? "Retry export" : "Export";

  return (
    <div className="reports-page__action-cell">
      <Button
        size="compact"
        onClick={() => runExport(investigationId, reportName)}
        disabled={state.status === "exporting"}
        aria-label={`Export ${reportName}`}
      >
        {label}
      </Button>
      {state.status === "success" ? (
        <p className="reports-page__action-note" role="status" aria-live="polite">
          Saved to {state.outputPath}
        </p>
      ) : null}
      {state.status === "error" ? (
        <p className="reports-page__action-note reports-page__action-note--error" role="alert">
          {state.message}
        </p>
      ) : null}
    </div>
  );
}
