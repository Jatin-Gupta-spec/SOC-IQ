// @vitest-environment jsdom
/**
 * `useSettingsBeforeUnloadGuard` tests -- SOC-IQ MAX-18 Phase 2A-5
 * (MAX18-F-01, browser `beforeunload` protection).
 *
 * Same `Probe`/`createRoot`/`act` convention as
 * `useSettingsNavigationGuardSync.test.tsx`. Covers exactly the
 * lifecycle the task brief's "Testing" section enumerates:
 *
 *   1. clean -> no listener
 *   2. dirty -> listener registered
 *   3. dirty -> repeated renders do not duplicate the listener
 *   4. dirty -> clean removes the listener
 *   5. unmount removes the listener
 *   6. remount behaves correctly
 *   7. multiple dirty controls still produce one effective browser
 *      guard
 *
 * What this file deliberately does NOT attempt: asserting that a real
 * native "leave site?" browser dialog appears, is suppressed, or
 * shows any particular text. jsdom implements `beforeunload` as a
 * dispatchable event, but -- like every headless DOM implementation
 * -- has no browser chrome and does not implement the real
 * unload-cancellation behavior a browser performs in response to
 * `preventDefault()`/`returnValue`. That is a permanent limitation of
 * jsdom/Vitest, not a gap in this hook; see
 * `useSettingsBeforeUnloadGuard.ts`'s own doc comment for the full
 * accounting.
 *
 * A related, narrower jsdom quirk shaped how "does the handler
 * actually intercept" is asserted below: per the DOM spec, a plain
 * `Event`'s `returnValue` getter reflects the boolean canceled flag
 * (`!defaultPrevented`), not whatever value was last assigned to it --
 * so dispatching a real `Event` and reading `.returnValue` back can
 * only ever observe `true`/`false`, never the literal empty string
 * this hook assigns for legacy-engine compatibility. Rather than
 * assert something jsdom cannot faithfully represent, the tests below
 * capture the exact listener function passed to
 * `window.addEventListener` and invoke it directly with a
 * purpose-built mock event object whose `returnValue` is a plain
 * writable property -- this verifies both effects the hook's handler
 * actually performs (`preventDefault()` called; `returnValue` set to
 * `""`) precisely, without relying on jsdom's `Event` semantics for
 * either. What *is* verified here, mechanically, is (a) the
 * listener's registration/removal lifecycle via spies on
 * `window.addEventListener`/`window.removeEventListener` filtered to
 * the `"beforeunload"` event type, and (b) that the registered
 * handler, when invoked, calls `preventDefault()` and sets
 * `returnValue` to `""`, exactly when `settingsDirty` is `true`.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockInstance,
} from "vitest";

import { useSettingsBeforeUnloadGuard } from "./useSettingsBeforeUnloadGuard";

let container: HTMLDivElement;
let root: Root;
let addSpy: MockInstance<typeof window.addEventListener>;
let removeSpy: MockInstance<typeof window.removeEventListener>;

function Probe({ dirty }: { readonly dirty: boolean }) {
  useSettingsBeforeUnloadGuard(dirty);
  return <div>{String(dirty)}</div>;
}

/** Counts only `"beforeunload"` registrations/removals -- jsdom's own
 * test harness and other application code may add unrelated listeners
 * for other event types on `window`, and those must not be conflated
 * with what this hook itself does. */
function beforeUnloadAddCalls(): number {
  return addSpy.mock.calls.filter(([type]) => type === "beforeunload").length;
}

function beforeUnloadRemoveCalls(): number {
  return removeSpy.mock.calls.filter(([type]) => type === "beforeunload")
    .length;
}

/** Returns the most recently registered `"beforeunload"` listener
 * function, or `undefined` if none is currently registered (i.e. the
 * last lifecycle event for it was a removal, or none was ever added).
 * Looking at add/remove call order directly -- rather than trusting a
 * running "is one registered" boolean this file would have to
 * maintain by hand -- keeps this helper honest about what actually
 * happened on `window`. */
function currentBeforeUnloadHandler(): ((event: MockBeforeUnloadEvent) => void) | undefined {
  const addedTypes = addSpy.mock.calls.filter(([type]) => type === "beforeunload");
  const removedCount = beforeUnloadRemoveCalls();
  const stillRegistered = addedTypes.slice(removedCount);
  const last = stillRegistered[stillRegistered.length - 1];
  return last?.[1] as ((event: MockBeforeUnloadEvent) => void) | undefined;
}

interface MockBeforeUnloadEvent {
  preventDefault: () => void;
  returnValue: unknown;
}

/** Invokes the currently registered handler (if any) with a
 * purpose-built mock event whose `returnValue` is a plain writable
 * property -- see this file's own doc comment for why a real jsdom
 * `Event` cannot be used to observe the literal string this hook
 * assigns. Returns `null` if no handler is currently registered,
 * mirroring "the browser guard did not fire". */
function invokeBeforeUnloadHandler(): { preventDefaultCalled: boolean; returnValue: unknown } | null {
  const handler = currentBeforeUnloadHandler();
  if (!handler) {
    return null;
  }
  let preventDefaultCalled = false;
  const event: MockBeforeUnloadEvent = {
    preventDefault: () => {
      preventDefaultCalled = true;
    },
    returnValue: true,
  };
  handler(event);
  return { preventDefaultCalled, returnValue: event.returnValue };
}

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  addSpy = vi.spyOn(window, "addEventListener");
  removeSpy = vi.spyOn(window, "removeEventListener");
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
  addSpy.mockRestore();
  removeSpy.mockRestore();
});

