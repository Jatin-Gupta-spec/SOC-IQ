import { describe, expect, it } from "vitest";

import { DEFAULT_NAVIGATION_PATH, NAVIGATION_ITEMS } from "./navigationModel";

const EXPECTED_LABELS = [
  "Dashboard",
  "Analyze",
  "Investigations",
  "Reports",
  "Settings",
];

describe("NAVIGATION_ITEMS", () => {
  it("contains exactly the five required destinations", () => {
    expect(NAVIGATION_ITEMS).toHaveLength(5);
    expect(NAVIGATION_ITEMS.map((item) => item.label).sort()).toEqual(
      [...EXPECTED_LABELS].sort(),
    );
  });

  it("PD-05: no longer includes the retired top-level IOC Explorer or Threat Intel destinations", () => {
    const ids = NAVIGATION_ITEMS.map((item) => item.id);
    const paths = NAVIGATION_ITEMS.map((item) => item.path);
    const labels = NAVIGATION_ITEMS.map((item) => item.label);

    expect(ids).not.toContain("ioc-explorer");
    expect(ids).not.toContain("threat-intel");
    expect(paths).not.toContain("/ioc-explorer");
    expect(paths).not.toContain("/threat-intel");
    expect(labels).not.toContain("IOC Explorer");
    expect(labels).not.toContain("Threat Intel");
  });

  it("PD-06: no longer includes the retired top-level standalone Risk destination", () => {
    const ids = NAVIGATION_ITEMS.map((item) => item.id);
    const paths = NAVIGATION_ITEMS.map((item) => item.path);
    const labels = NAVIGATION_ITEMS.map((item) => item.label);

    expect(ids).not.toContain("risk");
    expect(paths).not.toContain("/risk");
    expect(labels).not.toContain("Risk");
  });

  it("has a stable, unique id per destination", () => {
    const ids = NAVIGATION_ITEMS.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) {
      expect(id).toMatch(/^[a-z][a-z-]*[a-z]$/);
    }
  });

  it("has a unique canonical path per destination", () => {
    const paths = NAVIGATION_ITEMS.map((item) => item.path);
    expect(new Set(paths).size).toBe(paths.length);
    for (const path of paths) {
      expect(path.startsWith("/")).toBe(true);
    }
  });

  it("gives every destination an icon component", () => {
    for (const item of NAVIGATION_ITEMS) {
      expect(typeof item.icon).toBe("function");
    }
  });

  it("puts Settings alone in the secondary group and everything else in primary", () => {
    const secondary = NAVIGATION_ITEMS.filter((item) => item.group === "secondary");
    const primary = NAVIGATION_ITEMS.filter((item) => item.group === "primary");

    expect(secondary.map((item) => item.id)).toEqual(["settings"]);
    expect(primary).toHaveLength(4);
  });

  it("has no duplicate destinations", () => {
    const labels = NAVIGATION_ITEMS.map((item) => item.label);
    expect(new Set(labels).size).toBe(labels.length);
  });
});

describe("DEFAULT_NAVIGATION_PATH", () => {
  it("points at an actual navigation item's path", () => {
    expect(NAVIGATION_ITEMS.some((item) => item.path === DEFAULT_NAVIGATION_PATH)).toBe(
      true,
    );
  });

  it("defaults to Dashboard", () => {
    const dashboard = NAVIGATION_ITEMS.find((item) => item.id === "dashboard");
    expect(dashboard?.path).toBe(DEFAULT_NAVIGATION_PATH);
  });
});
