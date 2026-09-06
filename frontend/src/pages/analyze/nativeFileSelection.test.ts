import { afterEach, describe, expect, it, vi } from "vitest";

const openMock = vi.fn();
const readFileMock = vi.fn();
const isTauriMock = vi.fn();

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: (...args: unknown[]) => openMock(...args),
}));

vi.mock("@tauri-apps/plugin-fs", () => ({
  readFile: (...args: unknown[]) => readFileMock(...args),
}));

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => isTauriMock(),
}));

// Imported after the mocks above so the module under test picks up
// the mocked implementations (vi.mock calls are hoisted, but the
// import itself must still come after for readability/clarity here).
import { isNativeFileSelectionSupported, pickNativeReportFile } from "./nativeFileSelection";

afterEach(() => {
  vi.resetAllMocks();
});

describe("isNativeFileSelectionSupported", () => {
  it("mirrors the Tauri runtime detection", () => {
    isTauriMock.mockReturnValue(true);
    expect(isNativeFileSelectionSupported()).toBe(true);

    isTauriMock.mockReturnValue(false);
    expect(isNativeFileSelectionSupported()).toBe(false);
  });
});

describe("pickNativeReportFile", () => {
  it("is unsupported outside a Tauri runtime and never calls the dialog", async () => {
    isTauriMock.mockReturnValue(false);
    const result = await pickNativeReportFile();
    expect(result).toEqual({ ok: false, reason: "unsupported" });
    expect(openMock).not.toHaveBeenCalled();
  });

  it("returns cancelled when the user dismisses the dialog", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue(null);
    const result = await pickNativeReportFile();
    expect(result).toEqual({ ok: false, reason: "cancelled" });
    expect(readFileMock).not.toHaveBeenCalled();
  });

  it("resolves ok with a real sourcePath and readable file content on success", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue("/home/user/reports/report.txt");
    readFileMock.mockResolvedValue(new TextEncoder().encode("suspicious.exe contacted 10.0.0.1"));

    const result = await pickNativeReportFile();

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("expected ok result");
    expect(result.input.sourcePath).toBe("/home/user/reports/report.txt");
    expect(result.input.fileName).toBe("report.txt");
    expect(await result.input.file.text()).toBe("suspicious.exe contacted 10.0.0.1");
    expect(readFileMock).toHaveBeenCalledWith("/home/user/reports/report.txt");
  });

  it("extracts the basename from a Windows-style path for the display file name", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue("C:\\Users\\user\\reports\\report.txt");
    readFileMock.mockResolvedValue(new TextEncoder().encode("content"));

    const result = await pickNativeReportFile();

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("expected ok result");
    expect(result.input.fileName).toBe("report.txt");
  });

  it("reports read-failed, not a throw, when the dialog itself rejects", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockRejectedValue(new Error("dialog plugin unavailable"));

    const result = await pickNativeReportFile();

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("expected a failure result");
    expect(result.reason).toBe("read-failed");
  });

  it("reports read-failed, not a throw, when reading the picked file's bytes fails", async () => {
    isTauriMock.mockReturnValue(true);
    openMock.mockResolvedValue("/home/user/reports/report.txt");
    readFileMock.mockRejectedValue(new Error("permission denied"));

    const result = await pickNativeReportFile();

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("expected a failure result");
    expect(result.reason).toBe("read-failed");
  });
});
