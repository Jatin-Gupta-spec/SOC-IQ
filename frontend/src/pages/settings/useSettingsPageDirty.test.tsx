// @vitest-environment jsdom
/**
 * `useSettingsPageDirty` tests -- SOC-IQ MAX-18 Phase 2A-2
 * (MAX18-F-01, Settings dirty-state aggregation).
 *
 * Same `Probe`/`createRoot`/`act` convention as
 * `useVirustotalKeySave.test.tsx` and `useSettingsFieldSave.test.tsx`.
 * `computeSettingsDirty` itself is already exhaustively tested in
 * isolation by `settingsDirty.test.ts`; this file's job is narrower:
 * proving the hook actually holds the three flags correctly, that
 * each handler only ever touches its own flag, and that the exposed
 * `settingsDirty` re-derives correctly across every required
 * combination and transition.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useSettingsPageDirty } from "./useSettingsPageDirty";
import type { UseSettingsPageDirtyResult } from "./useSettingsPageDirty";

let container: HTMLDivElement;
let root: Root;
let latestResult: UseSettingsPageDirtyResult;

function Probe() {
  latestResult = useSettingsPageDirty();
  return <div>{String(latestResult.settingsDirty)}</div>;
}

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

function render(): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe />);
  });
}

describe("initial state", () => {
  it("starts clean -- settingsDirty is false with no control touched", () => {
    render();

    expect(latestResult.settingsDirty).toBe(false);
  });
});

describe("required combination matrix", () => {
  it("clean / clean / clean -> clean", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(false);
      latestResult.handleExportDirectoryDirtyChange(false);
      latestResult.handleVirustotalKeyDirtyChange(false);
    });

    expect(latestResult.settingsDirty).toBe(false);
  });

  it("dirty / clean / clean -> dirty", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(true);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });

  it("clean / dirty / clean -> dirty", () => {
    render();

    act(() => {
      latestResult.handleExportDirectoryDirtyChange(true);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });

  it("clean / clean / dirty -> dirty", () => {
    render();

    act(() => {
      latestResult.handleVirustotalKeyDirtyChange(true);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });

  it("dirty / dirty / clean -> dirty", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleExportDirectoryDirtyChange(true);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });

  it("dirty / clean / dirty -> dirty", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleVirustotalKeyDirtyChange(true);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });

  it("clean / dirty / dirty -> dirty", () => {
    render();

    act(() => {
      latestResult.handleExportDirectoryDirtyChange(true);
      latestResult.handleVirustotalKeyDirtyChange(true);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });

  it("dirty / dirty / dirty -> dirty", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleExportDirectoryDirtyChange(true);
      latestResult.handleVirustotalKeyDirtyChange(true);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });
});

describe("per-flag independence", () => {
  it("clearing only the Theme flag while the others stay dirty keeps the aggregate dirty", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleExportDirectoryDirtyChange(true);
      latestResult.handleVirustotalKeyDirtyChange(true);
    });
    act(() => {
      latestResult.handleThemeDirtyChange(false);
    });

    expect(latestResult.settingsDirty).toBe(true);
  });

  it("returns to clean only once every flag has returned to false", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleExportDirectoryDirtyChange(true);
      latestResult.handleVirustotalKeyDirtyChange(true);
    });

    act(() => {
      latestResult.handleThemeDirtyChange(false);
    });
    expect(latestResult.settingsDirty).toBe(true);

    act(() => {
      latestResult.handleExportDirectoryDirtyChange(false);
    });
    expect(latestResult.settingsDirty).toBe(true);

    act(() => {
      latestResult.handleVirustotalKeyDirtyChange(false);
    });
    expect(latestResult.settingsDirty).toBe(false);
  });

  it("calling one handler repeatedly never affects the other two flags", () => {
    render();

    act(() => {
      latestResult.handleExportDirectoryDirtyChange(true);
    });
    act(() => {
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleThemeDirtyChange(false);
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleThemeDirtyChange(false);
    });

    // Export Directory was never touched by any of those Theme calls.
    expect(latestResult.settingsDirty).toBe(true);

    act(() => {
      latestResult.handleExportDirectoryDirtyChange(false);
    });
    expect(latestResult.settingsDirty).toBe(false);
  });
});

describe("fresh mount", () => {
  it("a new hook instance never inherits a previous instance's dirty state", () => {
    render();

    act(() => {
      latestResult.handleThemeDirtyChange(true);
      latestResult.handleExportDirectoryDirtyChange(true);
      latestResult.handleVirustotalKeyDirtyChange(true);
    });
    expect(latestResult.settingsDirty).toBe(true);

    act(() => {
      root.unmount();
    });
    act(() => {
      root = createRoot(container);
      root.render(<Probe />);
    });

    expect(latestResult.settingsDirty).toBe(false);
  });
});
