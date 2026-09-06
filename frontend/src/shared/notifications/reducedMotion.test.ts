/**
 * Reduced-motion structural test — Phase 4G-4 Part 1, task brief §10.
 *
 * No browser/Tauri runtime is available in this environment to render
 * `@media (prefers-reduced-motion: reduce)` and read computed styles
 * (jsdom does not implement CSS media-feature evaluation), so this is
 * a structural check rather than a rendered-behavior one: it confirms
 * (a) the component composes the existing `.transition-fade` motion
 * utility rather than an animation of its own, and (b) that utility's
 * source still contains the existing reduced-motion rule this
 * checkpoint deliberately did not duplicate or bypass. Genuine
 * rendered-behavior verification of `prefers-reduced-motion` would
 * need a real browser/Tauri environment — see the final report's
 * Informational findings.
 *
 * Reads the two source files via Node's built-in `fs` (available in
 * the Vitest/Node process this test already runs in — not a new
 * dependency). Loaded through a dynamic `import()` with a single
 * `@ts-expect-error`, rather than adding the `@types/node` package
 * this project doesn't otherwise depend on just for this one test
 * file's two reads.
 */

import { beforeAll, describe, expect, it } from "vitest";

let motionCss = "";
let componentSource = "";

beforeAll(async () => {
  // @ts-expect-error -- no @types/node in this project; see module doc.
  const fs = await import(/* @vite-ignore */ "node:fs");
  motionCss = fs.readFileSync("src/styles/motion.css", "utf-8");
  componentSource = fs.readFileSync(
    "src/shared/notifications/RestartExhaustedNotification.tsx",
    "utf-8",
  );
});

describe("reduced motion", () => {
  it("the shared motion foundation still defines the reduced-motion rule this component relies on", () => {
    expect(motionCss).toContain("prefers-reduced-motion: reduce");
    expect(motionCss).toContain(".transition-fade");
  });

  it("the component composes the existing .transition-fade utility rather than a second motion system", () => {
    expect(componentSource).toContain("transition-fade");
    // No component-local @keyframes / new duration-property value —
    // this component introduces no second motion token system.
    expect(componentSource).not.toContain("@keyframes");
    expect(componentSource).not.toContain("transition-duration");
  });
});
