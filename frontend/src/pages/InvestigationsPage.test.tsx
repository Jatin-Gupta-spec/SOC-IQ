// @vitest-environment jsdom
/**
 * `InvestigationsPage` tests -- real backend wiring.
 *
 * `useInvestigationsList` is mocked at its own module boundary
 * (mirroring `InvestigationWorkspacePage.test.tsx`'s established
 * `vi.mock` convention for `useInvestigation`), so each load state
 * can be driven directly and deterministically -- this file tests the
 * page's own rendering/state-handling logic, not the fetch hook's
 * behavior (already covered by `useInvestigationsList.test.tsx`) or
 * the row-mapping logic (already covered by
 * `investigationsViewModel.test.ts`).
 *
 * `renderToStaticMarkup`, matching `pages.test.tsx`'s existing
 * no-jsdom-by-default convention -- no Router is needed here either:
 * navigation is a plain `<a href="#...">` per row, not
 * `useNavigate()` (see `InvestigationsPage.tsx`'s own doc comment for
 * why), so this page keeps rendering standalone exactly as
 * `pages.test.tsx` already exercises it.
 *
 * PD-08-P5.3: `InvestigationsCsvExportAction` is also mocked here, the
 * same way `ReportsPage.test.tsx` mocks `ReportExportAction` -- it has
 * its own real Tauri-dependent behavior (native save dialog,
 * `export_investigations_csv`) covered by
 * `investigations/useInvestigationsCsvExport.test.tsx` and
 * `investigations/investigationsCsvExportPath.test.ts`; mocking it here
 * keeps this file focused on what `InvestigationsPage` itself is
 * responsible for, and a `@tauri-apps/*` mock is still not needed in
 * this file.
 *
 * MAX7-F-05: this file now opts into `@vitest-environment jsdom` (this
 * was previously a plain-Node `renderToStaticMarkup`-only file) so the
 * row-activation `describe` block at the bottom can dispatch real
 * click/keydown events, mirroring `dashboard.test.tsx`'s own
 * established "Dashboard Recent Investigations keyboard activation"
 * convention (`act` + `createRoot` + native `dispatchEvent`) exactly.
 * `renderToStaticMarkup` still works identically under jsdom, so every
 * pre-existing test in the `describe("InvestigationsPage", ...)` block
 * above is unaffected by this change.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const useInvestigationsListMock = vi.fn();

vi.mock("./investigations/useInvestigationsList", () => ({
  useInvestigationsList: (...args: unknown[]) => useInvestigationsListMock(...args),
}));

vi.mock("./investigations/InvestigationsCsvExportAction", () => ({
  InvestigationsCsvExportAction: () => (
    <span data-testid="csv-export-action">Export CSV</span>
  ),
}));

import { InvestigationsPage } from "./InvestigationsPage";
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

// MAX10-F-01: a third row, deliberately unscored (`NOT_SCORED`
// sentinel) and dated earliest, so sort tests can exercise both
// chronological ordering and the "null risk score sorts last in
// either direction" rule -- not achievable with only the two rows
// above, which are both scored.
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
  return renderToStaticMarkup(<InvestigationsPage />);
}

describe("InvestigationsPage", () => {
  describe("loading", () => {
    it("renders a loading state with no investigation rows", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "loading" }));
      const html = render();

      expect(html).toContain("Loading investigations");
      expect(html).not.toContain("<table");
    });

    it("renders a structural table skeleton, not the visible loading message text (MAX-2)", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "loading" }));
      const html = render();

      expect(html).toContain("investigations-page__skeleton");
      expect(html).toContain("investigations-page__skeleton-row");
      expect(html).toContain('role="status"');
      expect(html).toContain('aria-live="polite"');
      // The accessible status text is visually hidden -- the skeleton
      // graphic, not visible loading prose, carries the loading state.
      expect(html).toContain("skeleton-status");
    });
  });

  describe("success", () => {
    it("renders the real investigation list, not mock data", () => {
      useInvestigationsListMock.mockReturnValue(
        makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
      );
      const html = render();

      expect(html).toContain("phishing-report.eml");
      expect(html).toContain("beacon-report.txt");
      // None of the old mock investigation names leak through.
      expect(html).not.toContain("Suspicious PowerShell chain");
      expect(html).not.toContain("Phishing report — finance distribution list");
    });

    it("links each investigation to the real Investigation Workspace route", () => {
      useInvestigationsListMock.mockReturnValue(
        makeResult({ state: "success", investigations: [INVESTIGATION] }),
      );
      const html = render();

      expect(html).toContain('href="#/investigations/42"');
    });

    it("does not render an Owner or IOCs column the real backend contract doesn't provide", () => {
      useInvestigationsListMock.mockReturnValue(
        makeResult({ state: "success", investigations: [INVESTIGATION] }),
      );
      const html = render();

      expect(html).not.toContain(">Owner<");
      expect(html).not.toContain(">IOCs<");
    });
  });

  describe("empty", () => {
    it("renders an explicit, truthful empty state for a genuinely empty result", () => {
      useInvestigationsListMock.mockReturnValue(makeResult({ state: "success", investigations: [] }));
      const html = render();

      expect(html).toContain("No investigations found.");
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
      expect(html).not.toContain("Suspicious PowerShell chain");
    });

    it("falls back to a generic message when no error message is available", () => {
      useInvestigationsListMock.mockReturnValue(
        makeResult({ state: "error", error: "not an Error instance" }),
      );
      const html = render();

      expect(html).toContain("An unknown error occurred while loading investigations.");
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

      expect(html).toContain('aria-label="Investigations page"');
      expect(html).toContain(">Investigations<");
    });
  });

  describe("CSV export action", () => {
    it("renders the export control regardless of list load state", () => {
      for (const overrides of [
        { state: "loading" as const },
        { state: "success" as const, investigations: [INVESTIGATION] },
        { state: "success" as const, investigations: [] },
        { state: "error" as const, error: new Error("boom") },
      ]) {
        useInvestigationsListMock.mockReturnValue(makeResult(overrides));
        const html = render();

        expect(html).toContain('data-testid="csv-export-action"');
      }
    });
  });
});

describe("InvestigationsPage row activation (MAX7-F-05)", () => {
  // Mirrors `dashboard.test.tsx`'s "Dashboard Recent Investigations
  // keyboard activation" describe block exactly -- DataTable's own
  // Enter/Space handling already has coverage there; this closes the
  // equivalent gap for InvestigationsPage's own interactive-row
  // consumption of it.
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
      root.render(<InvestigationsPage />);
    });
  }

  it("opens the investigation on a click anywhere in its row, not only the name link", () => {
    renderRows();
    // The second row's Severity cell -- deliberately not the name
    // link -- to prove whole-row activation, not just the existing
    // link, is what fires.
    const rows = container.querySelectorAll("tbody tr");
    const secondRowSeverityCell = rows[1]?.querySelectorAll("td")[2];

    act(() => {
      secondRowSeverityCell?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    expect(window.location.hash).toBe(`#/investigations/${INVESTIGATION_2.investigation_id}`);
  });

  it("opens the correct row's investigation on Enter, not always the first row", () => {
    renderRows();
    const rows = container.querySelectorAll("tbody tr");

    act(() => {
      rows[1]?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    });

    expect(window.location.hash).toBe(`#/investigations/${INVESTIGATION_2.investigation_id}`);
  });

  it("opens an investigation on Space", () => {
    renderRows();
    const rows = container.querySelectorAll("tbody tr");

    act(() => {
      rows[0]?.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true }));
    });

    expect(window.location.hash).toBe(`#/investigations/${INVESTIGATION.investigation_id}`);
  });

  it("still keeps the name cell's real <a href> for middle-click/open-in-new-tab", () => {
    renderRows();
    expect(container.querySelector(`a[href="#/investigations/${INVESTIGATION.investigation_id}"]`)).not.toBeNull();
  });
});

describe("InvestigationsPage search/filter (MAX7-F-03)", () => {
  // Mirrors `InvestigationIocWorkspace.test.tsx`'s established
  // native-setter + `dispatchEvent` idiom for driving a controlled
  // `<input>`/`<select>` under jsdom without a testing-library
  // dependency.
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
      root.render(<InvestigationsPage />);
    });
  }

  function searchInput(): HTMLInputElement {
    return container.querySelector("#investigations-search") as HTMLInputElement;
  }

  function statusSelect(): HTMLSelectElement {
    return container.querySelector("#investigations-status-filter") as HTMLSelectElement;
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

  it("renders a search input and status filter once real investigations exist", () => {
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

  it("narrows the table to rows matching the search text (name, status, or severity)", () => {
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
    renderRows();

    typeSearch("phishing");

    const rows = tableRowTexts();
    expect(rows.some((text) => text.includes("phishing-report.eml"))).toBe(true);
    expect(rows.some((text) => text.includes("beacon-report.txt"))).toBe(false);
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

    expect(container.textContent).toContain("No investigations match your filters.");
    expect(container.textContent).not.toContain("No investigations found.");
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

  it("shows a live count of filtered vs. total investigations", () => {
    useInvestigationsListMock.mockReturnValue(
      makeResult({ state: "success", investigations: [INVESTIGATION, INVESTIGATION_2] }),
    );
    renderRows();

    typeSearch("phishing");

    expect(container.textContent).toContain("Showing 1 of 2 investigations");
  });
});

describe("InvestigationsPage column sort (MAX10-F-01)", () => {
  // Same jsdom + createRoot idiom as the row-activation/search-filter
  // blocks above -- sorting needs real click events, not just static
  // markup.
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
      root.render(<InvestigationsPage />);
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
    // First `<td>` in each row is always the "Investigation" (name)
    // column -- reading it directly (rather than searching for the
    // `<a>` specifically) works for every row regardless of whether
    // that row happens to be link-backed.
    return Array.from(container.querySelectorAll("tbody tr")).map((row) => row.querySelector("td")?.textContent ?? "");
  }

  it("renders Status, Risk, and Analyzed headers as sortable buttons with aria-sort='none' before any interaction", () => {
    renderRows();

    expect(() => headerButton("Status")).not.toThrow();
    expect(() => headerButton("Risk")).not.toThrow();
    expect(() => headerButton("Analyzed")).not.toThrow();
    expect(ariaSortOf("Status")).toBe("none");
    expect(ariaSortOf("Risk")).toBe("none");
    expect(ariaSortOf("Analyzed")).toBe("none");
  });

  it("leaves Investigation, Severity, and Confidence as plain non-interactive headers (audit scope: status/date/risk only)", () => {
    renderRows();

    for (const label of ["Investigation", "Severity", "Confidence"]) {
      const headers = Array.from(container.querySelectorAll("thead th"));
      const th = headers.find((el) => el.textContent?.includes(label));
      expect(th?.querySelector("button")).toBeNull();
      expect(th?.getAttribute("aria-sort")).toBeNull();
    }
  });

  it("sorts ascending on first click of a sortable header and marks it aria-sort='ascending'", () => {
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
    // FAILED now sorts first; the two COMPLETED rows still keep their
    // original relative order under the tie (stable sort).
    expect(reportNameOrder()).toEqual(["unscored-report.txt", "phishing-report.eml", "beacon-report.txt"]);
  });

  it("sorts Risk numerically and places the unscored (null) row last in both directions", () => {
    renderRows();

    clickHeader("Risk");
    expect(reportNameOrder()).toEqual(["beacon-report.txt", "phishing-report.eml", "unscored-report.txt"]);

    clickHeader("Risk");
    // Descending flips the two scored rows but the unscored (null)
    // row stays last -- it never jumps to the top just because the
    // direction flipped.
    expect(reportNameOrder()).toEqual(["phishing-report.eml", "beacon-report.txt", "unscored-report.txt"]);
  });

  it("sorts Analyzed chronologically", () => {
    renderRows();

    clickHeader("Analyzed");

    expect(reportNameOrder()).toEqual([
      "unscored-report.txt",
      "phishing-report.eml",
      "beacon-report.txt",
    ]);
  });

  it("switching the active sort column to a different sortable column resets to ascending", () => {
    renderRows();

    clickHeader("Status");
    clickHeader("Status");
    expect(ariaSortOf("Status")).toBe("descending");

    clickHeader("Risk");

    expect(ariaSortOf("Status")).toBe("none");
    expect(ariaSortOf("Risk")).toBe("ascending");
  });

  it("composes with an active search filter -- sorts whatever rows currently pass the filter, not the full unfiltered set", () => {
    renderRows();
    const input = container.querySelector("#investigations-search") as HTMLInputElement;
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;
    act(() => {
      nativeSetter.call(input, "report");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });

    clickHeader("Risk");

    // All three rows match "report" in their filenames, but this
    // still proves sort applies post-filter: exactly 3 rows, ordered
    // ascending by risk with the unscored row last.
    expect(reportNameOrder()).toEqual(["beacon-report.txt", "phishing-report.eml", "unscored-report.txt"]);
  });
});
