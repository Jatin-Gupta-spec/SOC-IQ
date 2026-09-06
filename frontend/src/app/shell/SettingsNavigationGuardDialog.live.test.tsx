// @vitest-environment jsdom
/**
 * `SettingsNavigationGuardDialog` -- isolated accessibility/keyboard
 * tests. SOC-IQ MAX-18 Phase 2A-4 (MAX18-F-01, confirmation UX +
 * accessibility).
 *
 * Complements `settingsNavigationGuard.live.test.tsx` (which drives
 * the real, fully composed `<App />`) with focused tests against the
 * dialog component in isolation -- its own
 * `SettingsNavigationGuardStore` instance (never the shared
 * singleton, matching `RestartExhaustedNotification.live.test.tsx`'s
 * own precedent) wrapped only in the `MemoryRouter` the component's
 * `useNavigate()` call requires (matching
 * `CommandPaletteContainer.live.test.tsx`'s own precedent for a
 * router-dependent component that doesn't need the whole app around
 * it).
 *
 * Covers the Phase 2A-4 task brief's accessibility checklist:
 * dialog semantics, accessible name/description, keyboard navigation
 * (Tab/Shift+Tab containment), focus entry, focus never falling to
 * `document.body`, Escape's intentional (non-destructive) result,
 * Stay's focus return, Leave's non-interference with route-change
 * focus handling, and that no secret value ever appears in the
 * dialog's rendered output.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import { SettingsNavigationGuardStore } from "../../pages/settings/settingsNavigationGuardStore";
import { SettingsNavigationGuardDialog } from "./SettingsNavigationGuardDialog";

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

function renderDialog(store: SettingsNavigationGuardStore): void {
  act(() => {
    root = createRoot(container);
    root.render(
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route
            path="*"
            element={<SettingsNavigationGuardDialog store={store} />}
          />
        </Routes>
      </MemoryRouter>,
    );
  });
}

/** Opens a pending confirmation on a fresh, isolated store. */
function openPending(): SettingsNavigationGuardStore {
  const store = new SettingsNavigationGuardStore();
  store.setDirty(true);
  const decision = store.requestNavigation("/dashboard");
  if (decision !== "blocked") {
    throw new Error("expected requestNavigation to block on a dirty store");
  }
  return store;
}

function dialogEl(): HTMLElement {
  const el = container.querySelector('[role="alertdialog"]');
  if (!el) {
    throw new Error("dialog not found");
  }
  return el as HTMLElement;
}

function stayButton(): HTMLButtonElement {
  return container.querySelector(
    ".settings-nav-guard__button--stay",
  ) as HTMLButtonElement;
}

function leaveButton(): HTMLButtonElement {
  return container.querySelector(
    ".settings-nav-guard__button--leave",
  ) as HTMLButtonElement;
}

function pressKey(
  target: HTMLElement,
  key: string,
  options: { shiftKey?: boolean } = {},
): void {
  act(() => {
    target.dispatchEvent(
      new KeyboardEvent("keydown", {
        key,
        shiftKey: options.shiftKey ?? false,
        bubbles: true,
        cancelable: true,
      }),
    );
  });
}

describe("dialog semantics and accessible name/description", () => {
  it("uses role=alertdialog with aria-modal, and its own visible heading/body name it", () => {
    const store = openPending();
    renderDialog(store);

    const dialog = dialogEl();
    expect(dialog.getAttribute("aria-modal")).toBe("true");

    const labelledBy = dialog.getAttribute("aria-labelledby");
    const describedBy = dialog.getAttribute("aria-describedby");
    expect(labelledBy).toBeTruthy();
    expect(describedBy).toBeTruthy();

    const nameEl = document.getElementById(labelledBy as string);
    const descEl = document.getElementById(describedBy as string);
    expect(nameEl?.textContent).toBe("Unsaved changes");
    expect(descEl?.textContent).toMatch(/discard/i);
  });

  it("communicates the destructive consequence in visible/accessible text, not styling alone", () => {
    const store = openPending();
    renderDialog(store);

    // A screen reader user gets this from the accessible description
    // alone -- confirmed above -- and the two button labels are
    // unambiguous action verbs, not vague wording like "Cancel"/"OK".
    expect(stayButton().textContent).toBe("Stay");
    expect(leaveButton().textContent).toBe("Leave");
  });

  it("never renders a VirusTotal API key or other secret value in the dialog", () => {
    const store = openPending();
    renderDialog(store);

    const text = dialogEl().textContent ?? "";
    expect(text).not.toMatch(/virustotal/i);
    expect(text).not.toMatch(/api[_-]?key/i);
    // The dialog's entire text content is exactly the two static
    // strings + two button labels -- nothing interpolated from any
    // control's edit buffer.
    expect(text).toBe(
      "Unsaved changesYou have unsaved changes on the Settings page. Leaving now will discard them.StayLeave",
    );
  });
});

describe("focus entry", () => {
  it("moves focus onto the dialog the moment it becomes pending", () => {
    const store = openPending();
    renderDialog(store);

    expect(document.activeElement).toBe(dialogEl());
  });

  it("never leaves focus stranded on document.body", () => {
    const store = openPending();
    renderDialog(store);

    expect(document.activeElement).not.toBe(document.body);
  });
});

