/**
 * Native save-file picker for bulk investigation-history CSV export
 * (PD-08-P5.3).
 *
 * `export_investigations_csv` (`shared/api/types.ts::ExportInvestigationsCsvPayload`)
 * needs a real, absolute, backend-writable `output_path` -- there is
 * no "download" concept in a Tauri desktop app the way there is in a
 * browser tab (same reasoning `reportExportPath.ts`'s own doc comment
 * gives, and per the backend contract,
 * `docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md` §4, "the
 * only legitimate source of this value is a native OS save dialog").
 * This module is that same `pickReportSavePath()` pattern's one-format
 * counterpart: `save()` from `@tauri-apps/plugin-dialog`, filtered to
 * `.csv`, never throws, every outcome is a typed `ok`/`reason` result,
 * cancelling the dialog is a normal (not error) outcome.
 *
 * Unlike `pickReportSavePath`, there is only one export format here
 * (CSV), so there is no extension-to-format inference step -- the
 * dialog's own single `.csv` filter is enough.
 */

import { save } from "@tauri-apps/plugin-dialog";
import { isTauri } from "@tauri-apps/api/core";

export type InvestigationsCsvSavePathResult =
  | { readonly ok: true; readonly path: string }
  | { readonly ok: false; readonly reason: "unsupported" }
  | { readonly ok: false; readonly reason: "cancelled" }
  | { readonly ok: false; readonly reason: "dialog-failed"; readonly cause: unknown };

/**
 * Whether the native save dialog can run at all in the current
 * runtime -- `false` in a plain browser tab or the Vitest/jsdom test
 * environment (no Tauri IPC bridge present), mirroring
 * `isReportSaveSupported()`'s exact reasoning.
 */
export function isInvestigationsCsvSaveSupported(): boolean {
  return isTauri();
}

/**
 * Opens the native OS save dialog, filtered to `.csv`, and resolves
 * the chosen absolute path. `defaultFileName` is only ever used as the
 * dialog's suggested name -- never treated as, or combined into, a
 * path itself (the dialog's own return value is the only source of
 * the real path, same invariant `pickReportSavePath()` holds).
 */
export async function pickInvestigationsCsvSavePath(
  defaultFileName: string,
): Promise<InvestigationsCsvSavePathResult> {
  if (!isInvestigationsCsvSaveSupported()) {
    return { ok: false, reason: "unsupported" };
  }

  let path: string | null;
  try {
    path = await save({
      defaultPath: defaultFileName,
      filters: [{ name: "CSV", extensions: ["csv"] }],
    });
  } catch (cause) {
    return { ok: false, reason: "dialog-failed", cause };
  }

  if (path === null) {
    return { ok: false, reason: "cancelled" };
  }

  return { ok: true, path };
}
