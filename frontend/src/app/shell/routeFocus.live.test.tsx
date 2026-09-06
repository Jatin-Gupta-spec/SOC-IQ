// @vitest-environment jsdom
/**
 * Route-change focus management — MAX-17 Phase 2A (MAX17-F-01).
 *
 * Exercises the real composition root (`App.tsx`, real `HashRouter`,
 * real `AppShell`/`ContentRegion`/`PageLayout`) exactly the way
 * `navigation.live.test.tsx` and `AppShell.live.test.tsx` already do
 * for their own scopes, so this proves the production mechanism
 * (`ContentRegion`'s route-change effect) is what actually moves
 * focus — not a test-only stand-in. `document.activeElement` is
 * asserted directly throughout (task brief §11): no snapshot-only
 * assertions, no `.focus()` spies, no "a ref exists" checks.
 *
 * `useInvestigationsList` is mocked at its own module boundary, the
 * same convention `InvestigationsPage.test.tsx` already established,
 * so the whole-row-activation path (Test 2) has real, deterministic
 * rows to activate. `InvestigationWorkspacePage`'s own data fetch is
 * left real and unmocked — exactly like `router.live.test.tsx`'s
 * `/investigations/:id` case, it fails fast in this jsdom
 * environment (no Tauri runtime) and renders its own real error
 * state, which is still a real `<PageLayout>`-owned `<main>` and is
 * therefore exactly what this file needs to assert focus against.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { UseInvestigationsListResult } from "../../pages/investigations/useInvestigationsList";
import type { InvestigationSummary } from "../../shared/api/types";

/**
 * SOC-IQ GATE 2 STEP 5 — forensic finding (see the fuller note in
 * `router.live.test.tsx`, which this file's `waitForSettledPageMain`
 * helper already documents mirroring). A clean-Windows CI run timed
 * out waiting for exactly the three destinations this file touches
 * for the *first* time within it (Dashboard in Test 1, the
 * Investigation Workspace in Test 2, Analyze in Test 7) while every
 * destination re-touched later in the same file (once its module is
 * already resolved/cached in this worker) settled well within budget
 * -- consistent with first-import cold-transform cost, not a focus-
 * management or routing defect. This project's own reference
 * environment passes all five tests with zero flakiness (verified as
 * part of this investigation). Widening this file's own polling
 * budget and Vitest timeout, scoped here only, gives a colder/slower
 * environment real headroom without weakening what's asserted.
 */
vi.setConfig({ testTimeout: 9_000 });

const useInvestigationsListMock = vi.fn();

vi.mock("../../pages/investigations/useInvestigationsList", () => ({
  useInvestigationsList: (...args: unknown[]) => useInvestigationsListMock(...args),
}));

vi.mock("../../pages/investigations/InvestigationsCsvExportAction", () => ({
  InvestigationsCsvExportAction: () => (
    <span data-testid="csv-export-action">Export CSV</span>
  ),
}));

const { App } = await import("../App");

const INVESTIGATION: InvestigationSummary = {
  investigation_id: 42,
  report_name: "phishing-report.eml",
  risk_score: 87,
  severity: "HIGH",
  confidence: 0.91,
  status: "COMPLETED",
  analyzed_at: "2026-08-20T10:15:00",
};

function investigationsListResult(
  overrides: Partial<UseInvestigationsListResult> = {},
): UseInvestigationsListResult {
  return {
    state: "success",
    investigations: [INVESTIGATION],
    error: null,
    retry: vi.fn(),
    ...overrides,
  };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  useInvestigationsListMock.mockReturnValue(investigationsListResult());
  container = document.createElement("div");
  document.body.appendChild(container);
  act(() => {
    root = createRoot(container);
    root.render(<App />);
  });
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
  window.location.hash = "";
});

function findNavLink(label: string): HTMLAnchorElement {
  const link = Array.from(container.querySelectorAll("a")).find(
    (anchor) => anchor.getAttribute("aria-label") === label,
  );
  if (!link) {
    throw new Error(`No nav link found with aria-label "${label}"`);
  }
  return link;
}

function clickNavLink(label: string): void {
  act(() => {
    findNavLink(label).dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }),
    );
  });
}

/**
 * A page's `<main>` can briefly be `RouteLoadingFallback`'s own
 * `<PageLayout>` (same accessible name, no chunk loaded yet) before
 * the real page replaces it — mirrors `router.live.test.tsx`'s own
 * "poll with a real per-attempt budget" approach for exactly the
 * same cold-module-transform reason, rather than a fixed wait.
 */
