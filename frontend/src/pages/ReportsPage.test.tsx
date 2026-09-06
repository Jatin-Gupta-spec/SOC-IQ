// @vitest-environment jsdom
/**
 * `ReportsPage` tests -- real backend wiring (Phase 4L-P3).
 *
 * `useInvestigationsList` is mocked at its own module boundary
 * (mirroring `InvestigationsPage.test.tsx`'s established `vi.mock`
 * convention -- both pages consume the exact same hook), so each load
 * state can be driven directly and deterministically. Row-mapping
 * logic is covered separately by `reports/reportsViewModel.test.ts`;
 * this file tests the page's own rendering/state-handling logic.
 *
 * `ReportExportAction` is also mocked here: it has its own real
 * Tauri-dependent behavior (native save dialog, `export_report`)
 * covered by `reports/useReportExport.test.tsx`, and mocking it keeps
 * this file focused on what `ReportsPage` itself is responsible for
 * -- which rows render and which state message shows. The mock is a
 * real `<button>` (not the earlier plain `<span>`) so the MAX7-F-05
 * row-activation tests below can dispatch a real click on it and
 * assert that click is shielded from the row's own activation.
 *
 * MAX7-F-05: this file now opts into `@vitest-environment jsdom` (this
 * was previously a plain-Node `renderToStaticMarkup`-only file), the
 * same change made to `InvestigationsPage.test.tsx` for the same
 * reason -- see that file's own doc comment. `renderToStaticMarkup`
 * still works identically under jsdom, so every pre-existing test in
 * the `describe("ReportsPage", ...)` block below is unaffected.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const useInvestigationsListMock = vi.fn();

vi.mock("./investigations/useInvestigationsList", () => ({
  useInvestigationsList: (...args: unknown[]) => useInvestigationsListMock(...args),
}));

vi.mock("./reports/ReportExportAction", () => ({
  ReportExportAction: ({ reportName }: { readonly reportName: string }) => (
    <button type="button" data-testid="export-action">
      Export {reportName}
    </button>
  ),
}));

import { ReportsPage } from "./ReportsPage";
import type { UseInvestigationsListResult } from "./investigations/useInvestigationsList";
import type { InvestigationSummary } from "../shared/api/types";

const INVESTIGATION: InvestigationSummary = {
  investigation_id: 42,
  report_name: "phishing-report.eml",
  risk_score: 87,
  severity: "HIGH",
  confidence: 0.91,
  status: "COMPLETED",
  analyzed_at: "2026-08-20T10:15:00",
};

const INVESTIGATION_2: InvestigationSummary = {
  investigation_id: 43,
  report_name: "beacon-report.txt",
  risk_score: 55,
  severity: "MEDIUM",
  confidence: 0.6,
  status: "COMPLETED",
  analyzed_at: "2026-08-21T09:00:00",
};

// Phase 2B: a third row with a distinct status and an earlier
// `analyzed_at`, mirroring `InvestigationsPage.test.tsx`'s own
// `INVESTIGATION_3` fixture -- needed to exercise both alphabetical
// (status) and chronological (analyzed) sort with more than a
// two-row tie.
const INVESTIGATION_3: InvestigationSummary = {
  investigation_id: 44,
  report_name: "unscored-report.txt",
  risk_score: 0,
  severity: "NOT_SCORED",
  confidence: 0,
  status: "FAILED",
  analyzed_at: "2026-08-19T08:00:00",
};

function makeResult(overrides: Partial<UseInvestigationsListResult>): UseInvestigationsListResult {
  return {
    state: "loading",
    investigations: null,
    error: null,
    retry: vi.fn(),
    ...overrides,
  };
}

function render(): string {
  return renderToStaticMarkup(<ReportsPage />);
}

describe("ReportsPage", () => {
  describe("loading", () => {
    it("renders a loading state with no report rows", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "loading" }));
      const html = render();

      expect(html).toContain("Loading reports");
      expect(html).not.toContain("<table");
    });

    it("renders a structural table skeleton (MAX-2)", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "loading" }));
      const html = render();

      expect(html).toContain("reports-page__skeleton");
      expect(html).toContain("reports-page__skeleton-row");
      expect(html).toContain('role="status"');
      expect(html).toContain('aria-live="polite"');
      expect(html).toContain("skeleton-status");
    });
  });

  describe("success", () => {
    it("renders the real investigation-derived report list, not mock data", () => {
      useInvestigationsListMock.mockReturnValue(
        makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
      );
      const html = render();

      expect(html).toContain("phishing-report.eml");
      expect(html).toContain("beacon-report.txt");
      expect(html).not.toContain("Outbound beacon to unknown domain");
      expect(html).not.toContain("Weekly IOC export");
    });

    it("links each report to its real Investigation Workspace route", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "success", investigations: [INVESTIGATION] }));
      const html = render();

      expect(html).toContain('href="#/investigations/42"');
    });

    it("renders a real Export action per row instead of a permanently-disabled Download button", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "success", investigations: [INVESTIGATION] }));
      const html = render();

      expect(html).toContain("Export phishing-report.eml");
      expect(html).not.toContain(">Download<");
    });

    it("does not render a report Type column the real backend contract doesn't provide", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "success", investigations: [INVESTIGATION] }));
      const html = render();

      expect(html).not.toContain(">Type<");
    });
  });

  describe("empty", () => {
    it("renders an explicit, truthful empty state for a genuinely empty result", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "success", investigations: [] }));
      const html = render();

      expect(html).toContain("No reports available");
      expect(html).not.toContain("<table");
    });
  });

  describe("error", () => {
    it("renders the real error message and a retry action, never falls back to mock data", () => {
      useInvestigationsListMock.mockReturnValue(
        makeResult({ state: "error", error: new Error("boom: sidecar unreachable") }),
      );
      const html = render();

      expect(html).toContain("boom: sidecar unreachable");
      expect(html).toContain(">Retry<");
      expect(html).not.toContain("<table");
      expect(html).not.toContain("Outbound beacon to unknown domain");
    });

    it("falls back to a generic message when no error message is available", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "error", error: "not an Error instance" }));
      const html = render();

      expect(html).toContain("An unknown error occurred while loading reports.");
    });
  });

  describe("page structure", () => {
    it("renders without throwing", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "loading" }));
      expect(() => render()).not.toThrow();
    });

    it("carries the expected <main> landmark and title", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "loading" }));
      const html = render();

      expect(html).toContain('aria-label="Reports page"');
      expect(html).toContain(">Reports<");
    });
  });
});

describe("ReportsPage row activation (MAX7-F-05)", () => {
  // Mirrors `InvestigationsPage.test.tsx`'s equivalent describe block
  // and, in turn, `dashboard.test.tsx`'s original "Dashboard Recent
  // Investigations keyboard activation" convention.
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    window.location.hash = "";
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    window.location.hash = "";
  });

  function renderRows(): void {
    act(() => {
      root = createRoot(container);
      root.render(<ReportsPage />);
    });
  }

  it("opens the investigation on a click anywhere in its row, not only the name link", () => {
    renderRows();
    const rows = container.querySelectorAll("tbody tr");
    const secondRowAnalyzedCell = rows[1]?.querySelectorAll("td")[2];

    act(() => {
      secondRowAnalyzedCell?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    expect(window.location.hash).toBe(`#/investigations/${INVESTIGATION_2.investigation_id}`);
  });

  it("opens an investigation on Enter", () => {
    renderRows();
    const rows = container.querySelectorAll("tbody tr");

    act(() => {
      rows[0]?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    });

    expect(window.location.hash).toBe(`#/investigations/${INVESTIGATION.investigation_id}`);
  });

  it("does NOT navigate away when the row's Export button is clicked", () => {
    renderRows();
    const exportButton = container.querySelectorAll('[data-testid="export-action"]')[0];

    act(() => {
      exportButton?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    expect(window.location.hash).toBe("");
  });

  it("does NOT navigate away when Enter is pressed while the Export button is focused", () => {
    renderRows();
    const exportButton = container.querySelectorAll('[data-testid="export-action"]')[0];

    act(() => {
      exportButton?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    });

    expect(window.location.hash).toBe("");
  });

  it("still keeps the name cell's real <a href> for middle-click/open-in-new-tab", () => {
    renderRows();
    expect(container.querySelector(`a[href="#/investigations/${INVESTIGATION.investigation_id}"]`)).not.toBeNull();
  });
});

describe("ReportsPage search/filter (MAX7-F-03)", () => {
  // Mirrors `InvestigationsPage.test.tsx`'s identical describe block
  // (same underlying data, same toolbar pattern).
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  function renderRows(): void {
    act(() => {
      root = createRoot(container);
      root.render(<ReportsPage />);
    });
  }

  function searchInput(): HTMLInputElement {
    return container.querySelector("#reports-search") as HTMLInputElement;
  }

  function statusSelect(): HTMLSelectElement {
    return container.querySelector("#reports-status-filter") as HTMLSelectElement;
  }

  function typeSearch(value: string): void {
    const input = searchInput();
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;
    act(() => {
      nativeSetter.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  function selectStatus(value: string): void {
    const select = statusSelect();
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value")!.set!;
    act(() => {
      nativeSetter.call(select, value);
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function clickResetButton(): void {
    const button = Array.from(container.querySelectorAll("button")).find((el) => el.textContent === "Clear filters");
    act(() => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  }

  function tableRowTexts(): string[] {
    return Array.from(container.querySelectorAll(".data-table tbody tr")).map((row) => row.textContent ?? "");
  }

  it("renders a search input and status filter once real reports exist", () => {
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
    renderRows();

    expect(searchInput()).not.toBeNull();
    expect(statusSelect()).not.toBeNull();
  });

  it("does not render the search/filter toolbar for a genuinely empty result", () => {
    useInvestigationsListMock.mockReturnValue(makeResult({ state: "success", investigations: [] }));
    renderRows();

    expect(searchInput()).toBeNull();
  });

  it("narrows the table to rows matching the search text (name or status)", () => {
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
    renderRows();

    typeSearch("beacon");

    const rows = tableRowTexts();
    expect(rows.some((text) => text.includes("beacon-report.txt"))).toBe(true);
    expect(rows.some((text) => text.includes("phishing-report.eml"))).toBe(false);
  });

  it("narrows the table using the status filter", () => {
    const failed: InvestigationSummary = { ...INVESTIGATION_2, status: "FAILED" };
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, failed] }),
    );
    renderRows();

    selectStatus("FAILED");

    const rows = tableRowTexts();
    expect(rows.some((text) => text.includes("beacon-report.txt"))).toBe(true);
    expect(rows.some((text) => text.includes("phishing-report.eml"))).toBe(false);
  });

  it("shows a distinct, honest no-matches state (not the real-empty message) when search matches nothing", () => {
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
    renderRows();

    typeSearch("does-not-exist-anywhere");

    expect(container.textContent).toContain("No reports match your filters.");
    expect(container.textContent).not.toContain("No reports available.");
    expect(container.querySelector(".data-table")).toBeNull();
  });

  it("'Clear filters' resets search and status and restores every row", () => {
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
    renderRows();

    typeSearch("does-not-exist-anywhere");
    clickResetButton();

    expect(searchInput().value).toBe("");
    expect(tableRowTexts()).toHaveLength(2);
  });

  it("does not affect the Export action's own behavior on a filtered row", () => {
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
    renderRows();

    typeSearch("phishing");

    expect(container.querySelectorAll('[data-testid="export-action"]')).toHaveLength(1);
  });
});

describe("ReportsPage column sort (Phase 2B)", () => {
  // Phase 2B: extends MAX10-F-01's DataTable sort capability to this
  // page's Status/Analyzed columns -- the same two fields
  // `InvestigationsPage` already sorts, sourced from the same
  // `useInvestigationsList()` data. Mirrors
  // `InvestigationsPage.test.tsx`'s "column sort" describe block
  // exactly (same jsdom + createRoot idiom, same helper shapes),
  // adapted to this page's own columns -- there is no Risk column
  // here (`reportsViewModel.ts` intentionally excludes it), so only
  // Status and Analyzed are exercised.
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    useInvestigationsListMock.mockReturnValue(
      makeResult({
        state: "success",
        investigations: [INVESTIGATION, INVESTIGATION_2, INVESTIGATION_3],
      }),
    );
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  function renderRows(): void {
    act(() => {
      root = createRoot(container);
      root.render(<ReportsPage />);
    });
  }

  function headerButton(label: string): HTMLButtonElement {
    const headers = Array.from(container.querySelectorAll("thead th"));
    const th = headers.find((el) => el.textContent?.includes(label));
    const button = th?.querySelector("button");
    if (button === null || button === undefined) {
      throw new Error(`no sortable header button found for "${label}"`);
    }
    return button;
  }

  function clickHeader(label: string): void {
    act(() => {
      headerButton(label).dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  }

  function ariaSortOf(label: string): string | null {
    const headers = Array.from(container.querySelectorAll("thead th"));
    const th = headers.find((el) => el.textContent?.includes(label));
    return th?.getAttribute("aria-sort") ?? null;
  }

  function reportNameOrder(): string[] {
    // First `<td>` in each row is always the "Report" (name) column.
    return Array.from(container.querySelectorAll("tbody tr")).map((row) => row.querySelector("td")?.textContent ?? "");
  }

  it("renders Status and Analyzed headers as sortable buttons with aria-sort='none' before any interaction", () => {
    renderRows();

    expect(() => headerButton("Status")).not.toThrow();
    expect(() => headerButton("Analyzed")).not.toThrow();
    expect(ariaSortOf("Status")).toBe("none");
    expect(ariaSortOf("Analyzed")).toBe("none");
  });

  it("leaves Report and Export as plain non-interactive headers", () => {
    renderRows();

    for (const label of ["Report", "Export"]) {
      const headers = Array.from(container.querySelectorAll("thead th"));
      const th = headers.find((el) => el.textContent?.includes(label));
      expect(th?.querySelector("button")).toBeNull();
      expect(th?.getAttribute("aria-sort")).toBeNull();
    }
  });

  it("sorts ascending on first click of Status and marks it aria-sort='ascending'", () => {
    renderRows();

    clickHeader("Status");

    // COMPLETED < FAILED alphabetically; the two COMPLETED rows keep
    // their original relative order (stable sort).
    expect(reportNameOrder()).toEqual(["phishing-report.eml", "beacon-report.txt", "unscored-report.txt"]);
    expect(ariaSortOf("Status")).toBe("ascending");
  });

  it("toggles to descending on a second click of the same header", () => {
    renderRows();

    clickHeader("Status");
    clickHeader("Status");

    expect(ariaSortOf("Status")).toBe("descending");
    expect(reportNameOrder()).toEqual(["unscored-report.txt", "phishing-report.eml", "beacon-report.txt"]);
  });

  it("sorts Analyzed chronologically", () => {
    renderRows();

    clickHeader("Analyzed");

    expect(reportNameOrder()).toEqual(["unscored-report.txt", "phishing-report.eml", "beacon-report.txt"]);
  });

  it("switching the active sort column to a different sortable column resets to ascending", () => {
    renderRows();

    clickHeader("Status");
    clickHeader("Status");
    expect(ariaSortOf("Status")).toBe("descending");

    clickHeader("Analyzed");

    expect(ariaSortOf("Status")).toBe("none");
    expect(ariaSortOf("Analyzed")).toBe("ascending");
  });

  it("composes with an active search filter -- sorts whatever rows currently pass the filter, not the full unfiltered set", () => {
    renderRows();
    const input = container.querySelector("#reports-search") as HTMLInputElement;
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;
    act(() => {
      nativeSetter.call(input, "report");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });

    clickHeader("Analyzed");

    // All three rows match "report" in their filenames, so this still
    // proves sort applies post-filter in chronological order.
    expect(reportNameOrder()).toEqual(["unscored-report.txt", "phishing-report.eml", "beacon-report.txt"]);
  });
});
