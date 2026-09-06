/**
 * Real report export action (Phase 4L-P3).
 *
 * Drives one row's "Export" control end to end: opens the native save
 * dialog (`reportExportPath.ts::pickReportSavePath`), then calls the
 * real, already-typed `export_report` command
 * (`shared/api/client.ts::runCommand`, `shared/api/types.ts`'s
 * `ExportReportPayload`/`ExportReportResult`) -- no second export
 * path, no simulated progress, no fabricated success. Cancelling the
 * save dialog resolves back to `"idle"` silently, matching
 * `pickReportSavePath()`'s own "cancel is not an error" contract.
 *
 * Mirrors `useInvestigationsList.ts`'s cancellation discipline (a
 * closure-scoped `cancelled` flag per invocation, guarding against a
 * component unmounting mid-export) even though this hook fires on a
 * user action rather than on mount -- the same race is possible if a
 * row's export is in flight when `ReportsPage` re-fetches and this
 * row's component unmounts.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand } from "../../shared/api/client";
import { pickReportSavePath } from "./reportExportPath";

export type ReportExportState =
  | { readonly status: "idle" }
  | { readonly status: "exporting" }
  | { readonly status: "success"; readonly outputPath: string }
  | { readonly status: "error"; readonly message: string };

export interface UseReportExportResult {
  readonly state: ReportExportState;
  /** Starts the real export flow for `investigationId`, suggesting
   * `defaultFileName` as the save dialog's initial name. Safe to call
   * again after `"success"` or `"error"` to re-export. No-ops while
   * already `"exporting"`. */
  readonly runExport: (investigationId: number, defaultFileName: string) => void;
}

function describeExportError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while exporting the report.";
}

export function useReportExport(): UseReportExportResult {
  const [state, setState] = useState<ReportExportState>({ status: "idle" });
  const cancelledRef = useRef(false);

  useEffect(
    () => () => {
      cancelledRef.current = true;
    },
    [],
  );

  const runExport = useCallback((investigationId: number, defaultFileName: string) => {
    setState((current) => {
      if (current.status === "exporting") {
        return current;
      }
      return { status: "exporting" };
    });

    void (async () => {
      const picked = await pickReportSavePath(defaultFileName);

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
            ? "Exporting reports requires the desktop app."
            : picked.reason === "no-extension"
              ? "Choose a file name with a .html, .pdf, .json, or .md extension."
              : describeExportError(picked.cause);
        setState({ status: "error", message });
        return;
      }

      try {
        const result = await runCommand("export_report", {
          investigation_id: investigationId,
          export_format: picked.format,
          output_path: picked.path,
        });
        if (cancelledRef.current) {
          return;
        }
        setState({ status: "success", outputPath: result.output_path });
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
