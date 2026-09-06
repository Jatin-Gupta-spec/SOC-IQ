/**
 * Native save-file picker for report export (Phase 4L-P3).
 *
 * `export_report` (`shared/api/types.ts::ExportReportPayload`) needs
 * a real, absolute, backend-writable `output_path` -- there is no
 * "download" concept in a Tauri desktop app the way there is in a
 * browser tab. The architecture-consistent way to get one is the same
 * one `pages/analyze/nativeFileSelection.ts` already established for
 * the *open* side of this problem: `tauri-plugin-dialog`, the
 * officially documented Tauri plugin for exactly this, already a
 * project dependency (`@tauri-apps/plugin-dialog`, `package.json`).
 * This module is that same pattern's *save* counterpart -- `save()`
 * instead of `open()`, otherwise the same shape: never throws, every
 * outcome is a typed `ok`/`reason` result, cancelling the dialog is a
 * normal (not error) outcome.
 *
 * # Format selection
 *
 * Rather than inventing a new format-picker control (a second UI
 * surface duplicating what the OS save dialog's own file-type filter
 * already does), the dialog is given all four real
 * `VALID_EXPORT_FORMATS` as filters; the chosen `ExportFormat` is
 * derived from the extension the OS dialog returns, since
 * `tauri-plugin-dialog` appends the active filter's extension to the
 * path itself. This keeps the export action to a single "Export"
 * control per row, consistent with the page not introducing new
 * primitives (§7).
 */

import { save } from "@tauri-apps/plugin-dialog";
import { isTauri } from "@tauri-apps/api/core";

import { VALID_EXPORT_FORMATS, type ExportFormat } from "../../shared/api/types";

export type ReportSavePathResult =
  | { readonly ok: true; readonly path: string; readonly format: ExportFormat }
  | { readonly ok: false; readonly reason: "unsupported" }
  | { readonly ok: false; readonly reason: "cancelled" }
  | { readonly ok: false; readonly reason: "no-extension" }
  | { readonly ok: false; readonly reason: "dialog-failed"; readonly cause: unknown };

/**
 * Whether the native save dialog can run at all in the current
 * runtime -- `false` in a plain browser tab or the Vitest/jsdom test
 * environment (no Tauri IPC bridge present), mirroring
 * `isNativeFileSelectionSupported()`'s exact reasoning.
 */
export function isReportSaveSupported(): boolean {
  return isTauri();
}

const EXTENSION_TO_FORMAT: Record<string, ExportFormat> = {
  html: "html",
  htm: "html",
  pdf: "pdf",
  json: "json",
  md: "markdown",
  markdown: "markdown",
};

function extensionOf(path: string): string | null {
  const base = path.split(/[/\\]/).pop() ?? path;
  const dotIndex = base.lastIndexOf(".");
  if (dotIndex <= 0) {
    return null;
  }
  return base.slice(dotIndex + 1).toLowerCase();
}

/**
 * Opens the native OS save dialog, pre-filtered to the four real
 * `VALID_EXPORT_FORMATS`, and resolves the chosen absolute path plus
 * the `ExportFormat` implied by its extension. `defaultFileName` is
 * only ever used as the dialog's suggested name -- never treated as,
 * or combined into, a path itself (the dialog's own return value is
 * the only source of the real path, same invariant
 * `pickNativeReportFile()` holds for the open side).
 */
export async function pickReportSavePath(defaultFileName: string): Promise<ReportSavePathResult> {
  if (!isReportSaveSupported()) {
    return { ok: false, reason: "unsupported" };
  }

  let path: string | null;
  try {
    path = await save({
      defaultPath: defaultFileName,
      filters: VALID_EXPORT_FORMATS.map((format) => ({
        name: format.toUpperCase(),
        extensions: [format === "markdown" ? "md" : format],
      })),
    });
  } catch (cause) {
    return { ok: false, reason: "dialog-failed", cause };
  }

  if (path === null) {
    return { ok: false, reason: "cancelled" };
  }

  const extension = extensionOf(path);
  const format = extension !== null ? EXTENSION_TO_FORMAT[extension] : undefined;

  if (format === undefined) {
    return { ok: false, reason: "no-extension" };
  }

  return { ok: true, path, format };
}
