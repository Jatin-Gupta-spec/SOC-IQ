// @vitest-environment jsdom
/**
 * `useCommandPaletteShortcut` tests — Phase 4G-5 Part 1 (task brief
 * §14 items 12-15).
 */

import { act, StrictMode, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCommandPaletteShortcut } from "./useCommandPaletteShortcut";

function Probe({ onToggle }: { onToggle: () => void }): ReactElement {
  useCommandPaletteShortcut(onToggle);
  return <div />;
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

function dispatchKey(init: Partial<KeyboardEventInit>, target: EventTarget = window): void {
  const event = new KeyboardEvent("keydown", {
    bubbles: true,
    cancelable: true,
    key: "k",
    ...init,
  });
  act(() => {
    target.dispatchEvent(event);
  });
}

describe("useCommandPaletteShortcut", () => {
  it("calls onToggle on Ctrl+K", () => {
    const onToggle = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(<Probe onToggle={onToggle} />);
    });

    dispatchKey({ ctrlKey: true });

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("calls onToggle on Cmd+K (metaKey)", () => {
    const onToggle = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(<Probe onToggle={onToggle} />);
    });

    dispatchKey({ metaKey: true });

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("does not trigger for K without a modifier", () => {
    const onToggle = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(<Probe onToggle={onToggle} />);
    });

    dispatchKey({});

    expect(onToggle).not.toHaveBeenCalled();
  });

  it("does not trigger while typing in a text input", () => {
    const onToggle = vi.fn();
    const input = document.createElement("input");
    document.body.appendChild(input);

    act(() => {
      root = createRoot(container);
      root.render(<Probe onToggle={onToggle} />);
    });

    dispatchKey({ ctrlKey: true }, input);

    expect(onToggle).not.toHaveBeenCalled();
    input.remove();
  });

  it("does not trigger while typing in a textarea", () => {
    const onToggle = vi.fn();
    const textarea = document.createElement("textarea");
    document.body.appendChild(textarea);

    act(() => {
      root = createRoot(container);
      root.render(<Probe onToggle={onToggle} />);
    });

    dispatchKey({ ctrlKey: true }, textarea);

    expect(onToggle).not.toHaveBeenCalled();
    textarea.remove();
  });

  it("removes its listener on unmount", () => {
    const onToggle = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(<Probe onToggle={onToggle} />);
    });

    act(() => {
      root.unmount();
    });
    // afterEach will also call root.unmount(); make it a no-op here
    // by re-creating an (unused) root so afterEach's unmount is safe.
    act(() => {
      root = createRoot(container);
    });

    dispatchKey({ ctrlKey: true });

    expect(onToggle).not.toHaveBeenCalled();
  });

  it("does not register a duplicate listener under React Strict Mode", () => {
    const onToggle = vi.fn();
    act(() => {
      root = createRoot(container);
      root.render(
        <StrictMode>
          <Probe onToggle={onToggle} />
        </StrictMode>,
      );
    });

    dispatchKey({ ctrlKey: true });

    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});
