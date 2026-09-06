/**
 * Native directory selection for the Export Directory setting —
 * MAX-11 Phase 2A.
 *
 * # What this closes
 *
 * `ExportDirectoryControl` has always been a plain, hand-typed text
 * field: its own doc comment says so explicitly ("no filesystem-picker
 * architecture is introduced ... the legacy Qt page's `QFileDialog`
 * browse button has no frontend equivalent yet"). An analyst who wants
 * to point exports somewhere new has to know (or go find) the exact
 * absolute path and type it correctly by hand, with no OS-native
 * browsing and no way to confirm the folder actually exists — the
 * same "no real picker" gap `nativeFileSelection.ts` closed for the
 * *Analyze* file-selection flow, still open here on the *export*
 * side of the same workflow this checkpoint's prior two phases
 * (MAX-10 Phase 2A/Export & Filesystem Security Remediation) already
 * hardened.
 *
 * # Why this mirrors `nativeFileSelection.ts`
 *
 * Same plugin, same trust shape, same honesty conventions — this is
 * deliberately not a new pattern:
 *
 * - `dialog.open()` is the *only* thing that produces a path here,
 *   with `directory: true` instead of `directory: false` — never a
 *   guessed path, never string concatenation.
 * - No new Tauri capability is required. `tauri-plugin-dialog`
 *   exposes directory selection through the same `open` command
 *   file selection uses; `src-tauri/capabilities/default.json`
 *   already grants `dialog:allow-open` for `nativeFileSelection.ts`,
 *   and that grant is command-scoped, not mode-scoped, so it already
 *   covers `directory: true`. See this phase's closure doc for the
 *   verification-classification caveat (no Rust toolchain in this
 *   sandbox to compile-verify the manifest, consistent with every
 *   prior Tauri-touching session in this project).
 * - Cancelling the dialog (`open()` resolving to `null`) is a normal,
 *   silent outcome, not an error — matching `pickNativeReportFile`.
 * - This module only ever returns a path string. It does not read,
 *   write, or validate anything on disk — `save()`, unlike the
 *   read-and-validate shape `nativeFileSelection.ts` needs for
 *   Analyze, so there is no `plugin-fs` dependency here at all.
 * - The returned path is handed straight to `ExportDirectoryControl`'s
 *   existing `setValue`, which only ever reaches the backend through
 *   the field's existing, unmodified `save_settings` call once the
 *   analyst clicks Save — browsing fills the field, it does not
 *   silently persist a setting on the analyst's behalf.
 */

import { open } from "@tauri-apps/plugin-dialog";
import { isTauri } from "@tauri-apps/api/core";

export type DirectorySelectionResult =
  | { readonly ok: true; readonly path: string }
  | { readonly ok: false; readonly reason: "unsupported" }
  | { readonly ok: false; readonly reason: "cancelled" }
  | { readonly ok: false; readonly reason: "dialog-failed"; readonly cause: unknown };

/**
 * Whether the native directory picker can run at all in the current
 * runtime. `false` in a plain browser tab or the Vitest/jsdom test
 * environment (no Tauri IPC bridge present) — the UI uses this to
 * decide whether to offer a "Browse…" control at all, matching
 * `isNativeFileSelectionSupported`'s convention.
 */
export function isDirectoryBrowseSupported(): boolean {
  return isTauri();
}

/**
 * Opens the native OS folder picker and returns the selected
 * directory's real absolute path. Never throws — every failure mode
 * is a typed `ok: false` result, matching `pickNativeReportFile`'s
 * convention.
 */
export async function pickExportDirectory(): Promise<DirectorySelectionResult> {
  if (!isDirectoryBrowseSupported()) {
    return { ok: false, reason: "unsupported" };
  }

  let path: string | null;
  try {
    path = await open({ multiple: false, directory: true });
  } catch (cause) {
    return { ok: false, reason: "dialog-failed", cause };
  }

  if (path === null) {
    return { ok: false, reason: "cancelled" };
  }

  return { ok: true, path };
}
