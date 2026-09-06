import { useState } from "react";
import type { ChangeEvent, DragEvent, ReactElement } from "react";
import "./FileDropzone.css";

export interface FileDropzoneProps {
  /** Both the `<input>` id and its `htmlFor` — must be unique on the page. */
  readonly id: string;
  /** Accessible name for the underlying file input (not visible text). */
  readonly label: string;
  /** Visible prompt shown when no file is selected. */
  readonly helperText?: string;
  /**
   * Name of the currently selected file, if any — shown in place of
   * `helperText`. Typed with an explicit `| undefined` (not just
   * `?:`) because callers (e.g. `AnalyzePage`) commonly compute this
   * from a ternary that can itself produce `undefined` — under this
   * project's `exactOptionalPropertyTypes`, passing such a value to
   * a prop typed only `selectedFileName?: string` is a type error.
   */
  readonly selectedFileName?: string | undefined;
  readonly disabled?: boolean;
  /** Called with the single selected/dropped file. */
  readonly onFileSelected: (file: File) => void;
  /**
   * Called instead of `onFileSelected` when the drop/pick itself is
   * unsupported (more than one file) — distinct from *content*
   * validation, which is `analysisInput.ts`'s job, not this
   * component's (§7: file-content validation lives with the input
   * model; this is only "did the browser hand us something this
   * control can accept at all").
   */
  readonly onRejected?: (message: string) => void;
}

/**
 * Generic single-file drag-and-drop + browse control — Phase 4I-1A, §6.
 *
 * No `FileDropzone` existed anywhere in the frozen 4H baseline (the
 * Analyze page's dropzone was a static, non-interactive `<div>` with
 * a permanently `disabled` browse button — see `AnalyzePage.tsx`'s
 * prior revision). This is a new component, not a rewrite of an
 * existing one; the historical "palette.surface" defect this
 * checkpoint's brief asked to re-verify does not apply for the same
 * reason — there was nothing to have that defect.
 *
 * Built as a `<label>` wrapping a real (visually hidden, not
 * `display:none`'d) `<input type="file">` rather than a custom
 * `role="button"` + key-handler div: this gets click, Tab focus,
 * visible focus, and Enter/Space activation from the browser's own
 * native form-control behavior instead of a second, hand-rolled
 * implementation of it (§13: "Use semantic HTML first. Do not add
 * redundant ARIA").
 */
export function FileDropzone({
  id,
  label,
  helperText,
  selectedFileName,
  disabled = false,
  onFileSelected,
  onRejected,
}: FileDropzoneProps): ReactElement {
  const [isDragOver, setIsDragOver] = useState(false);

  function handleFiles(fileList: FileList | null): void {
    if (!fileList || fileList.length === 0) {
      return;
    }
    if (fileList.length > 1) {
      onRejected?.("Select a single file — only one file can be analyzed at a time.");
      return;
    }
    // `.item(0)` (not `fileList[0]`) because this project's
    // `noUncheckedIndexedAccess` makes `FileList`'s numeric index
    // signature return `File | undefined` even when `.length` is
    // known — `.item()` is the typed-safe accessor.
    const file = fileList.item(0);
    if (!file) {
      return;
    }
    onFileSelected(file);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>): void {
    handleFiles(event.target.files);
    // Reset so selecting the same file again still fires a change event.
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setIsDragOver(false);
    if (disabled) {
      return;
    }
    handleFiles(event.dataTransfer.files);
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    if (!disabled) {
      setIsDragOver(true);
    }
  }

  function handleDragLeave(): void {
    setIsDragOver(false);
  }

  const classes = [
    "file-dropzone",
    isDragOver ? "file-dropzone--drag-over" : "",
    disabled ? "file-dropzone--disabled" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={classes}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      data-testid="file-dropzone"
    >
      <label htmlFor={id} className="file-dropzone__label">
        <p className="file-dropzone__text">
          {selectedFileName ? (
            <span className="file-dropzone__filename">{selectedFileName}</span>
          ) : (
            (helperText ?? "Drag a file here, or browse to select one")
          )}
        </p>
        <span className="file-dropzone__browse-button" aria-hidden="true">
          Browse files
        </span>
      </label>
      <input
        id={id}
        type="file"
        className="file-dropzone__input"
        aria-label={label}
        disabled={disabled}
        onChange={handleInputChange}
      />
    </div>
  );
}
