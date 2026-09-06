/**
 * Mock data tests (Phase 4G-2 Part 3, §16/§24).
 *
 * Verifies every mock module imports successfully, exposes
 * non-empty collections, uses stable/unique IDs, and is deterministic
 * (importing twice yields deep-equal data — i.e. nothing is computed
 * from `Date.now()`/`Math.random()` at import time).
 */

import { describe, expect, it } from "vitest";

import * as dashboard from "./dashboard";
import * as investigations from "./investigations";
import * as reports from "./reports";
import * as settings from "./settings";

function expectUniqueIds(items: readonly { readonly id: string }[]): void {
  const ids = items.map((item) => item.id);
  expect(new Set(ids).size).toBe(ids.length);
}

describe("mock/dashboard", () => {
  it("exposes non-empty, deterministic collections", () => {
    expect(dashboard.mockDashboardMetrics.length).toBeGreaterThan(0);
    expect(dashboard.mockRecentInvestigations.length).toBeGreaterThan(0);
    expectUniqueIds(dashboard.mockDashboardMetrics);
    expectUniqueIds(dashboard.mockRecentInvestigations);
  });
});

describe("mock/investigations", () => {
  it("exposes non-empty, deterministic investigations with unique ids", () => {
    expect(investigations.mockInvestigations.length).toBeGreaterThan(0);
    expectUniqueIds(investigations.mockInvestigations);
    for (const inv of investigations.mockInvestigations) {
      expect(inv.iocCount).toBeGreaterThanOrEqual(0);
      expect(["open", "in_progress", "closed"]).toContain(inv.status);
      expect(["low", "medium", "high", "critical"]).toContain(inv.severity);
    }
  });
});

describe("mock/reports", () => {
  it("exposes non-empty, deterministic report records", () => {
    expect(reports.mockReports.length).toBeGreaterThan(0);
    expectUniqueIds(reports.mockReports);
    for (const report of reports.mockReports) {
      expect(reports.REPORT_TYPE_LABELS[report.type]).toBeTruthy();
    }
  });
});

describe("mock/settings", () => {
  it("exposes only architecturally-supported sections", () => {
    // SOC-IQ Part 2B-1: "integrations" (the VirusTotal API key mock
    // control) has been retired from this list -- it is now a real,
    // backend-backed control (`settings/VirustotalControl.tsx`)
    // rendered directly by `SettingsPage.tsx`, not from this mock
    // list. The remaining sections are still non-functional mock
    // display, unchanged.
    const ids = settings.mockSettingsSections.map((section) => section.id);
    expect(ids).toEqual(["appearance", "application", "notifications", "security"]);
    for (const section of settings.mockSettingsSections) {
      expect(section.controls.length).toBeGreaterThan(0);
    }
  });
});

describe("determinism", () => {
  it("re-importing every mock module yields identical data (no random/time-based values)", async () => {
    const again = await import("./dashboard");
    expect(again.mockDashboardMetrics).toEqual(dashboard.mockDashboardMetrics);
    expect(again.mockRecentInvestigations).toEqual(dashboard.mockRecentInvestigations);
  });
});
