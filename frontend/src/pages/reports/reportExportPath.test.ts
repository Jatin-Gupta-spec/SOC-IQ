import { afterEach, describe, expect, it, vi } from "vitest";

const saveMock = vi.fn();
const isTauriMock = vi.fn();

vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: (...args: unknown[]) => saveMock(...args),
}));

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => isTauriMock(),
}));

import { isReportSaveSupported, pickReportSavePath } from "./reportExportPath";

afterEach(() => {
  vi.resetAllMocks();
});

describe("isReportSaveSupported", () => {
  it("mirrors the Tauri runtime detection", () => {
    isTauriMock.mockReturnValue(true);
    expect(isReportSaveSupported()).toBe(true);

    isTauriMock.mockReturnValue(false);
    expect(isReportSaveSupported()).toBe(false);
  });
});

describe("pickReportSavePath", () => {
  it("is unsupported outside a Tauri runtime and never calls the dialog", async () => {
    isTauriMock.mockReturnValue(false);
    const result = await pickReportSavePath("report.pdf");
    expect(result).toEqual({ ok: false, reason: "unsupported" });
    expect(saveMock).not.toHaveBeenCalled();
  });

  it("returns cancelled when the user dismisses the dialog", async () => {
    isTauriMock.mockReturnValue(true);
    saveMock.mockResolvedValue(null);
    const result = await pickReportSavePath("report.pdf");
    expect(result).toEqual({ ok: false, reason: "cancelled" });
  });

  it("offers all four real export formats as dialog filters", async () => {
    isTauriMock.mockReturnValue(true);
    saveMock.mockResolvedValue("/home/user/reports/report.pdf");
    await pickReportSavePath("report.pdf");

    expect(saveMock).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultPath: "report.pdf",
        filters: [
          { name: "HTML", extensions: ["html"] },
          { name: "PDF", extensions: ["pdf"] },
          { name: "JSON", extensions: ["json"] },
          { name: "MARKDOWN", extensions: ["md"] },
        ],
      }),
    );
  });

  it("derives the ExportFormat from the chosen path's real extension", async () => {
    isTauriMock.mockReturnValue(true);

    saveMock.mockResolvedValueOnce("/home/user/reports/report.pdf");
    expect(await pickReportSavePath("report.pdf")).toEqual({
      ok: true,
      path: "/home/user/reports/report.pdf",
      format: "pdf",
    });

    saveMock.mockResolvedValueOnce("/home/user/reports/report.md");
    expect(await pickReportSavePath("report.md")).toEqual({
      ok: true,
      path: "/home/user/reports/report.md",
      format: "markdown",
    });

    saveMock.mockResolvedValueOnce("C:\\Users\\user\\reports\\report.JSON");
    expect(await pickReportSavePath("report.json")).toEqual({
      ok: true,
      path: "C:\\Users\\user\\reports\\report.JSON",
      format: "json",
    });
  });

  it("reports no-extension when the chosen path has no recognizable extension", async () => {
    isTauriMock.mockReturnValue(true);
    saveMock.mockResolvedValue("/home/user/reports/report");

    const result = await pickReportSavePath("report");

    expect(result).toEqual({ ok: false, reason: "no-extension" });
  });

  it("reports dialog-failed, not a throw, when the dialog itself rejects", async () => {
    isTauriMock.mockReturnValue(true);
    saveMock.mockRejectedValue(new Error("dialog plugin unavailable"));

    const result = await pickReportSavePath("report.pdf");

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("expected a failure result");
    expect(result.reason).toBe("dialog-failed");
  });
});
