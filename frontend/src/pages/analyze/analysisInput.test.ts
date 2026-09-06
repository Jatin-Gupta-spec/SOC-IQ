import { describe, expect, it } from "vitest";

import {
  describeRejection,
  toAnalysisInput,
  toNativeAnalysisInput,
  validateAnalysisInput,
} from "./analysisInput";

function file(contents: BlobPart[], name: string, type = "text/plain"): File {
  return new File(contents, name, { type });
}

describe("toAnalysisInput", () => {
  it("captures the file's name and size", () => {
    const f = file(["hello world"], "report.txt");
    const input = toAnalysisInput(f);
    expect(input.fileName).toBe("report.txt");
    expect(input.fileSize).toBe(f.size);
    expect(input.file).toBe(f);
  });

  it("never sets sourcePath for a browser-selected file", () => {
    const input = toAnalysisInput(file(["hello"], "report.txt"));
    expect(input.sourcePath).toBeUndefined();
  });
});

describe("toNativeAnalysisInput", () => {
  it("captures the file's name/size plus the real absolute sourcePath", () => {
    const f = file(["hello world"], "report.txt");
    const input = toNativeAnalysisInput(f, "/home/user/reports/report.txt");
    expect(input.fileName).toBe("report.txt");
    expect(input.fileSize).toBe(f.size);
    expect(input.file).toBe(f);
    expect(input.sourcePath).toBe("/home/user/reports/report.txt");
  });
});

describe("validateAnalysisInput", () => {
  it("rejects an empty file", async () => {
    const input = toAnalysisInput(file([], "empty.txt"));
    const result = await validateAnalysisInput(input);
    expect(result).toEqual({ ok: false, rejection: { reason: "empty" } });
  });

  it("accepts a non-empty UTF-8 text file", async () => {
    const input = toAnalysisInput(file(["suspicious.exe contacted 10.0.0.1"], "report.txt"));
    const result = await validateAnalysisInput(input);
    expect(result).toEqual({ ok: true });
  });

  it("rejects a file that doesn't decode as UTF-8", async () => {
    // 0xFF 0xFE alone is not valid UTF-8.
    const invalidUtf8 = new Uint8Array([0xff, 0xfe, 0x00, 0x00]);
    const input = toAnalysisInput(file([invalidUtf8], "binary.exe"));
    const result = await validateAnalysisInput(input);
    expect(result).toEqual({
      ok: false,
      rejection: { reason: "unreadable-encoding" },
    });
  });

  it("does not reject based on file extension alone", async () => {
    // No extension allowlist exists on the backend (see the module
    // doc comment) — a `.exe`-named file with valid UTF-8 text
    // content is valid input.
    const input = toAnalysisInput(file(["plain text content"], "notes.exe"));
    const result = await validateAnalysisInput(input);
    expect(result).toEqual({ ok: true });
  });
});

describe("describeRejection", () => {
  it("gives a human-readable, non-technical message for every reason", () => {
    expect(describeRejection({ reason: "empty" })).not.toMatch(/error|exception/i);
    expect(describeRejection({ reason: "unreadable-encoding" })).not.toMatch(
      /error|exception/i,
    );
    expect(
      describeRejection({ reason: "read-failed", cause: new Error("boom") }),
    ).not.toMatch(/boom|Error:/);
  });
});