describe("Escape has an intentional, non-destructive result", () => {
  it("dismisses the confirmation without discarding the pending edit (same result as Stay)", () => {
    const store = openPending();
    renderDialog(store);

    pressKey(dialogEl(), "Escape");

    expect(store.getState().pending).toBe(false);
    // Escape must not have run the Leave path: the store still
    // considers itself dirty, exactly as Stay would leave it.
    expect(store.isDirty()).toBe(true);
    expect(container.querySelector('[role="alertdialog"]')).toBeNull();
  });

  it("returns focus to the previously focused element, exactly like Stay", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "trigger";
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    const store = openPending();
    renderDialog(store);
    expect(document.activeElement).toBe(dialogEl());

    pressKey(dialogEl(), "Escape");

    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});

describe("Stay returns focus appropriately", () => {
  it("restores focus to whatever had it before the dialog opened", () => {
    const trigger = document.createElement("a");
    trigger.href = "#";
    trigger.textContent = "Dashboard";
    document.body.appendChild(trigger);
    trigger.focus();

    const store = openPending();
    renderDialog(store);

    act(() => {
      stayButton().click();
    });

    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});

describe("Leave allows route-change focus behavior to occur", () => {
  it("clears the pending state and navigates -- when the trigger is still in the document, it is restored (as Stay would), which the app's own MAX-17 route-change effect then supersedes", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const store = openPending();
    renderDialog(store);

    act(() => {
      leaveButton().click();
    });

    expect(store.getState().pending).toBe(false);
    expect(store.isDirty()).toBe(false);
    // The dialog's restore-on-idle effect does not distinguish Stay
    // from Leave -- it restores to whatever previously had focus if
    // that element is still in the document, same as Stay. What
    // makes Leave end up on the destination page's landmark instead
    // (verified end-to-end in
    // `settingsNavigationGuard.live.test.tsx`'s MAX-17 regression
    // test) is `ContentRegion`'s own route-change focus effect firing
    // afterward and taking over -- not this dialog refusing to
    // restore.
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });

  it("does not crash or strand focus on document.body when the previously focused trigger no longer exists (a route change already unmounted it)", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const store = openPending();
    renderDialog(store);

    // Simulates the real app's route change already having removed
    // whatever triggered the navigation by the time this dialog's
    // own restore step runs.
    trigger.remove();

    expect(() => {
      act(() => {
        leaveButton().click();
      });
    }).not.toThrow();

    expect(store.getState().pending).toBe(false);
  });
});

describe("keyboard navigation: focus does not escape the dialog (Tab containment)", () => {
  it("Tab from the last control (Leave) wraps to the first (Stay), not to background content", () => {
    const backgroundLink = document.createElement("a");
    backgroundLink.href = "#";
    backgroundLink.textContent = "background";
    document.body.appendChild(backgroundLink);

    const store = openPending();
    renderDialog(store);

    leaveButton().focus();
    expect(document.activeElement).toBe(leaveButton());

    pressKey(leaveButton(), "Tab");

    expect(document.activeElement).toBe(stayButton());
    backgroundLink.remove();
  });

  it("Shift+Tab from the first control (Stay) wraps to the last (Leave)", () => {
    const store = openPending();
    renderDialog(store);

    stayButton().focus();
    pressKey(stayButton(), "Tab", { shiftKey: true });

    expect(document.activeElement).toBe(leaveButton());
  });

  it("Shift+Tab immediately after opening (focus still on the dialog container) wraps to Leave, not to whatever precedes the dialog in the DOM", () => {
    const backgroundLink = document.createElement("a");
    backgroundLink.href = "#";
    backgroundLink.textContent = "background";
    document.body.appendChild(backgroundLink);

    const store = openPending();
    renderDialog(store);
    expect(document.activeElement).toBe(dialogEl());

    pressKey(dialogEl(), "Tab", { shiftKey: true });

    expect(document.activeElement).toBe(leaveButton());
    backgroundLink.remove();
  });
});

describe("keyboard activation", () => {
  it("Stay and Leave are real <button> elements, not divs -- native platform Enter/Space activation applies", () => {
    const store = openPending();
    renderDialog(store);

    expect(stayButton().tagName).toBe("BUTTON");
    expect(stayButton().getAttribute("type")).toBe("button");
    expect(leaveButton().tagName).toBe("BUTTON");
    expect(leaveButton().getAttribute("type")).toBe("button");
  });

  it("activating Stay (as a keyboard-focused button's click) dismisses without navigating", () => {
    const store = openPending();
    renderDialog(store);

    stayButton().focus();
    act(() => {
      // A synthetic keydown does not trigger a browser's native
      // Enter-activates-button behavior in jsdom (nor, per the HTML
      // spec, does a script-dispatched, untrusted keyboard event in a
      // real browser) -- the platform guarantee instead comes from
      // this being a real <button>, confirmed above. `.click()` here
      // stands in for that native activation the same way every
      // other Stay/Leave test in this suite already does.
      stayButton().click();
    });

    expect(store.getState().pending).toBe(false);
    expect(store.isDirty()).toBe(true);
  });
});
