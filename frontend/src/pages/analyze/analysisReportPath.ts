/**
 * Report-path resolution boundary — Phase 4I-1B §3/§4; Blocker A
 * remediation (Phase 4I Remediation Part 1).
 *
 * # Why this file exists
 *
 * The one real backend execution entry point, `analyze_report`
 * (`app/application/handlers.py::AnalyzeReportCommandHandler`,
 * mirrored as `analyze_report` in `shared/api/types.ts`), takes
 * exactly one field: `{ report_path: string }` — a filesystem path
 * the backend reads directly (`_report_path_is_valid` /
 * `app.analyzer.analyze_report` both take a `Path`).
 *
 * `AnalysisInput` (`analysisInput.ts`) carries a browser `File`, which
 * never has a real filesystem path for a drag/drop or
 * `<input type="file">` selection (a browser security property, not a
 * missing permission — see that file's doc comment). Blocker A closes
 * this gap for the one selection path that genuinely can supply a
 * real path: the native OS file picker
 * (`nativeFileSelection.ts`, via `tauri-plugin-dialog`), which resolves
 * an absolute path and stamps it onto `AnalysisInput.sourcePath`
 * (`toNativeAnalysisInput`).
 *
 * This function is the single place `analysisExecution.ts`
 * (indirectly, via `useAnalysisExecution.ts`) asks "do we have a
 * usable report_path for this input" — and now the honest answer is
 * "yes" for a native selection, "no" for anything else. Browser
 * drag/drop and the plain file input remain honestly blocked; this
 * checkpoint does not fake a path for them (§3 of the original 4I-1B
 * brief, unchanged: "If no real execution endpoint exists: DO NOT
 * INVENT ONE").
 */

import type { AnalysisInput } from "./analysisInput";

export type ReportPathBlockedReason = "no-filesystem-capability";

export type ReportPathResolution =
  | { readonly ok: true; readonly reportPath: string }
  | { readonly ok: false; readonly reason: ReportPathBlockedReason };

/**
 * A `sourcePath` is trusted only when it is non-empty, contains no
 * embedded NUL byte (a classic path-confusion vector — a NUL can
 * truncate how a lower-level C/OS API interprets the string), and is
 * absolute. `tauri-plugin-dialog`'s picker already only ever returns
 * absolute, OS-validated paths for a file the user themselves just
 * selected — this check is defense-in-depth against a malformed or
 * tampered value reaching this function some other way (e.g. a future
 * caller), not a workaround for anything the picker itself is known
 * to produce. It does not attempt `..`-segment normalization: the
 * path came from the OS's own picker dialog, not from user-typed or
 * URL-derived input, so there is no untrusted relative segment to
 * traverse away from an intended root — there is no "intended root"
 * at all, by design (§2 of the remediation brief: any file the user
 * can browse to and open is a legitimate report source).
 */
function isTrustedAbsolutePath(path: string): boolean {
  if (path.length === 0) {
    return false;
  }
  if (path.includes("\u0000")) {
    return false;
  }
  // POSIX absolute path, or a Windows drive-letter / UNC path — the
  // three shapes `tauri-plugin-dialog` can actually return across the
  // desktop platforms this project targets.
  const isPosixAbsolute = path.startsWith("/");
  const isWindowsDriveAbsolute = /^[a-zA-Z]:[\\/]/.test(path);
  const isWindowsUnc = path.startsWith("\\\\");
  return isPosixAbsolute || isWindowsDriveAbsolute || isWindowsUnc;
}

/**
 * Attempts to resolve a filesystem path for `input` that the backend
 * could open. `ok: true` only when `input.sourcePath` was set by the
 * native picker flow and passes `isTrustedAbsolutePath` — every
 * browser-only selection (`sourcePath` unset) is still always
 * `ok: false`, unchanged from before this remediation.
 */
export function resolveReportPath(input: AnalysisInput): ReportPathResolution {
  if (input.sourcePath !== undefined && isTrustedAbsolutePath(input.sourcePath)) {
    return { ok: true, reportPath: input.sourcePath };
  }
  return { ok: false, reason: "no-filesystem-capability" };
}

export function describeReportPathBlockedReason(reason: ReportPathBlockedReason): string {
  switch (reason) {
    case "no-filesystem-capability":
      return "This file doesn't have a backend-readable location — drag-and-drop and the plain file picker can't provide one. Use \u201CBrowse for Analysis\u201D to select a file through the native file picker instead.";
  }
}
