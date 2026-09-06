/**
 * `searchCommands` tests — Phase 4G-5 Part 1 (task brief §14 items
 * 4-6).
 */

import { describe, expect, it } from "vitest";

import { searchCommands } from "./searchCommands";
import type { Command } from "./types";

const FIXTURE: readonly Command[] = [
  {
    id: "navigate:dashboard",
    label: "Dashboard",
    description: "Go to Dashboard",
    category: "navigation",
    keywords: ["dashboard"],
    path: "/dashboard",
  },
  {
    id: "navigate:analyze",
    label: "Analyze",
    description: "Go to Analyze",
    category: "navigation",
    keywords: ["analyze"],
    path: "/analyze",
  },
  {
    id: "navigate:ioc-explorer",
    label: "IOC Explorer",
    description: "Go to IOC Explorer",
    category: "navigation",
    keywords: ["ioc-explorer", "ioc explorer"],
    path: "/ioc-explorer",
  },
];

describe("searchCommands", () => {
  it("returns every command for an empty query", () => {
    expect(searchCommands(FIXTURE, "")).toEqual(FIXTURE);
  });

  it("returns every command for a whitespace-only query", () => {
    expect(searchCommands(FIXTURE, "   ")).toEqual(FIXTURE);
  });

  it("matches by label substring", () => {
    const results = searchCommands(FIXTURE, "Dash");

    expect(results.map((c) => c.id)).toEqual(["navigate:dashboard"]);
  });

  it("matches by description substring", () => {
    const results = searchCommands(FIXTURE, "Go to Analyze");

    expect(results.map((c) => c.id)).toEqual(["navigate:analyze"]);
  });

  it("matches by keyword substring", () => {
    const results = searchCommands(FIXTURE, "ioc-explorer");

    expect(results.map((c) => c.id)).toEqual(["navigate:ioc-explorer"]);
  });

  it("is case-insensitive", () => {
    const results = searchCommands(FIXTURE, "dAsHbOaRd");

    expect(results.map((c) => c.id)).toEqual(["navigate:dashboard"]);
  });

  it("returns no results when nothing matches", () => {
    expect(searchCommands(FIXTURE, "zzz-no-match")).toEqual([]);
  });

  it("preserves the input array's order among multiple matches (stable ordering)", () => {
    // "e" matches "Analyze" (label) and "IOC Explorer" (description/
    // keywords), skipping "Dashboard" — asserting the exact returned
    // order proves FIXTURE's own order survives filtering.
    const results = searchCommands(FIXTURE, "e");

    expect(results.map((c) => c.id)).toEqual([
      "navigate:analyze",
      "navigate:ioc-explorer",
    ]);
  });

  it("is deterministic across repeated calls", () => {
    const first = searchCommands(FIXTURE, "explorer").map((c) => c.id);
    const second = searchCommands(FIXTURE, "explorer").map((c) => c.id);

    expect(first).toEqual(second);
  });
});