function render(dirty: boolean): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe dirty={dirty} />);
  });
}

function rerender(dirty: boolean): void {
  act(() => {
    root.render(<Probe dirty={dirty} />);
  });
}

describe("1. clean -> no listener", () => {
  it("does not register a beforeunload listener while clean", () => {
    render(false);
    expect(beforeUnloadAddCalls()).toBe(0);
  });

  it("has no handler to invoke while clean", () => {
    render(false);
    expect(invokeBeforeUnloadHandler()).toBeNull();
  });
});

describe("2. dirty -> listener registered", () => {
  it("registers exactly one beforeunload listener once dirty", () => {
    render(true);
    expect(beforeUnloadAddCalls()).toBe(1);
  });

  it("the registered handler prevents default and sets returnValue once dirty", () => {
    render(true);
    const result = invokeBeforeUnloadHandler();
    expect(result).not.toBeNull();
    expect(result?.preventDefaultCalled).toBe(true);
    expect(result?.returnValue).toBe("");
  });
});

describe("3. dirty -> repeated renders do not duplicate the listener", () => {
  it("re-rendering with the same dirty=true value adds no further listener", () => {
    render(true);
    expect(beforeUnloadAddCalls()).toBe(1);

    rerender(true);
    rerender(true);
    rerender(true);

    expect(beforeUnloadAddCalls()).toBe(1);
    expect(beforeUnloadRemoveCalls()).toBe(0);
  });

  it("still only ever intercepts via a single handler after repeated renders", () => {
    render(true);
    rerender(true);
    rerender(true);

    // The count assertion above is the direct signal that no
    // duplicate was added; this additionally confirms the one
    // handler that IS registered still behaves correctly after
    // several no-op re-renders, not just that the count looks right.
    const result = invokeBeforeUnloadHandler();
    expect(result?.preventDefaultCalled).toBe(true);
    expect(result?.returnValue).toBe("");
  });
});

describe("4. dirty -> clean removes the listener", () => {
  it("removes the listener when settingsDirty flips to false", () => {
    render(true);
    expect(beforeUnloadAddCalls()).toBe(1);

    rerender(false);

    expect(beforeUnloadRemoveCalls()).toBe(1);
  });

  it("has no handler to invoke once clean again", () => {
    render(true);
    rerender(false);

    expect(invokeBeforeUnloadHandler()).toBeNull();
  });

  it("going dirty -> clean -> dirty again registers a fresh single listener", () => {
    render(true);
    rerender(false);
    rerender(true);

    expect(beforeUnloadAddCalls()).toBe(2);
    expect(beforeUnloadRemoveCalls()).toBe(1);

    const result = invokeBeforeUnloadHandler();
    expect(result?.preventDefaultCalled).toBe(true);
  });
});

describe("5. unmount removes the listener", () => {
  it("removes the listener on unmount while dirty", () => {
    render(true);
    expect(beforeUnloadAddCalls()).toBe(1);

    act(() => {
      root.unmount();
    });

    expect(beforeUnloadRemoveCalls()).toBe(1);
  });

  it("does not attempt removal on unmount if never registered (clean)", () => {
    render(false);

    act(() => {
      root.unmount();
    });

    expect(beforeUnloadRemoveCalls()).toBe(0);
  });

  it("has no handler to invoke after unmount", () => {
    render(true);
    act(() => {
      root.unmount();
    });

    expect(invokeBeforeUnloadHandler()).toBeNull();
  });
});

describe("6. remount behaves correctly", () => {
  it("a fresh mount after a dirty unmount starts clean (no stale listener)", () => {
    render(true);
    act(() => {
      root.unmount();
    });
    container.remove();

    // Fresh container + root, mirroring a real remount of SettingsPage.
    container = document.createElement("div");
    document.body.appendChild(container);
    render(false);

    expect(beforeUnloadAddCalls()).toBe(1); // only the first mount's registration
    expect(invokeBeforeUnloadHandler()).toBeNull();
  });

  it("a fresh mount that starts dirty registers its own single listener", () => {
    render(true);
    act(() => {
      root.unmount();
    });
    container.remove();

    container = document.createElement("div");
    document.body.appendChild(container);
    render(true);

    expect(beforeUnloadAddCalls()).toBe(2); // one per mount
    const result = invokeBeforeUnloadHandler();
    expect(result?.preventDefaultCalled).toBe(true);
  });
});

describe("7. multiple dirty controls still produce one effective browser guard", () => {
  it("a settingsDirty aggregate that is true because of several controls still yields one listener", () => {
    // This hook only ever sees the already-aggregated boolean
    // (computeSettingsDirty's OR of the three per-control flags, per
    // Phase 2A-1/2A-2) -- there is no per-control registration path
    // here to multiply. Simulating "two controls dirty at once" is
    // simply rendering with settingsDirty=true; the aggregate does
    // not carry how many underlying controls contributed to it.
    render(true);
    expect(beforeUnloadAddCalls()).toBe(1);

    // One control becoming clean while another remains dirty keeps
    // the aggregate true -- still exactly one listener, no re-add.
    rerender(true);
    expect(beforeUnloadAddCalls()).toBe(1);

    // Only once every control is clean does the aggregate go false
    // and the single listener come off.
    rerender(false);
    expect(beforeUnloadRemoveCalls()).toBe(1);
  });
});

describe("no secret exposure", () => {
  it("returnValue is always the fixed empty string, never derived from any field value", () => {
    render(true);
    const result = invokeBeforeUnloadHandler();
    expect(result?.returnValue).toBe("");
  });
});
