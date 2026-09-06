// @vitest-environment jsdom
/**
 * `CommandPalette` interaction tests — Phase 4G-5 Part 1 (task brief
 * §14 items 4-5, 7-11).
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CommandPalette } from "./CommandPalette";
import type { Command } from "../../shared/commands/types";

const FIXTURE_COMMANDS: readonly Command[] = [
  {
    id: "navigate:dashboard",
    label: "Dashboard",
    description: "Go to Dashboard",
    category: "navigation",
    keywords: ["dashboard"],
    path: "/dashboard",
  },
  {
    id: "navigate:analyze",
    label: "Analyze",
    description: "Go to Analyze",
    category: "navigation",
    keywords: ["analyze"],
    path: "/analyze",
  },
  {
    id: "navigate:risk",
    label: "Risk",
    description: "Go to Risk",
    category: "navigation",
    keywords: ["risk"],
    path: "/risk",
  },
];

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

function pressKey(key: string): void {
  const dialog = container.querySelector('[role="dialog"]');
  act(() => {
    dialog?.dispatchEvent(
      new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
    );
  });
}

describe("CommandPalette interaction", () => {
  it("filters results as the search input changes", () => {
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    const input = container.querySelector("input")!;
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value",
    )!.set!;
    act(() => {
      nativeSetter.call(input, "risk");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });

    const options = container.querySelectorAll('[role="option"]');
    expect(options).toHaveLength(1);
    expect(options[0]?.textContent).toContain("Risk");
  });

  it("moves the selection with ArrowDown/ArrowUp", () => {
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    pressKey("ArrowDown");
    let selected = container.querySelector('[aria-selected="true"]');
    expect(selected?.textContent).toContain("Analyze");

    pressKey("ArrowDown");
    selected = container.querySelector('[aria-selected="true"]');
    expect(selected?.textContent).toContain("Risk");

    pressKey("ArrowUp");
    selected = container.querySelector('[aria-selected="true"]');
    expect(selected?.textContent).toContain("Analyze");
  });

  it("wraps selection from the last item back to the first on ArrowDown", () => {
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    pressKey("ArrowDown");
    pressKey("ArrowDown");
    pressKey("ArrowDown");
    const selected = container.querySelector('[aria-selected="true"]');
    expect(selected?.textContent).toContain("Dashboard");
  });

  it("Enter navigates to the selected command's path", () => {
    const onNavigate = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={onNavigate}
        />,
      );
    });

    pressKey("ArrowDown");
    pressKey("Enter");

    expect(onNavigate).toHaveBeenCalledWith("/analyze");
  });

  it("clicking a result navigates to its path", () => {
    const onNavigate = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={onNavigate}
        />,
      );
    });

    const riskOption = Array.from(
      container.querySelectorAll('[role="option"]'),
    ).find((el) => el.textContent?.includes("Risk"));
    act(() => {
      riskOption?.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
    });

    expect(onNavigate).toHaveBeenCalledWith("/risk");
  });

  it("Escape closes the palette", () => {
    const onClose = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={onClose}
          onNavigate={() => {}}
        />,
      );
    });

    pressKey("Escape");

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clicking the backdrop closes the palette", () => {
    const onClose = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={onClose}
          onNavigate={() => {}}
        />,
      );
    });

    const dismiss = container.querySelector<HTMLButtonElement>(
      ".command-palette-backdrop__dismiss",
    );
    act(() => {
      dismiss?.click();
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("resets query and selection each time it reopens", () => {
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    const input = container.querySelector("input")!;
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value",
    )!.set!;
    act(() => {
      nativeSetter.call(input, "risk");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(container.querySelectorAll('[role="option"]')).toHaveLength(1);

    // Close, then reopen.
    act(() => {
      root.render(
        <CommandPalette
          open={false}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });
    act(() => {
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    expect(container.querySelectorAll('[role="option"]')).toHaveLength(
      FIXTURE_COMMANDS.length,
    );
    expect(container.querySelector("input")?.value).toBe("");
  });
});

// MAX15-F-01: focus enters the palette on open and is restored to
// whatever held it beforehand on every close path. `document
// .activeElement` is asserted directly throughout — DOM presence
// alone doesn't prove focus moved.
describe("CommandPalette focus restoration (MAX15-F-01)", () => {
  function renderClosed(): void {
    act(() => {
      root = createRoot(container);
      root.render(
        <CommandPalette
          open={false}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });
  }

  it("moves focus into the palette's search input on open", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open palette";
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    renderClosed();
    act(() => {
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    expect(document.activeElement).toBe(container.querySelector("input"));

    trigger.remove();
  });

  it("restores focus to the previously focused control on Escape", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open palette";
    document.body.appendChild(trigger);
    trigger.focus();

    renderClosed();
    act(() => {
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });
    expect(document.activeElement).toBe(container.querySelector("input"));

    pressKey("Escape");
    act(() => {
      root.render(
        <CommandPalette
          open={false}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    expect(document.activeElement).toBe(trigger);

    trigger.remove();
  });

  it("restores focus to the previously focused control on backdrop dismiss", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open palette";
    document.body.appendChild(trigger);
    trigger.focus();

    renderClosed();
    act(() => {
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });
    expect(document.activeElement).toBe(container.querySelector("input"));

    const dismiss = container.querySelector<HTMLButtonElement>(
      ".command-palette-backdrop__dismiss",
    );
    act(() => {
      dismiss?.click();
    });
    act(() => {
      root.render(
        <CommandPalette
          open={false}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });

    expect(document.activeElement).toBe(trigger);

    trigger.remove();
  });

  it("navigates and restores focus on command selection when the previous target survives", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open palette";
    document.body.appendChild(trigger);
    trigger.focus();

    const onNavigate = vi.fn();
    renderClosed();
    act(() => {
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={onNavigate}
        />,
      );
    });

    pressKey("ArrowDown");
    pressKey("Enter");
    expect(onNavigate).toHaveBeenCalledWith("/analyze");

    // In real usage, selecting a command also closes the palette
    // (`CommandPaletteContainer.handleNavigate` calls `navigate` then
    // `close`); simulate the resulting `open={false}` re-render.
    act(() => {
      root.render(
        <CommandPalette
          open={false}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={onNavigate}
        />,
      );
    });

    expect(document.activeElement).toBe(trigger);

    trigger.remove();
  });

  it("does not throw and falls back safely when the previous target is detached before close", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open palette";
    document.body.appendChild(trigger);
    trigger.focus();

    renderClosed();
    act(() => {
      root.render(
        <CommandPalette
          open={true}
          commands={FIXTURE_COMMANDS}
          onClose={() => {}}
          onNavigate={() => {}}
        />,
      );
    });
    expect(document.activeElement).toBe(container.querySelector("input"));

    // Simulate navigation unmounting the page that held the
    // originally focused control.
    trigger.remove();

    expect(() => {
      act(() => {
        root.render(
          <CommandPalette
            open={false}
            commands={FIXTURE_COMMANDS}
            onClose={() => {}}
            onNavigate={() => {}}
          />,
        );
      });
    }).not.toThrow();

    // No attempt was made to focus the detached node; the safe
    // fallback is simply not forcing focus anywhere.
    expect(document.activeElement).not.toBe(trigger);
    expect(document.contains(trigger)).toBe(false);
  });
});
