import { describe, expect, it } from "vitest";

import type { SidecarStatus } from "./types";
import { projectSidecarStatusView } from "./sidecarStatusView";

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

describe("projectSidecarStatusView", () => {
  it("projects null (no snapshot yet) as unknown", () => {
    expect(projectSidecarStatusView(null)).toBe("unknown");
  });

  it("projects STARTING as starting", () => {
    expect(projectSidecarStatusView(status({ state: "STARTING" }))).toBe(
      "starting",
    );
  });

  it("projects RUNNING as connected", () => {
    expect(projectSidecarStatusView(status({ state: "RUNNING" }))).toBe(
      "connected",
    );
  });

  it.each(["NOT_STARTED", "STOPPING", "STOPPED"] as const)(
    "projects %s as disconnected",
    (state) => {
      expect(projectSidecarStatusView(status({ state }))).toBe(
        "disconnected",
      );
    },
  );

  it.each(["CRASHED", "FAILED", "TIMEOUT"] as const)(
    "projects %s as failure",
    (state) => {
      expect(projectSidecarStatusView(status({ state }))).toBe("failure");
    },
  );

  it("projects a pending restart as restarting even while CRASHED", () => {
    const view = projectSidecarStatusView(
      status({ state: "CRASHED", restart_pending: true, restart_pending_attempt: 1 }),
    );

    expect(view).toBe("restarting");
  });

  it("projects restart_exhausted as failure, taking precedence over a stale restart_pending flag", () => {
    const view = projectSidecarStatusView(
      status({
        state: "CRASHED",
        restart_pending: true,
        restart_pending_attempt: 3,
        restart_exhausted: true,
      }),
    );

    expect(view).toBe("failure");
  });

  it("does not treat RUNNING with restart_pending false / restart_exhausted false as anything but connected", () => {
    const view = projectSidecarStatusView(
      status({ state: "RUNNING", restart_pending: false, restart_exhausted: false }),
    );

    expect(view).toBe("connected");
  });

  it("falls back to unknown for an unrecognized future backend state, without throwing", () => {
    const futureStatus = status({
      // Intentionally invalid cast — simulates a backend FSM value
      // this frontend has not been updated for yet (task brief §8).
      state: "SOMETHING_FUTURE" as unknown as SidecarStatus["state"],
    });

    expect(() => projectSidecarStatusView(futureStatus)).not.toThrow();
    expect(projectSidecarStatusView(futureStatus)).toBe("unknown");
  });
});