async function waitForSettledPageMain(label: string): Promise<HTMLElement> {
  // 120 attempts (6s) rather than the original 40 (2s) -- see the
  // GATE 2 STEP 5 forensic note above `vi.setConfig` at the top of
  // this file. The 50ms interval and the condition checked are both
  // unchanged.
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const main = container.querySelector<HTMLElement>(`main[aria-label="${label}"]`);
    if (main && !main.textContent?.includes(`Loading ${label.replace(/ page$/, "")}…`)) {
      return main;
    }
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
  }
  throw new Error(`Timed out waiting for a settled <main aria-label="${label}">`);
}

describe("Route-change focus management (MAX17-F-01)", () => {
  it("Test 1 — sidebar navigation moves focus to the destination page's <main>, off the sidebar link", async () => {
    await waitForSettledPageMain("Dashboard page");

    const reportsLink = findNavLink("Reports");
    act(() => {
      reportsLink.focus();
    });
    expect(document.activeElement).toBe(reportsLink);

    clickNavLink("Reports");
    const reportsMain = await waitForSettledPageMain("Reports page");

    expect(document.activeElement).toBe(reportsMain);
    expect(document.activeElement).not.toBe(reportsLink);
  });

  it("Test 2 — whole-row activation moves focus to the Investigation Workspace's <main>, off the removed row", async () => {
    clickNavLink("Investigations");
    await waitForSettledPageMain("Investigations page");

    const row = container.querySelector<HTMLTableRowElement>("tbody tr");
    expect(row).not.toBeNull();

    act(() => {
      row?.focus();
    });
    expect(document.activeElement).toBe(row);

    act(() => {
      row?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    const workspaceMain = await waitForSettledPageMain("Investigation Workspace page");

    expect(document.activeElement).toBe(workspaceMain);
    expect(document.activeElement).not.toBe(row);
    // The old row is gone entirely, not merely unfocused.
    expect(document.contains(row)).toBe(false);
  });

  it("Test 3 — command-palette navigation moves focus to the destination page's <main>, closing the MAX17 gap", async () => {
    clickNavLink("Investigations");
    await waitForSettledPageMain("Investigations page");

    const searchInput = container.querySelector<HTMLInputElement>("#investigations-search");
    expect(searchInput).not.toBeNull();
    act(() => {
      searchInput?.focus();
    });
    expect(document.activeElement).toBe(searchInput);

    // Ctrl+K opens the palette (Cmd+K on macOS; either primary
    // modifier works per `useCommandPaletteShortcut`'s own chord
    // rule — Ctrl is used here to match this project's other
    // palette tests, e.g. `CommandPaletteContainer.live.test.tsx`).
    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true, cancelable: true }),
      );
    });
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();

    const dashboardOption = Array.from(container.querySelectorAll('[role="option"]')).find(
      (option) => option.textContent?.includes("Dashboard"),
    );
    expect(dashboardOption).toBeTruthy();

    act(() => {
      dashboardOption?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    // The palette closes and the old page (including the search
    // input that used to hold focus) unmounts as part of the same
    // navigation.
    expect(container.querySelector('[role="dialog"]')).toBeNull();

    const dashboardMain = await waitForSettledPageMain("Dashboard page");

    expect(document.activeElement).toBe(dashboardMain);
    expect(document.activeElement).not.toBe(searchInput);
    expect(document.contains(searchInput)).toBe(false);
  });

  it("Test 4 (regression) — CommandPalette still restores focus to the pre-open trigger when it closes without navigating (MAX-15)", async () => {
    await waitForSettledPageMain("Dashboard page");

    const analyzeLink = findNavLink("Analyze");
    act(() => {
      analyzeLink.focus();
    });
    expect(document.activeElement).toBe(analyzeLink);

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true, cancelable: true }),
      );
    });
    expect(container.querySelector('[role="dialog"]')).not.toBeNull();

    const dialog = container.querySelector('[role="dialog"]');
    act(() => {
      dialog?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }),
      );
    });

    expect(container.querySelector('[role="dialog"]')).toBeNull();
    // No navigation happened, so ContentRegion's route-change effect
    // never ran — MAX-15's own restore-on-close logic is the only
    // thing that could have put focus back here.
    expect(document.activeElement).toBe(analyzeLink);
  });

  it("Test 7 — repeated navigation (A → B → C → A) focuses each destination correctly every time", async () => {
    await waitForSettledPageMain("Dashboard page");

    clickNavLink("Analyze");
    const analyzeMain = await waitForSettledPageMain("Analyze page");
    expect(document.activeElement).toBe(analyzeMain);

    clickNavLink("Settings");
    const settingsMain = await waitForSettledPageMain("Settings page");
    expect(document.activeElement).toBe(settingsMain);
    expect(document.activeElement).not.toBe(analyzeMain);

    clickNavLink("Dashboard");
    const dashboardMainAgain = await waitForSettledPageMain("Dashboard page");
    expect(document.activeElement).toBe(dashboardMainAgain);
    expect(document.activeElement).not.toBe(settingsMain);
  });
});
