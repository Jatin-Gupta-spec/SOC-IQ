/**
 * Tests for `investigationsCsvExportPath.ts` -- mirrors
 * `reports/reportExportPath.test.ts`'s established mocking convention
 * for `@tauri-apps/plugin-dialog` / `@tauri-apps/api/core`.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

const saveMock = vi.fn();
const isTauriMock = vi.fn();

vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: (...args: unknown[]) => saveMock(...args),
}));

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => isTauriMock(),
}));

import {
  isInvestigationsCsvSaveSupported,
  pickInvestigationsCsvSavePath,
} from "./investigationsCsvExportPath";

afterEach(() => {
  vi.resetAllMocks();
});

describe("isInvestigationsCsvSaveSupported", () => {
  it("mirrors the Tauri runtime detection", () => {
    isTauriMock.mockReturnValue(true);
    expect(isInvestigationsCsvSaveSupported()).toBe(true);

    isTauriMock.mockReturnValue(false);
    expect(isInvestigationsCsvSaveSupported()).toBe(false);
  });
});

describe("pickInvestigationsCsvSavePath", () => {
  it("is unsupported outside a Tauri runtime and never calls the dialog", async () => {
    isTauriMock.mockReturnValue(false);
    const result = await pickInvestigationsCsvSavePath("investigations.csv");
    expect(result).toEqual({ ok: false, reason: "unsupported" });
    expect(saveMock).not.toHaveBeenCalled();
  });

  it("returns cancelled when the user dismisses the dialog", async () => {
    isTauriMock.mockReturnValue(true);
    saveMock.mockResolvedValue(null);
    const result = await pickInvestigationsCsvSavePath("investigations.csv");
    expect(result).toEqual({ ok: false, reason: "cancelled" });
  });

  it("offers a single CSV filter and forwards the default file name", async () => {
    isTauriMock.mockReturnValue(true);
    saveMock.mockResolvedValue("/home/user/exports/investigations.csv");
    await pickInvestigationsCsvSavePath("investigations.csv");

    expect(saveMock).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultPath: "investigations.csv",
        filters: [{ name: "CSV", extensions: ["csv"] }],
      }),
    );
  });

  it("resolves the real absolute path returned by the dialog", async () => {
    isTauriMock.mockReturnValue(true);
    saveMock.mockResolvedValue("/home/user/exports/investigations.csv");
    const result = await pickInvestigationsCsvSavePath("investigations.csv");

    expect(result).toEqual({ ok: true, path: "/home/user/exports/investigations.csv" });
  });

  it("surfaces a dialog failure without throwing", async () => {
    isTauriMock.mockReturnValue(true);
    const cause = new Error("dialog exploded");
    saveMock.mockRejectedValue(cause);

    const result = await pickInvestigationsCsvSavePath("investigations.csv");

    expect(result).toEqual({ ok: false, reason: "dialog-failed", cause });
  });
});
