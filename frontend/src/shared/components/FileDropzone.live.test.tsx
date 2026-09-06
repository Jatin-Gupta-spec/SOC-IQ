// @vitest-environment jsdom
/**
 * `FileDropzone` interaction tests — Phase 4I-1A, §6/§15.
 *
 * Exercises real DOM events (drag/drop, change, focus) the way
 * `CommandPaletteContainer.live.test.tsx` exercises real keyboard
 * events — `createRoot` + `act`, no `@testing-library` dependency
 * (none is installed; see `frontend/package.json`).
 *
 * Drag-and-drop is simulated with a minimal `FileList`-like stub
 * (array-indexed object carrying `length` + a numeric `item()`)
 * rather than `new DataTransfer()` + `dt.items.add()`: jsdom's
 * `DataTransfer`/`DataTransferItemList` file support has been
 * inconsistent across versions, and the component only ever reads
 * `event.dataTransfer.files.length` and indexes into it
 * (`FileDropzone.tsx::handleFiles`), so a plain object satisfying
 * that shape exercises the same code path without depending on a
 * jsdom API surface this project doesn't otherwise use.
 */

import type { ComponentProps } from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FileDropzone } from "./FileDropzone";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(props: Partial<ComponentProps<typeof FileDropzone>> = {}): {
  onFileSelected: ReturnType<typeof vi.fn>;
  onRejected: ReturnType<typeof vi.fn>;
} {
  const onFileSelected = vi.fn();
  const onRejected = vi.fn();
  act(() => {
    root = createRoot(container);
    root.render(
      <FileDropzone
        id="f1"
        label="Select a file"
        onFileSelected={onFileSelected}
        onRejected={onRejected}
        {...props}
      />,
    );
  });
  return { onFileSelected, onRejected };
}

/** Minimal `FileList`-like stub — see this file's doc comment. */
function fileListOf(files: File[]): FileList {
  const stub: Record<number, File> & { length: number; item: (i: number) => File | null } = {
    length: files.length,
    item(index: number) {
      return files[index] ?? null;
    },
  };
  files.forEach((f, i) => {
    stub[i] = f;
  });
  return stub as unknown as FileList;
}

function dropzoneRoot(): HTMLElement {
  return container.querySelector('[data-testid="file-dropzone"]') as HTMLElement;
}

function fileInput(): HTMLInputElement {
  return container.querySelector("input[type=file]") as HTMLInputElement;
}

function dispatchDrop(target: HTMLElement, files: File[]): void {
  act(() => {
    const event = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "dataTransfer", { value: { files: fileListOf(files) } });
    target.dispatchEvent(event);
  });
}

describe("FileDropzone browse/select", () => {
  it("calls onFileSelected with the chosen file via the native input", () => {
    const { onFileSelected } = render();
    const file = new File(["content"], "report.txt", { type: "text/plain" });
    const input = fileInput();

    Object.defineProperty(input, "files", {
      value: fileListOf([file]),
      configurable: true,
    });
    act(() => {
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(onFileSelected).toHaveBeenCalledTimes(1);
    expect(onFileSelected).toHaveBeenCalledWith(file);
  });

  it("is keyboard-focusable (a real, native form control)", () => {
    render();
    const input = fileInput();
    input.focus();
    expect(document.activeElement).toBe(input);
    expect(input.tabIndex).not.toBe(-1);
  });

  it("respects disabled — the input is disabled and not focusable via the UI", () => {
    render({ disabled: true });
    const input = fileInput();
    expect(input.disabled).toBe(true);
  });
});

describe("FileDropzone drag-and-drop", () => {
  it("calls onFileSelected with a single dropped file", () => {
    const { onFileSelected } = render();
    const file = new File(["content"], "dropped.txt", { type: "text/plain" });

    dispatchDrop(dropzoneRoot(), [file]);

    expect(onFileSelected).toHaveBeenCalledTimes(1);
    expect(onFileSelected).toHaveBeenCalledWith(file);
  });

  it("rejects (does not accept) more than one dropped file", () => {
    const { onFileSelected, onRejected } = render();

    dispatchDrop(dropzoneRoot(), [
      new File(["a"], "one.txt"),
      new File(["b"], "two.txt"),
    ]);

    expect(onFileSelected).not.toHaveBeenCalled();
    expect(onRejected).toHaveBeenCalledTimes(1);
  });

  it("shows a drag-over visual state while dragging, and clears it on drag leave", () => {
    render();
    const root_ = dropzoneRoot();

    act(() => {
      root_.dispatchEvent(new Event("dragover", { bubbles: true, cancelable: true }));
    });
    expect(root_.className).toContain("file-dropzone--drag-over");

    act(() => {
      root_.dispatchEvent(new Event("dragleave", { bubbles: true, cancelable: true }));
    });
    expect(root_.className).not.toContain("file-dropzone--drag-over");
  });

  it("ignores drops while disabled", () => {
    const { onFileSelected } = render({ disabled: true });

    dispatchDrop(dropzoneRoot(), [new File(["a"], "one.txt")]);

    expect(onFileSelected).not.toHaveBeenCalled();
  });
});
