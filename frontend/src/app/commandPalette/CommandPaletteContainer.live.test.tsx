// @vitest-environment jsdom
/**
 * `CommandPaletteContainer` integration tests — Phase 4G-5 Part 1.
 *
 * Exercises the real `COMMANDS` registry and a real
 * `react-router-dom` router together, the same "drive the real
 * default wiring end to end" approach
 * `AppShell.live.test.tsx` already uses for the 4G-4 notification.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import { CommandPaletteContainer } from "./CommandPaletteContainer";

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

function renderWithRouter(initialPath = "/dashboard"): void {
  act(() => {
    root = createRoot(container);
    root.render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="*" element={<CommandPaletteContainer />} />
        </Routes>
      </MemoryRouter>,
    );
  });
}

function ctrlK(): void {
  act(() => {
    window.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "k",
        ctrlKey: true,
        bubbles: true,
        cancelable: true,
      }),
    );
  });
}

describe("CommandPaletteContainer", () => {
  it("is closed by default", () => {
    renderWithRouter();
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("opens on Ctrl+K and closes on a second Ctrl+K", () => {
    renderWithRouter();

    ctrlK();
    expect(container.querySelector('[role="dialog"]')).not.toBeNull();

    ctrlK();
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("lists the real registered navigation commands when opened, without the retired IOC Explorer/Threat Intel/Risk commands (PD-05, PD-06)", () => {
    renderWithRouter();
    ctrlK();

    const text = container.querySelector('[role="listbox"]')?.textContent;
    expect(text).toContain("Dashboard");
    expect(text).toContain("Reports");
    expect(text).toContain("Settings");
    // PD-05: the retired top-level IOC Explorer/Threat Intel commands
    // no longer appear in the live command palette.
    expect(text).not.toContain("IOC Explorer");
    expect(text).not.toContain("Threat Intel");
    // PD-06: the retired top-level Risk command no longer appears in
    // the live command palette either.
    expect(text).not.toContain("Risk");
  });

  it("Escape closes the palette", () => {
    renderWithRouter();
    ctrlK();
    expect(container.querySelector('[role="dialog"]')).not.toBeNull();

    const dialog = container.querySelector('[role="dialog"]');
    act(() => {
      dialog?.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          bubbles: true,
          cancelable: true,
        }),
      );
    });

    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("selecting a command closes the palette (navigation itself is exercised via the real router)", () => {
    renderWithRouter();
    ctrlK();

    const analyzeOption = Array.from(
      container.querySelectorAll('[role="option"]'),
    ).find((el) => el.textContent?.includes("Analyze"));
    expect(analyzeOption).toBeTruthy();

    act(() => {
      analyzeOption?.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
    });

    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("restores focus to the control that opened it once Escape closes it (MAX15-F-01)", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Somewhere in the app";
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    renderWithRouter();
    ctrlK();
    expect(document.activeElement).toBe(container.querySelector("input"));

    const dialog = container.querySelector('[role="dialog"]');
    act(() => {
      dialog?.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          bubbles: true,
          cancelable: true,
        }),
      );
    });

    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);

    trigger.remove();
  });
});
