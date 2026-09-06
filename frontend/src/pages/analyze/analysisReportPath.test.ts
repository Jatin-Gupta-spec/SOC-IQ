import { describe, expect, it } from "vitest";

import { toAnalysisInput, toNativeAnalysisInput } from "./analysisInput";
import { describeReportPathBlockedReason, resolveReportPath } from "./analysisReportPath";

describe("resolveReportPath", () => {
  it("is blocked for a plain browser-selected file (no sourcePath)", () => {
    const input = toAnalysisInput(new File(["hello"], "report.txt", { type: "text/plain" }));
    const resolution = resolveReportPath(input);
    expect(resolution).toEqual({ ok: false, reason: "no-filesystem-capability" });
  });

  it("resolves ok with the real absolute path for a native (POSIX) selection", () => {
    const input = toNativeAnalysisInput(
      new File(["hello"], "report.txt"),
      "/home/user/reports/report.txt",
    );
    const resolution = resolveReportPath(input);
    expect(resolution).toEqual({ ok: true, reportPath: "/home/user/reports/report.txt" });
  });

  it("resolves ok with the real absolute path for a native (Windows drive) selection", () => {
    const input = toNativeAnalysisInput(
      new File(["hello"], "report.txt"),
      "C:\\Users\\user\\reports\\report.txt",
    );
    const resolution = resolveReportPath(input);
    expect(resolution).toEqual({ ok: true, reportPath: "C:\\Users\\user\\reports\\report.txt" });
  });

  it("resolves ok with the real absolute path for a native (Windows UNC) selection", () => {
    const input = toNativeAnalysisInput(
      new File(["hello"], "report.txt"),
      "\\\\server\\share\\report.txt",
    );
    const resolution = resolveReportPath(input);
    expect(resolution).toEqual({ ok: true, reportPath: "\\\\server\\share\\report.txt" });
  });

  it("rejects an empty sourcePath rather than trusting it", () => {
    const input = toNativeAnalysisInput(new File(["hello"], "report.txt"), "");
    const resolution = resolveReportPath(input);
    expect(resolution).toEqual({ ok: false, reason: "no-filesystem-capability" });
  });

  it("rejects a sourcePath containing an embedded NUL byte", () => {
    const input = toNativeAnalysisInput(
      new File(["hello"], "report.txt"),
      "/home/user/report.txt\u0000.exe",
    );
    const resolution = resolveReportPath(input);
    expect(resolution).toEqual({ ok: false, reason: "no-filesystem-capability" });
  });

  it("rejects a relative sourcePath rather than trusting it", () => {
    const input = toNativeAnalysisInput(new File(["hello"], "report.txt"), "reports/report.txt");
    const resolution = resolveReportPath(input);
    expect(resolution).toEqual({ ok: false, reason: "no-filesystem-capability" });
  });
});

describe("describeReportPathBlockedReason", () => {
  it("returns a non-empty, honest explanation pointing at the native picker", () => {
    const message = describeReportPathBlockedReason("no-filesystem-capability");
    expect(message.length).toBeGreaterThan(0);
    expect(message).toContain("Browse for Analysis");
  });
});
