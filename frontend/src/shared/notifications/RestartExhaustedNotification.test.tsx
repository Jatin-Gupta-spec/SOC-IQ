/**
 * Static/presentational tests for `RestartExhaustedNotification`
 * (Phase 4G-4 Part 1).
 *
 * Uses `renderToStaticMarkup`, matching
 * `SidecarStatusIndicator.test.tsx`'s own no-jsdom-by-default
 * convention for pure presentational assertions. Every state is
 * driven through a real, isolated `RestartExhaustedNotificationStore`
 * (constructed with its own isolated `SidecarProjectionStore`)
 * rather than the shared singletons — live-store wiring and dismiss
 * interaction are covered separately in
 * `RestartExhaustedNotification.live.test.tsx`.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SidecarProjectionStore } from "../sidecar/projectionStore";
import type { SidecarStatus } from "../sidecar/types";
import { RestartExhaustedNotificationStore } from "./restartExhaustedNotificationStore";
import { RestartExhaustedNotification } from "./RestartExhaustedNotification";

function status(overrides: Partial<SidecarStatus> = {}): SidecarStatus {
  return {
    state: "RUNNING",
    restart_pending: false,
    restart_pending_attempt: null,
    restart_attempts: 0,
    restart_exhausted: false,
    sequence: 1,
    ...overrides,
  };
}

function exhaustedStore(
  overrides: Partial<SidecarStatus> = {},
): RestartExhaustedNotificationStore {
  const source = new SidecarProjectionStore();
  source.applyProjectedState(status({ restart_exhausted: true, ...overrides }));
  const notification = new RestartExhaustedNotificationStore({ source });
  notification.initialize();
  return notification;
}

function hiddenStore(): RestartExhaustedNotificationStore {
  const source = new SidecarProjectionStore();
  const notification = new RestartExhaustedNotificationStore({ source });
  notification.initialize();
  return notification;
}

describe("renders nothing when hidden (task brief §11)", () => {
  it("renders no DOM output when the notification is not visible", () => {
    const html = renderToStaticMarkup(
      <RestartExhaustedNotification store={hiddenStore()} />,
    );
    expect(html).toBe("");
  });
});

describe("accessible content when visible (task brief §8)", () => {
  it("renders without throwing", () => {
    expect(() =>
      renderToStaticMarkup(
        <RestartExhaustedNotification store={exhaustedStore()} />,
      ),
    ).not.toThrow();
  });

  it("uses role=alert -- an assertive live region for a hard failure the person needs to know about", () => {
    const html = renderToStaticMarkup(
      <RestartExhaustedNotification store={exhaustedStore()} />,
    );
    expect(html).toContain('role="alert"');
  });

  it("carries meaning in visible text, not color alone", () => {
    const html = renderToStaticMarkup(
      <RestartExhaustedNotification store={exhaustedStore()} />,
    );
    expect(html).toContain("Sidecar restart attempts exhausted");
    expect(html).toContain(
      "automatic restart attempts have been exhausted",
    );
  });

  it("the dismiss control has a real accessible name, not an icon-only affordance", () => {
    const html = renderToStaticMarkup(
      <RestartExhaustedNotification store={exhaustedStore()} />,
    );
    expect(html).toContain("aria-label=");
    expect(html).toContain("Dismiss sidecar restart-exhausted notification");
  });

  it("reuses the existing motion utility class rather than inventing a new transition", () => {
    const html = renderToStaticMarkup(
      <RestartExhaustedNotification store={exhaustedStore()} />,
    );
    expect(html).toContain("transition-fade");
  });
});
