// @vitest-environment jsdom
/**
 * Phase 4G-2 Part 2 — live navigation behavior tests.
 *
 * §23 says: don't add a testing dependency automatically, but if one
 * is genuinely required, prove why and report it. This is that case.
 * `renderToStaticMarkup` (every other test file in this checkpoint,
 * matching Part 1's approach) can't observe click-driven navigation
 * or the "/" → "/dashboard" redirect: both `NavLink`'s click handling
 * and `<Navigate>`'s redirect are implemented with
 * `useLayoutEffect`/event handlers, which are no-ops under static
 * server rendering (confirmed directly: a `<Navigate>` redirect
 * renders as empty output under `renderToStaticMarkup`). Proving §11
 * ("clicking navigation updates the destination") and §22's "verify
 * navigation changes the actual route/navigation state" honestly
 * requires a real DOM.
 *
 * `jsdom` was added as the one new devDependency this checkpoint
 * needs (see the Part 2 report). Deliberately not
 * `@testing-library/react` on top of it — `react-dom/client` +
 * native `dispatchEvent` are enough for the handful of assertions
 * here, so no second dependency was added for convenience. This is
 * the only file in the checkpoint using the jsdom environment (see
 * the `@vitest-environment` pragma above); every other test keeps
 * the project's existing default (node) environment.
 *
 * Updated for Phase 4G-2 Part 3: routes render real pages now, so
 * the `"... page placeholder"` assertions (Part 2) are replaced with
 * `"... page"` — the accessible name each page's `PageLayout`
 * `<main>` landmark now carries.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { NAVIGATION_ITEMS } from "./navigation/navigationModel";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
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

function clickLink(label: string): void {
  const link = Array.from(container.querySelectorAll("a")).find(
    (anchor) => anchor.getAttribute("aria-label") === label,
  );
  if (!link) {
    throw new Error(`No nav link found with aria-label "${label}"`);
  }
  act(() => {
    link.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }),
    );
  });
}

describe("App navigation (live DOM)", () => {
  it("redirects from the root route to the Dashboard placeholder", () => {
    expect(container.querySelector('[aria-label="Dashboard page"]')).not.toBeNull();
  });

  it.each(NAVIGATION_ITEMS.map((item) => [item.label, item.ariaLabel ?? item.label] as const))(
    "clicking %s navigates to its route and marks it active",
    (label, ariaLabel) => {
      clickLink(ariaLabel);

      const placeholder = container.querySelector(
        `[aria-label="${label} page"]`,
      );
      expect(placeholder).not.toBeNull();

      const activeLink = container.querySelector('a[aria-current="page"]');
      expect(activeLink?.getAttribute("aria-label")).toBe(ariaLabel);
    },
  );

  it("only ever marks one navigation link as active at a time", () => {
    clickLink("Reports");
    const activeLinks = container.querySelectorAll('a[aria-current="page"]');
    expect(activeLinks).toHaveLength(1);
  });
});
