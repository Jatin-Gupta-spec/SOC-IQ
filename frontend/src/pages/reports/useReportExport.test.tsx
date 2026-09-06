// @vitest-environment jsdom
/**
 * Live-DOM tests for `useReportExport` -- mirrors
 * `pages/investigations/useInvestigationsList.test.tsx`'s established
 * `runCommand`-mocking + `act`/`createRoot` conventions.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runCommandMock = vi.fn();
const pickReportSavePathMock = vi.fn();

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>("../../shared/api/client");
  return {
    ...actual,
    runCommand: (...args: unknown[]) => runCommandMock(...args),
  };
});

vi.mock("./reportExportPath", () => ({
  pickReportSavePath: (...args: unknown[]) => pickReportSavePathMock(...args),
}));

import { CommandFailedError } from "../../shared/api/client";
import { useReportExport } from "./useReportExport";
import type { UseReportExportResult } from "./useReportExport";

let container: HTMLDivElement;
let root: Root;
let latestResult: UseReportExportResult;

function Probe() {
  latestResult = useReportExport();
  return <div data-testid="state">{latestResult.state.status}</div>;
}

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  runCommandMock.mockReset();
  pickReportSavePathMock.mockReset();
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe />);
  });
}

function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("initial state", () => {
  it("starts idle and calls nothing until runExport is invoked", () => {
    render();

    expect(latestResult.state).toEqual({ status: "idle" });
    expect(pickReportSavePathMock).not.toHaveBeenCalled();
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("cancelled save dialog", () => {
  it("returns to idle without calling export_report", async () => {
    render();
    pickReportSavePathMock.mockResolvedValue({ ok: false, reason: "cancelled" });

    await act(async () => {
      latestResult.runExport(42, "phishing-report.eml");
      await flush();
    });

    expect(latestResult.state).toEqual({ status: "idle" });
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("unsupported environment", () => {
  it("surfaces an honest error instead of calling export_report", async () => {
    render();
    pickReportSavePathMock.mockResolvedValue({ ok: false, reason: "unsupported" });

    await act(async () => {
      latestResult.runExport(42, "phishing-report.eml");
      await flush();
    });

    expect(latestResult.state).toEqual({
      status: "error",
      message: "Exporting reports requires the desktop app.",
    });
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("successful export", () => {
  it("calls the real export_report command with the picked path/format and reports success", async () => {
    render();
    pickReportSavePathMock.mockResolvedValue({
      ok: true,
      path: "/home/user/reports/phishing-report.pdf",
      format: "pdf",
    });
    runCommandMock.mockResolvedValue({
      investigation_id: 42,
      export_format: "pdf",
      output_path: "/home/user/reports/phishing-report.pdf",
    });

    await act(async () => {
      latestResult.runExport(42, "phishing-report.eml");
      await flush();
    });

    expect(runCommandMock).toHaveBeenCalledWith("export_report", {
      investigation_id: 42,
      export_format: "pdf",
      output_path: "/home/user/reports/phishing-report.pdf",
    });
    expect(latestResult.state).toEqual({
      status: "success",
      outputPath: "/home/user/reports/phishing-report.pdf",
    });
  });
});

describe("failed export", () => {
  it("preserves the real backend error rather than a generic message", async () => {
    render();
    pickReportSavePathMock.mockResolvedValue({
      ok: true,
      path: "/home/user/reports/phishing-report.pdf",
      format: "pdf",
    });
    const failure = new CommandFailedError("export_report", "SOME_CODE", "boom: export failed");
    runCommandMock.mockRejectedValue(failure);

    await act(async () => {
      latestResult.runExport(42, "phishing-report.eml");
      await flush();
    });

    expect(latestResult.state).toEqual({ status: "error", message: "boom: export failed" });
  });
});
