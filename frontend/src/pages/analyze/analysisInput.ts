/**
 * Analysis input model + validation — Phase 4I-1A, §5/§7/§8.
 *
 * # Why this shape (§5)
 *
 * The only backend entry point this checkpoint's input eventually
 * feeds is `analyze_report`, whose payload is `{ report_path: string
 * }` (`shared/api/types.ts::AnalyzeReportPayload`, mirroring
 * `AnalyzeReportRequest` in `app/application/dto.py`). The report
 * itself is read as plain UTF-8 text
 * (`app/extractor.py::read_report`) with no extension allowlist and
 * no documented size limit anywhere in the application/backend
 * layer — so this model does not invent one (§5, §7: "Do NOT invent
 * arbitrary file-size limits").
 *
 * `AnalysisInput` therefore carries what a browser-side file pick
 * genuinely gives us: the selected `File` and its metadata. A
 * drag-and-drop or `<input type="file">` selection still has no real
 * filesystem path available to it (a browser `File` object never
 * exposes one, with or without any Tauri capability — this is a
 * browser security property, not a missing permission) and so never
 * carries `sourcePath`.
 *
 * Phase 4I Remediation — Blocker A: a *native* desktop selection
 * (`nativeFileSelection.ts`, via `tauri-plugin-dialog`'s file picker)
 * genuinely does give us a real, absolute, backend-readable
 * filesystem path — the OS picker itself resolves it, and the
 * selecting user has already demonstrated read access to exactly that
 * file by choosing it. `sourcePath` carries that path when, and only
 * when, the input came from that native flow
 * (`toNativeAnalysisInput`) — never inferred, guessed, or derived
 * from `file.name` for a browser-only selection (`toAnalysisInput`
 * never sets it). `analysisReportPath.ts::resolveReportPath` is the
 * single place this field is read to decide whether real execution
 * can proceed.
 *
 * # Why validation reads file bytes (§7)
 *
 * The one real backend constraint that exists is implicit in
 * `read_report`: the file must decode as UTF-8, or the backend
 * raises `ReportReadError`. A file's name/MIME type cannot tell you
 * that — only its bytes can — so validation here actually reads the
 * file and attempts the same decode the backend will eventually
 * perform, rather than guessing from an extension allowlist this
 * project has no source of truth for. This is why validation is
 * async and why `analysisWorkflowState.ts` has a distinct
 * `validating` state.
 */

export interface AnalysisInput {
  readonly file: File;
  readonly fileName: string;
  readonly fileSize: number;
  /**
   * The real, absolute filesystem path backing `file`, if and only if
   * this input came from the native desktop picker
   * (`nativeFileSelection.ts::pickNativeReportFile`). `undefined` for
   * every browser drag/drop or `<input type="file">` selection — see
   * this file's doc comment for why those can never have one.
   */
  readonly sourcePath?: string;
}

export function toAnalysisInput(file: File): AnalysisInput {
  return { file, fileName: file.name, fileSize: file.size };
}

/**
 * Builds an `AnalysisInput` for a file selected through the native
 * desktop picker, where `sourcePath` is a real absolute path the
 * backend can open directly. `file` still carries real bytes (read
 * via `tauri-plugin-fs`) so the existing `validateAnalysisInput` UTF-8
 * check below applies identically to both selection paths — native
 * selection does not skip content validation.
 */
export function toNativeAnalysisInput(file: File, sourcePath: string): AnalysisInput {
  return { file, fileName: file.name, fileSize: file.size, sourcePath };
}

/**
 * Why validation fails, plus the accessible, non-technical message
 * shown for it (§8: "Do NOT display stack traces / Python exceptions
 * / internal class names / raw API responses"). `cause` preserves the
 * original error for diagnostics only — never rendered, so a real
 * decode/read exception doesn't leak into the UI (§8: "preserve
 * internal error information separately for diagnostics").
 */
export type AnalysisInputRejection =
  | { readonly reason: "empty" }
  | { readonly reason: "unreadable-encoding" }
  | { readonly reason: "read-failed"; readonly cause: unknown };

export function describeRejection(rejection: AnalysisInputRejection): string {
  switch (rejection.reason) {
    case "empty":
      return "This file is empty. Choose a file that contains report content.";
    case "unreadable-encoding":
      return "This file isn't readable as text. Analysis supports plain-text reports only.";
    case "read-failed":
      return "This file couldn't be read. Check that it's still available and try again.";
  }
}

export type AnalysisInputValidationResult =
  | { readonly ok: true }
  | { readonly ok: false; readonly rejection: AnalysisInputRejection };

/**
 * Validates a selected input against the one real backend constraint
 * (readable as UTF-8 text) plus basic presence. No extension
 * allowlist, no invented size ceiling — see this file's doc comment.
 */
export async function validateAnalysisInput(
  input: AnalysisInput,
): Promise<AnalysisInputValidationResult> {
  if (input.fileSize === 0) {
    return { ok: false, rejection: { reason: "empty" } };
  }

  let bytes: ArrayBuffer;
  try {
    bytes = await input.file.arrayBuffer();
  } catch (cause) {
    return { ok: false, rejection: { reason: "read-failed", cause } };
  }

  try {
    // `fatal: true` mirrors the backend's own `encoding="utf-8"`
    // strict decode in `app/extractor.py::read_report` — a file that
    // fails here is one the backend would reject with
    // `ReportReadError` too.
    new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return { ok: false, rejection: { reason: "unreadable-encoding" } };
  }

  return { ok: true };
}
