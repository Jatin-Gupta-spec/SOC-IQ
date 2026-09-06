/**
 * Native desktop file selection — Phase 4I Remediation, Blocker A.
 *
 * # What this closes
 *
 * `analysisReportPath.ts` needs a real, absolute, backend-readable
 * filesystem path. A browser `File` from `FileDropzone` (drag/drop or
 * `<input type="file">`) never carries one — that is a browser
 * security property, present in every browser-based webview including
 * Tauri's, not something any capability grant can change.
 *
 * The architecture-consistent fix already used for `get_sidecar_origin`
 * (`shared/api/client.ts`) is the Tauri IPC bridge itself — but a
 * filesystem *picker* is exactly what `tauri-plugin-dialog` exists
 * for, and is the officially documented, maintained path for this
 * exact use case (see `docs/security/tauri-capability-model.md`'s own
 * rule: widen the capability surface only for a specific, named,
 * implemented need — this is that need). No unrelated or invented
 * filesystem bridge is introduced: this module calls exactly two
 * plugin functions, `dialog::open` and `fs::readFile`, both official
 * Tauri plugins already used by the wider Tauri ecosystem for this
 * precise pattern (pick a file, read its bytes for client-side
 * validation before sending only its path to the backend).
 *
 * # Security shape
 *
 * - `dialog.open()` is the *only* thing that produces a path here —
 *   never a guessed path, never `file.name` treated as a path (the
 *   defect this remediation explicitly must not reintroduce).
 * - Per `@tauri-apps/plugin-dialog`'s own documented behavior, "the
 *   selected path is added to the filesystem ... scope" for the
 *   picked file only — this module never requests or relies on a
 *   broad, static filesystem scope grant; the user's own act of
 *   choosing a file in the OS-native dialog is what authorizes
 *   reading exactly that file, once, for this selection.
 * - `readFile()` is used only to validate the bytes the same way
 *   `validateAnalysisInput` already validates a browser-selected
 *   file's bytes (UTF-8 decodability) — this module does not send
 *   file contents anywhere; only the path is ever handed to
 *   `analyze_report` (`analysisExecution.ts`).
 * - Cancelling the dialog (`open()` resolving to `null`) is a normal,
 *   silent outcome, not an error.
 */

import { open } from "@tauri-apps/plugin-dialog";
import { readFile } from "@tauri-apps/plugin-fs";
import { isTauri } from "@tauri-apps/api/core";

import { toNativeAnalysisInput } from "./analysisInput";
import type { AnalysisInput } from "./analysisInput";

export type NativeFileSelectionResult =
  | { readonly ok: true; readonly input: AnalysisInput }
  | { readonly ok: false; readonly reason: "unsupported" }
  | { readonly ok: false; readonly reason: "cancelled" }
  | { readonly ok: false; readonly reason: "read-failed"; readonly cause: unknown };

/**
 * Whether the native picker can run at all in the current runtime.
 * `false` in a plain browser tab or the Vitest/jsdom test environment
 * (no Tauri IPC bridge present) — the UI uses this to decide whether
 * to offer the native "Browse for Analysis" control at all, rather
 * than offering a control that would only ever resolve `unsupported`.
 */
export function isNativeFileSelectionSupported(): boolean {
  return isTauri();
}

/** Best-effort basename extraction for both POSIX and Windows paths,
 * used only as the display file name — never fed back into any path
 * computation. */
function basename(path: string): string {
  const withoutTrailingSlash = path.replace(/[/\\]+$/, "");
  const segments = withoutTrailingSlash.split(/[/\\]/);
  return segments[segments.length - 1] || withoutTrailingSlash;
}

/**
 * Opens the native OS file picker, reads the selected file's real
 * bytes, and returns a ready-to-validate `AnalysisInput` carrying the
 * real absolute `sourcePath`. Never throws — every failure mode is a
 * typed `ok: false` result, matching `analysisExecution.ts`'s own
 * convention.
 */
export async function pickNativeReportFile(): Promise<NativeFileSelectionResult> {
  if (!isNativeFileSelectionSupported()) {
    return { ok: false, reason: "unsupported" };
  }

  let path: string | null;
  try {
    path = await open({ multiple: false, directory: false });
  } catch (cause) {
    return { ok: false, reason: "read-failed", cause };
  }

  if (path === null) {
    return { ok: false, reason: "cancelled" };
  }

  let bytes: Uint8Array;
  try {
    bytes = await readFile(path);
  } catch (cause) {
    return { ok: false, reason: "read-failed", cause };
  }

  const fileName = basename(path);
  // `bytes` is copied into the `File`/`Blob` constructor — this is a
  // real, self-contained snapshot of the file's content at selection
  // time, exactly as `File.arrayBuffer()` already gives
  // `validateAnalysisInput` for a browser-selected file. Using a
  // fresh `Uint8Array` view guards against `readFile`'s buffer being
  // any larger than the reported content (`ReadFileOptions` are not
  // passed here, so none is expected, but this keeps the invariant
  // explicit rather than assumed).
  const file = new File([new Uint8Array(bytes)], fileName);

  return { ok: true, input: toNativeAnalysisInput(file, path) };
}
