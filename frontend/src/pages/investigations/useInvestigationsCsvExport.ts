/**
 * Real bulk investigation-history CSV export action (PD-08-P5.3).
 *
 * Drives the Investigations page's "Export CSV" control end to end:
 * opens the native save dialog
 * (`investigationsCsvExportPath.ts::pickInvestigationsCsvSavePath`),
 * then calls the real, already-typed `export_investigations_csv`
 * command (`shared/api/client.ts::runCommand`,
 * `shared/api/types.ts`'s `ExportInvestigationsCsvPayload`/
 * `ExportInvestigationsCsvResult`) -- no second export path, no
 * client-side CSV generation, no fabricated success. Cancelling the
 * save dialog resolves back to `"idle"` silently, matching
 * `pickInvestigationsCsvSavePath()`'s own "cancel is not an error"
 * contract.
 *
 * This page currently has no search/filter/sort controls
 * (`InvestigationsPage.tsx`), so there is no active filter state to
 * forward -- `search` is simply omitted from the command payload,
 * which the backend contract already treats identically to `None`
 * ("no filter, export everything";
 * `docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md` §4). If
 * the page later grows a search box, that value threads through here
 * as `search` -- the export scope must keep matching whatever the
 * page is currently showing, per that same contract, rather than
 * silently diverging.
 *
 * Mirrors `useReportExport.ts`'s cancellation discipline (a
 * closure-scoped `cancelled` flag per invocation, guarding against the
 * page unmounting mid-export) for the identical reason.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand } from "../../shared/api/client";
import { pickInvestigationsCsvSavePath } from "./investigationsCsvExportPath";

export type InvestigationsCsvExportState =
  | { readonly status: "idle" }
  | { readonly status: "exporting" }
  | { readonly status: "success"; readonly outputPath: string; readonly rowCount: number }
  | { readonly status: "error"; readonly message: string };

export interface UseInvestigationsCsvExportResult {
  readonly state: InvestigationsCsvExportState;
  /** Starts the real export flow, suggesting `defaultFileName`
   * ("investigations.csv") as the save dialog's initial name. Safe to
   * call again after `"success"` or `"error"` to re-export. No-ops
   * while already `"exporting"` (Part 6: prevent accidental duplicate
   * submissions). */
  readonly runExport: (defaultFileName?: string) => void;
}

const DEFAULT_FILE_NAME = "investigations.csv";

function describeExportError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while exporting investigation history.";
}

export function useInvestigationsCsvExport(): UseInvestigationsCsvExportResult {
  const [state, setState] = useState<InvestigationsCsvExportState>({ status: "idle" });
  const cancelledRef = useRef(false);

  useEffect(
    () => () => {
      cancelledRef.current = true;
    },
    [],
  );

  const runExport = useCallback((defaultFileName: string = DEFAULT_FILE_NAME) => {
    setState((current) => {
      if (current.status === "exporting") {
        return current;
      }
      return { status: "exporting" };
    });

    void (async () => {
      const picked = await pickInvestigationsCsvSavePath(defaultFileName);

      if (cancelledRef.current) {
        return;
      }

      if (!picked.ok) {
        if (picked.reason === "cancelled") {
          setState({ status: "idle" });
          return;
        }
        const message =
          picked.reason === "unsupported"
            ? "Exporting investigation history requires the desktop app."
            : describeExportError(picked.cause);
        setState({ status: "error", message });
        return;
      }

      try {
        const result = await runCommand("export_investigations_csv", {
          output_path: picked.path,
        });
        if (cancelledRef.current) {
          return;
        }
        setState({
          status: "success",
          outputPath: result.output_path,
          rowCount: result.row_count,
        });
      } catch (error) {
        if (cancelledRef.current) {
          return;
        }
        setState({ status: "error", message: describeExportError(error) });
      }
    })();
  }, []);

  return { state, runExport };
}
