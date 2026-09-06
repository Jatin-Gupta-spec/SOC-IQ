// @vitest-environment jsdom
/**
 * Live-DOM tests for `ExportDirectoryControl`'s native "Browse…"
 * button (MAX-11 Phase 2A) -- a separate file from
 * `ExportDirectoryControl.live.test.tsx` because this suite mocks
 * `@tauri-apps/plugin-dialog`/`@tauri-apps/api/core` to force a
 * Tauri-supported runtime, while the existing suite deliberately runs
 * in the real (non-Tauri) jsdom environment to prove the field still
 * works as a plain text input outside Tauri. Save/dirty/error/retry
 * behavior is already fully covered there and is untouched by this
 * addition, so it is not re-tested here.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runCommandMock = vi.fn();
const openMock = vi.fn();
const isTauriMock = vi.fn();

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>(
    "../../shared/api/client",
  );
  return {
    ...actual,
    runCommand: (...args: unknown[]) => runCommandMock(...args),
  };
});

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: (...args: unknown[]) => openMock(...args),
}));

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => isTauriMock(),
}));

import { ExportDirectoryControl } from "./ExportDirectoryControl";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  runCommandMock.mockReset();
  openMock.mockReset();
  isTauriMock.mockReset();
  isTauriMock.mockReturnValue(true);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(persistedExportDirectory: string): void {
  act(() => {
    root = createRoot(container);
    root.render(<ExportDirectoryControl persistedExportDirectory={persistedExportDirectory} />);
  });
}

function inputEl(): HTMLInputElement {
  return container.querySelector("#settings-export-directory") as HTMLInputElement;
}

function saveButton(): HTMLButtonElement {
  return container.querySelector(".settings-page__save-button") as HTMLButtonElement;
}

function browseButton(): HTMLButtonElement | null {
  return container.querySelector(".settings-page__browse-button");
}

async function flush(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("Tauri runtime detection", () => {
  it("does not render Browse outside a Tauri runtime", () => {
    isTauriMock.mockReturnValue(false);
    render("/home/analyst/output");
    expect(browseButton()).toBeNull();
  });

  it("renders Browse in a Tauri runtime", () => {
    render("/home/analyst/output");
    expect(browseButton()).not.toBeNull();
    expect(browseButton()?.textContent).toBe("Browse…");
  });
});

describe("browsing", () => {
  it("fills the field with the picked directory without saving it", async () => {
    openMock.mockResolvedValue("/home/analyst/new-exports");
    render("/home/analyst/output");

    await act(async () => {
      browseButton()?.click();
      await flush();
    });

    expect(inputEl().value).toBe("/home/analyst/new-exports");
    expect(saveButton().disabled).toBe(false);
    expect(runCommandMock).not.toHaveBeenCalled();
  });

  it("opens the dialog in directory mode", async () => {
    openMock.mockResolvedValue("/home/analyst/new-exports");
    render("/home/analyst/output");

    await act(async () => {
      browseButton()?.click();
      await flush();
    });

    expect(openMock).toHaveBeenCalledWith({ multiple: false, directory: true });
  });

  it("leaves the field untouched when the dialog is cancelled", async () => {
    openMock.mockResolvedValue(null);
    render("/home/analyst/output");

    await act(async () => {
      browseButton()?.click();
      await flush();
    });

    expect(inputEl().value).toBe("/home/analyst/output");
    expect(saveButton().disabled).toBe(true);
    expect(container.textContent).not.toContain("Couldn't open the folder picker");
  });

  it("shows a recoverable error, not a crash, when the dialog itself fails", async () => {
    openMock.mockRejectedValue(new Error("dialog plugin unavailable"));
    render("/home/analyst/output");

    await act(async () => {
      browseButton()?.click();
      await flush();
    });

    expect(container.textContent).toContain("Couldn't open the folder picker");
    expect(inputEl().value).toBe("/home/analyst/output");
  });

  it("clears a previous browse error once a later browse succeeds", async () => {
    openMock.mockRejectedValueOnce(new Error("dialog plugin unavailable"));
    render("/home/analyst/output");

    await act(async () => {
      browseButton()?.click();
      await flush();
    });
    expect(container.textContent).toContain("Couldn't open the folder picker");

    openMock.mockResolvedValueOnce("/home/analyst/new-exports");
    await act(async () => {
      browseButton()?.click();
      await flush();
    });

    expect(container.textContent).not.toContain("Couldn't open the folder picker");
    expect(inputEl().value).toBe("/home/analyst/new-exports");
  });

  it("still saves normally through the existing Save flow after a browse fills the field", async () => {
    runCommandMock.mockResolvedValue({ field: "export_directory", updated: true });
    openMock.mockResolvedValue("/home/analyst/new-exports");
    render("/home/analyst/output");

    await act(async () => {
      browseButton()?.click();
      await flush();
    });

    act(() => {
      saveButton().click();
    });

    expect(runCommandMock).toHaveBeenCalledTimes(1);
    expect(runCommandMock).toHaveBeenNthCalledWith(1, "save_settings", {
      export_directory: "/home/analyst/new-exports",
    });

    await flush();
  });

  it("disables Browse while a save is in flight", async () => {
    let resolveSave!: (value: unknown) => void;
    runCommandMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSave = resolve;
        }),
    );
    openMock.mockResolvedValue("/home/analyst/new-exports");
    render("/home/analyst/output");

    await act(async () => {
      browseButton()?.click();
      await flush();
    });

    act(() => {
      saveButton().click();
    });
    expect(browseButton()?.disabled).toBe(true);

    act(() => {
      resolveSave({ field: "export_directory", updated: true });
    });
    await flush();
  });
});
