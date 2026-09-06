/**
 * `computeSettingsDirty` tests -- SOC-IQ MAX-18 Phase 2A-1
 * (MAX18-F-01). Pure function, no DOM/React needed.
 */

import { describe, expect, it } from "vitest";
import { computeSettingsDirty } from "./settingsDirty";

const CLEAN = {
  themeDirty: false,
  exportDirectoryDirty: false,
  virustotalKeyDirty: false,
};

describe("computeSettingsDirty", () => {
  it("is false when no control is dirty", () => {
    expect(computeSettingsDirty(CLEAN)).toBe(false);
  });

  it("is true when only themeDirty is true", () => {
    expect(computeSettingsDirty({ ...CLEAN, themeDirty: true })).toBe(true);
  });

  it("is true when only exportDirectoryDirty is true", () => {
    expect(computeSettingsDirty({ ...CLEAN, exportDirectoryDirty: true })).toBe(true);
  });

  it("is true when only virustotalKeyDirty is true", () => {
    expect(computeSettingsDirty({ ...CLEAN, virustotalKeyDirty: true })).toBe(true);
  });

  it("is true when multiple controls are dirty simultaneously", () => {
    expect(
      computeSettingsDirty({
        themeDirty: true,
        exportDirectoryDirty: true,
        virustotalKeyDirty: false,
      }),
    ).toBe(true);
  });

  it("is true when every control is dirty", () => {
    expect(
      computeSettingsDirty({
        themeDirty: true,
        exportDirectoryDirty: true,
        virustotalKeyDirty: true,
      }),
    ).toBe(true);
  });

  it("returns to false only once every flag returns to false", () => {
    const allDirty = { themeDirty: true, exportDirectoryDirty: true, virustotalKeyDirty: true };
    expect(computeSettingsDirty({ ...allDirty, themeDirty: false })).toBe(true);
    expect(computeSettingsDirty({ ...allDirty, themeDirty: false, exportDirectoryDirty: false })).toBe(
      true,
    );
    expect(
      computeSettingsDirty({
        themeDirty: false,
        exportDirectoryDirty: false,
        virustotalKeyDirty: false,
      }),
    ).toBe(false);
  });
});
