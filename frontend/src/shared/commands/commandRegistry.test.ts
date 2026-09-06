/**
 * Command registry tests — Phase 4G-5 Part 1 (task brief §14 items
 * 1-3, 6).
 */

import { describe, expect, it } from "vitest";

import { NAVIGATION_ITEMS } from "../../app/navigation/navigationModel";
import { COMMANDS } from "./commandRegistry";

describe("COMMANDS", () => {
  it("contains exactly one command per navigation destination", () => {
    expect(COMMANDS).toHaveLength(NAVIGATION_ITEMS.length);
  });

  it("contains the expected navigation commands", () => {
    const labels = COMMANDS.map((command) => command.label);

    expect(labels).toEqual([
      "Dashboard",
      "Analyze",
      "Investigations",
      "Reports",
      "Settings",
    ]);
  });

  it("PD-06: no longer exposes the retired standalone Risk navigation command", () => {
    const ids = COMMANDS.map((command) => command.id);
    const labels = COMMANDS.map((command) => command.label);
    const paths = COMMANDS.map((command) => command.path);

    expect(ids).not.toContain("navigate:risk");
    expect(labels).not.toContain("Risk");
    expect(paths).not.toContain("/risk");
  });

  it("PD-05: no longer exposes the retired IOC Explorer or Threat Intel navigation commands", () => {
    const ids = COMMANDS.map((command) => command.id);
    const paths = COMMANDS.map((command) => command.path);

    expect(ids).not.toContain("navigate:ioc-explorer");
    expect(ids).not.toContain("navigate:threat-intel");
    expect(paths).not.toContain("/ioc-explorer");
    expect(paths).not.toContain("/threat-intel");
  });

  it("every command id is unique", () => {
    const ids = COMMANDS.map((command) => command.id);

    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every navigation command maps to an existing route from NAVIGATION_ITEMS", () => {
    const navigationPaths = new Set(
      NAVIGATION_ITEMS.map((item) => item.path),
    );

    for (const command of COMMANDS) {
      expect(navigationPaths.has(command.path)).toBe(true);
    }
  });

  it("is deterministic — repeated reads return the same order and content", () => {
    const first = COMMANDS.map((command) => command.id);
    const second = COMMANDS.map((command) => command.id);

    expect(first).toEqual(second);
  });

  it("every command belongs to the navigation category (the only kind this skeleton defines)", () => {
    for (const command of COMMANDS) {
      expect(command.category).toBe("navigation");
    }
  });
});
