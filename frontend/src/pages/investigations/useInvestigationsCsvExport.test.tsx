// @vitest-environment jsdom
/**
 * Live-DOM tests for `useInvestigationsCsvExport` -- mirrors
 * `reports/useReportExport.test.tsx`'s established `runCommand`-mocking
 * + `act`/`createRoot` conventions.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runCommandMock = vi.fn();
const pickInvestigationsCsvSavePathMock = vi.fn();

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>(
    "../../shared/api/client",
  );
  return {
    ...actual,
    runCommand: (...args: unknown[]) => runCommandMock(...args),
  };
});

vi.mock("./investigationsCsvExportPath", () => ({
  pickInvestigationsCsvSavePath: (...args: unknown[]) =>
    pickInvestigationsCsvSavePathMock(...args),
}));

import { CommandFailedError } from "../../shared/api/client";
import { useInvestigationsCsvExport } from "./useInvestigationsCsvExport";
import type { UseInvestigationsCsvExportResult } from "./useInvestigationsCsvExport";

let container: HTMLDivElement;
let root: Root;
let latestResult: UseInvestigationsCsvExportResult;

function Probe() {
  latestResult = useInvestigationsCsvExport();
  return <div data-testid="state">{latestResult.state.status}</div>;
}

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  runCommandMock.mockReset();
  pickInvestigationsCsvSavePathMock.mockReset();
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
    expect(pickInvestigationsCsvSavePathMock).not.toHaveBeenCalled();
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("cancelled save dialog", () => {
  it("returns to idle without calling export_investigations_csv", async () => {
    render();
    pickInvestigationsCsvSavePathMock.mockResolvedValue({ ok: false, reason: "cancelled" });

    await act(async () => {
      latestResult.runExport();
      await flush();
    });

    expect(latestResult.state).toEqual({ status: "idle" });
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("unsupported environment", () => {
  it("surfaces an honest error instead of calling export_investigations_csv", async () => {
    render();
    pickInvestigationsCsvSavePathMock.mockResolvedValue({ ok: false, reason: "unsupported" });

    await act(async () => {
      latestResult.runExport();
      await flush();
    });

    expect(latestResult.state).toEqual({
      status: "error",
      message: "Exporting investigation history requires the desktop app.",
    });
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("default file name", () => {
  it("suggests investigations.csv when no override is given", async () => {
    render();
    pickInvestigationsCsvSavePathMock.mockResolvedValue({ ok: false, reason: "cancelled" });

    await act(async () => {
      latestResult.runExport();
      await flush();
    });

    expect(pickInvestigationsCsvSavePathMock).toHaveBeenCalledWith("investigations.csv");
  });
});

describe("duplicate submissions", () => {
  it("keeps the exporting state on a second runExport call while already exporting", async () => {
    render();
    let resolvePick!: (value: { ok: true; path: string }) => void;
    pickInvestigationsCsvSavePathMock.mockReturnValue(
      new Promise((resolve) => {
        resolvePick = resolve;
      }),
    );
    runCommandMock.mockResolvedValue({
      output_path: "/home/user/exports/investigations.csv",
      row_count: 1,
    });

    act(() => {
      latestResult.runExport();
    });
    expect(latestResult.state).toEqual({ status: "exporting" });

    // A second call while already exporting must not regress the
    // state away from "exporting" -- this is the state-level half of
    // Part 6's "prevent accidental duplicate submissions"; the other
    // half (never letting the user *trigger* a second call at all) is
    // enforced by `InvestigationsCsvExportAction`'s `disabled` button
    // while `status === "exporting"`, mirroring
    // `ReportExportAction`/`useReportExport`'s identical division of
    // responsibility.
    act(() => {
      latestResult.runExport();
    });
    expect(latestResult.state).toEqual({ status: "exporting" });

    await act(async () => {
      resolvePick({ ok: true, path: "/home/user/exports/investigations.csv" });
      await flush();
    });
  });
});

describe("successful export", () => {
  it("calls the real export_investigations_csv command with the picked path and no search", async () => {
    render();
    pickInvestigationsCsvSavePathMock.mockResolvedValue({
      ok: true,
      path: "/home/user/exports/investigations.csv",
    });
    runCommandMock.mockResolvedValue({
      output_path: "/home/user/exports/investigations.csv",
      row_count: 42,
    });

    await act(async () => {
      latestResult.runExport();
      await flush();
    });

    expect(runCommandMock).toHaveBeenCalledWith("export_investigations_csv", {
      output_path: "/home/user/exports/investigations.csv",
    });
    expect(latestResult.state).toEqual({
      status: "success",
      outputPath: "/home/user/exports/investigations.csv",
      rowCount: 42,
    });
  });

  it("handles a valid empty export as a success, not an error", async () => {
    render();
    pickInvestigationsCsvSavePathMock.mockResolvedValue({
      ok: true,
      path: "/home/user/exports/investigations.csv",
    });
    runCommandMock.mockResolvedValue({
      output_path: "/home/user/exports/investigations.csv",
      row_count: 0,
    });

    await act(async () => {
      latestResult.runExport();
      await flush();
    });

    expect(latestResult.state).toEqual({
      status: "success",
      outputPath: "/home/user/exports/investigations.csv",
      rowCount: 0,
    });
  });
});

describe("failed export", () => {
  it("preserves the real backend error rather than a generic message", async () => {
    render();
    pickInvestigationsCsvSavePathMock.mockResolvedValue({
      ok: true,
      path: "/home/user/exports/investigations.csv",
    });
    const failure = new CommandFailedError(
      "export_investigations_csv",
      "SOME_CODE",
      "boom: export failed",
    );
    runCommandMock.mockRejectedValue(failure);

    await act(async () => {
      latestResult.runExport();
      await flush();
    });

    expect(latestResult.state).toEqual({ status: "error", message: "boom: export failed" });
  });

  it("can be re-run after an error", async () => {
    render();
    pickInvestigationsCsvSavePathMock.mockResolvedValue({
      ok: true,
      path: "/home/user/exports/investigations.csv",
    });
    runCommandMock.mockRejectedValueOnce(new Error("network down"));
    runCommandMock.mockResolvedValueOnce({
      output_path: "/home/user/exports/investigations.csv",
      row_count: 3,
    });

    await act(async () => {
      latestResult.runExport();
      await flush();
    });
    expect(latestResult.state).toEqual({ status: "error", message: "network down" });

    await act(async () => {
      latestResult.runExport();
      await flush();
    });
    expect(latestResult.state).toEqual({
      status: "success",
      outputPath: "/home/user/exports/investigations.csv",
      rowCount: 3,
    });
  });
});
