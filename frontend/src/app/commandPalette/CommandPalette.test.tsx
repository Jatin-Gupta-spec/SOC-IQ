/**
 * `CommandPalette` static/structural tests — Phase 4G-5 Part 1.
 *
 * `renderToStaticMarkup`, no jsdom — matches
 * `RestartExhaustedNotification.test.tsx`'s own static/live split.
 * Interaction (typing, arrow keys, Enter, clicking) needs a live DOM
 * and lives in `CommandPalette.live.test.tsx` instead.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CommandPalette } from "./CommandPalette";
import type { Command } from "../../shared/commands/types";

const FIXTURE_COMMANDS: readonly Command[] = [
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
];

describe("CommandPalette", () => {
  it("renders nothing when closed", () => {
    const html = renderToStaticMarkup(
      <CommandPalette
        open={false}
        commands={FIXTURE_COMMANDS}
        onClose={() => {}}
        onNavigate={() => {}}
      />,
    );

    expect(html).toBe("");
  });

  it("renders a labeled dialog when open", () => {
    const html = renderToStaticMarkup(
      <CommandPalette
        open={true}
        commands={FIXTURE_COMMANDS}
        onClose={() => {}}
        onNavigate={() => {}}
      />,
    );

    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('aria-label="Command palette"');
  });

  it("renders an accessibly-labeled search input", () => {
    const html = renderToStaticMarkup(
      <CommandPalette
        open={true}
        commands={FIXTURE_COMMANDS}
        onClose={() => {}}
        onNavigate={() => {}}
      />,
    );

    expect(html).toContain('aria-label="Search commands"');
  });

  it("renders every command as a listbox option", () => {
    const html = renderToStaticMarkup(
      <CommandPalette
        open={true}
        commands={FIXTURE_COMMANDS}
        onClose={() => {}}
        onNavigate={() => {}}
      />,
    );

    expect(html).toContain('role="listbox"');
    expect((html.match(/role="option"/g) ?? []).length).toBe(2);
    expect(html).toContain("Dashboard");
    expect(html).toContain("Analyze");
  });

  it("renders an accessible close control for the backdrop", () => {
    const html = renderToStaticMarkup(
      <CommandPalette
        open={true}
        commands={FIXTURE_COMMANDS}
        onClose={() => {}}
        onNavigate={() => {}}
      />,
    );

    expect(html).toContain('aria-label="Close command palette"');
  });

  it("renders an empty state when no commands are provided", () => {
    const html = renderToStaticMarkup(
      <CommandPalette
        open={true}
        commands={[]}
        onClose={() => {}}
        onNavigate={() => {}}
      />,
    );

    expect(html).toContain("No matching commands");
  });
});
