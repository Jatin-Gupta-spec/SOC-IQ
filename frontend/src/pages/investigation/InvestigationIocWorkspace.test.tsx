// @vitest-environment jsdom
/**
 * `InvestigationIocWorkspace` tests — Phase 4J-6 Part 2A, extended in
 * Part 2B with search/filter coverage (task brief §21).
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationOverviewIOC.test.tsx`) -- no `@testing-library/react`
 * is introduced. Simulated typing/selecting follows the same
 * native-setter + `dispatchEvent` idiom `CommandPalette.live.test.tsx`
 * already uses for React-controlled inputs.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InvestigationIocWorkspace } from "./InvestigationIocWorkspace";
import type { InvestigationWorkspaceData } from "./investigationWorkspaceModel";
import type { TiState } from "../../shared/api/types";

const BASE_DATA: InvestigationWorkspaceData = {
  investigationId: 7,
  reportName: "malware_report.txt",
  analyzedAt: "2026-08-26T00:00:00",
  status: "completed",
  riskScore: 82,
  severity: "high",
  confidence: 0.9,
  iocsByType: {},
  rawThreatIntelligence: {},
  correlations: [],
};

function makeData(overrides: Partial<InvestigationWorkspaceData>): InvestigationWorkspaceData {
  return { ...BASE_DATA, ...overrides };
}

function indicator(value: string): { value: string; tiState: null; typedVerdict: null } {
  return { value, tiState: null, typedVerdict: null };
}

function indicatorWithState(
  value: string,
  tiState: TiState,
): { value: string; tiState: TiState; typedVerdict: null } {
  return { value, tiState, typedVerdict: null };
}

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

function render(data: InvestigationWorkspaceData): void {
  act(() => {
    root = createRoot(container);
    root.render(<InvestigationIocWorkspace data={data} />);
  });
}

function rerender(data: InvestigationWorkspaceData): void {
  act(() => {
    root.render(<InvestigationIocWorkspace data={data} />);
  });
}

function metricValue(label: string): string | null {
  const cards = Array.from(container.querySelectorAll(".metric-card"));
  const card = cards.find((el) => el.querySelector(".metric-card__label")?.textContent === label);
  return card?.querySelector(".metric-card__value")?.textContent ?? null;
}

function tableRows(): HTMLTableRowElement[] {
  return Array.from(container.querySelectorAll(".data-table tbody tr"));
}

function searchInput(): HTMLInputElement {
  return container.querySelector("#investigation-ioc-search") as HTMLInputElement;
}

function typeSelect(): HTMLSelectElement {
  return container.querySelector("#investigation-ioc-type-filter") as HTMLSelectElement;
}

function typeSearch(value: string): void {
  const input = searchInput();
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  )!.set!;
  act(() => {
    nativeSetter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function selectType(value: string): void {
  const select = typeSelect();
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype,
    "value",
  )!.set!;
  act(() => {
    nativeSetter.call(select, value);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function clickResetButton(): void {
  const button = Array.from(container.querySelectorAll("button")).find(
    (el) => el.textContent === "Clear filters",
  );
  act(() => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

function findRowByText(text: string): HTMLTableRowElement | undefined {
  return tableRows().find((row) => row.textContent?.includes(text));
}

function clickRow(text: string): void {
  const row = findRowByText(text);
  act(() => {
    row?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

function pressKeyOnRow(text: string, key: string): void {
  const row = findRowByText(text);
  act(() => {
    row?.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
  });
}

function detailPanel(): HTMLElement | null {
  return container.querySelector(".investigation-ioc-workspace__detail");
}

function clickDetailClose(): void {
  const button = detailPanel()?.querySelector(".investigation-ioc-workspace__detail-close");
  act(() => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

const MIXED_IOCS: InvestigationWorkspaceData["iocsByType"] = {
  ipv4: [indicator("1.2.3.4"), indicator("5.6.7.8")],
  domains: [indicator("evil.example"), indicator("microsoft-login.example")],
  sha256: [indicator("a".repeat(64))],
};

describe("InvestigationIocWorkspace", () => {
  describe("availability", () => {
    it("shows an honest unavailable state, never fabricated zero counts, when IOC data failed", () => {
      render(makeData({ iocsByType: null }));

      expect(container.textContent).toContain("IOC data unavailable");
      expect(container.textContent).not.toContain("No IOCs found");
      expect(container.querySelectorAll(".metric-card")).toHaveLength(0);
      expect(container.querySelector(".data-table")).toBeNull();
    });

    it("shows an honest empty state, distinct from unavailable, when every category is genuinely empty", () => {
      render(makeData({ iocsByType: {} }));

      expect(container.textContent).toContain("No IOCs found");
      expect(container.textContent).not.toContain("unavailable");
      expect(container.querySelectorAll(".metric-card")).toHaveLength(0);
      expect(container.querySelector(".data-table")).toBeNull();
    });
  });

  describe("summary", () => {
    it("renders real total and per-category counts, including the two Windows categories", () => {
      render(
        makeData({
          iocsByType: {
            ipv4: [indicator("1.2.3.4"), indicator("5.6.7.8")],
            domains: [indicator("evil.example")],
            sha256: [indicator("a".repeat(64))],
            windows_file_paths: [indicator("C:\\Windows\\evil.exe")],
          },
        }),
      );

      expect(metricValue("Total")).toBe("5");
      expect(metricValue("IPs")).toBe("2");
      expect(metricValue("Domains")).toBe("1");
      expect(metricValue("Hashes")).toBe("1");
      expect(metricValue("Windows File Paths")).toBe("1");
      expect(metricValue("Windows Registry Keys")).toBe("0");
    });

    it("treats a type key absent from a real response the same as a real empty array", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      expect(metricValue("IPs")).toBe("1");
      expect(metricValue("Domains")).toBe("0");
      expect(metricValue("Total")).toBe("1");
    });
  });

  describe("table", () => {
    it("renders one real row per indicator with its real value and type", () => {
      render(
        makeData({
          iocsByType: {
            ipv4: [indicator("1.2.3.4")],
            domains: [indicator("evil.example")],
          },
        }),
      );

      const rows = tableRows();
      expect(rows).toHaveLength(2);
      expect(container.textContent).toContain("1.2.3.4");
      expect(container.textContent).toContain("evil.example");
      expect(container.textContent).toContain("IP Address");
      expect(container.textContent).toContain("Domain");
    });

    it("does not fabricate any metadata columns beyond type, value, and significance", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      const headers = Array.from(container.querySelectorAll(".data-table th")).map((th) => th.textContent);
      expect(headers).toEqual(["Type", "Value", "Risk Significance"]);
    });

    it("renders the real value unmutated and untruncated", () => {
      const longHash = "a".repeat(64);
      render(makeData({ iocsByType: { sha256: [indicator(longHash)] } }));

      expect(container.textContent).toContain(longHash);
    });
  });

  describe("accessibility", () => {
    it("uses real headings for the summary and table cards", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      const headings = Array.from(container.querySelectorAll("h2")).map((el) => el.textContent);
      expect(headings).toContain("IOC Summary");
      expect(headings).toContain("Indicators");
    });

    it("gives the table accessible column headers", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      const headerCells = container.querySelectorAll(".data-table th[scope='col']");
      expect(headerCells.length).toBe(3);
    });

    it("gives the table a caption", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      expect(container.querySelector(".data-table__caption")).not.toBeNull();
    });

    it("associates the search input with a real, non-placeholder-only label", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      const label = container.querySelector('label[for="investigation-ioc-search"]');
      expect(label).not.toBeNull();
      expect(searchInput().getAttribute("placeholder")).toBe("Search IOCs...");
    });

    it("associates the type filter with a real label", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      const label = container.querySelector('label[for="investigation-ioc-type-filter"]');
      expect(label).not.toBeNull();
    });
  });

  describe("search", () => {
    it("renders a search input once real IOC data exists", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      expect(searchInput()).not.toBeNull();
    });

    it("does not render the search/filter toolbar when IOC data is unavailable", () => {
      render(makeData({ iocsByType: null }));

      expect(searchInput()).toBeNull();
      expect(typeSelect()).toBeNull();
    });

    it("does not render the search/filter toolbar when the dataset is genuinely empty", () => {
      render(makeData({ iocsByType: {} }));

      expect(searchInput()).toBeNull();
      expect(typeSelect()).toBeNull();
    });

    it("is case-insensitive", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("EVIL");

      const rows = tableRows();
      expect(rows).toHaveLength(1);
      expect(container.textContent).toContain("evil.example");
    });

    it("shows only matching IOC values and hides non-matching ones", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("microsoft");

      const rows = tableRows();
      expect(rows).toHaveLength(1);
      expect(container.textContent).toContain("microsoft-login.example");
      expect(container.textContent).not.toContain("1.2.3.4");
      expect(container.textContent).not.toContain("evil.example");
    });
  });

  describe("type filter", () => {
    it("offers 'All types' plus only the real categories present in the data", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      const optionLabels = Array.from(typeSelect().querySelectorAll("option")).map((el) => el.textContent);
      expect(optionLabels).toEqual(["All types", "IP Address", "Domain", "SHA256 Hash"]);
    });

    it("never offers a category with zero real indicators", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      const optionLabels = Array.from(typeSelect().querySelectorAll("option")).map((el) => el.textContent);
      expect(optionLabels).not.toContain("Domain");
      expect(optionLabels).not.toContain("Windows Registry Key");
    });

    it("'All types' shows every real IOC", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      selectType("all");

      expect(tableRows()).toHaveLength(5);
    });

    it("filtering by an individual type shows only that type's real values", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      selectType("domains");

      const rows = tableRows();
      expect(rows).toHaveLength(2);
      expect(container.textContent).toContain("evil.example");
      expect(container.textContent).toContain("microsoft-login.example");
      expect(container.textContent).not.toContain("1.2.3.4");
    });
  });

  describe("combined search + type filter", () => {
    it("applies both together", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      selectType("domains");
      typeSearch("microsoft");

      const rows = tableRows();
      expect(rows).toHaveLength(1);
      expect(container.textContent).toContain("microsoft-login.example");
      expect(container.textContent).not.toContain("evil.example");
    });
  });

  describe("result count", () => {
    it("shows the correct total count with no filter active", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      expect(container.textContent).toContain("Showing 5 of 5 IOCs");
    });

    it("shows the correct filtered count distinct from the total", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("microsoft");

      expect(container.textContent).toContain("Showing 1 of 5 IOCs");
    });
  });

  describe("reset", () => {
    it("shows a clear/reset action only once a filter is active", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      const findReset = () =>
        Array.from(container.querySelectorAll("button")).find((el) => el.textContent === "Clear filters");
      expect(findReset()).toBeUndefined();

      typeSearch("microsoft");
      expect(findReset()).not.toBeUndefined();
    });

    it("restores all real IOC values when clicked", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("microsoft");
      selectType("domains");
      expect(tableRows()).toHaveLength(1);

      clickResetButton();

      expect(tableRows()).toHaveLength(5);
      expect(searchInput().value).toBe("");
      expect(typeSelect().value).toBe("all");
    });
  });

  describe("filtered empty state", () => {
    it("distinguishes 'no matches' from the genuinely-empty and unavailable states", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("nonexistent-indicator-value");

      expect(container.textContent).toContain("No IOCs match your filters");
      expect(container.textContent).not.toContain("No IOCs found for this investigation");
      expect(container.textContent).not.toContain("IOC data unavailable");
      expect(container.querySelector(".data-table")).toBeNull();
    });

    it("offers a 'Clear filters' action from the no-matches state", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("nonexistent-indicator-value");
      clickResetButton();

      expect(tableRows()).toHaveLength(5);
    });

    it("does not display zero as though the source dataset were empty", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("nonexistent-indicator-value");

      expect(container.textContent).toContain("Showing 0 of 5 IOCs");
    });
  });

  describe("data integrity", () => {
    it("does not mutate the original normalized iocsByType while filtering", () => {
      const iocsByType = {
        ipv4: [indicator("1.2.3.4"), indicator("5.6.7.8")],
        domains: [indicator("evil.example")],
      };
      const snapshot = JSON.parse(JSON.stringify(iocsByType));

      render(makeData({ iocsByType }));
      typeSearch("evil");
      selectType("domains");
      clickResetButton();

      expect(iocsByType).toEqual(snapshot);
    });
  });

  describe("partial state", () => {
    it("TI failure does not affect IOC search/filter controls", () => {
      render(makeData({ iocsByType: MIXED_IOCS, rawThreatIntelligence: null }));

      expect(searchInput()).not.toBeNull();
      expect(typeSelect()).not.toBeNull();
    });

    it("IOC unavailability hides the filter controls even when TI data is present", () => {
      render(makeData({ iocsByType: null, rawThreatIntelligence: { some: "value" } }));

      expect(searchInput()).toBeNull();
      expect(typeSelect()).toBeNull();
    });
  });

  describe("investigation switching", () => {
    it("does not leak stale search/filter state into a different investigation", () => {
      render(makeData({ investigationId: 7, iocsByType: MIXED_IOCS }));

      typeSearch("microsoft");
      selectType("domains");
      expect(tableRows()).toHaveLength(1);

      rerender(
        makeData({
          investigationId: 42,
          iocsByType: { ipv4: [indicator("9.9.9.9")], urls: [indicator("http://example.test")] },
        }),
      );

      expect(searchInput().value).toBe("");
      expect(typeSelect().value).toBe("all");
      expect(tableRows()).toHaveLength(2);
      expect(container.textContent).toContain("Showing 2 of 2 IOCs");
    });

    it("preserves local filter state across a re-render of the same investigation", () => {
      render(makeData({ investigationId: 7, iocsByType: MIXED_IOCS }));

      typeSearch("microsoft");
      expect(tableRows()).toHaveLength(1);

      rerender(makeData({ investigationId: 7, iocsByType: MIXED_IOCS }));

      expect(searchInput().value).toBe("microsoft");
      expect(tableRows()).toHaveLength(1);
    });

    it("clears the selected IOC when switching to a different investigation", () => {
      render(makeData({ investigationId: 7, iocsByType: MIXED_IOCS }));

      clickRow("evil.example");
      expect(detailPanel()).not.toBeNull();

      rerender(makeData({ investigationId: 42, iocsByType: { ipv4: [indicator("9.9.9.9")] } }));

      expect(detailPanel()).toBeNull();
    });
  });

  describe("IOC selection", () => {
    it("is not rendered before any row is selected", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      expect(detailPanel()).toBeNull();
    });

    it("marks rows as keyboard-focusable and selectable", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      const row = findRowByText("evil.example");
      expect(row?.getAttribute("tabindex")).toBe("0");
      expect(row?.getAttribute("aria-selected")).toBe("false");
    });

    it("selecting a row displays its real value in the detail panel", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");

      const panel = detailPanel();
      expect(panel).not.toBeNull();
      expect(panel?.textContent).toContain("evil.example");
    });

    it("selecting a row displays its real type, from real data", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");

      expect(detailPanel()?.textContent).toContain("Domain");
    });

    it("marks the selected row's aria-selected as true", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");

      expect(findRowByText("evil.example")?.getAttribute("aria-selected")).toBe("true");
    });

    it("gives the selected row a non-color-only visual indicator class", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");

      // `data-table__row--selected` (DataTable.css) pairs the
      // background tint with a shape-based (border) cue, so the
      // selected state doesn't rely on color alone.
      expect(findRowByText("evil.example")?.className).toContain("data-table__row--selected");
    });

    it("selecting a different row swaps the detail panel to the new selection", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");
      expect(detailPanel()?.textContent).toContain("evil.example");

      clickRow("1.2.3.4");

      expect(detailPanel()?.textContent).toContain("1.2.3.4");
      expect(detailPanel()?.textContent).not.toContain("evil.example");
    });
  });

  describe("IOC detail — no fabricated fields", () => {
    it("does not invent metadata fields the normalized indicator does not have", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      clickRow("1.2.3.4");

      const panel = detailPanel();
      expect(panel?.textContent).not.toMatch(/confidence/i);
      expect(panel?.textContent).not.toMatch(/reputation/i);
      expect(panel?.textContent).not.toMatch(/first seen/i);
      expect(panel?.textContent).not.toMatch(/last seen/i);
      expect(panel?.textContent).not.toMatch(/provider/i);
      expect(panel?.textContent).not.toMatch(/malicious/i);
    });

    it("does not render a Threat Intelligence field when tiState is null", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      clickRow("1.2.3.4");

      expect(detailPanel()?.textContent).not.toContain("Threat Intelligence");
    });

    it("renders the real tiState when the normalized indicator has one", () => {
      render(makeData({ iocsByType: { ipv4: [indicatorWithState("1.2.3.4", "enriched")] } }));

      clickRow("1.2.3.4");

      expect(detailPanel()?.textContent).toContain("Threat Intelligence");
      expect(detailPanel()?.textContent).toContain("Enriched");
    });
  });

  describe("copy value", () => {
    let writeText: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        configurable: true,
      });
    });

    afterEach(() => {
      // @ts-expect-error -- test-only cleanup of the property this
      // suite itself defines above; jsdom has no real clipboard.
      delete navigator.clipboard;
    });

    function copyButton(): HTMLButtonElement | null {
      return detailPanel()?.querySelector(".investigation-ioc-workspace__copy") as HTMLButtonElement | null;
    }

    function copyStatusText(): string | null {
      return detailPanel()?.querySelector(".investigation-ioc-workspace__copy-status")?.textContent ?? null;
    }

    async function clickCopy(): Promise<void> {
      await act(async () => {
        copyButton()?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        // Flush the mocked `clipboard.writeText()` promise.
        await Promise.resolve();
        await Promise.resolve();
      });
    }

    it("offers a copy action for the selected IOC's value, with a real accessible name", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));
      clickRow("evil.example");

      const button = copyButton();
      expect(button).not.toBeNull();
      expect(button?.tagName).toBe("BUTTON");
      expect(button?.getAttribute("aria-label")).toMatch(/copy/i);
    });

    it("copies the exact real IOC value, never an altered form of it", async () => {
      render(makeData({ iocsByType: MIXED_IOCS }));
      clickRow("evil.example");

      await clickCopy();

      expect(writeText).toHaveBeenCalledWith("evil.example");
    });

    it("shows real text feedback after a successful copy, not only a color change", async () => {
      render(makeData({ iocsByType: MIXED_IOCS }));
      clickRow("evil.example");

      await clickCopy();

      expect(copyStatusText()).toBe("Copied");
    });

    it("exposes copy feedback through an accessible live region", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));
      clickRow("evil.example");

      const status = detailPanel()?.querySelector(".investigation-ioc-workspace__copy-status");
      expect(status?.getAttribute("role")).toBe("status");
      expect(status?.getAttribute("aria-live")).toBe("polite");
    });

    it("shows honest failure feedback, never a fabricated success, when the clipboard write fails", async () => {
      writeText.mockRejectedValue(new Error("denied"));
      render(makeData({ iocsByType: MIXED_IOCS }));
      clickRow("evil.example");

      await clickCopy();

      expect(copyStatusText()).toBe("Copy failed");
    });

    it("clears prior copy feedback when a different IOC is selected", async () => {
      render(makeData({ iocsByType: MIXED_IOCS }));
      clickRow("evil.example");
      await clickCopy();
      expect(copyStatusText()).toBe("Copied");

      clickRow("1.2.3.4");

      expect(copyStatusText()).toBe("");
    });

    it("copies the correct value for the currently selected row after switching selection", async () => {
      render(makeData({ iocsByType: MIXED_IOCS }));
      clickRow("evil.example");
      clickRow("1.2.3.4");

      await clickCopy();

      expect(writeText).toHaveBeenCalledWith("1.2.3.4");
      expect(writeText).not.toHaveBeenCalledWith("evil.example");
    });
  });

  describe("close / deselect", () => {
    it("removes the detail panel when the close control is clicked", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");
      expect(detailPanel()).not.toBeNull();

      clickDetailClose();

      expect(detailPanel()).toBeNull();
    });

    it("closing does not reset search or type filter", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("e");
      selectType("domains");
      clickRow("evil.example");

      clickDetailClose();

      expect(searchInput().value).toBe("e");
      expect(typeSelect().value).toBe("domains");
    });

    it("re-activating the selected row also deselects it", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");
      expect(detailPanel()).not.toBeNull();

      clickRow("evil.example");

      expect(detailPanel()).toBeNull();
    });
  });

  describe("selection + filtering", () => {
    it("selecting a row does not reset the active search/filter", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      typeSearch("evil");
      clickRow("evil.example");

      expect(searchInput().value).toBe("evil");
      expect(tableRows()).toHaveLength(1);
    });

    it("clears a stale detail view when the selected IOC is filtered out by search", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");
      expect(detailPanel()?.textContent).toContain("evil.example");

      typeSearch("microsoft");

      expect(detailPanel()).toBeNull();
    });

    it("clears a stale detail view when the selected IOC is filtered out by type", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("1.2.3.4");
      expect(detailPanel()?.textContent).toContain("1.2.3.4");

      selectType("domains");

      expect(detailPanel()).toBeNull();
    });

    it("retains the detail view when the selected IOC still matches after a filter change", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      clickRow("evil.example");
      selectType("domains");

      expect(detailPanel()?.textContent).toContain("evil.example");
    });
  });

  describe("keyboard accessibility", () => {
    it("selects a row on Enter", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      pressKeyOnRow("evil.example", "Enter");

      expect(detailPanel()?.textContent).toContain("evil.example");
    });

    it("selects a row on Space", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      pressKeyOnRow("1.2.3.4", " ");

      expect(detailPanel()?.textContent).toContain("1.2.3.4");
    });

    it("every row is keyboard-focusable, not just the selected one", () => {
      render(makeData({ iocsByType: MIXED_IOCS }));

      for (const row of tableRows()) {
        expect(row.getAttribute("tabindex")).toBe("0");
      }
    });
  });

  describe("long values", () => {
    it("keeps a long IOC value accessible in the detail panel", () => {
      const longHash = "a".repeat(64);
      render(makeData({ iocsByType: { sha256: [indicator(longHash)] } }));

      clickRow(longHash);

      expect(detailPanel()?.textContent).toContain(longHash);
    });
  });

  describe("partial investigation state", () => {
    it("IOC detail still works when Threat Intelligence failed", () => {
      render(makeData({ iocsByType: MIXED_IOCS, rawThreatIntelligence: null }));

      clickRow("evil.example");

      expect(detailPanel()?.textContent).toContain("evil.example");
    });
  });

  describe("unavailable / empty states", () => {
    it("never renders detail when IOC data is unavailable", () => {
      render(makeData({ iocsByType: null }));

      expect(detailPanel()).toBeNull();
    });

    it("never renders detail when the dataset is genuinely empty", () => {
      render(makeData({ iocsByType: {} }));

      expect(detailPanel()).toBeNull();
    });
  });

  describe("data integrity", () => {
    it("selecting and deselecting rows does not mutate the original normalized iocsByType", () => {
      const iocsByType = {
        ipv4: [indicator("1.2.3.4")],
        domains: [indicator("evil.example")],
      };
      const snapshot = JSON.parse(JSON.stringify(iocsByType));

      render(makeData({ iocsByType }));
      clickRow("evil.example");
      clickRow("1.2.3.4");
      clickDetailClose();

      expect(iocsByType).toEqual(snapshot);
    });
  });

  describe("risk significance badge (PD-08-P4.2)", () => {
    const SIGNIFICANCE = {
      ipv4: { weight: 8, significance: "High" },
      domains: { weight: 3, significance: "Medium" },
      urls: { weight: 1, significance: "Low" },
      windows_file_paths: { weight: 0, significance: "Informational" },
    };

    it("renders the real known significance label for an IOC's category", () => {
      render(
        makeData({
          iocsByType: { ipv4: [indicator("1.2.3.4")] },
          iocSignificance: { ipv4: SIGNIFICANCE.ipv4 },
        }),
      );

      const row = findRowByText("1.2.3.4");
      expect(row?.textContent).toContain("High");
    });

    it("attaches each row's badge to that row's own category, not another one", () => {
      render(
        makeData({
          iocsByType: {
            ipv4: [indicator("1.2.3.4")],
            domains: [indicator("evil.example")],
          },
          iocSignificance: { ipv4: SIGNIFICANCE.ipv4, domains: SIGNIFICANCE.domains },
        }),
      );

      const ipRow = findRowByText("1.2.3.4");
      const domainRow = findRowByText("evil.example");
      expect(ipRow?.textContent).toContain("High");
      expect(ipRow?.textContent).not.toContain("Medium");
      expect(domainRow?.textContent).toContain("Medium");
      expect(domainRow?.textContent).not.toContain("High");
    });

    it("renders the significance label exactly as the backend sent it, never reinterpreted", () => {
      render(
        makeData({
          iocsByType: { urls: [indicator("http://evil.example")] },
          iocSignificance: { urls: SIGNIFICANCE.urls },
        }),
      );

      expect(findRowByText("http://evil.example")?.textContent).toContain("Low");
    });

    it("renders an honest empty cell, never a fabricated badge, when a category has no significance entry", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] }, iocSignificance: {} }));

      const row = findRowByText("1.2.3.4");
      expect(row?.querySelectorAll(".status-badge")).toHaveLength(1); // only the Type badge
      expect(row?.textContent).not.toMatch(/unknown/i);
    });

    it("renders an honest empty cell when iocSignificance itself was never provided", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] } }));

      const row = findRowByText("1.2.3.4");
      expect(row?.querySelectorAll(".status-badge")).toHaveLength(1);
    });

    it("does not break rendering for other IOC types when significance data is partial", () => {
      render(
        makeData({
          iocsByType: MIXED_IOCS,
          iocSignificance: { ipv4: SIGNIFICANCE.ipv4 },
        }),
      );

      expect(tableRows()).toHaveLength(5);
      expect(container.textContent).toContain("evil.example");
      expect(container.textContent).toContain(("a").repeat(64));
    });

    it("does not destroy the layout for a long IOC value paired with a significance badge", () => {
      const longHash = "a".repeat(64);
      render(
        makeData({
          iocsByType: { sha256: [indicator(longHash)] },
          iocSignificance: { sha256: { weight: 6, significance: "High" } },
        }),
      );

      const row = findRowByText(longHash);
      expect(row?.textContent).toContain(longHash);
      expect(row?.textContent).toContain("High");
    });

    it("carries the significance value through to the IOC detail panel", () => {
      render(
        makeData({
          iocsByType: { ipv4: [indicator("1.2.3.4")] },
          iocSignificance: { ipv4: SIGNIFICANCE.ipv4 },
        }),
      );

      clickRow("1.2.3.4");

      expect(detailPanel()?.textContent).toContain("Risk Significance");
      expect(detailPanel()?.textContent).toContain("High");
    });

    it("does not render a Risk Significance detail field when the category has no entry", () => {
      render(makeData({ iocsByType: { ipv4: [indicator("1.2.3.4")] }, iocSignificance: {} }));

      clickRow("1.2.3.4");

      expect(detailPanel()?.textContent).not.toContain("Risk Significance");
    });

    it("carries existing IOC content (type/value) alongside the significance badge without hiding it", () => {
      render(
        makeData({
          iocsByType: { ipv4: [indicator("1.2.3.4")] },
          iocSignificance: { ipv4: SIGNIFICANCE.ipv4 },
        }),
      );

      const row = findRowByText("1.2.3.4");
      expect(row?.textContent).toContain("IP Address");
      expect(row?.textContent).toContain("1.2.3.4");
      expect(row?.textContent).toContain("High");
    });

    it("never performs client-side risk calculation -- renders only the real backend significance string", () => {
      // A deliberately "wrong" weight/significance pairing (a real
      // IPv4 weight is 8, not 1) proves the badge renders the
      // backend's own `significance` string verbatim rather than
      // recomputing it from `weight` via any local banding logic.
      render(
        makeData({
          iocsByType: { ipv4: [indicator("1.2.3.4")] },
          iocSignificance: { ipv4: { weight: 1, significance: "Low" } },
        }),
      );

      expect(findRowByText("1.2.3.4")?.textContent).toContain("Low");
      expect(findRowByText("1.2.3.4")?.textContent).not.toContain("High");
    });
  });
});
