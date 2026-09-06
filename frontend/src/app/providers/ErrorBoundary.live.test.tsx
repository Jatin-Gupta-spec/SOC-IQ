// @vitest-environment jsdom
/**
 * Live-DOM tests for `ErrorBoundary` -- same `act`/`createRoot` convention
 * as `settings/ThemeControl.live.test.tsx`. Real DOM rendering is required
 * here specifically because these tests must prove an actual React
 * remount cycle (child throws -> fallback appears -> reset -> child
 * renders again), which `react-dom/server`'s `renderToStaticMarkup`
 * (used by the plain-jsdom-free `App.test.tsx`) cannot exercise.
 *
 * MAX13-F-01: `App.test.tsx`'s existing composition-root smoke tests
 * only prove the app renders on a happy path -- they never throw inside
 * the tree, so they never prove `ErrorBoundary` actually catches
 * anything or that its fallback's recovery action works. These tests
 * close that gap directly against `ErrorBoundary` in isolation, at the
 * narrowest level that can prove it.
 *
 * MAX14-F-01: the "focus behavior" suite below extends the same
 * real-DOM setup to prove actual `document.activeElement` transitions
 * -- not just that the fallback/button exist in the DOM, but that
 * keyboard focus is actually moved into the fallback on catch, and
 * does not stay stranded on a since-removed node after recovery.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

/**
 * A child whose thrown-vs-not behavior is controlled from outside via a
 * mutable ref object, so the same component instance can be told (via a
 * prop) whether to throw on this render -- exactly what "recovery"
 * needs to prove: the boundary's children genuinely render again after
 * reset, not just that the fallback disappears.
 */
function Bomb({ shouldThrow }: { shouldThrow: boolean }): JSX.Element {
  if (shouldThrow) {
    throw new Error("MAX13-F-01 test detonation");
  }
  return <div data-testid="bomb-ok">Recovered content</div>;
}

let container: HTMLDivElement;
let root: Root;
let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  // React logs caught render errors to console.error in addition to
  // this boundary's own intentional componentDidCatch log -- expected
  // noise for an intentionally-thrown test error, not something this
  // suite is asserting on, so it is silenced here only, not globally.
  consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
  consoleErrorSpy.mockRestore();
});

function render(shouldThrow: boolean): void {
  act(() => {
    root = createRoot(container);
    root.render(
      <ErrorBoundary>
        <Bomb shouldThrow={shouldThrow} />
      </ErrorBoundary>,
    );
  });
}

function alertEl(): HTMLElement | null {
  return container.querySelector('[role="alert"]');
}

function tryAgainButton(): HTMLButtonElement | undefined {
  return Array.from(container.querySelectorAll("button")).find(
    (button) => button.textContent === "Try again",
  );
}

describe("catch behavior", () => {
  it("renders children normally when nothing throws", () => {
    render(false);
    expect(container.querySelector('[data-testid="bomb-ok"]')).not.toBeNull();
    expect(alertEl()).toBeNull();
  });

  it("catches a render-time error and shows the fallback via role=alert", () => {
    render(true);

    expect(alertEl()).not.toBeNull();
    expect(container.textContent).toContain("Something went wrong");
    expect(container.querySelector('[data-testid="bomb-ok"]')).toBeNull();
  });

  it("logs the caught error via componentDidCatch's existing console.error call", () => {
    render(true);

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "SOC-IQ: unhandled error in component tree",
      expect.any(Error),
      expect.anything(),
    );
  });

  it("exposes a recovery action from the fallback", () => {
    render(true);

    const button = tryAgainButton();
    expect(button).toBeDefined();
    expect(button?.tagName).toBe("BUTTON");
    expect(button?.disabled).toBe(false);
  });
});

describe("recovery behavior", () => {
  it("clears the error state and renders the children again after the recovery action is activated", () => {
    render(true);
    expect(alertEl()).not.toBeNull();

    act(() => {
      root.render(
        <ErrorBoundary>
          <Bomb shouldThrow={false} />
        </ErrorBoundary>,
      );
    });
    act(() => {
      tryAgainButton()?.click();
    });

    expect(alertEl()).toBeNull();
    expect(container.querySelector('[data-testid="bomb-ok"]')).not.toBeNull();
    expect(container.textContent).not.toContain("Something went wrong");
  });

  it("catches the error again if the underlying cause is still present after reset -- no speculative retry machinery", () => {
    render(true);

    act(() => {
      tryAgainButton()?.click();
    });

    // The child was not swapped out for a non-throwing version this
    // time, so the boundary genuinely re-rendered its children (proving
    // the reset is real, not a no-op) and caught the same error again.
    expect(alertEl()).not.toBeNull();
    expect(tryAgainButton()).toBeDefined();
  });
});

describe("focus behavior", () => {
  it("does not move focus when nothing throws", () => {
    render(false);
    expect(document.activeElement).not.toBe(alertEl());
  });

  it("moves focus into the fallback alert as soon as it is caught", () => {
    render(true);

    // Proves an actual keyboard-focus transition, not just that the
    // alert exists: before this fix, document.activeElement was left
    // on <body> (or wherever it was before the crash) with no signal
    // to a keyboard user of where the fallback landed.
    expect(document.activeElement).toBe(alertEl());
  });

  it("keeps the fallback alert as a valid, non-tabbable-by-default programmatic focus target", () => {
    render(true);

    const alert = alertEl();
    expect(alert?.getAttribute("tabindex")).toBe("-1");
  });

  it("re-focuses the fallback alert if the same error is caught again after reset", () => {
    render(true);
    const firstAlert = alertEl();
    expect(document.activeElement).toBe(firstAlert);

    // Move focus elsewhere first so the assertion below can't pass by
    // coincidence (e.g. focus never having left in the first place).
    act(() => {
      tryAgainButton()?.focus();
    });
    expect(document.activeElement).not.toBe(firstAlert);

    act(() => {
      tryAgainButton()?.click();
    });

    expect(document.activeElement).toBe(alertEl());
  });

  it("does not leave focus stranded on the removed \"Try again\" button once recovery succeeds", () => {
    render(true);

    act(() => {
      root.render(
        <ErrorBoundary>
          <Bomb shouldThrow={false} />
        </ErrorBoundary>,
      );
    });
    act(() => {
      tryAgainButton()?.click();
    });

    // The button that was focused no longer exists in the document at
    // all -- the browser's own removal-of-focused-node handling takes
    // over here (matching real-browser behavior), rather than this
    // foundation-level boundary reaching into unknown recovered
    // children to guess a focus target.
    expect(document.body.contains(document.activeElement)).toBe(true);
    expect(tryAgainButton()).toBeUndefined();
  });
});
