import { afterEach, describe, expect, it, vi } from "vitest";

const openMock = vi.fn();
const isTauriMock = vi.fn();

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: (...args: unknown[]) => openMock(...args),
}));

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => isTauriMock(),
}));

// Imported after the mocks above so the module under test picks up
// the mocked implementations (vi.mock calls are hoisted, but the
// import itself must still come after for readability/clarity here).
import { isDirectoryBrowseSupported, pickExportDirectory } from "./exportDirectoryBrowse";

afterEach(() => {
  vi.resetAllMocks();
});

describe("isDirectoryBrowseSupported", () => {
  it("mirrors the Tauri runtime detection", () => {
    isTauriMock.mockReturnValue(true);
    expect(isDirectoryBrowseSupported()).toBe(true);

    isTauriMock.mockReturnValue(false);
    expect(isDirectoryBrowseSupported()).toBe(false);
  });
});

describe("pickExportDirectory", () => {
  it("is unsupported outside a Tauri runtime and never calls the dialog", async () => {
    isTauriMock.mockReturnValue(false);
    const result = await pickExportDirectory();
    expect(result).toEqual({ ok: false, reason: "unsupported" });
    expect(openMock).not.toHaveBeenCalled();
  });

  it("opens the dialog in directory mode, not file mode", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue("/home/analyst/exports");
    await pickExportDirectory();
    expect(openMock).toHaveBeenCalledWith({ multiple: false, directory: true });
  });

  it("returns cancelled when the user dismisses the dialog", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue(null);
    const result = await pickExportDirectory();
    expect(result).toEqual({ ok: false, reason: "cancelled" });
  });

  it("resolves ok with the real selected path on success", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue("/home/analyst/exports");
    const result = await pickExportDirectory();
    expect(result).toEqual({ ok: true, path: "/home/analyst/exports" });
  });

  it("resolves ok with a Windows-style path unchanged", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue("C:\\Users\\analyst\\exports");
    const result = await pickExportDirectory();
    expect(result).toEqual({ ok: true, path: "C:\\Users\\analyst\\exports" });
  });

  it("reports dialog-failed, not a throw, when the dialog itself rejects", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockRejectedValue(new Error("dialog plugin unavailable"));

    const result = await pickExportDirectory();

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("expected a failure result");
    expect(result.reason).toBe("dialog-failed");
  });
});
