/**
 * `SettingsPage` tests -- real backend wiring (SOC-IQ Part 2B-1).
 *
 * `useSettings` is mocked at its own module boundary (mirroring
 * `InvestigationsPage.test.tsx`'s established `vi.mock` convention
 * for `useInvestigationsList`), so each load state can be driven
 * directly and deterministically -- this file tests the page's own
 * rendering/state-handling logic, not the fetch hook's behavior
 * (already covered by `settings/useSettings.test.tsx`) or the
 * per-field save behavior (already covered by
 * `settings/useSettingsFieldSave.test.tsx`,
 * `settings/ThemeControl.live.test.tsx`,
 * `settings/ExportDirectoryControl.live.test.tsx`).
 *
 * `renderToStaticMarkup`, matching `pages.test.tsx`'s existing
 * no-jsdom-by-default convention -- no effects run, so this
 * naturally exercises exactly the initial state `useSettings`
 * reports, without needing to await anything.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const useSettingsMock = vi.fn();

vi.mock("./settings/useSettings", () => ({
  useSettings: (...args: unknown[]) => useSettingsMock(...args),
}));

import { SettingsPage } from "./SettingsPage";
import type { UseSettingsResult } from "./settings/useSettings";
import type { GetSettingsResult } from "../shared/api/types";

const SETTINGS: GetSettingsResult = {
  theme: "Dark Mode (SOC-IQ Standard)",
  export_directory: "/home/analyst/output",
  virustotal_api_key_configured: true,
};

function makeResult(overrides: Partial<UseSettingsResult>): UseSettingsResult {
  return {
    state: "loading",
    settings: null,
    error: null,
    retry: vi.fn(),
    ...overrides,
  };
}

function render(): string {
  return renderToStaticMarkup(<SettingsPage />);
}

describe("SettingsPage", () => {
  describe("loading", () => {
    it("renders a loading state with no settings controls", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "loading" }));
      const html = render();

      expect(html).toContain("Loading settings");
      expect(html).not.toContain("settings-theme-select");
      expect(html).not.toContain("settings-export-directory");
    });

    it("renders a structural card skeleton, not fabricated controls (MAX-2)", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "loading" }));
      const html = render();

      expect(html).toContain("settings-page__skeleton");
      expect(html).toContain("settings-page__skeleton-card");
      expect(html).toContain('role="status"');
      expect(html).toContain('aria-live="polite"');
      expect(html).toContain("skeleton-status");
      // No fake toggle/control markup while loading.
      expect(html).not.toContain("settings-page__toggle");
    });
  });

  describe("error", () => {
    it("renders the real error message and a retry action, no fake settings", () => {
      useSettingsMock.mockReturnValue(
        makeResult({ state: "error", error: new Error("sidecar unreachable") }),
      );
      const html = render();

      expect(html).toContain("Settings Unavailable");
      expect(html).toContain("sidecar unreachable");
      expect(html).toContain("Retry");
    });
  });

  describe("success", () => {
    it("renders the real persisted Theme value", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "success", settings: SETTINGS }));
      const html = render();

      expect(html).toContain("settings-theme-select");
      expect(html).toContain("Dark Mode (SOC-IQ Standard)");
    });

    it("renders the real persisted Export Directory value", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "success", settings: SETTINGS }));
      const html = render();

      expect(html).toContain("settings-export-directory");
      expect(html).toContain("/home/analyst/output");
    });

    it("renders the VirusTotal control as disabled, with a Configured badge", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "success", settings: SETTINGS }));
      const html = render();

      expect(html).toContain("Configured");
      expect(html).toContain("disabled=\"\"");
    });

    it("shows Not configured when the backend reports no VirusTotal key", () => {
      useSettingsMock.mockReturnValue(
        makeResult({
          state: "success",
          settings: { ...SETTINGS, virustotal_api_key_configured: false },
        }),
      );
      const html = render();

      expect(html).toContain("Not configured");
    });

    it("never renders a raw VirusTotal API key value", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "success", settings: SETTINGS }));
      const html = render();

      // The command contract never returns a raw key field, but this
      // guards against any future accidental widening of that
      // contract slipping a real key value into rendered markup.
      expect(html).not.toContain("virustotal_api_key\":");
      expect(html).not.toMatch(/value="[^"]*virustotal[^"]*"/i);
    });

    it("still renders the remaining non-functional mock sections unchanged", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "success", settings: SETTINGS }));
      const html = render();

      for (const section of ["Application", "Notifications", "Security"]) {
        expect(html).toContain(section);
      }
      expect(html).toContain("read-only mock values");
    });

    it("no longer renders the retired mock Theme or VirusTotal mock controls", () => {
      useSettingsMock.mockReturnValue(makeResult({ state: "success", settings: SETTINGS }));
      const html = render();

      expect(html).not.toContain("Dark (default)");
      expect(html).not.toContain("integration-vt");
    });
  });
});
